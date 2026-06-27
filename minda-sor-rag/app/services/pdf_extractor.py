"""PDF extraction using Docling.

Returns a flat ordered list of typed items the section splitter can walk:

  {"kind": "section", "level": int, "text": str}    — SectionHeaderItem
  {"kind": "text", "text": str}                      — TextItem (paragraph)
  {"kind": "list", "text": str}                      — ListItem (one bullet)
  {"kind": "table", "headers": list, "rows": list}   — TableItem
  {"kind": "picture"}                                — PictureItem (placeholder)

We rely on Docling's layout model for heading detection / reading order /
table structure rather than heuristic font/score rules.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_CONVERTER = None


def _converter():
    """Lazy-init Docling once per process (model loading is slow).

    Picture image generation is OFF by default in Docling — we explicitly
    enable it so PictureItem.get_image(doc) returns real PIL images instead
    of None. images_scale=1.5 keeps each cropped picture readable without
    blowing up the response size.
    """
    global _CONVERTER
    if _CONVERTER is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        logger.info("Initializing Docling DocumentConverter (first call)…")
        pipeline_opts = PdfPipelineOptions()
        pipeline_opts.images_scale = 1.5
        pipeline_opts.generate_picture_images = True

        _CONVERTER = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)
            }
        )
    return _CONVERTER


def extract_text(pdf_path: str) -> dict[str, Any]:
    if not os.path.isfile(pdf_path):
        raise ValueError(f"PDF file not found: {pdf_path}")

    from docling_core.types.doc import (
        ListItem,
        PictureItem,
        SectionHeaderItem,
        TableItem,
        TextItem,
    )

    try:
        result = _converter().convert(pdf_path)
    except Exception as e:
        raise ValueError(f"Docling failed to parse PDF: {e}") from e

    doc = result.document

    items: list[dict[str, Any]] = []
    for item, level in doc.iterate_items():
        if isinstance(item, SectionHeaderItem):
            txt = (item.text or "").strip()
            if txt:
                items.append({"kind": "section", "level": int(level), "text": txt})
        elif isinstance(item, ListItem):
            txt = (item.text or "").strip()
            if txt:
                # Pull the original PDF bullet marker (➢, •, ·, …) when Docling
                # carries it; default to "•" only when the field is empty so
                # the UI always has *something* to render and never invents
                # a marker that wasn't there.
                marker = (getattr(item, "marker", None) or "").strip()
                items.append(
                    {"kind": "list", "text": txt, "marker": marker}
                )
        elif isinstance(item, TextItem):
            txt = (item.text or "").strip()
            if txt:
                items.append({"kind": "text", "text": txt})
        elif isinstance(item, TableItem):
            headers, rows = _extract_table(item, doc)
            if rows or headers:
                items.append(
                    {"kind": "table", "headers": headers, "rows": rows}
                )
        elif isinstance(item, PictureItem):
            pic = _extract_picture(item, doc)
            if pic is not None:
                items.append(pic)

    total_chars = sum(
        len(i.get("text", "") or "") for i in items if "text" in i
    )
    if total_chars < 100:
        raise ValueError(
            "PDF appears to be image-based or empty — Docling extracted < 100 chars."
        )

    return {
        "filename": os.path.basename(pdf_path),
        "items": items,
        "page_count": doc.num_pages(),
    }


def _extract_picture(picture_item, doc) -> dict[str, Any] | None:
    """Return a picture block dict with base64-encoded PNG and metadata.

    Returns None if the image can't be extracted (Docling occasionally yields
    PictureItems with no decodable image — usually inline vector art).
    """
    import base64
    import io

    try:
        img = picture_item.get_image(doc)
    except TypeError:
        # older docling-core: image is attribute, not method
        img = getattr(picture_item, "image", None)
    except Exception as e:
        logger.warning("Picture extraction failed: %s", e)
        return None

    if img is None:
        return None

    try:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        logger.warning("PNG encode failed: %s", e)
        return None

    caption = None
    try:
        cap = picture_item.caption_text(doc=doc)
        if cap:
            caption = cap.strip() or None
    except Exception:
        pass

    page = None
    try:
        # prov is a list of provenance records; the first one usually carries page_no
        prov = getattr(picture_item, "prov", None) or []
        if prov:
            page = int(getattr(prov[0], "page_no", None) or 0) or None
    except Exception:
        pass

    return {
        "kind": "picture",
        "image_base64": f"data:image/png;base64,{b64}",
        "caption": caption,
        "page": page,
    }


def _extract_table(table_item, doc) -> tuple[list[str], list[list[str]]]:
    """Pull headers + rows out of a Docling TableItem in a tolerant way."""
    try:
        df = table_item.export_to_dataframe(doc=doc)
    except TypeError:
        # older docling-core versions don't accept `doc`
        df = table_item.export_to_dataframe()
    except Exception as e:
        logger.warning("Could not export table to dataframe: %s", e)
        return [], []
    headers = [str(c) for c in df.columns]
    rows = [
        [("" if v is None else str(v)).strip() for v in row]
        for row in df.values.tolist()
    ]
    rows = [r for r in rows if any(c for c in r)]
    return headers, rows
