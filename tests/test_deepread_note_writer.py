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


def test_build_deepread_markdown_handles_missing_page_and_section():
    claimset = ClaimSet(
        doc_id="doc1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Fallback location claim.",
                confidence=0.6,
                evidence_spans=[EvidenceSpan(raw_text="Fallback evidence")],
            )
        ],
    )

    md = build_deepread_markdown("model-x", claimset)
    assert "Fallback evidence" in md
    assert "(Section: Unknown)" in md


def test_build_deepread_markdown_renders_table_evidence_without_raw_text():
    claimset = ClaimSet(
        doc_id="doc1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Table-backed claim.",
                confidence=0.6,
                evidence_spans=[EvidenceSpan(raw_text=" ", table_id="tbl-1", cell_id="r1c1")],
            )
        ],
    )

    md = build_deepread_markdown("model-x", claimset)
    assert "Table tbl-1, cell r1c1" in md
