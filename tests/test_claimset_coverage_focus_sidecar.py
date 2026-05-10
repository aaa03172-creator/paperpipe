from datetime import datetime, timezone

from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, ScientificClaim
from src.schemas.claimset_coverage import (
    ClaimsetCoverageEvidenceSummary,
    ClaimsetCoverageMetrics,
    ClaimsetCoveragePageSummary,
    ClaimsetCoverageSidecar,
    ClaimsetCoverageTopicSignal,
)
from src.services.claimset_coverage_focus_sidecar import (
    build_claimset_coverage_focus_sidecar,
    build_focus_targets,
    write_claimset_coverage_focus_sidecar,
)


def _coverage() -> ClaimsetCoverageSidecar:
    return ClaimsetCoverageSidecar(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        generated_at=datetime.now(timezone.utc),
        coverage_status="warn",
        metrics=ClaimsetCoverageMetrics(document_page_count=9, missing_topic_signal_count=1),
        page_summary=ClaimsetCoveragePageSummary(covered_pages=[2], missing_page_ranges=["4-9"]),
        topic_signals=[
            ClaimsetCoverageTopicSignal(
                key="ai_computational",
                label="AI and computational methods",
                keywords=["AI", "machine learning"],
                present_in_document=True,
                covered_by_claimset=False,
            )
        ],
        evidence_summary=ClaimsetCoverageEvidenceSummary(total_spans=2, grounded_spans=2, grounded_ratio=1.0),
        recommended_next_action="run_focused_coverage_review_for_missing_topics",
    )


def test_build_focus_targets_uses_missing_topics_and_page_ranges():
    targets = build_focus_targets(_coverage())

    assert len(targets) == 1
    assert targets[0].key == "ai_computational"
    assert targets[0].page_ranges == ["4-9"]


def test_build_claimset_coverage_focus_sidecar_records_candidate_metrics(tmp_path):
    candidate = ClaimSet(
        doc_id="doc-1",
        claims=[
            ScientificClaim(
                claim_id="CLM-COV-001",
                type="methods",
                statement="AI prioritizes candidates.",
                confidence=0.82,
                evidence_spans=[
                    EvidenceSpan(
                        page=3,
                        chunk_id="p04_c01",
                        raw_text="AI prioritizes candidates.",
                        quote="AI prioritizes candidates.",
                        rationale="Direct evidence.",
                        grounded=True,
                    )
                ],
            )
        ],
    )

    sidecar = build_claimset_coverage_focus_sidecar(
        paper_id="paper-1",
        run_id="run-1",
        coverage=_coverage(),
        candidate_claimset=candidate,
    )

    assert sidecar.canonical_status == "non_canonical"
    assert sidecar.focus_status == "generated"
    assert sidecar.metrics.target_count == 1
    assert sidecar.metrics.generated_claim_count == 1
    assert sidecar.metrics.grounded_span_count == 1
    assert sidecar.recommended_next_action == "review_focused_coverage_candidates_before_promotion"

    path = write_claimset_coverage_focus_sidecar(sidecar, tmp_path)
    assert path.name == "claimset_coverage_focus.json"
