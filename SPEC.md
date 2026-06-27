# CLAUDE.md — SOR Requirements Analyzer (Demo Build)

## What To Build

A FastAPI server. Upload an SOR (Statement of Requirement) PDF → extract text → split into sections → classify each statement as Ask or Requirement using OpenAI → run INCOSE/ISO 29148 quality checks → return JSON + generate Excel + PDF reports.

Demo-grade: works end-to-end, shows well, not production-hardened.

---

## Tech Stack

```
Python 3.11+
fastapi + uvicorn          (server)
python-multipart           (file upload)
pdfplumber                 (PDF text extraction)
openai                     (GPT classification + embeddings)
chromadb                   (vector DB, embedded mode)
openpyxl                   (Excel reports)
weasyprint                 (PDF reports via HTML→PDF)
pydantic-settings          (config)
python-dotenv              (env vars)
```

---

## Folder Structure

```
sor-analyzer/
├── CLAUDE.md
├── requirements.txt
├── .env
├── run.py                          # uvicorn entry point
│
├── knowledge_base/
│   ├── incose_rules.json
│   ├── iso29148_clauses.json
│   ├── weak_words.json
│   └── seed.py                     # seeds ChromaDB on first run
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, CORS, lifespan
│   ├── config.py                   # Settings from .env
│   ├── schemas.py                  # all Pydantic models
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               # all endpoints in one file
│   │
│   └── services/
│       ├── __init__.py
│       ├── pdf_extractor.py        # PDF → raw text + font metadata
│       ├── section_splitter.py     # raw text → {section: [statements]}
│       ├── classifier.py           # ChromaDB retrieval + OpenAI classification
│       ├── rule_engine.py          # INCOSE deterministic checks
│       ├── pipeline.py             # orchestrates extract→classify→check→report
│       ├── report_excel.py         # generates .xlsx
│       └── report_pdf.py           # generates .pdf via HTML→weasyprint
│
├── storage/
│   ├── uploads/
│   ├── results/
│   ├── exports/
│   └── chroma_data/
│
└── Dockerfile
```

---

## .env

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
HOST=0.0.0.0
PORT=8000
```

---

## requirements.txt

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9
pdfplumber>=0.11.0
openai>=1.40.0
chromadb>=0.5.0
openpyxl>=3.1.0
weasyprint>=62.0
pydantic>=2.8.0
pydantic-settings>=2.4.0
python-dotenv>=1.0.0
```

---

## run.py

```python
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
```

---

## app/config.py

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    UPLOAD_DIR: str = "storage/uploads"
    RESULTS_DIR: str = "storage/results"
    EXPORT_DIR: str = "storage/exports"
    CHROMA_DIR: str = "storage/chroma_data"

    MAX_PDF_SIZE_MB: int = 50
    BATCH_SIZE: int = 10  # statements per OpenAI call

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## app/schemas.py

All request/response models in one file:

```python
from pydantic import BaseModel
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Classification(str, Enum):
    REQUIREMENT = "REQUIREMENT"
    RECOMMENDATION = "RECOMMENDATION"
    ASK = "ASK"
    INFORMATIONAL = "INFORMATIONAL"

class UploadResponse(BaseModel):
    job_id: str
    filename: str
    status: str

class StatusResponse(BaseModel):
    job_id: str
    status: str
    progress: str | None = None

class AnalyzedStatement(BaseModel):
    id: str
    section: str
    text: str
    classification: str          # REQUIREMENT / RECOMMENDATION / ASK / INFORMATIONAL
    iso_category: str            # Functional / Performance / Interface / Safety / etc.
    obligation_keyword: str      # shall / must / should / will / none
    quality_score: int           # 0-100
    ambiguous_words: list[str]
    escape_clauses: list[str]
    placeholders: list[str]
    is_passive_voice: bool
    is_atomic: bool
    verifiability: str           # PASS / WARN / FAIL
    is_negative: bool
    violated_rules: list[str]    # ["R3", "R7"]
    suggested_action: str

class SectionResult(BaseModel):
    section_name: str
    total: int
    requirements: int
    recommendations: int
    asks: int
    informational: int
    avg_quality_score: float
    statements: list[AnalyzedStatement]

class AnalysisResult(BaseModel):
    job_id: str
    filename: str
    total_statements: int
    total_sections: int
    sections: list[SectionResult]

class SummaryResponse(BaseModel):
    job_id: str
    filename: str
    total_statements: int
    total_sections: int
    requirements_count: int
    recommendations_count: int
    asks_count: int
    informational_count: int
    statements_with_issues: int
    avg_quality_score: float
    rule_violation_counts: dict[str, int]
```

---

## app/main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes import router
from app.services.classifier import init_knowledge_base
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create storage dirs
    for d in ["storage/uploads", "storage/results", "storage/exports", "storage/chroma_data"]:
        os.makedirs(d, exist_ok=True)
    # Seed ChromaDB if empty
    init_knowledge_base()
    yield

