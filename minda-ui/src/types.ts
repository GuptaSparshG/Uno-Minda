export type Classification =
  | "REQUIREMENT"
  | "RECOMMENDATION"
  | "ASK"
  | "INFORMATIONAL";

export type SourceType = "text" | "bullet" | "numbered" | "table_row";

export interface AnalyzedStatement {
  id: string;
  section: string;
  text: string;
  source_type?: SourceType;
  classification: Classification;
  classification_reason?: string;
  iso_category: string;
  obligation_keyword: string;
  quality_score: number;
  ambiguous_words: string[];
  escape_clauses: string[];
  placeholders: string[];
  is_passive_voice: boolean;
  is_atomic: boolean;
  verifiability: "PASS" | "WARN" | "FAIL";
  is_negative: boolean;
  violated_rules: string[];
  suggested_action: string;
}

export interface SectionResult {
  section_name: string;
  heading_only?: boolean;
  blocks?: RawBlock[];
  total: number;
  requirements: number;
  recommendations: number;
  asks: number;
  informational: number;
  avg_quality_score: number;
  statements: AnalyzedStatement[];
}

export interface AnalysisResult {
  job_id: string;
  filename: string;
  total_statements: number;
  total_sections: number;
  sections: SectionResult[];
}

export interface SummaryResponse {
  job_id: string;
  filename: string;
  total_statements: number;
  total_sections: number;
  requirements_count: number;
  recommendations_count: number;
  asks_count: number;
  informational_count: number;
  statements_with_issues: number;
  avg_quality_score: number;
  rule_violation_counts: Record<string, number>;
}

export interface UploadResponse {
  job_id: string;
  filename: string;
  status: string;
}

export interface JobListItem {
  job_id: string;
  filename: string;
  total_statements: number;
  total_sections: number;
  requirements_count: number;
  asks_count: number;
  created_at: string;
}

export interface JobsListResponse {
  jobs: JobListItem[];
}

export type RawBlock =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "bullet_list"; items: string[] }
  | { type: "numbered_list"; items: string[] }
  | { type: "table"; headers: string[]; rows: string[][] }
  | {
      type: "picture";
      image_base64: string;
      caption?: string | null;
      page?: number | null;
    };

export interface SectionRawResponse {
  job_id: string;
  section_name: string;
  heading_only: boolean;
  blocks: RawBlock[];
}

export interface SectionSemanticResponse {
  job_id: string;
  section_name: string;
  totals: Record<Classification, number>;
  groups: Record<Classification, AnalyzedStatement[]>;
}
