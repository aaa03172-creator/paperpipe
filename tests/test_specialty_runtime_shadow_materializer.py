from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.materialize_specialty_runtime_shadow import run_specialty_shadow_materializer
from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2
from src.schemas.core import SpecialtyTrialExtraction


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _gold_payload(*, paper_id: str, include: bool, mci_only: bool) -> dict:
    return SpecialtyTrialExtraction(
        paper_id=paper_id,
        citation={
            "title": f"Title for {paper_id}",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
        },
        population={"mci_only": mci_only, "n_total": 42},
        intervention={"product_name": "Avagacestat"},
        comparator={"description": "Placebo"},
        outcomes={"cognition": [{"name": "ADAS-Cog-12", "effect_direction": "no_change"}]},
        eligibility_flags={"include_for_mci_mct_review": include},
        extraction_quality={"confidence": "high"},
    ).model_dump(mode="json")


def _doc_artifact_payload(title: str) -> dict:
    return DocumentArtifactV2(
        document_id=title,
        meta=ArtifactMetaV2(title=title, authors=["Kim"], year=2026, journal="Test Journal", source_ref=title),
        pages=[
            PageV2(
                page_index=0,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id="b1",
                        lines=[
                            LineV2(
                                line_id="l1",
                                text="Abstract Background randomized placebo trial in mild cognitive impairment.",
                                spans=[SpanV2(span_id="s1", text="Abstract Background randomized placebo trial in mild cognitive impairment.")],
                            )
                        ],
                    )
                ],
            ),
            PageV2(
                page_index=1,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id="b2",
                        lines=[
                            LineV2(
                                line_id="l2",
                                text="Design, Setting, and Participants 42 participants randomized to avagacestat or placebo.",
                                spans=[SpanV2(span_id="s2", text="Design, Setting, and Participants 42 participants randomized to avagacestat or placebo.")],
                            )
                        ],
                    )
                ],
            ),
        ],
        tables=[],
    ).model_dump(mode="json")


