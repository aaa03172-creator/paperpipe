from __future__ import annotations

from datetime import datetime, timezone

import pytest

import src.protocol_attachments.store as protocol_attachment_store
from src.protocol_attachments.store import (
    load_protocol_attachment_bundle,
    protocol_attachment_json_path,
    protocol_attachment_source_path,
    save_protocol_attachment_bundle,
)
from src.schemas.protocol_attachment import (
    ProtocolAttachmentArtifactRef,
    ProtocolAttachmentBundle,
)


def _sample_attachment_bundle() -> ProtocolAttachmentBundle:
    return ProtocolAttachmentBundle(
        attachment_bundle_id="protatt_alpha",
        title="Alpha attachment",
        source_filename="alpha.pdf",
        media_type="application/pdf",
        byte_size=4,
        sha1="0" * 40,
        created_at=datetime(2026, 3, 24, tzinfo=timezone.utc),
        source_ref=ProtocolAttachmentArtifactRef(kind="source_file", path="source/alpha.pdf"),
        extracted_markdown_ref=ProtocolAttachmentArtifactRef(kind="extracted_markdown", path="extracted/alpha.md"),
        extraction_status="succeeded",
    )


def test_protocol_attachment_store_roundtrip_creates_expected_layout(tmp_path) -> None:
    root = tmp_path / "protocol_attachments"
    bundle = _sample_attachment_bundle()

    result = save_protocol_attachment_bundle(
        bundle,
        source_bytes=b"%PDF",
        extracted_markdown="# Alpha\n",
        root=root,
    )
    loaded = load_protocol_attachment_bundle(bundle.attachment_bundle_id, root)

    assert result["json"] == protocol_attachment_json_path(bundle.attachment_bundle_id, root)
    assert result["source"] == root / bundle.attachment_bundle_id / "source" / "alpha.pdf"
    assert result["markdown"] == root / bundle.attachment_bundle_id / "extracted" / "alpha.md"
    assert loaded.attachment_bundle_id == bundle.attachment_bundle_id


def test_protocol_attachment_store_rejects_path_like_bundle_ids(tmp_path) -> None:
    root = tmp_path / "protocol_attachments"

    with pytest.raises(ValueError, match="attachment_bundle_id"):
        protocol_attachment_json_path("../escape", root)

    with pytest.raises(ValueError, match="attachment_bundle_id"):
        protocol_attachment_source_path("protatt_nested/escape", "source/alpha.pdf", root)


def test_protocol_attachment_store_rolls_back_if_markdown_write_fails(tmp_path, monkeypatch) -> None:
    root = tmp_path / "protocol_attachments"
    bundle = _sample_attachment_bundle()
    save_protocol_attachment_bundle(
        bundle,
        source_bytes=b"%PDF",
        extracted_markdown="# Original\n",
        root=root,
    )
    bundle_dir = root / bundle.attachment_bundle_id
    operator_notes = bundle_dir / "operator_notes.txt"
    source_readme = bundle_dir / "source" / "README.txt"
    extracted_readme = bundle_dir / "extracted" / "README.txt"
    operator_notes.write_text("keep local attachment notes", encoding="utf-8")
    source_readme.write_text("source sidecar", encoding="utf-8")
    extracted_readme.write_text("extracted sidecar", encoding="utf-8")

    updated_bundle = bundle.model_copy(update={"title": "Updated attachment"})
    original_atomic_write_bytes = protocol_attachment_store._atomic_write_bytes
    call_count = {"value": 0}

    def fail_on_third_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 3:
            raise IOError("boom")
        return original_atomic_write_bytes(path, content)

    monkeypatch.setattr(protocol_attachment_store, "_atomic_write_bytes", fail_on_third_write)

    with pytest.raises(OSError):
        save_protocol_attachment_bundle(
            updated_bundle,
            source_bytes=b"%PDF updated",
            extracted_markdown="# Updated\n",
            root=root,
        )

    loaded = load_protocol_attachment_bundle(bundle.attachment_bundle_id, root)
    assert loaded.title == "Alpha attachment"
    assert (bundle_dir / "source" / "alpha.pdf").read_bytes() == b"%PDF"
    assert (bundle_dir / "extracted" / "alpha.md").read_text(encoding="utf-8") == "# Original\n"
    assert operator_notes.read_text(encoding="utf-8") == "keep local attachment notes"
    assert source_readme.read_text(encoding="utf-8") == "source sidecar"
    assert extracted_readme.read_text(encoding="utf-8") == "extracted sidecar"
