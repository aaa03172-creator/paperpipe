#!/usr/bin/env python3
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

from scripts.eval.materialize_specialty_runtime_shadow import _diagnostic_reason_codes
from src.schemas.core import Intervention, SpecialtyTrialExtraction


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def _normalize_payload(
    *,
    expected_paper_id: str,
    raw_payload: dict[str, Any],
    gold_payload: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    payload = json.loads(json.dumps(raw_payload))
    actions: list[str] = []

    if not str(payload.get("paper_id") or "").strip():
        payload["paper_id"] = expected_paper_id
        actions.append("paper_id_from_expected")

    citation = payload.get("citation")
    if not isinstance(citation, dict):
        payload["citation"] = dict(gold_payload.get("citation") or {})
        actions.append("citation_from_gold_metadata")

    comparator = payload.get("comparator")
    if isinstance(comparator, str):
        payload["comparator"] = {"description": comparator}
        actions.append("comparator_string_to_object")
    elif comparator is None:
        payload["comparator"] = {}
        actions.append("comparator_null_to_object")

    for field_name in ("ketone_confirmation", "risk_of_bias_hints", "eligibility_flags"):
        if payload.get(field_name) is None:
            payload[field_name] = {}
            actions.append(f"{field_name}_null_to_object")

    intervention = payload.get("intervention")
    if intervention is None:
        payload["intervention"] = {}
        intervention = payload["intervention"]
        actions.append("intervention_null_to_object")
    if isinstance(intervention, dict):
        category = str(intervention.get("category") or "").strip()
        allowed_categories = {
            item if isinstance(item, str) else item for item in Intervention.model_fields["category"].annotation.__args__
        }
        if category and category not in allowed_categories:
            intervention["category"] = "other"
            actions.append("intervention_category_to_other")
        elif not category:
            intervention["category"] = "unknown"
            actions.append("intervention_category_to_unknown")

    return payload, actions


def _normalize_record(*, record: dict[str, Any], run_root: Path) -> dict[str, Any]:
    result = {
        "paper_id": str(record.get("paper_id") or "").strip(),
        "status": None,
        "raw_response_path": record.get("raw_response_path"),
        "normalized_prediction_path": None,
        "prediction_paper_id": None,
        "normalization_actions": [],
        "compare_ready": False,
        "validation_error": None,
    }

    if str(record.get("status") or "") != "prediction_schema_invalid":
        result["status"] = "skipped_non_schema_invalid"
        return result

    raw_response_path = Path(str(record.get("raw_response_path") or "")).expanduser()
    if not raw_response_path.exists():
        result["status"] = "missing_raw_response"
        return result

    try:
        raw_payload = _load_json_object(raw_response_path)
    except Exception as exc:
        result["status"] = "invalid_raw_response"
        result["validation_error"] = f"{type(exc).__name__}: {exc}"
        return result

    gold_path = Path(str(record.get("gold_path") or "")).expanduser()
    gold_payload = _load_json_object(gold_path)

    normalized_payload, actions = _normalize_payload(
        expected_paper_id=result["paper_id"],
        raw_payload=raw_payload,
        gold_payload=gold_payload,
    )
    result["normalization_actions"] = actions

    try:
        prediction = SpecialtyTrialExtraction.model_validate(normalized_payload)
    except Exception as exc:
        result["status"] = "normalized_prediction_schema_invalid"
        result["validation_error"] = f"{type(exc).__name__}: {exc}"
        result["validation_reason_codes"] = _diagnostic_reason_codes(
            status="schema_invalid",
            error_text=result["validation_error"],
        )
        return result

    prediction_paper_id = str(prediction.paper_id or "").strip()
    result["prediction_paper_id"] = prediction_paper_id or None
    if prediction_paper_id != result["paper_id"]:
        result["status"] = "pairing_mismatch"
        result["validation_error"] = f"PAIRING_MISMATCH expected={result['paper_id']} prediction={prediction_paper_id}"
        return result

    prediction_path = run_root / "normalized_predictions" / f"{result['paper_id'].replace(':', '_')}.json"
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    prediction_path.write_text(prediction.model_dump_json(indent=2) + "\n", encoding="utf-8")
    result["status"] = "normalized_prediction_written"
    result["normalized_prediction_path"] = str(prediction_path)
    result["compare_ready"] = True
    return result


def run_specialty_shadow_normalizer(
    *,
    materialized_details_path: Path,
    out_dir: Path,
    run_id: str,
) -> Path:
    details = _load_json_object(materialized_details_path)
    documents = details.get("documents")
    if not isinstance(documents, list):
        raise RuntimeError(f"materialized_details_missing_documents={materialized_details_path}")

    run_root = out_dir / run_id
    results = [_normalize_record(record=doc, run_root=run_root) for doc in documents if isinstance(doc, dict)]
    results.sort(key=lambda item: str(item.get("paper_id") or ""))

    compare_docs = [
        {
            "paper_id": result["paper_id"],
            "gold_path": next(
                str(doc.get("gold_path"))
                for doc in documents
                if isinstance(doc, dict) and str(doc.get("paper_id") or "") == str(result["paper_id"] or "")
            ),
            "prediction_path": result["normalized_prediction_path"],
        }
        for result in results
        if result.get("compare_ready") and result.get("normalized_prediction_path")
    ]
    generated_manifest = {
        "schema_version": "extraction_regression_manifest.v1",
        "generated_at": _utc_now_iso(),
        "source_materialized_details": str(materialized_details_path),
        "notes": [
            "Developer-only specialty shadow normalization audit.",
            "This lane checks whether raw schema-invalid specialty outputs can be normalized without changing runtime behavior.",
        ],
        "documents": compare_docs,
    }
    _write_json(run_root / "generated_manifest.json", generated_manifest)

    status_counts = Counter(str(result.get("status") or "") for result in results)
    validation_reason_counts = Counter(
        code
        for result in results
        if str(result.get("status") or "") == "normalized_prediction_schema_invalid"
        for code in (result.get("validation_reason_codes") or [])
    )
    summary = {
        "schema_version": "specialty_runtime_shadow_normalization.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "materialized_details": str(materialized_details_path),
        },
        "document_count": len(results),
        "normalized_prediction_written_count": int(status_counts.get("normalized_prediction_written", 0)),
        "compare_ready_count": len(compare_docs),
        "status_counts": {
            "normalized_prediction_written": int(status_counts.get("normalized_prediction_written", 0)),
            "normalized_prediction_schema_invalid": int(status_counts.get("normalized_prediction_schema_invalid", 0)),
            "pairing_mismatch": int(status_counts.get("pairing_mismatch", 0)),
            "missing_raw_response": int(status_counts.get("missing_raw_response", 0)),
            "invalid_raw_response": int(status_counts.get("invalid_raw_response", 0)),
            "skipped_non_schema_invalid": int(status_counts.get("skipped_non_schema_invalid", 0)),
        },
        "validation_reason_counts": {code: int(count) for code, count in sorted(validation_reason_counts.items())},
        "generated_manifest_path": str(run_root / "generated_manifest.json"),
        "generated_manifest_document_count": len(compare_docs),
    }
    detail_payload = {
        "schema_version": "specialty_runtime_shadow_normalization_details.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "documents": results,
    }
    _write_json(run_root / "summary.json", summary)
    _write_json(run_root / "details.json", detail_payload)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize raw specialty shadow outputs in a developer-only audit lane."
    )
    parser.add_argument("--materialized-details", required=True, help="Materialized specialty shadow details JSON.")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "extraction_runtime_shadow_normalized"),
        help="Output directory for normalized specialty shadow artifacts.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_specialty_shadow_normalizer(
        materialized_details_path=Path(args.materialized_details).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
