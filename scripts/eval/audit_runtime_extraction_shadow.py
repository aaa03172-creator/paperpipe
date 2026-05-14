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

from src.schemas.core import BiomedicalClinicalExtraction, SpecialtyTrialExtraction


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    documents = payload.get("documents")
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


def _candidate_run_dirs(*, manifest_path: Path, doc: dict[str, Any], artifacts_root: Path) -> list[Path]:
    paper_id = str(doc.get("paper_id") or "").strip()
    run_dirs: dict[str, Path] = {}

    if paper_id:
        canonical_root = artifacts_root / paper_id
        if canonical_root.exists():
            for run_dir in canonical_root.glob("run_*"):
                if run_dir.is_dir():
                    run_dirs[str(run_dir.resolve())] = run_dir.resolve()

    for source_path in doc.get("gold_source_paths") or []:
        resolved = _resolve_manifest_entry_path(manifest_path, str(source_path or ""))
        if resolved.exists():
            parent = resolved.parent.resolve()
            if parent.is_dir():
                run_dirs[str(parent)] = parent

    return sorted(run_dirs.values(), key=lambda item: item.name)


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _detect_runtime_schema(path: Path) -> str:
    payload = _load_optional_json(path)
    if payload is None:
        return "missing"
    try:
        SpecialtyTrialExtraction.model_validate(payload)
        return "specialty_trial_extraction"
    except Exception:
        pass
    try:
        BiomedicalClinicalExtraction.model_validate(payload)
        return "biomedical_clinical_extraction"
    except Exception:
        return "invalid"


def classify_shadow_record(*, manifest_path: Path, doc: dict[str, Any], artifacts_root: Path) -> dict[str, Any]:
    paper_id = str(doc.get("paper_id") or "").strip()
    gold_path = _resolve_manifest_entry_path(manifest_path, str(doc.get("gold_path") or ""))
    run_dirs = _candidate_run_dirs(manifest_path=manifest_path, doc=doc, artifacts_root=artifacts_root)

    record: dict[str, Any] = {
        "paper_id": paper_id,
        "gold_path": str(gold_path),
        "candidate_run_dir_count": len(run_dirs),
        "latest_run_dir": None,
        "latest_run_id": None,
        "latest_run_status": None,
        "clinical_extraction_status": None,
        "clinical_extraction_note_type": None,
        "clinical_extraction_artifact_path": None,
        "runtime_schema": None,
        "bucket": None,
        "shadow_comparable": False,
    }

    if not run_dirs:
        record["bucket"] = "no_runtime_run"
        record["runtime_schema"] = "missing"
        return record

    latest_run_dir = run_dirs[-1]
    record["latest_run_dir"] = str(latest_run_dir)
    record["latest_run_id"] = latest_run_dir.name

    run_meta = _load_optional_json(latest_run_dir / "run_meta.json") or {}
    bootstrap_meta = _load_optional_json(latest_run_dir / "bootstrap_meta.json") or {}
    record["latest_run_status"] = str(run_meta.get("status") or "").strip() or None
    clinical_status = str(
        run_meta.get("clinical_extraction_status")
        or bootstrap_meta.get("clinical_extraction_status")
        or ""
    ).strip() or None
    note_type = str(bootstrap_meta.get("clinical_extraction_note_type") or "").strip() or None
    record["clinical_extraction_status"] = clinical_status
    record["clinical_extraction_note_type"] = note_type

    artifact_path_raw = str(run_meta.get("clinical_extraction_artifact") or "").strip()
    artifact_path = Path(artifact_path_raw).expanduser().resolve() if artifact_path_raw else (latest_run_dir / "clinical_extraction.json").resolve()
    if not artifact_path.exists():
        artifact_path = latest_run_dir / "clinical_extraction.json"
    if artifact_path.exists():
        record["clinical_extraction_artifact_path"] = str(artifact_path)
        schema = _detect_runtime_schema(artifact_path)
        record["runtime_schema"] = schema
        if schema == "specialty_trial_extraction":
            record["bucket"] = "specialty_runtime_artifact"
            record["shadow_comparable"] = True
        elif schema == "biomedical_clinical_extraction":
            record["bucket"] = "biomedical_runtime_artifact"
        else:
            record["bucket"] = "invalid_runtime_artifact"
        return record

    record["runtime_schema"] = "missing"
    if clinical_status == "not_clinical_note":
        record["bucket"] = "not_clinical_note"
    elif clinical_status:
        record["bucket"] = "runtime_status_without_artifact"
    else:
        record["bucket"] = "legacy_missing_status"
    return record