app = FastAPI(
    title="SOR Requirements Analyzer",
    version="1.0.0",
    description="Upload SOR PDFs → classify statements as Ask vs Requirement per INCOSE/ISO 29148",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
```

---

## app/api/routes.py

All endpoints in one file for demo:

```
POST /api/v1/upload
  - Accepts PDF file (multipart form, field name "file")
  - Validates: is PDF, size < 50MB
  - Generates UUID job_id
  - Saves to storage/uploads/{job_id}.pdf
  - Runs full pipeline SYNCHRONOUSLY (demo — no background tasks, just wait)
  - Saves results to storage/results/{job_id}.json
  - Generates Excel → storage/exports/{job_id}.xlsx
  - Generates PDF → storage/exports/{job_id}.pdf
  - Returns UploadResponse with job_id and status "completed"
  - If pipeline fails, returns 500 with error detail

GET /api/v1/jobs/{job_id}/results
  - Loads storage/results/{job_id}.json
  - Returns AnalysisResult
  - 404 if not found

GET /api/v1/jobs/{job_id}/summary
  - Loads results, computes summary stats
  - Returns SummaryResponse

GET /api/v1/jobs/{job_id}/sections
  - Returns list of section names with their Ask/Requirement counts

GET /api/v1/jobs/{job_id}/export/excel
  - Returns FileResponse for storage/exports/{job_id}.xlsx
  - 404 if not found

GET /api/v1/jobs/{job_id}/export/pdf
  - Returns FileResponse for storage/exports/{job_id}.pdf

GET /api/v1/jobs/{job_id}/export/json
  - Returns FileResponse for storage/results/{job_id}.json

GET /api/v1/health
  - Returns {"status": "ok"}
```

NOTE: For demo, the upload endpoint is SYNCHRONOUS — it processes and returns results in one call. The UI will show a loading spinner for 20-40 seconds. This is fine for demo. No background tasks, no polling, no job status tracking needed.

---

## app/services/pdf_extractor.py

```
Function: extract_text(pdf_path: str) -> dict

Returns:
{
    "full_text": str,         # all pages concatenated
    "pages": [
        {"page_num": 1, "text": str, "lines": [
            {"text": str, "is_bold": bool, "font_size": float, "is_upper": bool}
        ]}
    ]
}

Implementation:
1. Open PDF with pdfplumber
2. For each page:
   a. page.extract_text(layout=True) for full text
   b. Analyze page.chars to detect bold text and font sizes:
      - Group chars by y-position (same line)
      - For each line: get dominant fontname, font_size
      - Mark is_bold = True if fontname contains "Bold" or "bold"
      - Mark is_upper = True if text == text.upper() and len > 3
   c. Extract tables via page.extract_tables() — THIS IS CRITICAL
      Tables contain ~15-20% of actual requirements in typical SOR documents.
      
      Table handling strategy:
      
      TYPE 1: Key-Value tables (2 columns: Parameter | Value)
        Example: Technical Details table, Mechanical Requirements table
        Detection: exactly 2 columns, first column is labels
        Convert each row to: "{column1_header}: {cell1} — {column2_header}: {cell2}"
        Example output:
          "Voltage Range, V DC: 12"
          "Operating Voltage, V DC: 9 TO 16"
          "Operating noise: Less than 45 dB"
        Each row becomes a SEPARATE statement (these are individual specs/requirements).
      
      TYPE 2: Multi-column spec tables (3+ columns with parameter/target/description)
        Example: Switch operations table, Feedback voltage table, Pin details table
        Detection: 3+ columns, has header row
        Convert each data row to a sentence:
          "{row_header} — {col1_header}: {val1}, {col2_header}: {val2}, ..."
        Example (pin table): 
          "Pin 1 Battery: Max Current ≤ 1A, Functionality: Required"
          "Pin 18 BLOWER GATE: Max Current 20mA, Functionality: Required"
        Example (feedback voltage):
          "MODE flap FACE position: Angle 0°, Feedback Voltage 0.278V"
          "MODE flap FACE-FOOT position: Angle 39°, Feedback Voltage 1.361V"
        Each row becomes a SEPARATE statement.
      
      TYPE 3: Standards/compliance tables (Standard name | Standard No | Revision)
        Example: Material standards tables on pages 23-26
        Convert each row to:
          "Applicable standard: {name} — {standard_no} Rev {revision}"
        These are compliance requirements.
      
      TYPE 4: Matrix tables (variant/feature matrices)
        Example: Variant & Feature Matrix (Base/Mid/High/High+)
        Convert to: "HVAC Fully Auto Climate Control Panel — Diesel variant: Base=N, Mid=N, High=Y, High+=Y"
        These are informational.
      
      IMPORTANT: Track which section each table belongs to (by its position in the page flow).
      Tables within a section get their rows added as statements in that section.
      
      Edge cases:
      - Merged cells: pdfplumber returns None for merged cells. Fill forward from last non-None value.
      - Empty rows: skip.
      - Header row detection: first row where all cells are short (<30 chars) and look like labels.
3. Detect and remove repeated headers/footers:
   - Find lines that appear on 3+ pages with identical text → strip them
   - Common: "Classification: Internal" in your HVAC SOR
4. Return structured result

Error handling:
- If total extracted text < 100 chars → raise ValueError("PDF appears to be image-based or empty. Cannot extract text.")
- If file is not valid PDF → raise ValueError("Invalid PDF file.")

DIAGRAMS/IMAGES:
- pdfplumber cannot extract text from images/diagrams.
- Your SOR has circuit diagrams, phase flow diagrams, assembly flow diagrams.
- For demo: SKIP diagram content. The text surrounding diagrams usually describes the same info.
- Add a note in the output: "Note: Embedded diagrams/images were not analyzed. Only text and table content was extracted."
- Future: use OpenAI Vision API to send page images and extract diagram content.

TABLE-TO-SECTION INTEGRATION:
- Tables must be associated with the section they appear in.
- Track the current section heading as you process pages top-to-bottom.
- When a table is found, its converted rows get added to the current section's statement list.
- If a table spans a page break, pdfplumber handles this per-page. 
  Combine tables from consecutive pages if their column structure matches.
```

---

## app/services/section_splitter.py

THIS IS THE MOST CRITICAL FILE. Be precise.

```
Function: split_into_sections(extraction_result: dict) -> dict[str, list[str]]

Takes the output of pdf_extractor and returns OrderedDict of {section_name: [statements]}.

ALGORITHM — 3 passes:

═══ PASS 1: Identify heading lines ═══

For each line across all pages, compute a heading_score (0-100):

  +40  if is_bold AND font_size > median_font_size
  +30  if is_upper AND word_count <= 6 AND char_count < 60
  +20  if matches numbered pattern: /^\d+(\.\d+)*[\s.\-)]/ 
  +20  if matches known section keyword (fuzzy match against KNOWN_SECTIONS list)
  +10  if line ends with ":" and char_count < 50
  -50  if starts with bullet marker (➢ • ▪ ► - ▸)
  -30  if starts with lowercase letter
  -20  if char_count > 100 (too long for a heading)

  Threshold: heading_score >= 40 → classify as HEADING

