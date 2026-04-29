from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.schemas.slot_classification_rerun_drift import (
    SlotClassificationRerunDriftDetails,
    SlotClassificationRerunDriftDocument,
    SlotClassificationRerunDriftMetrics,
    SlotClassificationRerunDriftSummary,
    SlotClassificationRerunDriftSurface,
)
from src.skills.storage import atomic_write_text


def load_slot_classification_audit_run(path_or_dir: Path) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    run_root = path_or_dir.expanduser().resolve()
    if run_root.is_file():
        if run_root.name != "summary.json":
            raise ValueError(f"slot_classification_summary_expected={run_root}")
        run_root = run_root.parent
    summary_path = run_root / "summary.json"
    details_path = run_root / "details.json"
    summary = _load_json(summary_path)
    details = _load_json(details_path)
    summary_schema = str(summary.get("schema_version") or "")
    details_schema = str(details.get("schema_version") or "")
    if not summary_schema.startswith("slot_classification_goldset_audit_summary.v"):
        raise ValueError(f"unsupported_slot_classification_summary_schema={summary_path}")
    if not details_schema.startswith("slot_classification_goldset_audit_details.v"):
        raise ValueError(f"unsupported_slot_classification_details_schema={details_path}")
    return summary_path, details_path, summary, details


def build_slot_classification_rerun_drift(
    *,
    prior_summary: dict[str, Any],
    prior_summary_path: Path,
    prior_details: dict[str, Any],
    prior_details_path: Path,
    new_summary: dict[str, Any],
    new_summary_path: Path,
    new_details: dict[str, Any],
    new_details_path: Path,
    run_id: str,
) -> tuple[SlotClassificationRerunDriftSummary, SlotClassificationRerunDriftDetails]:
    prior_docs = _documents_by_id(prior_details)
    new_docs = _documents_by_id(new_details)

    all_ids = sorted(set(prior_docs) | set(new_docs))
    drift_docs: list[SlotClassificationRerunDriftDocument] = []
    documents_with_drift: list[str] = []
    documents_missing_in_prior: list[str] = []
    documents_missing_in_new: list[str] = []
    mismatch_status_changed_count = 0
    predicted_slot_changed_count = 0
    prediction_status_changed_count = 0

    for document_id in all_ids:
        prior_doc = prior_docs.get(document_id)
        new_doc = new_docs.get(document_id)
        if prior_doc is None:
            documents_missing_in_prior.append(document_id)
            continue
        if new_doc is None:
            documents_missing_in_new.append(document_id)
            continue

        changed_fields: list[str] = []
        if _clean_optional_text(prior_doc.get("predicted_slot")) != _clean_optional_text(new_doc.get("predicted_slot")):
            changed_fields.append("predicted_slot")
            predicted_slot_changed_count += 1
        if _coerce_optional_bool(prior_doc.get("matched")) != _coerce_optional_bool(new_doc.get("matched")):
            changed_fields.append("matched")
            mismatch_status_changed_count += 1
        if _clean_optional_text(prior_doc.get("prediction_status")) != _clean_optional_text(
            new_doc.get("prediction_status")
        ):
            changed_fields.append("prediction_status")
            prediction_status_changed_count += 1

        if not changed_fields:
            continue

        drift_docs.append(
            SlotClassificationRerunDriftDocument(
                paper_id=document_id,
                doi=_clean_optional_text(new_doc.get("doi") or prior_doc.get("doi")),
                title=_clean_optional_text(new_doc.get("title") or prior_doc.get("title")),
                gold_slot=str(new_doc.get("gold_slot") or prior_doc.get("gold_slot") or "").strip(),
                prior_predicted_slot=_clean_optional_text(prior_doc.get("predicted_slot")),
                new_predicted_slot=_clean_optional_text(new_doc.get("predicted_slot")),
                prior_matched=_coerce_optional_bool(prior_doc.get("matched")),
                new_matched=_coerce_optional_bool(new_doc.get("matched")),
                prior_prediction_status=_clean_optional_text(prior_doc.get("prediction_status")),
                new_prediction_status=_clean_optional_text(new_doc.get("prediction_status")),
                changed_fields=changed_fields,
            )
        )
        documents_with_drift.append(document_id)

    document_count = max(len(prior_docs), len(new_docs))
    metrics = SlotClassificationRerunDriftMetrics(
        document_count=document_count,
        drift_count=len(documents_with_drift),
        drift_rate=(len(documents_with_drift) / document_count) if document_count else 0.0,
        mismatch_status_changed_count=mismatch_status_changed_count,
        predicted_slot_changed_count=predicted_slot_changed_count,
        prediction_status_changed_count=prediction_status_changed_count,
        missing_in_prior_count=len(documents_missing_in_prior),
        missing_in_new_count=len(documents_missing_in_new),
    )
    generated_at = datetime.now(timezone.utc)
    summary = SlotClassificationRerunDriftSummary(
        generated_at=generated_at,
        run_id=run_id,
        prior=_build_surface(summary=prior_summary, summary_path=prior_summary_path, details_path=prior_details_path),
        new=_build_surface(summary=new_summary, summary_path=new_summary_path, details_path=new_details_path),
        metrics=metrics,
        documents_with_drift=documents_with_drift,
        documents_missing_in_prior=documents_missing_in_prior,
        documents_missing_in_new=documents_missing_in_new,
    )
    details = SlotClassificationRerunDriftDetails(
        generated_at=generated_at,
        run_id=run_id,
        documents=drift_docs,
    )
    return summary, details


