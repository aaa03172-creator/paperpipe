from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main as api_main
from backend.routers import paper_notes as paper_notes_router


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _note_content(
    *,
    note_id: str,
    alias: str,
    tags: list[str],
    date_processed: str,
    confidence: float,
    status: str,
    related_slug: str | None = None,
    doi: str | None = "10.1000/182",
    zotero_link: str | None = None,
    pdf_url: str | None = None,
    reference_lines: list[str] | None = None,
) -> str:
    related_block = ""
    if related_slug:
        related_block = (
            "\n## 🔗 Related Papers\n"
            f"- [[Inbox/PaperPipe/{related_slug}|Related Title]] (shared tags: {tags[0]})\n"
        )
    references = reference_lines if reference_lines is not None else ["* [Open PDF](file:///Users/test/Documents/private.pdf)"]
    frontmatter_lines = [
        "---",
        f"id: {note_id}",
        f"aliases: [\"{alias}\"]",
        "tags:",
        *[f"  - {tag}" for tag in tags],
        f"date_processed: {date_processed}",
        f"confidence: {confidence}",
        f"status: {status}",
    ]
    if doi is not None:
        frontmatter_lines.append(f"doi: {doi}")
    if zotero_link is not None:
        frontmatter_lines.append(f"zotero_link: {zotero_link}")
    if pdf_url is not None:
        frontmatter_lines.append(f"pdf_url: {pdf_url}")
    frontmatter_lines.append("---")

    return (
        "\n".join(frontmatter_lines)
        + "\n\n"
        f"# {alias}\n\n"
        "> **One-Line Summary**\n"
        "> Summary text.\n\n"
        "## Critical Review (ClaimSet)\n"
        "### Claim 1\n"
        "- Claim: Example claim\n"
        + (f"- Context: [[Inbox/PaperPipe/{related_slug}|Related Title]]\n" if related_slug else "")
        + "- Confidence: 0.9\n"
        + related_block
        + "\n## 🔗 References\n"
        + "\n".join(references)
        + "\n"
    )


def test_paper_notes_list_builds_index_and_filters(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "zoteroduboisAlzheimerDiseaseClinicalBiological2024.md",
        _note_content(
            note_id="zotero:duboisAlzheimerDiseaseClinicalBiological2024",
            alias="Alzheimer Disease as a Clinical-Biological Construct—An International Working Group Recommendation",
            tags=["Medicine/Neurology", "Alzheimers_Disease"],
            date_processed="2026-02-24",
            confidence=0.9,
            status="INDEXED",
            related_slug="zoteroduboisAmnesticMCIProdromal2004",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "zoteroduboisAmnesticMCIProdromal2004.md",
        _note_content(
            note_id="zotero:duboisAmnesticMCIProdromal2004",
            alias="Amnestic MCI or prodromal Alzheimer's disease?",
            tags=["Medicine/Neurology", "Alzheimers_Disease"],
            date_processed="2026-02-20",
            confidence=0.8,
            status="INDEXED",
        ),
    )
    _write(vault_dir / "2026-02-24.md", "# daily note\n")

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)

    response = client.get("/paper-notes")
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"
    assert (tmp_path / "storage" / "obsidian" / "paper_notes_index.json").exists()

    filtered = client.get("/paper-notes", params={"tag": "Alzheimers_Disease", "q": "prodromal"})
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["slug"] == "zoteroduboisAmnesticMCIProdromal2004"


