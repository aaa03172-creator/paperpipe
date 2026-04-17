from src.agents.stats_agent import StatsVerificationAgent
from src.schemas.agent_artifacts import (
    ClaimSet,
    DocumentArtifact,
    PaperMetadata,
    ScientificClaim,
    SourceInfo,
    TableData,
    VerificationStatus,
)


def test_run_short_circuits_to_no_table_unverifiable_checks() -> None:
    doc = DocumentArtifact(
        doc_id="file:sample.pdf",
        source=SourceInfo(type="pdf", ref="/tmp/sample.pdf"),
        metadata=PaperMetadata(title="Sample", authors=[], year=0, journal="Unknown"),
        sections=[],
        tables=[],
    )
    claims = ClaimSet(
        doc_id="file:sample.pdf",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Claim one",
                confidence=0.8,
            ),
            ScientificClaim(
                claim_id="c2",
                type="safety",
                statement="Claim two",
                confidence=0.7,
            ),
        ],
    )

    # Bypass heavy init; no-table path should not touch workflow/model.
    agent = StatsVerificationAgent.__new__(StatsVerificationAgent)
    report = StatsVerificationAgent.run(agent, job_id="job-no-table", doc=doc, claims=claims)

    assert report.doc_id == "file:sample.pdf"
    assert report.run_id == "job-no-table"
    assert len(report.checks) == 2
    assert report.checks[0].method == "no_table_data"
    assert report.checks[0].verdict == VerificationStatus.UNVERIFIABLE
    assert report.checks[1].check_id == "c2"


def test_run_short_circuits_degenerate_tables_to_unverifiable_checks() -> None:
    doc = DocumentArtifact(
        doc_id="file:sample.pdf",
        source=SourceInfo(type="pdf", ref="/tmp/sample.pdf"),
        metadata=PaperMetadata(title="Sample", authors=[], year=0, journal="Unknown"),
        sections=[],
        tables=[
            TableData(
                table_id="t1",
                caption="Table found on page 4",
                data=[["53.08\n52.31"]],
                source_page=4,
            )
        ],
    )
    claims = ClaimSet(
        doc_id="file:sample.pdf",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Claim one",
                confidence=0.8,
            )
        ],
    )

    agent = StatsVerificationAgent.__new__(StatsVerificationAgent)
    report = StatsVerificationAgent.run(agent, job_id="job-degenerate", doc=doc, claims=claims)

    assert report.doc_id == "file:sample.pdf"
    assert report.run_id == "job-degenerate"
    assert len(report.checks) == 1
    assert report.checks[0].verdict == VerificationStatus.UNVERIFIABLE
    assert report.checks[0].notes == "auto_fallback_degenerate_table_shape"
    assert "Degenerate table shape detected" in (report.checks[0].outputs or "")
