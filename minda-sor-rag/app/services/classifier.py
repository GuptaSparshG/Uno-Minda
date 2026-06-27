"""RAG retrieval + LLM batch classification.

Vector DB (Chroma / Pinecone) and LLM (OpenAI / self-hosted via
OpenAI-compatible endpoint) are both configurable via .env. Falls back to
keyword heuristics when the LLM is unreachable or returns malformed JSON,
so the demo keeps working even fully offline.
"""

from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.config import settings
from app.services.llm import get_llm_client
from app.services.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

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


def init_knowledge_base() -> None:
    """Seed the vector store on startup. Idempotent."""
    try:
        store = get_vector_store()
    except Exception as e:
        logger.warning("Vector store unavailable, skipping seed: %s", e)
        return

    try:
        if store.count() > 0:
            return
    except Exception as e:
        logger.warning("Vector store count() failed, skipping seed: %s", e)
        return

    kb_dir = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base")
    rules_path = os.path.join(kb_dir, "incose_rules.json")
    clauses_path = os.path.join(kb_dir, "iso29148_clauses.json")

    documents: list[str] = []
    ids: list[str] = []
    metadatas: list[dict[str, Any]] = []

    if os.path.isfile(rules_path):
        with open(rules_path) as f:
            for r in json.load(f):
                documents.append(r["text"])
                ids.append(r["id"])
                metadatas.append({"rule_id": r["rule_id"], "source": "INCOSE"})

    if os.path.isfile(clauses_path):
        with open(clauses_path) as f:
            for c in json.load(f):
                documents.append(c["text"])
                ids.append(c["id"])
                metadatas.append({"clause_id": c["clause_id"], "source": "ISO29148"})

    if documents:
        try:
            store.add(documents, ids, metadatas)
            logger.info(
                "Seeded %d docs into %s vector store",
                len(documents),
                settings.VECTOR_DB,
            )
        except Exception as e:
            logger.warning("Failed to seed vector store: %s", e)


def classify_sections(
    sections: dict[str, list[dict[str, str]]],
) -> dict[str, list[dict[str, Any]]]:
    """Classify every statement across all sections.

    Each `sections[name]` is a list of `{text, source_type}` dicts. The
    `source_type` is preserved through to the output. Batches across sections
    are processed in parallel; the section heading + source_type are passed
    to the LLM for semantic context.
    """
    client = get_llm_client()
    store: VectorStore | None
    try:
        store = get_vector_store()
    except Exception as e:
        logger.warning("Vector store unavailable, using fallback only: %s", e)
        store = None

    batch_size = settings.BATCH_SIZE
    top_k = settings.RETRIEVAL_TOP_K
    workers = max(1, settings.MAX_PARALLEL_BATCHES)

    # Flatten: (section, batch_idx, [{text, source_type}, ...])
    tasks: list[tuple[str, int, list[dict[str, str]]]] = []
    for section_name, statements in sections.items():
        for batch_idx, i in enumerate(range(0, len(statements), batch_size)):
            tasks.append((section_name, batch_idx, statements[i : i + batch_size]))

    results: dict[str, dict[int, list[dict[str, Any]]]] = {
        name: {} for name in sections
    }

    def process(
        task: tuple[str, int, list[dict[str, str]]],
    ) -> tuple[str, int, list[dict[str, Any]]]:
        section_name, batch_idx, batch = task
        texts = [b["text"] for b in batch]

        rag_context = ""
        if store is not None and texts:
            try:
                docs = store.query(texts[0], top_k=top_k)
                rag_context = "\n".join(docs)
            except Exception as e:
                logger.warning("Vector store query failed: %s", e)

        items = _call_llm(client, section_name, batch, rag_context)
        if items is None or len(items) < len(batch):
            items = _fallback_classify(texts, section_name)

        classified: list[dict[str, Any]] = []
        for idx, b in enumerate(batch):
            item = items[idx] if idx < len(items) else {}
            classified.append(
                {
                    "text": b["text"],
                    "source_type": b.get("source_type", "text"),
                    "classification": item.get("classification") or "INFORMATIONAL",
                    "iso_category": item.get("iso_category") or "Functional",
                    "obligation_keyword": item.get("obligation_keyword") or "none",
                    "reason": item.get("reason") or "",
                }
            )
        return section_name, batch_idx, classified

    if workers == 1 or len(tasks) <= 1:
        for t in tasks:
            section_name, batch_idx, classified = process(t)
            results[section_name][batch_idx] = classified
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed(pool.submit(process, t) for t in tasks):
                try:
                    section_name, batch_idx, classified = fut.result()
                except Exception as e:
                    logger.exception("Batch failed: %s", e)
                    continue
                results[section_name][batch_idx] = classified

    # Reassemble preserving section order + within-section batch order
    out: dict[str, list[dict[str, Any]]] = {}
    for section_name in sections:
        by_idx = results.get(section_name, {})
        merged: list[dict[str, Any]] = []
        for batch_idx in sorted(by_idx):
            merged.extend(by_idx[batch_idx])
        out[section_name] = merged
    return out


