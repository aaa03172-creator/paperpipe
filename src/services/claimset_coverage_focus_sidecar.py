from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.schemas.agent_artifacts import ClaimSet
from src.schemas.claimset_coverage import ClaimsetCoverageSidecar
from src.schemas.claimset_coverage_focus import (
    ClaimsetCoverageFocusMetrics,
    ClaimsetCoverageFocusSidecar,
    ClaimsetCoverageFocusStatus,
    ClaimsetCoverageFocusTarget,
)
from src.skills.storage import atomic_write_text


def build_focus_targets(coverage: ClaimsetCoverageSidecar) -> list[ClaimsetCoverageFocusTarget]:
    page_ranges = list(coverage.page_summary.missing_page_ranges or coverage.page_summary.undercovered_page_ranges)
    targets = [
        ClaimsetCoverageFocusTarget(
            key=signal.key,
            label=signal.label,
            keywords=list(signal.keywords),
            page_ranges=page_ranges,
        )
        for signal in coverage.topic_signals
        if signal.present_in_document and not signal.covered_by_claimset
    ]
    if not targets and page_ranges:
        targets.append(
            ClaimsetCoverageFocusTarget(
                key="undercovered_pages",
                label="Undercovered pages",
                keywords=[],
                page_ranges=page_ranges,
            )
        )
    return targets


def build_claimset_coverage_focus_sidecar(
    *,
    paper_id: str,
    run_id: str,
    coverage: ClaimsetCoverageSidecar,
    candidate_claimset: ClaimSet | None = None,
    focus_status: ClaimsetCoverageFocusStatus = "generated",
    reason: str | None = None,
) -> ClaimsetCoverageFocusSidecar:
    candidates = candidate_claimset or ClaimSet(doc_id=coverage.doc_id, claims=[])
    evidence_span_count = sum(len(claim.evidence_spans) for claim in candidates.claims)
    grounded_span_count = sum(
        1 for claim in candidates.claims for span in claim.evidence_spans if span.grounded is True
    )
    unresolved_span_count = sum(
        1 for claim in candidates.claims for span in claim.evidence_spans if span.grounded is False
    )
    targets = build_focus_targets(coverage)
    return ClaimsetCoverageFocusSidecar(
        paper_id=paper_id,
        doc_id=coverage.doc_id,
        run_id=run_id,
        source_artifacts=[
            "document_artifact.json",
            "index_artifact.json",
            "claimset.resolved.json",
            "claimset_coverage.json",
        ],
        generated_at=datetime.now(timezone.utc),
        focus_status=focus_status,
        reason=reason,
        targets=targets,
        metrics=ClaimsetCoverageFocusMetrics(
            target_count=len(targets),
            generated_claim_count=len(candidates.claims),
            evidence_span_count=evidence_span_count,
            grounded_span_count=grounded_span_count,
            unresolved_span_count=unresolved_span_count,
        ),
        candidate_claimset=candidates,
        recommended_next_action=_recommended_next_action(focus_status, len(candidates.claims)),
    )


def write_claimset_coverage_focus_sidecar(sidecar: ClaimsetCoverageFocusSidecar, artifact_dir: Path) -> Path:
    path = artifact_dir / "claimset_coverage_focus.json"
    atomic_write_text(path, sidecar.model_dump_json(indent=2))
    return path


def _recommended_next_action(status: ClaimsetCoverageFocusStatus, claim_count: int) -> str:
    if status == "generated" and claim_count > 0:
        return "review_focused_coverage_candidates_before_promotion"
    if status == "generated":
        return "manual_review_missing_coverage_topics"
    if status == "skipped":
        return "none"
    return "inspect_focused_coverage_pass_error"
