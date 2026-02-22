from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from src.pdf import extract_text_from_pdf
from src.schemas import PaperTagging


def step_fetch(
    row: Dict[str, Any],
    *,
    state_fetched: str,
    state_pdf_missing: str,
    update_status_fn,
    logger: logging.Logger,
) -> None:
    """Step 1: NEW -> FETCHED (Check PDF)"""
    pid = row["paper_id"]
    pdf_path_str = row["pdf_path"]
    logger.info(f"   [Step 1: Fetch] {pid}")

    final_pdf_path = None

    if pdf_path_str:
        path = Path(pdf_path_str)
        if path.exists():
            final_pdf_path = path

    if not final_pdf_path:
        lib_path = Path(f"Library/{pid}.pdf")
        if lib_path.exists():
            final_pdf_path = lib_path

    if final_pdf_path:
        update_status_fn(pid, state_fetched, {"pdf_path": str(final_pdf_path)})
        logger.info(f"      -> Verified PDF at {final_pdf_path}")
    else:
        update_status_fn(pid, state_pdf_missing)
        logger.warning(f"      -> PDF Missing for {pid}")


def step_analyze(
    row: Dict[str, Any],
    *,
    llm_provider,
    state_gated: str,
    extract_text_fn=extract_text_from_pdf,
    update_status_fn,
    logger: logging.Logger,
) -> None:
    """Step 2: Analysis (FETCHED -> GATED)"""
    pid = row["paper_id"]
    title = row["title"]
    pdf_path = row["pdf_path"]
    logger.info(f"   [Step 2: Analyze] {pid} ({title})")

    if not llm_provider or not llm_provider.is_available():
        raise RuntimeError("LLM Provider not available")

    summary = row.get("summary", "") or "Abstract not available."
    full_text = None
    if pdf_path:
        path = Path(pdf_path)
        if path.exists():
            logger.info(f"      -> Extracting text from PDF: {path.name}")
            full_text = extract_text_fn(path, max_pages=5)

    paper_obj = {
        "title": title,
        "summary": summary,
        "full_text": full_text,
    }

    logger.info("      -> Running Hybrid Tagging & Extraction...")
    tags_data = llm_provider.tag_paper(paper_obj)
    if not tags_data:
        raise ValueError("Tagging returned None")

    confidence = tags_data.get("confidence", 0.0)
    update_status_fn(
        pid,
        state_gated,
        {
            "confidence": confidence,
            "feedback_json": json.dumps(tags_data),
        },
    )
    logger.info(f"      -> Analysis Done. Confidence: {confidence}")


def step_gate(
    row: Dict[str, Any],
    *,
    gate_engine,
    status_map: Dict[Any, str],
    update_status_fn,
    logger: logging.Logger,
) -> None:
    """Step 3: Gate (GATED -> APPROVED/QUARANTINED/PENDING/FAILED)"""
    pid = row["paper_id"]
    confidence = row.get("confidence", 0.0)
    logger.info(f"   [Step 3: Gate] {pid} (Conf: {confidence})")

    parse_ok = True
    schema_ok = True
    analysis: Dict[str, Any] = {}
    feedback_json = row.get("feedback_json")
    if feedback_json:
        try:
            parsed = json.loads(feedback_json)
            if isinstance(parsed, dict):
                analysis = parsed
            else:
                parse_ok = False
        except Exception:
            parse_ok = False

    analysis.setdefault("confidence", confidence)
    analysis.setdefault("soft_tags", [])
    analysis.setdefault("hard_tags", {})

    if parse_ok:
        try:
            PaperTagging.model_validate(analysis)
        except Exception:
            schema_ok = False

    gate_result = gate_engine.evaluate(analysis, parse_ok=parse_ok, schema_ok=schema_ok)
    status = status_map[gate_result.decision]
    decision = gate_result.decision.value
    reason = ",".join([rc.value for rc in gate_result.reason_codes]) or "NONE"

    update_status_fn(
        pid,
        status,
        {
            "gate_decision": decision,
            "gate_reason": reason,
        },
    )
    logger.info(f"      -> Gate Decision: {decision} ({reason})")


def step_finalize(
    row: Dict[str, Any],
    *,
    state_indexed: str,
    update_status_fn,
    logger: logging.Logger,
) -> None:
    """Step 4: Finalize (APPROVED -> INDEXED)"""
    pid = row["paper_id"]
    logger.info(f"   [Step 4: Finalize] {pid}")

    feedback_json = row["feedback_json"]
    if feedback_json:
        try:
            json.loads(feedback_json)
            logger.info("      -> Prepared for Obsidian (Mock)")
        except Exception as exc:
            logger.warning(f"      -> Failed to parse feedback_json for Obsidian: {exc}")

    update_status_fn(pid, state_indexed)
    logger.info("      -> Status: INDEXED")
