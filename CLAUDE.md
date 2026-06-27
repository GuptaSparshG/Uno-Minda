# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A FastAPI service that ingests an SOR (Statement of Requirement) PDF, runs a layout-aware extraction + RAG-classification pipeline, and exposes two parallel response endpoints — **section analysis** (raw, untouched content) and **semantic analysis** (Ask/Requirement classification per INCOSE & ISO 29148). The owner of this repo delivers the **API**; a separate engineer consumes it from their own UI. The `minda-ui/` directory is a throwaway demo for smoke-testing — do **not** treat it as the production frontend.

## Repository layout

```
uno-minda/
├── minda-sor-rag/          ← the deliverable: FastAPI backend
│   ├── app/
│   │   ├── api/routes.py   ← endpoint definitions
│   │   ├── services/
│   │   │   ├── pdf_extractor.py    ← Docling wrapper (layout-aware)
│   │   │   ├── section_splitter.py ← Docling items → RawBlock schema
│   │   │   ├── classifier.py       ← RAG + LLM batch classify, parallel
│   │   │   ├── rule_engine.py      ← INCOSE deterministic checks
│   │   │   ├── pipeline.py         ← orchestrator
│   │   │   ├── vector_store.py     ← Chroma / Pinecone abstraction
│   │   │   ├── embeddings.py       ← OpenAI / sentence-transformers factory
│   │   │   ├── llm.py              ← OpenAI client (any /v1-compatible endpoint)
│   │   │   ├── report_excel.py     ← .xlsx generator
│   │   │   └── report_pdf.py       ← weasyprint HTML→PDF (often 404s on macOS)
│   │   ├── schemas.py      ← all Pydantic models (the API contract)
│   │   ├── config.py       ← Settings (env-driven, all knobs)
│   │   └── main.py         ← FastAPI app + lifespan (Chroma seed)
│   ├── knowledge_base/     ← INCOSE rules + ISO 29148 clauses (seeded to Chroma)
│   ├── storage/            ← runtime state (uploads, results, exports, chroma_data)
│   ├── API.md              ← reference doc for the UI engineer (hand this over)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── run.py              ← uvicorn entrypoint (reload=False intentionally)
│
├── minda-ui/               ← demo React+Vite app — DO NOT over-invest here
├── minda-env/              ← shared Python venv (Python 3.11)
├── SPEC.md                 ← original 1248-line build plan (kept for reference, stale)
└── HVAC-Panel-SOR.pdf      ← canonical test PDF
```

## Run / dev / test commands

```bash
# Backend (the deliverable)
cd minda-sor-rag
source ../minda-env/bin/activate
python run.py                       # uvicorn :8001, no auto-reload by design

# Quick smoke test (in another shell)
curl http://localhost:8001/api/v1/health
curl -F "file=@../HVAC-Panel-SOR.pdf" http://localhost:8001/api/v1/upload
                                    # synchronous, takes 90–180 s end-to-end

# OpenAPI / Swagger (share with the UI engineer)
open http://localhost:8001/docs

# Demo UI (optional, just for visual sanity)
cd ../minda-ui
npm install                         # first time only
npm run dev                         # http://localhost:5173, proxies /api → :8001
npm run build                       # TS check + production bundle (no lint configured)
```

There is no formal test suite — verify changes by running the smoke upload end-to-end and inspecting `storage/results/<job_id>.json`. The pipeline prints the full result JSON to stdout between `=====` banners at the end of every analysis, so the backend terminal IS the test output.

## Architecture (the big picture)

The pipeline is **synchronous** and single-process. One `POST /upload` runs everything end-to-end before responding, which is why uploads take minutes.

