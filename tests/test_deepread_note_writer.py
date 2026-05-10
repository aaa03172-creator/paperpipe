from datetime import datetime, timezone

from src.schemas.agent_artifacts import (
    ClaimSet,
    ScientificClaim,
    EvidenceSpan,
    StatsReport,
    StatCheckEntry,
    VerificationStatus,
)
from src.schemas.core import BiomedicalClinicalExtraction
from src.schemas.claimset_coverage import (
    ClaimsetCoverageDuplicateWarning,
    ClaimsetCoverageEvidenceSummary,
    ClaimsetCoverageMetrics,
    ClaimsetCoveragePageSummary,
    ClaimsetCoverageSidecar,
    ClaimsetCoverageTopicSignal,
)
from src.services.deepread_note_writer import (
    DEEPREAD_HEADER,
    _format_evidence_text_for_display,
    build_clinical_extraction_markdown,
    build_deepread_markdown,
    build_stats_markdown,
    upsert_deepread_section,
)


def test_build_deepread_markdown_renders_claims():
    claimset = ClaimSet(
        doc_id="doc1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Drug A improved outcome.",
                confidence=0.91,
                evidence_spans=[EvidenceSpan(raw_text="Result section evidence", page=2)],
            )
        ],
    )
    md = build_deepread_markdown("llama3:latest", claimset)
    assert md.startswith(DEEPREAD_HEADER)
    assert "Analyzed via llama3:latest" in md
    assert "Drug A improved outcome." in md
    assert "Result section evidence" in md


def test_build_deepread_markdown_renders_coverage_warning_for_warn_or_fail():
    claimset = ClaimSet(
        doc_id="doc1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="mechanism",
                statement="Claims are clustered.",
                confidence=0.91,
            )
        ],
    )
    coverage = ClaimsetCoverageSidecar(
        paper_id="paper-1",
        doc_id="doc1",
        run_id="run-1",
        source_artifacts=["claimset.resolved.json"],
        generated_at=datetime.now(timezone.utc),
        coverage_status="warn",
        metrics=ClaimsetCoverageMetrics(document_page_count=9),
        page_summary=ClaimsetCoveragePageSummary(covered_pages=[2], missing_page_ranges=["1", "3-9"]),
        topic_signals=[
            ClaimsetCoverageTopicSignal(
                key="ai_computational",
                label="AI and computational methods",
                present_in_document=True,
                covered_by_claimset=False,
            )
        ],
        duplicate_warnings=[
            ClaimsetCoverageDuplicateWarning(
                claim_ids=["c1", "c2"],
                similarity=0.8,
                reason="claim_statements_have_high_token_overlap",
            )
        ],
        evidence_summary=ClaimsetCoverageEvidenceSummary(total_spans=3, grounded_spans=3, grounded_ratio=1.0),
        recommended_next_action="run_focused_coverage_review_for_missing_topics",
        reason_codes=["low_page_coverage"],
    )

    md = build_deepread_markdown("llama3:latest", claimset, coverage=coverage)

    assert "### Coverage Review" in md
    assert "- **Status**: WARN" in md
    assert "- **Gate**: Advisory only" in md
    assert "- **Covered Pages**: 2 of 9" in md
    assert "- **Undercovered Page Ranges**: 1, 3-9" in md
    assert "AI and computational methods" in md
    assert "run focused coverage review for missing topics" in md


def test_build_deepread_markdown_omits_coverage_block_for_pass():
    claimset = ClaimSet(
        doc_id="doc1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="mechanism",
                statement="Claims are distributed.",
                confidence=0.91,
            )
        ],
    )
    coverage = ClaimsetCoverageSidecar(
        paper_id="paper-1",
        doc_id="doc1",
        run_id="run-1",
        generated_at=datetime.now(timezone.utc),
        coverage_status="pass",
        metrics=ClaimsetCoverageMetrics(document_page_count=2, covered_page_count=2, page_coverage_ratio=1.0),
        page_summary=ClaimsetCoveragePageSummary(covered_pages=[1, 2]),
        evidence_summary=ClaimsetCoverageEvidenceSummary(total_spans=2, grounded_spans=2, grounded_ratio=1.0),
        recommended_next_action="none",
    )

    md = build_deepread_markdown("llama3:latest", claimset, coverage=coverage)

    assert "### Coverage Review" not in md


