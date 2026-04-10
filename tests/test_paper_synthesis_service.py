from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.paper_syntheses.service import (
    build_paper_synthesis_for_slug,
    load_paper_synthesis_inputs,
    materialize_paper_synthesis_for_slug,
    paper_synthesis_list_response,
)
from src.paper_syntheses.store import load_paper_synthesis, load_paper_synthesis_markdown
from src.schemas.paper_synthesis import PaperSynthesis, PaperSynthesisSourceRef
from src.schemas.skills import SkillRunRecord, StructuredPaperState
from src.skills.storage import structured_state_path, write_structured_state


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_structured_state(
    vault_path: Path,
    slug: str,
    *,
    last_run_id: str = "run-latest",
    claim_count: int = 1,
) -> None:
    state = StructuredPaperState(
        paper_slug=slug,
        updated_at="2026-04-07T11:00:00+00:00",
        runs=[
            SkillRunRecord(
                id=last_run_id,
                action="deep_read",
                ts="2026-04-07T11:00:00+00:00",
                status="succeeded",
                summary="Canonical state snapshot",
            )
        ],
        signals={"last_run_id": last_run_id},
        claimset=[
            {
                "id": f"claim_{index}",
                "run_id": last_run_id,
                "claim": f"Claim {index}",
                "evidence": [
                    {
                        "id": f"evidence_{index}",
                        "run_id": last_run_id,
                        "text": f"Evidence {index}",
                        "page": index + 1,
                        "grounded": True,
                        "resolution": "resolved",
                        "source": "reader",
                    }
                ],
            }
            for index in range(claim_count)
        ],
    )
    write_structured_state(structured_state_path(vault_path, slug), state)


def _write_fixture_structured_state(vault_path: Path, slug: str) -> None:
    _write_json(
        structured_state_path(vault_path, slug),
        {
            "schema_version": "2026-03-09.chat-hooks.v1",
            "paper_slug": slug,
            "updated_at": "2026-04-07T11:00:00+00:00",
            "runs": [],
            "signals": {"last_run_id": "run-current"},
            "claimset": [
                {
                    "id": "claim_c0ffee000001",
                    "source_claim_id": "e2e-claim-1",
                    "run_id": "run-current",
                    "claim": "Fixture claim should stay hidden from paper synthesis generation.",
                    "evidence_ids": ["evidence_deadbeef0001"],
                    "evidence": [
                        {
                            "id": "evidence_deadbeef0001",
                            "claim_id": "claim_c0ffee000001",
                            "run_id": "run-current",
                            "text": "Fixture evidence.",
                            "page": 1,
                            "grounded": True,
                            "resolution": "resolved",
                            "source": "reader",
                            "locator": {"chunk_id": "chunk-e2e-001"},
                        }
                    ],
                }
            ],
            "entities": [],
            "mesh": [],
            "outcomes": [],
        },
    )


def _write_artifact_run(
    artifact_dir: Path,
    *,
    run_id: str,
    status: str = "succeeded",
    claim_count: int = 1,
    grounded: bool = True,
    quality_gate_status: str = "pass",
) -> None:
    _write_json(
        artifact_dir / "run_meta.json",
        {
            "run_id": run_id,
            "status": status,
            "finished_at": "2026-04-07T12:00:00+00:00",
            "parser_backend": "docling",
        },
    )
    _write_json(
        artifact_dir / "claimset.resolved.json",
        {
            "doc_id": artifact_dir.parent.name,
            "claims": [
                {
                    "claim_id": f"claim-{index}",
                    "type": "finding",
                    "statement": f"Finding {index}",
                    "confidence": 0.8,
                    "evidence_spans": [
                        {
                            "quote": f"Evidence quote {index}",
                            "page": index + 1,
                            "section": "Results",
                            "chunk_id": f"chunk-{index}",
                            "grounded": grounded,
                            "resolution": "resolved" if grounded else "unresolved",
                            "source": "reader",
                        }
                    ],
                }
                for index in range(claim_count)
            ],
        },
    )
    _write_json(
        artifact_dir / "quality_gate.json",
        {
            "run_id": run_id,
            "overall_status": quality_gate_status,
        },
    )
    _write_json(
        artifact_dir / "acceptance_contract.json",
        {
            "run_id": run_id,
            "status": "ready" if quality_gate_status == "pass" else "review_required",
        },
    )


def test_load_paper_synthesis_inputs_skips_incomplete_newer_runs(tmp_path):
    vault_path = tmp_path / "Vault"
    slug = "demo-note"
    _write_structured_state(vault_path, slug, last_run_id="run-older")

    paper_dir = tmp_path / "storage" / "artifacts" / slug
    older = paper_dir / "run-older"
    newer_incomplete = paper_dir / "run-newer"
    _write_artifact_run(older, run_id="run-older", claim_count=1)
    _write_json(
        newer_incomplete / "run_meta.json",
        {
            "run_id": "run-newer",
            "status": "succeeded",
            "finished_at": "2026-04-07T12:30:00+00:00",
        },
    )

    inputs = load_paper_synthesis_inputs(
        slug,
        vault_path=vault_path,
        artifacts_root=tmp_path / "storage" / "artifacts",
    )

    assert inputs.run_id == "run-older"
    assert inputs.claimset_path.name == "claimset.resolved.json"
    assert inputs.run_meta_path.name == "run_meta.json"


