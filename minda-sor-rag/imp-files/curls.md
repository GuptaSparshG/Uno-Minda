# curls.md — Every API call as a copy-pasteable curl

Set these once per shell so the rest of the snippets work:

```bash
BASE=http://localhost:8001/api/v1
PDF=/Users/sparsh/Desktop/uno-minda/HVAC-Panel-SOR.pdf
```

---

## 1. Liveness

```bash
curl $BASE/health
# → {"status":"ok"}
```

---

## 2. PRIMARY — `POST /analyze`  (stateless: PDF in, JSON out)

```bash
# Run analysis, save the JSON locally
curl -F "file=@$PDF" "$BASE/analyze" -o analysis.json

# Quick peek
jq '{filename, total_sections, total_statements}' analysis.json

# Listing all section names
jq -r '.sections[].section_name' analysis.json

# First section, raw blocks (Section Analysis source)
jq '.sections[0] | {section_name, heading_only, blocks}' analysis.json

# First section, statements grouped by class (Semantic Analysis source)
jq '.sections[0].statements | group_by(.classification) | map({class: .[0].classification, count: length})' analysis.json
```

The response IS the full `AnalysisResult`. There's no follow-up call needed.

---

## 3. Stateless exports — POST the JSON back, get a file

```bash
# Excel
curl -X POST "$BASE/export/excel" \
     -H "Content-Type: application/json" \
     -d @analysis.json \
     -o report.xlsx

# CSV (one row per statement)
curl -X POST "$BASE/export/csv" \
     -H "Content-Type: application/json" \
     -d @analysis.json \
     -o report.csv

# PDF (requires weasyprint native libs on the server; 503 if missing)
curl -X POST "$BASE/export/pdf" \
     -H "Content-Type: application/json" \
     -d @analysis.json \
     -o report.pdf
```

---

## 4. Legacy stateful path  (`/upload` + `/jobs/*`)

Only useful for operator-side debugging. The UI doesn't need this.

```bash
# Upload PDF, returns just a job_id
curl -F "file=@$PDF" "$BASE/upload"
# → {"job_id":"…","filename":"…","status":"completed"}

# Set JOB to the returned id for the rest of this section
JOB=8930cdec-06fc-4a29-adcd-0a1a96199904

# List recent jobs (server keeps latest 20)
curl "$BASE/jobs" | jq

# Aggregate counts + rule-violation totals
curl "$BASE/jobs/$JOB/summary" | jq

# Per-section roll-up (no statement text)
curl "$BASE/jobs/$JOB/sections" | jq

# Full payload (sections + raw blocks + classified statements)
curl "$BASE/jobs/$JOB/results" -o results.json

# One section, raw — note: URL-encode the heading. Slashes in the heading
# (e.g. "AC ON/OFF") stay literal — encode each path segment separately.
curl "$BASE/jobs/$JOB/sections/raw/Supplier%20Scope" | jq

# One section, classified
curl "$BASE/jobs/$JOB/sections/semantic/Supplier%20Scope" | jq

# Tricky heading: 11- GD&T  →  11-%20GD%26T
curl "$BASE/jobs/$JOB/sections/raw/11-%20GD%26T" | jq

# Section name with literal slash (e.g. "AC ON/OFF") — slash stays literal
curl "$BASE/jobs/$JOB/sections/raw/AC%20ON/OFF" | jq

# Delete a persisted job
curl -X DELETE "$BASE/jobs/$JOB"
```

### Persisted-job downloads

```bash
curl "$BASE/jobs/$JOB/export/excel" -o report.xlsx
curl "$BASE/jobs/$JOB/export/csv"   -o report.csv
curl "$BASE/jobs/$JOB/export/json"  -o results.json
curl "$BASE/jobs/$JOB/export/pdf"   -o report.pdf   # 404 if weasyprint missing
```

---

## 5. End-to-end one-liner (no file artifacts)

```bash
# Run analysis and pretty-print the first 3 sections' Ask vs Requirement counts
curl -s -F "file=@$PDF" "$BASE/analyze" \
  | jq '.sections[:3] | map({name: .section_name, req: .requirements, ask: .asks})'
```

---

## 6. Useful URL-encoded section names from the HVAC SOR

| Heading | URL form |
|---|---|
| `Supplier Scope` | `Supplier%20Scope` |
| `Change Management` | `Change%20Management` |
| `Concern Management` | `Concern%20Management` |
| `Component Delivery` | `Component%20Delivery` |
| `Engineering design requirement` | `Engineering%20design%20requirement` |
| `11- GD&T` | `11-%20GD%26T` |
| `3D Data` | `3D%20Data` |
| `STATEMENT OF REQUIREMENT` | `STATEMENT%20OF%20REQUIREMENT` |
| `TEMPERATURE CONTROL PANEL (FATC).` | `TEMPERATURE%20CONTROL%20PANEL%20(FATC).` |
| `DFMEA, PFMEA, IFMEA` | `DFMEA%2C%20PFMEA%2C%20IFMEA` |

Generic rule: `encodeURIComponent(name)` in JS, or pipe through `python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.stdin.read().strip()))'` in bash.

---

## 7. Diagnose without the server

```bash
# Get the OpenAPI spec (every endpoint's request/response schema)
curl $BASE/../../openapi.json | jq '.paths | keys'

# Open Swagger UI in a browser
open http://localhost:8001/docs
```

---

## 8. Common failures

| Symptom | Likely cause |
|---|---|
| `curl: (7) Failed to connect` | Server isn't running on `:8001` |
| `HTTP 400: File is not a valid PDF` | First 4 bytes of file aren't `%PDF` |
| `HTTP 400: File too large` | > `MAX_PDF_SIZE_MB` (default 50) |
| `HTTP 404: Section not found` | `section_name` doesn't match exactly — check URL-encoding |
| `HTTP 503: PDF generation requires weasyprint…` | `brew install pango cairo gdk-pixbuf libffi` |
| Hangs 5+ min | Pipeline running — that's the normal upper bound for a large SOR |
