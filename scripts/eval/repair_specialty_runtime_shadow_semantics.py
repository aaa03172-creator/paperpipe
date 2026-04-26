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

from scripts.eval.generate_extraction_predictions import (
    _extract_intervention_name,
    _infer_duration_fields_from_text,
    _infer_outcome_name_from_text,
    _infer_sample_size_from_text,
    _normalize_text,
)
from scripts.eval.materialize_specialty_runtime_shadow import (
    _build_specialty_shadow_inputs,
    _diagnostic_reason_codes,
    _load_artifact,
    _load_json_object,
)
from scripts.eval.normalize_specialty_runtime_shadow import _normalize_payload
from src.schemas.core import SpecialtyTrialExtraction


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _source_text(*, paper_payload: dict[str, Any], methods_snippet: str) -> str:
    return _normalize_text(
        " ".join(
            str(part or "")
            for part in (
                paper_payload.get("title"),
                paper_payload.get("summary"),
                methods_snippet,
            )
        )
    ) or ""


def _apply_semantic_repairs(*, payload: dict[str, Any], source_text: str) -> tuple[dict[str, Any], list[str]]:
    repaired = json.loads(json.dumps(payload))
    actions: list[str] = []

    population = repaired.get("population") if isinstance(repaired.get("population"), dict) else {}
    if int(population.get("n_total") or 0) <= 0:
        inferred_sample_size = _infer_sample_size_from_text(source_text)
        if inferred_sample_size > 0:
            population["n_total"] = inferred_sample_size
            actions.append("population_n_total_from_source")
    repaired["population"] = population

    intervention = repaired.get("intervention") if isinstance(repaired.get("intervention"), dict) else {}
    inferred_product_name = _extract_intervention_name(
        raw_type=intervention.get("type") or intervention.get("category"),
        raw_product_name=intervention.get("product_name") or intervention.get("name"),
    )
    if inferred_product_name and intervention.get("product_name") != inferred_product_name:
        intervention["product_name"] = inferred_product_name
        actions.append("intervention_product_name_from_source")
    if (
        str(intervention.get("category") or "").strip() == "other"
        and _normalize_text(intervention.get("product_name"))
    ):
        intervention["category"] = "unknown"
        actions.append("intervention_category_to_unknown_for_named_product")

    study_design = repaired.get("study_design") if isinstance(repaired.get("study_design"), dict) else {}
    existing_duration = int(intervention.get("duration_weeks") or 0) or int(study_design.get("duration_weeks") or 0)
    inferred_duration, _ = _infer_duration_fields_from_text(source_text)
    if existing_duration <= 0 and inferred_duration > 0:
        study_design["duration_weeks"] = inferred_duration
        intervention["duration_weeks"] = inferred_duration
        actions.append("duration_weeks_from_source")
    repaired["study_design"] = study_design
    repaired["intervention"] = intervention

    outcomes = repaired.get("outcomes") if isinstance(repaired.get("outcomes"), dict) else {}
    cognition = outcomes.get("cognition") if isinstance(outcomes.get("cognition"), list) else []
    first_outcome = cognition[0] if cognition and isinstance(cognition[0], dict) else None
    inferred_outcome_name = _infer_outcome_name_from_text(source_text)
    if not first_outcome and inferred_outcome_name:
        cognition = [{"name": inferred_outcome_name}]
        actions.append("outcome_name_from_source")
        first_outcome = cognition[0]
    elif first_outcome and not str(first_outcome.get("name") or "").strip() and inferred_outcome_name:
        first_outcome["name"] = inferred_outcome_name
        actions.append("outcome_name_from_source")
    if first_outcome and str(first_outcome.get("effect_direction") or "").strip() in {"", "unknown"}:
        if "no significant treatment differences" in source_text:
            first_outcome["effect_direction"] = "no_change"
            actions.append("outcome_effect_no_change_from_source")
    outcomes["cognition"] = cognition
    repaired["outcomes"] = outcomes
    return repaired, actions


