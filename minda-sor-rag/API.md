# Minda SOR Analyzer — API Reference

FastAPI service that ingests a Statement of Requirement PDF, extracts its
structure with layout-aware parsing, and classifies every statement as
**Ask / Requirement / Recommendation / Informational** per INCOSE & ISO 29148.

- **Base URL** (dev): `http://localhost:8001/api/v1`
- **CORS**: open (`*`) — any web origin can call directly. No proxy needed.
- **Interactive docs**: `http://localhost:8001/docs` (Swagger) and `/redoc`
- **All responses**: JSON unless noted (`/export/*` returns the file).

## How the pipeline works

```
PDF
 ├─ Docling (IBM)                — layout-aware extraction
 │    • SectionHeaderItem        → section boundaries (real headings, not font heuristics)
 │    • TextItem                 → paragraph blocks
 │    • ListItem                 → bullet_list blocks (grouped)
 │    • TableItem                → table blocks (headers + rows preserved)
 │    • PictureItem              → noted as "diagram not analyzed"
 │
 ├─ Section splitter             — flat mapper from Docling items → RawBlocks
 │    + Duplicate-section merge  (TOC entries collapse into body sections)
 │
 ├─ Classifier                   — RAG (ChromaDB / Pinecone) + OpenAI batch
 │    • Per-section context, source-type aware
 │    • Parallel batches (MAX_PARALLEL_BATCHES from .env)
 │
 └─ Rule engine                  — deterministic INCOSE R2/R3/R4/R5/R7/R10/R14 checks
```

