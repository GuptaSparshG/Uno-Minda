from enum import Enum

from pydantic import BaseModel


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
    source_type: str = "text"
    classification: str
    classification_reason: str = ""
    iso_category: str
    obligation_keyword: str
    quality_score: int
    ambiguous_words: list[str]
    escape_clauses: list[str]
    placeholders: list[str]
    is_passive_voice: bool
    is_atomic: bool
    verifiability: str
    is_negative: bool
    violated_rules: list[str]
    suggested_action: str


class RawBlock(BaseModel):
    """A block of original content from the PDF — untouched, just typed.

    Discriminator: `type`. Field availability by type:
      heading / paragraph → text
      bullet_list / numbered_list → items
      table → headers, rows
      picture → image_base64 (data: URI), caption, page
    """

    type: str
    text: str | None = None
    items: list[str] | None = None
    headers: list[str] | None = None
    rows: list[list[str]] | None = None
    image_base64: str | None = None
    caption: str | None = None
    page: int | None = None


class SectionResult(BaseModel):
    section_name: str  # EXACT heading text from the PDF
    heading_only: bool = False  # True if the heading has no body content
    blocks: list[RawBlock] = []  # raw, untouched content
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


class SectionSummary(BaseModel):
    section_name: str
    total: int
    requirements: int
    recommendations: int
    asks: int
    informational: int
    avg_quality_score: float


class SectionsResponse(BaseModel):
    job_id: str
    sections: list[SectionSummary]


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


class JobListItem(BaseModel):
    job_id: str
    filename: str
    total_statements: int
    total_sections: int
    requirements_count: int
    asks_count: int
    created_at: str


class JobsListResponse(BaseModel):
    jobs: list[JobListItem]