def _call_llm(
    client,
    section_name: str,
    batch: list[dict[str, str]],
    rag_context: str,
) -> list[dict[str, Any]] | None:
    statements_block = "\n".join(
        f"{i}. [{b.get('source_type', 'text')}] {b['text']}"
        for i, b in enumerate(batch)
    )
    user_prompt = (
        f'You are classifying statements from the SOR section: "{section_name}".\n'
        "Use the section name as semantic context — for example, a 'Safety' "
        "section makes Safety the default ISO category, a 'Manufacturing' or "
        "'PPAP' section biases toward Process, an 'Actuator' or 'Sensor' "
        "section biases toward Interface or Design Constraint. Each statement "
        "is prefixed by its source type in brackets — table_row items are "
        "typically REQUIREMENT (specification rows), bullet/numbered items "
        "follow obligation keywords.\n\n"
        f"Relevant INCOSE/ISO 29148 rules:\n{rag_context}\n\n"
        "Return ONLY a JSON object with key \"results\" whose value is an "
        "array. Each array element must have keys: \"index\" (int), "
        "\"classification\" (REQUIREMENT / RECOMMENDATION / ASK / "
        "INFORMATIONAL), \"iso_category\", \"obligation_keyword\", "
        "\"reason\" (≤20 words citing the trigger word or section context).\n\n"
        f"Statements (in section \"{section_name}\"):\n{statements_block}"
    )
    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
    except Exception as e:
        logger.warning("LLM classification call failed: %s", e)
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM response was not valid JSON: %s", raw[:200])
        return None

    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = None
        for v in parsed.values():
            if isinstance(v, list):
                items = v
                break
        if items is None:
            return None
    else:
        return None

    items_by_index: dict[int, dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        idx = it.get("index")
        if isinstance(idx, int) and 0 <= idx < len(batch):
            items_by_index[idx] = it

    out: list[dict[str, Any]] = []
    for i in range(len(batch)):
        it = items_by_index.get(i, {})
        out.append(
            {
                "classification": it.get("classification", "INFORMATIONAL"),
                "iso_category": it.get("iso_category", "Functional"),
                "obligation_keyword": it.get("obligation_keyword", "none"),
                "reason": it.get("reason", ""),
            }
        )
    return out


def _fallback_classify(
    batch: list[str], section_name: str
) -> list[dict[str, Any]]:
    category = _guess_category(section_name)
    out: list[dict[str, Any]] = []
    for stmt in batch:
        text_lower = stmt.lower()
        if re.search(r"\bshall\b", text_lower):
            classification, obligation = "REQUIREMENT", "shall"
            reason = "Contains 'shall' — binding requirement (keyword fallback)."
        elif re.search(r"\bmust\b", text_lower):
            classification, obligation = "REQUIREMENT", "must"
            reason = "Contains 'must' — binding requirement (keyword fallback)."
        elif re.search(r"\bshould\b", text_lower):
            classification, obligation = "RECOMMENDATION", "should"
            reason = "Contains 'should' — advisory (keyword fallback)."
        elif any(
            p in text_lower
            for p in (
                "supplier will",
                "supplier to ",
                "supplier needs",
                "supplier shall provide",
            )
        ):
            classification, obligation = "ASK", "will"
            reason = "Supplier-action phrasing — process expectation (keyword fallback)."
        elif re.search(r":\s*\S", stmt) and re.search(r"\d", stmt):
            classification, obligation = "REQUIREMENT", "none"
            reason = "Specification table row with numeric value (keyword fallback)."
        else:
            classification, obligation = "INFORMATIONAL", "none"
            reason = "No obligation keyword — treated as informational (keyword fallback)."
        out.append(
            {
                "classification": classification,
                "iso_category": category,
                "obligation_keyword": obligation,
                "reason": reason,
            }
        )
    return out


def _guess_category(section_name: str) -> str:
    lo = section_name.lower()
    if "safety" in lo:
        return "Safety"
    if "environment" in lo or "elv" in lo or "emi" in lo or "emc" in lo:
        return "Environmental"
    if "performance" in lo or "reliability" in lo or "quality target" in lo:
        return "Performance"
    if "interface" in lo or "communication" in lo or "pin" in lo:
        return "Interface"
    if "regulatory" in lo or "homologation" in lo or "legal" in lo:
        return "Regulatory"
    if "design" in lo or "mechanical" in lo or "material" in lo:
        return "Design Constraint"
    if "service" in lo or "warranty" in lo or "spare" in lo:
        return "Serviceability"
    if (
        "supplier" in lo
        or "delivery" in lo
        or "ppap" in lo
        or "apqp" in lo
        or "manufacturing" in lo
    ):
        return "Process"
    return "Functional"
