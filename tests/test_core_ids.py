from src.core.ids import (
    classify_paper_id,
    is_canonical_paper_id,
    make_paper_id,
    normalize_doi,
    propose_canonical_paper_id,
)


def test_normalize_doi_strips_prefix_and_case():
    assert normalize_doi("https://doi.org/10.1000/ABC.1") == "10.1000/abc.1"
    assert normalize_doi("DOI:10.2000/XyZ") == "10.2000/xyz"


def test_make_paper_id_priority_order():
    assert make_paper_id(zotero_key="PaperKey", doi="10.1000/abc") == "zotero:PaperKey"
    assert make_paper_id(doi="https://doi.org/10.1000/AbC") == "doi:10.1000/abc"
    assert make_paper_id(fallback="PMID:12345") == "PMID:12345"


def test_canonical_paper_id_detection():
    assert is_canonical_paper_id("doi:10.1000/abc") is True
    assert is_canonical_paper_id("zotero:ABCD1234") is True
    assert is_canonical_paper_id("pdfsha256:deadbeef") is True
    assert is_canonical_paper_id("10.1000/abc") is False
    assert is_canonical_paper_id("https://doi.org/10.1000/abc") is False


def test_classify_paper_id_supports_operational_audit():
    assert classify_paper_id("doi:10.1000/abc") == "canonical:doi"
    assert classify_paper_id("zotero:XYZ") == "canonical:zotero"
    assert classify_paper_id("10.1000/abc") == "legacy:doi_like"
    assert classify_paper_id("https://example.org/paper") == "legacy:url_like"
    assert classify_paper_id("local--1234") == "legacy:local_like"
    assert classify_paper_id("PMID:12345") == "legacy:other"


def test_propose_canonical_paper_id_promotes_noncanonical_when_possible(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nx\n")

    assert propose_canonical_paper_id("10.1000/abc", doi="10.1000/abc") == "doi:10.1000/abc"
    assert (
        propose_canonical_paper_id("legacy:id", zotero_key="legacyKey", doi="10.1000/abc")
        == "zotero:legacyKey"
    )
    assert propose_canonical_paper_id("legacy:id", pdf_path=pdf_path).startswith("pdfsha256:")
    assert propose_canonical_paper_id("doi:10.1000/abc", doi="10.1000/xyz") == "doi:10.1000/abc"
    assert propose_canonical_paper_id("legacy:id") == "legacy:id"