KNOWN_SECTIONS list (case-insensitive substring match):
[
    "introduction", "statement of requirement", "supplier scope",
    "change management", "concern management", "component delivery",
    "supply", "engineering design", "design requirement",
    "technical specification", "functional requirement",
    "blower control", "actuator", "temperature control",
    "air intake", "mode actuator", "defrost", "rear defrost",
    "max ac", "auto", "ac on", "sensor", "thermistor",
    "communication", "technical details", "switch operation",
    "mechanical requirement", "light illumination",
    "drawing requirement", "cae", "nvh", "bsr",
    "manufacturing", "assembly", "handling",
    "perceived quality", "safety requirement", "safety",
    "environment", "warranty", "quality target", "reliability",
    "eol requirement", "end of line", "service requirement",
    "regulatory", "homologation", "gd&t", "gdt",
    "dfmea", "pfmea", "apqp", "ppap", "logistics",
    "material requirement", "surface finish", "appearance",
    "ergonomic", "standardization", "identification",
    "inspection", "rfq", "spare part", "legal",
    "elv requirement", "emi", "emc", "checking fixture",
    "time plan", "variant", "feature matrix",
    "primary function", "part detail", "benchmark",
    "validation", "certification", "cost", "weight",
    "shipping", "general note", "project description",
    "project overview", "phased process", "phase 1",
    "phase 2", "phase 3", "scope", "performance",
    "dvp", "design cad", "cad data", "data exchange",
    "arbitration", "mandatory test", "production validation",
    "special characteristic", "advance product quality",
    "supplier readiness", "pre-production sample",
    "first production sample", "joint supplier"
]

═══ PASS 2: Group text into sections ═══

  current_section = "General"  # default if no heading found before first content
  sections = OrderedDict()

  For each line:
    if line is HEADING:
      current_section = clean_heading_text(line)
      # clean: strip numbers, colons, trailing whitespace
      # "7.1 Technical Specification:" → "Technical Specification"
      # "BLOWER CONTROL" → "Blower Control"  (title case)
      if current_section not in sections:
        sections[current_section] = []
    else:
      if line.strip():  # skip blank lines
        sections[current_section].append(line.strip())

═══ PASS 3: Split section text into individual statements ═══

  For each section, take the collected lines and split into statements:

  def split_statements(lines: list[str]) -> list[str]:
      # Join all lines into one block
      block = " ".join(lines)
      
      # Step 1: Split on bullet markers
      # Split on: ➢  •  ▪  ►  ▸ (with optional space after)
      parts = re.split(r'\s*[➢•▪►▸]\s*', block)
      
      # Step 2: For each part, split on numbered items at start
      # "1. First thing 2. Second thing" → ["First thing", "Second thing"]
      # BUT protect version numbers (V5.1), standard numbers (ISO 898), 
      # decimal numbers (3.5 mm), and section refs (section 6, point 18)
      expanded = []
      for part in parts:
          # Only split on numbers that start a new item:
          # pattern: newline or 2+ spaces followed by digit(s) then "." or ")"
          # NOT: "V5", "R21", "ISO 898", "3.5 mm", "section 6"
          sub_items = re.split(r'(?<!\w)(?<![VvRr])(\d{1,2})[.)]\s+(?=[A-Z])', part)
          # Recombine split artifacts and filter
          buffer = ""
          for chunk in sub_items:
              if re.match(r'^\d{1,2}$', chunk.strip()):
                  if buffer.strip():
                      expanded.append(buffer.strip())
                  buffer = ""
              else:
                  buffer += " " + chunk
          if buffer.strip():
              expanded.append(buffer.strip())
      
      # Step 3: For parts that are still long (> 300 chars), 
      # split on sentence boundaries ONLY if they contain multiple "shall"/"must"/"should"
      final = []
      for part in expanded:
          part = part.strip()
          if not part or len(part) < 15:
              continue
          
          obligation_count = len(re.findall(r'\b(shall|must|should)\b', part, re.I))
          if obligation_count > 1 and len(part) > 200:
              # Split on sentence boundaries between obligation keywords
              sentences = re.split(r'(?<=[.;])\s+(?=[A-Z])', part)
              final.extend([s.strip() for s in sentences if len(s.strip()) > 15])
          else:
              final.append(part)
      
      # Step 4: Clean each statement
      cleaned = []
      for stmt in final:
          stmt = re.sub(r'^[\d+.)\s]+', '', stmt)  # strip leading numbers
          stmt = re.sub(r'\s+', ' ', stmt).strip()  # normalize whitespace
          if len(stmt) > 15:  # skip fragments
              cleaned.append(stmt)
      
      return cleaned

  # Apply to each section
  for section_name in sections:
      sections[section_name] = split_statements(sections[section_name])
  
  # Remove empty sections
  sections = {k: v for k, v in sections.items() if len(v) > 0}

  return sections