def test_paper_note_detail_renders_properties_related_and_references(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "zoteroduboisAlzheimerDiseaseClinicalBiological2024.md",
        _note_content(
            note_id="zotero:duboisAlzheimerDiseaseClinicalBiological2024",
            alias="Alzheimer Disease as a Clinical-Biological Construct—An International Working Group Recommendation",
            tags=["Medicine/Neurology", "Alzheimers_Disease"],
            date_processed="2026-02-24",
            confidence=0.9,
            status="INDEXED",
            related_slug="zoteroduboisAmnesticMCIProdromal2004",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "zoteroduboisAmnesticMCIProdromal2004.md",
        _note_content(
            note_id="zotero:duboisAmnesticMCIProdromal2004",
            alias="Amnestic MCI or prodromal Alzheimer's disease?",
            tags=["Medicine/Neurology", "Alzheimers_Disease"],
            date_processed="2026-02-20",
            confidence=0.8,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/zoteroduboisAlzheimerDiseaseClinicalBiological2024")
    assert response.status_code == 200

    payload = response.json()
    assert payload["note"]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"
    assert payload["frontmatter"]["status"] == "INDEXED"
    assert "One-Line Summary" in payload["body_markdown"]
    assert "## 🔗 Related Papers" not in payload["body_markdown"]
    assert "/papers/zoteroduboisAmnesticMCIProdromal2004" in payload["body_markdown"]

    assert len(payload["related"]) == 1
    assert payload["related"][0]["slug"] == "zoteroduboisAmnesticMCIProdromal2004"
    assert "Medicine/Neurology" in payload["related"][0]["shared_tags"]

    assert len(payload["references"]) >= 1
    assert payload["references"][0]["source"] == "pdf"
    assert payload["references"][0]["label"] == "Open PDF"


def test_paper_notes_list_supports_status_filter_and_sorting(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-alpha.md",
        _note_content(
            note_id="zotero:alpha",
            alias="Alpha Note",
            tags=["Tag/Shared"],
            date_processed="2026-01-01",
            confidence=0.95,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-beta.md",
        _note_content(
            note_id="zotero:beta",
            alias="Beta Note",
            tags=["Tag/Other"],
            date_processed="2026-03-01",
            confidence=0.55,
            status="REVIEW",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-gamma.md",
        _note_content(
            note_id="zotero:gamma",
            alias="Gamma Note",
            tags=["Tag/Shared"],
            date_processed="2026-02-01",
            confidence=0.8,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )
    client = TestClient(api_main.app)

    confidence_sorted = client.get(
        "/paper-notes",
        params={"status": "INDEXED", "sort_by": "confidence", "sort_order": "asc"},
    )
    assert confidence_sorted.status_code == 200
    confidence_payload = confidence_sorted.json()
    assert confidence_payload["total"] == 2
    assert [item["slug"] for item in confidence_payload["items"]] == ["note-gamma", "note-alpha"]

    date_sorted = client.get("/paper-notes", params={"sort_by": "date_processed", "sort_order": "asc"})
    assert date_sorted.status_code == 200
    date_payload = date_sorted.json()
    assert [item["slug"] for item in date_payload["items"][:3]] == ["note-alpha", "note-gamma", "note-beta"]


def test_paper_notes_list_supports_multi_tag_filter_and_pagination(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-one.md",
        _note_content(
            note_id="zotero:one",
            alias="Note One",
            tags=["A"],
            date_processed="2026-01-01",
            confidence=0.1,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-two.md",
        _note_content(
            note_id="zotero:two",
            alias="Note Two",
            tags=["B"],
            date_processed="2026-01-02",
            confidence=0.2,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-three.md",
        _note_content(
            note_id="zotero:three",
            alias="Note Three",
            tags=["A", "B"],
            date_processed="2026-01-03",
            confidence=0.3,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )
    client = TestClient(api_main.app)

    response = client.get(
        "/paper-notes",
        params={
            "tags": "A,B",
            "sort_by": "date_processed",
            "sort_order": "desc",
            "page": 2,
            "page_size": 1,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 3
    assert payload["page"] == 2
    assert payload["page_size"] == 1
    assert payload["total_pages"] == 3
    assert len(payload["items"]) == 1
    assert payload["items"][0]["slug"] == "note-two"
    assert sorted(payload["available_tags"]) == ["A", "B"]
    assert payload["available_statuses"] == ["INDEXED"]


def test_paper_note_detail_related_limit_and_scoring(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "target-note.md",
        _note_content(
            note_id="zotero:target",
            alias="Target Note",
            tags=["A", "B", "C"],
            date_processed="2026-02-28",
            confidence=0.7,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "triple-match.md",
        _note_content(
            note_id="zotero:triple",
            alias="Triple Match",
            tags=["A", "B", "C"],
            date_processed="2026-02-01",
            confidence=0.5,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "double-match.md",
        _note_content(
            note_id="zotero:double",
            alias="Double Match",
            tags=["A", "B"],
            date_processed="2026-03-01",
            confidence=0.99,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )
    client = TestClient(api_main.app)

    response = client.get("/paper-notes/target-note", params={"related_limit": 1})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["related"]) == 1
    assert payload["related"][0]["slug"] == "triple-match"
    assert payload["related"][0]["shared_tags"] == ["A", "B", "C"]


def test_paper_note_detail_excludes_pdf_references_when_path_masking_enabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_MASK_LOCAL_PATHS", "1")
    monkeypatch.delenv("PAPERPIPE_MASK_LOCAL_PATHS", raising=False)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "masked-note.md",
        _note_content(
            note_id="zotero:masked",
            alias="Masked Note",
            tags=["Tag/One"],
            date_processed="2026-02-24",
            confidence=0.9,
            status="INDEXED",
            doi="10.1016/S1474-4422(24)00001-2",
            zotero_link="zotero://select/items/1_ABCDE",
            pdf_url="file:///Users/test/Documents/private.pdf",
            reference_lines=[
                "* [Open PDF](file:///Users/test/Documents/private.pdf)",
                "* [Publisher Link](https://example.org/paper)",
            ],
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/masked-note")
    assert response.status_code == 200
    payload = response.json()

    sources = [item["source"] for item in payload["references"]]
    assert "pdf" not in sources
    assert "doi" in sources
    assert "zotero" in sources
    assert "external" in sources
    labels = [item["label"] for item in payload["references"]]
    assert "Open PDF" not in labels


def test_paper_note_detail_uses_doi_and_zotero_when_pdf_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LATTICE_MASK_LOCAL_PATHS", raising=False)
    monkeypatch.delenv("PAPERPIPE_MASK_LOCAL_PATHS", raising=False)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "fallback-note.md",
        _note_content(
            note_id="zotero:fallback",
            alias="Fallback Note",
            tags=["Tag/One"],
            date_processed="2026-02-24",
            confidence=0.9,
            status="INDEXED",
            doi="10.1038/fallback",
            zotero_link="zotero://select/items/1_FALLBACK",
            pdf_url=None,
            reference_lines=["* [Publisher Link](https://example.org/fallback)"],
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/fallback-note")
    assert response.status_code == 200
    payload = response.json()

    sources = [item["source"] for item in payload["references"]]
    assert "pdf" not in sources
    assert "doi" in sources
    assert "zotero" in sources
