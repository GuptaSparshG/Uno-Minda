"""PDF report generator (weasyprint).

Renders an HTML string to PDF. Requires system libs (libpango, libcairo,
libgdk-pixbuf, libffi) — see Dockerfile.
"""

from __future__ import annotations

import html as html_lib

from app.schemas import AnalysisResult

CSS = """
  body { font-family: Arial, sans-serif; margin: 40px; font-size: 11px; }
  h1 { color: #1a365d; font-size: 22px; }
  h2 { color: #2c5282; font-size: 16px; margin-top: 30px; border-bottom: 2px solid #2c5282; padding-bottom: 4px; }
  h3 { color: #2d3748; font-size: 13px; }
  table { width: 100%; border-collapse: collapse; margin: 10px 0; }
  th { background: #1a365d; color: white; padding: 6px 8px; text-align: left; font-size: 10px; }
  td { padding: 5px 8px; border-bottom: 1px solid #e2e8f0; font-size: 10px; vertical-align: top; }
  tr:nth-child(even) { background: #f7fafc; }
  .req { color: #1a365d; font-weight: bold; }
  .rec { color: #744210; }
  .ask { color: #553c9a; }
  .info { color: #718096; }
  .score-good { color: #276749; font-weight: bold; }
  .score-warn { color: #975a16; font-weight: bold; }
  .score-bad { color: #c53030; font-weight: bold; }
  .stat-box { display: inline-block; padding: 8px 16px; margin: 4px; background: #ebf8ff; border-radius: 4px; }
  .stat-num { font-size: 20px; font-weight: bold; color: #2c5282; }
  .stat-label { font-size: 9px; color: #718096; }
  @page { margin: 1.5cm; @bottom-center { content: "Page " counter(page) " of " counter(pages); font-size: 9px; } }
"""

CLASS_CSS = {
    "REQUIREMENT": "req",
    "RECOMMENDATION": "rec",
    "ASK": "ask",
    "INFORMATIONAL": "info",
}


def generate(result: AnalysisResult, output_path: str) -> None:
    from weasyprint import HTML

    html = _build_html(result)
    HTML(string=html).write_pdf(output_path)


def _build_html(result: AnalysisResult) -> str:
    totals = {"REQUIREMENT": 0, "RECOMMENDATION": 0, "ASK": 0, "INFORMATIONAL": 0}
    for sec in result.sections:
        totals["REQUIREMENT"] += sec.requirements
        totals["RECOMMENDATION"] += sec.recommendations
        totals["ASK"] += sec.asks
        totals["INFORMATIONAL"] += sec.informational

    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<style>{CSS}</style></head><body>",
        "<h1>SOR Requirements Analysis Report</h1>",
        f"<p>File: {html_lib.escape(result.filename)} | "
        f"Statements: {result.total_statements} | "
        f"Sections: {result.total_sections}</p>",
        "<div>",
        _stat_box(totals["REQUIREMENT"], "Requirements"),
        _stat_box(totals["RECOMMENDATION"], "Recommendations"),
        _stat_box(totals["ASK"], "Asks"),
        _stat_box(totals["INFORMATIONAL"], "Informational"),
        "</div>",
    ]

    for section in result.sections:
        parts.append(f"<h2>{html_lib.escape(section.section_name)}</h2>")
        parts.append(
            f"<p>Requirements: {section.requirements} | "
            f"Asks: {section.asks} | "
            f"Avg Score: {section.avg_quality_score}</p>"
        )
        parts.append(
            "<table><thead><tr>"
            "<th>ID</th><th>Classification</th><th>Statement</th>"
            "<th>Score</th><th>Issues</th>"
            "</tr></thead><tbody>"
        )
        for stmt in section.statements:
            cls = CLASS_CSS.get(stmt.classification, "info")
            score_cls = (
                "score-good"
                if stmt.quality_score >= 80
                else "score-warn"
                if stmt.quality_score >= 50
                else "score-bad"
            )
            issues = ", ".join(stmt.violated_rules) or "✓"
            parts.append(
                "<tr>"
                f"<td>{html_lib.escape(stmt.id)}</td>"
                f"<td class='{cls}'>{html_lib.escape(stmt.classification)}</td>"
                f"<td>{html_lib.escape(stmt.text)}</td>"
                f"<td class='{score_cls}'>{stmt.quality_score}</td>"
                f"<td>{html_lib.escape(issues)}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")

    parts.append("</body></html>")
    return "".join(parts)


def _stat_box(num: int, label: str) -> str:
    return (
        f"<div class='stat-box'>"
        f"<div class='stat-num'>{num}</div>"
        f"<div class='stat-label'>{html_lib.escape(label)}</div>"
        f"</div>"
    )
