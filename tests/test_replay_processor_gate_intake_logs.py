import json
import sqlite3
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

stub_llm_provider = types.ModuleType("src.llm_provider")
stub_llm_provider.get_llm_provider = lambda *args, **kwargs: None
stub_llm_provider.LLMProvider = object
_inserted_stub_llm_provider = "src.llm_provider" not in sys.modules
if _inserted_stub_llm_provider:
    sys.modules["src.llm_provider"] = stub_llm_provider

from scripts.replay_processor_gate_intake_logs import (
    apply_processor_gate_replay,
    build_processor_gate_replay_plan,
    select_backfill_intake_override_rows,
)
from src.gates import GateEngine
from src.services.intake_override_log import build_intake_override_log, merge_feedback_json_with_intake_override

if _inserted_stub_llm_provider:
    sys.modules.pop("src.llm_provider", None)


def _create_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            gate_decision TEXT,
            feedback_json TEXT,
            updated_at TEXT,
            confidence REAL,
            slot TEXT
        )
        """
    )
    return conn


def _backfill_feedback_json(*, confidence: float, processing_status: str = "INDEXED") -> str:
    payload = json.dumps(
        {
            "hard_tags": {"species": "human"},
            "soft_tags": ["#Clinical"],
            "evidence_span": "evidence",
            "confidence": confidence,
        },
        ensure_ascii=False,
    )
    intake_override_log = build_intake_override_log(
        producer="backfill_analysis",
        analysis_available=True,
        llm_tagging_used=False,
        llm_slot_classification_used=False,
        input_slot="clinical",
        stored_slot="clinical",
        input_tags=["#Clinical"],
        stored_tags=["#Clinical"],
        processing_status=processing_status,
        issues_state="clear",
        confidence=confidence,
    )
    return merge_feedback_json_with_intake_override(payload, intake_override_log)


def test_build_processor_gate_replay_plan_only_promotes_stable_rows(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-approved", "Approved Paper", "INDEXED", "APPROVED", _backfill_feedback_json(confidence=0.95), 0.95, "clinical"),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-mismatch", "Mismatch Paper", "INDEXED", "PENDING_REVIEW", _backfill_feedback_json(confidence=0.95), 0.95, "clinical"),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-runtime", "Runtime Paper", "INDEXED", "APPROVED", _backfill_feedback_json(confidence=0.95).replace("backfill_analysis", "processor_gate"), 0.95, "clinical"),
    )
    conn.commit()

    rows = select_backfill_intake_override_rows(conn)
    plans = build_processor_gate_replay_plan(rows, gate_engine=GateEngine(high_threshold=0.9, low_threshold=0.7))

    assert [plan.paper_id for plan in plans] == ["paper-approved", "paper-mismatch"]
    assert [plan.eligible_for_apply for plan in plans] == [True, False]
    assert plans[0].replay_gate_decision == "APPROVED"
    assert plans[0].replay_status == "APPROVED"
    assert plans[1].skip_reason == "gate_decision_mismatch"
    conn.close()


def test_apply_processor_gate_replay_updates_only_promotable_rows(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-approved", "Approved Paper", "INDEXED", "APPROVED", _backfill_feedback_json(confidence=0.95), 0.95, "clinical"),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-mismatch", "Mismatch Paper", "INDEXED", "PENDING_REVIEW", _backfill_feedback_json(confidence=0.95), 0.95, "clinical"),
    )
    conn.commit()

    rows = select_backfill_intake_override_rows(conn)
    plans = build_processor_gate_replay_plan(rows, gate_engine=GateEngine(high_threshold=0.9, low_threshold=0.7))
    updated = apply_processor_gate_replay(conn, plans)

    approved_row = conn.execute(
        "SELECT status, gate_decision, feedback_json FROM papers WHERE paper_id = ?",
        ("paper-approved",),
    ).fetchone()
    mismatch_row = conn.execute(
        "SELECT status, gate_decision, feedback_json FROM papers WHERE paper_id = ?",
        ("paper-mismatch",),
    ).fetchone()
    conn.close()

    approved_payload = json.loads(approved_row["feedback_json"])
    mismatch_payload = json.loads(mismatch_row["feedback_json"])

    assert updated == 1
    assert approved_row["status"] == "INDEXED"
    assert approved_row["gate_decision"] == "APPROVED"
    assert approved_payload["intake_override_log"]["producer"] == "processor_gate"
    assert approved_payload["intake_override_log"]["processing_status"] == "APPROVED"
    assert mismatch_payload["intake_override_log"]["producer"] == "backfill_analysis"
