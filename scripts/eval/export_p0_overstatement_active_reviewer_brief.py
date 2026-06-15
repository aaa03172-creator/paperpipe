#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.evidence_grounding_benchmark import (  # noqa: E402
    EvidenceGroundingP0OverstatementReviewClaimRow,
    EvidenceGroundingP0OverstatementReviewPacket,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402
from src.skills.storage import atomic_write_text  # noqa: E402


def _read_json_object(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_required: {path}")
    return payload


def _read_open_issue_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{str(key): str(value or "") for key, value in row.items()} for row in reader]
    if not reader.fieldnames:
        raise ValueError(f"open_issue_csv_missing_header: {path}")
    required = {
        "split",
        "paper_id",
        "run_id",
        "claim_id",
        "system_claim",
        "normalized_decision",
        "issue_codes",
    }
    missing = sorted(required.difference(reader.fieldnames))
    if missing:
        raise ValueError(f"open_issue_csv_missing_columns: {','.join(missing)}")
    return rows


def _require_existing_file(path: str, label: str) -> None:
    if not Path(path).is_file():
        raise ValueError(f"{label}_missing: {path}")


def _claim_key(*, split: str | None, paper_id: str, run_id: str | None, claim_id: str) -> tuple[str, str, str, str]:
    return (str(split or ""), str(paper_id), str(run_id or ""), str(claim_id))


def _packet_claim_index(
    packet: EvidenceGroundingP0OverstatementReviewPacket,
) -> dict[tuple[str, str, str, str], EvidenceGroundingP0OverstatementReviewClaimRow]:
    claims: dict[tuple[str, str, str, str], EvidenceGroundingP0OverstatementReviewClaimRow] = {}
    for paper in packet.papers:
        for claim in paper.system_claims:
            key = _claim_key(
                split=claim.split,
                paper_id=claim.paper_id,
                run_id=claim.run_id,
                claim_id=claim.claim_id,
            )
            claims[key] = claim
    return claims


def _split_list_cell(value: str) -> list[str]:
    return [part.strip() for part in value.replace("|", ";").split(";") if part.strip()]


def _compact(value: str, *, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)].rstrip()}..."


def _markdown_cell(value: str) -> str:
    return _compact(value).replace("|", "\\|")


def _format_issue_counts(issue_counts: dict[str, int]) -> str:
    if not issue_counts:
        return "-"
    return ", ".join(f"{key}: {issue_counts[key]}" for key in sorted(issue_counts))