def write_slot_classification_rerun_drift(
    *,
    summary: SlotClassificationRerunDriftSummary,
    details: SlotClassificationRerunDriftDetails,
    out_dir: Path,
) -> Path:
    run_root = out_dir / summary.run_id
    atomic_write_text(run_root / "summary.json", summary.model_dump_json(indent=2))
    atomic_write_text(run_root / "details.json", details.model_dump_json(indent=2))
    atomic_write_text(run_root / "audit.md", render_slot_classification_rerun_drift_markdown(summary=summary, details=details))
    return run_root


def render_slot_classification_rerun_drift_markdown(
    *,
    summary: SlotClassificationRerunDriftSummary,
    details: SlotClassificationRerunDriftDetails,
) -> str:
    lines = [
        f"# Slot Classification Rerun Drift: {summary.run_id}",
        "",
        f"- Generated At: {summary.generated_at.isoformat()}",
        f"- Prior Run: {summary.prior.run_id}",
        f"- New Run: {summary.new.run_id}",
        f"- Drift Count: {summary.metrics.drift_count}",
        f"- Drift Rate: {summary.metrics.drift_rate:.4f}",
        f"- Predicted Slot Changed Count: {summary.metrics.predicted_slot_changed_count}",
        f"- Mismatch Status Changed Count: {summary.metrics.mismatch_status_changed_count}",
        "",
        "## Surface Metrics",
        (
            f"- prior: accuracy={summary.prior.accuracy:.4f}, coverage={summary.prior.prediction_coverage_rate:.4f}, "
            f"mismatch_count={summary.prior.mismatch_count}"
        ),
        (
            f"- new: accuracy={summary.new.accuracy:.4f}, coverage={summary.new.prediction_coverage_rate:.4f}, "
            f"mismatch_count={summary.new.mismatch_count}"
        ),
        "",
        "## Drift Documents",
    ]
    if not details.documents:
        lines.append("- No row-level drift detected.")
    for doc in details.documents:
        lines.append(
            f"- {doc.paper_id}: gold={doc.gold_slot}, prior={doc.prior_predicted_slot}, new={doc.new_predicted_slot}, "
            f"prior_matched={doc.prior_matched}, new_matched={doc.new_matched}, changed_fields={doc.changed_fields}"
        )
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"slot_classification_json_object_expected={path}")
    return payload


def _documents_by_id(details: dict[str, Any]) -> dict[str, dict[str, Any]]:
    documents = details.get("documents")
    if not isinstance(documents, list):
        raise ValueError("slot_classification_details_documents_missing")
    rows: dict[str, dict[str, Any]] = {}
    for raw in documents:
        if not isinstance(raw, dict):
            continue
        document_id = str(raw.get("paper_id") or "").strip()
        if not document_id:
            continue
        rows[document_id] = raw
    return rows


def _build_surface(*, summary: dict[str, Any], summary_path: Path, details_path: Path) -> SlotClassificationRerunDriftSurface:
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"slot_classification_metrics_missing={summary_path}")
    return SlotClassificationRerunDriftSurface(
        summary_path=str(summary_path),
        details_path=str(details_path),
        run_id=_clean_optional_text(summary.get("run_id")),
        generated_at=_coerce_optional_datetime(summary.get("generated_at")),
        document_count=_as_int(metrics.get("document_count")),
        mismatch_count=_as_int(metrics.get("mismatch_count")),
        accuracy=_as_float(metrics.get("accuracy")),
        prediction_coverage_rate=_as_float(metrics.get("prediction_coverage_rate")),
    )


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _clean_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _coerce_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _coerce_optional_datetime(value: Any) -> datetime | None:
    text = _clean_optional_text(value)
    if text is None:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
