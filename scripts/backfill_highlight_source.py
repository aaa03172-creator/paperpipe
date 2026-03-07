from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

VALID_HIGHLIGHT_SOURCES = {"bbox", "text_match", "approx"}


@dataclass(frozen=True)
class BackfillStats:
    files_scanned: int
    files_updated: int
    claims_scanned: int
    spans_scanned: int
    spans_updated: int


def infer_highlight_source(span: dict[str, Any]) -> str:
    bbox_pdf = span.get("bbox_pdf")
    if isinstance(bbox_pdf, list) and len(bbox_pdf) == 4:
        return "bbox"

    bbox_pct = span.get("bbox_pct")
    if isinstance(bbox_pct, dict):
        keys = set(bbox_pct.keys())
        if {"left", "top", "width", "height"}.issubset(keys):
            return "bbox"

    raw_text = str(span.get("raw_text") or "").strip()
    quote = str(span.get("quote") or "").strip()
    if raw_text or quote:
        return "text_match"
    return "approx"


def backfill_claimset_payload(payload: dict[str, Any]) -> tuple[bool, int, int]:
    claims = payload.get("claims")
    if not isinstance(claims, list):
        return False, 0, 0

    updated_spans = 0
    scanned_spans = 0
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        spans = claim.get("evidence_spans")
        if not isinstance(spans, list):
            continue
        for span in spans:
            if not isinstance(span, dict):
                continue
            scanned_spans += 1
            current = span.get("highlight_source")
            if current in VALID_HIGHLIGHT_SOURCES:
                continue
            span["highlight_source"] = infer_highlight_source(span)
            updated_spans += 1
    return updated_spans > 0, updated_spans, scanned_spans


def collect_claimset_files(
    artifacts_root: Path,
    *,
    include_legacy: bool,
    paper_ids: set[str] | None = None,
) -> Iterable[Path]:
    if not artifacts_root.exists():
        return []

    candidates: list[Path] = []
    for paper_dir in sorted(artifacts_root.iterdir()):
        if not paper_dir.is_dir():
            continue
        if paper_ids and paper_dir.name not in paper_ids:
            continue
        for run_dir in sorted(paper_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            resolved = run_dir / "claimset.resolved.json"
            legacy = run_dir / "claimset.json"
            if resolved.exists():
                candidates.append(resolved)
                if include_legacy and legacy.exists():
                    candidates.append(legacy)
                continue
            if legacy.exists():
                candidates.append(legacy)
    return candidates


def run_backfill(
    artifacts_root: Path,
    *,
    apply_changes: bool,
    include_legacy: bool,
    paper_ids: set[str] | None = None,
) -> BackfillStats:
    files_scanned = 0
    files_updated = 0
    claims_scanned = 0
    spans_scanned = 0
    spans_updated = 0

    for file_path in collect_claimset_files(artifacts_root, include_legacy=include_legacy, paper_ids=paper_ids):
        files_scanned += 1
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[SKIP] invalid JSON: {file_path}")
            continue

        claims = payload.get("claims")
        if isinstance(claims, list):
            claims_scanned += len([claim for claim in claims if isinstance(claim, dict)])

        changed, file_updated_spans, file_scanned_spans = backfill_claimset_payload(payload)
        spans_scanned += file_scanned_spans
        spans_updated += file_updated_spans

        if changed:
            files_updated += 1
            print(f"[UPDATE] {file_path} spans_updated={file_updated_spans}")
            if apply_changes:
                file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return BackfillStats(
        files_scanned=files_scanned,
        files_updated=files_updated,
        claims_scanned=claims_scanned,
        spans_scanned=spans_scanned,
        spans_updated=spans_updated,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill missing highlight_source in claimset artifacts.")
    parser.add_argument(
        "--artifacts-root",
        default="storage/artifacts",
        help="Root directory containing paper/run artifacts (default: storage/artifacts).",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to disk. Default is dry-run.")
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="If claimset.resolved.json exists, also patch claimset.json in the same run directory.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Optional paper_id filter. Can be passed multiple times.",
    )
    args = parser.parse_args()

    artifacts_root = Path(args.artifacts_root).expanduser()
    paper_ids = {item.strip() for item in args.paper_id if item.strip()} or None
    stats = run_backfill(
        artifacts_root,
        apply_changes=bool(args.apply),
        include_legacy=bool(args.include_legacy),
        paper_ids=paper_ids,
    )

    print(f"[SUMMARY] files_scanned={stats.files_scanned}")
    print(f"[SUMMARY] files_updated={stats.files_updated}")
    print(f"[SUMMARY] claims_scanned={stats.claims_scanned}")
    print(f"[SUMMARY] spans_scanned={stats.spans_scanned}")
    print(f"[SUMMARY] spans_updated={stats.spans_updated}")
    if not args.apply:
        print("[SUMMARY] dry-run complete (no files written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
