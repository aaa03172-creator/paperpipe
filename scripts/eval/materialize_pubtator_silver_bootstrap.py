#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.bc5cdr_prediction import load_manifest, resolve_manifest_entry_path, safe_file_stem  # noqa: E402
from src.services.evidence_extraction_sidecar import write_evidence_extraction_bundle  # noqa: E402
from src.services.pubtator_adapter import load_pubtator_document, project_pubtator_to_evidence_extraction_bundle  # noqa: E402


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def materialize_pubtator_silver_bootstrap(
    *,
    manifest_path: Path,
    out_dir: Path,
    run_id: str,
) -> Path:
    documents = load_manifest(manifest_path)
    run_root = out_dir / run_id
    bundles_root = run_root / "bundles"
    run_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    generated_docs: list[dict[str, Any]] = []

    for doc in documents:
        source_path = resolve_manifest_entry_path(manifest_path, str(doc.get("source_path") or ""))
        if not source_path.exists():
            raise FileNotFoundError(f"pubtator_source_missing={source_path}")

        document = load_pubtator_document(source_path)
        paper_id = str(doc.get("paper_id") or "").strip() or document.doc_id
        safe_id = safe_file_stem(paper_id)
        bundle = project_pubtator_to_evidence_extraction_bundle(
            document,
            paper_id=paper_id,
            run_id=run_id,
            source_artifact=source_path.name,
        )
        bundle_path = write_evidence_extraction_bundle(bundle, bundles_root / safe_id)

        generated_docs.append(
            {
                "paper_id": paper_id,
                "doc_id": document.doc_id,
                "source_path": str(source_path),
                "bundle_path": str(bundle_path),
            }
        )
        rows.append(
            {
                "paper_id": paper_id,
                "doc_id": document.doc_id,
                "source_path": str(source_path),
                "bundle_path": str(bundle_path),
                "entity_record_count": bundle.metrics.entity_record_count,
                "relation_record_count": bundle.metrics.relation_record_count,
                "warning_count": len(bundle.warnings),
                "warnings": list(bundle.warnings),
            }
        )

    generated_manifest_path = run_root / "generated_manifest.json"
    _write_json(
        generated_manifest_path,
        {
            "schema_version": "pubtator_silver_generated_manifest.v1",
            "generated_at": _utc_now_iso(),
            "source_manifest": str(manifest_path),
            "documents": generated_docs,
        },
    )

    metrics = {
        "schema_version": "pubtator_silver_materialization.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "source_manifest": str(manifest_path),
        "document_count": len(rows),
        "success_count": len(rows),
        "rows": rows,
        "generated_manifest_path": str(generated_manifest_path),
    }
    _write_json(run_root / "metrics.json", metrics)
    _write_json(
        run_root / "summary.json",
        {
            "run_id": run_id,
            "status": "ok",
            "document_count": len(rows),
            "success_count": len(rows),
            "generated_manifest_path": str(generated_manifest_path),
        },
    )
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize a batch of PubTatorCentral silver documents into evidence_extraction_bundle sidecars.",
    )
    parser.add_argument("--manifest", required=True, help="Manifest with PubTator-style source_path entries.")
    parser.add_argument("--out-dir", default="snapshots/pubtator_silver_materialization", help="Output root directory.")
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("pubtator_silver_materialization_%Y%m%d_%H%M%S")
    run_root = materialize_pubtator_silver_bootstrap(
        manifest_path=Path(args.manifest).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=run_id,
    )
    print(f"[materialize_pubtator_silver_bootstrap] out={run_root}")
    print(f"[materialize_pubtator_silver_bootstrap] metrics={run_root / 'metrics.json'}")


if __name__ == "__main__":
    main()
