import requests

from src.verify.anchor_api import resolve_anchor_api_context


class _Resp:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_resolve_anchor_api_context_without_doi_returns_no_api() -> None:
    result = resolve_anchor_api_context("file:paper.pdf")
    assert result["provider"] == "none"
    assert result["status"] == "no_doi"
    assert "NO_DOI" in result["reason_codes"]
    assert "NO_API" in result["reason_codes"]


def test_resolve_anchor_api_context_prefers_crossref(monkeypatch) -> None:
    def fake_get(url, timeout=None, headers=None):
        if "crossref" in url:
            return _Resp(200)
        raise AssertionError("semantic scholar should not be called when crossref succeeds")

    monkeypatch.setattr(requests, "get", fake_get)
    result = resolve_anchor_api_context("doi:10.1000/xyz123")
    assert result["provider"] == "crossref"
    assert result["status"] == "ok"
    assert result["reason_codes"] == ["CROSSREF_OK"]


def test_resolve_anchor_api_context_uses_doi_hint_when_doc_id_is_file(monkeypatch) -> None:
    def fake_get(url, timeout=None, headers=None):
        if "crossref" in url:
            return _Resp(200)
        raise AssertionError("semantic scholar should not be called when crossref succeeds")

    monkeypatch.setattr(requests, "get", fake_get)
    result = resolve_anchor_api_context(
        "file:paper.pdf",
        doi_hint="https://doi.org/10.1000/xyz123",
        source_ref="/tmp/paper.pdf",
    )
    assert result["doi"] == "10.1000/xyz123"
    assert result["provider"] == "crossref"
    assert result["status"] == "ok"
    assert result["reason_codes"] == ["CROSSREF_OK"]


def test_resolve_anchor_api_context_falls_back_to_semantic_scholar(monkeypatch) -> None:
    def fake_get(url, timeout=None, headers=None):
        if "crossref" in url:
            return _Resp(404)
        if "semanticscholar" in url:
            return _Resp(200)
        return _Resp(500)

    monkeypatch.setattr(requests, "get", fake_get)
    result = resolve_anchor_api_context("doi:10.1000/xyz123")
    assert result["provider"] == "semantic_scholar"
    assert result["status"] == "ok"
    assert "CROSSREF_NOT_FOUND" in result["reason_codes"]
    assert "S2_OK" in result["reason_codes"]


def test_resolve_anchor_api_context_marks_no_api_when_both_fail(monkeypatch) -> None:
    def fake_get(url, timeout=None, headers=None):
        if "crossref" in url:
            return _Resp(503)
        if "semanticscholar" in url:
            return _Resp(404)
        return _Resp(500)

    monkeypatch.setattr(requests, "get", fake_get)
    result = resolve_anchor_api_context("doi:10.1000/xyz123")
    assert result["provider"] == "none"
    assert result["status"] == "unavailable"
    assert "CROSSREF_HTTP_503" in result["reason_codes"]
    assert "S2_NOT_FOUND" in result["reason_codes"]
    assert "NO_API" in result["reason_codes"]
