import json
import sqlite3
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure `src` package is importable in direct pytest runs.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep this test independent from optional runtime deps (e.g., numpy/openai).
stub_llm_provider = types.ModuleType("src.llm_provider")
stub_llm_provider.get_llm_provider = lambda *args, **kwargs: None
stub_llm_provider.LLMProvider = object
_inserted_stub_llm_provider = "src.llm_provider" not in sys.modules
if _inserted_stub_llm_provider:
    sys.modules["src.llm_provider"] = stub_llm_provider

from src.processor import (
    PaperProcessor,
    STATE_APPROVED,
    STATE_FAILED,
    STATE_PENDING,
    STATE_QUARANTINED,
)
import src.db_utils as db_utils

if _inserted_stub_llm_provider:
    sys.modules.pop("src.llm_provider", None)


class _FakeProviderWithoutEscalation:
    def is_available(self):
        return True


def _init_processor_gate_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            status TEXT,
            gate_decision TEXT,
            gate_reason TEXT,
            feedback_json TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
@patch("src.processor.update_paper_status")
def test_step_gate_maps_decisions(mock_update_status, mock_load_config, mock_get_llm):
    mock_config = MagicMock()
    mock_config.confidence_thresholds.high = 0.9
    mock_config.confidence_thresholds.low = 0.7
    mock_config.paths.upload_dir = None
    mock_load_config.return_value = mock_config

    mock_get_llm.return_value = _FakeProviderWithoutEscalation()

    processor = PaperProcessor()

    processor._step_gate(
        {
            "paper_id": "p1",
            "confidence": 0.95,
            "feedback_json": '{"confidence": 0.95, "soft_tags": ["#a"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
        }
    )
    assert mock_update_status.call_args[0][1] == STATE_APPROVED

    processor._step_gate(
        {
            "paper_id": "p2",
            "confidence": 0.75,
            "feedback_json": '{"confidence": 0.75, "soft_tags": ["#a"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
        }
    )
    assert mock_update_status.call_args[0][1] == STATE_PENDING

    processor._step_gate(
        {
            "paper_id": "p3",
            "confidence": 0.55,
            "feedback_json": '{"confidence": 0.55, "soft_tags": ["#a"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
        }
    )
    assert mock_update_status.call_args[0][1] == STATE_QUARANTINED


@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
@patch("src.processor.update_paper_status")
def test_step_gate_marks_failed_when_feedback_json_broken(
    mock_update_status, mock_load_config, mock_get_llm
):
    mock_config = MagicMock()
    mock_config.confidence_thresholds.high = 0.9
    mock_config.confidence_thresholds.low = 0.7
    mock_config.paths.upload_dir = None
    mock_load_config.return_value = mock_config

    mock_get_llm.return_value = _FakeProviderWithoutEscalation()

    processor = PaperProcessor()
    processor._step_gate({"paper_id": "broken", "confidence": 0.95, "feedback_json": "{bad json"})
    assert mock_update_status.call_args[0][1] == STATE_FAILED


@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
@patch("src.processor.update_paper_status")
def test_step_gate_marks_failed_when_schema_invalid(
    mock_update_status, mock_load_config, mock_get_llm
):
    mock_config = MagicMock()
    mock_config.confidence_thresholds.high = 0.9
    mock_config.confidence_thresholds.low = 0.7
    mock_config.paths.upload_dir = None
    mock_load_config.return_value = mock_config

    mock_get_llm.return_value = _FakeProviderWithoutEscalation()

    processor = PaperProcessor()
    processor._step_gate(
        {
            "paper_id": "schema_bad",
            "confidence": 0.95,
            "feedback_json": '{"confidence": 0.95, "soft_tags": ["#a"], "hard_tags": "invalid_type"}',
        }
    )
    assert mock_update_status.call_args[0][1] == STATE_FAILED


