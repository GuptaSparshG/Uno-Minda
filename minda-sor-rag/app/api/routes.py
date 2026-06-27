"""FastAPI routes. /upload is synchronous (demo): processes and returns in one call."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.schemas import (
    AnalysisResult,
    JobListItem,
    JobsListResponse,
    SectionSummary,
    SectionsResponse,
    SummaryResponse,
    UploadResponse,
)
from app.services.pipeline import analyze_pdf, run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(file: UploadFile = File(...)) -> AnalysisResult:
    """Stateless: upload PDF, get full AnalysisResult back in one response.

    No `job_id`, no server-side storage. The response contains every section
    (with raw `blocks` for Section Analysis and `statements` for Semantic
    Analysis). The UI is responsible for caching / history.

    Synchronous — connection stays open for 30s–5m depending on PDF size.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_PDF_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Max: {settings.MAX_PDF_SIZE_MB} MB.",
        )
    if not contents.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF.")

    import tempfile

    with tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False
    ) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = await asyncio.to_thread(
            analyze_pdf, tmp_path, file.filename
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Stateless analyze failed")
        raise HTTPException(status_code=500, detail=f"Analyze failed: {e}") from e
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return result


@router.post("/export/excel")
async def export_excel_stateless(result: AnalysisResult):
    """Stateless: POST an AnalysisResult JSON in, get .xlsx back."""
    return await _build_export(result, "xlsx")


@router.post("/export/csv")
async def export_csv_stateless(result: AnalysisResult):
    """Stateless: POST an AnalysisResult JSON in, get .csv back."""
    return await _build_export(result, "csv")


@router.post("/export/pdf")
async def export_pdf_stateless(result: AnalysisResult):
    """Stateless: POST an AnalysisResult JSON in, get .pdf back.

    Returns 503 if weasyprint native deps aren't installed on the server.
    """
    return await _build_export(result, "pdf")


async def _build_export(result: AnalysisResult, fmt: str):
    """Run the report generator into a temp file, stream it back, clean up."""
    import tempfile

    from fastapi.responses import Response

    from app.services import report_excel, report_pdf

    suffix = f".{fmt}"
    base = (result.filename or "analysis").rsplit(".", 1)[0]
    fname = f"{base}{suffix}"

    if fmt == "csv":
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id", "section", "classification", "iso_category", "obligation",
                "quality_score", "verifiability", "violated_rules",
                "classification_reason", "suggested_action", "text",
            ]
        )
        for sec in result.sections:
            for s in sec.statements:
                writer.writerow(
                    [
                        s.id, s.section, s.classification, s.iso_category,
                        s.obligation_keyword, s.quality_score, s.verifiability,
                        ", ".join(s.violated_rules),
                        s.classification_reason or "", s.suggested_action,
                        s.text,
                    ]
                )
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
    try:
        if fmt == "xlsx":
            await asyncio.to_thread(report_excel.generate, result, tmp_path)
            media = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        elif fmt == "pdf":
            try:
                await asyncio.to_thread(report_pdf.generate, result, tmp_path)
            except Exception as e:
                logger.warning("PDF export failed: %s", e)
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "PDF generation requires weasyprint native libs "
                        "(pango, cairo, gdk-pixbuf, libffi)."
                    ),
                ) from e
            media = "application/pdf"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown format: {fmt}")

        with open(tmp_path, "rb") as f:
            data = f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str) -> dict[str, str]:
    """Remove a single job's files from all storage subdirs.

    Returns 200 with a list of removed paths even if some artifacts were
    already missing. 404 if no trace of the job exists anywhere.
    """
    removed: list[str] = []
    candidates = [
        os.path.join(settings.RESULTS_DIR, f"{job_id}.json"),
        os.path.join(settings.UPLOAD_DIR, f"{job_id}.pdf"),
        os.path.join(settings.EXPORT_DIR, f"{job_id}.xlsx"),
        os.path.join(settings.EXPORT_DIR, f"{job_id}.pdf"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                os.remove(path)
                removed.append(path)
            except OSError as e:
                logger.warning("Failed to remove %s: %s", path, e)
    if not removed:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job_id": job_id, "removed_count": str(len(removed))}


@router.get("/jobs", response_model=JobsListResponse)
def list_jobs() -> JobsListResponse:
    items: list[JobListItem] = []
    if not os.path.isdir(settings.RESULTS_DIR):
        return JobsListResponse(jobs=[])
    for fname in os.listdir(settings.RESULTS_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(settings.RESULTS_DIR, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            req = sum(
                1
                for sec in data.get("sections", [])
                for s in sec.get("statements", [])
                if s.get("classification") == "REQUIREMENT"
            )
            ask = sum(
                1
                for sec in data.get("sections", [])
                for s in sec.get("statements", [])
                if s.get("classification") == "ASK"
            )
            items.append(
                JobListItem(
                    job_id=data["job_id"],
                    filename=data["filename"],
                    total_statements=data["total_statements"],
                    total_sections=data["total_sections"],
                    requirements_count=req,
                    asks_count=ask,
                    created_at=datetime.fromtimestamp(
                        os.path.getmtime(path)
                    ).isoformat(timespec="seconds"),
                )
            )
        except (OSError, KeyError, json.JSONDecodeError) as e:
            logger.warning("Skipping malformed result file %s: %s", fname, e)
    items.sort(key=lambda j: j.created_at, reverse=True)
    return JobsListResponse(jobs=items)


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_PDF_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Max: {settings.MAX_PDF_SIZE_MB} MB.",
        )
    if not contents.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF.")

    job_id = str(uuid.uuid4())
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    pdf_path = os.path.join(settings.UPLOAD_DIR, f"{job_id}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(contents)

    try:
        # Offload the blocking pipeline (Docling + LLM batches + report
        # generation) to a worker thread so the event loop stays responsive
        # for other readers (sections, summaries, downloads) during long
        # uploads.
        await asyncio.to_thread(
            run_pipeline, pdf_path, job_id, file.filename
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Pipeline failure for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}") from e

    return UploadResponse(job_id=job_id, filename=file.filename, status="completed")


@router.get("/jobs/{job_id}/results", response_model=AnalysisResult)
def get_results(job_id: str) -> AnalysisResult:
    data = _load_result(job_id)
    return AnalysisResult.model_validate(data)


@router.get("/jobs/{job_id}/summary", response_model=SummaryResponse)
def get_summary(job_id: str) -> SummaryResponse:
    data = _load_result(job_id)
    result = AnalysisResult.model_validate(data)

    totals = Counter()
    statements_with_issues = 0
    quality_sum = 0
    count = 0
    rule_counter: Counter[str] = Counter()

    for sec in result.sections:
        for stmt in sec.statements:
            totals[stmt.classification] += 1
            count += 1
            quality_sum += stmt.quality_score
            if stmt.violated_rules:
                statements_with_issues += 1
            for r in stmt.violated_rules:
                rule_counter[r] += 1

    avg = round(quality_sum / count, 1) if count else 0.0

    return SummaryResponse(
        job_id=job_id,
        filename=result.filename,
        total_statements=result.total_statements,
        total_sections=result.total_sections,
        requirements_count=totals["REQUIREMENT"],
        recommendations_count=totals["RECOMMENDATION"],
        asks_count=totals["ASK"],
        informational_count=totals["INFORMATIONAL"],
        statements_with_issues=statements_with_issues,
        avg_quality_score=avg,
        rule_violation_counts=dict(rule_counter),
    )


@router.get("/jobs/{job_id}/sections/raw/{section_name:path}")
def get_section_raw(job_id: str, section_name: str):
    """Return the EXACT untouched content of a section: ordered blocks
    (paragraph / bullet_list / numbered_list / table). No classification applied."""
    data = _load_result(job_id)
    target = section_name
    for sec in data.get("sections", []):
        if sec.get("section_name") == target:
            return {
                "job_id": job_id,
                "section_name": sec.get("section_name"),
                "heading_only": sec.get("heading_only", False),
                "blocks": sec.get("blocks", []),
            }
    raise HTTPException(status_code=404, detail="Section not found.")


@router.get("/jobs/{job_id}/sections/semantic/{section_name:path}")
def get_section_semantic(job_id: str, section_name: str):
    """Return classified statements for the section, grouped by class."""
    data = _load_result(job_id)
    target = section_name
    for sec in data.get("sections", []):
        if sec.get("section_name") == target:
            stmts = sec.get("statements", [])
            buckets: dict[str, list] = {
                "REQUIREMENT": [],
                "ASK": [],
                "RECOMMENDATION": [],
                "INFORMATIONAL": [],
            }
            for s in stmts:
                cls = s.get("classification", "INFORMATIONAL")
                buckets.setdefault(cls, []).append(s)
            return {
                "job_id": job_id,
                "section_name": sec.get("section_name"),
                "totals": {
                    "REQUIREMENT": sec.get("requirements", 0),
                    "RECOMMENDATION": sec.get("recommendations", 0),
                    "ASK": sec.get("asks", 0),
                    "INFORMATIONAL": sec.get("informational", 0),
                },
                "groups": buckets,
            }
    raise HTTPException(status_code=404, detail="Section not found.")


@router.get("/jobs/{job_id}/sections", response_model=SectionsResponse)
def get_sections(job_id: str) -> SectionsResponse:
    data = _load_result(job_id)
    result = AnalysisResult.model_validate(data)
    summaries = [
        SectionSummary(
            section_name=s.section_name,
            total=s.total,
            requirements=s.requirements,
            recommendations=s.recommendations,
            asks=s.asks,
            informational=s.informational,
            avg_quality_score=s.avg_quality_score,
        )
        for s in result.sections
    ]
    return SectionsResponse(job_id=job_id, sections=summaries)


@router.get("/jobs/{job_id}/export/excel")
def export_excel(job_id: str) -> FileResponse:
    path = os.path.join(settings.EXPORT_DIR, f"{job_id}.xlsx")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Excel export not found.")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{job_id}.xlsx",
    )


@router.get("/jobs/{job_id}/export/pdf")
def export_pdf(job_id: str) -> FileResponse:
    path = os.path.join(settings.EXPORT_DIR, f"{job_id}.pdf")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="PDF export not found.")
    return FileResponse(path, media_type="application/pdf", filename=f"{job_id}.pdf")


@router.get("/jobs/{job_id}/export/json")
def export_json(job_id: str) -> FileResponse:
    path = os.path.join(settings.RESULTS_DIR, f"{job_id}.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Results JSON not found.")
    return FileResponse(path, media_type="application/json", filename=f"{job_id}.json")


@router.get("/jobs/{job_id}/export/csv")
def export_csv(job_id: str):
    import csv
    import io

    from fastapi.responses import Response

    data = _load_result(job_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "section",
            "classification",
            "iso_category",
            "obligation",
            "quality_score",
            "verifiability",
            "violated_rules",
            "classification_reason",
            "suggested_action",
            "text",
        ]
    )
    for sec in data.get("sections", []):
        for s in sec.get("statements", []):
            writer.writerow(
                [
                    s.get("id", ""),
                    s.get("section", ""),
                    s.get("classification", ""),
                    s.get("iso_category", ""),
                    s.get("obligation_keyword", ""),
                    s.get("quality_score", 0),
                    s.get("verifiability", ""),
                    ", ".join(s.get("violated_rules", [])),
                    s.get("classification_reason", ""),
                    s.get("suggested_action", ""),
                    s.get("text", ""),
                ]
            )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.csv"'},
    )


def _load_result(job_id: str) -> dict:
    path = os.path.join(settings.RESULTS_DIR, f"{job_id}.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Job not found.")
    with open(path) as f:
        return json.load(f)
