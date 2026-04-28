from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.db_utils import get_db_connection
from src.exporter import run_export
from src.jobs.queue import JobQueue
from scripts.qa_report import (
    _expected_obsidian_relpath_for_candidate,
    _has_claimset_artifact,
    _has_valid_claimset,
    _is_test_fixture_record,
)


@dataclass(frozen=True)
class BackfillCandidate:
    paper_id: str
    title: str
    pdf_ready: bool
    markdown_missing: bool
    claimset_missing: bool


def _paper_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT paper_id, title, status, feedback_json, pdf_path, obsidian_path, updated_at
        FROM papers
        WHERE status IN ('APPROVED', 'INDEXED')
        ORDER BY updated_at ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _note_exists(vault_path: Path, row: dict[str, Any]) -> bool:
    rel_path = str(row.get("obsidian_path") or "").strip().replace("\\", "/")
    if not rel_path:
        rel_path = _expected_obsidian_relpath_for_candidate(row)
    target = vault_path / rel_path
    return target.exists()


def collect_backfill_candidates(
    rows: list[dict[str, Any]],
    *,
    vault_path: Path,
    include_test_fixtures: bool = False,
) -> list[BackfillCandidate]:
    candidates: list[BackfillCandidate] = []
    for row in rows:
        paper_id = str(row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        pdf_path = row.get("pdf_path")
        if not include_test_fixtures and _is_test_fixture_record(paper_id, pdf_path):
            continue

        feedback_json = row.get("feedback_json")
        pdf_path_raw = str(row.get("pdf_path") or "").strip()
        pdf_ready = bool(pdf_path_raw and Path(pdf_path_raw).expanduser().exists())
        markdown_missing = not _note_exists(vault_path, row)
        claimset_missing = (not _has_valid_claimset(feedback_json)) and (not _has_claimset_artifact(paper_id))
        if not markdown_missing and not claimset_missing:
            continue
        candidates.append(
            BackfillCandidate(
                paper_id=paper_id,
                title=str(row.get("title") or ""),
                pdf_ready=pdf_ready,
                markdown_missing=markdown_missing,
                claimset_missing=claimset_missing,
            )
        )
    return candidates


def _open_job_exists(conn: sqlite3.Connection, paper_id: str) -> bool:
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE paper_id = ? AND status IN ('queued', 'running')
            """,
            (paper_id,),
        ).fetchone()
        return bool(row and int(row[0]) > 0)
    except sqlite3.OperationalError:
        return False


def enqueue_claimset_backfill(
    conn: sqlite3.Connection,
    *,
    candidates: list[BackfillCandidate],
    limit: int,
    require_pdf_ready: bool = True,
    run_verify: bool = False,
    persona_id: str = "default",
) -> tuple[int, int, int]:
    queue = JobQueue()
    enqueued = 0
    skipped_open = 0
    skipped_pdf = 0
    for item in candidates:
        if not item.claimset_missing:
            continue
        if enqueued >= limit:
            break
        if require_pdf_ready and not item.pdf_ready:
            skipped_pdf += 1
            continue
        if _open_job_exists(conn, item.paper_id):
            skipped_open += 1
            continue
        queue.enqueue(item.paper_id, run_verify=run_verify, persona_id=persona_id)
        enqueued += 1
    return enqueued, skipped_open, skipped_pdf


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Operational backfill helper for missing Obsidian markdown and claimset outputs."
    )
    parser.add_argument("--apply", action="store_true", help="Apply actions. Default is dry-run.")
    parser.add_argument(
        "--export-missing",
        action="store_true",
        help="Run exporter (overwrite=False) to fill missing markdown files.",
    )
    parser.add_argument(
        "--enqueue-claimset",
        action="store_true",
        help="Enqueue DeepRead jobs for papers missing claimset.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Max jobs to enqueue for claimset backfill.")
    parser.add_argument("--run-verify", action="store_true", help="When enqueueing, enable verify stage.")
    parser.add_argument("--persona-id", default="default", help="Persona id for enqueued jobs.")
    parser.add_argument(
        "--allow-missing-pdf",
        action="store_true",
        help="Allow enqueue even when local pdf_path is missing/not found.",
    )
    parser.add_argument(
        "--include-test-fixtures",
        action="store_true",
        help="Include test fixtures(local--, *_test_...) in candidate scan.",
    )
    parser.add_argument("--print-sample", type=int, default=10, help="Number of sample candidates to print.")
    args = parser.parse_args()

    cfg = load_config()
    vault_path = Path(cfg.paths.obsidian_vault).expanduser()
    conn = get_db_connection()
    try:
        rows = _paper_rows(conn)
        candidates = collect_backfill_candidates(
            rows,
            vault_path=vault_path,
            include_test_fixtures=args.include_test_fixtures,
        )
        markdown_missing = sum(1 for item in candidates if item.markdown_missing)
        claimset_missing = sum(1 for item in candidates if item.claimset_missing)
        both_missing = sum(1 for item in candidates if item.markdown_missing and item.claimset_missing)
        claimset_with_pdf = sum(1 for item in candidates if item.claimset_missing and item.pdf_ready)
        claimset_without_pdf = sum(1 for item in candidates if item.claimset_missing and not item.pdf_ready)

        print(f"[BACKFILL] active_rows={len(rows)}")
        print(f"[BACKFILL] candidates_total={len(candidates)}")
        print(f"[BACKFILL] markdown_missing={markdown_missing}")
        print(f"[BACKFILL] claimset_missing={claimset_missing}")
        print(f"[BACKFILL] both_missing={both_missing}")
        print(f"[BACKFILL] claimset_missing_pdf_ready={claimset_with_pdf}")
        print(f"[BACKFILL] claimset_missing_pdf_missing={claimset_without_pdf}")
        for item in candidates[: max(0, args.print_sample)]:
            print(
                f"  - {item.paper_id} | md_missing={item.markdown_missing} "
                f"| claimset_missing={item.claimset_missing} "
                f"| pdf_ready={item.pdf_ready} | {item.title}"
            )

        if not args.apply:
            print("[BACKFILL] dry-run only (no changes applied)")
            return 0

        if args.export_missing:
            run_export(overwrite=False)
            print("[BACKFILL] exporter run complete (overwrite=False)")

        if args.enqueue_claimset:
            claimset_candidates = [item for item in candidates if item.claimset_missing]
            enqueued, skipped_open, skipped_pdf = enqueue_claimset_backfill(
                conn,
                candidates=claimset_candidates,
                limit=max(0, args.limit),
                require_pdf_ready=not args.allow_missing_pdf,
                run_verify=bool(args.run_verify),
                persona_id=args.persona_id,
            )
            print(f"[BACKFILL] claimset_jobs_enqueued={enqueued}")
            print(f"[BACKFILL] claimset_jobs_skipped_open={skipped_open}")
            print(f"[BACKFILL] claimset_jobs_skipped_pdf_missing={skipped_pdf}")

        if not args.export_missing and not args.enqueue_claimset:
            print("[BACKFILL] no action flags selected (--export-missing / --enqueue-claimset)")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
