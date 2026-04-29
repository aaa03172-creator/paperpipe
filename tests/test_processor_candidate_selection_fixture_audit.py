from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.audit_processor_candidate_selection_fixture import run_audit


def test_processor_candidate_selection_fixture_audit_writes_artifacts(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/processor_candidate_selection_pools_20260429.json")

    run_root = run_audit(
        fixture_path=fixture,
        out_dir=tmp_path,
        run_id="candidate_selection_fixture_audit_test",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    markdown = (run_root / "audit.md").read_text(encoding="utf-8")

    assert summary["schema_version"] == "processor_candidate_selection_fixture_audit.v1"
    assert summary["metrics"]["pool_count"] == 3
    assert summary["metrics"]["matched_count"] == 3
    assert summary["metrics"]["mismatch_count"] == 0
    assert summary["metrics"]["accuracy"] == 1.0
    assert summary["pools_with_mismatch"] == []
    assert len(details["pools"]) == 3
    assert details["pools"][0]["matches_expected"] is True
    assert details["pools"][0]["top_candidates"][0]["score_breakdown"]["final_score"] > 0
    assert "Processor Candidate Selection Fixture Audit" in markdown
    assert "clinical_pubmed_metadata_beats_preprint_freshness" in markdown