def run_shadow_audit(
    *,
    manifest_path: Path,
    artifacts_root: Path,
    out_dir: Path,
    run_id: str,
) -> Path:
    documents = _load_manifest(manifest_path)
    records = [
        classify_shadow_record(manifest_path=manifest_path, doc=doc, artifacts_root=artifacts_root)
        for doc in documents
    ]
    records.sort(key=lambda item: str(item.get("paper_id") or ""))

    bucket_counts = Counter(str(item.get("bucket") or "") for item in records)
    schema_counts = Counter(str(item.get("runtime_schema") or "") for item in records)
    compare_docs = [
        {
            "paper_id": item["paper_id"],
            "gold_path": item["gold_path"],
            "prediction_path": item["clinical_extraction_artifact_path"],
        }
        for item in records
        if item.get("shadow_comparable") and item.get("clinical_extraction_artifact_path")
    ]

    run_root = out_dir / run_id
    compare_manifest = {
        "schema_version": "extraction_regression_manifest.v1",
        "generated_at": _utc_now_iso(),
        "source_manifest": str(manifest_path),
        "notes": [
            "Shadow-compare manifest containing only runtime-persisted SpecialtyTrialExtraction artifacts.",
            "This manifest may be empty when runtime does not persist a comparable specialty extraction artifact for the target set.",
        ],
        "documents": compare_docs,
    }
    _write_json(run_root / "shadow_compare_manifest.json", compare_manifest)

    summary = {
        "schema_version": "runtime_extraction_shadow_audit.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "manifest": str(manifest_path),
            "artifacts_root": str(artifacts_root),
        },
        "document_count": len(records),
        "documents_with_runtime_runs": sum(1 for item in records if int(item.get("candidate_run_dir_count") or 0) > 0),
        "documents_with_shadow_comparable_runtime_artifact": len(compare_docs),
        "bucket_counts": {
            "specialty_runtime_artifact": int(bucket_counts.get("specialty_runtime_artifact", 0)),
            "biomedical_runtime_artifact": int(bucket_counts.get("biomedical_runtime_artifact", 0)),
            "invalid_runtime_artifact": int(bucket_counts.get("invalid_runtime_artifact", 0)),
            "not_clinical_note": int(bucket_counts.get("not_clinical_note", 0)),
            "runtime_status_without_artifact": int(bucket_counts.get("runtime_status_without_artifact", 0)),
            "legacy_missing_status": int(bucket_counts.get("legacy_missing_status", 0)),
            "no_runtime_run": int(bucket_counts.get("no_runtime_run", 0)),
        },
        "runtime_schema_counts": {
            "specialty_trial_extraction": int(schema_counts.get("specialty_trial_extraction", 0)),
            "biomedical_clinical_extraction": int(schema_counts.get("biomedical_clinical_extraction", 0)),
            "invalid": int(schema_counts.get("invalid", 0)),
            "missing": int(schema_counts.get("missing", 0)),
        },
        "shadow_compare_manifest_path": str(run_root / "shadow_compare_manifest.json"),
        "shadow_compare_manifest_document_count": len(compare_docs),
        "non_comparable_papers": [
            {
                "paper_id": item["paper_id"],
                "bucket": item["bucket"],
                "clinical_extraction_status": item["clinical_extraction_status"],
                "clinical_extraction_note_type": item["clinical_extraction_note_type"],
            }
            for item in records
            if not item.get("shadow_comparable")
        ],
    }
    details = {
        "schema_version": "runtime_extraction_shadow_audit_details.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "documents": records,
    }
    _write_json(run_root / "summary.json", summary)
    _write_json(run_root / "details.json", details)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit runtime extraction availability against a repo-grounded SpecialtyTrialExtraction gold manifest."
    )
    parser.add_argument("--manifest", required=True, help="Repo-grounded gold manifest to inspect.")
    parser.add_argument("--artifacts-root", default="storage/artifacts", help="Root directory containing runtime artifact runs.")
    parser.add_argument("--out-dir", required=True, help="Directory to write audit outputs into.")
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    run_id = args.run_id.strip() or f"runtime_extraction_shadow_audit_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_root = run_shadow_audit(
        manifest_path=Path(args.manifest).expanduser().resolve(),
        artifacts_root=Path(args.artifacts_root).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=run_id,
    )
    print(f"[audit_runtime_extraction_shadow] out={run_root}")
    print(f"[audit_runtime_extraction_shadow] summary={run_root / 'summary.json'}")


if __name__ == "__main__":
    main()