```
PDF
 │
 ├─ pdf_extractor.py        — Docling (IBM) layout-aware extraction
 │    emits flat items:     SectionHeader / Text / List / Table / Picture
 │
 ├─ section_splitter.py     — pure mapper from Docling items → RawBlock schema
 │    + _merge_duplicates() collapses TOC entries into their body counterparts
 │      (e.g. "11- GD&T" merges into "GD&T")
 │
 ├─ classifier.py           — RAG (Chroma top-3) + OpenAI chat completion
 │    • ThreadPoolExecutor: MAX_PARALLEL_BATCHES (default 6) batches in flight
 │    • Section name + source_type are passed to the LLM as semantic context
 │    • Keyword-fallback path runs whenever the LLM call fails or returns bad JSON
 │
 ├─ rule_engine.py          — INCOSE R2/R3/R4/R5/R7/R10/R14 deterministic checks
 │
 └─ pipeline.py             — composes all of the above, writes:
        storage/results/<job>.json    full AnalysisResult
        storage/exports/<job>.xlsx    multi-sheet workbook
        storage/exports/<job>.pdf     weasyprint report (often missing locally)
```

The classifier and rule_engine are **independent**: the LLM does Ask/Req/Rec/Info + ISO category, the rule_engine does the 0-100 quality score and rule violations. Both run for every statement; their outputs are joined in `pipeline.py`.

`config.py` is the single source of truth for everything that switches behavior (LLM provider via `LLM_BASE_URL`, vector DB via `VECTOR_DB=chroma|pinecone`, embedding provider, batch sizes). Legacy `OPENAI_API_KEY` is preserved as a fallback for `LLM_API_KEY` and `EMBEDDING_API_KEY` — see `Settings.model_post_init`.

## The deliverable: two endpoints

These are the contract the UI engineer builds against. Both take the same `(job_id, section_name)`. **`section_name` is the EXACT heading text from the PDF, URL-encoded** (spaces, `&`, `(`, etc. — keep them).

```
GET /api/v1/jobs/{id}/sections/{name}/raw       ← Section Analysis (untouched content)
GET /api/v1/jobs/{id}/sections/{name}/semantic  ← Semantic Analysis (Ask/Req groups)
```

Full reference in `minda-sor-rag/API.md` — that file is the deliverable for the UI engineer, keep it current when you touch endpoints or schema shapes.

## Things that have tripped us up before

- **`reload=True` causes hangs** under long synchronous requests — `run.py` deliberately keeps `reload=False`. Don't switch it back.
- **Docling first call downloads ~500 MB** of layout/OCR weights. Subsequent calls in the same process are fast. The lazy init lives in `pdf_extractor._converter()`.
- **`Chroma` collection embedding dimension** is frozen on first seed — if you change `EMBEDDING_MODEL`, delete `storage/chroma_data/` before restarting or you'll get a dim-mismatch crash.
- **Section names are user-facing identifiers** — they're used directly as URL path segments. Don't normalize / lowercase / title-case them.
- **`heading_only: true` sections are common** — Docling emits parent SectionHeaders that have no direct body content (their content lives under child headings). Keep them in responses.
- **weasyprint 404s** locally because pango/cairo aren't installed via brew. The pipeline catches that and the job still completes — only the PDF report is missing.
- **macOS `find` warning**: don't recursively search `~/Library` etc.; scope finds to project dirs.

## Behavioral preferences (from memory)

- This codebase's owner ships the **API**, not the UI. Default any change toward affecting `app/services/` and `app/api/`, not `minda-ui/`.
- **Never put model names, provider names, or upsell CTAs in any UI surface** (even in the demo).
- The UI's primary surface is **Section Analysis** (raw structure) and **Semantic Analysis** (Ask/Req). INCOSE quality scoring, ISO categories, and 4-way classification stay backend-only — surface them only if explicitly asked.
- **Act on evidence, don't poll the user with multi-choice questions** — read the data, hit the endpoints, then propose or fix.

## Memory location
Project-specific memory lives at `/Users/sparsh/.claude/projects/-Users-sparsh-Desktop-uno-minda/memory/`. Read its `MEMORY.md` for accumulated context (user role, feedback preferences) before non-trivial work.