**Layout parsing**: powered by [Docling](https://github.com/DS4SD/docling). No
hand-tuned font/score heuristics for heading detection. The first upload after
a server restart triggers Docling's model load (~5–10 s); subsequent uploads
skip that cost.

---

## Primary endpoint (the deliverable)

| Method | Path | Purpose |
|---|---|---|
| **POST** | **`/analyze`** | **PDF in → full `AnalysisResult` JSON. Stateless.** |
| GET  | `/health` | Liveness check |

`/analyze` is the only endpoint a UI consumer needs. It takes the PDF,
runs the full pipeline, and returns everything (raw content blocks +
semantic classification) in a single response. **No `job_id`, no
server-side persistence** — the UI is responsible for caching.

## Optional legacy endpoints

The server also exposes a stateful path that persists results to disk for
the operator's own testing. Kept for back-compat / debugging:

| Method | Path | Purpose |
|---|---|---|
| POST | `/upload` | Like `/analyze` but writes to `storage/`, returns just a `job_id` |
| GET | `/jobs` | List recent persisted jobs |
| DELETE | `/jobs/{id}` | Delete a persisted job's files |
| GET | `/jobs/{id}/summary` | Aggregate counts + rule violations |
| GET | `/jobs/{id}/sections` | Per-section roll-up (counts only) |
| GET | `/jobs/{id}/sections/raw/{name}` | Section Analysis from persisted job |
| GET | `/jobs/{id}/sections/semantic/{name}` | Semantic Analysis from persisted job |
| GET | `/jobs/{id}/results` | Full payload from persisted job |
| GET | `/jobs/{id}/export/{excel,csv,json,pdf}` | File downloads |

> **Storage retention** — when `/upload` is used, the server auto-prunes
> persisted jobs beyond the latest 20. Configure via `MAX_RETAINED_JOBS`
> env var (`0` = keep forever). The `/analyze` path bypasses this entirely.

> Paths above are relative to the base URL. Full URL = `BASE_URL` + `path`.

---

## Endpoints — detail

### `GET /health`
Liveness probe. Returns `200`.

```json
{ "status": "ok" }
```

---

### `POST /upload`
Upload a PDF and synchronously run the full analysis pipeline.

**Request**: `multipart/form-data`
- Field name: `file`
- Type: PDF, max 50 MB

**Response (200)**:
```json
{
  "job_id": "780ea62d-f62d-4724-8a65-f7f8f63cc361",
  "filename": "HVAC-Panel-SOR.pdf",
  "status": "completed"
}
```

**Errors**:
- `400` — not a PDF / too large / malformed PDF
- `500` — pipeline crashed mid-flight

⚠️ Synchronous endpoint. Takes **30 seconds to 5 minutes** depending on PDF
size. The browser/HTTP client must keep the connection open. There is no
polling fallback — when the call returns, all artifacts are on disk.

---

### `GET /jobs`
List every completed analysis on disk, newest first.

**Response (200)**:
```json
{
  "jobs": [
    {
      "job_id": "780ea62d-...",
      "filename": "HVAC-Panel-SOR.pdf",
      "total_statements": 494,
      "total_sections": 30,
      "requirements_count": 224,
      "asks_count": 92,
      "created_at": "2026-06-26T18:14:52"
    }
  ]
}
```

`created_at` is the local time when the result JSON was written (ISO 8601,
no timezone suffix).

---

### `GET /jobs/{job_id}/summary`
Aggregate counts + rule-violation totals for a single job.

**Response (200)**:
```json
{
  "job_id": "780ea62d-...",
  "filename": "HVAC-Panel-SOR.pdf",
  "total_statements": 494,
  "total_sections": 30,
  "requirements_count": 224,
  "recommendations_count": 64,
  "asks_count": 92,
  "informational_count": 114,
  "statements_with_issues": 419,
  "avg_quality_score": 89.0,
  "rule_violation_counts": { "R7": 358, "R2": 150, "R3": 59, "R10": 17, "R5": 13, "R14": 10, "R4": 1 }
}
```

`rule_violation_counts` keys are INCOSE rule IDs:
- `R2` — Active Voice
- `R3` — Unambiguous (weak/vague words found)
- `R4` — Complete (TBD/TBC placeholders)
- `R5` — Singular (multiple "shall" in one statement)
- `R7` — Verifiable (no measurable criteria)
- `R10` — No Escape Clauses
- `R14` — Positive Statement

---

### `GET /jobs/{job_id}/sections`
Per-section roll-up (no statement text).

```json
{
  "job_id": "780ea62d-...",
  "sections": [
    {
      "section_name": "STATEMENT OF REQUIREMENT",
      "total": 78,
      "requirements": 20,
      "recommendations": 1,
      "asks": 18,
      "informational": 28,
      "avg_quality_score": 89.3
    }
  ]
}
```

Sections appear in **document order**. The `section_name` is the **exact
heading text** as it appears in the source PDF (preserved verbatim — no
title-casing, no trimming of leading numbers).

---

### `GET /jobs/{job_id}/sections/raw/{section_name}`
**The Section Analysis view** — original PDF content for a section, untouched.
No classification applied. Use this when the user wants to see what the
document actually says.

`section_name` must be URL-encoded (it can contain spaces, `&`, `(`, etc.).

Block types come straight from Docling's layout model:
- **`heading`** — a sub-heading inside the section (Docling SectionHeader at a deeper level)
- **`paragraph`** — a TextItem from Docling
- **`bullet_list`** — consecutive ListItems grouped together
- **`numbered_list`** — same as bullet_list when items are numbered (rare in this codebase — most lists come back as bullet_list)
- **`table`** — a TableItem with structured rows and headers

**Response (200)**:
```json
{
  "job_id": "...",
  "section_name": "STATEMENT OF REQUIREMENT",
  "heading_only": false,
  "blocks": [
    { "type": "heading", "text": "Introduction to Statement of Requirement (SOR):" },
    { "type": "paragraph", "text": "The purpose of this document is to assist..." },
    { "type": "bullet_list", "items": ["Scope of supply will be as per BOM…"] },
    { "type": "numbered_list", "items": ["First item…", "Second item…"] },
    { "type": "table", "headers": ["Parameter", "Value"], "rows": [["Voltage", "12 V"]] }
  ]
}
```

**`heading_only: true`** means the heading appears in the document but no
body content follows it (typically a TOC entry that doesn't map to a body
section). Render it as a navigation marker.

**Block types** (discriminated union — UIs should switch on `type`):

| `type`           | Other fields           |
|------------------|------------------------|
| `heading`        | `text: string` — a sub-heading inside the section |
| `paragraph`      | `text: string` |
| `bullet_list`    | `items: string[]` |
| `numbered_list`  | `items: string[]` |
| `table`          | `headers: string[]`, `rows: string[][]` |

Blocks are emitted in **document order**.

---

### `GET /jobs/{job_id}/sections/semantic/{section_name}`
**The Semantic Analysis view** — classified statements for the section,
grouped by class.

**Response (200)**:
```json
{
  "job_id": "...",
  "section_name": "STATEMENT OF REQUIREMENT",
  "totals": {
    "REQUIREMENT": 21,
    "RECOMMENDATION": 2,
    "ASK": 29,
    "INFORMATIONAL": 26
  },
  "groups": {
    "REQUIREMENT": [ AnalyzedStatement, ... ],
    "ASK":         [ AnalyzedStatement, ... ],
    "RECOMMENDATION": [ ... ],
    "INFORMATIONAL":  [ ... ]
  }
}
```

`AnalyzedStatement` shape:

```ts
{
  id: string,                       // "SOR-001" etc., globally unique within a job
  section: string,                  // matches the section_name
  text: string,                     // the statement
  source_type: "text" | "bullet" | "numbered" | "table_row",
  classification: "REQUIREMENT" | "RECOMMENDATION" | "ASK" | "INFORMATIONAL",
  classification_reason: string,    // ≤20 word LLM explanation; can be empty
  iso_category: string,             // "Functional" | "Performance" | "Safety" | …
  obligation_keyword: string,       // "shall" | "must" | "should" | "will" | "may" | "none"
  quality_score: number,            // 0–100
  ambiguous_words: string[],
  escape_clauses: string[],
  placeholders: string[],           // ["TBD", "TBC", …]
  is_passive_voice: boolean,
  is_atomic: boolean,
  verifiability: "PASS" | "WARN" | "FAIL",
  is_negative: boolean,
  violated_rules: string[],         // INCOSE rule IDs that this statement violates
  suggested_action: string
}
```

---

### `GET /jobs/{job_id}/results`
**Full payload** — every section with both raw blocks AND classified
statements. Heavy (300–500 KB for a typical SOR).

Useful if a UI wants a single fetch and indexes client-side.

**Response (200)**: an `AnalysisResult`:

```ts
{
  job_id: string,
  filename: string,
  total_statements: number,
  total_sections: number,
  sections: SectionResult[]
}

SectionResult {
  section_name: string,
  heading_only: boolean,
  blocks: RawBlock[],               // same shape as /sections/raw/{name}
  total: number,
  requirements: number,
  recommendations: number,
  asks: number,
  informational: number,
  avg_quality_score: number,
  statements: AnalyzedStatement[]
}
```

---

### `GET /jobs/{job_id}/export/excel`
Returns the `.xlsx` workbook (multi-sheet: Summary, All Statements, one
sheet per section).
`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

### `GET /jobs/{job_id}/export/csv`
Flat CSV — one row per statement. Columns:
`id, section, classification, iso_category, obligation, quality_score, verifiability, violated_rules, classification_reason, suggested_action, text`.
`Content-Type: text/csv`

### `GET /jobs/{job_id}/export/json`
Raw JSON file download (same payload as `/results`).
`Content-Type: application/json`

### `GET /jobs/{job_id}/export/pdf`
PDF report. **Returns 404 if weasyprint system libs aren't installed** on
the server (`brew install pango cairo gdk-pixbuf`).

All `/export/*` endpoints return `404` if the job doesn't exist or the
artifact was never produced.

---

## Conventions & gotchas

1. **Section name as identifier** — the URL-encoded exact heading text. Stable
   for a given source PDF. Use `encodeURIComponent` on the client.
2. **Order matters** — `sections`, `blocks`, `statements`, and `groups[CLASS]`
   are all returned in document order. Don't sort on the client unless the
   user picks a different sort.
3. **`source_type` mirrors `RawBlock.type`** — `"bullet"` statements came
   from `bullet_list` blocks, `"table_row"` statements came from `table`
   blocks, etc. Use this when joining the two views.
4. **`classification_reason`** is short and meant for tooltips. It can be
   empty if the LLM didn't return a reason for that statement.
5. **`heading_only` sections** — keep showing them in lists; they're useful
   navigation markers. They have empty `blocks` and `statements`.
6. **Duplicate section detection** — the server already merges TOC duplicates
   (e.g. `"11- GD&T"` + `"GD&T"` → one section). Each `section_name` you see
   is unique.
7. **Section count is high (typically 80–100 for a 30-page SOR)** — that's
   because Docling treats every sub-heading as a real section, not a buried
   paragraph. The UI should plan for a scrollable / searchable section list,
   not a fixed tabbed layout.
8. **Heading-only sections are common** — many sections (e.g. `"Phased Process"`,
   `"STATEMENT OF REQUIREMENT"`) are pure parent headings with no direct body
   content; their content lives under the child headings that follow. Display
   them in the list but show a "no body content" hint when opened.

---

## Operational

- **Storage**: `storage/results/{job_id}.json` (full result), `storage/uploads/{job_id}.pdf`, `storage/exports/{job_id}.{xlsx,csv,pdf}`.
- **Env vars** (server-side, in `.env`): `LLM_API_KEY`, `LLM_MODEL`, `VECTOR_DB`, `CHROMA_DIR`, `MAX_PARALLEL_BATCHES`, `BATCH_SIZE`, `HOST`, `PORT`, `MAX_PDF_SIZE_MB`.
- **Logging**: at end of each `/upload`, the server prints the full result
  JSON between `=====` banners on stdout for inspection.

## Status code summary

| Endpoint family | 200 | 400 | 404 | 500 |
|---|---|---|---|---|
| `/health`, `/jobs` | always | – | – | – |
| `/upload` | success | bad PDF / too large | – | pipeline crash |
| `/jobs/{id}/*` | success | – | job or section not found | – |
| `/jobs/{id}/export/*` | file | – | artifact missing | – |
