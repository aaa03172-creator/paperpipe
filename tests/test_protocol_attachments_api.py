from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main as api_main
from backend.routers import protocol_cards as protocol_cards_router


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_note(vault_path, slug: str) -> None:
    _write(
        vault_path / "Inbox" / "PaperPipe" / f"{slug}.md",
        (
            "---\n"
            "id: doi:10.1000/a\n"
            "title: Alpha Trial\n"
            "---\n\n"
            "# Alpha Trial\n\n"
            "## Methods\n"
            "- Seed cells\n"
            "- Apply treatment\n"
        ),
    )
    _write(
        vault_path / ".pp" / slug / "state.json",
        (
            "{\n"
            '  "schema_version": "2026-03-09.chat-hooks.v1",\n'
            '  "paper_slug": "paper-alpha",\n'
            '  "updated_at": "2026-04-10T10:00:00Z",\n'
            '  "runs": [{"id": "run-current", "action": "deep_read", "ts": "2026-04-10T10:00:00Z", "status": "succeeded", "summary": "Canonical state snapshot"}],\n'
            '  "signals": {"last_run_id": "run-current"},\n'
            '  "claimset": [],\n'
            '  "entities": [],\n'
            '  "mesh": [],\n'
            '  "outcomes": ["Cell viability"]\n'
            "}\n"
        ),
    )


