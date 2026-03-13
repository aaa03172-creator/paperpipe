from src.agents.stats_agent import StatsVerificationAgent
from src.schemas.agent_artifacts import (
    ClaimSet,
    DocumentArtifact,
    PaperMetadata,
    ScientificClaim,
    SourceInfo,
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
