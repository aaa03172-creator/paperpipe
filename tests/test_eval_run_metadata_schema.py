from datetime import datetime

from src.schemas.eval_harness import EvalRunMetadata, build_eval_run_metadata


def test_eval_run_metadata_model_serializes_current_contract() -> None:
    metadata = build_eval_run_metadata(
        harness="scripts/eval/run_eval.py",
        run_id="run-001",
        mode="snapshot",
        eval_id="eval-fixture",
        case_ids=["case-1", "case-2"],
        subset="smoke",
    )

    payload = metadata.model_dump(mode="json")
    assert payload["schema_version"] == "eval_run_metadata.v1"
    assert payload["harness"] == "scripts/eval/run_eval.py"
    assert payload["run_id"] == "run-001"
    assert payload["mode"] == "snapshot"
    assert payload["payload_class"] == "local_only"
    assert payload["provider"] == "deterministic"
    assert payload["model"] is None
    assert payload["eval_id"] == "eval-fixture"
    assert payload["case_ids"] == ["case-1", "case-2"]
    assert payload["subset"] == "smoke"
    assert payload["generated_at_utc"].endswith("Z")


def test_eval_run_metadata_accepts_existing_json_payload() -> None:
    payload = {
        "schema_version": "eval_run_metadata.v1",
        "harness": "scripts/eval/run_eval.py",
        "run_id": "run-001",
        "mode": "quality",
        "generated_at_utc": "2026-05-31T00:00:00Z",
        "payload_class": "local_only",
        "provider": "deterministic",
        "model": None,
        "eval_id": None,
        "case_ids": [],
        "subset": None,
    }

    metadata = EvalRunMetadata.model_validate(payload)
    assert isinstance(metadata.generated_at_utc, datetime)
    assert metadata.model_dump(mode="json") == payload
