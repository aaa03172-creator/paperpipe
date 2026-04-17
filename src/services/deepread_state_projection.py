from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from src.contracts.output_bridge import (
    bind_claim_cards_to_run,
    claim_cards_from_claimset_payload,
    normalize_claimset_payload,
)
from src.schemas import BiomedicalClinicalExtraction
from src.schemas.skills import SkillRunRecord, StructuredPaperState
from src.skills.storage import (
    atomic_write_text,
    compose_note,
    load_structured_state,
    safe_read_text,
    split_frontmatter,
    structured_state_path,
    update_frontmatter_pp,
    write_structured_state,
)


DEEP_READ_PROMOTION_SOURCE = "deep_read_promotion"
DEEP_READ_PROMOTION_VERSION = "v1"


def build_deepread_structured_state_candidate(
    *,
    paper_slug: str,
    artifact_dir: Path,
) -> StructuredPaperState | None:
    run_meta = _load_json_dict(artifact_dir / "run_meta.json")
    if run_meta is None:
        return None

    run_status = _normalize_run_status(run_meta.get("status"))
    if run_status != "succeeded":
        return None

    claimset_payload = normalize_claimset_payload(_load_json_dict(artifact_dir / "claimset.resolved.json"))
    if claimset_payload is None:
        return None

    bootstrap_meta = _load_json_dict(artifact_dir / "bootstrap_meta.json") or {}
    run_id = str(run_meta.get("run_id") or artifact_dir.name).strip() or artifact_dir.name
    run_ts = _select_run_timestamp(run_meta)
    clinical_extraction = _load_biomedical_clinical_extraction(artifact_dir)
    clinical_artifact_path = artifact_dir / "clinical_extraction.json"
    clinical_status = str(
        run_meta.get("clinical_extraction_status")
        or bootstrap_meta.get("clinical_extraction_status")
        or ""
    ).strip() or None
    clinical_note_type = str(bootstrap_meta.get("clinical_extraction_note_type") or "").strip() or None

    claim_cards = bind_claim_cards_to_run(claim_cards_from_claimset_payload(claimset_payload), run_id)
    claim_count = len(claim_cards)
    evidence_count = sum(len(card.evidence) for card in claim_cards)
    parser_backend = str(run_meta.get("parser_backend") or bootstrap_meta.get("parser_backend") or "").strip() or None
    claimset_readiness = str(bootstrap_meta.get("claimset_readiness") or "").strip() or None
    quality_gate = _load_json_dict(artifact_dir / "quality_gate.json") or {}
    quality_gate_status = str(quality_gate.get("overall_status") or "").strip() or None
    section_navigation_signal_status, section_navigation_signal_detail = _quality_gate_check_status_and_detail(
        quality_gate,
        "section_navigation_signal",
    )
    clinical_summary = _build_clinical_extraction_summary(clinical_extraction)

    summary_parts = [f"Projected Deep Read artifact bundle into canonical state ({claim_count} claims"]
    if parser_backend:
        summary_parts.append(f", parser={parser_backend}")
    if claimset_readiness:
        summary_parts.append(f", readiness={claimset_readiness}")
    if quality_gate_status:
        summary_parts.append(f", gate={quality_gate_status}")
    if clinical_status == "completed" and clinical_summary["condition"]:
        summary_parts.append(f", clinical={clinical_summary['condition']}")
    summary_parts.append(").")
    run_record = SkillRunRecord(
        id=run_id,
        action="deep_read",
        ts=run_ts,
        status=run_status,
        summary="".join(summary_parts),
        artifacts={
            "artifact_dir": str(artifact_dir),
            "run_meta_path": str(artifact_dir / "run_meta.json"),
            "bootstrap_meta_path": str(artifact_dir / "bootstrap_meta.json"),
            "claimset_source": "claimset.resolved.json",
            "claimset_path": str(artifact_dir / "claimset.resolved.json"),
            "stats_report_path": str(artifact_dir / "stats_report.json"),
            "acceptance_contract_path": str(artifact_dir / "acceptance_contract.json"),
            "quality_gate_path": str(artifact_dir / "quality_gate.json"),
            "clinical_extraction_path": str(clinical_artifact_path) if clinical_artifact_path.exists() else None,
        },
        data={
            "claim_count": claim_count,
            "evidence_count": evidence_count,
            "claimset_readiness": claimset_readiness,
            "claimset_ready": bootstrap_meta.get("claimset_ready"),
            "verification_status": run_meta.get("verification_status"),
            "quality_gate_status": quality_gate.get("overall_status"),
            "review_ready": quality_gate.get("review_ready"),
            "current_promotion_candidate": quality_gate.get("current_promotion_candidate"),
            "section_navigation_signal_status": section_navigation_signal_status,
            "section_navigation_signal_detail": section_navigation_signal_detail,
            "clinical_extraction_status": clinical_status,
            "clinical_extraction_note_type": clinical_note_type,
            "clinical_condition": clinical_summary["condition"],
            "clinical_intervention": clinical_summary["intervention"],
            "clinical_followup_tag": clinical_summary["followup_tag"],
        },
    )

    outcomes = _unique_texts(
        outcome
        for card in claim_cards
        for outcome in card.outcomes
    )
    state_signals = _compact_signals(
        {
            "state_source": DEEP_READ_PROMOTION_SOURCE,
            "state_source_run_id": run_id,
            "state_source_version": DEEP_READ_PROMOTION_VERSION,
            "parser_backend": parser_backend,
            "claimset_readiness": bootstrap_meta.get("claimset_readiness"),
            "claimset_readiness_badge": bootstrap_meta.get("claimset_readiness_badge"),
            "claimset_ops_action": bootstrap_meta.get("claimset_ops_action"),
            "claimset_ops_alert": bootstrap_meta.get("claimset_ops_alert"),
            "claimset_ops_note": bootstrap_meta.get("claimset_ops_note"),
            "claimset_ready": bootstrap_meta.get("claimset_ready"),
            "stats_report_written": bootstrap_meta.get("stats_report_written"),
            "artifact_document_written": bootstrap_meta.get("artifact_document_written"),
            "artifact_index_written": bootstrap_meta.get("artifact_index_written"),
            "artifact_claimset_written": bootstrap_meta.get("artifact_claimset_written"),
            "artifact_stats_written": bootstrap_meta.get("artifact_stats_written"),
            "artifact_acceptance_contract_written": bootstrap_meta.get("artifact_acceptance_contract_written"),
            "artifact_quality_gate_written": bootstrap_meta.get("artifact_quality_gate_written"),
            "artifact_clinical_extraction_written": bootstrap_meta.get("artifact_clinical_extraction_written"),
            "clinical_extraction_status": clinical_status,
            "clinical_extraction_note_type": clinical_note_type,
            "clinical_condition": clinical_summary["condition"],
            "clinical_intervention": clinical_summary["intervention"],
            "clinical_followup_tag": clinical_summary["followup_tag"],
            "verification_status": run_meta.get("verification_status"),
            "anchor_verify_summary": bootstrap_meta.get("anchor_verify_summary"),
            "quality_gate_status": quality_gate.get("overall_status"),
            "quality_gate_review_ready": quality_gate.get("review_ready"),
            "quality_gate_current_promotion_candidate": quality_gate.get("current_promotion_candidate"),
            "quality_gate_section_navigation_signal": section_navigation_signal_status,
            "claim_count": claim_count,
            "evidence_count": evidence_count,
        }
    )

    return StructuredPaperState(
        paper_slug=paper_slug,
        updated_at=run_ts,
        runs=[run_record],
        signals=state_signals,
        claimset=claim_cards,
        entities=[],
        mesh=[],
        outcomes=outcomes,
    )


