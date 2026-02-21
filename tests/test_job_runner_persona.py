from types import SimpleNamespace
from pathlib import Path

import backend.services.job_runner as job_runner


def test_resolve_persona_hint_returns_none_for_default(monkeypatch):
    monkeypatch.setattr(job_runner, "load_profiles", lambda: SimpleNamespace(profiles=[]))
    assert job_runner._resolve_persona_hint("default") is None


def test_resolve_persona_hint_reads_enabled_profile(monkeypatch):
    profile = SimpleNamespace(
        id="coglab",
        title="Cognitive Lab",
        enabled=True,
        notes="prioritize confounds",
        query=SimpleNamespace(to_boolean_string=lambda: "(memory AND confound)"),
    )
    monkeypatch.setattr(job_runner, "load_profiles", lambda: SimpleNamespace(profiles=[profile]))

    hint = job_runner._resolve_persona_hint("coglab")

    assert hint is not None
    assert "profile_id=coglab" in hint
    assert "title=Cognitive Lab" in hint
    assert "notes=prioritize confounds" in hint
    assert "query_focus=(memory AND confound)" in hint


def test_resolve_persona_hint_skips_disabled_profile(monkeypatch):
    profile = SimpleNamespace(
        id="coglab",
        title="Cognitive Lab",
        enabled=False,
        notes="x",
        query=SimpleNamespace(to_boolean_string=lambda: "x"),
    )
    monkeypatch.setattr(job_runner, "load_profiles", lambda: SimpleNamespace(profiles=[profile]))
    assert job_runner._resolve_persona_hint("coglab") is None


def test_load_similar_feedback_top3_ignores_same_paper_and_limits(tmp_path, monkeypatch):
    feedback_file = tmp_path / "feedback.jsonl"
    feedback_file.write_text(
        "\n".join(
            [
                '{"paper_id":"same","accepted":true,"user_correction":"should be ignored"}',
                '{"paper_id":"p1","accepted":false,"user_correction":"corr1 rejected"}',
                '{"paper_id":"p2","accepted":true,"user_correction":"corr2"}',
                '{"paper_id":"p2","accepted":true,"user_correction":"corr2 duplicate latest"}',
                '{"paper_id":"p3","accepted":true,"user_correction":"corr3"}',
                '{"paper_id":"p4","accepted":true,"user_correction":"corr4"}',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(job_runner, "FEEDBACK_FILE", feedback_file)

    top3 = job_runner._load_similar_feedback_top3("same", limit=3)

    assert len(top3) == 3
    # reverse scan (latest first)
    assert top3[0]["paper_id"] == "p4"
    assert top3[1]["paper_id"] == "p3"
    assert top3[2]["paper_id"] == "p2"
