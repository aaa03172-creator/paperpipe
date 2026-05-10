#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _schema_contract(root: Path) -> dict[str, object]:
    path = root / "src" / "schemas" / "meeting_pack.py"
    text = _read_text(path)
    checks = {
        "schema_file_present": path.exists(),
        "layer_present": 'layer: Literal["user_facing_artifact"] = "user_facing_artifact"' in text,
        "canonical_status_present": 'canonical_status: Literal["non_canonical"] = "non_canonical"' in text,
        "readiness_present": 'readiness: MeetingPackReadiness = "evidence_backed"' in text,
        "generation_request_present": "generation_request: MeetingPackRequestSnapshot | None = None" in text,
        "source_items_present": "source_items: list[MeetingPackSourceItem] = Field(default_factory=list)" in text,
        "retrieval_trace_present": (
            "retrieval_trace: list[MeetingPackRetrievalTraceEntry] = Field(default_factory=list)" in text
        ),
        "evidence_refs_present": "evidence_refs: list[MeetingPackEvidenceRef] = Field(default_factory=list)" in text,
        "artifact_brief_present": "artifact_brief: ArtifactBrief | None = None" in text,
        "artifact_brief_review_present": "artifact_brief_review: ArtifactPlanReview | None = None" in text,
        "validation_markdown_sync_present": "markdown_sync: MeetingPackMarkdownSync" in text,
        "validation_regenerate_strategy_present": "regenerate_strategy: MeetingPackRegenerateStrategy" in text,
    }
    return {"ready": all(checks.values()), **checks}


def _store_contract(root: Path) -> dict[str, object]:
    path = root / "src" / "meeting_packs" / "store.py"
    text = _read_text(path)
    checks = {
        "store_file_present": path.exists(),
        "json_filename_present": '"meeting_pack.json"' in text,
        "markdown_filename_present": '"meeting_pack.md"' in text,
        "save_bundle_present": "def save_meeting_pack_bundle(" in text,
        "load_json_present": "def load_meeting_pack(" in text,
        "load_markdown_present": "def load_meeting_pack_markdown(" in text,
        "save_artifact_json_present": "def save_meeting_pack_artifact_json(" in text,
        "rollback_restore_present": "_restore_optional_text(" in text,
        "cleanup_empty_dir_present": "_remove_empty_dir(" in text,
    }
    return {"ready": all(checks.values()), **checks}


def _renderer_contract(root: Path) -> dict[str, object]:
    path = root / "src" / "meeting_packs" / "renderer.py"
    text = _read_text(path)
    checks = {
        "renderer_file_present": path.exists(),
        "layer_line_present": 'f"- Layer: {pack.layer}"' in text,
        "canonical_status_line_present": 'f"- Canonical status: {pack.canonical_status}"' in text,
        "readiness_line_present": 'f"- Readiness: {pack.readiness}"' in text,
        "sources_line_present": 'f"- Sources: {source_refs}"' in text,
        "artifact_brief_section_present": '"## Artifact Brief"' in text,
        "artifact_brief_review_section_present": '"## Artifact Brief Review"' in text,
        "promotion_guardrail_section_present": '"## Promotion guardrail"' in text,
        "promotion_guardrail_warning_present": "derived user-facing artifact, not canonical scientific truth" in text,
    }
    return {"ready": all(checks.values()), **checks}


def _route_contract(root: Path) -> dict[str, object]:
    path = root / "backend" / "routers" / "meeting_packs.py"
    text = _read_text(path)
    checks = {
        "router_file_present": path.exists(),
        "generate_route_present": '@router.post("/generate"' in text,
        "list_route_present": '@router.get("", response_model=MeetingPackListResponse)' in text,
        "get_route_present": '@router.get("/{pack_id}", response_model=MeetingPackResponse)' in text,
        "trace_route_present": '@router.get("/{pack_id}/trace", response_model=MeetingPackTraceResponse)' in text,
        "validate_route_present": (
            '@router.get("/{pack_id}/validate", response_model=MeetingPackValidationResponse)' in text
        ),
        "regenerate_route_present": '@router.post("/{pack_id}/regenerate", response_model=MeetingPackResponse)' in text,
        "rerender_route_present": '@router.post("/{pack_id}/rerender", response_model=MeetingPackResponse)' in text,
        "outcome_route_present": '@router.post("/{pack_id}/outcome")' in text,
        "review_route_present": '@router.post("/{pack_id}/review")' in text,
        "markdown_route_present": '@router.get("/{pack_id}/markdown", response_class=PlainTextResponse)' in text,
    }
    return {"ready": all(checks.values()), **checks}


