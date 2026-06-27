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

    # Per-section structural cleanups before duplicate-merging
    for sec in sections:
        sec["blocks"] = _post_process_blocks(sec["blocks"])
        sec["heading_only"] = not (sec["blocks"] or sec["statements"])

    return _merge_duplicates(sections)


# ─────────────────────────── post-processing passes ───────────────────────────
#
# Docling is line-granular; we fix the three common rough edges here so the
# /sections/raw response shows what the human actually wrote in the PDF.

_BULLET_CHARS = "➢•▪►▸·"


def _post_process_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run corrective passes on the in-memory block list:
      1. attach orphan bullet markers ('➢' alone) to the next paragraph
      2. join wrapped paragraphs (no terminal punctuation → continues)
      3. split mixed-marker lists + merge sequential enumerations (e → f)
      4. repair Docling's concatenated numbering ('1Final' → '1. Final')
    """
    blocks = _attach_orphan_markers(blocks)
    blocks = _join_wrapped_paragraphs(blocks)
    blocks = _split_and_merge_lists(blocks)
    blocks = _repair_concatenated_numbering(blocks)
    return blocks


def _repair_concatenated_numbering(
    blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Docling sometimes emits ListItems where the item number was stuck onto
    the text with no separator (e.g. '1Final CAD data', '22D drawing',
    '1818- Mould flow' — that last one is '18' + '18- Mould flow').

    Detect lists whose items match the sequence 1, 2, 3, … and insert '. '
    between the number prefix and the rest. Also flip the block type to
    numbered_list since it's clearly an enumeration.
    """
    out = []
    for b in blocks:
        if b["type"] not in ("bullet_list", "numbered_list") or not b.get("items"):
            out.append(b)
            continue
        items = list(b["items"])
        fixed, looks_numbered = _try_repair_sequence(items)
        if looks_numbered:
            out.append({"type": "numbered_list", "items": fixed})
        else:
            out.append(b)
    return out


def _try_repair_sequence(items: list[str]) -> tuple[list[str], bool]:
    """If items look like a 1,2,3,… sequence with no separator between number
    and text, repair to 'N. content'. Returns (fixed_items, did_repair).
    Only considered a sequence if EVERY item starts with the right number.
    """
    if len(items) < 2:
        return items, False

    fixed: list[str] = []
    looks_numbered = True
    for i, item in enumerate(items):
        expected = str(i + 1)
        s = item.lstrip()
        # Strip any existing common markers first so we work on the raw text
        if not s.startswith(expected):
            looks_numbered = False
            break
        rest = s[len(expected):]
        # Acceptable separators in source: '.', ')', ' ', or none (concat bug)
        if rest.startswith(". "):
            fixed.append(f"{expected}. {rest[2:].lstrip()}")
        elif rest.startswith(".") and len(rest) > 1 and rest[1] != " ":
            fixed.append(f"{expected}. {rest[1:].lstrip()}")
        elif rest.startswith(") "):
            fixed.append(f"{expected}. {rest[2:].lstrip()}")
        elif rest.startswith(" "):
            fixed.append(f"{expected}. {rest.lstrip()}")
        elif rest == "":
            fixed.append(f"{expected}.")
        else:
            # No separator at all — the Docling concatenation bug
            fixed.append(f"{expected}. {rest}")
    if not looks_numbered:
        return items, False
    return fixed, True


