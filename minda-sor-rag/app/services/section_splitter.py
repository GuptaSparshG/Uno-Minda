"""Section splitter — maps Docling's structured items to our RawBlock schema.

Walks the flat item stream from pdf_extractor and:

  • Treats every SectionHeaderItem as the start of a new section. The
    section's heading text is preserved verbatim.
  • Groups consecutive ListItems into one bullet_list block.
  • Emits each TextItem as a paragraph block.
  • Emits each TableItem as a table block (headers + rows preserved).
  • Skips PictureItems (no text content to classify).

The classifier-input statement list is built in parallel: each list item
becomes a "bullet" statement, each paragraph a "text" statement, each table
row a "table_row" statement.
"""

from __future__ import annotations

import re
from typing import Any


def split_into_sections(extraction_result: dict[str, Any]) -> list[dict[str, Any]]:
    items = extraction_result.get("items") or []
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending_list: list[str] = []

    def flush_list_into(sec: dict[str, Any]) -> None:
        nonlocal pending_list
        if pending_list:
            sec["blocks"].append({"type": "bullet_list", "items": list(pending_list)})
            for it in pending_list:
                if len(it) >= 5:
                    sec["statements"].append(
                        {"text": _normalize(it), "source_type": "bullet"}
                    )
            pending_list = []

    def ensure_current() -> dict[str, Any]:
        nonlocal current
        if current is None:
            current = _new_section("General", level=0)
        return current

    for item in items:
        kind = item["kind"]

        if kind == "section":
            if current is not None:
                flush_list_into(current)
                sections.append(current)
            current = _new_section(item["text"], level=item.get("level", 1))
            continue

        sec = ensure_current()

        if kind == "list":
            # Re-attach the original PDF marker (e.g. ➢, •, ·) if Docling
            # gave us one — otherwise leave the text as-is.
            marker = (item.get("marker") or "").strip()
            text_in = item["text"]
            pending_list.append(f"{marker} {text_in}".strip() if marker else text_in)
        elif kind == "text":
            flush_list_into(sec)
            # Docling sometimes lumps inline bullets/numbered/lettered/middle-dot
            # markers into one big TextItem. Split them into properly-typed blocks
            # so the UI shows real structure rather than one wall of text.
            for blk in _split_paragraph(item["text"]):
                sec["blocks"].append(blk)
                _emit_statements_for_block(blk, sec["statements"])
        elif kind == "table":
            flush_list_into(sec)
            headers = item.get("headers") or []
            rows = item.get("rows") or []
            sec["blocks"].append(
                {"type": "table", "headers": headers, "rows": rows}
            )
            for row in rows:
                row_text = _row_to_text(headers, row)
                if row_text:
                    sec["statements"].append(
                        {"text": row_text, "source_type": "table_row"}
                    )
        elif kind == "picture":
            flush_list_into(sec)
            sec["blocks"].append(
                {
                    "type": "picture",
                    "image_base64": item.get("image_base64"),
                    "caption": item.get("caption"),
                    "page": item.get("page"),
                }
            )

    if current is not None:
        flush_list_into(current)
        sections.append(current)

    # Drop the implicit "General" pre-heading if empty
    if (
        sections
        and sections[0]["heading"] == "General"
        and not (sections[0]["blocks"] or sections[0]["statements"])
    ):
        sections = sections[1:]

    for sec in sections:
        sec["heading_only"] = not (sec["blocks"] or sec["statements"])

    return _merge_duplicates(sections)


def _new_section(heading: str, level: int) -> dict[str, Any]:
    return {
        "heading": heading,
        "level": level,
        "blocks": [],
        "statements": [],
    }


# ─────────────────────────── inline-structure splitter ───────────────────────
#
# Docling sometimes returns one big TextItem that actually contains multiple
# inline structural markers (➢ • · 1. 2. f. g. h.). We post-process those into
# properly-typed blocks. The text content of every segment is preserved
# **verbatim** — we only group / type it. No edits, no reordering.

_BULLET_MARKERS = "➢•▪►▸"
_BULLET_SPLIT_RE = re.compile(rf"\s*([{re.escape(_BULLET_MARKERS)}])\s+")
_NUMBERED_RE = re.compile(r"(?<![\w.])(\d{1,2})\.\s+(?=[A-Z(])")
_LETTERED_RE = re.compile(r"(?:^|\s)([a-zA-Z])\.\s+(?=[A-Z(])")
_MIDDOT_SPLIT_RE = re.compile(r"\s+·\s+")


