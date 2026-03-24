from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from src.schemas.agent_artifacts import ClaimSet
from src.schemas.teacher_review_eval import (
    TeacherReviewEvalClaimEntry,
    TeacherReviewEvalMetrics,
    TeacherReviewEvalSidecar,
)


def load_teacher_review_rows(review_jsonl_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in review_jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def build_teacher_review_eval_sidecar(
    *,
    bundle_dir: Path,
    review_rows: list[dict[str, Any]],
    review_jsonl_path: Path | None = None,
    review_source: str | None = None,
) -> TeacherReviewEvalSidecar:
    bundle_dir = bundle_dir.expanduser().resolve()
    manifest = _load_json(bundle_dir / "manifest.json")
    teacher_output = ClaimSet.model_validate(_load_json(bundle_dir / "teacher_output.json"))
    meta_path = bundle_dir / "teacher_output.meta.json"
    meta = _load_json(meta_path) if meta_path.exists() else {}

    paper_id = str(meta.get("paper_id") or manifest.get("paper_id") or "").strip()
    bundle_rows = _filter_bundle_rows(review_rows, bundle_dir=bundle_dir, paper_id=paper_id)
    rows_by_claim: dict[str, dict[str, Any]] = {}
    duplicate_review_row_count = 0
    for claim_id, claim_rows in _group_rows_by_claim(bundle_rows).items():
        rows_by_claim[claim_id] = claim_rows[-1]
        duplicate_review_row_count += max(0, len(claim_rows) - 1)

    claim_ids = {claim.claim_id for claim in teacher_output.claims}
    extra_review_count = sum(1 for claim_id in rows_by_claim if claim_id not in claim_ids)

    entries: list[TeacherReviewEvalClaimEntry] = []
    for claim in teacher_output.claims:
        row = rows_by_claim.get(claim.claim_id)
        entries.append(
            TeacherReviewEvalClaimEntry(
                claim_id=claim.claim_id,
                statement=claim.statement,
                reviewed=row is not None,
                anchor_quality_label=_classify_anchor_quality(row),
                support_label=_clean_str(row, "support_label"),
                location_label=_clean_str(row, "location_label"),
                keep_teacher_claim=_clean_bool(row, "keep_teacher_claim"),
                source_page=_clean_int(row, "source_page"),
                source_chunk_id=_clean_str(row, "source_chunk_id"),
                bundle_outcome=_clean_str(row, "bundle_outcome"),
                issue_pattern=_clean_str(row, "issue_pattern"),
                reviewer=_clean_str(row, "reviewer"),
                notes=_clean_str(row, "notes"),
            )
        )

    reviewed_entries = [entry for entry in entries if entry.reviewed]
    supported_claim_count = sum(entry.support_label == "SUPPORTED" for entry in reviewed_entries)
    unsupported_claim_count = sum(entry.support_label == "UNSUPPORTED" for entry in reviewed_entries)
    ambiguous_claim_count = sum(entry.support_label == "AMBIGUOUS" for entry in reviewed_entries)
    precision_denominator = supported_claim_count + unsupported_claim_count
    precision = round(supported_claim_count / precision_denominator, 4) if precision_denominator else 0.0

    metrics = TeacherReviewEvalMetrics(
        claim_count=len(entries),
        reviewed_claim_count=len(reviewed_entries),
        missing_review_count=sum(not entry.reviewed for entry in entries),
        extra_review_count=extra_review_count,
        duplicate_review_row_count=duplicate_review_row_count,
        direct_quote_support_count=sum(entry.anchor_quality_label == "DIRECT_QUOTE_SUPPORT" for entry in reviewed_entries),
        adjacent_support_count=sum(entry.anchor_quality_label == "ADJACENT_SUPPORT" for entry in reviewed_entries),
        heading_level_support_count=sum(entry.anchor_quality_label == "HEADING_LEVEL_SUPPORT" for entry in reviewed_entries),
        misaligned_quote_count=sum(entry.anchor_quality_label == "MISALIGNED_QUOTE" for entry in reviewed_entries),
        fragmentary_claim_count=sum(entry.anchor_quality_label == "FRAGMENTARY_CLAIM" for entry in reviewed_entries),
        supported_claim_count=supported_claim_count,
        unsupported_claim_count=unsupported_claim_count,
        ambiguous_claim_count=ambiguous_claim_count,
        good_location_count=sum(entry.location_label == "GOOD" for entry in reviewed_entries),
        weak_location_count=sum(entry.location_label == "WEAK" for entry in reviewed_entries),
        misleading_location_count=sum(entry.location_label == "MISLEADING" for entry in reviewed_entries),
        keep_teacher_claim_count=sum(entry.keep_teacher_claim is True for entry in reviewed_entries),
        drop_teacher_claim_count=sum(entry.keep_teacher_claim is False for entry in reviewed_entries),
        supported_claim_precision=precision,
    )
    bundle_outcome = _single_or_mixed([entry.bundle_outcome for entry in reviewed_entries if entry.bundle_outcome])
    issue_patterns = sorted({entry.issue_pattern for entry in reviewed_entries if entry.issue_pattern})
    reviewers = sorted({entry.reviewer for entry in reviewed_entries if entry.reviewer})
    resolved_review_source = review_source or (reviewers[0] if len(reviewers) == 1 else "mixed")

    return TeacherReviewEvalSidecar(
        generated_at=datetime.now(timezone.utc),
        paper_id=paper_id,
        doc_id=teacher_output.doc_id,
        bundle_dir=str(bundle_dir),
        review_source=resolved_review_source,
        review_jsonl_path=str(review_jsonl_path) if review_jsonl_path is not None else None,
        bundle_outcome=bundle_outcome,
        issue_patterns=issue_patterns,
        metrics=metrics,
        claims=entries,
    )


def write_teacher_review_eval_sidecar(sidecar: TeacherReviewEvalSidecar, bundle_dir: Path) -> Path:
    bundle_dir = bundle_dir.expanduser().resolve()
    path = bundle_dir / "teacher_review_eval.json"
    path.write_text(sidecar.model_dump_json(indent=2), encoding="utf-8")
    return path


def _filter_bundle_rows(review_rows: list[dict[str, Any]], *, bundle_dir: Path, paper_id: str) -> list[dict[str, Any]]:
    resolved_bundle = str(bundle_dir)
    rows: list[dict[str, Any]] = []
    for row in review_rows:
        row_bundle_dir = str(row.get("bundle_dir") or "").strip()
        row_paper_id = str(row.get("paper_id") or "").strip()
        if row_bundle_dir and row_bundle_dir == resolved_bundle:
            rows.append(row)
        elif paper_id and row_paper_id == paper_id:
            rows.append(row)
    return rows


def _group_rows_by_claim(review_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in review_rows:
        claim_id = str(row.get("claim_id") or "").strip()
        if claim_id:
            grouped[claim_id].append(row)
    return grouped


def _single_or_mixed(values: list[str]) -> str | None:
    if not values:
        return None
    counts = Counter(values)
    if len(counts) == 1:
        return values[0]
    return "MIXED"


def _classify_anchor_quality(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    issue_pattern = str(row.get("issue_pattern") or "").strip()
    support_label = str(row.get("support_label") or "").strip()
    location_label = str(row.get("location_label") or "").strip()

    if "fragmentary" in issue_pattern:
        return "FRAGMENTARY_CLAIM"
    if "heading-level" in issue_pattern:
        return "HEADING_LEVEL_SUPPORT"
    if "adjacent-quote" in issue_pattern:
        return "ADJACENT_SUPPORT"
    if "wrong-anchor" in issue_pattern:
        return "MISALIGNED_QUOTE"
    if location_label == "MISLEADING":
        return "MISALIGNED_QUOTE"
    if support_label == "SUPPORTED" and location_label == "GOOD":
        return "DIRECT_QUOTE_SUPPORT"
    if support_label == "SUPPORTED" and location_label == "WEAK":
        return "ADJACENT_SUPPORT"
    if support_label == "AMBIGUOUS" and location_label == "WEAK":
        return "HEADING_LEVEL_SUPPORT"
    return None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_str(row: dict[str, Any] | None, key: str) -> str | None:
    if not row:
        return None
    value = str(row.get(key) or "").strip()
    return value or None


def _clean_bool(row: dict[str, Any] | None, key: str) -> bool | None:
    if not row or key not in row:
        return None
    value = row.get(key)
    if isinstance(value, bool):
        return value
    return None


def _clean_int(row: dict[str, Any] | None, key: str) -> int | None:
    if not row:
        return None
    value = row.get(key)
    if isinstance(value, int):
        return value
    return None
