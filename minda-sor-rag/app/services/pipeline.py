"""End-to-end orchestrator: PDF → AnalysisResult + Excel + PDF reports."""

from __future__ import annotations

import os

from app.config import settings
from app.schemas import AnalysisResult, AnalyzedStatement, RawBlock, SectionResult
from app.services import (
    classifier,
    pdf_extractor,
    report_excel,
    report_pdf,
    section_splitter,
)
from app.services.rule_engine import RuleEngine


def analyze_pdf(
    pdf_path: str,
    display_filename: str | None = None,
    job_id: str | None = None,
) -> AnalysisResult:
    """Run the full extract → split → classify → rule-check pipeline.

    Returns the AnalysisResult in memory. No disk writes, no reports.
    Use this for the stateless POST /analyze endpoint.
    """
    extraction = pdf_extractor.extract_text(pdf_path)
    raw_sections = section_splitter.split_into_sections(extraction)

    # Build the dict that classify_sections expects: {section_name: [{text, source_type}]}
    classifier_input: dict[str, list[dict[str, str]]] = {
        sec["heading"]: sec["statements"] for sec in raw_sections if sec["statements"]
    }
    classified = classifier.classify_sections(classifier_input)

    rule_engine = RuleEngine()
    all_sections: list[SectionResult] = []
    global_id = 1

    for raw_sec in raw_sections:
        section_name = raw_sec["heading"]
        statements_data = classified.get(section_name, [])

        section_statements: list[AnalyzedStatement] = []
        for stmt_data in statements_data:
            rules_result = rule_engine.analyze(stmt_data["text"])
            section_statements.append(
                AnalyzedStatement(
                    id=f"SOR-{global_id:03d}",
                    section=section_name,
                    text=stmt_data["text"],
                    source_type=stmt_data.get("source_type", "text"),
                    classification=stmt_data["classification"],
                    classification_reason=stmt_data.get("reason", ""),
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
            )
            global_id += 1

        blocks = [RawBlock(**b) for b in raw_sec.get("blocks", [])]
        n = max(len(section_statements), 1)
        all_sections.append(
            SectionResult(
                section_name=section_name,
                heading_only=bool(raw_sec.get("heading_only", False))
                and not section_statements,
                blocks=blocks,
                total=len(section_statements),
                requirements=sum(
                    1 for s in section_statements if s.classification == "REQUIREMENT"
                ),
                recommendations=sum(
                    1
                    for s in section_statements
                    if s.classification == "RECOMMENDATION"
                ),
                asks=sum(1 for s in section_statements if s.classification == "ASK"),
                informational=sum(
                    1
                    for s in section_statements
                    if s.classification == "INFORMATIONAL"
                ),
                avg_quality_score=round(
                    sum(s.quality_score for s in section_statements) / n, 1
                )
                if section_statements
                else 0.0,
                statements=section_statements,
            )
        )

    result = AnalysisResult(
        job_id=job_id or "",
        filename=display_filename or os.path.basename(pdf_path),
        total_statements=global_id - 1,
        total_sections=len(all_sections),
        sections=all_sections,
    )

    _log_result(result)
    return result


def run_pipeline(
    pdf_path: str,
    job_id: str,
    display_filename: str | None = None,
) -> AnalysisResult:
    """Stateful pipeline used by the legacy /upload + /jobs endpoints.

    Runs analyze_pdf, then persists JSON + Excel + PDF reports to storage/
    and prunes old jobs. The stateless /analyze endpoint calls analyze_pdf
    directly and skips all the disk writes.
    """
    result = analyze_pdf(pdf_path, display_filename=display_filename, job_id=job_id)

    os.makedirs(settings.RESULTS_DIR, exist_ok=True)
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)

    results_path = os.path.join(settings.RESULTS_DIR, f"{job_id}.json")
    with open(results_path, "w") as f:
        f.write(result.model_dump_json(indent=2))

    xlsx_path = os.path.join(settings.EXPORT_DIR, f"{job_id}.xlsx")
    report_excel.generate(result, xlsx_path)

    pdf_out = os.path.join(settings.EXPORT_DIR, f"{job_id}.pdf")
    try:
        report_pdf.generate(result, pdf_out)
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(
            "PDF report generation failed (weasyprint deps missing?): %s", e
        )

    _prune_old_jobs()
    return result


def _log_result(result: AnalysisResult) -> None:
    """Print the final analysis JSON to stdout so the operator can see it in the log."""
    bar = "=" * 80
    print(f"\n{bar}\nANALYSIS COMPLETE — job_id={result.job_id}\n{bar}", flush=True)
    print(result.model_dump_json(indent=2), flush=True)
    print(f"{bar}\n", flush=True)


def _prune_old_jobs() -> None:
    """Keep only the latest N jobs across results / uploads / exports.

    Iterates result JSONs by mtime; the oldest beyond MAX_RETAINED_JOBS are
    deleted along with their matching .pdf / .xlsx / .pdf-report siblings.
    """
    cap = settings.MAX_RETAINED_JOBS
    if cap <= 0:
        return

    results_dir = settings.RESULTS_DIR
    if not os.path.isdir(results_dir):
        return

    try:
        result_files = [
            (f, os.path.getmtime(os.path.join(results_dir, f)))
            for f in os.listdir(results_dir)
            if f.endswith(".json")
        ]
    except OSError:
        return
    if len(result_files) <= cap:
        return

    result_files.sort(key=lambda x: x[1], reverse=True)  # newest first
    to_delete = result_files[cap:]

    import logging

    logger = logging.getLogger(__name__)
    for fname, _ in to_delete:
        job_id = fname[:-5]  # strip ".json"
        for path in (
            os.path.join(results_dir, f"{job_id}.json"),
            os.path.join(settings.UPLOAD_DIR, f"{job_id}.pdf"),
            os.path.join(settings.EXPORT_DIR, f"{job_id}.xlsx"),
            os.path.join(settings.EXPORT_DIR, f"{job_id}.pdf"),
        ):
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError as e:
                logger.warning("Failed to prune %s: %s", path, e)
        logger.info("Pruned old job %s (retention cap=%d)", job_id, cap)
