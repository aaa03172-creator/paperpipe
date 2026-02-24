import json
import sqlite3
from pathlib import Path

from scripts.extract_teacher_candidates import extract_teacher_candidates


def _init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            status TEXT,
            confidence REAL,
            summary TEXT,
            feedback_json TEXT,
            prompt_version TEXT,
            pdf_path TEXT,
            updated_at TEXT
        );
        CREATE TABLE review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT,
            decision TEXT,
            reason TEXT,
            resolved_at TEXT
        );
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT,
            status TEXT
        );
        """
    )

    conn.execute(
        """
        INSERT INTO papers (paper_id, status, confidence, summary, feedback_json, prompt_version, pdf_path, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            "paper-001",
            "DONE",
            0.42,
            "No summary available",
            None,
            "prompt.v1",
            "/tmp/paper-001.pdf",
        ),
    )
    conn.execute(
        """
        INSERT INTO review_queue (paper_id, decision, reason, resolved_at)
        VALUES (?, ?, ?, NULL)
        """,
        ("paper-001", "NEEDS_READER", "missing claimset"),
    )
    conn.commit()
    conn.close()


def test_extract_teacher_candidates_writes_manifest_and_bundle_files(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    artifacts_root = tmp_path / "artifacts"
    _init_db(db_path)

    bundles = extract_teacher_candidates(
        db_path=db_path,
        artifacts_root=artifacts_root,
        extraction_run_id="run-x",
        low_confidence_threshold=0.7,
        limit=10,
        paper_id_filter={"paper-001"},
    )

    assert len(bundles) == 1
    bundle_dir = bundles[0]
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["paper_id"] == "paper-001"
    assert manifest["git_commit"]
    assert "model" in manifest
    assert manifest["prompt_version"] == "prompt.v1"
    assert manifest["created_at"]
    assert "CLAIMSET_MISSING_OR_INVALID" in manifest["candidate_reason_codes"]

    assert (bundle_dir / "input_chunks.jsonl").exists()
    assert (bundle_dir / "tables.json").exists()
    assert (bundle_dir / "prior_output.json").exists()
