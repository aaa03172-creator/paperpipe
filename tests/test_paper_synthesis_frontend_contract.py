from pathlib import Path
import re


def test_frontend_paper_synthesis_client_prefers_split_manifest_and_markdown_routes() -> None:
    root = Path(__file__).resolve().parents[1]
    api_path = root / "frontend" / "src" / "app" / "lib" / "api.ts"
    types_path = root / "frontend" / "src" / "app" / "lib" / "types.ts"

    api_text = api_path.read_text(encoding="utf-8")
    types_text = types_path.read_text(encoding="utf-8")

    assert "export async function getPaperSynthesisManifest(" in api_text
    assert "`/paper-syntheses/${encodeURIComponent(normalizedId)}/manifest`" in api_text
    assert "export function getPaperSynthesisMarkdownUrl(" in api_text
    assert "`/paper-syntheses/${encodeURIComponent(synthesisId)}/markdown`" in api_text
    assert "getPaperSynthesisDetail" not in api_text
    assert "PaperSynthesisDetail" not in api_text

    bare_bundle_route_pattern = re.compile(r"/paper-syntheses/\$\{encodeURIComponent\(normalizedId\)\}(?!/)")
    assert not bare_bundle_route_pattern.search(api_text)

    assert "export interface PaperSynthesisManifest" in types_text
    assert "export interface PaperSynthesisDetail" not in types_text
