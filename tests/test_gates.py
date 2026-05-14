from src.gates import GateEngine
from src.schemas.gates import GateDecision, ReasonCode


def _base_analysis(confidence: float = 0.95):
    return {
        "confidence": confidence,
        "soft_tags": ["#ketone"],
        "hard_tags": {"sample_size": 40},
        "evidence_span": "Ketone levels increased in the intervention arm.",
    }


def test_gate_approves_high_confidence_with_evidence():
    engine = GateEngine(high_threshold=0.9, low_threshold=0.7, require_evidence=True)
    result = engine.evaluate(_base_analysis(0.93))
    assert result.decision == GateDecision.APPROVED
    assert ReasonCode.EVIDENCE_MISSING not in result.reason_codes
    assert result.confidence_total == 0.93


def test_gate_quarantines_low_confidence():
    engine = GateEngine(high_threshold=0.9, low_threshold=0.7, require_evidence=True)
    result = engine.evaluate(_base_analysis(0.5))
    assert result.decision == GateDecision.QUARANTINED
    assert ReasonCode.CONFIDENCE_LOW in result.reason_codes


def test_gate_marks_failed_on_schema_parse_failure():
    engine = GateEngine(high_threshold=0.9, low_threshold=0.7, require_evidence=True)
    result = engine.evaluate(_base_analysis(), parse_ok=False)
    assert result.decision == GateDecision.FAILED
    assert result.reason_codes == [ReasonCode.SCHEMA_PARSE_FAIL]


def test_gate_downgrades_without_evidence():
    engine = GateEngine(high_threshold=0.9, low_threshold=0.7, require_evidence=True)
    analysis = _base_analysis(0.95)
    analysis.pop("evidence_span")
    result = engine.evaluate(analysis)
    assert result.decision == GateDecision.PENDING_REVIEW
    assert ReasonCode.EVIDENCE_MISSING in result.reason_codes


def test_gate_fails_when_required_fields_missing():
    engine = GateEngine(high_threshold=0.9, low_threshold=0.7, require_evidence=True)
    analysis = {"confidence": 0.95, "soft_tags": ["#mci"]}
    result = engine.evaluate(analysis)
    assert result.decision == GateDecision.FAILED
    assert ReasonCode.MISSING_REQUIRED_FIELDS in result.reason_codes
    assert result.missing_fields == ["hard_tags"]