def _repair_record(*, record: dict[str, Any], run_root: Path) -> dict[str, Any]:
    result = {
        "paper_id": str(record.get("paper_id") or "").strip(),
        "status": None,
        "raw_response_path": record.get("raw_response_path"),
        "repaired_prediction_path": None,
        "prediction_paper_id": None,
        "normalization_actions": [],
        "semantic_repair_actions": [],
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

    document_artifact_path = Path(str(record.get("document_artifact_path") or "")).expanduser()
    if not document_artifact_path.exists():
        result["status"] = "missing_document_artifact"
        return result

    raw_payload = _load_json_object(raw_response_path)
    gold_path = Path(str(record.get("gold_path") or "")).expanduser()
    gold_payload = _load_json_object(gold_path)
    gold_extraction = SpecialtyTrialExtraction.model_validate(gold_payload)

    normalized_payload, normalization_actions = _normalize_payload(
        expected_paper_id=result["paper_id"],
        raw_payload=raw_payload,
        gold_payload=gold_payload,
    )
    result["normalization_actions"] = normalization_actions

    doc_artifact = _load_artifact(document_artifact_path)
    paper_payload, methods_snippet = _build_specialty_shadow_inputs(
        doc_artifact,
        paper_id=result["paper_id"],
        gold_extraction=gold_extraction,
    )
    source_text = _source_text(paper_payload=paper_payload, methods_snippet=methods_snippet)
    repaired_payload, semantic_actions = _apply_semantic_repairs(payload=normalized_payload, source_text=source_text)
    result["semantic_repair_actions"] = semantic_actions

    try:
        prediction = SpecialtyTrialExtraction.model_validate(repaired_payload)
    except Exception as exc:
        result["status"] = "semantic_prediction_schema_invalid"
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

    prediction_path = run_root / "repaired_predictions" / f"{result['paper_id'].replace(':', '_')}.json"
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    prediction_path.write_text(prediction.model_dump_json(indent=2) + "\n", encoding="utf-8")
    result["status"] = "semantic_prediction_written"
    result["repaired_prediction_path"] = str(prediction_path)
    result["compare_ready"] = True
    return result


def run_specialty_shadow_semantic_repair(
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
    results = [_repair_record(record=doc, run_root=run_root) for doc in documents if isinstance(doc, dict)]
    results.sort(key=lambda item: str(item.get("paper_id") or ""))

    compare_docs = [
        {
            "paper_id": result["paper_id"],
            "gold_path": next(
                str(doc.get("gold_path"))
                for doc in documents
                if isinstance(doc, dict) and str(doc.get("paper_id") or "") == str(result["paper_id"] or "")
            ),
            "prediction_path": result["repaired_prediction_path"],
        }
        for result in results
        if result.get("compare_ready") and result.get("repaired_prediction_path")
    ]
    generated_manifest = {
        "schema_version": "extraction_regression_manifest.v1",
        "generated_at": _utc_now_iso(),
        "source_materialized_details": str(materialized_details_path),
        "notes": [
            "Developer-only specialty shadow semantic repair audit.",
            "This lane checks whether schema-valid specialty shadow predictions can recover source-grounded core semantics without changing runtime behavior.",
        ],
        "documents": compare_docs,
    }
    _write_json(run_root / "generated_manifest.json", generated_manifest)

    status_counts = Counter(str(result.get("status") or "") for result in results)
    validation_reason_counts = Counter(
        code
        for result in results
        if str(result.get("status") or "") == "semantic_prediction_schema_invalid"
        for code in (result.get("validation_reason_codes") or [])
    )
    summary = {
        "schema_version": "specialty_runtime_shadow_semantic_repair.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "materialized_details": str(materialized_details_path),
        },
        "document_count": len(results),
        "semantic_prediction_written_count": int(status_counts.get("semantic_prediction_written", 0)),
        "compare_ready_count": len(compare_docs),
        "status_counts": {
            "semantic_prediction_written": int(status_counts.get("semantic_prediction_written", 0)),
            "semantic_prediction_schema_invalid": int(status_counts.get("semantic_prediction_schema_invalid", 0)),
            "pairing_mismatch": int(status_counts.get("pairing_mismatch", 0)),
            "missing_raw_response": int(status_counts.get("missing_raw_response", 0)),
            "missing_document_artifact": int(status_counts.get("missing_document_artifact", 0)),
            "skipped_non_schema_invalid": int(status_counts.get("skipped_non_schema_invalid", 0)),
        },
        "validation_reason_counts": {code: int(count) for code, count in sorted(validation_reason_counts.items())},
        "generated_manifest_path": str(run_root / "generated_manifest.json"),
        "generated_manifest_document_count": len(compare_docs),
    }
    detail_payload = {
        "schema_version": "specialty_runtime_shadow_semantic_repair_details.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "documents": results,
    }
    _write_json(run_root / "summary.json", summary)
    _write_json(run_root / "details.json", detail_payload)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply developer-only source-grounded semantic repair to specialty shadow outputs."
    )
    parser.add_argument("--materialized-details", required=True, help="Materialized specialty shadow details JSON.")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "extraction_runtime_shadow_semantic_repair"),
        help="Output directory for semantic-repair specialty shadow artifacts.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_specialty_shadow_semantic_repair(
        materialized_details_path=Path(args.materialized_details).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
