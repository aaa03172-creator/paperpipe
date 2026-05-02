from src.zotero import export_to_ris


def test_export_to_ris_omits_do_field_when_doi_missing(tmp_path):
    ris_path = export_to_ris(
        {
            "id": "PMID:12345",
            "doi": "",
            "title": "PubMed Only Paper",
            "authors": ["Doe J"],
            "published": "2026-03-13",
            "source": "PubMed",
            "summary": "Abstract",
            "link": "https://example.org/paper",
            "slot": "mechanism",
        },
        tmp_path,
    )

    content = ris_path.read_text(encoding="utf-8")

    assert "DO  -" not in content
    assert "UR  - https://example.org/paper" in content


def test_export_to_ris_uses_explicit_doi_field(tmp_path):
    ris_path = export_to_ris(
        {
            "id": "PMID:12345",
            "doi": "10.1000/example",
            "title": "PubMed Plus DOI Paper",
            "authors": ["Doe J"],
            "published": "2026-03-13",
            "source": "PubMed",
            "summary": "Abstract",
            "link": "https://example.org/paper",
            "slot": "mechanism",
        },
        tmp_path,
    )

    content = ris_path.read_text(encoding="utf-8")

    assert "DO  - 10.1000/example" in content
