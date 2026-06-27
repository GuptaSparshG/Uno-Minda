# SOR Analyzer — UI Engineer Guide

Everything you need to build the frontend. Read this once, top to bottom.

---

## 1. The contract — one endpoint

```
POST  http://<host>:8001/api/v1/analyze
      multipart/form-data
      field: file=<PDF, ≤ 50 MB>
      ↓
      synchronous, blocks 30 s – 5 min
      ↓
{ filename, total_sections, sections: [...] }   ← JSON response
```

That's it. Cache the response on your side (localStorage / IndexedDB / your backend). The server keeps no record of the job.

Bonus liveness probe: `GET /api/v1/health` → `{"status":"ok"}`.

**CORS is open** (`*`) and **no auth** is required.

> **OpenAPI spec** at `http://<host>:8001/openapi.json` — generate a typed client in one line:
> ```bash
> npx openapi-typescript http://<host>:8001/openapi.json -o api.d.ts
> ```

---

## 2. Response shape — one JSON, two angles

```json
{
  "filename": "HVAC-Panel-SOR.pdf",
  "total_statements": 491,
  "total_sections": 93,
  "sections": [
    {
      "section_name": "Supplier Scope",          ← exact PDF heading
      "heading_only": false,                     ← true = no body content

      "blocks":     [...],   // ← Section Analysis page reads THIS
      "statements": [...],   // ← Semantic Analysis page reads THIS

      "total": 17,
      "requirements": 7, "asks": 5,
      "recommendations": 2, "informational": 3,
      "avg_quality_score": 84.2
    },
    …
  ]
}
```

You don't switch endpoints — you switch which property you read.

| Page | Read | Discriminator |
|---|---|---|
| **Section Analysis** | `section.blocks[]` | `block.type` → `heading` \| `paragraph` \| `bullet_list` \| `numbered_list` \| `table` \| `picture` |
| **Semantic Analysis** | `section.statements[]` | `statement.classification` → `REQUIREMENT` \| `ASK` \| `RECOMMENDATION` \| `INFORMATIONAL` |

---

## 3. Page A — Section Analysis (raw, untouched content)

Render `section.blocks` **in order**. Each block is a discriminated union:

```ts
type RawBlock =
  | { type: "heading";       text: string }
  | { type: "paragraph";     text: string }
  | { type: "bullet_list";   items: string[] }
  | { type: "numbered_list"; items: string[] }
  | { type: "table";         headers: string[]; rows: string[][] }
  | { type: "picture";       image_base64: string; caption?: string | null; page?: number | null }
```

Reference renderer (React-ish):

```tsx
section.blocks.map((block, i) => {
  switch (block.type) {
    case "heading":
      return <h3 key={i} className="subhead">{block.text}</h3>
    case "paragraph":
      return <p key={i}>{block.text}</p>
    case "bullet_list":
      return <ul key={i}>{block.items.map((x, j) => <li key={j}>{x}</li>)}</ul>
    case "numbered_list":
      return <ol key={i}>{block.items.map((x, j) => <li key={j}>{x}</li>)}</ol>
    case "table":
      return (
        <table key={i}>
          <thead><tr>{block.headers.map(h => <th>{h}</th>)}</tr></thead>
          <tbody>
            {block.rows.map((row, r) => (
              <tr key={r}>{row.map((c, k) => <td key={k}>{c}</td>)}</tr>
            ))}
          </tbody>
        </table>
      )
    case "picture":
      return (
        <figure key={i}>
          <img src={block.image_base64} alt={block.caption ?? ""} />
          {block.caption && <figcaption>{block.caption}</figcaption>}
        </figure>
      )
  }
})
```

**`heading_only` sections**: when `section.heading_only === true`, `blocks` is `[]`. Show a "no body content" hint and move on.

---

## 4. Page B — Semantic Analysis (classified)

Filter `section.statements` by `classification`. Render as 4 columns or 4 stacked panels.

```ts
type Classification = "REQUIREMENT" | "ASK" | "RECOMMENDATION" | "INFORMATIONAL"

interface AnalyzedStatement {
  id: string                       // "SOR-001"
  section: string                  // matches section_name
  text: string
  source_type: "text" | "bullet" | "numbered" | "table_row"
  classification: Classification
  classification_reason: string    // LLM's short "why" — empty if missing
  iso_category: string             // "Functional" | "Safety" | "Performance" | …
  obligation_keyword: string       // "shall" | "must" | "should" | "will" | "may" | "none"
  quality_score: number            // 0–100
  ambiguous_words: string[]
  escape_clauses: string[]
  placeholders: string[]           // ["TBD", "TBC", …]
  is_passive_voice: boolean
  is_atomic: boolean
  verifiability: "PASS" | "WARN" | "FAIL"
  is_negative: boolean
  violated_rules: string[]         // ["R2", "R7", …]
  suggested_action: string
}
```

