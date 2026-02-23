from src.core.ids import make_paper_id, normalize_doi


def test_normalize_doi_strips_prefix_and_case():
    assert normalize_doi("https://doi.org/10.1000/ABC.1") == "10.1000/abc.1"
    assert normalize_doi("DOI:10.2000/XyZ") == "10.2000/xyz"


def test_make_paper_id_priority_order():
    assert make_paper_id(zotero_key="PaperKey", doi="10.1000/abc") == "zotero:PaperKey"
    assert make_paper_id(doi="https://doi.org/10.1000/AbC") == "doi:10.1000/abc"
    assert make_paper_id(fallback="PMID:12345") == "PMID:12345"