def test_run_specialty_shadow_materializer_writes_compare_manifest_for_eligible_doc(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    artifacts_root = tmp_path / "artifacts"
    out_dir = tmp_path / "out"
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    eligible_gold = gold_dir / "paper-eligible.json"
    ineligible_gold = gold_dir / "paper-ineligible.json"
    _write_json(eligible_gold, _gold_payload(paper_id="paper-eligible", include=True, mci_only=True))
    _write_json(ineligible_gold, _gold_payload(paper_id="paper-ineligible", include=False, mci_only=False))
    _write_json(
        manifest_path,
        {
            "schema_version": "extraction_regression_manifest.v1",
            "documents": [
                {"paper_id": "paper-eligible", "gold_path": str(eligible_gold), "gold_source_paths": []},
                {"paper_id": "paper-ineligible", "gold_path": str(ineligible_gold), "gold_source_paths": []},
            ],
        },
    )

    run_dir = artifacts_root / "paper-eligible" / "run_20260328_000001"
    _write_json(run_dir / "document_artifact.json", _doc_artifact_payload("Eligible Trial"))

    class FakeProvider:
        def is_available(self) -> bool:
            return True

        def extract_specialty_trial_data(self, paper_payload, methods_snippet):
            assert paper_payload["title"] == "Title for paper-eligible"
            assert "Design, Setting, and Participants" in methods_snippet
            return SpecialtyTrialExtraction.model_validate(_gold_payload(paper_id="paper-eligible", include=True, mci_only=True))

        def get_specialty_trial_extraction_raw_response(self):
            return "{\"paper_id\":\"paper-eligible\"}"

    run_root = run_specialty_shadow_materializer(
        manifest_path=manifest_path,
        artifacts_root=artifacts_root,
        out_dir=out_dir,
        run_id="shadow_ok",
        provider=FakeProvider(),
        feature_enabled=False,
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    generated_manifest = json.loads((run_root / "generated_manifest.json").read_text(encoding="utf-8"))

    assert summary["runtime_feature_enabled"] is False
    assert summary["provider_available"] is True
    assert summary["eligible_document_count"] == 1
    assert summary["prediction_written_count"] == 1
    assert summary["raw_response_written_count"] == 1
    assert summary["generated_manifest_document_count"] == 1
    assert summary["status_counts"]["skipped_ineligible"] == 1
    assert [item["paper_id"] for item in generated_manifest["documents"]] == ["paper-eligible"]
    assert [item["status"] for item in details["documents"]] == ["prediction_written", "skipped_ineligible"]
    assert details["documents"][0]["raw_response_chars"] > 0
    assert Path(str(details["documents"][0]["raw_response_path"])).exists()


def test_run_specialty_shadow_materializer_records_empty_prediction(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    artifacts_root = tmp_path / "artifacts"
    out_dir = tmp_path / "out"
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    gold_path = gold_dir / "paper-eligible.json"
    _write_json(gold_path, _gold_payload(paper_id="paper-eligible", include=True, mci_only=True))
    _write_json(
        manifest_path,
        {
            "schema_version": "extraction_regression_manifest.v1",
            "documents": [
                {"paper_id": "paper-eligible", "gold_path": str(gold_path), "gold_source_paths": []},
            ],
        },
    )
    run_dir = artifacts_root / "paper-eligible" / "run_20260328_000001"
    _write_json(run_dir / "document_artifact.json", _doc_artifact_payload("Eligible Trial"))

    class EmptyProvider:
        def is_available(self) -> bool:
            return True

        def extract_specialty_trial_data(self, _paper_payload, _methods_snippet):
            return None

    run_root = run_specialty_shadow_materializer(
        manifest_path=manifest_path,
        artifacts_root=artifacts_root,
        out_dir=out_dir,
        run_id="shadow_empty",
        provider=EmptyProvider(),
        feature_enabled=False,
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    generated_manifest = json.loads((run_root / "generated_manifest.json").read_text(encoding="utf-8"))

    assert summary["prediction_written_count"] == 0
    assert summary["status_counts"]["prediction_empty"] == 1
    assert generated_manifest["documents"] == []
    assert details["documents"][0]["status"] == "prediction_empty"


def test_run_specialty_shadow_materializer_records_schema_invalid_prediction(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    artifacts_root = tmp_path / "artifacts"
    out_dir = tmp_path / "out"
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    gold_path = gold_dir / "paper-eligible.json"
    _write_json(gold_path, _gold_payload(paper_id="paper-eligible", include=True, mci_only=True))
    _write_json(
        manifest_path,
        {
            "schema_version": "extraction_regression_manifest.v1",
            "documents": [
                {"paper_id": "paper-eligible", "gold_path": str(gold_path), "gold_source_paths": []},
            ],
        },
    )
    run_dir = artifacts_root / "paper-eligible" / "run_20260328_000001"
    _write_json(run_dir / "document_artifact.json", _doc_artifact_payload("Eligible Trial"))

    class InvalidProvider:
        def is_available(self) -> bool:
            return True

        def extract_specialty_trial_data(self, _paper_payload, _methods_snippet):
            return None

        def get_specialty_trial_extraction_raw_response(self):
            return "{\"citation\":{\"authors\":[\"Kim\"]},\"intervention\":{\"category\":\"γ-secretase inhibitor\"}}"

        def get_specialty_trial_extraction_diagnostic(self):
            return {
                "status": "schema_invalid",
                "error": "\n".join(
                    [
                        "ValidationError: 2 validation errors for SpecialtyTrialExtraction",
                        "citation.authors_first",
                        "  Field required [type=missing]",
                        "intervention.category",
                        "  Input should be 'mct' or 'unknown' [type=literal_error]",
                    ]
                ),
            }

    run_root = run_specialty_shadow_materializer(
        manifest_path=manifest_path,
        artifacts_root=artifacts_root,
        out_dir=out_dir,
        run_id="shadow_schema_invalid",
        provider=InvalidProvider(),
        feature_enabled=False,
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    generated_manifest = json.loads((run_root / "generated_manifest.json").read_text(encoding="utf-8"))

    assert summary["prediction_written_count"] == 0
    assert summary["raw_response_written_count"] == 1
    assert summary["status_counts"]["prediction_empty"] == 0
    assert summary["status_counts"]["prediction_schema_invalid"] == 1
    assert summary["schema_invalid_reason_counts"] == {
        "invalid_intervention_category": 1,
        "missing_citation_authors_first": 1,
    }
    assert generated_manifest["documents"] == []
    assert details["documents"][0]["status"] == "prediction_schema_invalid"
    assert details["documents"][0]["provider_diagnostic_status"] == "schema_invalid"
    assert details["documents"][0]["provider_diagnostic_reason_codes"] == [
        "missing_citation_authors_first",
        "invalid_intervention_category",
    ]
    assert details["documents"][0]["raw_response_chars"] > 0
    assert Path(str(details["documents"][0]["raw_response_path"])).exists()
    assert "ValidationError:" in str(details["documents"][0]["error"])


def test_run_specialty_shadow_materializer_rejects_pairing_mismatch(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    artifacts_root = tmp_path / "artifacts"
    out_dir = tmp_path / "out"
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    gold_path = gold_dir / "paper-eligible.json"
    _write_json(gold_path, _gold_payload(paper_id="paper-eligible", include=True, mci_only=True))
    _write_json(
        manifest_path,
        {
            "schema_version": "extraction_regression_manifest.v1",
            "documents": [
                {"paper_id": "paper-eligible", "gold_path": str(gold_path), "gold_source_paths": []},
            ],
        },
    )
    run_dir = artifacts_root / "paper-eligible" / "run_20260328_000001"
    _write_json(run_dir / "document_artifact.json", _doc_artifact_payload("Eligible Trial"))

    class MismatchProvider:
        def is_available(self) -> bool:
            return True

        def extract_specialty_trial_data(self, _paper_payload, _methods_snippet):
            payload = _gold_payload(paper_id="doi:10.1234/example", include=True, mci_only=True)
            return SpecialtyTrialExtraction.model_validate(payload)

    run_root = run_specialty_shadow_materializer(
        manifest_path=manifest_path,
        artifacts_root=artifacts_root,
        out_dir=out_dir,
        run_id="shadow_pairing_mismatch",
        provider=MismatchProvider(),
        feature_enabled=False,
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    generated_manifest = json.loads((run_root / "generated_manifest.json").read_text(encoding="utf-8"))

    assert summary["prediction_written_count"] == 0
    assert summary["generated_manifest_document_count"] == 0
    assert summary["status_counts"]["pairing_mismatch"] == 1
    assert generated_manifest["documents"] == []
    assert details["documents"][0]["status"] == "pairing_mismatch"
    assert details["documents"][0]["prediction_paper_id"] == "doi:10.1234/example"
