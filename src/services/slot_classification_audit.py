from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.schemas.slot_classification_audit import (
    SlotClassificationGoldsetAuditDetails,
    SlotClassificationGoldsetAuditDocument,
    SlotClassificationGoldsetAuditInput,
    SlotClassificationGoldsetAuditMetrics,
    SlotClassificationGoldsetAuditSummary,
)
from src.skills.storage import atomic_write_text

_VALID_SLOTS = ("clinical", "mechanism", "methods")
_VALID_CURRENT_SLOTS = _VALID_SLOTS + ("unknown",)


def load_slot_classification_goldset_csv(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, raw_row in enumerate(reader, start=1):
            row = {str(key or "").strip(): str(value or "").strip() for key, value in raw_row.items()}
            paper_id = row.get("paper_id") or row.get("doi") or row.get("title") or f"row-{index}"
            rows.append(
                {
                    "paper_id": paper_id,
                    "doi": row.get("doi") or None,
                    "title": row.get("title") or None,
                    "summary": row.get("summary") or None,
                    "full_text": row.get("full_text") or None,
                    "gold_slot_rationale": row.get("gold_slot_rationale") or None,
                    "input_richness": classify_slot_classification_input_richness(
                        title=row.get("title"),
                        summary=row.get("summary"),
                        full_text=row.get("full_text"),
                    ),
                    "current_slot": _normalize_current_slot(row.get("current_slot")),
                    "gold_slot": _normalize_slot(row.get("gold_slot")),
                    "predicted_slot": _normalize_slot(row.get("predicted_slot")),
                    "prediction_status": row.get("prediction_status") or None,
                    "prediction_source": row.get("prediction_source") or None,
                    "first_pass_predicted_slot": _normalize_slot(row.get("first_pass_predicted_slot")),
                    "final_source": row.get("final_source") or None,
                    "adjudication_triggered": _coerce_optional_bool(row.get("adjudication_triggered")),
                    "adjudication_reason": row.get("adjudication_reason") or None,
                    "confidence": _coerce_optional_float(row.get("confidence")),
                }
            )
    return rows


def load_slot_classification_predictions_jsonl(jsonl_path: Path | None) -> dict[str, dict]:
    if jsonl_path is None or not jsonl_path.exists():
        return {}

    predictions_by_key: dict[str, dict] = {}
    for raw_line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        normalized = {
            "paper_id": str(payload.get("paper_id") or "").strip() or None,
            "doi": str(payload.get("doi") or "").strip() or None,
            "title": str(payload.get("title") or "").strip() or None,
            "current_slot": _normalize_current_slot(payload.get("current_slot")),
            "predicted_slot": _normalize_slot(payload.get("predicted_slot")),
            "prediction_status": str(payload.get("prediction_status") or "").strip() or None,
            "prediction_source": str(payload.get("prediction_source") or "").strip() or None,
            "first_pass_predicted_slot": _normalize_slot(payload.get("first_pass_predicted_slot")),
            "final_source": str(payload.get("final_source") or "").strip() or None,
            "adjudication_triggered": _coerce_optional_bool(payload.get("adjudication_triggered")),
            "adjudication_reason": str(payload.get("adjudication_reason") or "").strip() or None,
            "confidence": _coerce_optional_float(payload.get("confidence")),
        }
        for key in _match_keys(normalized):
            predictions_by_key[key] = normalized
    return predictions_by_key


def build_slot_classification_goldset_audit(
    *,
    goldset_rows: list[dict],
    predictions_by_key: dict[str, dict],
    run_id: str,
    goldset_csv_path: Path,
    predictions_jsonl_path: Path | None = None,
) -> tuple[SlotClassificationGoldsetAuditSummary, SlotClassificationGoldsetAuditDetails]:
    documents: list[SlotClassificationGoldsetAuditDocument] = []
    rows_with_gold_slot = 0

    for row in goldset_rows:
        gold_slot = _normalize_slot(row.get("gold_slot"))
        if gold_slot is None:
            continue
        rows_with_gold_slot += 1
        prediction = _find_prediction(row, predictions_by_key)
        predicted_slot = _normalize_slot((prediction or {}).get("predicted_slot") or row.get("predicted_slot"))
        prediction_status = (
            str((prediction or {}).get("prediction_status") or row.get("prediction_status") or "").strip() or None
        )
        prediction_source = (
            str((prediction or {}).get("prediction_source") or row.get("prediction_source") or "").strip() or None
        )
        matched = predicted_slot == gold_slot if predicted_slot is not None else None
        documents.append(
            SlotClassificationGoldsetAuditDocument(
                paper_id=str(row.get("paper_id") or "").strip(),
                doi=_clean_optional_text(row.get("doi")),
                title=_clean_optional_text(row.get("title")),
                current_slot=_normalize_current_slot((prediction or {}).get("current_slot") or row.get("current_slot")),
                gold_slot=gold_slot,
                gold_slot_rationale=_clean_optional_text(row.get("gold_slot_rationale")),
                input_richness=str(
                    (prediction or {}).get("input_richness")
                    or row.get("input_richness")
                    or classify_slot_classification_input_richness(
                        title=row.get("title"),
                        summary=row.get("summary"),
                        full_text=row.get("full_text"),
                    )
                ).strip()
                or "title_only",
                predicted_slot=predicted_slot,
                matched=matched,
                prediction_status=prediction_status or ("ok" if predicted_slot is not None else "missing"),
                prediction_source=prediction_source or ("goldset_row" if predicted_slot is not None else "none"),
                summary_present=bool(str(row.get("summary") or "").strip()),
                full_text_present=bool(str(row.get("full_text") or "").strip()),
                first_pass_predicted_slot=_normalize_slot(
                    (prediction or {}).get("first_pass_predicted_slot") or row.get("first_pass_predicted_slot")
                ),
                final_source=_clean_optional_text((prediction or {}).get("final_source") or row.get("final_source")),
                adjudication_triggered=_coerce_optional_bool(
                    (prediction or {}).get("adjudication_triggered")
                    if prediction
                    else row.get("adjudication_triggered")
                ),
                adjudication_reason=_clean_optional_text(
                    (prediction or {}).get("adjudication_reason") or row.get("adjudication_reason")
                ),
                confidence=_coerce_optional_float((prediction or {}).get("confidence") or row.get("confidence")),
            )
        )

    metrics = _build_metrics(documents)
    generated_at = datetime.now(timezone.utc)
    summary = SlotClassificationGoldsetAuditSummary(
        generated_at=generated_at,
        run_id=run_id,
        inputs=SlotClassificationGoldsetAuditInput(
            goldset_csv_path=str(goldset_csv_path),
            predictions_jsonl_path=str(predictions_jsonl_path) if predictions_jsonl_path is not None else None,
            row_count=len(goldset_rows),
            rows_with_gold_slot=rows_with_gold_slot,
            rows_with_predictions=sum(1 for doc in documents if doc.predicted_slot is not None),
        ),
        metrics=metrics,
        documents_with_mismatch=[doc.paper_id for doc in documents if doc.matched is False],
        documents_missing_prediction=[doc.paper_id for doc in documents if doc.predicted_slot is None],
    )
    details = SlotClassificationGoldsetAuditDetails(
        generated_at=generated_at,
        run_id=run_id,
        documents=documents,
    )
    return summary, details


def write_slot_classification_goldset_audit(
    *,
    summary: SlotClassificationGoldsetAuditSummary,
    details: SlotClassificationGoldsetAuditDetails,
    out_dir: Path,
) -> Path:
    run_root = out_dir / summary.run_id
    atomic_write_text(run_root / "summary.json", summary.model_dump_json(indent=2))
    atomic_write_text(run_root / "details.json", details.model_dump_json(indent=2))
    atomic_write_text(
        run_root / "audit.md",
        render_slot_classification_goldset_markdown(summary=summary, details=details),
    )
    return run_root


def render_slot_classification_goldset_markdown(
    *,
    summary: SlotClassificationGoldsetAuditSummary,
    details: SlotClassificationGoldsetAuditDetails,
) -> str:
    metrics = summary.metrics
    lines = [
        f"# Slot Classification Goldset Audit: {summary.run_id}",
        "",
        f"- Generated At: {summary.generated_at.isoformat()}",
        f"- Goldset Rows: {summary.inputs.rows_with_gold_slot}",
        f"- Evaluated Rows: {metrics.evaluated_count}",
        f"- Matched Rows: {metrics.matched_count}",
        f"- Accuracy: {metrics.accuracy:.4f}",
        f"- Prediction Coverage Rate: {metrics.prediction_coverage_rate:.4f}",
        "",
        "## Metrics",
        f"- Gold Slot Counts: {dict(metrics.gold_slot_counts)}",
        f"- Predicted Slot Counts: {dict(metrics.predicted_slot_counts)}",
        f"- Confusion Counts: {dict(metrics.confusion_counts)}",
        f"- Per-Gold Accuracy: {dict(metrics.per_gold_slot_accuracy)}",
        f"- Per-Gold Coverage: {dict(metrics.per_gold_slot_coverage)}",
        f"- Prediction Status Counts: {dict(metrics.prediction_status_counts)}",
        f"- Prediction Source Counts: {dict(metrics.prediction_source_counts)}",
        f"- Input Richness Counts: {dict(metrics.input_richness_counts)}",
        "",
        "## Examples",
    ]
    mismatch_docs = [doc for doc in details.documents if doc.matched is False][:5]
    missing_docs = [doc for doc in details.documents if doc.predicted_slot is None][:5]
    if not mismatch_docs and not missing_docs:
        lines.append("- No mismatches or missing predictions recorded.")
    for doc in mismatch_docs:
        line = (
            f"- mismatch {doc.paper_id}: gold={doc.gold_slot}, predicted={doc.predicted_slot}, "
            f"source={doc.prediction_source}, status={doc.prediction_status}"
        )
        if doc.gold_slot_rationale:
            line += f", gold_rationale={doc.gold_slot_rationale}"
        lines.append(line)
    for doc in missing_docs:
        line = (
            f"- missing {doc.paper_id}: gold={doc.gold_slot}, source={doc.prediction_source}, "
            f"status={doc.prediction_status}"
        )
        if doc.gold_slot_rationale:
            line += f", gold_rationale={doc.gold_slot_rationale}"
        lines.append(line)
    rationale_docs = [doc for doc in details.documents if doc.gold_slot_rationale][:10]
    if rationale_docs:
        lines.extend(
            [
                "",
                "## Gold Label Rationales",
            ]
        )
        for doc in rationale_docs:
            lines.append(f"- {doc.paper_id} ({doc.gold_slot}): {doc.gold_slot_rationale}")
    return "\n".join(lines) + "\n"


def _build_metrics(documents: list[SlotClassificationGoldsetAuditDocument]) -> SlotClassificationGoldsetAuditMetrics:
    document_count = len(documents)
    evaluated_docs = [doc for doc in documents if doc.predicted_slot is not None]
    evaluated_count = len(evaluated_docs)
    matched_count = sum(1 for doc in evaluated_docs if doc.matched is True)
    mismatch_count = sum(1 for doc in evaluated_docs if doc.matched is False)
    missing_prediction_count = sum(1 for doc in documents if doc.predicted_slot is None)
    gold_slot_counts = Counter(doc.gold_slot for doc in documents)
    predicted_slot_counts = Counter(doc.predicted_slot for doc in evaluated_docs if doc.predicted_slot)
    confusion_counts = Counter(f"{doc.gold_slot}->{doc.predicted_slot}" for doc in evaluated_docs if doc.predicted_slot)
    prediction_status_counts = Counter(doc.prediction_status for doc in documents if doc.prediction_status)
    prediction_source_counts = Counter(doc.prediction_source for doc in documents if doc.prediction_source)
    input_richness_counts = Counter(doc.input_richness for doc in documents if doc.input_richness)

    per_gold_slot_accuracy: dict[str, float] = {}
    per_gold_slot_coverage: dict[str, float] = {}
    for slot in _VALID_SLOTS:
        slot_docs = [doc for doc in documents if doc.gold_slot == slot]
        if not slot_docs:
            continue
        slot_evaluated = [doc for doc in slot_docs if doc.predicted_slot is not None]
        slot_matched = sum(1 for doc in slot_evaluated if doc.matched is True)
        per_gold_slot_accuracy[slot] = round(slot_matched / len(slot_evaluated), 4) if slot_evaluated else 0.0
        per_gold_slot_coverage[slot] = round(len(slot_evaluated) / len(slot_docs), 4)

    accuracy = round(matched_count / evaluated_count, 4) if evaluated_count else 0.0
    prediction_coverage_rate = round(evaluated_count / document_count, 4) if document_count else 0.0
    return SlotClassificationGoldsetAuditMetrics(
        document_count=document_count,
        evaluated_count=evaluated_count,
        matched_count=matched_count,
        mismatch_count=mismatch_count,
        missing_prediction_count=missing_prediction_count,
        accuracy=accuracy,
        prediction_coverage_rate=prediction_coverage_rate,
        gold_slot_counts=dict(gold_slot_counts),
        predicted_slot_counts=dict(predicted_slot_counts),
        confusion_counts=dict(confusion_counts),
        per_gold_slot_accuracy=per_gold_slot_accuracy,
        per_gold_slot_coverage=per_gold_slot_coverage,
        prediction_status_counts=dict(prediction_status_counts),
        prediction_source_counts=dict(prediction_source_counts),
        input_richness_counts=dict(input_richness_counts),
    )


def classify_slot_classification_input_richness(
    *,
    title: object,
    summary: object,
    full_text: object,
) -> str:
    has_title = bool(str(title or "").strip())
    has_summary = bool(str(summary or "").strip())
    has_full_text = bool(str(full_text or "").strip())
    if has_title and has_summary and has_full_text:
        return "title_summary_full_text"
    if has_title and has_summary:
        return "title_summary"
    if has_title and has_full_text:
        return "title_full_text"
    if has_title:
        return "title_only"
    if has_summary and has_full_text:
        return "summary_full_text"
    if has_summary:
        return "summary_only"
    if has_full_text:
        return "full_text_only"
    return "empty"


def _find_prediction(row: dict, predictions_by_key: dict[str, dict]) -> dict | None:
    for key in _match_keys(row):
        if key in predictions_by_key:
            return predictions_by_key[key]
    return None


def _match_keys(payload: dict) -> list[str]:
    keys: list[str] = []
    paper_id = str(payload.get("paper_id") or "").strip()
    doi = str(payload.get("doi") or "").strip()
    title = _normalize_title(payload.get("title"))
    if paper_id:
        keys.append(f"paper_id:{paper_id}")
    if doi:
        keys.append(f"doi:{doi.lower()}")
    if title:
        keys.append(f"title:{title}")
    return keys


def _normalize_title(value: object) -> str | None:
    normalized = " ".join(str(value or "").strip().lower().split())
    return normalized or None


def _normalize_slot(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in _VALID_SLOTS:
        return normalized
    return None


def _normalize_current_slot(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in _VALID_CURRENT_SLOTS:
        return normalized
    return None


def _coerce_optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def _clean_optional_text(value: object) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None
