# Minda SOR Analyzer

FastAPI service that ingests a Statement of Requirement PDF and returns
structured **section analysis** (raw content blocks) and **semantic analysis**
(Ask / Requirement / Recommendation / Informational classification per
INCOSE & ISO 29148) in a single JSON response.

## Repo layout

```
uno-minda/
├── minda-sor-rag/      ← the deliverable: FastAPI backend
│   ├── app/            ← API + services
│   ├── knowledge_base/ ← INCOSE rules + ISO 29148 clauses
│   ├── storage/        ← runtime data (uploads, results, exports, chroma)
│   ├── imp-files/      ← API.md, ui.md, curls.md, SPEC.md (handoff docs)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── run.py          ← uvicorn entrypoint
│
├── minda-ui/           ← demo React+Vite app (smoke-test only)
└── README.md           ← this file
```

## Quick start

### 1. Prerequisites

| Tool | Version | Required for |
|---|---|---|
| Python | 3.11 | Backend |
| Node.js | 18+ | Demo UI only |
| OpenAI API key (or compatible local LLM) | — | LLM classification + embeddings |
| Native libs: `pango`, `cairo`, `gdk-pixbuf`, `libffi` | — | **Only for PDF export** (`POST /export/pdf` and `/jobs/{id}/export/pdf`) |

### Why the native libs?
The PDF report generator uses [WeasyPrint](https://weasyprint.org/), which is
a Python wrapper around system C libraries — Pango (text layout), Cairo (2D
rendering), GDK-PixBuf (image loading), libffi (FFI). These are **not Python
packages**; they're shared libraries the OS needs to provide. WeasyPrint
imports them at runtime.

If you don't need server-rendered PDF reports (you can generate them
client-side from the JSON response with `jspdf` / `react-pdf` etc.), you can
**skip this step entirely**. Excel, CSV, JSON exports work without it.

### Install native libs

**macOS** (Homebrew):
```bash
brew install pango cairo gdk-pixbuf libffi
```

**Debian / Ubuntu**:
```bash
sudo apt-get install -y \
  libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev libcairo2
```

**Fedora / RHEL**:
```bash
sudo dnf install -y pango cairo gdk-pixbuf2 libffi-devel
```

**Windows**:
WeasyPrint on Windows needs GTK3. The maintained path is via MSYS2 or by
running the backend inside WSL2 / Docker (recommended). See the
[WeasyPrint Windows guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows).