def _guardrail_contract(root: Path) -> dict[str, object]:
    schema_test_path = root / "tests" / "test_meeting_pack_schema.py"
    store_test_path = root / "tests" / "test_meeting_pack_store.py"
    service_test_path = root / "tests" / "test_meeting_pack_service.py"
    api_test_path = root / "tests" / "test_meeting_pack_api.py"
    handoff_test_path = root / "tests" / "test_meeting_pack_handoff_artifacts.py"
    verify_script_path = root / "scripts" / "run_meeting_pack_verify.sh"
    real_smoke_script_path = root / "scripts" / "check_meeting_pack_real_smoke.py"
    storage_sync_script_path = root / "scripts" / "check_meeting_pack_storage_sync.py"

    schema_test_text = _read_text(schema_test_path)
    store_test_text = _read_text(store_test_path)
    service_test_text = _read_text(service_test_path)
    api_test_text = _read_text(api_test_path)
    handoff_test_text = _read_text(handoff_test_path)
    verify_script_text = _read_text(verify_script_path)
    real_smoke_script_text = _read_text(real_smoke_script_path)

    checks = {
        "schema_test_present": schema_test_path.exists(),
        "store_test_present": store_test_path.exists(),
        "service_test_present": service_test_path.exists(),
        "api_test_present": api_test_path.exists(),
        "handoff_test_present": handoff_test_path.exists(),
        "verify_script_present": verify_script_path.exists(),
        "real_smoke_script_present": real_smoke_script_path.exists(),
        "storage_sync_script_present": storage_sync_script_path.exists(),
        "schema_contract_assertions_present": (
            'assert pack.layer == "user_facing_artifact"' in schema_test_text
            and 'assert response.validation.regenerate_strategy == "legacy_source_items"' in schema_test_text
            and 'assert response.markdown_sync.status == "drifted"' in schema_test_text
        ),
        "store_contract_assertions_present": (
            'assert loaded.layer == "user_facing_artifact"' in store_test_text
            and 'assert loaded.canonical_status == "non_canonical"' in store_test_text
            and '"quality_gate.json"' in store_test_text
        ),
        "service_contract_assertions_present": (
            'assert response.pack.layer == "user_facing_artifact"' in service_test_text
            and 'assert response.pack.canonical_status == "non_canonical"' in service_test_text
            and 'assert response.markdown_sync.status == "in_sync"' in service_test_text
            and 'assert response.pack.artifact_brief_review.overall_status == "pass"' in service_test_text
            and 'assert stored.pack.retrieval_trace == response.pack.retrieval_trace' in service_test_text
            and '"acceptance_contract.json"' in service_test_text
            and '"quality_gate.json"' in service_test_text
        ),
        "api_contract_assertions_present": (
            'assert generate.json()["pack"]["layer"] == "user_facing_artifact"' in api_test_text
            and 'assert generate.json()["pack"]["canonical_status"] == "non_canonical"' in api_test_text
            and 'assert generate.json()["markdown_sync"]["status"] == "in_sync"' in api_test_text
        ),
        "handoff_contract_assertions_present": (
            'assert contract.operator_contract["regenerate_strategy_snapshot"] == "saved_request"' in handoff_test_text
            and 'assert gate.discussion_ready is True' in handoff_test_text
            and '"TRACE_MISSING" in gate.reason_codes' in handoff_test_text
        ),
        "verify_lane_assertions_present": (
            "scripts/check_meeting_pack_real_smoke.py" in verify_script_text
            and "scripts/check_meeting_pack_storage_sync.py" in verify_script_text
            and "--require-regenerable" in verify_script_text
        ),
        "real_smoke_readiness_assertion_present": "expected evidence_backed readiness" in real_smoke_script_text,
    }
    return {"ready": all(checks.values()), **checks}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize whether the current repo still satisfies the bounded meeting-pack partial manifest "
            "conformance contract."
        )
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to inspect. Default: current working directory.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    schema_contract = _schema_contract(root)
    store_contract = _store_contract(root)
    renderer_contract = _renderer_contract(root)
    route_contract = _route_contract(root)
    guardrail_contract = _guardrail_contract(root)

    ready = all(
        contract["ready"]
        for contract in (
            schema_contract,
            store_contract,
            renderer_contract,
            route_contract,
            guardrail_contract,
        )
    )

    summary = {
        "root": str(root),
        "artifact_family": "meeting_pack",
        "conformance_level": "partial",
        "conformant": ready,
        "schema_contract": schema_contract,
        "store_contract": store_contract,
        "renderer_contract": renderer_contract,
        "route_contract": route_contract,
        "guardrail_contract": guardrail_contract,
    }
    print(json.dumps(summary, indent=2))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
