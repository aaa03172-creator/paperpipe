from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval.generate_slot_classification_prompt_candidate_predictions import (
    load_candidate_prompt_template,
    run_candidate_generation,
)


class _FakeCandidateProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def is_available(self) -> bool:
        return True

    def _paper_evidence_bundle(
        self,
        paper: dict,
        *,
        current_slot: str | None = None,
        max_chars: int = 6000,
        per_section_chars: int = 1200,
    ) -> str:
        return f"Title: {paper.get('title')}\nCurrent Slot: {current_slot}"

    def _make_request(self, task: str, prompt: str, is_json: bool = False, **_: object) -> str:
        self.prompts.append(prompt)
        predicted = "Methods" if "multiplex" in prompt.lower() else "Clinical"
        return json.dumps(
            {
                "reasoning": "candidate reasoning",
                "domain_in_scope": True,
                "clinical_signal": predicted == "Clinical",
                "methods_signal": predicted == "Methods",
                "mechanism_signal": False,
                "predicted_slot": predicted,
                "confidence": 0.88,
                "needs_adjudication": False,
            }
        )

    def _extract_json(self, response_content: str) -> dict:
        return json.loads(response_content)

    def _normalize_slot_prediction(self, value: object) -> str | None:
        normalized = str(value or "").strip().lower()
        if normalized == "clinical":
            return "Clinical"
        if normalized == "methods":
            return "Methods"
        if normalized == "mechanism":
            return "Mechanism"
        return None


def test_load_candidate_prompt_template_extracts_fenced_text(tmp_path: Path) -> None:
    prompt_path = tmp_path / "candidate.md"
    prompt_path.write_text(
        "# Candidate\n\n```text\nUse this.\n{evidence_bundle}\n```\n",
        encoding="utf-8",
    )

    assert load_candidate_prompt_template(prompt_path) == "Use this.\n{evidence_bundle}"


def test_load_candidate_prompt_template_requires_evidence_placeholder(tmp_path: Path) -> None:
    prompt_path = tmp_path / "candidate.md"
    prompt_path.write_text("```text\nNo placeholder.\n```\n", encoding="utf-8")

    with pytest.raises(ValueError, match="candidate_prompt_missing_evidence_bundle_placeholder"):
        load_candidate_prompt_template(prompt_path)


def test_run_candidate_generation_writes_audit_compatible_predictions(tmp_path: Path) -> None:
    goldset_csv = tmp_path / "goldset.csv"
    candidate_prompt = tmp_path / "candidate_prompt.md"
    goldset_csv.write_text(
        "\n".join(
            [
                "paper_id,doi,title,summary,full_text,current_slot,gold_slot",
                "paper-a,10.1000/a,Clinical cohort paper,Human biomarker cohort.,,,clinical",
                "paper-b,10.1000/b,Validation of a multiplex cytokine assay,Assay benchmark study.,Methods excerpt,,methods",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    candidate_prompt.write_text(
        "\n".join(
            [
                "# Candidate",
                "",
                "```text",
                "Classify this paper.",
                "{evidence_bundle}",
                "Return JSON STRICTLY.",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    provider = _FakeCandidateProvider()
    run_root = run_candidate_generation(
        goldset_csv_path=goldset_csv,
        candidate_prompt_path=candidate_prompt,
        out_dir=tmp_path / "out",
        run_id="candidate_generation_test",
        candidate_id="candidate-test",
        provider=provider,
        fallback_current_slot="unknown",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    predictions = [
        json.loads(line)
        for line in (run_root / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert summary["schema_version"] == "slot_classification_prompt_candidate_prediction_generation.v1"
    assert summary["candidate_id"] == "candidate-test"
    assert summary["prediction_written_count"] == 2
    assert summary["status_counts"] == {"ok": 2}
    assert predictions[0]["prediction_source"] == "prompt_candidate"
    assert predictions[0]["candidate_id"] == "candidate-test"
    assert predictions[1]["predicted_slot"] == "methods"
    assert details["documents"][0]["current_slot"] == "unknown"
    assert details["documents"][0]["final_source"] == "candidate_prompt_first_pass"
    assert "{evidence_bundle}" not in provider.prompts[0]
    assert "Current Slot: Unknown" in provider.prompts[0]
