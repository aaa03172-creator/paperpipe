from __future__ import annotations

import json
from pathlib import Path

from src.protocol_attachments.service import (
    build_protocol_card_draft_from_attachment,
    get_protocol_attachment_bundle,
    get_protocol_attachment_markdown,
)
from src.schemas.protocol_attachment import ProtocolAttachmentDraftRequest
from src.schemas.skills import SkillRunRecord, StructuredPaperState
from src.services.runtime_paths import preferred_artifact_paper_dir
from src.skills.storage import structured_state_path, write_structured_state


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
) -> None:
    _write(
        vault_path / "Inbox" / "PaperPipe" / f"{slug}.md",
        f"---\nid: {note_id}\ntitle: {title}\n---\n\n{body.strip()}\n",
    )


def _write_structured_state(vault_path: Path, slug: str, *, run_id: str) -> None:
    write_structured_state(
        structured_state_path(vault_path, slug),
        StructuredPaperState(
            paper_slug=slug,
            updated_at="2026-04-10T10:00:00+00:00",
            runs=[
                SkillRunRecord(
                    id=run_id,
                    action="deep_read",
                    ts="2026-04-10T10:00:00+00:00",
                    status="succeeded",
                    summary="Canonical state snapshot",
                )
            ],
            signals={"last_run_id": run_id},
            claimset=[],
            outcomes=["Cell viability"],
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
                        "claim_id": "CLM-0",
                        "statement": "Baseline protocol evidence.",
                        "type": "procedure",
                        "evidence_spans": [
                            {
                                "quote": "Baseline protocol evidence.",
                                "page": 1,
                                "section": "Methods",
                                "grounded": True,
                                "resolution": "resolved",
                                "source": "reader",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_build_protocol_card_draft_from_attachment_persists_bundle_and_markdown(tmp_path) -> None:
    root = tmp_path / "protocol_attachments"

    result = build_protocol_card_draft_from_attachment(
        request=ProtocolAttachmentDraftRequest(
            filename="assay.md",
            media_type="text/markdown",
        ),
        content=(
            b"# Assay Protocol\n\n"
            b"- Prepare cells\n"
            b"- Add reagent\n"
            b"- Measure signal\n"
        ),
        root=root,
    )

    saved_bundle = get_protocol_attachment_bundle(result.attachment_bundle.attachment_bundle_id, root=root)
    saved_markdown = get_protocol_attachment_markdown(result.attachment_bundle.attachment_bundle_id, root=root)

    assert saved_bundle.attachment_bundle_id.startswith("protatt_")
    assert saved_bundle.layer == "raw_source"
    assert saved_bundle.artifact_family == "protocol_attachment"
    assert saved_bundle.extraction_status == "succeeded"
    assert saved_bundle.extraction_engine == "plain_text"
    assert saved_bundle.source_ref.path == "source/assay.md"
    assert saved_bundle.extracted_markdown_ref is not None
    assert saved_markdown.startswith("# Assay Protocol")
    assert result.draft.source_kind == "internal_adaptation"
    assert result.draft.versions[0].key_steps_summary == [
        "Prepare cells",
        "Add reagent",
        "Measure signal",
    ]
    assert result.warnings == []


def test_build_protocol_card_draft_from_attachment_preserves_raw_but_sanitizes_user_surfaces(tmp_path) -> None:
    root = tmp_path / "protocol_attachments"

    result = build_protocol_card_draft_from_attachment(
        request=ProtocolAttachmentDraftRequest(
            filename="secret-protocol.md",
            media_type="text/markdown",
            title="Secret protocol sk-proj-protocol-title-secret-abcdef",
        ),
        content=(
            b"# Secret Protocol\n\n"
            b"- Prime pump with Authorization: Bearer protocol-attachment-token-123\n"
            b"- Store sk-proj-protocol-attachment-secret-abcdef outside draft\n"
        ),
        root=root,
    )

    saved_markdown = get_protocol_attachment_markdown(result.attachment_bundle.attachment_bundle_id, root=root)

    assert "protocol-attachment-token-123" in saved_markdown
    assert "sk-proj-protocol-attachment-secret-abcdef" in saved_markdown
    assert "protocol-attachment-token-123" not in result.attachment_bundle.extracted_markdown_excerpt
    assert "sk-proj-protocol-attachment-secret-abcdef" not in result.draft.versions[0].content_snapshot
    assert result.attachment_bundle.title == "Secret protocol <redacted>"
    assert "Authorization: <redacted>" in result.draft.versions[0].content_snapshot


def test_build_protocol_card_draft_from_attachment_merges_with_note_context(tmp_path) -> None:
    root = tmp_path / "protocol_attachments"
    vault_path = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    _write_note(
        vault_path,
        "paper-alpha",
        note_id="doi:10.1000/a",
        title="Alpha Trial",
        body=(
            "# Alpha Trial\n\n"
            "## Methods\n"
            "- Seed cells\n"
            "- Apply treatment\n"
        ),
    )
    _write_structured_state(vault_path, "paper-alpha", run_id="run-current")
    _write_resolved_claimset(
        artifacts_root,
        paper_id="doi:10.1000/a",
        run_id="run-current",
    )

    result = build_protocol_card_draft_from_attachment(
        request=ProtocolAttachmentDraftRequest(
            filename="bench-notes.txt",
            media_type="text/plain",
            note_slug="paper-alpha",
        ),
        content=(
            b"- Warm media\n"
            b"- Measure viability\n"
        ),
        root=root,
        vault_path=vault_path,
        artifacts_root=artifacts_root,
    )

    assert result.draft.source_kind == "mixed"
    assert result.draft.linked_note_slugs == ["paper-alpha"]
    assert result.draft.linked_paper_ids == ["doi:10.1000/a"]
    assert "## Attached Material: bench-notes.txt" in result.draft.versions[0].content_snapshot
    assert "Warm media" in result.draft.versions[0].content_snapshot
    assert result.draft.versions[0].key_steps_summary == [
        "Seed cells",
        "Apply treatment",
        "Warm media",
        "Measure viability",
    ]
    assert result.paper_source_summary is not None
    assert result.paper_source_summary.used_claimset is True


def test_build_protocol_card_draft_from_attachment_keeps_placeholder_when_extraction_unavailable(tmp_path) -> None:
    root = tmp_path / "protocol_attachments"

    result = build_protocol_card_draft_from_attachment(
        request=ProtocolAttachmentDraftRequest(
            filename="protocol-image.png",
            media_type="image/png",
        ),
        content=b"PNGDATA",
        root=root,
    )

    warning_codes = {warning.code for warning in result.warnings}

    assert result.attachment_bundle.extraction_status == "failed"
    assert result.attachment_bundle.extracted_markdown_ref is None
    assert result.draft.versions[0].content_snapshot.startswith("Uploaded attachment bundle")
    assert "ATTACHMENT_EXTRACTION_UNAVAILABLE" in warning_codes
