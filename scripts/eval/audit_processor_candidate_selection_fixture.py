#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime as RealDateTime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.processor as processor


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fixed_datetime_class(fixed_now: str):
    fixed_dt = RealDateTime.fromisoformat(fixed_now)

    class FixedDateTime:
        @classmethod
        def now(cls):
            return fixed_dt

        @classmethod
        def strptime(cls, value, fmt):
            return RealDateTime.strptime(value, fmt)

        @classmethod
        def fromisoformat(cls, value):
            return RealDateTime.fromisoformat(value)

    return FixedDateTime


def _config() -> SimpleNamespace:
    return SimpleNamespace(ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)))


def _paper_from_fixture(payload: dict[str, Any]) -> SimpleNamespace:
    paper = SimpleNamespace(
        id=str(payload.get("id") or ""),
        doi=payload.get("doi") if isinstance(payload.get("doi"), str) else None,
        title=str(payload.get("title") or payload.get("id") or ""),
        authors=list(payload.get("authors") or ["fixture"]),
        published=str(payload.get("published") or ""),
        source=str(payload.get("source") or ""),
        summary=str(payload.get("summary") or "Fixture-backed candidate selection benchmark."),
        link=str(payload.get("link") or ""),
        local_pdf_path=payload.get("local_pdf_path") if isinstance(payload.get("local_pdf_path"), str) else None,
        pdf_link=payload.get("pdf_link") if isinstance(payload.get("pdf_link"), str) else None,
        download_attempts=[],
    )
    if isinstance(payload.get("manual_rank_score"), (int, float)):
        paper.manual_rank_score = float(payload["manual_rank_score"])
    return paper


def _candidate_preview(slot: str, paper: Any, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "paper_id": str(getattr(paper, "id", "") or ""),
        "title": str(getattr(paper, "title", "") or ""),
        "source": str(getattr(paper, "source", "") or ""),
        "published": str(getattr(paper, "published", "") or ""),
        "score_breakdown": processor._candidate_selection_breakdown(slot, paper),
    }


def _build_markdown(summary: dict[str, Any], details: dict[str, Any]) -> str:
    metrics = summary["metrics"]
    lines = [
        "# Processor Candidate Selection Fixture Audit",
        "",
        f"Run ID: `{summary['run_id']}`",
        f"Fixture: `{summary['inputs']['fixture_path']}`",
        "",
        "## Metrics",
        "",
        f"- Pool count: `{metrics['pool_count']}`",
        f"- Matched count: `{metrics['matched_count']}`",
        f"- Mismatch count: `{metrics['mismatch_count']}`",
        f"- Accuracy: `{metrics['accuracy']}`",
        "",
        "## Pools",
        "",
    ]
    for pool in details["pools"]:
        status = "PASS" if pool["matches_expected"] else "FAIL"
        lines.extend(
            [
                f"### {pool['pool_id']}",
                "",
                f"- Status: `{status}`",
                f"- Slot: `{pool['slot']}`",
                f"- Expected Top1: `{pool['expected_top1']}`",
                f"- Observed Top1: `{pool['observed_top1']}`",
                f"- Rationale: {pool['rationale']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def run_audit(*, fixture_path: Path, out_dir: Path, run_id: str) -> Path:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixed_now = str(fixture.get("fixed_now") or RealDateTime.now().date().isoformat())
    run_root = out_dir / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    original_datetime = processor.datetime
    processor.datetime = _fixed_datetime_class(fixed_now)
    try:
        pool_details: list[dict[str, Any]] = []
        for pool in fixture.get("pools", []):
            slot = str(pool.get("slot") or "")
            candidates = [_paper_from_fixture(candidate) for candidate in pool.get("candidates", [])]
            ranked = processor._rank_slot_candidates(slot, candidates, _config())
            observed_top1 = str(getattr(ranked[0], "id", "") or "") if ranked else None
            expected_top1 = str(pool.get("expected_top1") or "")
            pool_details.append(
                {
                    "pool_id": str(pool.get("id") or ""),
                    "slot": slot,
                    "expected_top1": expected_top1,
                    "observed_top1": observed_top1,
                    "matches_expected": observed_top1 == expected_top1,
                    "rationale": str(pool.get("rationale") or ""),
                    "candidate_count": len(candidates),
                    "top_candidates": [
                        _candidate_preview(slot, candidate, rank)
                        for rank, candidate in enumerate(ranked[:3], start=1)
                    ],
                }
            )
    finally:
        processor.datetime = original_datetime

    pool_count = len(pool_details)
    matched_count = sum(1 for pool in pool_details if pool["matches_expected"])
    mismatch_count = pool_count - matched_count
    summary = {
        "schema_version": "processor_candidate_selection_fixture_audit.v1",
        "generated_at": RealDateTime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_id": run_id,
        "inputs": {
            "fixture_path": str(fixture_path),
            "schema_version": fixture.get("schema_version"),
            "fixed_now": fixed_now,
        },
        "metrics": {
            "pool_count": pool_count,
            "matched_count": matched_count,
            "mismatch_count": mismatch_count,
            "accuracy": round(matched_count / pool_count, 4) if pool_count else 0.0,
        },
        "pools_with_mismatch": [
            pool["pool_id"] for pool in pool_details if not pool["matches_expected"]
        ],
    }
    details = {
        "schema_version": "processor_candidate_selection_fixture_audit_details.v1",
        "run_id": run_id,
        "pools": pool_details,
    }
    _write_json(run_root / "summary.json", summary)
    _write_json(run_root / "details.json", details)
    (run_root / "audit.md").write_text(_build_markdown(summary, details), encoding="utf-8")
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit fixture-backed processor candidate selection expected-Top1 pools."
    )
    parser.add_argument(
        "--fixture",
        default=str(ROOT / "tests" / "fixtures" / "processor_candidate_selection_pools_20260429.json"),
        help="Candidate-pool fixture JSON path.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "processor_candidate_selection_fixture_audits"),
        help="Output directory for audit artifacts.",
    )
    parser.add_argument("--run-id", required=True, help="Audit run identifier.")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    run_root = run_audit(
        fixture_path=Path(args.fixture).expanduser(),
        out_dir=Path(args.out_dir).expanduser(),
        run_id=args.run_id,
    )
    payload = {
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "details_path": str(run_root / "details.json"),
        "markdown_path": str(run_root / "audit.md"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