def test_build_paper_synthesis_for_slug_keeps_inputs_bounded_and_marks_review_guardrail(tmp_path):
    vault_path = tmp_path / "Vault"
    slug = "demo-note"
    _write_structured_state(vault_path, slug, last_run_id="run-current", claim_count=2)

    artifact_dir = tmp_path / "storage" / "artifacts" / slug / "run-current"
    _write_artifact_run(artifact_dir, run_id="run-current", claim_count=2)
    _write_json(artifact_dir / "document_artifact.json", {"ignored": True})

    result = build_paper_synthesis_for_slug(
        slug,
        vault_path=vault_path,
        artifacts_root=tmp_path / "storage" / "artifacts",
        now=datetime(2026, 4, 7, 13, 0, tzinfo=timezone.utc),
    )

    assert result.synthesis.readiness == "evidence_backed"
    assert result.synthesis.freshness == "current"
    assert result.synthesis.artifact_family == "paper_synthesis"
    assert result.synthesis.template_kind == "paper"
    assert result.synthesis.layer == "compiled_knowledge"
    assert result.synthesis.canonical_status == "non_canonical"
    assert result.synthesis.lineage_summary.minimum_required_source_kinds == [
        "structured_state",
        "claimset_resolved",
        "run_meta",
    ]
    assert result.synthesis.lineage_summary.present_required_source_kinds == [
        "structured_state",
        "claimset_resolved",
        "run_meta",
    ]
    assert result.synthesis.lineage_summary.review_artifact_kinds == [
        "quality_gate",
        "acceptance_contract",
    ]
    assert result.synthesis.lineage_summary.answer_route == "canonical_state_then_upstream_evidence"
    assert {item.kind for item in result.synthesis.source_refs} == {
        "structured_state",
        "claimset_resolved",
        "quality_gate",
        "acceptance_contract",
        "run_meta",
    }
    assert all(item.kind != "document_artifact" for item in result.synthesis.source_refs)
    assert result.markdown.startswith("---\nartifact_family: paper_synthesis\n")
    assert "canonical_status: non_canonical" in result.markdown
    assert "required_answer_route: canonical_state_then_upstream_evidence" in result.markdown
    assert "## Layer contract" in result.markdown
    assert "- Layer: `compiled_knowledge`" in result.markdown
    assert "- Canonical status: `non_canonical`" in result.markdown
    assert "Promoted biomedical answers must jump back" in result.markdown
    assert "Derived from canonical structured state plus the selected `claimset.resolved.json` and `run_meta.json` only." in result.markdown
    assert "Raw-memory helpers such as project memory, work traces, or conversation logs are intentionally excluded" in result.markdown
    assert "Additive review artifacts may be attached for this run" in result.markdown


def test_build_paper_synthesis_for_slug_warns_when_state_and_run_diverge(tmp_path):
    vault_path = tmp_path / "Vault"
    slug = "demo-note"
    _write_structured_state(vault_path, slug, last_run_id="run-state", claim_count=2)

    artifact_dir = tmp_path / "storage" / "artifacts" / slug / "run-synthesis"
    _write_artifact_run(
        artifact_dir,
        run_id="run-synthesis",
        claim_count=1,
        grounded=False,
        quality_gate_status="warn",
    )

    result = build_paper_synthesis_for_slug(
        slug,
        vault_path=vault_path,
        artifacts_root=tmp_path / "storage" / "artifacts",
        now=datetime(2026, 4, 7, 13, 30, tzinfo=timezone.utc),
    )

    assert result.synthesis.readiness == "mixed"
    assert result.synthesis.freshness == "stale"
    assert any("last_run_id differs" in warning for warning in result.synthesis.warnings)
    assert any("quality gate is `warn`" in warning for warning in result.synthesis.warnings)
    assert any("not aligned yet" in note for note in result.synthesis.uncertainty_notes)


