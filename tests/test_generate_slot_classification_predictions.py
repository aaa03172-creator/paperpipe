from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.generate_slot_classification_predictions import run_generation


class _FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, str]] = []
        self._metrics: dict[str, object] = {}

    def is_available(self) -> bool:
        return True

    def classify_slot(self, paper: dict, current_slot: str) -> str:
        self.calls.append((paper, current_slot))
        title = str(paper.get("title") or "")
        if "multiplex" in title.lower():
            self._metrics = {
                "first_pass_predicted_slot": "Methods",
                "final_source": "first_pass",
                "adjudication_triggered": False,
                "adjudication_reason": None,
                "first_pass_confidence": 0.86,
            }
            return "Methods"
        self._metrics = {
            "first_pass_predicted_slot": "Clinical",
            "final_source": "adjudicated",
            "adjudication_triggered": True,
            "adjudication_reason": "signal_conflict",
            "first_pass_confidence": 0.74,
        }
        return "Clinical"

    def get_slot_classification_metrics(self) -> dict[str, object]:
        return dict(self._metrics)


def test_run_generation_writes_predictions_and_summary(tmp_path: Path) -> None:
    goldset_csv = tmp_path / "goldset.csv"
    goldset_csv.write_text(
        "\n".join(
            [
                "paper_id,doi,title,summary,full_text,current_slot,gold_slot",
                "paper-a,10.1000/a,Clinical cohort paper,Human biomarker cohort.,,mechanism,clinical",
                "paper-b,10.1000/b,Validation of a multiplex cytokine assay,Assay benchmark study.,Methods excerpt,methods,methods",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    provider = _FakeProvider()
    run_root = run_generation(
        goldset_csv_path=goldset_csv,
        out_dir=tmp_path / "out",
        run_id="slot_generation_test",
        provider=provider,
        feature_enabled=True,
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    predictions = [
        json.loads(line)
        for line in (run_root / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert summary["prediction_written_count"] == 2
    assert summary["status_counts"] == {"ok": 2}
    assert summary["input_richness_counts"] == {
        "title_summary": 1,
        "title_summary_full_text": 1,
    }
    assert len(predictions) == 2
    assert predictions[0]["prediction_source"] == "live_provider"
    assert predictions[1]["predicted_slot"] == "methods"
    assert details["documents"][0]["first_pass_predicted_slot"] == "clinical"
    assert details["documents"][0]["adjudication_triggered"] is True
    assert provider.calls[0][1] == "Mechanism"


def test_run_generation_marks_missing_current_slot_without_fallback(tmp_path: Path) -> None:
    goldset_csv = tmp_path / "goldset.csv"
    goldset_csv.write_text(
        "\n".join(
            [
                "paper_id,doi,title,summary,full_text,current_slot,gold_slot",
                "paper-a,10.1000/a,Clinical cohort paper,Human biomarker cohort.,,,,clinical",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    provider = _FakeProvider()
    run_root = run_generation(
        goldset_csv_path=goldset_csv,
        out_dir=tmp_path / "out",
        run_id="slot_generation_missing_current_slot",
        provider=provider,
        feature_enabled=True,
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    predictions_jsonl = (run_root / "predictions.jsonl").read_text(encoding="utf-8").strip()

    assert summary["prediction_written_count"] == 0
    assert summary["status_counts"] == {"missing_current_slot": 1}
    assert details["documents"][0]["prediction_status"] == "missing_current_slot"
    assert predictions_jsonl == ""


def test_run_generation_accepts_unknown_fallback_current_slot(tmp_path: Path) -> None:
    goldset_csv = tmp_path / "goldset.csv"
    goldset_csv.write_text(
        "\n".join(
            [
                "paper_id,doi,title,summary,full_text,current_slot,gold_slot",
                "paper-a,10.1000/a,Clinical cohort paper,Human biomarker cohort.,,,clinical",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    provider = _FakeProvider()
    run_root = run_generation(
        goldset_csv_path=goldset_csv,
        out_dir=tmp_path / "out",
        run_id="slot_generation_unknown_fallback",
        provider=provider,
        feature_enabled=True,
        fallback_current_slot="unknown",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))

    assert summary["prediction_written_count"] == 1
    assert summary["inputs"]["fallback_current_slot"] == "unknown"
    assert details["documents"][0]["current_slot"] == "unknown"
    assert provider.calls[0][1] == "Unknown"