Reference renderer:

```tsx
const ORDER: Classification[] = ["REQUIREMENT", "ASK", "RECOMMENDATION", "INFORMATIONAL"]

return (
  <div className="grid grid-cols-4 gap-4">
    {ORDER.map(cls => {
      const items = section.statements.filter(s => s.classification === cls)
      return (
        <div key={cls} className="panel">
          <header>{cls} ({items.length})</header>
          {items.map(s => (
            <Card key={s.id}>
              <div className="text">{s.text}</div>
              {s.classification_reason && (
                <div className="why">Why: {s.classification_reason}</div>
              )}
              <div className="chips">
                <Chip>{s.iso_category}</Chip>
                {s.obligation_keyword !== "none" && <Chip>{s.obligation_keyword}</Chip>}
                <Chip className={scoreColor(s.quality_score)}>{s.quality_score}</Chip>
              </div>
            </Card>
          ))}
        </div>
      )
    })}
  </div>
)
```

What to show per statement at minimum: `text`, `classification_reason`, `iso_category`. Quality score, obligation keyword, rule violations are nice-to-have. Everything else is for an expanded/detail view.

---

## 5. Suggested page structure

```
History  ──┐
           ├──► Pick a job (your own cached jobs in localStorage)
Upload ────┘     │
                 ▼
            ┌────────────────────┬────────────────────┐
            │ Section Analysis   │ Semantic Analysis  │
            │ (left: section     │ (left: section     │
            │  list, right:      │  list, right: 4    │
            │  blocks renderer)  │  classification    │
            │                    │  columns)          │
            └────────────────────┴────────────────────┘
```

**Empty state** when no job is loaded: "Pick from history" + "Upload a new PDF". Don't auto-restore the previous job on refresh — feels stale.

---

## 6. Gotchas (read these)

1. **`POST /analyze` is synchronous, 30 s – 5 min.** Keep the connection open. Show a progress spinner. There is no polling endpoint.
2. **Section count is high — typically 80–100 sections for a 30-page SOR.** Use a scrollable / searchable list, not tabs.
3. **`section_name` for routing** — use the exact text URL-encoded. `Supplier Scope` → `Supplier%20Scope`. `11- GD&T` → `11-%20GD%26T`. Don't normalize or lowercase.
4. **`heading_only: true`** = parent heading with no direct body content (its content is in child sections). Show the section in the list, render a "no body content" hint when opened.
5. **`AnalyzedStatement.source_type`** mirrors `RawBlock.type` — `"bullet"` statements came from `bullet_list` blocks, `"table_row"` came from `table` blocks. Useful if you want to highlight where a classified statement came from.
6. **`classification_reason` can be empty** — fallback to "" without crashing.
7. **No model names / provider names in UI** — keep it product-flavored, not implementation-flavored.

---

## 7. Optional file downloads

If you want server-rendered Excel / CSV / PDF (instead of generating client-side with `sheetjs`/`jspdf`), the server has stateless export endpoints. POST the JSON you got from `/analyze` back:

```
POST /api/v1/export/excel    Body: AnalysisResult JSON   →  .xlsx
POST /api/v1/export/csv      Body: AnalysisResult JSON   →  .csv
POST /api/v1/export/pdf      Body: AnalysisResult JSON   →  .pdf
```

All three are optional — you can do the same thing client-side. PDF endpoint returns 503 if the server's weasyprint deps aren't installed.

---

## 8. Quick test

```bash
# Pull the JSON for any PDF
curl -F "file=@your-doc.pdf" http://<host>:8001/api/v1/analyze > out.json

# Count sections
jq '.total_sections' out.json

# Peek the first section's first 2 blocks (Section Analysis source)
jq '.sections[0].blocks[:2]' out.json

# Group statements by classification for that section (Semantic Analysis source)
jq '.sections[0].statements | group_by(.classification) | map({class: .[0].classification, count: length})' out.json
```

---

## 9. If anything's unclear

- Swagger: `http://<host>:8001/docs` — every endpoint clickable, runnable inline
- OpenAPI JSON: `http://<host>:8001/openapi.json` — full machine-readable contract
- Ping the API owner if you need a field changed/added — backend can ship a schema update in minutes.