```

---

## app/services/classifier.py

Two functions: `init_knowledge_base()` and `classify_sections()`.

```
═══ init_knowledge_base() ═══

Called once on startup. Seeds ChromaDB if collection is empty.

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from app.config import settings

def get_chroma_collection():
    client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
    embedding_fn = OpenAIEmbeddingFunction(
        api_key=settings.OPENAI_API_KEY,
        model_name=settings.OPENAI_EMBEDDING_MODEL
    )
    collection = client.get_or_create_collection(
        name="incose_iso_rules",
        embedding_function=embedding_fn
    )
    return collection

def init_knowledge_base():
    collection = get_chroma_collection()
    if collection.count() > 0:
        return  # already seeded
    
    import json, os
    kb_dir = os.path.join(os.path.dirname(__file__), "../../knowledge_base")
    
    rules = json.load(open(os.path.join(kb_dir, "incose_rules.json")))
    clauses = json.load(open(os.path.join(kb_dir, "iso29148_clauses.json")))
    
    documents = []
    ids = []
    metadatas = []
    
    for r in rules:
        documents.append(r["text"])
        ids.append(r["id"])
        metadatas.append({"rule_id": r["rule_id"], "source": "INCOSE"})
    
    for c in clauses:
        documents.append(c["text"])
        ids.append(c["id"])
        metadatas.append({"clause_id": c["clause_id"], "source": "ISO29148"})
    
    collection.add(documents=documents, ids=ids, metadatas=metadatas)


═══ classify_sections(sections: dict[str, list[str]]) -> dict[str, list[dict]] ═══

Takes {section_name: [statements]} and returns {section_name: [classified_dicts]}.

from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)

For each section:
  1. Get all statements for that section
  2. Batch them (BATCH_SIZE = 10)
  3. For each batch:
     a. Query ChromaDB: retrieve top-3 relevant rules for the FIRST statement in batch
        (optimization: one retrieval per batch, not per statement)
        
        collection = get_chroma_collection()
        rag_results = collection.query(query_texts=[batch[0]], n_results=3)
        rag_context = "\n".join(rag_results["documents"][0])
     
     b. Build OpenAI prompt:
     
        SYSTEM_PROMPT = """You are an ISO 29148 / INCOSE requirements engineering expert.
        You classify statements from engineering SOR documents.
        
        Classification rules:
        - REQUIREMENT: Binding obligation. Uses "shall" or "must". Or functionally binding 
          even without shall (e.g., "Supplier will be responsible for..." is binding).
          Also: specification values from tables (voltage ratings, current limits, 
          temperature ranges, force/torque specs) are REQUIREMENTS even without "shall".
        - RECOMMENDATION: Advisory. Uses "should".
        - ASK: Process expectation, deliverable request, action item. 
          (e.g., "Supplier to provide...", "Supplier needs to submit...")
        - INFORMATIONAL: Background info, description, context, definitions.
        
        IMPORTANT: Rows extracted from specification tables (e.g., "Pin 1 Battery: 
        Max Current ≤ 1A" or "Operating Voltage: 9 TO 16 V DC") are technical 
        specifications and should be classified as REQUIREMENT with category Performance
        or Design Constraint, even though they don't use "shall".
        
        ISO 29148 categories:
        Functional, Performance, Interface, Design Constraint, Quality Attribute,
        Safety, Environmental, Regulatory, Process, Serviceability
        
        Obligation keywords: shall, must, should, will, may, none"""
        
        USER_PROMPT = f"""Section: "{section_name}"
        
        Relevant INCOSE/ISO 29148 context:
        {rag_context}
        
        Classify each statement below. Return ONLY a JSON array.
        Each element: {{"index": 0, "classification": "...", "iso_category": "...", "obligation_keyword": "..."}}
        
        Statements:
        {chr(10).join(f'{i}. {s}' for i, s in enumerate(batch))}"""
     
     c. Call OpenAI:
        
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        raw = response.choices[0].message.content
     
     d. Parse response:
        
        import json
        
        # response_format=json_object wraps in {"result": [...]} or similar
        parsed = json.loads(raw)
        
        # Handle different response shapes:
        if isinstance(parsed, list):
            items = parsed
        elif isinstance(parsed, dict):
            # Find the array inside the dict
            for v in parsed.values():
                if isinstance(v, list):
                    items = v
                    break
            else:
                items = []
        
        # Validate each item has required fields, fill defaults if missing
        for item in items:
            item.setdefault("classification", "INFORMATIONAL")
            item.setdefault("iso_category", "Functional")
            item.setdefault("obligation_keyword", "none")
     
     e. FALLBACK if OpenAI call fails (network error, rate limit, parse error):
        
        For each statement, apply keyword rules:
          text_lower = statement.lower()
          if "shall" in text_lower:
              classification = "REQUIREMENT", obligation = "shall"
          elif "must" in text_lower:
              classification = "REQUIREMENT", obligation = "must"
          elif "should" in text_lower:
              classification = "RECOMMENDATION", obligation = "should"
          elif any(phrase in text_lower for phrase in 
                   ["supplier will", "supplier to ", "supplier needs"]):
              classification = "ASK", obligation = "will"
          else:
              classification = "INFORMATIONAL", obligation = "none"
          
          iso_category = guess_category_from_section_name(section_name)
          # Simple mapping: if section contains "safety" → Safety, 
          # "environment" → Environmental, "performance" → Performance, etc.
          # Default: "Functional"

  4. Return results dict
