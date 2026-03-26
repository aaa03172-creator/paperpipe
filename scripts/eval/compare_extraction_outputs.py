#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.core import TrialExtraction


CORE_FIELDS = ("population", "intervention", "outcome", "sample_size", "duration")
NEGATION_POSITIVE_VALUES = {"improved", "worsened", "mixed"}
MISSING_FIELD_ALIASES = {
    "population": {"population", "mci_only", "population.mci_only"},
    "intervention": {
        "intervention",
        "intervention.category",
        "intervention.product_name",
        "category",
        "product_name",
    },
    "outcome": {"outcome", "outcomes", "outcomes.cognition", "primary_outcome", "primary_readout"},
    "sample_size": {"sample_size", "population.n_total", "n_total"},
    "duration": {"duration", "duration_weeks", "intervention.duration_weeks", "study_design.duration_weeks"},
    "comparator": {"comparator", "comparator.description"},
    "outcome_effect": {"outcome_effect", "effect_direction", "outcomes.cognition.effect_direction"},
    "eligibility": {
        "eligibility",
        "eligibility_flags",
        "eligibility_flags.include_for_mci_mct_review",
        "include_for_mci_mct_review",
    },
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents = payload.get("documents") if isinstance(payload, dict) else None
    if not isinstance(documents, list):
        raise RuntimeError(f"manifest_missing_documents={path}")
    return [doc for doc in documents if isinstance(doc, dict)]


def _normalize_text(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _unwrap_extraction_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("trial_extraction", "extraction", "data"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
    return payload


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return _unwrap_extraction_payload(payload)


def _missing_aliases(extraction: TrialExtraction) -> set[str]:
    values = extraction.extraction_quality.missing_fields or []
    return {_normalize_text(value) for value in values if _normalize_text(value)}


def _field_marked_missing(missing_fields: set[str], field_name: str) -> bool:
    aliases = MISSING_FIELD_ALIASES.get(field_name, set())
    normalized_aliases = {_normalize_text(alias) for alias in aliases if _normalize_text(alias)}
    return any(alias in missing_fields for alias in normalized_aliases)


def _normalized_snapshot(extraction: TrialExtraction) -> dict[str, Any]:
    missing_fields = _missing_aliases(extraction)
    first_outcome = extraction.outcomes.cognition[0] if extraction.outcomes.cognition else None

    population_value: bool | None
    if _field_marked_missing(missing_fields, "population"):
        population_value = None
    else:
        population_value = bool(extraction.population.mci_only)

    if _field_marked_missing(missing_fields, "intervention"):
        intervention_core = None
    else:
        intervention_core = None
        if extraction.intervention.category != "unknown":
            intervention_core = str(extraction.intervention.category)
        elif extraction.intervention.product_name:
            intervention_core = _normalize_text(extraction.intervention.product_name)

    if _field_marked_missing(missing_fields, "outcome"):
        outcome_name = None
    else:
        outcome_name = _normalize_text(first_outcome.name) if first_outcome and first_outcome.name else None

    if _field_marked_missing(missing_fields, "sample_size"):
        sample_size = None
    else:
        sample_size = int(extraction.population.n_total) if int(extraction.population.n_total or 0) > 0 else None

    raw_duration = int(extraction.intervention.duration_weeks or 0) or int(extraction.study_design.duration_weeks or 0)
    if _field_marked_missing(missing_fields, "duration"):
        duration_weeks = None
    else:
        duration_weeks = raw_duration if raw_duration > 0 else None

    if _field_marked_missing(missing_fields, "outcome_effect"):
        outcome_effect = None
    else:
        raw_effect = str(first_outcome.effect_direction) if first_outcome else ""
        outcome_effect = raw_effect if raw_effect and raw_effect != "unknown" else None

    if _field_marked_missing(missing_fields, "eligibility"):
        include_for_review = None
    else:
        include_for_review = bool(extraction.eligibility_flags.include_for_mci_mct_review)

    if _field_marked_missing(missing_fields, "comparator"):
        comparator_text = None
    else:
        comparator_text = _normalize_text(extraction.comparator.description)

    intervention_text = _normalize_text(extraction.intervention.product_name)
    if intervention_text is None and extraction.intervention.category != "unknown":
        intervention_text = _normalize_text(extraction.intervention.category)

    return {
        "paper_id": str(extraction.paper_id),
        "missing_fields": sorted(value for value in missing_fields if value),
        "population_mci_only": population_value,
        "intervention_core": intervention_core,
        "outcome_name": outcome_name,
        "sample_size": sample_size,
        "duration_weeks": duration_weeks,
        "intervention_text": intervention_text,
        "comparator_text": comparator_text,
        "outcome_effect": outcome_effect,
        "include_for_review": include_for_review,
    }


def _core_field_map(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "population": snapshot.get("population_mci_only"),
        "intervention": snapshot.get("intervention_core"),
        "outcome": snapshot.get("outcome_name"),
        "sample_size": snapshot.get("sample_size"),
        "duration": snapshot.get("duration_weeks"),
    }


def _classify_buckets(*, gold: dict[str, Any], prediction: dict[str, Any], mismatched_fields: list[str]) -> list[str]:
    buckets: list[str] = []
    gold_core = _core_field_map(gold)
    prediction_core = _core_field_map(prediction)

    if any(gold_core.get(field) is not None and prediction_core.get(field) is None for field in CORE_FIELDS):
        buckets.append("missing_core_field")
    if any(gold_core.get(field) is None and prediction_core.get(field) is not None for field in CORE_FIELDS):
        buckets.append("hallucination")

    gold_effect = gold.get("outcome_effect")
    pred_effect = prediction.get("outcome_effect")
    gold_include = gold.get("include_for_review")
    pred_include = prediction.get("include_for_review")
    if (
        (gold_effect == "no_change" and pred_effect in NEGATION_POSITIVE_VALUES)
        or (pred_effect == "no_change" and gold_effect in NEGATION_POSITIVE_VALUES)
        or (gold_include is False and pred_include is True)
    ):
        buckets.append("negation_failure")

    gold_intervention = gold.get("intervention_text")
    gold_comparator = gold.get("comparator_text")
    pred_intervention = prediction.get("intervention_text")
    pred_comparator = prediction.get("comparator_text")
    if (
        (gold_comparator and pred_intervention and gold_comparator == pred_intervention)
        or (gold_intervention and pred_comparator and gold_intervention == pred_comparator)
    ):
        buckets.append("comparator_confusion")

    if mismatched_fields and not buckets:
        buckets.append("other_core_mismatch")

    return buckets


def evaluate_extraction_pair(
    *,
    gold_path: Path,
    prediction_path: Path,
    paper_id: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": "extraction_regression_eval_row.v1",
        "evaluated_at": _utc_now_iso(),
        "paper_id": paper_id,
        "gold_path": str(gold_path),
        "prediction_path": str(prediction_path),
        "schema_valid": False,
        "pairing_valid": True,
        "error": None,
        "core_fields": {},
        "mismatched_fields": [],
        "buckets": [],
        "gold_snapshot": {},
        "prediction_snapshot": {},
    }

    gold_payload = _load_json_object(gold_path.expanduser().resolve())
    gold_extraction = TrialExtraction.model_validate(gold_payload)
    row["paper_id"] = row["paper_id"] or str(gold_extraction.paper_id)
    gold_snapshot = _normalized_snapshot(gold_extraction)
    row["gold_snapshot"] = gold_snapshot

    try:
        prediction_payload = _load_json_object(prediction_path.expanduser().resolve())
        prediction_extraction = TrialExtraction.model_validate(prediction_payload)
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["buckets"] = ["schema_invalid"]
        return row

    row["schema_valid"] = True
    gold_paper_id = str(gold_extraction.paper_id)
    prediction_paper_id = str(prediction_extraction.paper_id)
    expected_paper_id = str(row["paper_id"] or gold_paper_id)
    if len({expected_paper_id, gold_paper_id, prediction_paper_id}) != 1:
        row["pairing_valid"] = False
        row["error"] = (
            f"PAIRING_MISMATCH expected={expected_paper_id} "
            f"gold={gold_paper_id} prediction={prediction_paper_id}"
        )
        row["buckets"] = ["pairing_mismatch"]
        return row

    row["paper_id"] = expected_paper_id
    prediction_snapshot = _normalized_snapshot(prediction_extraction)
    row["prediction_snapshot"] = prediction_snapshot

    gold_core = _core_field_map(gold_snapshot)
    prediction_core = _core_field_map(prediction_snapshot)
    core_fields: dict[str, Any] = {}
    mismatched_fields: list[str] = []
    for field_name in CORE_FIELDS:
        gold_value = gold_core.get(field_name)
        prediction_value = prediction_core.get(field_name)
        match = gold_value == prediction_value
        core_fields[field_name] = {
            "gold": gold_value,
            "prediction": prediction_value,
            "match": match,
        }
        if not match:
            mismatched_fields.append(field_name)

    row["core_fields"] = core_fields
    row["mismatched_fields"] = mismatched_fields
    row["buckets"] = _classify_buckets(gold=gold_snapshot, prediction=prediction_snapshot, mismatched_fields=mismatched_fields)
    return row


def compare_extraction_rows(
    *,
    rows: list[dict[str, Any]],
    max_pairing_mismatch_docs: int = 0,
    max_schema_invalid_docs: int = 0,
    max_missing_core_field_docs: int = 0,
    max_hallucination_docs: int = 0,
    max_negation_failure_docs: int = 0,
    max_comparator_confusion_docs: int = 0,
    max_other_core_mismatch_docs: int = 0,
    max_core_mismatch_docs: int = 0,
) -> dict[str, Any]:
    pairing_mismatch_docs = [row for row in rows if "pairing_mismatch" in (row.get("buckets") or [])]
    schema_invalid_docs = [row for row in rows if not bool(row.get("schema_valid"))]
    missing_core_field_docs = [row for row in rows if "missing_core_field" in (row.get("buckets") or [])]
    hallucination_docs = [row for row in rows if "hallucination" in (row.get("buckets") or [])]
    negation_failure_docs = [row for row in rows if "negation_failure" in (row.get("buckets") or [])]
    comparator_confusion_docs = [row for row in rows if "comparator_confusion" in (row.get("buckets") or [])]
    other_core_mismatch_docs = [row for row in rows if "other_core_mismatch" in (row.get("buckets") or [])]
    core_mismatch_docs = [row for row in rows if row.get("mismatched_fields")]

    match_rates: dict[str, float] = {}
    for field_name in CORE_FIELDS:
        values = [
            bool(((row.get("core_fields") or {}).get(field_name) or {}).get("match"))
            for row in rows
            if field_name in (row.get("core_fields") or {})
        ]
        match_rates[field_name] = mean(values) if values else 0.0

    failed_checks: list[str] = []
    if len(pairing_mismatch_docs) > max_pairing_mismatch_docs:
        failed_checks.append("pairing_mismatch_docs")
    if len(schema_invalid_docs) > max_schema_invalid_docs:
        failed_checks.append("schema_invalid_docs")
    if len(missing_core_field_docs) > max_missing_core_field_docs:
        failed_checks.append("missing_core_field_docs")
    if len(hallucination_docs) > max_hallucination_docs:
        failed_checks.append("hallucination_docs")
    if len(negation_failure_docs) > max_negation_failure_docs:
        failed_checks.append("negation_failure_docs")
    if len(comparator_confusion_docs) > max_comparator_confusion_docs:
        failed_checks.append("comparator_confusion_docs")
    if len(other_core_mismatch_docs) > max_other_core_mismatch_docs:
        failed_checks.append("other_core_mismatch_docs")
    if len(core_mismatch_docs) > max_core_mismatch_docs:
        failed_checks.append("core_mismatch_docs")

    return {
        "document_count": len(rows),
        "pairing_mismatch_docs": [
            {"paper_id": row.get("paper_id"), "error": row.get("error"), "prediction_path": row.get("prediction_path")}
            for row in pairing_mismatch_docs
        ],
        "schema_invalid_docs": [
            {"paper_id": row.get("paper_id"), "error": row.get("error"), "prediction_path": row.get("prediction_path")}
            for row in schema_invalid_docs
        ],
        "missing_core_field_docs": [
            {"paper_id": row.get("paper_id"), "mismatched_fields": row.get("mismatched_fields")}
            for row in missing_core_field_docs
        ],
        "hallucination_docs": [
            {"paper_id": row.get("paper_id"), "mismatched_fields": row.get("mismatched_fields")}
            for row in hallucination_docs
        ],
        "negation_failure_docs": [
            {"paper_id": row.get("paper_id"), "mismatched_fields": row.get("mismatched_fields")}
            for row in negation_failure_docs
        ],
        "comparator_confusion_docs": [
            {"paper_id": row.get("paper_id"), "mismatched_fields": row.get("mismatched_fields")}
            for row in comparator_confusion_docs
        ],
        "other_core_mismatch_docs": [
            {"paper_id": row.get("paper_id"), "mismatched_fields": row.get("mismatched_fields")}
            for row in other_core_mismatch_docs
        ],
        "core_mismatch_docs": [
            {"paper_id": row.get("paper_id"), "mismatched_fields": row.get("mismatched_fields")}
            for row in core_mismatch_docs
        ],
        "core_field_match_rates": match_rates,
        "decision": {
            "passed": len(failed_checks) == 0,
            "failed_checks": failed_checks,
            "thresholds": {
                "max_pairing_mismatch_docs": max_pairing_mismatch_docs,
                "max_schema_invalid_docs": max_schema_invalid_docs,
                "max_missing_core_field_docs": max_missing_core_field_docs,
                "max_hallucination_docs": max_hallucination_docs,
                "max_negation_failure_docs": max_negation_failure_docs,
                "max_comparator_confusion_docs": max_comparator_confusion_docs,
                "max_other_core_mismatch_docs": max_other_core_mismatch_docs,
                "max_core_mismatch_docs": max_core_mismatch_docs,
            },
        },
    }


def run_comparison(
    *,
    manifest_path: Path,
    out_dir: Path,
    run_id: str,
    max_pairing_mismatch_docs: int,
    max_schema_invalid_docs: int,
    max_missing_core_field_docs: int,
    max_hallucination_docs: int,
    max_negation_failure_docs: int,
    max_comparator_confusion_docs: int,
    max_other_core_mismatch_docs: int,
    max_core_mismatch_docs: int,
) -> Path:
    documents = _load_manifest(manifest_path)
    rows: list[dict[str, Any]] = []
    for doc in documents:
        gold_path = Path(str(doc.get("gold_path") or "")).expanduser().resolve()
        prediction_path = Path(str(doc.get("prediction_path") or "")).expanduser().resolve()
        paper_id = str(doc.get("paper_id") or "").strip() or None
        if not gold_path.exists():
            raise FileNotFoundError(f"gold_missing={gold_path}")
        rows.append(
            evaluate_extraction_pair(
                gold_path=gold_path,
                prediction_path=prediction_path,
                paper_id=paper_id,
            )
        )

    run_root = out_dir / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    detailed_results_path = run_root / "detailed_results.jsonl"
    with detailed_results_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    comparison = compare_extraction_rows(
        rows=rows,
        max_pairing_mismatch_docs=max_pairing_mismatch_docs,
        max_schema_invalid_docs=max_schema_invalid_docs,
        max_missing_core_field_docs=max_missing_core_field_docs,
        max_hallucination_docs=max_hallucination_docs,
        max_negation_failure_docs=max_negation_failure_docs,
        max_comparator_confusion_docs=max_comparator_confusion_docs,
        max_other_core_mismatch_docs=max_other_core_mismatch_docs,
        max_core_mismatch_docs=max_core_mismatch_docs,
    )

    metrics = {
        "schema_version": "extraction_regression_eval.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "document_count": len(rows),
        "inputs": {
            "manifest": str(manifest_path),
        },
        "comparison": comparison,
    }
    _write_json(run_root / "metrics.json", metrics)
    _write_json(
        run_root / "summary.json",
        {
            "run_id": run_id,
            "status": "ok",
            "metrics_path": str(run_root / "metrics.json"),
            "details_path": str(detailed_results_path),
            "passed": comparison["decision"]["passed"],
            "failed_checks": comparison["decision"]["failed_checks"],
        },
    )
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare TrialExtraction outputs against a bounded goldset.")
    parser.add_argument("--manifest", required=True, help="Manifest with documents[].gold_path and prediction_path.")
    parser.add_argument("--out-dir", default="snapshots/extraction_regression_eval", help="Output root directory.")
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    parser.add_argument("--max-pairing-mismatch-docs", type=int, default=0)
    parser.add_argument("--max-schema-invalid-docs", type=int, default=0)
    parser.add_argument("--max-missing-core-field-docs", type=int, default=0)
    parser.add_argument("--max-hallucination-docs", type=int, default=0)
    parser.add_argument("--max-negation-failure-docs", type=int, default=0)
    parser.add_argument("--max-comparator-confusion-docs", type=int, default=0)
    parser.add_argument("--max-other-core-mismatch-docs", type=int, default=0)
    parser.add_argument("--max-core-mismatch-docs", type=int, default=0)
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    run_id = args.run_id or datetime.now(timezone.utc).strftime("extraction_regression_eval_%Y%m%d_%H%M%S")
    run_root = run_comparison(
        manifest_path=Path(args.manifest).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=run_id,
        max_pairing_mismatch_docs=int(args.max_pairing_mismatch_docs),
        max_schema_invalid_docs=int(args.max_schema_invalid_docs),
        max_missing_core_field_docs=int(args.max_missing_core_field_docs),
        max_hallucination_docs=int(args.max_hallucination_docs),
        max_negation_failure_docs=int(args.max_negation_failure_docs),
        max_comparator_confusion_docs=int(args.max_comparator_confusion_docs),
        max_other_core_mismatch_docs=int(args.max_other_core_mismatch_docs),
        max_core_mismatch_docs=int(args.max_core_mismatch_docs),
    )
    print(f"[compare_extraction_outputs] out={run_root}")
    print(f"[compare_extraction_outputs] metrics={run_root / 'metrics.json'}")


if __name__ == "__main__":
    main()
