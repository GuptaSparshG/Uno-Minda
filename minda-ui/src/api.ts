import type {
  AnalysisResult,
  JobsListResponse,
  SectionRawResponse,
  SectionSemanticResponse,
  SummaryResponse,
  UploadResponse,
} from "./types";

const BASE = "/api/v1";

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`${r.status}: ${detail}`);
  }
  return r.json() as Promise<T>;
}

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const fd = new FormData();
  fd.append("file", file);
  return jsonFetch<UploadResponse>(`${BASE}/upload`, {
    method: "POST",
    body: fd,
  });
}

export function getResults(jobId: string) {
  return jsonFetch<AnalysisResult>(`${BASE}/jobs/${jobId}/results`);
}

export function getSummary(jobId: string) {
  return jsonFetch<SummaryResponse>(`${BASE}/jobs/${jobId}/summary`);
}

export function listJobs() {
  return jsonFetch<JobsListResponse>(`${BASE}/jobs`);
}

export function getSectionRaw(jobId: string, sectionName: string) {
  // section names can contain '/' (e.g. "AC ON/OFF"), so we keep slashes
  // literal but encode the other special characters.
  const safe = sectionName.split("/").map(encodeURIComponent).join("/");
  return jsonFetch<SectionRawResponse>(
    `${BASE}/jobs/${jobId}/sections/raw/${safe}`,
  );
}

export function getSectionSemantic(jobId: string, sectionName: string) {
  const safe = sectionName.split("/").map(encodeURIComponent).join("/");
  return jsonFetch<SectionSemanticResponse>(
    `${BASE}/jobs/${jobId}/sections/semantic/${safe}`,
  );
}

export const exportUrl = {
  excel: (jobId: string) => `${BASE}/jobs/${jobId}/export/excel`,
  pdf: (jobId: string) => `${BASE}/jobs/${jobId}/export/pdf`,
  json: (jobId: string) => `${BASE}/jobs/${jobId}/export/json`,
  csv: (jobId: string) => `${BASE}/jobs/${jobId}/export/csv`,
};
