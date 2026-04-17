import inspect

import src.cli as cli


class _RecordingConsole:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, *args, **_kwargs) -> None:
        self.lines.append(" ".join(str(arg) for arg in args))


def test_print_results_uses_clinical_data_payload_and_icon(monkeypatch) -> None:
    recorder = _RecordingConsole()
    monkeypatch.setattr(cli, "console", recorder)

    cli._print_results(
        [
            {
                "slot": "Clinical",
                "title": "Clinical Study",
                "ai_one_liner": "Useful summary",
                "clinical_data": {
                    "population": "Adults with biomarker-positive disease",
                    "effect": "Median survival improved",
                },
            }
        ]
    )

    output = "\n".join(recorder.lines)
    assert "🏥 [Clinical] Clinical Study" in output
    assert "Clinical Data Extracted" in output
    assert "population: Adults with biomarker-positive disease" in output
    assert "effect: Median survival improved" in output


def test_repair_stats_help_mentions_historical_seed_set() -> None:
    paper_id_option = inspect.signature(cli.repair_stats).parameters["paper_id"].default

    assert paper_id_option.help is not None
    assert "curated historical 3-paper repair seed set" in paper_id_option.help
