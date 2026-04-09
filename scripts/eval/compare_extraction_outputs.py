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


def _resolve_manifest_entry_path(manifest_path: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path or "").strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (manifest_path.parent / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


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

    if _field_marked_missing(missing_fields, "population"):
        population_value: bool | None = None
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
    if gold_paper_id != prediction_paper_id:
        row["pairing_valid"] = False
        row["error"] = f"PAIRING_MISMATCH gold={gold_paper_id} prediction={prediction_paper_id}"
        row["prediction_snapshot"] = _normalized_snapshot(prediction_extraction)
        row["buckets"] = ["pairing_mismatch"]
        return row

    prediction_snapshot = _normalized_snapshot(prediction_extraction)
    row["prediction_snapshot"] = prediction_snapshot

    core_fields: dict[str, dict[str, Any]] = {}
    mismatched_fields: list[str] = []
    for field in CORE_FIELDS:
        gold_value = _core_field_map(gold_snapshot).get(field)
        prediction_value = _core_field_map(prediction_snapshot).get(field)
        matched = gold_value == prediction_value
        core_fields[field] = {
            "gold": gold_value,
            "prediction": prediction_value,
            "matched": matched,
        }
        if not matched:
            mismatched_fields.append(field)

    row["core_fields"] = core_fields
    row["mismatched_fields"] = mismatched_fields
    row["buckets"] = _classify_buckets(
        gold=gold_snapshot,
        prediction=prediction_snapshot,
        mismatched_fields=mismatched_fields,
    )
    return row


def compare_extraction_rows(*, rows: list[dict[str, Any]]) -> dict[str, Any]:
    document_count = len(rows)
    schema_invalid_docs = [row for row in rows if "schema_invalid" in row.get("buckets", [])]
    pairing_mismatch_docs = [row for row in rows if "pairing_mismatch" in row.get("buckets", [])]
    missing_core_field_docs = [row for row in rows if "missing_core_field" in row.get("buckets", [])]
    negation_failure_docs = [row for row in rows if "negation_failure" in row.get("buckets", [])]
    comparator_confusion_docs = [row for row in rows if "comparator_confusion" in row.get("buckets", [])]
    hallucination_docs = [row for row in rows if "hallucination" in row.get("buckets", [])]
    other_core_mismatch_docs = [row for row in rows if "other_core_mismatch" in row.get("buckets", [])]

    core_field_match_rates: dict[str, float] = {}
    for field in CORE_FIELDS:
        values = [bool(row.get("core_fields", {}).get(field, {}).get("matched")) for row in rows if row.get("schema_valid")]
        core_field_match_rates[field] = mean(values) if values else 0.0

    failed_checks: list[str] = []
    if schema_invalid_docs or pairing_mismatch_docs:
        failed_checks.append("invalid_docs")
    if any(group for group in (missing_core_field_docs, negation_failure_docs, comparator_confusion_docs, hallucination_docs, other_core_mismatch_docs)):
        failed_checks.append("core_mismatch_docs")

    return {
        "schema_version": "extraction_regression_eval_compare.v1",
        "generated_at": _utc_now_iso(),
        "document_count": document_count,
        "schema_invalid_docs": schema_invalid_docs,
        "pairing_mismatch_docs": pairing_mismatch_docs,
        "missing_core_field_docs": missing_core_field_docs,
        "negation_failure_docs": negation_failure_docs,
        "comparator_confusion_docs": comparator_confusion_docs,
        "hallucination_docs": hallucination_docs,
        "other_core_mismatch_docs": other_core_mismatch_docs,
        "core_field_match_rates": core_field_match_rates,
        "decision": {
            "passed": not failed_checks,
            "failed_checks": failed_checks,
        },
    }


def run_comparison(
    *,
    manifest_path: Path,
    out_dir: Path,
    run_id: str,
) -> Path:
    documents = _load_manifest(manifest_path)
    rows: list[dict[str, Any]] = []
    for doc in documents:
        gold_path = _resolve_manifest_entry_path(manifest_path, str(doc.get("gold_path") or ""))
        prediction_path = _resolve_manifest_entry_path(manifest_path, str(doc.get("prediction_path") or ""))
        paper_id = str(doc.get("paper_id") or "").strip() or None
        if not gold_path.exists():
            raise FileNotFoundError(f"gold_missing={gold_path}")
        if not prediction_path.exists():
            raise FileNotFoundError(f"prediction_missing={prediction_path}")
        rows.append(
            evaluate_extraction_pair(
                gold_path=gold_path,
                prediction_path=prediction_path,
                paper_id=paper_id,
            )
        )

    comparison = compare_extraction_rows(rows=rows)
    run_root = out_dir / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    _write_json(run_root / "metrics.json", {"comparison": comparison, "document_count": len(rows)})
    _write_json(run_root / "summary.json", {"status": "ok", "document_count": len(rows)})
    (run_root / "detailed_results.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return run_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare gold vs prediction extraction outputs.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--run-id", type=str, required=True)
    args = parser.parse_args()

    run_root = run_comparison(
        manifest_path=args.manifest.expanduser().resolve(),
        out_dir=args.out_dir.expanduser().resolve(),
        run_id=str(args.run_id).strip(),
    )
    print(json.dumps({"run_root": str(run_root)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