def test_materialize_paper_synthesis_for_slug_saves_bundle(tmp_path):
    vault_path = tmp_path / "Vault"
    slug = "demo-note"
    _write_structured_state(vault_path, slug, last_run_id="run-current")

    artifact_dir = tmp_path / "storage" / "artifacts" / slug / "run-current"
    _write_artifact_run(artifact_dir, run_id="run-current", claim_count=1)

    result = materialize_paper_synthesis_for_slug(
        slug,
        vault_path=vault_path,
        artifacts_root=tmp_path / "storage" / "artifacts",
        output_root=tmp_path / "storage" / "paper_syntheses",
        now=datetime(2026, 4, 7, 14, 0, tzinfo=timezone.utc),
    )

    loaded = load_paper_synthesis(result.synthesis.synthesis_id, tmp_path / "storage" / "paper_syntheses")
    loaded_markdown = load_paper_synthesis_markdown(
        result.synthesis.synthesis_id,
        tmp_path / "storage" / "paper_syntheses",
    )
    assert loaded.synthesis_id == result.synthesis.synthesis_id
    assert loaded.canonical_status == "non_canonical"
    assert loaded_markdown.startswith("---\nartifact_family: paper_synthesis\n")


def test_paper_synthesis_list_response_can_filter_by_paper_slug(tmp_path):
    vault_path = tmp_path / "Vault"
    output_root = tmp_path / "storage" / "paper_syntheses"
    artifacts_root = tmp_path / "storage" / "artifacts"

    _write_structured_state(vault_path, "paper-alpha", last_run_id="run-alpha")
    _write_structured_state(vault_path, "paper-beta", last_run_id="run-beta")
    _write_artifact_run(artifacts_root / "paper-alpha" / "run-alpha", run_id="run-alpha", claim_count=1)
    _write_artifact_run(artifacts_root / "paper-beta" / "run-beta", run_id="run-beta", claim_count=1)

    materialize_paper_synthesis_for_slug(
        "paper-alpha",
        vault_path=vault_path,
        artifacts_root=artifacts_root,
        output_root=output_root,
        now=datetime(2026, 4, 7, 14, 0, tzinfo=timezone.utc),
    )
    materialize_paper_synthesis_for_slug(
        "paper-beta",
        vault_path=vault_path,
        artifacts_root=artifacts_root,
        output_root=output_root,
        now=datetime(2026, 4, 7, 14, 5, tzinfo=timezone.utc),
    )

    filtered = paper_synthesis_list_response(root=output_root, paper_slug="paper-alpha")

    assert filtered.total == 1
    assert [item.paper_slug for item in filtered.items] == ["paper-alpha"]
    assert filtered.items[0].canonical_status == "non_canonical"
    assert filtered.items[0].lineage_summary.present_required_source_kinds == [
        "structured_state",
        "claimset_resolved",
        "run_meta",
    ]
    assert filtered.items[0].lineage_summary.review_artifact_kinds == [
        "quality_gate",
        "acceptance_contract",
    ]


def test_build_paper_synthesis_for_slug_requires_canonical_structured_state(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_paper_synthesis_for_slug(
            "missing-note",
            vault_path=tmp_path / "Vault",
            artifacts_root=tmp_path / "storage" / "artifacts",
        )


def test_build_paper_synthesis_for_slug_rejects_fixture_structured_state_by_default(tmp_path):
    vault_path = tmp_path / "Vault"
    slug = "fixture-note"
    _write_fixture_structured_state(vault_path, slug)

    artifact_dir = tmp_path / "storage" / "artifacts" / slug / "run-current"
    _write_artifact_run(artifact_dir, run_id="run-current", claim_count=1)

    with pytest.raises(FileNotFoundError, match="appears to be a test fixture"):
        build_paper_synthesis_for_slug(
            slug,
            vault_path=vault_path,
            artifacts_root=tmp_path / "storage" / "artifacts",
        )


def test_build_paper_synthesis_for_slug_allows_fixture_structured_state_in_e2e_runtime(tmp_path):
    vault_path = tmp_path / "frontend" / ".e2e-backend-runtime" / "obsidian"
    slug = "fixture-note"
    _write_fixture_structured_state(vault_path, slug)

    artifact_dir = tmp_path / "storage" / "artifacts" / slug / "run-current"
    _write_artifact_run(artifact_dir, run_id="run-current", claim_count=1)

    result = build_paper_synthesis_for_slug(
        slug,
        vault_path=vault_path,
        artifacts_root=tmp_path / "storage" / "artifacts",
        now=datetime(2026, 4, 7, 14, 30, tzinfo=timezone.utc),
    )

    assert result.synthesis.paper_slug == slug
    assert result.inputs.state.paper_slug == slug


def test_paper_synthesis_schema_requires_minimum_lineage_and_readiness_consistency():
    with pytest.raises(ValidationError, match="claimset_resolved, run_meta"):
        PaperSynthesis(
            synthesis_id="papersynth_demo_run_1234567890",
            paper_slug="demo-paper",
            title="Paper synthesis: demo-paper",
            created_at=datetime(2026, 4, 7, 14, 30, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 7, 14, 30, tzinfo=timezone.utc),
            readiness="background_only",
            source_refs=[
                PaperSynthesisSourceRef(
                    kind="structured_state",
                    paper_slug="demo-paper",
                    path="vault/.pp/demo-paper/state.json",
                )
            ],
            evidence_refs=[],
        )
