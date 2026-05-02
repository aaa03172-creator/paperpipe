from __future__ import annotations

import json
from pathlib import Path

from scripts.backfill_highlight_source import (
    backfill_claimset_payload,
    collect_claimset_files,
    infer_highlight_source,
    run_backfill,
)


def test_infer_highlight_source_prefers_bbox() -> None:
    assert infer_highlight_source({"bbox_pdf": [1, 2, 3, 4], "raw_text": "x"}) == "bbox"
    assert infer_highlight_source({"bbox_pct": {"left": 1, "top": 2, "width": 3, "height": 4}, "quote": "x"}) == "bbox"


def test_infer_highlight_source_text_match_and_approx() -> None:
    assert infer_highlight_source({"raw_text": "evidence quote"}) == "text_match"
    assert infer_highlight_source({"quote": "table says..."}) == "text_match"
    assert infer_highlight_source({}) == "approx"


def test_backfill_claimset_payload_updates_only_missing_entries() -> None:
    payload = {
        "claims": [
            {
                "claim_id": "c1",
                "evidence_spans": [
                    {"raw_text": "alpha", "page": 1},
                    {"raw_text": "beta", "highlight_source": "text_match"},
                    {"bbox_pct": {"left": 5, "top": 6, "width": 7, "height": 8}},
                ],
            }
        ]
    }
    changed, updated, scanned = backfill_claimset_payload(payload)
    assert changed is True
    assert updated == 2
    assert scanned == 3
    spans = payload["claims"][0]["evidence_spans"]
    assert spans[0]["highlight_source"] == "text_match"
    assert spans[1]["highlight_source"] == "text_match"
    assert spans[2]["highlight_source"] == "bbox"


def test_collect_claimset_files_prefers_resolved_over_legacy(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "paper-a" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    resolved = run_dir / "claimset.resolved.json"
    legacy = run_dir / "claimset.json"
    resolved.write_text("{}", encoding="utf-8")
    legacy.write_text("{}", encoding="utf-8")

    files_default = list(collect_claimset_files(artifacts, include_legacy=False))
    assert files_default == [resolved]

    files_with_legacy = list(collect_claimset_files(artifacts, include_legacy=True))
    assert files_with_legacy == [resolved, legacy]


def test_run_backfill_dry_run_and_apply(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "paper-b" / "run-2"
    run_dir.mkdir(parents=True, exist_ok=True)
    target = run_dir / "claimset.json"
    target.write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "c1",
                        "evidence_spans": [{"quote": "Some evidence"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    dry = run_backfill(artifacts, apply_changes=False, include_legacy=False)
    assert dry.files_scanned == 1
    assert dry.files_updated == 1
    assert dry.spans_updated == 1
    payload_after_dry = json.loads(target.read_text(encoding="utf-8"))
    assert "highlight_source" not in payload_after_dry["claims"][0]["evidence_spans"][0]

    backup_dir = tmp_path / "backups"
    applied = run_backfill(artifacts, apply_changes=True, include_legacy=False, backup_dir=backup_dir)
    assert applied.files_updated == 1
    assert applied.files_backed_up == 1
    payload_after_apply = json.loads(target.read_text(encoding="utf-8"))
    assert payload_after_apply["claims"][0]["evidence_spans"][0]["highlight_source"] == "text_match"
    backup_payload = json.loads((backup_dir / "paper-b" / "run-2" / "claimset.json").read_text(encoding="utf-8"))
    assert "highlight_source" not in backup_payload["claims"][0]["evidence_spans"][0]