**Docker (all platforms)**:
The `Dockerfile` already installs the right libs on Debian — no host setup
needed if you containerize. See the [Docker section](#docker) below.

### 2. Backend setup

```bash
cd minda-sor-rag
```

**macOS / Linux:**
```bash
python3.11 -m venv ../minda-env
source ../minda-env/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
py -3.11 -m venv ..\minda-env
..\minda-env\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Windows (cmd):**
```cmd
py -3.11 -m venv ..\minda-env
..\minda-env\Scripts\activate.bat
pip install -r requirements.txt
```

> First install downloads **~2 GB** (Docling layout/OCR models + PyTorch + ONNX runtime). One-time. Subsequent runs are instant.

### 3. Configure `.env`

Copy the sample:

```bash
# macOS / Linux
cp .env.example .env

# Windows (cmd / PowerShell)
copy .env.example .env
```

Open `minda-sor-rag/.env` in any editor and set your OpenAI API key:

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...your-key...
LLM_MODEL=gpt-4o-mini

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small

VECTOR_DB=chroma
HOST=0.0.0.0
PORT=8001
```

> ⚠️ `.env` is gitignored — never commit a real key.

### 4. Run the backend

```bash
python run.py
```

You'll see:
```
INFO:     Uvicorn running on http://0.0.0.0:8001
INFO:     Application startup complete.
```

Verify:
```bash
curl http://localhost:8001/api/v1/health
# → {"status":"ok"}
```

Interactive Swagger UI: <http://localhost:8001/docs>

### 5. (Optional) Run the demo UI

```bash
cd minda-ui
npm install
npm run dev
# → http://localhost:8000
```

The UI is **not the production frontend** — it's a smoke-test surface. The
real frontend will be built by a separate engineer using only the API.

## How to use the API

### One call, full analysis

```bash
curl -F "file=@your-doc.pdf" http://localhost:8001/api/v1/analyze
```

Response (synchronous, takes 30 s – 5 min):

```json
{
  "filename": "your-doc.pdf",
  "total_sections": 93,
  "total_statements": 659,
  "sections": [
    {
      "section_name": "Supplier Scope",
      "heading_only": false,
      "blocks": [...],          // Section Analysis: raw content blocks
      "statements": [...],      // Semantic Analysis: classified statements
      "requirements": 7, "asks": 5, "recommendations": 2, "informational": 3
    },
    ...
  ]
}
```

UI consumers:
- Render **Section Analysis** from `section.blocks[]` (discriminator: `block.type`)
- Render **Semantic Analysis** from `section.statements[]` (grouped by `classification`)

Full endpoint reference: [`minda-sor-rag/imp-files/ui.md`](minda-sor-rag/imp-files/ui.md) and
[`minda-sor-rag/API.md`](minda-sor-rag/API.md).

Copy-paste curl recipes: [`minda-sor-rag/imp-files/curls.md`](minda-sor-rag/imp-files/curls.md).

## Architecture (TL;DR)

```
PDF
 ├─ Docling (IBM)          — layout-aware extraction
 ├─ section_splitter       — typed RawBlock schema, marker preservation
 ├─ classifier             — RAG (Chroma) + LLM batch classify, parallel
 └─ rule_engine            — INCOSE deterministic quality checks
```

The pipeline is **synchronous** by design — one `POST /analyze` runs everything
end-to-end and returns the full result. No job IDs or polling needed for the
stateless path (`POST /analyze`); a legacy stateful path (`POST /upload` +
`/jobs/*`) exists for operator debugging only.

## Switching providers

Everything provider-related is in `.env`. Common preset blocks:

**Ollama (fully self-hosted, free)**
```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:14b
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

**vLLM / LM Studio**
```bash
LLM_BASE_URL=http://localhost:8000/v1
LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct
```

**OpenRouter**
```bash
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-...
LLM_MODEL=anthropic/claude-3.5-sonnet
```

**Pinecone (cloud vector DB)**
```bash
VECTOR_DB=pinecone
PINECONE_API_KEY=pcsk-...
PINECONE_INDEX=sor-incose-iso
PINECONE_DIMENSION=1536
```

⚠️ If you change `EMBEDDING_MODEL`, delete `storage/chroma_data/` before restart
or you'll get a vector-dimension mismatch.

## Operational knobs (also `.env`)

| Variable | Default | Effect |
|---|---|---|
| `BATCH_SIZE` | `10` | Statements per LLM call |
| `MAX_PARALLEL_BATCHES` | `6` | Concurrent LLM calls during classify |
| `MAX_PDF_SIZE_MB` | `50` | Upload size cap |
| `MAX_RETAINED_JOBS` | `20` | How many persisted jobs to keep (stateful path); `0` = unlimited |
| `RETRIEVAL_TOP_K` | `3` | Number of INCOSE/ISO docs retrieved per batch |

## Docker

```bash
cd minda-sor-rag
docker build -t minda-sor-rag .
docker run -p 8001:8000 --env-file .env minda-sor-rag
```

The Dockerfile already installs the weasyprint native libs.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `404 Not Found` on `/api/v1/jobs/{id}/sections/raw/...` | Section name must be URL-encoded; slashes in names work because of the `:path` converter |
| `503` on `/export/pdf` | `brew install pango cairo gdk-pixbuf libffi` then restart |
| `Connection refused` | Backend isn't running — `python run.py` in `minda-sor-rag/` |
| `Chroma collection dimension mismatch` | You changed `EMBEDDING_MODEL` — delete `storage/chroma_data/` |
| Hangs > 5 min | Pipeline running — Docling layout inference + LLM batches; normal for large PDFs |

## Storage layout (auto-created)

```
minda-sor-rag/storage/
├── uploads/      raw uploaded PDFs (stateful path only)
├── results/      AnalysisResult JSON per job (stateful path only)
├── exports/      .xlsx / .pdf / .csv per job
└── chroma_data/  vector index (re-seeds on first startup)
```

`POST /analyze` (stateless) writes nothing — it uses a temp file that's
deleted as soon as the response is returned.

## Documents

- [`CLAUDE.md`](CLAUDE.md) — guidance for future Claude Code sessions
- [`minda-sor-rag/API.md`](minda-sor-rag/API.md) — full API reference
- [`minda-sor-rag/imp-files/ui.md`](minda-sor-rag/imp-files/ui.md) — UI engineer's guide
- [`minda-sor-rag/imp-files/curls.md`](minda-sor-rag/imp-files/curls.md) — copy-paste API test recipes
- [`minda-sor-rag/imp-files/SPEC.md`](minda-sor-rag/imp-files/SPEC.md) — original 1248-line build plan (historical reference)