def _count_open_rows_by_paper(open_rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in open_rows:
        paper_id = str(row.get("paper_id") or "").strip() or "-"
        counts[paper_id] = counts.get(paper_id, 0) + 1
    return dict(sorted(counts.items()))


def _packet_markdown_path(packet_path: str) -> str:
    return str(Path(packet_path).with_suffix(".md"))


def _evidence_snapshot(claim: EvidenceGroundingP0OverstatementReviewClaimRow) -> str:
    refs = []
    for ref in claim.system_evidence_refs:
        quote = _compact(ref.quote, limit=120)
        locator = _compact(ref.locator, limit=70)
        if quote and locator:
            refs.append(f"{locator}: {quote}")
        elif quote:
            refs.append(quote)
        elif locator:
            refs.append(locator)
    return " / ".join(refs)


def _gold_context_snapshot(claim: EvidenceGroundingP0OverstatementReviewClaimRow) -> str:
    snippets = []
    for statement in claim.gold_context[:3]:
        kind = statement.kind or statement.group
        text = _compact(statement.text, limit=130)
        evidence = _evidence_refs_snapshot(statement.evidence_refs, limit=110)
        if evidence:
            snippets.append(f"{kind}: {text} ({evidence})")
        else:
            snippets.append(f"{kind}: {text}")
    return " / ".join(snippets)


def _evidence_refs_snapshot(refs, *, limit: int) -> str:
    snippets = []
    for ref in refs[:2]:
        quote = _compact(ref.quote, limit=limit)
        locator = _compact(ref.locator, limit=70)
        if quote and locator:
            snippets.append(f"{locator}: {quote}")
        elif quote:
            snippets.append(quote)
        elif locator:
            snippets.append(locator)
    return "; ".join(snippets)


def render_p0_active_reviewer_brief(
    *,
    packet_path: str,
    reviewed_csv_path: str,
    open_issue_csv_path: str,
    summary_out_path: str,
    generated_date: str,
) -> str:
    _require_existing_file(packet_path, "packet")
    _require_existing_file(reviewed_csv_path, "reviewed_csv")
    _require_existing_file(open_issue_csv_path, "open_issue_csv")
    packet = EvidenceGroundingP0OverstatementReviewPacket.model_validate(
        _read_json_object(Path(packet_path))
    )
    open_rows = _read_open_issue_csv(Path(open_issue_csv_path))
    claim_index = _packet_claim_index(packet)
    missing_claim_keys: list[str] = []
    issue_counts: dict[str, int] = {}
    for row in open_rows:
        key = _claim_key(
            split=row.get("split"),
            paper_id=row.get("paper_id", ""),
            run_id=row.get("run_id"),
            claim_id=row.get("claim_id", ""),
        )
        if key not in claim_index:
            missing_claim_keys.append(":".join(key))
        for issue_code in _split_list_cell(row.get("issue_codes", "")):
            issue_counts[issue_code] = issue_counts.get(issue_code, 0) + 1
    if missing_claim_keys:
        raise ValueError(f"open_issue_rows_not_found_in_packet: {','.join(missing_claim_keys)}")
    open_rows_by_paper = _count_open_rows_by_paper(open_rows)

    rows = [
        "# P0 Overstatement Active Reviewer Brief",
        "",
        f"Generated: {generated_date}",
        "Layer: working handoff, non-canonical",
        "",
        (
            "This brief lists only the current P0 overstatement reviewer work. It does not "
            "provide reviewer decisions, approve labels, or replace the reviewed CSV."
        ),
        "",
        "## Current Status",
        "",
        f"- Packet: `{packet_path}`",
        f"- Packet Markdown with full gold context: `{_packet_markdown_path(packet_path)}`",
        f"- Reviewed CSV to edit: `{reviewed_csv_path}`",
        f"- Open-issue CSV: `{open_issue_csv_path}`",
        f"- Papers: `{packet.paper_count}`",
        f"- Claim review rows: `{packet.claim_review_row_count}`",
        f"- Open issue rows: `{len(open_rows)}`",
        f"- Open papers: `{len(open_rows_by_paper)}`",
        f"- Issue counts: `{_format_issue_counts(issue_counts)}`",
        "",
        "## Review Scope",
        "",
        "- Start with the packet Markdown full gold context before opening original papers.",
        "- Expected paper reading: `targeted`, only when packet evidence or gold context is insufficient or contradictory.",
        "- Reviewer decision remains human-owned; this brief only narrows the claims and evidence to inspect.",
        "",
        "## What To Fill",
        "",
        "- `reviewer_decision`: use `overstated`, `not_overstated`, or `uncertain`.",
        "- `uncertain` rows are excluded and keep the P0 overstatement metric not ready.",
        "",
        (
            "For each listed row, fill `reviewer_decision` and, when the decision contributes to "
            "the metric, `reviewer_rationale` in the reviewed CSV. Use the packet evidence and "
            "gold context for judgment."
        ),
        "",
        (
            "Do not fill by inference from this brief. The claim/evidence/gold text below is support "
            "material, not an approved decision."
        ),
    ]
    rows.extend(
        [
            "",
            "## Open Claims By Paper",
            "",
            "| Paper | Open claims |",
            "| --- | ---: |",
        ]
    )
    for paper_id, count in open_rows_by_paper.items():
        rows.append(f"| `{paper_id}` | `{count}` |")
    rows.extend(
        [
            "",
            "## Open Claim Details",
            "",
            "| Split | Paper | Claim | Issue | System claim | Evidence snapshot | Gold context snapshot |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in open_rows:
        key = _claim_key(
            split=row.get("split"),
            paper_id=row.get("paper_id", ""),
            run_id=row.get("run_id"),
            claim_id=row.get("claim_id", ""),
        )
        claim = claim_index[key]
        rows.append(
            "| "
            f"`{row.get('split', '') or '-'}` | "
            f"`{row.get('paper_id', '')}` | "
            f"`{row.get('claim_id', '')}` | "
            f"`{row.get('issue_codes', '')}` | "
            f"{_markdown_cell(claim.system_claim)} | "
            f"{_markdown_cell(_evidence_snapshot(claim))} | "
            f"{_markdown_cell(_gold_context_snapshot(claim))} |"
        )

    rows.extend(
        [
            "",
            "## Recheck Command",
            "",
            "Run this after reviewer decisions and rationales are entered:",
            "",
            "```bash",
            ".venv/bin/python scripts/eval/summarize_p0_overstatement_review_packet.py \\",
            f"  --packet {packet_path} \\",
            f"  --reviewed-csv {reviewed_csv_path} \\",
            f"  --out {summary_out_path} \\",
            f"  --open-issue-csv-out {open_issue_csv_path}",
            "```",
            "",
            "## Not In This Brief",
            "",
            "- This brief does not decide whether any claim is overstated.",
            "- This brief does not create OVERSTATED_RESULT labels.",
            "- Production threshold adoption still requires a separate approval reference.",
        ]
    )
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a compact non-canonical reviewer brief for open P0 overstatement "
            "decisions without filling reviewer-owned decisions."
        )
    )
    parser.add_argument("--packet", required=True, help="P0 overstatement review packet JSON.")
    parser.add_argument("--reviewed-csv", required=True, help="Reviewed CSV the reviewer should edit.")
    parser.add_argument("--open-issue-csv", required=True, help="Open-issue CSV from the summary CLI.")
    parser.add_argument("--summary-out", required=True, help="Summary JSON path to regenerate after review.")
    parser.add_argument("--out", required=True, help="Markdown brief output path.")
    parser.add_argument("--generated-date", default="2026-05-31", help="Date string to print in the brief.")
    args = parser.parse_args()

    try:
        markdown = render_p0_active_reviewer_brief(
            packet_path=args.packet,
            reviewed_csv_path=args.reviewed_csv,
            open_issue_csv_path=args.open_issue_csv,
            summary_out_path=args.summary_out,
            generated_date=args.generated_date,
        )
        atomic_write_text(Path(args.out).expanduser().resolve(), markdown)
    except Exception as exc:
        print(
            f"[p0_overstatement_active_reviewer_brief] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    print(
        "[p0_overstatement_active_reviewer_brief] "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
