from src.agents.stats_agent import StatsVerificationAgent
from src.schemas.agent_artifacts import ClaimSet, ScientificClaim, VerificationStatus, DocumentArtifact, SourceInfo, PaperMetadata, TableData


def test_build_unverifiable_fallback_checks_from_extraction_items() -> None:
    state = {
        "job_id": "job-1",
        "claims": ClaimSet(
            doc_id="file:x",
            claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="s", confidence=0.8)],
        ),
        "python_code": "print('x')",
        "execution_output": "stderr...",
        "execution_error": "Exit 1",
        "extraction_result": [
            {
                "claim_text": "Claim A",
                "test_type": "t-test",
                "reported_p": "0.04",
            }
        ],
    }

    checks = StatsVerificationAgent._build_unverifiable_fallback_checks(state)
    assert len(checks) == 1
    assert checks[0].check_id == "auto_1"
    assert checks[0].test_type == "t-test"
    assert checks[0].verdict == VerificationStatus.UNVERIFIABLE


def test_build_unverifiable_fallback_checks_from_claims_when_no_extraction() -> None:
    state = {
        "job_id": "job-1",
        "claims": ClaimSet(
            doc_id="file:x",
            claims=[
                ScientificClaim(claim_id="c1", type="efficacy", statement="claim 1", confidence=0.8),
                ScientificClaim(claim_id="c2", type="safety", statement="claim 2", confidence=0.7),
            ],
        ),
        "python_code": "",
        "execution_output": "",
        "execution_error": "no output",
        "extraction_result": [],
    }

    checks = StatsVerificationAgent._build_unverifiable_fallback_checks(state)
    assert len(checks) == 2
    assert checks[0].check_id == "c1"
    assert checks[1].check_id == "c2"
    assert all(c.verdict == VerificationStatus.UNVERIFIABLE for c in checks)


def test_build_unverifiable_fallback_checks_marks_degenerate_table_shape() -> None:
    state = {
        "job_id": "job-1",
        "doc": DocumentArtifact(
            doc_id="file:x",
            source=SourceInfo(type="pdf", ref="/tmp/x.pdf"),
            metadata=PaperMetadata(title="t", authors=[], year=2024),
            tables=[
                TableData(
                    table_id="t1",
                    caption="Table found on page 4",
                    data=[["53.08\n52.31"]],
                    source_page=4,
                )
            ],
        ),
        "claims": ClaimSet(
            doc_id="file:x",
            claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim 1", confidence=0.8)],
        ),
        "python_code": "",
        "execution_output": "",
        "execution_error": "no output",
        "extraction_result": [],
    }

    checks = StatsVerificationAgent._build_unverifiable_fallback_checks(state)

    assert len(checks) == 1
    assert checks[0].notes == "auto_fallback_degenerate_table_shape"
    assert "Degenerate table shape detected" in (checks[0].outputs or "")
