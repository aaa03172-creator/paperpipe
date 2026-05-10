from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_meeting_pack_manifest_conformance_script_reports_ready_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_meeting_pack_manifest_conformance.py"

    _write(
        workspace / "src" / "schemas" / "meeting_pack.py",
        "\n".join(
            [
                'layer: Literal["user_facing_artifact"] = "user_facing_artifact"',
                'canonical_status: Literal["non_canonical"] = "non_canonical"',
                'readiness: MeetingPackReadiness = "evidence_backed"',
                "generation_request: MeetingPackRequestSnapshot | None = None",
                "source_items: list[MeetingPackSourceItem] = Field(default_factory=list)",
                "retrieval_trace: list[MeetingPackRetrievalTraceEntry] = Field(default_factory=list)",
                "evidence_refs: list[MeetingPackEvidenceRef] = Field(default_factory=list)",
                "artifact_brief: ArtifactBrief | None = None",
                "artifact_brief_review: ArtifactPlanReview | None = None",
                "markdown_sync: MeetingPackMarkdownSync",
                "regenerate_strategy: MeetingPackRegenerateStrategy",
            ]
        )
        + "\n",
    )
    _write(
        workspace / "src" / "meeting_packs" / "store.py",
        "\n".join(
            [
                'json_name = "meeting_pack.json"',
                'md_name = "meeting_pack.md"',
                "def save_meeting_pack_bundle(): pass",
                "def load_meeting_pack(): pass",
                "def load_meeting_pack_markdown(): pass",
                "def save_meeting_pack_artifact_json(): pass",
                "def _restore_optional_text(): pass",
                "def _remove_empty_dir(): pass",
            ]
        )
        + "\n",
    )
    _write(
        workspace / "src" / "meeting_packs" / "renderer.py",
        "\n".join(
            [
                'line = f"- Layer: {pack.layer}"',
                'line = f"- Canonical status: {pack.canonical_status}"',
                'line = f"- Readiness: {pack.readiness}"',
                'line = f"- Sources: {source_refs}"',
                '"## Artifact Brief"',
                '"## Artifact Brief Review"',
                '"## Promotion guardrail"',
                '"derived user-facing artifact, not canonical scientific truth"',
            ]
        )
        + "\n",
    )
    _write(
        workspace / "backend" / "routers" / "meeting_packs.py",
        "\n".join(
            [
                '@router.post("/generate", response_model=MeetingPackResponse)',
                '@router.get("", response_model=MeetingPackListResponse)',
                '@router.get("/{pack_id}", response_model=MeetingPackResponse)',
                '@router.get("/{pack_id}/trace", response_model=MeetingPackTraceResponse)',
                '@router.get("/{pack_id}/validate", response_model=MeetingPackValidationResponse)',
                '@router.post("/{pack_id}/regenerate", response_model=MeetingPackResponse)',
                '@router.post("/{pack_id}/rerender", response_model=MeetingPackResponse)',
                '@router.post("/{pack_id}/outcome")',
                '@router.post("/{pack_id}/review")',
                '@router.get("/{pack_id}/markdown", response_class=PlainTextResponse)',
            ]
        )
        + "\n",
    )
    _write(
        workspace / "tests" / "test_meeting_pack_schema.py",
        "\n".join(
            [
                'assert pack.layer == "user_facing_artifact"',
                'assert response.validation.regenerate_strategy == "legacy_source_items"',
                'assert response.markdown_sync.status == "drifted"',
            ]
        )
        + "\n",
    )
    _write(
        workspace / "tests" / "test_meeting_pack_store.py",
        "\n".join(
            [
                'assert loaded.layer == "user_facing_artifact"',
                'assert loaded.canonical_status == "non_canonical"',
                '"quality_gate.json"',
            ]
        )
        + "\n",
    )
    _write(
        workspace / "tests" / "test_meeting_pack_service.py",
        "\n".join(
            [
                'assert response.pack.layer == "user_facing_artifact"',
                'assert response.pack.canonical_status == "non_canonical"',
                'assert response.markdown_sync.status == "in_sync"',
                'assert response.pack.artifact_brief_review.overall_status == "pass"',
                'assert stored.pack.retrieval_trace == response.pack.retrieval_trace',
                '"acceptance_contract.json"',
                '"quality_gate.json"',
            ]
        )
        + "\n",
    )
    _write(
        workspace / "tests" / "test_meeting_pack_api.py",
        "\n".join(
            [
                'assert generate.json()["pack"]["layer"] == "user_facing_artifact"',
                'assert generate.json()["pack"]["canonical_status"] == "non_canonical"',
                'assert generate.json()["markdown_sync"]["status"] == "in_sync"',
            ]
        )
        + "\n",
    )
    _write(
        workspace / "tests" / "test_meeting_pack_handoff_artifacts.py",
        "\n".join(
            [
                'assert contract.operator_contract["regenerate_strategy_snapshot"] == "saved_request"',
                'assert gate.discussion_ready is True',
                'assert "TRACE_MISSING" in gate.reason_codes',
            ]
        )
        + "\n",
    )
    _write(
        workspace / "scripts" / "run_meeting_pack_verify.sh",
        "\n".join(
            [
                "scripts/check_meeting_pack_real_smoke.py",
                "scripts/check_meeting_pack_storage_sync.py",
                "--require-regenerable",
            ]
        )
        + "\n",
    )
    _write(
        workspace / "scripts" / "check_meeting_pack_real_smoke.py",
        'raise SystemExit("expected evidence_backed readiness")\n',
    )
    _write(workspace / "scripts" / "check_meeting_pack_storage_sync.py", "print('ok')\n")

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["artifact_family"] == "meeting_pack"
    assert payload["conformance_level"] == "partial"
    assert payload["conformant"] is True
    assert payload["schema_contract"]["ready"] is True
    assert payload["store_contract"]["ready"] is True
    assert payload["renderer_contract"]["ready"] is True
    assert payload["route_contract"]["ready"] is True
    assert payload["guardrail_contract"]["ready"] is True


def test_meeting_pack_manifest_conformance_script_flags_missing_contracts(tmp_path):
    workspace = tmp_path / "workspace"
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_meeting_pack_manifest_conformance.py"

    _write(
        workspace / "src" / "schemas" / "meeting_pack.py",
        'layer: Literal["user_facing_artifact"] = "user_facing_artifact"\n',
    )

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["artifact_family"] == "meeting_pack"
    assert payload["conformance_level"] == "partial"
    assert payload["conformant"] is False
    assert payload["schema_contract"]["ready"] is False
    assert payload["store_contract"]["ready"] is False
    assert payload["renderer_contract"]["ready"] is False
    assert payload["route_contract"]["ready"] is False
    assert payload["guardrail_contract"]["ready"] is False
