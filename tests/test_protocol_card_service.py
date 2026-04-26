from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from src.protocol_cards.service import (
    build_protocol_card_draft_from_note,
    get_protocol_card_bundle,
    list_protocol_card_summaries,
    protocol_card_list_response,
    upsert_protocol_card,
)
from src.schemas.protocol_card import ProtocolCardDraftRequest, ProtocolCardRequest
from src.schemas.skills import SkillRunRecord, StructuredPaperState
from src.services.runtime_paths import preferred_artifact_paper_dir
from src.skills.storage import structured_state_path, write_structured_state


def _sample_request(*, title: str = "Alpha assay", protocol_id: str | None = "protocol_alpha") -> ProtocolCardRequest:
    return ProtocolCardRequest(
        protocol_id=protocol_id,
        title=title,
        purpose="Evaluate treatment response",
        context="In vitro assay",
        source_kind="paper_derived",
        linked_paper_ids=["paper-001"],
        linked_note_slugs=["alpha-note"],
        versions=[
            {
                "version_id": "protver_alpha_v1",
                "version_number": 1,
                "key_steps_summary": ["Seed cells"],
                "critical_conditions": ["37 C"],
                "readouts": ["Cell viability"],
                "content_snapshot": "Step 1: seed cells",
                "status": "active",
                "created_by": "operator",
                "created_at": datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
                "source_refs": [{"paper_slug": "paper-alpha", "claim_id": "claim-001"}],
            }
        ],
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_note(
    vault_path: Path,
    slug: str,
    *,
    note_id: str,
    title: str,
    body: str,
    summary: str | None = None,
) -> None:
    frontmatter_lines = [
        "---",
        f"id: {note_id}",
        f"title: {title}",
    ]
    if summary:
        frontmatter_lines.append(f"summary: {summary}")
    frontmatter_lines.extend(["---", "", body.strip(), ""])
    _write(
        vault_path / "Inbox" / "PaperPipe" / f"{slug}.md",
        "\n".join(frontmatter_lines),
    )


def _write_structured_state(
    vault_path: Path,
    slug: str,
    *,
    run_id: str,
    outcomes: list[str],
) -> None:
    write_structured_state(
        structured_state_path(vault_path, slug),
        StructuredPaperState(
            paper_slug=slug,
            updated_at="2026-04-10T09:00:00+00:00",
            runs=[
                SkillRunRecord(
                    id=run_id,
                    action="deep_read",
                    ts="2026-04-10T09:00:00+00:00",
                    status="succeeded",
                    summary="Canonical state snapshot",
                )
            ],
            signals={"last_run_id": run_id},
            claimset=[],
            outcomes=outcomes,
        ),
    )


def _write_resolved_claimset(artifacts_root: Path, *, paper_id: str, run_id: str) -> None:
    run_dir = preferred_artifact_paper_dir(paper_id, root=artifacts_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.resolved.json").write_text(
        json.dumps(
            {
                "doc_id": paper_id,
                "claims": [
                    {
                        "claim_id": "CLM-1",
                        "statement": "Cells were prepared before treatment.",
                        "type": "procedure",
                        "confidence": 0.84,
                        "evidence_spans": [
                            {
                                "quote": "Cells were prepared in assay plates.",
                                "page": 2,
                                "section": "Methods",
                                "chunk_id": "chunk-1",
                                "grounded": True,
                                "resolution": "resolved",
                                "source": "reader",
                            }
                        ],
                    },
                    {
                        "claim_id": "CLM-2",
                        "statement": "Viability was measured after incubation.",
                        "type": "readout",
                        "confidence": 0.8,
                        "evidence_spans": [
                            {
                                "quote": "Cell viability was measured after incubation.",
                                "page": 3,
                                "section": "Methods",
                                "chunk_id": "chunk-2",
                                "grounded": True,
                                "resolution": "resolved",
                                "source": "reader",
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_upsert_protocol_card_roundtrip_builds_bundle_and_defaults_current_version(tmp_path) -> None:
    root = tmp_path / "protocol_cards"
    request = _sample_request()

    created = upsert_protocol_card(request=request, root=root)
    fetched = get_protocol_card_bundle("protocol_alpha", root=root)

    assert created.protocol_card.protocol_id == "protocol_alpha"
    assert created.protocol_card.current_version_id == "protver_alpha_v1"
    assert created.protocol_card.validation_status == "draft"
    assert created.versions[0].protocol_id == "protocol_alpha"
    assert fetched.protocol_card.title == "Alpha assay"
    assert fetched.versions[0].version_id == "protver_alpha_v1"
    assert "# Alpha assay" in fetched.markdown
    assert "Step 1: seed cells" in fetched.markdown


def test_upsert_protocol_card_generates_protocol_and_version_ids_when_missing(tmp_path) -> None:
    root = tmp_path / "protocol_cards"
    request = ProtocolCardRequest(
        title="Generated protocol",
        source_kind="mixed",
        versions=[
            {
                "version_number": 2,
                "content_snapshot": "Protocol snapshot",
                "status": "draft",
                "created_by": "operator",
            }
        ],
    )

    created = upsert_protocol_card(
        request=request,
        root=root,
        now=datetime(2026, 3, 23, 3, 0, tzinfo=timezone.utc),
    )

    assert created.protocol_card.protocol_id.startswith("protocol_20260323T030000Z_")
    assert created.versions[0].version_id.startswith("protver_20260323T030000Z_")
    assert created.protocol_card.current_version_id == created.versions[0].version_id


def test_protocol_card_list_response_orders_recent_first(tmp_path) -> None:
    root = tmp_path / "protocol_cards"
    older = _sample_request(title="Older protocol", protocol_id="protocol_older")
    newer = _sample_request(title="Newer protocol", protocol_id="protocol_newer")

    upsert_protocol_card(
        request=older,
        root=root,
        now=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
    )
    upsert_protocol_card(
        request=newer,
        root=root,
        now=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc) + timedelta(hours=1),
    )

    summaries = list_protocol_card_summaries(root=root)
    payload = protocol_card_list_response(root=root)

    assert [item.protocol_id for item in summaries] == ["protocol_newer", "protocol_older"]
    assert [item.protocol_id for item in payload.items] == ["protocol_newer", "protocol_older"]
    assert payload.total == 2


def test_build_protocol_card_draft_from_note_uses_methods_section_and_claimset(tmp_path) -> None:
    vault_path = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    slug = "paper-alpha"
    _write_note(
        vault_path,
        slug,
        note_id="doi:10.1000/a",
        title="Alpha Trial",
        summary="Capture the core assay procedure from the paper note.",
        body=(
            "# Alpha Trial\n\n"
            "Overview text.\n\n"
            "## Methods\n"
            "- Prepare cells\n"
            "- Apply treatment\n"
            "- Measure viability\n\n"
            "## Results\n"
            "Treatment response increased.\n"
        ),
    )
    _write_structured_state(
        vault_path,
        slug,
        run_id="run-current",
        outcomes=["Cell viability", "Apoptosis"],
    )
    _write_resolved_claimset(
        artifacts_root,
        paper_id="doi:10.1000/a",
        run_id="run-current",
    )

    result = build_protocol_card_draft_from_note(
        request=ProtocolCardDraftRequest(note_slug=slug),
        vault_path=vault_path,
        artifacts_root=artifacts_root,
    )

    assert result.draft.title == "Alpha Trial protocol draft"
    assert result.draft.purpose == "Capture the core assay procedure from the paper note."
    assert result.draft.linked_paper_ids == ["doi:10.1000/a"]
    assert result.draft.linked_note_slugs == ["paper-alpha"]
    assert result.draft.versions[0].key_steps_summary == [
        "Prepare cells",
        "Apply treatment",
        "Measure viability",
    ]
    assert result.draft.versions[0].readouts == ["Cell viability", "Apoptosis"]
    assert "Prepare cells" in result.draft.versions[0].content_snapshot
    assert len(result.draft.versions[0].source_refs) == 2
    assert all(ref.claim_id for ref in result.draft.versions[0].source_refs)
    assert result.source_summary.note_slug == slug
    assert result.source_summary.paper_id == "doi:10.1000/a"
    assert result.source_summary.run_id == "run-current"
    assert result.source_summary.claim_count == 2
    assert result.source_summary.evidence_count == 2
    assert result.source_summary.used_note_body is True
    assert result.source_summary.used_structured_state is True
    assert result.source_summary.used_claimset is True
    assert result.warnings == []


def test_build_protocol_card_draft_from_note_falls_back_without_structured_state(tmp_path) -> None:
    vault_path = tmp_path / "vault"
    slug = "paper-fallback"
    _write_note(
        vault_path,
        slug,
        note_id="paper-fallback",
        title="Fallback Trial",
        body=(
            "# Fallback Trial\n\n"
            "This note describes a rapid pilot workflow for thawing samples, incubating them, "
            "and collecting fluorescence measurements.\n"
            "The same sequence is reused as a draft protocol when no dedicated methods section exists.\n"
        ),
    )

    result = build_protocol_card_draft_from_note(
        request=ProtocolCardDraftRequest(note_slug=slug),
        vault_path=vault_path,
        artifacts_root=tmp_path / "artifacts",
    )

    warning_codes = {warning.code for warning in result.warnings}

    assert result.draft.linked_paper_ids == ["paper-fallback"]
    assert result.draft.versions[0].source_refs[0].paper_slug == slug
    assert result.source_summary.used_structured_state is False
    assert result.source_summary.used_claimset is False
    assert result.source_summary.claim_count == 0
    assert result.source_summary.evidence_count == 0
    assert {"METHOD_SECTION_MISSING", "STRUCTURED_STATE_MISSING", "SOURCE_REFS_FALLBACK"} <= warning_codes