```

---

## app/services/rule_engine.py

```
Class: RuleEngine

Loads weak_words.json once on init.

WEAK_WORDS: loaded from knowledge_base/weak_words.json
ESCAPE_CLAUSES: [
    "unless otherwise specified", "as far as practical", "where possible",
    "if resources permit", "to the extent feasible", "except where noted",
    "as agreed", "subject to", "wherever applicable",
    "to be revised after", "to be confirmed", "to be defined",
    "to be shared", "to be discussed", "to be finalized"
]
PLACEHOLDERS: ["TBD", "TBS", "TBC", "TBA"]

Methods:

def analyze(self, text: str) -> dict:
    return {
        "ambiguous_words": self._check_ambiguity(text),
        "escape_clauses": self._check_escapes(text),
        "placeholders": self._check_placeholders(text),
        "is_passive_voice": self._check_passive(text),
        "is_atomic": self._check_atomic(text),
        "verifiability": self._check_verifiable(text),
        "is_negative": self._check_negative(text),
        "quality_score": self._compute_score(text),
        "violated_rules": self._get_violated_rules(text),
        "suggested_action": self._suggest_action(text),
    }

def _check_ambiguity(self, text) -> list[str]:
    text_lower = text.lower()
    return [w for w in self.WEAK_WORDS if w.lower() in text_lower]

def _check_escapes(self, text) -> list[str]:
    text_lower = text.lower()
    return [e for e in self.ESCAPE_CLAUSES if e.lower() in text_lower]

def _check_placeholders(self, text) -> list[str]:
    return [p for p in self.PLACEHOLDERS if re.search(r'\b' + p + r'\b', text, re.I)]

def _check_passive(self, text) -> bool:
    patterns = [
        r'\b(is|are|was|were|be|been)\s+\w+ed\b',
        r'\b(is|are)\s+to\s+be\b'
    ]
    return any(re.search(p, text, re.I) for p in patterns)

def _check_atomic(self, text) -> bool:
    shall_count = len(re.findall(r'\bshall\b', text, re.I))
    return shall_count <= 1

def _check_verifiable(self, text) -> str:
    text_lower = text.lower()
    subjective = ["objectionable", "easy", "adequate", "properly", "smoothly",
                  "convenient", "harmony", "user-friendly", "friendly", "good"]
    if any(w in text_lower for w in subjective):
        return "FAIL"
    has_number = bool(re.search(r'\d+', text))
    has_unit = bool(re.search(
        r'(mm|cm|kg|°c|v\b|hz|db|ppm|%|sone|lux|years|km|cycles|passes|seconds|minutes|hours|n\b|mA|kΩ)',
        text, re.I))
    has_ref = bool(re.search(
        r'(as per|per std|standard|ais|iso|din|asme|cispr|eec|ece|fmvss|astm)',
        text, re.I))
    if has_number and (has_unit or has_ref):
        return "PASS"
    if has_ref:
        return "PASS"
    return "WARN"

def _check_negative(self, text) -> bool:
    return bool(re.search(r'\b(shall|should|must)\s+not\b', text, re.I))

def _compute_score(self, text) -> int:
    s = 100
    s -= len(self._check_ambiguity(text)) * 8
    s -= len(self._check_escapes(text)) * 10
    s -= len(self._check_placeholders(text)) * 15
    if self._check_passive(text): s -= 5
    if not self._check_atomic(text): s -= 15
    v = self._check_verifiable(text)
    if v == "FAIL": s -= 20
    elif v == "WARN": s -= 10
    if self._check_negative(text): s -= 5
    return max(0, min(100, s))

def _get_violated_rules(self, text) -> list[str]:
    rules = []
    if self._check_ambiguity(text): rules.append("R3")
    if self._check_escapes(text): rules.append("R10")
    if self._check_placeholders(text): rules.append("R4")
    if self._check_passive(text): rules.append("R2")
    if not self._check_atomic(text): rules.append("R5")
    if self._check_verifiable(text) != "PASS": rules.append("R7")
    if self._check_negative(text): rules.append("R14")
    return rules

def _suggest_action(self, text) -> str:
    actions = []
    amb = self._check_ambiguity(text)
    if amb: actions.append(f"Remove ambiguous terms: {', '.join(amb[:3])}")
    esc = self._check_escapes(text)
    if esc: actions.append(f"Remove escape clause: {esc[0]}")
    ph = self._check_placeholders(text)
    if ph: actions.append(f"Resolve placeholder: {ph[0]}")
    if self._check_passive(text): actions.append("Rewrite in active voice")
    if not self._check_atomic(text): actions.append("Split into separate requirements")
    v = self._check_verifiable(text)
    if v == "FAIL": actions.append("Add measurable acceptance criteria")
    elif v == "WARN": actions.append("Consider adding quantitative criteria")
    if self._check_negative(text): actions.append("Rewrite as positive requirement")
    return "; ".join(actions) if actions else "No issues found"
```

---

## app/services/pipeline.py

```
Function: run_pipeline(pdf_path: str, job_id: str) -> AnalysisResult

This is the orchestrator. Calls everything in sequence.

1. EXTRACT
   extraction = pdf_extractor.extract_text(pdf_path)

2. SPLIT
   sections = section_splitter.split_into_sections(extraction)
   # sections = {"Blower Control": ["stmt1", "stmt2"], "Safety": [...], ...}

