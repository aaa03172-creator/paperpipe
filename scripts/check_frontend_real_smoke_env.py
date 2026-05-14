from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import load_config
from src.services.runtime_paths import artifacts_root, state_db_path


def _apply_env_override(name: str, value: str | None) -> None:
    if value:
        os.environ[name] = value


def _display_path(path: Path) -> str:
    name = path.name.strip()
    if not name:
        return str(path)
    return f".../{name}"


def _as_record(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return value


def _as_page_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value != value:
            return None
        return max(0, int(round(value)))
    return None


def _resolve_claim_entries(payload: Any) -> list[dict[str, Any]]:
    root = _as_record(payload)
    if not root:
        return []
    direct_claims = root.get("claims")
    if isinstance(direct_claims, list):
        return [claim for claim in direct_claims if isinstance(claim, dict)]
    nested = _as_record(root.get("claimset"))
    if not nested:
        return []
    nested_claims = nested.get("claims")
    if not isinstance(nested_claims, list):
        return []
    return [claim for claim in nested_claims if isinstance(claim, dict)]


def _resolve_claim_page(claim: dict[str, Any]) -> int | None:
    evidence = claim.get("evidence_spans")
    if not isinstance(evidence, list) or not evidence:
        evidence = claim.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return None
    first = _as_record(evidence[0])
    if not first:
        return None
    page = _as_page_number(first.get("page"))
    if page is not None:
        return page
    return _as_page_number(first.get("page_index"))


def _claimset_has_distinct_pages(payload: Any) -> bool:
    claims = _resolve_claim_entries(payload)
    pages = [page for claim in claims if (page := _resolve_claim_page(claim)) is not None]
    if len(pages) < 2:
        return False
    has_zero_based_hint = any(page == 0 for page in pages)
    display_pages = [page + 1 if has_zero_based_hint else max(page, 1) for page in pages]
    first = display_pages[0]
    return any(page != first for page in display_pages[1:])


def _load_latest_claimset_payload(paper_artifact_dir: Path) -> Any | None:
    if not paper_artifact_dir.exists() or not paper_artifact_dir.is_dir():
        return None
    run_dirs = sorted((path for path in paper_artifact_dir.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime, reverse=True)
    for run_dir in run_dirs:
        for filename in ("claimset.resolved.json", "claimset.json"):
            target = run_dir / filename
            if not target.is_file():
                continue
            try:
                return json.loads(target.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
    return None


def _collect_real_smoke_candidates(db_path: Path, artifacts_dir: Path, limit: int = 5) -> list[dict[str, str]]:
    if not db_path.is_file():
        return []
    candidates: list[dict[str, str]] = []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT paper_id, pdf_path
            FROM papers
            WHERE paper_id IS NOT NULL
              AND paper_id NOT LIKE 'paper-e2e-%'
              AND pdf_path IS NOT NULL
            ORDER BY updated_at DESC, paper_id ASC
            LIMIT 200
            """
        ).fetchall()

    for paper_id, pdf_path in rows:
        if not isinstance(paper_id, str) or not paper_id.strip():
            continue
        pdf_file = Path(str(pdf_path)).expanduser()
        if not pdf_file.is_file():
            continue
        payload = _load_latest_claimset_payload(artifacts_dir / paper_id)
        if payload is None or not _claimset_has_distinct_pages(payload):
            continue
        candidates.append({"paper_id": paper_id, "pdf_path": str(pdf_file)})
        if len(candidates) >= limit:
            break
    return candidates


def run_preflight(require_candidates: bool) -> tuple[int, dict[str, Any]]:
    config_path = Path(os.getenv("PAPERPIPE_CONFIG_PATH", "config.yaml")).expanduser()
    summary: dict[str, Any] = {
        "config_path": _display_path(config_path),
        "obsidian_vault": None,
        "db_path": None,
        "artifacts_dir": None,
        "candidate_count": 0,
        "candidates": [],
        "errors": [],
    }

    if not config_path.is_file():
        summary["errors"].append(f"config_not_found:{config_path}")
        return 1, summary

    try:
        config = load_config(str(config_path))
    except Exception as exc:  # pragma: no cover - defensive path
        summary["errors"].append(f"config_load_failed:{exc}")
        return 1, summary

    vault_path = Path(config.paths.obsidian_vault).expanduser()
    summary["obsidian_vault"] = _display_path(vault_path)
    if not vault_path.exists():
        summary["errors"].append(f"vault_not_found:{vault_path}")
    elif not vault_path.is_dir():
        summary["errors"].append(f"vault_not_directory:{vault_path}")

    db_path = state_db_path()
    summary["db_path"] = _display_path(db_path)
    if not db_path.exists():
        summary["errors"].append(f"db_not_found:{db_path}")
    elif not db_path.is_file():
        summary["errors"].append(f"db_not_file:{db_path}")

    artifacts_dir = artifacts_root()
    summary["artifacts_dir"] = _display_path(artifacts_dir)
    if not artifacts_dir.exists():
        summary["errors"].append(f"artifacts_not_found:{artifacts_dir}")
    elif not artifacts_dir.is_dir():
        summary["errors"].append(f"artifacts_not_directory:{artifacts_dir}")

    if not summary["errors"]:
        candidates = _collect_real_smoke_candidates(db_path, artifacts_dir)
        for candidate in candidates:
            pdf_path = Path(candidate["pdf_path"]).expanduser()
            candidate["pdf_path"] = _display_path(pdf_path)
        summary["candidate_count"] = len(candidates)
        summary["candidates"] = candidates
        if require_candidates and not candidates:
            summary["errors"].append("no_real_smoke_candidates")

    return (0 if not summary["errors"] else 1), summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight validation for frontend real smoke E2E")
    parser.add_argument("--config", help="Override PAPERPIPE_CONFIG_PATH")
    parser.add_argument("--storage-dir", help="Override PAPERPIPE_STORAGE_DIR")
    parser.add_argument("--db-path", help="Override PAPERPIPE_DB_PATH")
    parser.add_argument("--artifacts-dir", help="Override PAPERPIPE_ARTIFACTS_DIR")
    parser.add_argument("--require-candidates", action="store_true", help="Fail when no real-paper smoke candidates are available")
    args = parser.parse_args()

    _apply_env_override("PAPERPIPE_CONFIG_PATH", args.config)
    _apply_env_override("PAPERPIPE_STORAGE_DIR", args.storage_dir)
    _apply_env_override("PAPERPIPE_DB_PATH", args.db_path)
    _apply_env_override("PAPERPIPE_ARTIFACTS_DIR", args.artifacts_dir)

    code, summary = run_preflight(require_candidates=args.require_candidates)
    print(json.dumps(summary, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
