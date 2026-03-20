import pytest
from pydantic import ValidationError

from src.quality.claimset_policy import (
    UNKNOWN_REASON_EVIDENCE_LOCATION_MISSING,
    UNKNOWN_REASON_EVIDENCE_MISSING,
    UNKNOWN_REASON_UNSPECIFIED,
    enforce_claimset_evidence_policy,
)
from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, ScientificClaim


def _base_claim(*, claim_id: str, confidence: float = 0.9, evidence_spans=None) -> ScientificClaim:
    return ScientificClaim(
        claim_id=claim_id,
        type="efficacy",
        statement=f"statement-{claim_id}",
        confidence=confidence,
        evidence_spans=evidence_spans or [],
    )


def test_evidence_span_allows_table_cell_link_without_raw_text() -> None:
    span = EvidenceSpan(table_id="T1", cell_id="R1C2")
    assert span.raw_text is None
    assert span.table_id == "T1"
    assert span.cell_id == "R1C2"


def test_evidence_span_requires_raw_text_or_table_cell_link() -> None:
    with pytest.raises(ValidationError):
        EvidenceSpan()


def test_evidence_span_requires_table_id_and_cell_id_together() -> None:
    with pytest.raises(ValidationError):
        EvidenceSpan(table_id="T1")
    with pytest.raises(ValidationError):
        EvidenceSpan(cell_id="R1C2")


def test_evidence_span_rejects_invalid_bbox_pdf() -> None:
    with pytest.raises(ValidationError):
        EvidenceSpan(raw_text="evidence", bbox_pdf=[1.0, 2.0, 3.0])
    with pytest.raises(ValidationError):
        EvidenceSpan(raw_text="evidence", bbox_pdf=[2.0, 1.0, 0.0, 4.0])
    with pytest.raises(ValidationError):
        EvidenceSpan(raw_text="evidence", bbox_pdf=[-1.0, 0.0, 3.0, 4.0])


def test_evidence_span_requires_complete_bbox_pct() -> None:
    with pytest.raises(ValidationError):
        EvidenceSpan(raw_text="evidence", bbox_pct={"left": 1.0, "top": 2.0, "width": 3.0})


def test_evidence_span_normalizes_blank_raw_text_when_table_link_exists() -> None:
    span = EvidenceSpan(raw_text="   ", table_id="T1", cell_id="R1C2")
    assert span.raw_text is None
    assert span.table_id == "T1"
    assert span.cell_id == "R1C2"


def test_policy_marks_claim_unknown_when_evidence_missing() -> None:
    claim_set = ClaimSet(doc_id="doc-1", claims=[_base_claim(claim_id="c1", confidence=0.92)])

    out = enforce_claimset_evidence_policy(claim_set)

    claim = out.claims[0]
    assert claim.unknown is True
    assert claim.unknown_reason == UNKNOWN_REASON_EVIDENCE_MISSING
    assert claim.confidence == 0.35


def test_policy_marks_claim_unknown_when_location_missing() -> None:
    claim = _base_claim(
        claim_id="c1",
        confidence=0.88,
        evidence_spans=[EvidenceSpan(raw_text="evidence only")],
    )
    claim_set = ClaimSet(doc_id="doc-1", claims=[claim])

    out = enforce_claimset_evidence_policy(claim_set)

    patched = out.claims[0]
    assert patched.unknown is True
    assert patched.unknown_reason == UNKNOWN_REASON_EVIDENCE_LOCATION_MISSING
    assert patched.confidence == 0.5


def test_policy_keeps_known_claim_when_location_exists() -> None:
    claim = _base_claim(
        claim_id="c1",
        confidence=0.77,
        evidence_spans=[EvidenceSpan(raw_text="evidence", page=3)],
    )
    claim_set = ClaimSet(doc_id="doc-1", claims=[claim])

    out = enforce_claimset_evidence_policy(claim_set)

    kept = out.claims[0]
    assert kept.unknown is False
    assert kept.unknown_reason is None
    assert kept.confidence == 0.77


def test_policy_sets_bbox_highlight_source_when_bbox_exists() -> None:
    claim = _base_claim(
        claim_id="c1",
        confidence=0.77,
        evidence_spans=[EvidenceSpan(raw_text="evidence", page=3, bbox_pdf=[1.0, 2.0, 3.0, 4.0])],
    )
    claim_set = ClaimSet(doc_id="doc-1", claims=[claim])

    out = enforce_claimset_evidence_policy(claim_set)

    kept = out.claims[0]
    assert kept.evidence_spans[0].highlight_source == "bbox"


def test_policy_sets_text_match_highlight_source_when_text_only() -> None:
    claim = _base_claim(
        claim_id="c1",
        confidence=0.77,
        evidence_spans=[EvidenceSpan(raw_text="evidence", page=3)],
    )
    claim_set = ClaimSet(doc_id="doc-1", claims=[claim])

    out = enforce_claimset_evidence_policy(claim_set)

    kept = out.claims[0]
    assert kept.evidence_spans[0].highlight_source == "text_match"


def test_policy_fills_unspecified_reason_for_pre_marked_unknown_claim() -> None:
    claim = _base_claim(
        claim_id="c1",
        confidence=0.6,
        evidence_spans=[EvidenceSpan(raw_text="evidence", page=0)],
    )
    claim.unknown = True
    claim.unknown_reason = "   "
    claim_set = ClaimSet(doc_id="doc-1", claims=[claim])

    out = enforce_claimset_evidence_policy(claim_set)

    patched = out.claims[0]
    assert patched.unknown is True
    assert patched.unknown_reason == UNKNOWN_REASON_UNSPECIFIED
    assert patched.confidence == 0.6


def test_scientific_claim_defaults_unknown_reason_when_unknown_true() -> None:
    claim = ScientificClaim(
        claim_id="c1",
        type="efficacy",
        statement="statement",
        confidence=0.7,
        evidence_spans=[EvidenceSpan(raw_text="evidence", page=1)],
        unknown=True,
        unknown_reason="   ",
    )

    assert claim.unknown is True
    assert claim.unknown_reason == UNKNOWN_REASON_UNSPECIFIED
