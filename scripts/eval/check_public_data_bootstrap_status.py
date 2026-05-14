#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


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


def _load_json_list(path: Path) -> list[Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        questions = payload.get("questions")
        if isinstance(questions, list):
            return questions
    if not isinstance(payload, list):
        raise RuntimeError(f"invalid_json_list={path}")
    return payload


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _resolve_manifest_entry_path(manifest_path: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path or "").strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (manifest_path.parent / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def _count_document_source_shapes(manifest_path: Path, *, key: str) -> dict[str, int]:
    payload = _load_json_object(manifest_path)
    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise RuntimeError(f"manifest_missing_documents={manifest_path}")

    shape_counts: dict[str, int] = {}
    for item in documents:
        if not isinstance(item, dict):
            continue
        resolved = _resolve_source_payload_path(manifest_path, item.get(key))
        source_payload = _load_json_object(resolved)
        shape = _infer_document_shape(source_payload)
        shape_counts[shape] = shape_counts.get(shape, 0) + 1
    return shape_counts


def _resolve_source_payload_path(manifest_path: Path, raw_value: object) -> Path:
    if isinstance(raw_value, list):
        for entry in raw_value:
            if str(entry or "").strip():
                return _resolve_manifest_entry_path(manifest_path, str(entry))
        raise RuntimeError(f"manifest_missing_source_path={manifest_path}")
    if isinstance(raw_value, str) and raw_value.strip():
        return _resolve_manifest_entry_path(manifest_path, raw_value)
    raise RuntimeError(f"manifest_missing_source_path={manifest_path}")


def _infer_document_shape(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("pages"), list):
        return "pages"
    if isinstance(payload.get("sections"), list):
        return "sections"
    if "documents" in payload:
        return "bioc_collection"
    if isinstance(payload.get("passages"), list):
        return "direct_document"
    return "unknown"


def build_public_data_bootstrap_summary(
    *,
    bc5cdr_manifest_path: Path,
    biored_manifest_path: Path,
    pubtator_manifest_path: Path,
    bioasq_questions_path: Path,
    bioasq_run_metrics_path: Path,
    bioasq_screening_queue_path: Path,
    run_id: str,
) -> dict[str, Any]:
    bc5cdr_manifest = _load_json_object(bc5cdr_manifest_path)
    biored_manifest = _load_json_object(biored_manifest_path)
    pubtator_manifest = _load_json_object(pubtator_manifest_path)
    bioasq_questions = [item for item in _load_json_list(bioasq_questions_path) if isinstance(item, dict)]
    bioasq_metrics = _load_json_object(bioasq_run_metrics_path)
    bioasq_rows = _load_jsonl_rows(bioasq_screening_queue_path)

    bc5cdr_documents = [item for item in (bc5cdr_manifest.get("documents") or []) if isinstance(item, dict)]
    biored_documents = [item for item in (biored_manifest.get("documents") or []) if isinstance(item, dict)]
    pubtator_documents = [item for item in (pubtator_manifest.get("documents") or []) if isinstance(item, dict)]

    question_alias_fallback_count = sum(
        1
        for row in bioasq_questions
        if (
            isinstance(row.get("metadata"), dict)
            and isinstance(row["metadata"].get("source_candidate_aliases"), list)
            and row["metadata"]["source_candidate_aliases"]
        )
        or (isinstance(row.get("source_candidate_aliases"), list) and row.get("source_candidate_aliases"))
    )
    row_identifier_alias_count = sum(
        1
        for row in bioasq_rows
        if isinstance(row.get("metadata"), dict)
        and isinstance(row["metadata"].get("identifier_aliases"), list)
        and row["metadata"]["identifier_aliases"]
    )

    lanes = {
        "bc5cdr_prediction": {
            "lane_type": "extraction_gold_prediction_replay",
            "source_manifest": str(bc5cdr_manifest_path),
            "document_count": len(bc5cdr_documents),
            "source_shape_counts": _count_document_source_shapes(bc5cdr_manifest_path, key="gold_source_paths"),
            "replay_ready": len(bc5cdr_documents) > 0,
            "canonical_owner_changed": False,
        },
        "biored_prediction": {
            "lane_type": "extraction_gold_prediction_replay",
            "source_manifest": str(biored_manifest_path),
            "document_count": len(biored_documents),
            "source_shape_counts": _count_document_source_shapes(biored_manifest_path, key="gold_source_paths"),
            "replay_ready": len(biored_documents) > 0,
            "supports_relation_novelty": True,
            "canonical_owner_changed": False,
        },
        "pubtator_silver": {
            "lane_type": "silver_bootstrap_batch_replay",
            "source_manifest": str(pubtator_manifest_path),
            "document_count": len(pubtator_documents),
            "source_shape_counts": _count_document_source_shapes(pubtator_manifest_path, key="source_path"),
            "replay_ready": len(pubtator_documents) > 0,
            "explicit_silver_provenance": True,
            "canonical_owner_changed": False,
        },
        "bioasq_eval": {
            "lane_type": "retrieval_evidence_replay",
            "questions_path": str(bioasq_questions_path),
            "run_metrics_path": str(bioasq_run_metrics_path),
            "screening_queue_path": str(bioasq_screening_queue_path),
            "question_count": len(bioasq_questions),
            "screening_row_count": len(bioasq_rows),
            "question_identifier_alias_fixture_count": question_alias_fallback_count,
            "row_identifier_alias_fixture_count": row_identifier_alias_count,
            "metrics_seed_run_id": str(bioasq_metrics.get("run_id") or ""),
            "replay_ready": bool(bioasq_questions) and bool(bioasq_rows),
            "canonical_owner_changed": False,
        },
    }

    replay_ready = all(bool(lane.get("replay_ready")) for lane in lanes.values())
    blockers: list[str] = []
    if not replay_ready:
        blockers.append("missing_repo_grounded_replay_lane")

    return {
        "schema_version": "public_data_bootstrap_status.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "lanes": lanes,
        "decision": {
            "repo_grounded_replay_ready": replay_ready,
            "sidecar_bootstrap_ready": replay_ready,
            "runtime_promotion_ready": False,
            "blockers": blockers,
        },
        "public_data_sufficient_for": [
            "bounded_extraction_eval",
            "bounded_extraction_prediction_replay",
            "silver_bootstrap_projection",
            "retrieval_evidence_eval",
            "rerank_calibration",
        ],
        "internal_data_still_required_for": [
            "project_context_relevance",
            "state_transition_supervision",
            "artifact_generation_supervision",
            "runtime_default_promotion",
        ],
    }


def run_public_data_bootstrap_status(
    *,
    bc5cdr_manifest_path: Path,
    biored_manifest_path: Path,
    pubtator_manifest_path: Path,
    bioasq_questions_path: Path,
    bioasq_run_metrics_path: Path,
    bioasq_screening_queue_path: Path,
    out_dir: Path,
    run_id: str,
) -> Path:
    summary = build_public_data_bootstrap_summary(
        bc5cdr_manifest_path=bc5cdr_manifest_path,
        biored_manifest_path=biored_manifest_path,
        pubtator_manifest_path=pubtator_manifest_path,
        bioasq_questions_path=bioasq_questions_path,
        bioasq_run_metrics_path=bioasq_run_metrics_path,
        bioasq_screening_queue_path=bioasq_screening_queue_path,
        run_id=run_id,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize the repo-grounded public-data bootstrap status across extraction, silver bootstrap, and retrieval lanes."
    )
    parser.add_argument(
        "--bc5cdr-manifest",
        default=str(ROOT / "goldset" / "manifests" / "bc5cdr_prediction_repo_grounded_pilot_20260413.json"),
        help="BC5CDR repo-grounded replay manifest.",
    )
    parser.add_argument(
        "--biored-manifest",
        default=str(ROOT / "goldset" / "manifests" / "biored_prediction_repo_grounded_pilot_20260409.json"),
        help="BioRED repo-grounded replay manifest.",
    )
    parser.add_argument(
        "--pubtator-manifest",
        default=str(ROOT / "goldset" / "manifests" / "pubtator_silver_repo_grounded_pilot_20260409.json"),
        help="PubTatorCentral repo-grounded silver manifest.",
    )
    parser.add_argument(
        "--bioasq-questions",
        default=str(ROOT / "goldset" / "bioasq_eval" / "repo_grounded_pilot_20260410" / "questions" / "repo_grounded_questions.json"),
        help="BioASQ repo-grounded question fixture.",
    )
    parser.add_argument(
        "--bioasq-run-metrics",
        default=str(ROOT / "goldset" / "bioasq_eval" / "repo_grounded_pilot_20260410" / "run_dir" / "metrics.json"),
        help="BioASQ repo-grounded run metrics fixture.",
    )
    parser.add_argument(
        "--bioasq-screening-queue",
        default=str(ROOT / "goldset" / "bioasq_eval" / "repo_grounded_pilot_20260410" / "run_dir" / "screening_queue.jsonl"),
        help="BioASQ repo-grounded screening queue fixture.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "public_data_bootstrap_status"),
        help="Output root directory for the summary.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_public_data_bootstrap_status(
        bc5cdr_manifest_path=Path(args.bc5cdr_manifest).expanduser().resolve(),
        biored_manifest_path=Path(args.biored_manifest).expanduser().resolve(),
        pubtator_manifest_path=Path(args.pubtator_manifest).expanduser().resolve(),
        bioasq_questions_path=Path(args.bioasq_questions).expanduser().resolve(),
        bioasq_run_metrics_path=Path(args.bioasq_run_metrics).expanduser().resolve(),
        bioasq_screening_queue_path=Path(args.bioasq_screening_queue).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