3. CLASSIFY
   classified = classifier.classify_sections(sections)
   # classified = {"Blower Control": [
   #   {"text": "stmt1", "classification": "REQUIREMENT", "iso_category": "Functional", "obligation_keyword": "shall"},
   #   ...
   # ]}

4. RULE CHECK
   rule_engine = RuleEngine()
   
   all_sections = []
   global_id = 1
   
   for section_name, statements in classified.items():
       section_statements = []
       for stmt_data in statements:
           rules_result = rule_engine.analyze(stmt_data["text"])
           
           analyzed = AnalyzedStatement(
               id=f"SOR-{global_id:03d}",
               section=section_name,
               text=stmt_data["text"],
               classification=stmt_data["classification"],
               iso_category=stmt_data["iso_category"],
               obligation_keyword=stmt_data["obligation_keyword"],
               quality_score=rules_result["quality_score"],
               ambiguous_words=rules_result["ambiguous_words"],
               escape_clauses=rules_result["escape_clauses"],
               placeholders=rules_result["placeholders"],
               is_passive_voice=rules_result["is_passive_voice"],
               is_atomic=rules_result["is_atomic"],
               verifiability=rules_result["verifiability"],
               is_negative=rules_result["is_negative"],
               violated_rules=rules_result["violated_rules"],
               suggested_action=rules_result["suggested_action"],
           )
           section_statements.append(analyzed)
           global_id += 1
       
       # Build section result
       section_result = SectionResult(
           section_name=section_name,
           total=len(section_statements),
           requirements=sum(1 for s in section_statements if s.classification == "REQUIREMENT"),
           recommendations=sum(1 for s in section_statements if s.classification == "RECOMMENDATION"),
           asks=sum(1 for s in section_statements if s.classification == "ASK"),
           informational=sum(1 for s in section_statements if s.classification == "INFORMATIONAL"),
           avg_quality_score=round(sum(s.quality_score for s in section_statements) / max(len(section_statements), 1), 1),
           statements=section_statements,
       )
       all_sections.append(section_result)
   
   result = AnalysisResult(
       job_id=job_id,
       filename=os.path.basename(pdf_path),
       total_statements=global_id - 1,
       total_sections=len(all_sections),
       sections=all_sections,
   )

5. SAVE JSON
   with open(f"storage/results/{job_id}.json", "w") as f:
       f.write(result.model_dump_json(indent=2))

6. GENERATE EXCEL
   report_excel.generate(result, f"storage/exports/{job_id}.xlsx")

7. GENERATE PDF
   report_pdf.generate(result, f"storage/exports/{job_id}.pdf")

8. Return result
```

---

## app/services/report_excel.py

```
Function: generate(result: AnalysisResult, output_path: str) -> None

Use openpyxl. Create workbook with:

Sheet 1: "Summary"
  Row 1: "SOR Requirements Analysis Report" (merged, bold, 14pt)
  Row 3: "File:", result.filename
  Row 4: "Total Statements:", result.total_statements
  Row 5: "Total Sections:", result.total_sections
  Row 7: "Classification Breakdown" (bold)
  Row 8-11: Requirements / Recommendations / Asks / Informational counts
  Row 13: "Section Summary" (bold)
  Row 14+: Table with columns: Section | Total | Requirements | Asks | Avg Score
  
Sheet 2: "All Statements"
  Header row (dark blue bg, white bold text):
    ID | Section | Text | Classification | ISO Category | Obligation | Score | Violated Rules | Suggested Action
  One row per statement across all sections.
  Color code the Classification column:
    REQUIREMENT → light blue fill
    RECOMMENDATION → light yellow fill
    ASK → light purple fill
    INFORMATIONAL → light gray fill
  Color code Score:
    >= 80 → green fill
    >= 50 → yellow fill
    < 50 → red fill
  Enable auto-filter. Freeze row 1. Wrap text on Text column.
  Column widths: ID=10, Section=22, Text=70, Classification=18, Category=18, Obligation=12, Score=8, Rules=20, Action=40

Sheet 3+ (one per section, named by section_name truncated to 31 chars):
  Same layout as Sheet 2 but only statements from that section.
  First 2 rows: section name + summary stats.
```

---

## app/services/report_pdf.py

```
Function: generate(result: AnalysisResult, output_path: str) -> None

Use weasyprint: build an HTML string, convert to PDF.

