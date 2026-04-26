from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.materialize_pubtator_silver_bootstrap import materialize_pubtator_silver_bootstrap


def test_materialize_pubtator_silver_bootstrap_replays_repo_manifest(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = repo_root / "goldset" / "manifests" / "pubtator_silver_repo_grounded_pilot_20260409.json"

    run_root = materialize_pubtator_silver_bootstrap(
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        run_id="pubtator-batch",
    )

    generated_manifest = json.loads((run_root / "generated_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((run_root / "metrics.json").read_text(encoding="utf-8"))

    assert generated_manifest["source_manifest"] == str(manifest_path)
    assert len(generated_manifest["documents"]) == 2
    assert metrics["success_count"] == 2

    rows_by_paper = {row["paper_id"]: row for row in metrics["rows"]}
    assert rows_by_paper["repo-pubtator-egfr"]["entity_record_count"] == 4
    assert rows_by_paper["repo-pubtator-egfr"]["relation_record_count"] == 1
    assert rows_by_paper["repo-pubtator-kras"]["entity_record_count"] == 3
    assert rows_by_paper["repo-pubtator-kras"]["relation_record_count"] == 1
    assert rows_by_paper["repo-pubtator-kras"]["warnings"] == ["silver_bootstrap:pubtator_central"]

    bundle_path = Path(rows_by_paper["repo-pubtator-kras"]["bundle_path"])
    assert bundle_path.exists()
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["doc_id"] == "repo-pubtator-kras"
