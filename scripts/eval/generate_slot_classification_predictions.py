from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.llm_provider import get_llm_provider
from src.services.slot_classification_audit import (
    classify_slot_classification_input_richness,
    load_slot_classification_goldset_csv,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _normalize_slot(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"clinical", "mechanism", "methods"}:
        return normalized
    return None


def _normalize_current_slot(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"clinical", "mechanism", "methods", "unknown"}:
        return normalized
    return None


def _title_case_current_slot(value: str) -> str:
    return {
        "clinical": "Clinical",
        "mechanism": "Mechanism",
        "methods": "Methods",
        "unknown": "Unknown",
    }[value]


def _coerce_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_provider_payload(row: dict) -> dict[str, Any]:
    payload: dict[str, Any] = {"title": row.get("title") or ""}
    if row.get("summary"):
        payload["summary"] = row["summary"]
    if row.get("full_text"):
        payload["full_text"] = row["full_text"]
    return payload


def run_generation(
    *,
    goldset_csv_path: Path,
    out_dir: Path,
    run_id: str,
    provider: Any | None = None,
    feature_enabled: bool | None = None,
    fallback_current_slot: str | None = None,
) -> Path:
    rows = load_slot_classification_goldset_csv(goldset_csv_path)
    config = None
    if provider is None or feature_enabled is None:
        config = load_config()
    if provider is None:
        provider = get_llm_provider(config.llm, getattr(config, "entity_aliases", None))
    provider_available = bool(provider and provider.is_available())
    if feature_enabled is None:
        feature_enabled = bool(getattr(getattr(config.llm, "features", None), "slot_classification", None).enabled)

    fallback_current_slot = _normalize_current_slot(fallback_current_slot)
    run_root = out_dir / run_id
    prediction_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []

    for row in rows:
        current_slot = _normalize_current_slot(row.get("current_slot")) or fallback_current_slot
        input_richness = classify_slot_classification_input_richness(
            title=row.get("title"),
            summary=row.get("summary"),
            full_text=row.get("full_text"),
        )
        record: dict[str, Any] = {
            "paper_id": row.get("paper_id"),
            "doi": row.get("doi"),
            "title": row.get("title"),
            "gold_slot": row.get("gold_slot"),
            "current_slot": current_slot,
            "input_richness": input_richness,
            "predicted_slot": None,
            "prediction_status": None,
            "prediction_source": "none",
            "first_pass_predicted_slot": None,
            "final_source": None,
            "adjudication_triggered": None,
            "adjudication_reason": None,
            "confidence": None,
            "error": None,
        }
        if not feature_enabled:
            record["prediction_status"] = "feature_disabled"
            detail_rows.append(record)
            continue
        if not provider_available:
            record["prediction_status"] = "provider_unavailable"
            detail_rows.append(record)
            continue
        if not current_slot:
            record["prediction_status"] = "missing_current_slot"
            detail_rows.append(record)
            continue
        try:
            predicted = provider.classify_slot(_build_provider_payload(row), _title_case_current_slot(current_slot))
            metrics = {}
            get_metrics = getattr(provider, "get_slot_classification_metrics", None)
            if callable(get_metrics):
                metrics_candidate = get_metrics()
                if isinstance(metrics_candidate, dict):
                    metrics = metrics_candidate
            normalized_predicted = _normalize_slot(predicted)
            if normalized_predicted is None:
                record["prediction_status"] = "invalid_prediction"
            else:
                record["predicted_slot"] = normalized_predicted
                record["prediction_status"] = "ok"
                record["prediction_source"] = "live_provider"
            record["first_pass_predicted_slot"] = _normalize_slot(metrics.get("first_pass_predicted_slot"))
            final_source = str(metrics.get("final_source") or "").strip() or None
            record["final_source"] = final_source
            adjudication_triggered = metrics.get("adjudication_triggered")
            if isinstance(adjudication_triggered, bool):
                record["adjudication_triggered"] = adjudication_triggered
            record["adjudication_reason"] = str(metrics.get("adjudication_reason") or "").strip() or None
            record["confidence"] = _coerce_optional_float(metrics.get("first_pass_confidence"))
        except Exception as exc:
            record["prediction_status"] = "provider_exception"
            record["error"] = str(exc)
        detail_rows.append(record)
        if record["prediction_status"] == "ok":
            prediction_rows.append(
                {
                    "paper_id": record["paper_id"],
                    "doi": record["doi"],
                    "title": record["title"],
                    "current_slot": record["current_slot"],
                    "input_richness": record["input_richness"],
                    "predicted_slot": record["predicted_slot"],
                    "prediction_status": record["prediction_status"],
                    "prediction_source": record["prediction_source"],
                    "first_pass_predicted_slot": record["first_pass_predicted_slot"],
                    "final_source": record["final_source"],
                    "adjudication_triggered": record["adjudication_triggered"],
                    "adjudication_reason": record["adjudication_reason"],
                    "confidence": record["confidence"],
                }
            )

    status_counts = Counter(str(row.get("prediction_status") or "") for row in detail_rows)
    input_richness_counts = Counter(str(row.get("input_richness") or "") for row in detail_rows)
    summary = {
        "schema_version": "slot_classification_prediction_generation.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "goldset_csv_path": str(goldset_csv_path),
            "fallback_current_slot": fallback_current_slot,
        },
        "provider_available": provider_available,
        "runtime_feature_enabled": bool(feature_enabled),
        "document_count": len(rows),
        "prediction_written_count": len(prediction_rows),
        "status_counts": {key: int(value) for key, value in sorted(status_counts.items())},
        "input_richness_counts": {key: int(value) for key, value in sorted(input_richness_counts.items())},
        "predictions_jsonl_path": str(run_root / "predictions.jsonl"),
    }
    details = {
        "schema_version": "slot_classification_prediction_generation_details.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "documents": detail_rows,
    }
    _write_jsonl(run_root / "predictions.jsonl", prediction_rows)
    _write_json(run_root / "summary.json", summary)
    _write_json(run_root / "details.json", details)
    return run_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate slot-classification prediction JSONL from a goldset CSV using the current provider path."
    )
    parser.add_argument(
        "--goldset-csv",
        default=str(ROOT / "tests" / "gold_set" / "gold_standard_template.csv"),
        help="Goldset CSV path with title, gold_slot, and optional summary/full_text/current_slot columns.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "slot_classification_predictions"),
        help="Output directory for generated predictions and summary artifacts.",
    )
    parser.add_argument(
        "--fallback-current-slot",
        default=None,
        choices=["clinical", "mechanism", "methods", "unknown"],
        help="Optional fallback slot when the goldset row omits current_slot.",
    )
    parser.add_argument("--run-id", required=True, help="Generation run identifier.")
    args = parser.parse_args()

    run_root = run_generation(
        goldset_csv_path=Path(args.goldset_csv).expanduser(),
        out_dir=Path(args.out_dir).expanduser(),
        run_id=args.run_id,
        fallback_current_slot=args.fallback_current_slot,
    )
    payload = {
        "run_root": str(run_root),
        "predictions_jsonl_path": str(run_root / "predictions.jsonl"),
        "summary_path": str(run_root / "summary.json"),
        "details_path": str(run_root / "details.json"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
