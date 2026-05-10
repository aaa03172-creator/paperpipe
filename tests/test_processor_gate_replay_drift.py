import json
import sqlite3
import subprocess
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
    build_processor_gate_replay_plan,
    select_backfill_intake_override_rows,
)
from src.gates import GateEngine
from src.services.intake_override_log import build_intake_override_log, merge_feedback_json_with_intake_override
from src.services.processor_gate_replay_drift import build_processor_gate_replay_drift

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
            gate_reason TEXT,
            feedback_json TEXT,
            created_at TEXT,
            updated_at TEXT,
            confidence REAL,
            slot TEXT
        )
        """
    )
    return conn


def _migration_plan(*, legacy_paper_id: str, canonical_paper_id: str) -> dict[str, str]:
    return {canonical_paper_id: legacy_paper_id}


def _feedback_json(*, confidence: float) -> str:
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
        processing_status="INDEXED",
        issues_state="clear",
        confidence=confidence,
    )
    return merge_feedback_json_with_intake_override(payload, intake_override_log)


def test_build_processor_gate_replay_drift_summarizes_promotable_and_drift_rows(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-high", "High Paper", "INDEXED", "APPROVED", "CONFIDENCE_HIGH", _feedback_json(confidence=0.95), 0.95, "clinical"),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-mid", "Mid Paper", "INDEXED", "APPROVED", "CONFIDENCE_HIGH", _feedback_json(confidence=0.8), 0.8, "clinical"),
    )
    conn.commit()

    candidate_rows = select_backfill_intake_override_rows(conn)
    plans = build_processor_gate_replay_plan(candidate_rows, gate_engine=GateEngine(high_threshold=0.9, low_threshold=0.7))
    summary, details = build_processor_gate_replay_drift(
        rows=candidate_rows,
        plans=plans,
        run_id="processor_gate_replay_drift_test",
        db_path=db_path,
        high_threshold=0.9,
        low_threshold=0.7,
    )
    conn.close()

    assert summary.metrics.candidate_count == 2
    assert summary.metrics.promotable_count == 1
    assert summary.metrics.drift_count == 1
    assert summary.metrics.drift_rate == 0.5
    assert summary.metrics.skip_reason_counts == {"gate_decision_mismatch": 1}
    assert summary.metrics.decision_transition_counts == {"APPROVED->PENDING_REVIEW": 1}
    assert summary.metrics.gate_reason_category_counts == {"confidence_threshold": 1}
    assert summary.metrics.timestamp_relation_counts == {"missing_created_or_updated": 1}
    assert summary.metrics.historical_path_hint_counts == {"explicit_confidence_gate_reason_present": 1}
    assert summary.metrics.confidence_value_counts == {"0.8": 1}
    assert summary.metrics.confidence_band_counts == {"mid": 1}
    assert summary.metrics.evidence_source_counts == {"evidence_span": 1}
    assert summary.documents_with_drift == ["paper-mid"]

    by_id = {doc.paper_id: doc for doc in details.documents}
    assert by_id["paper-high"].eligible_for_apply is True
    assert by_id["paper-mid"].eligible_for_apply is False
    assert by_id["paper-mid"].current_gate_reason == "CONFIDENCE_HIGH"
    assert by_id["paper-mid"].current_gate_reason_category == "confidence_threshold"
    assert by_id["paper-mid"].confidence_band == "mid"
    assert by_id["paper-mid"].timestamp_relation == "missing_created_or_updated"
    assert by_id["paper-mid"].evidence_source == "evidence_span"
    assert by_id["paper-mid"].probable_drift_cause == "legacy_mid_confidence_approval"
    assert by_id["paper-mid"].historical_path_hint == "explicit_confidence_gate_reason_present"


def test_build_processor_gate_replay_drift_classifies_probable_causes(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-manual", "Manual Paper", "INDEXED", "APPROVED", "Manual Gatekeeper Approval", _feedback_json(confidence=0.8), 0.8, "clinical"),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-indexed-pending", "Indexed Pending", "INDEXED", "PENDING_REVIEW", None, _feedback_json(confidence=0.8), 0.8, "clinical"),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-high-pending", "High Pending", "INDEXED", "PENDING_REVIEW", None, _feedback_json(confidence=0.95), 0.95, "clinical"),
    )
    conn.commit()

    candidate_rows = select_backfill_intake_override_rows(conn)
    plans = build_processor_gate_replay_plan(candidate_rows, gate_engine=GateEngine(high_threshold=0.9, low_threshold=0.7))
    summary, details = build_processor_gate_replay_drift(
        rows=candidate_rows,
        plans=plans,
        run_id="processor_gate_replay_drift_cause_test",
        db_path=db_path,
        high_threshold=0.9,
        low_threshold=0.7,
    )
    conn.close()

    assert summary.metrics.probable_drift_cause_counts == {
        "legacy_high_confidence_pending": 1,
        "legacy_indexed_pending_review": 1,
        "manual_or_human_override_mid_confidence": 1,
    }
    assert summary.metrics.gate_reason_category_counts == {
        "manual_or_human": 1,
        "none": 2,
    }
    assert summary.metrics.timestamp_relation_counts == {
        "missing_created_or_updated": 3,
    }
    assert summary.metrics.historical_path_hint_counts == {
        "legacy_pending_indexed_shape": 1,
        "manual_or_human_gate_reason_present": 1,
        "no_direct_history_hint": 1,
    }
    assert summary.metrics.confidence_value_counts == {
        "0.8": 2,
        "0.95": 1,
    }

    by_id = {doc.paper_id: doc for doc in details.documents}
    assert by_id["paper-manual"].probable_drift_cause == "manual_or_human_override_mid_confidence"
    assert by_id["paper-manual"].current_gate_reason_category == "manual_or_human"
    assert by_id["paper-manual"].historical_path_hint == "manual_or_human_gate_reason_present"
    assert by_id["paper-indexed-pending"].probable_drift_cause == "legacy_indexed_pending_review"
    assert by_id["paper-indexed-pending"].historical_path_hint == "legacy_pending_indexed_shape"
    assert by_id["paper-high-pending"].probable_drift_cause == "legacy_high_confidence_pending"
    assert by_id["paper-high-pending"].historical_path_hint == "no_direct_history_hint"


def test_build_processor_gate_replay_drift_tracks_precanonical_identity_migration(tmp_path):
    db_path = tmp_path / "state.db"
    legacy_db_path = tmp_path / "legacy.db"

    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        (
            "zotero:legacy-paper",
            "Legacy Paper",
            "INDEXED",
            "APPROVED",
            None,
            _feedback_json(confidence=0.8),
            0.8,
            "clinical",
        ),
    )
    conn.commit()

    legacy_conn = _create_db(legacy_db_path)
    legacy_conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        (
            "legacy-paper",
            "Legacy Paper",
            "INDEXED",
            "APPROVED",
            None,
            _feedback_json(confidence=0.8),
            0.8,
            "clinical",
        ),
    )
    legacy_conn.commit()

    candidate_rows = select_backfill_intake_override_rows(conn)
    plans = build_processor_gate_replay_plan(candidate_rows, gate_engine=GateEngine(high_threshold=0.9, low_threshold=0.7))
    summary, details = build_processor_gate_replay_drift(
        rows=candidate_rows,
        plans=plans,
        run_id="processor_gate_replay_drift_identity_test",
        db_path=db_path,
        paper_id_migration_plan_path=tmp_path / "paper_id_migration_plan.json",
        precanonical_db_path=legacy_db_path,
        canonical_to_legacy_paper_id=_migration_plan(
            legacy_paper_id="legacy-paper",
            canonical_paper_id="zotero:legacy-paper",
        ),
        precanonical_rows_by_paper_id={
            "legacy-paper": {
                "paper_id": "legacy-paper",
                "status": "INDEXED",
                "gate_decision": "APPROVED",
                "confidence": 0.8,
            }
        },
        high_threshold=0.9,
        low_threshold=0.7,
    )
    conn.close()
    legacy_conn.close()

    assert summary.metrics.identity_migration_hint_counts == {
        "precanonical_row_matches_current_decision": 1
    }
    doc = details.documents[0]
    assert doc.precanonical_paper_id == "legacy-paper"
    assert doc.precanonical_status == "INDEXED"
    assert doc.precanonical_gate_decision == "APPROVED"
    assert doc.precanonical_confidence == 0.8
    assert doc.identity_migration_hint == "precanonical_row_matches_current_decision"


def test_build_processor_gate_replay_drift_tracks_feedback_import_hint(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        (
            "zotero:legacy-paper",
            "Legacy Paper",
            "INDEXED",
            "APPROVED",
            None,
            _feedback_json(confidence=0.8),
            0.8,
            "clinical",
        ),
    )
    conn.commit()

    candidate_rows = select_backfill_intake_override_rows(conn)
    plans = build_processor_gate_replay_plan(candidate_rows, gate_engine=GateEngine(high_threshold=0.9, low_threshold=0.7))
    summary, details = build_processor_gate_replay_drift(
        rows=candidate_rows,
        plans=plans,
        run_id="processor_gate_replay_drift_feedback_test",
        db_path=db_path,
        feedback_log_path=tmp_path / "feedback.jsonl",
        feedback_log_summary_by_paper_id={
            "legacy-paper": {
                "avg_confidence": 0.92,
                "gate_decision_hint": "APPROVED",
            }
        },
        high_threshold=0.9,
        low_threshold=0.7,
    )
    conn.close()

    assert summary.metrics.feedback_log_import_hint_counts == {
        "feedback_import_gate_preserved_confidence_overwritten": 1
    }
    doc = details.documents[0]
    assert doc.feedback_log_paper_id == "legacy-paper"
    assert doc.feedback_log_avg_confidence == 0.92
    assert doc.feedback_log_gate_decision_hint == "APPROVED"
    assert doc.feedback_log_import_hint == "feedback_import_gate_preserved_confidence_overwritten"


def test_build_processor_gate_replay_drift_tracks_feedback_log_timestamp_relation(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (
            paper_id, title, status, gate_decision, gate_reason, feedback_json, created_at, updated_at, confidence, slot
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "zotero:legacy-paper",
            "Legacy Paper",
            "INDEXED",
            "APPROVED",
            None,
            _feedback_json(confidence=0.8),
            "2026-02-13 13:57:58",
            "2026-02-13 13:57:58",
            0.8,
            "clinical",
        ),
    )
    conn.commit()

    candidate_rows = select_backfill_intake_override_rows(conn)
    plans = build_processor_gate_replay_plan(candidate_rows, gate_engine=GateEngine(high_threshold=0.9, low_threshold=0.7))
    summary, details = build_processor_gate_replay_drift(
        rows=candidate_rows,
        plans=plans,
        run_id="processor_gate_replay_drift_feedback_timestamp_test",
        db_path=db_path,
        feedback_log_path=tmp_path / "feedback.jsonl",
        feedback_log_summary_by_paper_id={
            "legacy-paper": {
                "avg_confidence": 0.92,
                "gate_decision_hint": "APPROVED",
                "timestamp": "2026-02-13T10:43:09.583099",
            }
        },
        high_threshold=0.9,
        low_threshold=0.7,
    )
    conn.close()

    assert summary.metrics.feedback_log_timestamp_relation_counts == {
        "feedback_before_or_equal_created": 1
    }
    doc = details.documents[0]
    assert doc.feedback_log_timestamp == "2026-02-13T10:43:09.583099"
    assert doc.feedback_log_timestamp_relation == "feedback_before_or_equal_created"


def test_build_processor_gate_replay_drift_tracks_local_provenance_hints(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        (
            "phase0_test",
            "Unknown Title",
            "INDEXED",
            "PENDING_REVIEW",
            None,
            _feedback_json(confidence=0.95),
            0.95,
            "clinical",
        ),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        (
            "zotero:legacy-explicit",
            "Legacy Explicit",
            "INDEXED",
            "APPROVED",
            "Confidence 0.9",
            _feedback_json(confidence=0.8),
            0.8,
            "clinical",
        ),
    )
    conn.commit()

    candidate_rows = select_backfill_intake_override_rows(conn)
    plans = build_processor_gate_replay_plan(candidate_rows, gate_engine=GateEngine(high_threshold=0.9, low_threshold=0.7))
    summary, details = build_processor_gate_replay_drift(
        rows=candidate_rows,
        plans=plans,
        run_id="processor_gate_replay_drift_local_provenance_test",
        db_path=db_path,
        paper_id_migration_plan_path=tmp_path / "paper_id_migration_plan.json",
        precanonical_db_path=tmp_path / "legacy.db",
        feedback_log_path=tmp_path / "feedback.jsonl",
        canonical_to_legacy_paper_id=_migration_plan(
            legacy_paper_id="legacy-explicit",
            canonical_paper_id="zotero:legacy-explicit",
        ),
        precanonical_rows_by_paper_id={
            "legacy-explicit": {
                "paper_id": "legacy-explicit",
                "status": "INDEXED",
                "gate_decision": "APPROVED",
                "gate_reason": "Confidence 0.9",
                "confidence": 0.8,
            }
        },
        feedback_log_summary_by_paper_id={
            "phase0_test": {
                "avg_confidence": 0.75,
                "gate_decision_hint": "PENDING_REVIEW",
            }
        },
        high_threshold=0.9,
        low_threshold=0.7,
    )
    conn.close()

    assert summary.metrics.local_provenance_hint_counts == {
        "precanonical_explicit_gate_reason_preserved": 1,
        "test_fixture_row": 1,
    }

    by_id = {doc.paper_id: doc for doc in details.documents}
    assert by_id["phase0_test"].fixture_classification_reason == "fixture_visibility_rule"
    assert by_id["phase0_test"].local_provenance_hint == "test_fixture_row"

    assert by_id["zotero:legacy-explicit"].precanonical_gate_reason == "Confidence 0.9"
    assert by_id["zotero:legacy-explicit"].precanonical_gate_reason_category == "confidence_threshold"
    assert by_id["zotero:legacy-explicit"].feedback_log_import_hint == "no_feedback_log_match"
    assert by_id["zotero:legacy-explicit"].local_provenance_hint == "precanonical_explicit_gate_reason_preserved"


def test_build_processor_gate_replay_drift_tracks_historical_rewrite_hint(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (
            paper_id, title, status, gate_decision, gate_reason, feedback_json, created_at, updated_at, confidence, slot
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "zotero:legacy-paper",
            "Legacy Paper",
            "INDEXED",
            "APPROVED",
            None,
            _feedback_json(confidence=0.8),
            "2026-02-13 13:57:58",
            "2026-02-13 13:57:58",
            0.8,
            "clinical",
        ),
    )
    conn.commit()

    candidate_rows = select_backfill_intake_override_rows(conn)
    plans = build_processor_gate_replay_plan(candidate_rows, gate_engine=GateEngine(high_threshold=0.9, low_threshold=0.7))
    summary, details = build_processor_gate_replay_drift(
        rows=candidate_rows,
        plans=plans,
        run_id="processor_gate_replay_drift_historical_rewrite_test",
        db_path=db_path,
        paper_id_migration_plan_path=tmp_path / "paper_id_migration_plan.json",
        precanonical_db_path=tmp_path / "legacy.db",
        feedback_log_path=tmp_path / "feedback.jsonl",
        canonical_to_legacy_paper_id=_migration_plan(
            legacy_paper_id="legacy-paper",
            canonical_paper_id="zotero:legacy-paper",
        ),
        precanonical_rows_by_paper_id={
            "legacy-paper": {
                "paper_id": "legacy-paper",
                "created_at": "2026-02-13 13:57:58",
                "updated_at": "2026-02-17 13:52:06.058222",
                "status": "INDEXED",
                "gate_decision": "APPROVED",
                "gate_reason": None,
                "confidence": 0.8,
            }
        },
        feedback_log_summary_by_paper_id={
            "legacy-paper": {
                "avg_confidence": 0.92,
                "gate_decision_hint": "APPROVED",
                "timestamp": "2026-02-13T10:43:09.583099",
            }
        },
        high_threshold=0.9,
        low_threshold=0.7,
    )
    conn.close()

    assert summary.metrics.feedback_log_to_precanonical_update_relation_counts == {
        "feedback_before_or_equal_created": 1
    }
    assert summary.metrics.historical_rewrite_hint_counts == {
        "post_feedback_precanonical_confidence_overwrite_candidate": 1
    }
    doc = details.documents[0]
    assert doc.precanonical_updated_at == "2026-02-17 13:52:06.058222"
    assert doc.feedback_log_to_precanonical_update_relation == "feedback_before_or_equal_created"
    assert doc.historical_rewrite_hint == "post_feedback_precanonical_confidence_overwrite_candidate"


def test_audit_processor_gate_replay_drift_script_emits_threshold_review_command(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        ("paper-mid", "Mid Paper", "INDEXED", "APPROVED", "CONFIDENCE_HIGH", _feedback_json(confidence=0.8), 0.8, "clinical"),
    )
    conn.commit()
    conn.close()

    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "audit_processor_gate_replay_drift.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--db-path",
            str(db_path),
            "--out-dir",
            str(tmp_path / "out"),
            "--paper-id-migration-plan",
            str(tmp_path / "missing_plan.json"),
            "--precanonical-db-path",
            str(tmp_path / "missing_legacy.db"),
            "--feedback-log-path",
            str(tmp_path / "missing_feedback.jsonl"),
            "--run-id",
            "processor_gate_replay_drift_script_test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["summary_path"].endswith("/processor_gate_replay_drift_script_test/summary.json")
    assert payload["details_path"].endswith("/processor_gate_replay_drift_script_test/details.json")
    assert payload["markdown_path"].endswith("/processor_gate_replay_drift_script_test/audit.md")
    assert "recommend_processor_gate_threshold_review.py" in payload["threshold_review_command"]
    assert "--drift-summary" in payload["threshold_review_command"]
    assert "processor_gate_replay_drift_script_test__threshold_review" in payload["threshold_review_command"]


def test_audit_processor_gate_replay_drift_script_replays_threshold_change_proposal(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "state.db"
    conn = _create_db(db_path)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, updated_at, confidence, slot)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        (
            "paper-boundary",
            "Boundary Paper",
            "INDEXED",
            "APPROVED",
            "CONFIDENCE_HIGH",
            _feedback_json(confidence=0.86),
            0.86,
            "clinical",
        ),
    )
    conn.commit()
    conn.close()
    proposal_path = tmp_path / "threshold_change_proposal.json"
    proposal_path.write_text(
        json.dumps(
            {
                "schema_version": "processor_gate_threshold_change_proposal.v1",
                "run_id": "gate_threshold_review_ready",
                "proposal_ready": True,
                "target_field": "confidence_thresholds.high",
                "current_thresholds": {"high": 0.9, "low": 0.7},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "audit_processor_gate_replay_drift.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--db-path",
            str(db_path),
            "--out-dir",
            str(tmp_path / "out"),
            "--paper-id-migration-plan",
            str(tmp_path / "missing_plan.json"),
            "--precanonical-db-path",
            str(tmp_path / "missing_legacy.db"),
            "--feedback-log-path",
            str(tmp_path / "missing_feedback.jsonl"),
            "--run-id",
            "processor_gate_replay_drift_proposal_validation",
            "--threshold-change-proposal",
            str(proposal_path),
            "--reviewed-high-threshold",
            "0.85",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    summary = json.loads(Path(payload["summary_path"]).read_text(encoding="utf-8"))
    details = json.loads(Path(payload["details_path"]).read_text(encoding="utf-8"))
    assert payload["threshold_replay"] == {
        "threshold_replay_mode": "threshold_change_proposal_replay",
        "threshold_change_proposal_path": str(proposal_path.resolve(strict=False)),
        "reviewed_high_threshold": 0.85,
        "proposal_run_id": "gate_threshold_review_ready",
        "high_threshold": 0.85,
        "low_threshold": 0.7,
    }
    threshold_replay_artifact = json.loads(
        Path(payload["threshold_replay_path"]).read_text(encoding="utf-8")
    )
    threshold_replay_markdown = Path(
        payload["threshold_replay_markdown_path"]
    ).read_text(encoding="utf-8")
    audit_markdown = Path(payload["markdown_path"]).read_text(encoding="utf-8")
    for key, value in payload["threshold_replay"].items():
        assert threshold_replay_artifact[key] == value
    assert (
        threshold_replay_artifact["threshold_review_command"]
        == payload["threshold_review_command"]
    )
    assert (
        threshold_replay_artifact["threshold_review_next_step"]
        == "Run this command to review the validation replay summary before changing config."
    )
    assert "Processor Gate Threshold Replay Context" in threshold_replay_markdown
    assert "Mode: threshold_change_proposal_replay" in threshold_replay_markdown
    assert "Reviewed High Threshold: 0.85" in threshold_replay_markdown
    assert "Threshold Change Proposal:" in threshold_replay_markdown
    assert "Next Threshold Review Command" in threshold_replay_markdown
    assert "recommend_processor_gate_threshold_review.py" in threshold_replay_markdown
    assert "Processor Gate Threshold Replay Context" in audit_markdown
    assert "Next Threshold Review Command" in audit_markdown
    assert "recommend_processor_gate_threshold_review.py" in audit_markdown
    assert summary["inputs"]["high_threshold"] == 0.85
    assert summary["inputs"]["low_threshold"] == 0.7
    assert details["documents"][0]["paper_id"] == "paper-boundary"
    assert details["documents"][0]["replay_gate_decision"] == "APPROVED"


def test_audit_processor_gate_replay_drift_help_mentions_threshold_review() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "audit_processor_gate_replay_drift.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    normalized_help = " ".join(completed.stdout.split())
    assert "recommend_processor_gate_threshold_review.py" in normalized_help
    assert "Writes summary.json, details.json, and audit.md into the run directory." in normalized_help
    assert "--threshold-change-proposal" in normalized_help
    assert "--reviewed-high-threshold" in normalized_help
