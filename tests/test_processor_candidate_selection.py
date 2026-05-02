from __future__ import annotations

import json
from datetime import datetime as RealDateTime
from pathlib import Path
from types import SimpleNamespace

import src.processor as processor


class FixedDateTime:
    @classmethod
    def now(cls):
        return RealDateTime(2026, 4, 29)

    @classmethod
    def strptime(cls, value, fmt):
        return RealDateTime.strptime(value, fmt)

    @classmethod
    def fromisoformat(cls, value):
        return RealDateTime.fromisoformat(value)


def _config():
    return SimpleNamespace(ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)))


def _paper(
    paper_id: str,
    *,
    source: str,
    published: str,
    doi: str | None = None,
    local_pdf_path: str | None = None,
    manual_rank_score: float | None = None,
):
    paper = SimpleNamespace(
        id=paper_id,
        doi=doi,
        title=f"Candidate {paper_id}",
        authors=["A"],
        published=published,
        source=source,
        summary="Synthetic candidate selection benchmark.",
        link=f"https://example.test/{paper_id}",
        local_pdf_path=local_pdf_path,
        pdf_link=None,
        download_attempts=[],
    )
    if manual_rank_score is not None:
        paper.manual_rank_score = manual_rank_score
    return paper


def _paper_from_fixture(payload: dict[str, object]):
    return _paper(
        str(payload["id"]),
        source=str(payload["source"]),
        published=str(payload["published"]),
        doi=payload.get("doi") if isinstance(payload.get("doi"), str) else None,
        local_pdf_path=(
            payload.get("local_pdf_path")
            if isinstance(payload.get("local_pdf_path"), str)
            else None
        ),
        manual_rank_score=(
            float(payload["manual_rank_score"])
            if isinstance(payload.get("manual_rank_score"), (int, float))
            else None
        ),
    )


def test_clinical_selection_prefers_pubmed_doi_pdf_over_fresher_preprint(monkeypatch):
    monkeypatch.setattr(processor, "datetime", FixedDateTime)
    pubmed_candidate = _paper(
        "pmid:clinical-pubmed",
        source="PubMed",
        published="2026-03-20",
        doi="10.1000/clinical-pubmed",
        local_pdf_path="/tmp/clinical-pubmed.pdf",
    )
    preprint_candidate = _paper(
        "arxiv:clinical-preprint",
        source="ArXiv",
        published="2026-04-25",
        local_pdf_path="/tmp/clinical-preprint.pdf",
    )

    ranked = processor._rank_slot_candidates(
        "clinical",
        [preprint_candidate, pubmed_candidate],
        _config(),
    )

    assert [paper.id for paper in ranked] == ["pmid:clinical-pubmed", "arxiv:clinical-preprint"]
    pubmed_breakdown = processor._candidate_selection_breakdown("clinical", pubmed_candidate)
    preprint_breakdown = processor._candidate_selection_breakdown("clinical", preprint_candidate)
    assert pubmed_breakdown["source_bonus"] == 0.25
    assert preprint_breakdown["source_bonus"] == 0.04
    assert pubmed_breakdown["metadata_components"]["doi_bonus"] == 0.08
    assert pubmed_breakdown["metadata_components"]["pdf_bonus"] == 0.07
    assert pubmed_breakdown["final_score"] > preprint_breakdown["final_score"]


def test_methods_selection_allows_recent_preprint_when_pubmed_has_weak_metadata(monkeypatch):
    monkeypatch.setattr(processor, "datetime", FixedDateTime)
    weak_pubmed_candidate = _paper(
        "pmid:methods-weak",
        source="PubMed",
        published="2025-01-01",
    )
    recent_preprint_candidate = _paper(
        "arxiv:methods-recent",
        source="ArXiv",
        published="2026-04-25",
        local_pdf_path="/tmp/methods-recent.pdf",
    )

    ranked = processor._rank_slot_candidates(
        "methods",
        [weak_pubmed_candidate, recent_preprint_candidate],
        _config(),
    )

    assert [paper.id for paper in ranked] == ["arxiv:methods-recent", "pmid:methods-weak"]
    preprint_breakdown = processor._candidate_selection_breakdown("methods", recent_preprint_candidate)
    pubmed_breakdown = processor._candidate_selection_breakdown("methods", weak_pubmed_candidate)
    assert preprint_breakdown["source_bonus"] == 0.08
    assert preprint_breakdown["metadata_components"]["recency_bonus"] == 0.15
    assert pubmed_breakdown["source_bonus"] == 0.18
    assert preprint_breakdown["final_score"] > pubmed_breakdown["final_score"]


def test_mechanism_selection_preserves_manual_base_score_priority(monkeypatch):
    monkeypatch.setattr(processor, "datetime", FixedDateTime)
    high_signal_candidate = _paper(
        "pmid:mechanism-high-signal",
        source="PubMed",
        published="2025-01-01",
        manual_rank_score=0.45,
    )
    fresh_preprint_candidate = _paper(
        "arxiv:mechanism-fresh",
        source="ArXiv",
        published="2026-04-25",
        local_pdf_path="/tmp/mechanism-fresh.pdf",
    )

    ranked = processor._rank_slot_candidates(
        "mechanism",
        [fresh_preprint_candidate, high_signal_candidate],
        _config(),
    )

    assert [paper.id for paper in ranked] == ["pmid:mechanism-high-signal", "arxiv:mechanism-fresh"]
    breakdown = processor._candidate_selection_breakdown("mechanism", high_signal_candidate)
    assert breakdown["base_score"] == 0.45
    assert breakdown["source_bonus"] == 0.18
    assert breakdown["final_score"] > processor._candidate_selection_breakdown(
        "mechanism",
        fresh_preprint_candidate,
    )["final_score"]


def test_selection_tie_breaker_prefers_newer_candidate_then_original_order(monkeypatch):
    monkeypatch.setattr(processor, "datetime", FixedDateTime)
    older_equal_score = _paper(
        "pmid:older-equal-score",
        source="PubMed",
        published="2026-04-20",
    )
    newer_equal_score = _paper(
        "pmid:newer-equal-score",
        source="PubMed",
        published="2026-04-25",
    )
    same_date_first = _paper(
        "pmid:same-date-first",
        source="PubMed",
        published="2026-04-25",
    )

    ranked = processor._rank_slot_candidates(
        "mechanism",
        [older_equal_score, same_date_first, newer_equal_score],
        _config(),
    )

    assert [paper.id for paper in ranked] == [
        "pmid:same-date-first",
        "pmid:newer-equal-score",
        "pmid:older-equal-score",
    ]


def test_fixture_backed_candidate_pools_match_expected_top1(monkeypatch):
    monkeypatch.setattr(processor, "datetime", FixedDateTime)
    fixture_path = Path(__file__).parent / "fixtures" / "processor_candidate_selection_pools_20260429.json"
    fixture = json.loads(fixture_path.read_text())

    assert fixture["fixed_now"] == "2026-04-29"
    observed_top1: dict[str, str] = {}
    for pool in fixture["pools"]:
        candidates = [_paper_from_fixture(candidate) for candidate in pool["candidates"]]
        ranked = processor._rank_slot_candidates(str(pool["slot"]), candidates, _config())
        observed_top1[str(pool["id"])] = ranked[0].id

    assert observed_top1 == {
        pool["id"]: pool["expected_top1"]
        for pool in fixture["pools"]
    }