@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
@patch("src.processor.update_paper_status")
def test_step_gate_promotes_pending_review_when_escalation_fast_lane_approves(
    mock_update_status, mock_load_config, mock_get_llm
):
    mock_config = MagicMock()
    mock_config.confidence_thresholds.high = 0.9
    mock_config.confidence_thresholds.low = 0.7
    mock_config.paths.upload_dir = None
    mock_load_config.return_value = mock_config

    class FakeProvider:
        def is_available(self):
            return True

        def evaluate_escalation(self, _payload):
            return {
                "approved": True,
                "reason": "Guideline metadata is explicit.",
                "final_route": "FAST_LANE_APPROVE",
                "in_biomedical_scope": True,
                "reason_codes": ["FASTLANE_GUIDANCE"],
            }

    mock_get_llm.return_value = FakeProvider()

    processor = PaperProcessor()
    processor._step_gate(
        {
            "paper_id": "p_escalated",
            "title": "Oncology guideline paper",
            "summary": "Guideline metadata is explicit.",
            "slot": "clinical",
            "confidence": 0.75,
            "feedback_json": '{"confidence": 0.75, "soft_tags": ["#oncology"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
        }
    )

    assert mock_update_status.call_args[0][1] == STATE_APPROVED
    updates = mock_update_status.call_args[0][2]
    assert updates["gate_decision"] == "APPROVED"
    assert updates["gate_reason"] == "CONFIDENCE_MID,FASTLANE_GUIDANCE"
    payload = json.loads(updates["feedback_json"])
    assert payload["escalation"]["approved"] is True
    assert payload["escalation"]["final_route"] == "FAST_LANE_APPROVE"
    assert payload["escalation"]["reason_codes"] == ["FASTLANE_GUIDANCE"]


@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
@patch("src.processor.update_paper_status")
def test_step_gate_keeps_pending_review_when_escalation_requires_human_review(
    mock_update_status, mock_load_config, mock_get_llm
):
    mock_config = MagicMock()
    mock_config.confidence_thresholds.high = 0.9
    mock_config.confidence_thresholds.low = 0.7
    mock_config.paths.upload_dir = None
    mock_load_config.return_value = mock_config

    class FakeProvider:
        def is_available(self):
            return True

        def evaluate_escalation(self, _payload):
            return {
                "approved": False,
                "reason": "Broad review; keep pending review.",
                "final_route": "QUEUE_HUMAN_REVIEW",
                "in_biomedical_scope": True,
                "reason_codes": ["MODEL_REVIEW_REQUIRED"],
            }

    mock_get_llm.return_value = FakeProvider()

    processor = PaperProcessor()
    processor._step_gate(
        {
            "paper_id": "p_pending",
            "title": "Broad biomedical review",
            "summary": "Broad review; keep pending review.",
            "slot": "clinical",
            "confidence": 0.75,
            "feedback_json": '{"confidence": 0.75, "soft_tags": ["#biomaterials"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
        }
    )

    assert mock_update_status.call_args[0][1] == STATE_PENDING
    updates = mock_update_status.call_args[0][2]
    assert updates["gate_decision"] == "PENDING_REVIEW"
    assert updates["gate_reason"] == "CONFIDENCE_MID,MODEL_REVIEW_REQUIRED"
    payload = json.loads(updates["feedback_json"])
    assert payload["escalation"]["approved"] is False
    assert payload["escalation"]["final_route"] == "QUEUE_HUMAN_REVIEW"
    assert payload["escalation"]["reason_codes"] == ["MODEL_REVIEW_REQUIRED"]


