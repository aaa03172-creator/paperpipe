#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.vector_index_rebuild import (
    CONFIRM_REBUILD_PHRASE,
    build_vector_rebuild_dry_run_plan,
    load_document_artifact_for_rebuild,
    validate_vector_rebuild_apply,
    validate_vector_rebuild_candidates,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _delete_collection_ids(collection: Any, *, batch_size: int = 500) -> int:
    existing = collection.get(include=["metadatas"])
    ids = [str(item) for item in (existing.get("ids") or []) if str(item or "").strip()]
    for start in range(0, len(ids), batch_size):
        collection.delete(ids=ids[start : start + batch_size])
    return len(ids)


def _restore_vector_root_from_backup(vector_root: Path, backup_dir: Path) -> None:
    if vector_root.exists():
        shutil.rmtree(vector_root)
    shutil.copytree(backup_dir, vector_root)


def _apply_rebuild(plan: dict[str, Any]) -> dict[str, Any]:
    vector_root = Path(str(plan["vector_root"])).expanduser().resolve()
    backup_dir = Path(str(plan["proposed_backup_dir"])).expanduser().resolve()
    artifact_root = Path(str(plan["artifact_root"])).expanduser().resolve()
    if not vector_root.exists():
        raise RuntimeError(f"Vector root does not exist: {vector_root}")
    if backup_dir.exists():
        raise RuntimeError(f"Backup directory already exists: {backup_dir}")

    candidates = list(plan.get("candidates") or [])
    if not candidates:
        raise RuntimeError("No rebuild candidates found; refusing to clear vector index")
    preflight = validate_vector_rebuild_candidates(
        artifact_root=artifact_root,
        candidates=candidates,
    )
    if int(preflight.get("failure_count") or 0) > 0:
        raise RuntimeError(f"Preflight failed before backup/delete: {preflight}")

    backup_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(vector_root, backup_dir)

    from src.agents.indexer_agent import IndexerAgent

    agent = IndexerAgent(persist_path=str(vector_root))
    deleted_count = _delete_collection_ids(agent.collection)
    indexed_documents = 0
    indexed_chunks = 0
    failures: list[dict[str, str]] = []

    for candidate in candidates:
        document_path = artifact_root / str(candidate.get("document_artifact_path") or "")
        try:
            doc = load_document_artifact_for_rebuild(document_path)
            index_artifact = agent.process(doc)
            indexed_documents += 1
            indexed_chunks += int(index_artifact.chunk_count)
        except Exception as exc:
            failures.append(
                {
                    "document_artifact_path": str(candidate.get("document_artifact_path") or ""),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    if failures:
        _restore_vector_root_from_backup(vector_root, backup_dir)
        return {
            "applied": False,
            "restored_from_backup": True,
            "backup_dir": str(backup_dir),
            "deleted_vector_count": deleted_count,
            "preflight": preflight,
            "indexed_documents": indexed_documents,
            "indexed_chunks": indexed_chunks,
            "failure_count": len(failures),
            "failures": failures[:25],
        }

    audit = agent.audit_vector_index()
    return {
        "applied": True,
        "restored_from_backup": False,
        "backup_dir": str(backup_dir),
        "deleted_vector_count": deleted_count,
        "preflight": preflight,
        "indexed_documents": indexed_documents,
        "indexed_chunks": indexed_chunks,
        "failure_count": len(failures),
        "failures": failures[:25],
        "post_rebuild_audit": audit,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or apply a local Chroma vector-index rebuild from Deep Read document artifacts. "
            "Dry-run is the default and never modifies Chroma."
        )
    )
    parser.add_argument("--artifact-root", type=Path, default=None)
    parser.add_argument("--vector-root", type=Path, default=None)
    parser.add_argument("--backup-root", type=Path, default=None)
    parser.add_argument("--sample-limit", type=int, default=25)
    parser.add_argument("--all-runs", action="store_true", help="Plan all artifact runs instead of latest per document.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout.")
    parser.add_argument("--apply", action="store_true", help="Actually back up and rebuild the local vector index.")
    parser.add_argument(
        "--confirm",
        default=None,
        help=f"Required with --apply. Must equal {CONFIRM_REBUILD_PHRASE}.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    plan = build_vector_rebuild_dry_run_plan(
        artifact_root=args.artifact_root,
        vector_root=args.vector_root,
        backup_root=args.backup_root,
        latest_only=not args.all_runs,
        sample_limit=args.sample_limit,
    )
    error = validate_vector_rebuild_apply(apply=bool(args.apply), confirm=args.confirm)
    if error:
        payload = {"status": "refused", "error": error, "plan": plan}
        if args.output:
            _write_json(args.output, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else error)
        return 2

    payload: dict[str, Any] = {"status": "dry_run", "plan": plan}
    if args.apply:
        try:
            result = _apply_rebuild(plan)
            payload = {
                "status": "applied" if result.get("applied") else "failed",
                "plan": plan,
                "result": result,
            }
            if not result.get("applied"):
                if args.output:
                    _write_json(args.output, payload)
                print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else "rebuild failed; restored from backup")
                return 1
        except Exception as exc:
            payload = {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "plan": plan,
            }
            if args.output:
                _write_json(args.output, payload)
            print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else payload["error"])
            return 1

    if args.output:
        _write_json(args.output, payload)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"status={payload['status']}")
        print(f"candidate_count={plan['candidate_count']}")
        print(f"total_candidate_chunks={plan['total_candidate_chunks']}")
        print(f"will_modify_chroma={bool(args.apply)}")
        print(f"proposed_backup_dir={plan['proposed_backup_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
