import json
from pathlib import Path

from scripts.eval.compare_eval import compare_eval
from scripts.eval.run_eval import run_quality_eval


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _valid_claimset(paper_id: str) -> dict:
    return {
        "doc_id": f"doc-{paper_id}",
        "claims": [
            {
                "claim_id": "CLM-001",
                "type": "efficacy",
                "statement": "Outcome improved by 20% (p<0.05).",
                "evidence_spans": [
                    {
                        "page": 1,
                        "chunk_id": "chunk-1",
                        "char_start": 5,
                        "char_end": 40,
                        "raw_text": "Outcome improved by 20% and p=0.02 in the treatment arm.",
                        "quote": "improved by 20% and p=0.02",
                        "rationale": "directly reports effect size and p-value",
                    }
                ],
                "limitations": ["small sample"],
                "confidence": 0.8,
            }
        ],
    }


def test_quality_eval_metrics_and_compare_promotion(tmp_path: Path) -> None:
    eval_jsonl = tmp_path / "splits" / "eval.jsonl"
    pred_jsonl = tmp_path / "pred" / "pred.jsonl"
    manual_jsonl = tmp_path / "manual" / "human_decisions.jsonl"
    snapshots_dir = tmp_path / "snapshots"

    _write_jsonl(
        eval_jsonl,
        [
            {"paper_id": "paper-1"},
            {"paper_id": "paper-2"},
            {"paper_id": "paper-3"},
        ],
    )
    _write_jsonl(
        pred_jsonl,
        [
            {"paper_id": "paper-1", "claimset": _valid_claimset("paper-1"), "summary": "Clean summary."},
            {
                "paper_id": "paper-2",
                "claimset": {"doc_id": "doc-paper-2", "claims": []},
                "summary": "No summary available",
            },
        ],
    )
    _write_jsonl(
        manual_jsonl,
        [
            {"paper_id": "paper-2", "resolution": "MANUAL_FIX"},
        ],
    )

    run_root = run_quality_eval(
        eval_jsonl=eval_jsonl,
        pred_jsonl=pred_jsonl,
        snapshots_dir=snapshots_dir,
        run_id="run_new",
        manual_decisions_jsonl=manual_jsonl,
    )

    metrics = json.loads((run_root / "metrics.json").read_text(encoding="utf-8"))
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    metadata = metrics["metadata"]

    assert summary["metadata"] == metadata
    assert metadata["schema_version"] == "eval_run_metadata.v1"
    assert metadata["harness"] == "scripts/eval/run_eval.py"
    assert metadata["run_id"] == "run_new"
    assert metadata["mode"] == "quality"
    assert metadata["payload_class"] == "local_only"
    assert metadata["provider"] == "deterministic"
    assert metadata["model"] is None
    assert metrics["total"] == 3
    assert metrics["schema_valid_rate"] == 2 / 3
    assert metrics["evidence_location_rate"] == 1 / 3
    assert metrics["summary_artifact_rate"] == 1 / 3
    assert metrics["manual_correction_rate"] == 1 / 3

    baseline_path = tmp_path / "baseline" / "metrics.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps(
            {
                "run_id": "baseline",
                "schema_valid_rate": 0.2,
                "evidence_location_rate": 0.2,
                "summary_artifact_rate": 0.2,
                "manual_correction_rate": 0.6,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    compare_out = tmp_path / "compare" / "report.json"
    baselines_dir = tmp_path / "baselines"
    report = compare_eval(
        baseline=baseline_path,
        new=run_root / "metrics.json",
        out=compare_out,
        promote_dir=baselines_dir,
    )

    assert report["decision"]["passed"] is True
    assert report["promotion"]["promoted"] is True
    promoted_metrics = Path(report["promotion"]["path"]) / "metrics.json"
    assert promoted_metrics.exists()


def test_compare_eval_rejects_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline_metrics.json"
    new = tmp_path / "new_metrics.json"
    out = tmp_path / "compare" / "report.json"

    baseline.write_text(
        json.dumps(
            {
                "run_id": "baseline",
                "schema_valid_rate": 0.8,
                "evidence_location_rate": 0.7,
                "summary_artifact_rate": 0.9,
                "manual_correction_rate": 0.1,
            }
        ),
        encoding="utf-8",
    )
    new.write_text(
        json.dumps(
            {
                "run_id": "new",
                "schema_valid_rate": 0.79,
                "evidence_location_rate": 0.7,
                "summary_artifact_rate": 0.9,
                "manual_correction_rate": 0.1,
            }
        ),
        encoding="utf-8",
    )

    report = compare_eval(baseline=baseline, new=new, out=out)

    assert report["decision"]["passed"] is False
    assert "schema_valid_rate" in report["decision"]["failed_checks"]
