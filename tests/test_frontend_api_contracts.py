from __future__ import annotations

import re
from pathlib import Path

from backend.main import app


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_TYPES = REPO_ROOT / "frontend" / "src" / "app" / "lib" / "types.ts"
FRONTEND_API = REPO_ROOT / "frontend" / "src" / "app" / "lib" / "api.ts"


def _interface_body(types_text: str, interface_name: str) -> str:
    match = re.search(rf"export interface {re.escape(interface_name)}\s*\{{(?P<body>.*?)\n\}}", types_text, re.S)
    assert match is not None, f"frontend type interface missing: {interface_name}"
    return match.group("body")


def _interface_fields(types_text: str, interface_name: str) -> set[str]:
    body = _interface_body(types_text, interface_name)
    return set(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\??:", body, re.M))


def _openapi_schema_fields(schema_name: str) -> set[str]:
    schema = app.openapi()["components"]["schemas"][schema_name]
    return set(schema.get("properties", {}).keys())


def _openapi_required_fields(schema_name: str) -> set[str]:
    schema = app.openapi()["components"]["schemas"][schema_name]
    return set(schema.get("required", []))


def test_frontend_paper_notes_types_include_backend_response_contract_fields() -> None:
    types_text = FRONTEND_TYPES.read_text(encoding="utf-8")

    for schema_name, interface_name in [
        ("PaperNoteListResponse", "PaperNoteListResponse"),
        ("PaperNoteDetailResponse", "PaperNoteDetailResponse"),
        ("PaperNoteImportResponse", "PaperNoteImportResponse"),
        ("PaperNoteStructuredStateLookupResponse", "PaperNoteStructuredStateLookupResponse"),
    ]:
        backend_fields = _openapi_schema_fields(schema_name)
        frontend_fields = _interface_fields(types_text, interface_name)
        assert backend_fields <= frontend_fields

        backend_required = _openapi_required_fields(schema_name)
        frontend_body = _interface_body(types_text, interface_name)
        for field_name in backend_required:
            assert re.search(rf"^\s*{re.escape(field_name)}:", frontend_body, re.M), (
                f"{interface_name}.{field_name} is required by backend but optional or missing in frontend"
            )


def test_frontend_artifact_types_include_backend_response_contract_fields() -> None:
    types_text = FRONTEND_TYPES.read_text(encoding="utf-8")

    for schema_name, interface_name in [
        ("ArtifactBundleResponse", "ArtifactBundle"),
        ("ArtifactFileEntry", "ArtifactFileEntry"),
        ("RunInferenceSummary", "RunInferenceSummary"),
    ]:
        backend_fields = _openapi_schema_fields(schema_name)
        frontend_fields = _interface_fields(types_text, interface_name)
        assert backend_fields <= frontend_fields

    artifact_bundle_body = _interface_body(types_text, "ArtifactBundle")
    for field_name in _openapi_required_fields("ArtifactBundleResponse"):
        assert re.search(rf"^\s*{re.escape(field_name)}:", artifact_bundle_body, re.M), (
            f"ArtifactBundle.{field_name} is required by backend but optional or missing in frontend"
        )


def test_frontend_api_uses_backend_routes_for_paper_note_and_artifact_contracts() -> None:
    api_text = FRONTEND_API.read_text(encoding="utf-8")

    assert 'firstSuccess<PaperNoteListResponse>([`/paper-notes${query}`])' in api_text
    assert 'firstSuccess<PaperNoteDetailResponse>([detailPath])' in api_text
    assert "/paper-notes/resolve-by-paper-id?paper_id=" in api_text
    assert "candidates.map((candidate) => `/artifacts/${encodeURIComponent(candidate)}/latest`)" in api_text
    assert "emptyArtifactBundle(paperId)" in api_text
