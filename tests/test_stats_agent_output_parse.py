from src.agents.stats_agent import StatsVerificationAgent
from src.schemas.agent_artifacts import VerificationStatus


def test_extract_json_payload_from_plain_json_dict() -> None:
    payload = StatsVerificationAgent._extract_json_payload('{"check_1": {"verdict": "consistent", "computed_p": 0.04}}')
    assert isinstance(payload, dict)
    assert "check_1" in payload


def test_extract_json_payload_from_fenced_block() -> None:
    text = """
noise
```json
[{"check_id":"c1","test_type":"t-test","verdict":"verified"}]
```
more noise
"""
    payload = StatsVerificationAgent._extract_json_payload(text)
    assert isinstance(payload, list)
    assert payload[0]["check_id"] == "c1"


def test_checks_from_execution_payload_maps_consistent_to_verified() -> None:
    state = {
        "python_code": "print('x')",
        "execution_output": "{...}",
    }
    agent = StatsVerificationAgent.__new__(StatsVerificationAgent)
    checks = StatsVerificationAgent._checks_from_execution_payload(
        agent,
        {"check_1": {"computed_p": 0.04, "verdict": "consistent", "test_type": "t-test"}},
        state,
    )
    assert len(checks) == 1
    assert checks[0].check_id == "check_1"
    assert checks[0].verdict == VerificationStatus.VERIFIED
    assert checks[0].test_type == "t-test"


def test_checks_from_execution_payload_handles_unknown_verdict() -> None:
    state = {
        "python_code": "print('x')",
        "execution_output": "{...}",
    }
    agent = StatsVerificationAgent.__new__(StatsVerificationAgent)
    checks = StatsVerificationAgent._checks_from_execution_payload(
        agent,
        [{"check_id": "c1", "test_type": "anova", "verdict": "maybe"}],
        state,
    )
    assert len(checks) == 1
    assert checks[0].verdict == VerificationStatus.UNVERIFIABLE
