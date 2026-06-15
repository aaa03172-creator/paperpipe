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

    assert ris_path.parent == tmp_path / "ris"
    assert ris_path.name.startswith("PMID_12345-")
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


def test_export_to_ris_writes_one_atomic_file_per_paper(tmp_path):
    first_path = export_to_ris(
        {
            "paper_id": "doi:10.1000/example",
            "doi": "10.1000/example",
            "title": "First Title",
            "authors": ["Doe J"],
            "published": "2026-03-13",
            "source": "PubMed",
            "summary": "First abstract",
            "link": "https://example.org/first",
            "slot": "mechanism",
        },
        tmp_path,
    )
    second_path = export_to_ris(
        {
            "paper_id": "doi:10.1000/example",
            "doi": "10.1000/example",
            "title": "Second Title",
            "authors": ["Doe J"],
            "published": "2026-03-13",
            "source": "PubMed",
            "summary": "Second abstract",
            "link": "https://example.org/second",
            "slot": "mechanism",
        },
        tmp_path,
    )
    other_path = export_to_ris(
        {
            "paper_id": "PMID:67890",
            "doi": "",
            "title": "Other Paper",
            "authors": ["Roe J"],
            "published": "2026-03-13",
            "source": "PubMed",
            "summary": "Other abstract",
            "link": "https://example.org/other",
            "slot": "mechanism",
        },
        tmp_path,
    )

    assert first_path == second_path
    assert first_path != other_path
    assert first_path.parent == tmp_path / "ris"
    assert first_path.name.startswith("doi_10.1000_example-")

    content = first_path.read_text(encoding="utf-8")
    assert "TI  - Second Title" in content
    assert "TI  - First Title" not in content
    assert len(list((tmp_path / "ris").glob("*.ris"))) == 2
