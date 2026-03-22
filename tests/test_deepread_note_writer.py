from src.schemas.agent_artifacts import (
    ClaimSet,
    ScientificClaim,
    EvidenceSpan,
    StatsReport,
    StatCheckEntry,
    VerificationStatus,
)
from src.services.deepread_note_writer import (
    DEEPREAD_HEADER,
    _format_evidence_text_for_display,
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
