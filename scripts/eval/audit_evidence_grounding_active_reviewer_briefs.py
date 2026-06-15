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

from src.services.path_masking import mask_local_paths_in_text  # noqa: E402
from src.skills.storage import atomic_write_text  # noqa: E402


def _read_json_object(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_required: {path}")
    return payload


def _read_csv_rows(path: Path, *, required_columns: set[str], label: str) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{str(key): str(value or "") for key, value in row.items()} for row in reader]
    if not reader.fieldnames:
        raise ValueError(f"{label}_missing_header: {path}")
    missing = sorted(required_columns.difference(reader.fieldnames))
    if missing:
        raise ValueError(f"{label}_missing_columns: {','.join(missing)}")
    return rows


def _check_contains(markdown: str, needle: str, check_id: str, detail: str) -> dict:
    return {
        "check_id": check_id,
        "passed": needle in markdown,
        "detail": detail if needle in markdown else f"{detail}; missing `{needle}`",
    }


def _split_issue_codes(value: str) -> list[str]:
    return [part.strip() for part in value.replace("|", ";").split(";") if part.strip()]


def _compact_markdown_needle(value: str, *, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        text = text[:limit].rstrip()
    return text.replace("|", "\\|")


def _audit_structured_brief(
    *,
    brief_path: str,
    fill_review_status_path: str,
    open_records_csv_path: str,
) -> tuple[list[dict], dict[str, int]]:
    markdown = Path(brief_path).read_text(encoding="utf-8")
    status = _read_json_object(Path(fill_review_status_path))
    open_records = _read_csv_rows(
        Path(open_records_csv_path),
        required_columns={"record_ref", "open_field_names"},
        label="structured_open_records_csv",
    )
    open_record_count = int(status.get("open_record_count", -1))
    open_csv_row_count = int(status.get("open_csv_row_count", -1))
    missing_value_count = int(status.get("missing_value_count", -1))
    checks = [
        _check_contains(
            markdown,
            f"- Open records: `{open_record_count}`",
            "structured_open_record_count_listed",
            "structured brief lists current open record count",
        ),
        _check_contains(
            markdown,
            f"- Open cells: `{open_csv_row_count}`",
            "structured_open_cell_count_listed",
            "structured brief lists current open cell count",
        ),
        _check_contains(
            markdown,
            f"- Missing reviewer values: `{missing_value_count}`",
            "structured_missing_value_count_listed",
            "structured brief lists current missing reviewer value count",
        ),
        _check_contains(
            markdown,
            "- Expected paper reading: `no`, unless the context packet is insufficient or contradictory.",
            "structured_review_scope_no_paper_reading_listed",
            "structured brief explains that current metadata review should not require paper reading",
        ),
    ]
    for row in open_records:
        record_ref = row["record_ref"].strip()
        checks.append(
            _check_contains(
                markdown,
                f"`{record_ref}`",
                f"structured_record_ref_listed:{record_ref}",
                "structured brief lists open record ref",
            )
        )
        context_hint = str(
            row.get("reviewer_evidence_hint") or row.get("available_context_values") or ""
        ).strip()
        if context_hint:
            checks.append(
                _check_contains(
                    markdown,
                    _compact_markdown_needle(context_hint),
                    f"structured_context_preview_listed:{record_ref}",
                    "structured brief lists context/evidence preview",
                )
            )
    counts = {
        "structured_open_record_count": open_record_count,
        "structured_open_csv_row_count": open_csv_row_count,
        "structured_missing_value_count": missing_value_count,
    }
    return checks, counts


def _audit_p0_brief(
    *,
    brief_path: str,
    open_issue_csv_path: str,
) -> tuple[list[dict], dict[str, int]]:
    markdown = Path(brief_path).read_text(encoding="utf-8")
    open_rows = _read_csv_rows(
        Path(open_issue_csv_path),
        required_columns={"paper_id", "claim_id", "issue_codes"},
        label="p0_open_issue_csv",
    )
    issue_counts: dict[str, int] = {}
    paper_ids = {row["paper_id"].strip() for row in open_rows if row["paper_id"].strip()}
    for row in open_rows:
        for issue_code in _split_issue_codes(row.get("issue_codes", "")):
            issue_counts[issue_code] = issue_counts.get(issue_code, 0) + 1
    checks = [
        _check_contains(
            markdown,
            f"- Open issue rows: `{len(open_rows)}`",
            "p0_open_issue_row_count_listed",
            "P0 brief lists current open issue row count",
        ),
        _check_contains(
            markdown,
            f"- Open papers: `{len(paper_ids)}`",
            "p0_open_paper_count_listed",
            "P0 brief lists current open paper count",
        ),
        _check_contains(
            markdown,
            "- Expected paper reading: `targeted`, only when packet evidence or gold context is insufficient or contradictory.",
            "p0_review_scope_targeted_reading_listed",
            "P0 brief explains targeted paper-reading scope",
        ),
    ]
    for issue_code, count in sorted(issue_counts.items()):
        checks.append(
            _check_contains(
                markdown,
                f"{issue_code}: {count}",
                f"p0_issue_count_listed:{issue_code}",
                "P0 brief lists current issue-code count",
            )
        )
    for row in open_rows:
        paper_id = row["paper_id"].strip()
        claim_id = row["claim_id"].strip()
        checks.extend(
            [
                _check_contains(
                    markdown,
                    f"`{paper_id}`",
                    f"p0_paper_id_listed:{paper_id}:{claim_id}",
                    "P0 brief lists open paper id",
                ),
                _check_contains(
                    markdown,
                    f"`{claim_id}`",
                    f"p0_claim_id_listed:{paper_id}:{claim_id}",
                    "P0 brief lists open claim id",
                ),
            ]
        )
    counts = {
        "p0_open_issue_row_count": len(open_rows),
        "p0_open_paper_count": len(paper_ids),
    }
    counts.update({f"p0_issue_count:{issue_code}": count for issue_code, count in issue_counts.items()})
    return checks, counts


def build_active_reviewer_brief_audit(
    *,
    structured_brief: str,
    structured_fill_review_status: str,
    structured_open_records_csv: str,
    p0_brief: str,
    p0_open_issue_csv: str,
) -> dict:
    checks: list[dict] = []
    counts: dict[str, int] = {}
    structured_checks, structured_counts = _audit_structured_brief(
        brief_path=structured_brief,
        fill_review_status_path=structured_fill_review_status,
        open_records_csv_path=structured_open_records_csv,
    )
    p0_checks, p0_counts = _audit_p0_brief(
        brief_path=p0_brief,
        open_issue_csv_path=p0_open_issue_csv,
    )
    checks.extend(structured_checks)
    checks.extend(p0_checks)
    counts.update(structured_counts)
    counts.update(p0_counts)
    fail_count = sum(1 for check in checks if not check["passed"])
    pass_count = len(checks) - fail_count
    return {
        "schema_version": "evidence_grounding_active_reviewer_brief_audit.v1",
        "layer": "review_gate_artifact",
        "canonical_status": "non_canonical",
        "all_passed": fail_count == 0,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "counts": counts,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit active reviewer briefs against their source status/open CSV artifacts. "
            "This verifies handoff freshness only; it does not create reviewer values."
        )
    )
    parser.add_argument("--structured-brief", required=True)
    parser.add_argument("--structured-fill-review-status", required=True)
    parser.add_argument("--structured-open-records-csv", required=True)
    parser.add_argument("--p0-brief", required=True)
    parser.add_argument("--p0-open-issue-csv", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    try:
        report = build_active_reviewer_brief_audit(
            structured_brief=args.structured_brief,
            structured_fill_review_status=args.structured_fill_review_status,
            structured_open_records_csv=args.structured_open_records_csv,
            p0_brief=args.p0_brief,
            p0_open_issue_csv=args.p0_open_issue_csv,
        )
        atomic_write_text(Path(args.out).expanduser().resolve(), json.dumps(report, indent=2) + "\n")
    except Exception as exc:
        print(
            f"[active_reviewer_brief_audit] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    print(
        "[active_reviewer_brief_audit] "
        f"all_passed={str(report['all_passed']).lower()} "
        f"pass_count={report['pass_count']} fail_count={report['fail_count']} "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