def promote_deepread_structured_state_for_note(
    *,
    vault_path: Path,
    note_path: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    slug = note_path.stem
    content = safe_read_text(note_path)
    frontmatter, body = split_frontmatter(content)
    existing_state = load_structured_state(vault_path, slug, frontmatter)
    if existing_state is not None and existing_state.signals.get("state_source") != DEEP_READ_PROMOTION_SOURCE:
        return {
            "status": "skipped",
            "reason": "canonical_state_owned_elsewhere",
            "slug": slug,
        }

    candidate = build_deepread_structured_state_candidate(
        paper_slug=slug,
        artifact_dir=artifact_dir,
    )
    if candidate is None:
        return {
            "status": "skipped",
            "reason": "artifact_bundle_not_eligible",
            "slug": slug,
        }

    output_path = structured_state_path(vault_path, slug)
    write_structured_state(output_path, candidate)
    updated_frontmatter = update_frontmatter_pp(frontmatter, candidate, candidate.runs[0])
    atomic_write_text(note_path, compose_note(updated_frontmatter, body))
    return {
        "status": "created" if existing_state is None else "refreshed",
        "reason": None,
        "slug": slug,
        "structured_path": str(output_path),
        "run_id": candidate.runs[0].id,
    }


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _load_biomedical_clinical_extraction(artifact_dir: Path) -> BiomedicalClinicalExtraction | None:
    payload = _load_json_dict(artifact_dir / "clinical_extraction.json")
    if payload is None:
        return None
    try:
        return BiomedicalClinicalExtraction.model_validate(payload)
    except Exception:
        return None


def _quality_gate_check_status_and_detail(
    quality_gate: dict[str, Any],
    name: str,
) -> tuple[str | None, str | None]:
    checks = quality_gate.get("checks")
    if not isinstance(checks, list):
        return None, None
    for item in checks:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "").strip() != name:
            continue
        status = str(item.get("status") or "").strip() or None
        detail = str(item.get("detail") or "").strip() or None
        return status, detail
    return None, None


def _build_clinical_extraction_summary(
    extraction: BiomedicalClinicalExtraction | None,
) -> dict[str, str | None]:
    if extraction is None:
        return {
            "condition": None,
            "intervention": None,
            "followup_tag": None,
        }

    intervention_parts: list[str] = []
    if extraction.intervention.name:
        intervention_parts.append(extraction.intervention.name)
    if extraction.intervention.category != "unknown":
        intervention_parts.append(extraction.intervention.category.replace("_", " "))
    intervention = ", ".join(intervention_parts) or None

    followup_tag = extraction.eligibility_flags.followup_tag
    if followup_tag == "unknown":
        followup_tag = None

    return {
        "condition": extraction.population.condition or None,
        "intervention": intervention,
        "followup_tag": followup_tag,
    }


def _normalize_run_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text == "succeeded":
        return "succeeded"
    if text in {"failed", "cancelled"}:
        return "failed"
    return "blocked"


def _select_run_timestamp(run_meta: dict[str, Any]) -> str:
    for key in ("finished_at", "updated_at", "started_at"):
        text = str(run_meta.get(key) or "").strip()
        if text:
            return text
    return datetime.now(timezone.utc).isoformat()


def _unique_texts(values: Any) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _compact_signals(payload: dict[str, Any]) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        compacted[key] = value
    return compacted