@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
def test_step_gate_persists_fast_lane_escalation_to_db(mock_load_config, mock_get_llm, tmp_path):
    db_path = tmp_path / "state.db"
    _init_processor_gate_db(db_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    try:
        mock_config = MagicMock()
        mock_config.confidence_thresholds.high = 0.9
        mock_config.confidence_thresholds.low = 0.7
        mock_config.paths.upload_dir = None
        mock_load_config.return_value = mock_config

        class FakeProvider:
            def is_available(self):
                return True

            def evaluate_escalation(self, _payload):
                return {
                    "approved": True,
                    "reason": "Guideline metadata is explicit.",
                    "final_route": "FAST_LANE_APPROVE",
                    "in_biomedical_scope": True,
                    "reason_codes": ["FASTLANE_GUIDANCE"],
                }

        mock_get_llm.return_value = FakeProvider()

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO papers (paper_id, status, gate_decision, gate_reason, feedback_json, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                "p_db_escalated",
                "GATED",
                None,
                None,
                '{"confidence": 0.75, "soft_tags": ["#oncology"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
            ),
        )
        conn.commit()
        conn.close()

        processor = PaperProcessor()
        processor._step_gate(
            {
                "paper_id": "p_db_escalated",
                "title": "Oncology guideline paper",
                "summary": "Guideline metadata is explicit.",
                "slot": "clinical",
                "confidence": 0.75,
                "feedback_json": '{"confidence": 0.75, "soft_tags": ["#oncology"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
            }
        )

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT status, gate_decision, gate_reason, feedback_json FROM papers WHERE paper_id = ?",
            ("p_db_escalated",),
        ).fetchone()
        conn.close()

        assert row["status"] == "APPROVED"
        assert row["gate_decision"] == "APPROVED"
        assert row["gate_reason"] == "CONFIDENCE_MID,FASTLANE_GUIDANCE"
        payload = json.loads(row["feedback_json"])
        assert payload["escalation"]["approved"] is True
        assert payload["escalation"]["final_route"] == "FAST_LANE_APPROVE"
        assert payload["escalation"]["reason_codes"] == ["FASTLANE_GUIDANCE"]
    finally:
        db_utils.DB_PATH = original_db_path


@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
def test_step_gate_persists_pending_review_escalation_to_db(mock_load_config, mock_get_llm, tmp_path):
    db_path = tmp_path / "state.db"
    _init_processor_gate_db(db_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    try:
        mock_config = MagicMock()
        mock_config.confidence_thresholds.high = 0.9
        mock_config.confidence_thresholds.low = 0.7
        mock_config.paths.upload_dir = None
        mock_load_config.return_value = mock_config

        class FakeProvider:
            def is_available(self):
                return True

            def evaluate_escalation(self, _payload):
                return {
                    "approved": False,
                    "reason": "Broad review; keep pending review.",
                    "final_route": "QUEUE_HUMAN_REVIEW",
                    "in_biomedical_scope": True,
                    "reason_codes": ["MODEL_REVIEW_REQUIRED"],
                }

        mock_get_llm.return_value = FakeProvider()

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO papers (paper_id, status, gate_decision, gate_reason, feedback_json, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                "p_db_pending",
                "GATED",
                None,
                None,
                '{"confidence": 0.75, "soft_tags": ["#biomaterials"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
            ),
        )
        conn.commit()
        conn.close()

        processor = PaperProcessor()
        processor._step_gate(
            {
                "paper_id": "p_db_pending",
                "title": "Broad biomedical review",
                "summary": "Broad review; keep pending review.",
                "slot": "clinical",
                "confidence": 0.75,
                "feedback_json": '{"confidence": 0.75, "soft_tags": ["#biomaterials"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
            }
        )

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT status, gate_decision, gate_reason, feedback_json FROM papers WHERE paper_id = ?",
            ("p_db_pending",),
        ).fetchone()
        conn.close()

        assert row["status"] == "PENDING_REVIEW"
        assert row["gate_decision"] == "PENDING_REVIEW"
        assert row["gate_reason"] == "CONFIDENCE_MID,MODEL_REVIEW_REQUIRED"
        payload = json.loads(row["feedback_json"])
        assert payload["escalation"]["approved"] is False
        assert payload["escalation"]["final_route"] == "QUEUE_HUMAN_REVIEW"
        assert payload["escalation"]["reason_codes"] == ["MODEL_REVIEW_REQUIRED"]
    finally:
        db_utils.DB_PATH = original_db_path