def test_build_deepread_markdown_can_include_bounded_clinical_extraction_block():
    claimset = ClaimSet(
        doc_id="doc1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Drug A improved outcome.",
                confidence=0.91,
            )
        ],
    )
    extraction = BiomedicalClinicalExtraction(
        paper_id="doc1",
        citation={
            "title": "Clinical note",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Clinical Journal",
            "doi": None,
            "url": None,
        },
        population={"condition": "Ulcerative colitis", "n_total": 48},
        intervention={"category": "biologic", "name": "Monoclonal antibody"},
        outcomes={"primary": [{"name": "Clinical remission", "domain": "primary"}]},
        eligibility_flags={"followup_tag": "therapeutic"},
    )

    clinical_md = build_clinical_extraction_markdown(extraction)
    md = build_deepread_markdown("llama3:latest", claimset, clinical_md=clinical_md)

    assert "### 🏥 Clinical Extraction" in md
    assert "Ulcerative colitis, n=48" in md
    assert "Monoclonal antibody, Biologic" in md
    assert "Clinical remission" in md
    assert "Therapeutic" in md


def test_build_stats_markdown_renders_checks():
    report = StatsReport(
        doc_id="doc1",
        run_id="run1",
        checks=[
            StatCheckEntry(
                check_id="c1",
                test_type="t-test",
                hypothesis="A > B",
                reported_p="0.04",
                computed_p=0.041,
                code="print('ok')",
                outputs="ok",
                verdict=VerificationStatus.VERIFIED,
            )
        ],
    )
    stats_md = build_stats_markdown(report)
    assert "### 🧪 Stats Verification" in stats_md
    assert "#### Check: t-test" in stats_md
    assert "Computed" in stats_md


def test_build_stats_markdown_renders_notes_when_present():
    report = StatsReport(
        doc_id="doc1",
        run_id="run1",
        checks=[
            StatCheckEntry(
                check_id="c1",
                test_type="unknown",
                hypothesis="A > B",
                reported_p=None,
                computed_p=None,
                code="N/A",
                outputs="Degenerate table shape detected; statistical recomputation skipped.",
                verdict=VerificationStatus.UNVERIFIABLE,
                notes="auto_fallback_degenerate_table_shape",
            )
        ],
    )
    stats_md = build_stats_markdown(report)
    assert "auto_fallback_degenerate_table_shape" in stats_md
    assert "Degenerate table shape detected" in stats_md


def test_upsert_deepread_section_with_service_contract():
    content = "# Note\n\n## Section\nBody\n"
    claimset = ClaimSet(
        doc_id="doc1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Claim.",
                confidence=0.7,
            )
        ],
    )
    md = build_deepread_markdown("model-x", claimset)
    updated = upsert_deepread_section(content, md)
    assert updated.count(DEEPREAD_HEADER) == 1
    assert "Claim." in updated


def test_build_deepread_markdown_cleans_wrapped_evidence_quote_for_display():
    claimset = ClaimSet(
        doc_id="doc1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="KARI compounds directly inhibit ASM activity.",
                confidence=0.91,
                evidence_spans=[
                    EvidenceSpan(
                        raw_text="S4 D and E),\nindicating that KARI compounds inhibited ASM activity with-\nout changing mRNA and protein levels.",
                        quote="S4 D and E),\nindicating that KARI compounds inhibited ASM activity with-\nout changing mRNA and protein levels.",
                        page=2,
                    )
                ],
            )
        ],
    )
    md = build_deepread_markdown("llama3:latest", claimset)
    assert "S4 D and E)," not in md
    assert "with-\nout" not in md
    assert 'indicating that KARI compounds inhibited ASM activity without changing mRNA and protein levels.' in md


def test_format_evidence_text_for_display_is_conservative_when_no_cleanup_needed():
    text = "Direct evidence snippet from source text."
    assert _format_evidence_text_for_display(text) == text