html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: Arial, sans-serif; margin: 40px; font-size: 11px; }}
  h1 {{ color: #1a365d; font-size: 22px; }}
  h2 {{ color: #2c5282; font-size: 16px; margin-top: 30px; border-bottom: 2px solid #2c5282; padding-bottom: 4px; }}
  h3 {{ color: #2d3748; font-size: 13px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
  th {{ background: #1a365d; color: white; padding: 6px 8px; text-align: left; font-size: 10px; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #e2e8f0; font-size: 10px; vertical-align: top; }}
  tr:nth-child(even) {{ background: #f7fafc; }}
  .req {{ color: #1a365d; font-weight: bold; }}
  .rec {{ color: #744210; }}
  .ask {{ color: #553c9a; }}
  .info {{ color: #718096; }}
  .score-good {{ color: #276749; font-weight: bold; }}
  .score-warn {{ color: #975a16; font-weight: bold; }}
  .score-bad {{ color: #c53030; font-weight: bold; }}
  .stat-box {{ display: inline-block; padding: 8px 16px; margin: 4px; background: #ebf8ff; border-radius: 4px; }}
  .stat-num {{ font-size: 20px; font-weight: bold; color: #2c5282; }}
  .stat-label {{ font-size: 9px; color: #718096; }}
  @page {{ margin: 1.5cm; @bottom-center {{ content: "Page " counter(page) " of " counter(pages); font-size: 9px; }} }}
</style>
</head>
<body>
  <h1>SOR Requirements Analysis Report</h1>
  <p>File: {result.filename} | Statements: {result.total_statements} | Sections: {result.total_sections}</p>
  
  <!-- Summary stats boxes -->
  <div>
    <div class="stat-box"><div class="stat-num">{req_count}</div><div class="stat-label">Requirements</div></div>
    <div class="stat-box"><div class="stat-num">{rec_count}</div><div class="stat-label">Recommendations</div></div>
    <div class="stat-box"><div class="stat-num">{ask_count}</div><div class="stat-label">Asks</div></div>
    <div class="stat-box"><div class="stat-num">{info_count}</div><div class="stat-label">Informational</div></div>
  </div>

  <!-- For each section -->
  <h2>{section.section_name}</h2>
  <p>Requirements: {section.requirements} | Asks: {section.asks} | Avg Score: {section.avg_quality_score}</p>
  <table>
    <tr><th>ID</th><th>Classification</th><th>Statement</th><th>Score</th><th>Issues</th></tr>
    <!-- For each statement in section -->
    <tr>
      <td>{stmt.id}</td>
      <td class="req/rec/ask/info">{stmt.classification}</td>
      <td>{stmt.text}</td>
      <td class="score-good/warn/bad">{stmt.quality_score}</td>
      <td>{', '.join(stmt.violated_rules) or '✓'}</td>
    </tr>
  </table>
  <!-- repeat for all sections -->
  
</body>
</html>
"""

# Convert HTML to PDF
from weasyprint import HTML
HTML(string=html).write_pdf(output_path)

NOTE: weasyprint needs system dependencies. In Dockerfile add:
  apt-get install -y libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev libcairo2
```

---

## knowledge_base/incose_rules.json

Generate this file with 18 rules. Each rule:

```json
[
  {
    "id": "incose-R1",
    "rule_id": "R1",
    "rule_name": "Necessary",
    "text": "INCOSE Rule R1 - Necessary: A requirement is necessary if removing it would cause a deficiency that cannot be fulfilled by other requirements. Every requirement must trace to a higher-level need or stakeholder requirement. Check: does the requirement have a traceable source? If no parent need or use case is referenced, flag as potentially unnecessary."
  },
  {
    "id": "incose-R2",
    "rule_id": "R2",
    "rule_name": "Active Voice",
    "text": "INCOSE Rule R2 - Active Voice: Requirements shall be written in active voice with a clear subject performing the action. BAD: 'The data shall be processed by the system.' GOOD: 'The system shall process the data.' Passive constructions obscure who/what is responsible. Detect patterns: is/are/was/were + past participle."
  },
  {
    "id": "incose-R3",
    "rule_id": "R3",
    "rule_name": "Unambiguous",
    "text": "INCOSE Rule R3 - Unambiguous: Requirements shall not contain vague, subjective, or ambiguous terms. Problematic words include: adequate, appropriate, as applicable, as needed, efficient, easy, enough, etc., flexible, friendly, generally, improved, maximize, minimize, normal, optimal, reasonable, robust, seamless, several, significant, simple, some, sufficient, suitable, timely, user-friendly, versatile, and/or. BAD: 'The system shall provide adequate performance.' GOOD: 'The system shall process 500 requests per second.'"
  },
  {
    "id": "incose-R4",
    "rule_id": "R4",
    "rule_name": "Complete",
    "text": "INCOSE Rule R4 - Complete: A requirement is complete when it contains all necessary information to be understood without needing additional explanation. Flag: TBD, TBS, TBC, TBA placeholders, missing units, missing reference document versions, ellipsis, incomplete sentences. BAD: 'The response time shall be TBD.' GOOD: 'The system shall respond within 200ms.'"
  },
  {
    "id": "incose-R5",
    "rule_id": "R5",
    "rule_name": "Singular",
    "text": "INCOSE Rule R5 - Singular (Atomic): Each requirement shall address one and only one capability, characteristic, or constraint. Multiple 'shall' keywords in one statement indicate it should be split. BAD: 'The system shall log events and shall generate alerts.' GOOD: Split into two: 'The system shall log events.' and 'The system shall generate alerts.'"
  },
  {
    "id": "incose-R7",
    "rule_id": "R7",
    "rule_name": "Verifiable",
    "text": "INCOSE Rule R7 - Verifiable: A requirement must be written so that a test, analysis, inspection, or demonstration can confirm whether it is met. Requirements need measurable criteria: numbers with units, reference to a standard, or defined threshold. BAD: 'The system shall be fast.' GOOD: 'The system shall complete startup within 5 seconds.' Subjective terms like objectionable, easy, adequate make requirements untestable."
  },
  {
    "id": "incose-R10",
    "rule_id": "R10",
    "rule_name": "No Escape Clauses",
    "text": "INCOSE Rule R10 - Free of Escape Clauses: Requirements shall not contain clauses that provide a way to avoid meeting the requirement. Escape phrases: 'unless otherwise specified', 'as far as practical', 'where possible', 'if resources permit', 'to the extent feasible', 'except where noted', 'as agreed', 'subject to'. These undermine the binding nature of shall."
  },
  {
    "id": "incose-R14",
    "rule_id": "R14",
    "rule_name": "Positive",
    "text": "INCOSE Rule R14 - Positive Statement: Requirements should state what the system SHALL do, not what it shall NOT do. Negative requirements are harder to verify. BAD: 'The system shall not lose data.' GOOD: 'The system shall maintain data integrity with zero data loss.' Flag: 'shall not', 'should not', 'must not' constructions."
  },
  {
    "id": "incose-R15",
    "rule_id": "R15",
    "rule_name": "Correct Obligation Keywords",
    "text": "INCOSE Rule R15 / ISO 29148 Section 5.2.7 - Obligation Keywords: 'shall' = mandatory requirement (binding). 'should' = recommendation (advisory). 'may' = permission. 'will' = statement of fact or declaration of purpose. Using 'must' instead of 'shall' is non-standard per ISO 29148. 'needs to', 'has to', 'is required to' should be replaced with 'shall'."
  }
]

Generate at least 12-15 rules total. Include R1 through R18. Each with practical examples.
```

---

## knowledge_base/iso29148_clauses.json

```json
[
  {
    "id": "iso-5.2.7",
    "clause_id": "5.2.7",
    "text": "ISO 29148 Section 5.2.7 - Obligation Keywords: The standard defines four obligation levels. 'Shall' indicates a binding requirement that must be met. 'Should' indicates a recommendation that is advised but not mandatory. 'May' indicates a permission or optional feature. 'Will' indicates a statement of fact, a declaration of purpose, or a future action that is not a requirement."
  },
  {
    "id": "iso-5.2.8-structure",
    "clause_id": "5.2.8",
    "text": "ISO 29148 Section 5.2.8 - Requirement Statement Structure: Well-formed requirements follow one of two patterns. Syntax 1: [Subject] [Action] [Constraint]. Example: 'The system shall process transactions within 2 seconds.' Syntax 2: [Condition] [Subject] [Action] [Object] [Constraint]. Example: 'When the temperature exceeds 85C, the system shall activate the cooling fan within 500ms.'"
  },
  {
    "id": "iso-5.2.8-characteristics",
    "clause_id": "5.2.8",
    "text": "ISO 29148 Section 5.2.8 - Nine Characteristics of Well-Formed Requirements: 1. Necessary 2. Appropriate (implementation-free) 3. Unambiguous 4. Complete 5. Singular (atomic) 6. Feasible 7. Verifiable 8. Correct 9. Conforming to an approved standard template."
  },
  {
    "id": "iso-annexC",
    "clause_id": "Annex C",
    "text": "ISO 29148 Annex C - Problematic Words and Phrases: The following terms introduce ambiguity and should be avoided in requirements: adequate, appropriate, as applicable, be able to, be capable of, but not limited to, capability of, easy, effective, efficient, etc., as a minimum, flexible, improved, maximize, minimize, normal, optimal, rapid, sufficient, suitable, timely, user-friendly."
  },
  {
    "id": "iso-taxonomy",
    "clause_id": "5.2.4",
    "text": "ISO 29148 Requirement Taxonomy: Requirements are classified into types. Functional requirements define what the system does. Performance requirements define how well (speed, capacity, accuracy). Interface requirements define external system boundaries. Design constraints are imposed limitations. Quality attributes cover reliability, maintainability, security, usability. Additional categories: Safety, Environmental, Regulatory compliance."
  }
]

Generate 8-10 clauses covering the key ISO 29148 sections.
```

---

## knowledge_base/weak_words.json

```json
["adequate", "appropriate", "as applicable", "as needed", "as a minimum",
 "but not limited to", "capable of", "effective", "efficient", "easy",
 "enough", "etc.", "etc", "flexible", "friendly", "generally",
 "if practical", "improved", "maximize", "minimize", "normal",
 "optimal", "optionally", "rapid", "reasonable", "robust",
 "seamless", "several", "significant", "simple", "some",
 "state-of-the-art", "sufficient", "suitable", "timely",
 "user-friendly", "versatile", "and/or", "good", "high quality",
 "properly", "approximately", "near", "similar", "fast", "slow",
 "large", "small", "as required", "if required", "wherever applicable",
 "if applicable", "as per requirement", "smoothly", "objectionable",
 "convenient", "acceptable", "best", "useful", "lightweight",
 "strong", "adequate", "fair", "satisfactory", "typical",
 "common", "standard", "superior", "major", "minor",
 "critical", "essential", "important", "preferred", "desired"]
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim

# weasyprint system dependencies
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p storage/uploads storage/results storage/exports storage/chroma_data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Build Order

Claude CLI should build files in this order:

1. requirements.txt, .env (copy from .env example), .gitignore
2. app/config.py
3. app/schemas.py
4. knowledge_base/weak_words.json
5. knowledge_base/incose_rules.json (generate full 15+ rules)
6. knowledge_base/iso29148_clauses.json (generate 8-10 clauses)
7. app/services/rule_engine.py
8. app/services/pdf_extractor.py
9. app/services/section_splitter.py
10. app/services/classifier.py (includes init_knowledge_base + classify_sections)
11. app/services/pipeline.py
12. app/services/report_excel.py
13. app/services/report_pdf.py
14. app/api/routes.py
15. app/main.py
16. run.py
17. Dockerfile

---

## Test Command

```bash
# Start
python run.py

# Upload test (curl)
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@HVAC_Panel_SOR.pdf"

# Response: {"job_id": "abc-123", "filename": "HVAC_Panel_SOR.pdf", "status": "completed"}

# Get results
curl http://localhost:8000/api/v1/jobs/abc-123/results | python -m json.tool

# Download Excel
curl -o report.xlsx http://localhost:8000/api/v1/jobs/abc-123/export/excel

# Swagger docs
open http://localhost:8000/docs
```