def _attach_orphan_markers(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """When a paragraph's text is JUST a bullet marker, glue it onto the next
    paragraph and emit a single bullet_list item that preserves the marker."""
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        text = (b.get("text") or "").strip() if b["type"] == "paragraph" else ""
        is_orphan = (
            b["type"] == "paragraph"
            and len(text) <= 2
            and text
            and text[0] in _BULLET_CHARS
        )
        if is_orphan and i + 1 < len(blocks):
            nxt = blocks[i + 1]
            if nxt["type"] == "paragraph":
                marker = text
                out.append(
                    {
                        "type": "bullet_list",
                        "items": [f"{marker} {(nxt.get('text') or '').strip()}"],
                    }
                )
                i += 2
                continue
        out.append(dict(b))
        i += 1
    return out


_TERMINAL_PUNCT = set(".!?")
_NEUTRAL_END = set(":;)]\"'")


def _join_wrapped_paragraphs(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive paragraph blocks that look like one wrapped sentence,
    and also bridge wrap-continuation from a list's LAST item into the next
    paragraph (PDF bullets can wrap into what looks like a separate text)."""
    out: list[dict[str, Any]] = []
    for b in blocks:
        if not out:
            out.append(dict(b))
            continue
        prev = out[-1]

        # paragraph → paragraph wrap-merge
        if (
            b["type"] == "paragraph"
            and prev["type"] == "paragraph"
            and _is_wrap_continuation(prev.get("text", ""), b.get("text", ""))
        ):
            prev["text"] = prev["text"].rstrip() + " " + (b.get("text") or "").lstrip()
            continue

        # list's last item → paragraph wrap-merge
        if (
            b["type"] == "paragraph"
            and prev["type"] in ("bullet_list", "numbered_list")
            and prev.get("items")
            and _is_wrap_continuation(prev["items"][-1], b.get("text", ""))
        ):
            prev["items"][-1] = (
                prev["items"][-1].rstrip()
                + " "
                + (b.get("text") or "").lstrip()
            )
            continue

        out.append(dict(b))
    return out


def _is_wrap_continuation(prev_text: str, next_text: str) -> bool:
    if not prev_text or not next_text:
        return False
    last = prev_text.rstrip()[-1] if prev_text.rstrip() else ""
    first = next_text.lstrip()[:1]
    if not last or not first:
        return False
    # Hard sentence terminators → never wrap-continue
    if last in _TERMINAL_PUNCT:
        return False
    # Heading-style colon / closing punctuation → don't wrap-merge
    if last in _NEUTRAL_END:
        return False
    # Comma at end → almost certainly continues
    if last == ",":
        return True
    # Next starts lowercase → continues
    if first.isalpha() and first.islower():
        return True
    # prev ends with a digit and next starts with a unit-like word
    if last.isdigit():
        return True
    return False


def _split_and_merge_lists(
    blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Two passes:
       (a) split a list block whose items have mixed marker categories
       (b) merge consecutive list blocks whose markers form a continuous
           enumeration (e → f, 1 → 2, …)
    """
    # ── (a) split mixed-category lists
    split_out: list[dict[str, Any]] = []
    for b in blocks:
        if b["type"] not in ("bullet_list", "numbered_list") or not b.get("items"):
            split_out.append(b)
            continue
        # Group consecutive items by marker category
        groups: list[tuple[str, list[str]]] = []
        cur_cat: str | None = None
        cur_items: list[str] = []
        for it in b["items"]:
            cat = _marker_category(it)
            if cat != cur_cat and cur_items:
                groups.append((cur_cat or "none", cur_items))
                cur_items = []
            cur_cat = cat
            cur_items.append(it)
        if cur_items:
            groups.append((cur_cat or "none", cur_items))

        if len(groups) == 1:
            split_out.append(b)
        else:
            for cat, items in groups:
                btype = "numbered_list" if cat == "enumeration" else "bullet_list"
                split_out.append({"type": btype, "items": items})

    # ── (b) merge sequential enumerations
    merged: list[dict[str, Any]] = []
    for b in split_out:
        if (
            merged
            and merged[-1]["type"] in ("bullet_list", "numbered_list")
            and b["type"] in ("bullet_list", "numbered_list")
            and merged[-1].get("items")
            and b.get("items")
        ):
            prev_mk = _extract_enum_marker(merged[-1]["items"][-1])
            next_mk = _extract_enum_marker(b["items"][0])
            if prev_mk and next_mk and _is_sequential_marker(prev_mk, next_mk):
                merged[-1] = {
                    "type": "numbered_list",
                    "items": list(merged[-1]["items"]) + list(b["items"]),
                }
                continue
        merged.append(b)
    return merged


def _marker_category(item: str) -> str:
    if not item:
        return "none"
    s = item.lstrip()
    if not s:
        return "none"
    if s[0] in "➢•▪►▸":
        return "decoration"
    if s[0] == "·":
        return "sub-decoration"
    if re.match(r"^[a-zA-Z]\.\s|^\d+\.\s", s):
        return "enumeration"
    return "none"


def _extract_enum_marker(item: str) -> str | None:
    m = re.match(r"^([a-zA-Z]|\d+)\.\s", (item or "").lstrip())
    return m.group(1) if m else None


def _is_sequential_marker(prev: str, nxt: str) -> bool:
    if not prev or not nxt:
        return False
    if prev.isdigit() and nxt.isdigit():
        return int(nxt) == int(prev) + 1
    if len(prev) == 1 and len(nxt) == 1 and prev.isalpha() and nxt.isalpha():
        # Treat 'I' (uppercase I) and 'l' kindly — PDFs often confuse i/I
        return ord(nxt.lower()) == ord(prev.lower()) + 1
    return False


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
