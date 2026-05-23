import json
from src.institutional_access import (
    generate_institutional_proxy_url,
    upsert_institutional_proxy_link,
    extract_institutional_proxy_link,
)

def test_generate_institutional_proxy_url_from_doi():
    url = generate_institutional_proxy_url(doi="10.1038/s41586-020-2165-8")
    assert url == "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1038/s41586-020-2165-8"

def test_generate_institutional_proxy_url_from_clean_doi():
    url = generate_institutional_proxy_url(doi="https://doi.org/10.1038/nature1234")
    assert url == "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1038/nature1234"

def test_generate_institutional_proxy_url_from_publisher():
    url = generate_institutional_proxy_url(publisher_url="https://www.nature.com/articles/s41586-020-2165-8")
    assert url == "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://www.nature.com/articles/s41586-020-2165-8"

def test_generate_institutional_proxy_url_fallback():
    url = generate_institutional_proxy_url(doi=None, publisher_url=None)
    assert url is None

def test_generate_institutional_proxy_url_does_not_use_paper_id_as_doi():
    url = generate_institutional_proxy_url(
        paper={"paper_id": "local--paper-001", "doi": None, "feedback_json": "{}"}
    )
    assert url is None

def test_upsert_institutional_proxy_link_on_empty_dict():
    res = upsert_institutional_proxy_link("{}", "https://example.com/proxy")
    parsed = json.loads(res)
    assert parsed["links"]["institutional_proxy_url"] == "https://example.com/proxy"

def test_upsert_institutional_proxy_link_preserves_existing():
    initial = '{"decision": "APPROVED", "soft_tags": ["a", "b"]}'
    res = upsert_institutional_proxy_link(initial, "https://example.com/proxy")
    parsed = json.loads(res)
    assert parsed["decision"] == "APPROVED"
    assert parsed["soft_tags"] == ["a", "b"]
    assert parsed["links"]["institutional_proxy_url"] == "https://example.com/proxy"

def test_extract_institutional_proxy_link():
    payload = '{"links": {"institutional_proxy_url": "https://example.com/test"}}'
    assert extract_institutional_proxy_link(payload) == "https://example.com/test"
    
def test_extract_institutional_proxy_link_missing():
    assert extract_institutional_proxy_link("{}") is None
    assert extract_institutional_proxy_link("") is None
