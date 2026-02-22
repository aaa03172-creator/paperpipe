from __future__ import annotations

from src.core.paper_identity import make_paper_key


def test_make_paper_key_is_deterministic_and_safe():
    paper_id = "doi:10.1000/My Paper (v2)"
    key1 = make_paper_key(paper_id)
    key2 = make_paper_key(paper_id)

    assert key1 == key2
    assert len(key1) > 8
    assert key1.count("_") >= 1
    assert key1.replace("_", "").isalnum()


def test_make_paper_key_handles_empty_input():
    key = make_paper_key("")
    assert key.startswith("paper_")