def _split_paragraph(text: str) -> list[dict[str, Any]]:
    """Turn a single Docling TextItem into one or more typed blocks.

    Original markers (➢ • ▪ ► ▸ · 1. 2. f. g. …) are **preserved verbatim** at
    the start of each item — never stripped — so the UI shows exactly what
    the PDF shows. Block typing (bullet_list vs numbered_list vs paragraph)
    is only used for grouping / visual indent; the UI does NOT prepend its
    own bullet character.

    Priority of markers detected inline:
      1. ➢ • ▪ ► ▸    → bullet_list (each item starts with its marker)
      2. 1. 2. 3.     → numbered_list (item text starts with "1.")
      3. f. g. h.     → numbered_list (lettered enumeration, 3+ items)
      4. · text · …   → bullet_list (middle-dot)
      5. nothing      → paragraph (unchanged)
    """
    text = (text or "").strip()
    if not text:
        return []

    # ── 1) Major bullet markers (➢ • ▪ ► ▸)
    parts = _BULLET_SPLIT_RE.split(text)
    if len(parts) > 1:
        out: list[dict[str, Any]] = []
        head = parts[0].strip()
        if head:
            out.extend(_split_paragraph(head))
        items: list[str] = []
        # parts = [head, marker1, body1, marker2, body2, …]
        # Preserve the marker at the start of each item.
        for i in range(1, len(parts) - 1, 2):
            marker = parts[i]
            body = parts[i + 1].strip()
            if body:
                items.append(f"{marker} {body}")
        if items:
            out.append({"type": "bullet_list", "items": items})
        return out

    # ── 2) Inline numbered enumeration ("1. … 2. …")
    nums = list(_NUMBERED_RE.finditer(text))
    if len(nums) >= 2:
        return _segments_to_list_block(text, nums, "numbered_list")

    # ── 3) Lettered enumeration ("f. … g. … h. …")
    lets = list(_LETTERED_RE.finditer(text))
    if len(lets) >= 3:
        return _segments_to_list_block(text, lets, "numbered_list")

    # ── 4) Middle-dot sub-bullets ("· text · text")
    if _MIDDOT_SPLIT_RE.search(text):
        out_dot: list[dict[str, Any]] = []
        first_match = _MIDDOT_SPLIT_RE.search(text)
        prefix = text[: first_match.start()].strip()
        if prefix:
            out_dot.append({"type": "paragraph", "text": prefix})
        # Split the rest on " · " and re-attach "·" to each item.
        tail = text[first_match.start():]  # includes the first "·"
        # Split keeping the "·" at the start of each segment.
        raw_items = re.split(r"\s+(?=·\s)", tail)
        items_dot = [it.strip() for it in raw_items if it.strip()]
        if items_dot:
            out_dot.append({"type": "bullet_list", "items": items_dot})
        if out_dot:
            return out_dot

    # ── 5) Plain paragraph
    return [{"type": "paragraph", "text": text}]


def _segments_to_list_block(
    text: str,
    matches: list[re.Match],
    block_type: str,
) -> list[dict[str, Any]]:
    """Given regex matches that mark item boundaries, return
    [optional paragraph prefix] + [list block].

    Each item includes its original marker prefix (e.g. "1.", "f.")
    so the UI can display the PDF's exact ordering character.
    """
    out: list[dict[str, Any]] = []
    prefix = text[: matches[0].start()].strip()
    if prefix:
        out.append({"type": "paragraph", "text": prefix})
    items: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()  # include the marker (e.g. "1." or "f.")
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[start:end].strip()
        if seg:
            items.append(seg)
    if items:
        out.append({"type": block_type, "items": items})
    return out


def _emit_statements_for_block(
    block: dict[str, Any],
    statements: list[dict[str, str]],
) -> None:
    """Push classifier-input statements for a freshly-emitted block, using a
    source_type that matches the block's type so the LLM knows the provenance.
    """
    btype = block["type"]
    if btype == "paragraph":
        txt = block.get("text") or ""
        if len(txt.strip()) >= 5:
            statements.append({"text": _normalize(txt), "source_type": "text"})
    elif btype == "bullet_list":
        for item in block.get("items", []) or []:
            if len(item.strip()) >= 5:
                statements.append({"text": _normalize(item), "source_type": "bullet"})
    elif btype == "numbered_list":
        for item in block.get("items", []) or []:
            if len(item.strip()) >= 5:
                statements.append({"text": _normalize(item), "source_type": "numbered"})
    # heading / table / picture statements are emitted elsewhere


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _row_to_text(headers: list[str], row: list[str]) -> str:
    """Turn a table row into one statement string for the classifier."""
    cells = [c for c in row if c and c.strip()]
    if not cells:
        return ""
    if len(headers) == len(row) and any(h.strip() for h in headers):
        pairs = [f"{h}: {v}" for h, v in zip(headers, row) if v and v.strip()]
        return _normalize(", ".join(pairs))
    return _normalize(" | ".join(cells))


def _merge_duplicates(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse TOC + body duplicate sections (e.g. '11- GD&T' + 'GD&T')."""
    def norm_key(heading: str) -> str:
        s = re.sub(r"^\d+\s*[-.:)]\s*", "", heading or "")
        s = s.strip().rstrip(".:")
        s = re.sub(r"[^A-Za-z0-9]+", " ", s).strip().lower()
        return s

    groups: dict[str, list[int]] = {}
    order: list[str] = []
    for i, sec in enumerate(sections):
        k = norm_key(sec["heading"])
        if not k:
            k = f"__unique_{i}__"
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(i)

    merged: list[dict[str, Any]] = []
    for k in order:
        idxs = groups[k]
        if len(idxs) == 1:
            merged.append(sections[idxs[0]])
            continue
        members = [sections[i] for i in idxs]
        members.sort(
            key=lambda s: (len(s["blocks"]) + len(s["statements"])),
            reverse=True,
        )
        canonical = dict(members[0])
        canonical["blocks"] = list(canonical["blocks"])
        canonical["statements"] = list(canonical["statements"])
        for other in members[1:]:
            canonical["blocks"].extend(other["blocks"])
            canonical["statements"].extend(other["statements"])
        canonical["heading_only"] = not (
            canonical["blocks"] or canonical["statements"]
        )
        merged.append(canonical)
    return merged