def test_protocol_cards_api_builds_attachment_draft_and_persists_bundle(tmp_path, monkeypatch) -> None:
    attachments_root = tmp_path / "protocol_attachments"
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_ATTACHMENTS_DIR", str(attachments_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    response = client.post(
        "/protocol-cards/draft-from-attachment",
        files={"file": ("assay.txt", b"- Prepare cells\n- Measure signal\n", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    attachment_bundle_id = payload["attachment_bundle"]["attachment_bundle_id"]
    assert payload["attachment_bundle"]["artifact_family"] == "protocol_attachment"
    assert payload["attachment_bundle"]["layer"] == "raw_source"
    assert payload["draft"]["source_kind"] == "internal_adaptation"
    assert payload["draft"]["versions"][0]["key_steps_summary"] == [
        "Prepare cells",
        "Measure signal",
    ]

    bundle = client.get(f"/protocol-cards/attachments/{attachment_bundle_id}")
    assert bundle.status_code == 200
    assert bundle.json()["attachment_bundle_id"] == attachment_bundle_id

    source = client.get(f"/protocol-cards/attachments/{attachment_bundle_id}/source")
    assert source.status_code == 200
    assert source.content == b"- Prepare cells\n- Measure signal\n"
    assert source.headers["content-type"].startswith("text/plain")
    assert source.headers["content-disposition"].startswith('inline; filename="assay.txt"')

    source_download = client.get(f"/protocol-cards/attachments/{attachment_bundle_id}/source?download=1")
    assert source_download.status_code == 200
    assert source_download.content == b"- Prepare cells\n- Measure signal\n"
    assert source_download.headers["content-type"].startswith("text/plain")
    assert source_download.headers["content-disposition"].startswith('attachment; filename="assay.txt"')

    markdown = client.get(f"/protocol-cards/attachments/{attachment_bundle_id}/extracted-markdown")
    assert markdown.status_code == 200
    assert markdown.text.startswith("- Prepare cells")


def test_protocol_cards_api_sanitizes_attachment_derived_user_surfaces(tmp_path, monkeypatch) -> None:
    attachments_root = tmp_path / "protocol_attachments"
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_ATTACHMENTS_DIR", str(attachments_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    response = client.post(
        "/protocol-cards/draft-from-attachment",
        files={
            "file": (
                "secret-assay.txt",
                (
                    b"- Prime pump with Authorization: Bearer protocol-api-token-123\n"
                    b"- Store sk-proj-protocol-api-secret-abcdef outside draft\n"
                ),
                "text/plain",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    attachment_bundle_id = payload["attachment_bundle"]["attachment_bundle_id"]
    serialized = json.dumps(payload)
    assert "protocol-api-token-123" not in serialized
    assert "sk-proj-protocol-api-secret-abcdef" not in serialized
    assert "Authorization: <redacted>" in payload["draft"]["versions"][0]["content_snapshot"]

    markdown = client.get(f"/protocol-cards/attachments/{attachment_bundle_id}/extracted-markdown")
    assert markdown.status_code == 200
    assert "protocol-api-token-123" not in markdown.text
    assert "sk-proj-protocol-api-secret-abcdef" not in markdown.text
    assert "Authorization: <redacted>" in markdown.text

    source = client.get(f"/protocol-cards/attachments/{attachment_bundle_id}/source")
    assert source.status_code == 200
    assert b"protocol-api-token-123" in source.content
    assert b"sk-proj-protocol-api-secret-abcdef" in source.content


def test_protocol_cards_api_builds_mixed_attachment_draft_with_note_context(tmp_path, monkeypatch) -> None:
    attachments_root = tmp_path / "protocol_attachments"
    artifacts_root = tmp_path / "artifacts"
    vault_dir = tmp_path / "vault"
    _write_note(vault_dir, "paper-alpha")
    _write(
        artifacts_root / "paper-alpha" / "run-current" / "claimset.resolved.json",
        (
            "{\n"
            '  "doc_id": "paper-alpha",\n'
            '  "claims": [{"claim_id": "CLM-0", "statement": "Baseline protocol evidence.", "type": "procedure", "evidence_spans": [{"quote": "Baseline protocol evidence.", "page": 1, "section": "Methods", "grounded": true, "resolution": "resolved", "source": "reader"}]}]\n'
            "}\n"
        ),
    )

    monkeypatch.setenv("PAPERPIPE_PROTOCOL_ATTACHMENTS_DIR", str(attachments_root))
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    monkeypatch.setattr(
        protocol_cards_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.post(
        "/protocol-cards/draft-from-attachment",
        data={"note_slug": "paper-alpha"},
        files={"file": ("bench.txt", b"- Warm media\n- Measure viability\n", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft"]["source_kind"] == "mixed"
    assert payload["paper_source_summary"]["note_slug"] == "paper-alpha"
    assert "## Attached Material: bench.txt" in payload["draft"]["versions"][0]["content_snapshot"]


def test_protocol_cards_api_rejects_attachment_source_path_escape(tmp_path, monkeypatch) -> None:
    attachments_root = tmp_path / "protocol_attachments"
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_ATTACHMENTS_DIR", str(attachments_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    bundle_id = "protatt_escapecheck"
    bundle_dir = attachments_root / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "attachment_bundle.json").write_text(
        json.dumps(
            {
                "attachment_bundle_id": bundle_id,
                "artifact_family": "protocol_attachment",
                "layer": "raw_source",
                "source_kind": "uploaded_file",
                "title": "escape",
                "source_filename": "escape.txt",
                "media_type": "text/plain",
                "byte_size": 7,
                "sha1": "0123456789abcdef0123456789abcdef01234567",
                "created_at": "2026-04-13T14:46:00Z",
                "source_ref": {"kind": "source_file", "path": "../escape.txt"},
                "extraction_status": "failed",
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(api_main.app)
    response = client.get(f"/protocol-cards/attachments/{bundle_id}/source")

    assert response.status_code == 400
    assert "escapes bundle directory" in response.json()["detail"]


def test_protocol_cards_api_does_not_resolve_encoded_attachment_ids_outside_root(tmp_path, monkeypatch) -> None:
    attachments_root = tmp_path / "protocol_attachments"
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)
    (outside / "attachment_bundle.json").write_text('{"sentinel":"do-not-read"}', encoding="utf-8")
    (outside / "source.txt").write_text("SENTINEL-SOURCE", encoding="utf-8")
    (outside / "extracted.md").write_text("SENTINEL-MARKDOWN", encoding="utf-8")

    monkeypatch.setenv("PAPERPIPE_PROTOCOL_ATTACHMENTS_DIR", str(attachments_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    responses = [
        client.get("/protocol-cards/attachments/..%2Foutside"),
        client.get("/protocol-cards/attachments/..%2Foutside/source"),
        client.get("/protocol-cards/attachments/..%2Foutside/extracted-markdown"),
    ]

    assert all(response.status_code in {400, 404} for response in responses)
    combined = "\n".join(response.text for response in responses)
    assert "SENTINEL" not in combined
    assert "do-not-read" not in combined
