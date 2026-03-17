import json
from pathlib import Path

from src.services.stats_repair import seed_for_paper, seed_stats_reports_from_claimset


def _write_claimset(run_dir: Path) -> None:
    payload = {
        "doc_id": "paper_001",
        "claims": [
            {
                "claim_id": "CLM-001",
                "type": "efficacy",
                "statement": "Treatment improved memory score by 18% (p=0.01).",
                "confidence": 0.9,
                "limitations": [],
                "evidence_spans": [
                    {
                        "page": 0,
                        "chunk_id": "chunk_1",
                        "raw_text": "Treatment improved memory score by 18% (p=0.01).",
                        "quote": "improved memory score by 18% (p=0.01)",
                        "rationale": "Direct statement in result paragraph.",
                        "section": "results",
                    }
                ],
            }
        ],
    }
    (run_dir / "claimset.json").write_text(json.dumps(payload), encoding="utf-8")


def test_seed_for_paper_writes_stats_and_bootstrap_flags(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "storage" / "artifacts"
    run_dir = artifacts_root / "paper_001" / "run_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_claimset(run_dir)
    (run_dir / "bootstrap_meta.json").write_text(json.dumps({"paper_id": "paper_001"}), encoding="utf-8")

    result = seed_for_paper(
        artifacts_root=artifacts_root,
        paper_id="paper_001",
        max_checks=5,
        write_bootstrap_meta=True,
        skip_existing=False,
        dry_run=False,
    )

    assert result.status == "seeded"
    assert result.checks == 1
    stats_payload = json.loads((run_dir / "stats_report.json").read_text(encoding="utf-8"))
    assert stats_payload["run_id"] == "run_001"
    assert len(stats_payload["checks"]) == 1
    assert stats_payload["checks"][0]["method"] == "claimset_fallback"
    assert stats_payload["checks"][0]["verdict"] == "unverifiable"

    bootstrap = json.loads((run_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
    assert bootstrap["stats_report_written"] is True
    assert bootstrap["artifact_stats_written"] is True


def test_seed_stats_reports_skip_existing(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "storage" / "artifacts"
    run_dir = artifacts_root / "paper_001" / "run_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_claimset(run_dir)
    (run_dir / "stats_report.json").write_text(json.dumps({"doc_id": "x", "run_id": "run_001", "checks": []}), encoding="utf-8")

    results = seed_stats_reports_from_claimset(
        paper_ids=["paper_001"],
        artifacts_root=artifacts_root,
        skip_existing=True,
        dry_run=False,
    )

    assert len(results) == 1
    assert results[0].status == "skipped"
    assert results[0].reason == "stats_exists"


def test_seed_for_paper_prefers_existing_legacy_dir_for_unsafe_paper_id(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "storage" / "artifacts"
    legacy_run_dir = artifacts_root / "doi:10.1000" / "test" / "run_legacy"
    hashed_run_dir = artifacts_root / "paper_deadbeefdeadbeef" / "run_hashed"
    legacy_run_dir.mkdir(parents=True, exist_ok=True)
    hashed_run_dir.mkdir(parents=True, exist_ok=True)

    _write_claimset(legacy_run_dir)
    (legacy_run_dir / "bootstrap_meta.json").write_text(json.dumps({"paper_id": "doi:10.1000/test"}), encoding="utf-8")
    _write_claimset(hashed_run_dir)

    result = seed_for_paper(
        artifacts_root=artifacts_root,
        paper_id="doi:10.1000/test",
        max_checks=5,
        write_bootstrap_meta=False,
        skip_existing=False,
        dry_run=False,
    )

    assert result.status == "seeded"
    assert result.run_id == "run_legacy"
    assert (legacy_run_dir / "stats_report.json").exists()
    assert not (hashed_run_dir / "stats_report.json").exists()
