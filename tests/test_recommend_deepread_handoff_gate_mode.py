from types import SimpleNamespace

from scripts.eval import recommend_deepread_handoff_gate_mode as mod


def test_resolve_changed_files_prefers_explicit_files():
    files = mod.resolve_changed_files(
        files=["src/services/deepread_handoff_artifacts.py"],
        base=None,
        head=None,
        against_ref=None,
    )

    assert files == ["src/services/deepread_handoff_artifacts.py"]


def test_resolve_changed_files_uses_base_head(monkeypatch):
    monkeypatch.setattr(
        mod,
        "_diff_files",
        lambda base, head: [f"{base}->{head}"],
    )

    files = mod.resolve_changed_files(
        files=None,
        base="base123",
        head="head456",
        against_ref=None,
    )

    assert files == ["base123->head456"]


def test_resolve_changed_files_uses_merge_base_against_ref(monkeypatch):
    monkeypatch.setattr(mod, "_merge_base", lambda base_ref, head_ref: f"merge:{base_ref}:{head_ref}")
    monkeypatch.setattr(
        mod,
        "_diff_files",
        lambda base, head: [f"{base}->{head}"],
    )

    files = mod.resolve_changed_files(
        files=None,
        base=None,
        head=None,
        against_ref="origin/main",
    )

    assert files == ["merge:origin/main:HEAD->HEAD"]


def test_resolve_changed_files_errors_without_input():
    try:
        mod.resolve_changed_files(
            files=None,
            base=None,
            head=None,
            against_ref=None,
        )
    except ValueError as exc:
        assert "Provide --files OR both --base and --head OR --against-ref." in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_main_json_emits_compact_stderr_and_json_stdout(monkeypatch, capsys):
    monkeypatch.setattr(
        mod,
        "resolve_changed_files",
        lambda **_: [
            "src/services/deepread_handoff_artifacts.py",
            "tests/test_deepread_handoff_artifacts.py",
        ],
    )
    monkeypatch.setattr(
        mod,
        "classify_deepread_handoff_gate_scope",
        lambda files: SimpleNamespace(
            mode="cross-paper",
            reason="cross-paper files changed",
            relevant_files=list(files),
            continuity_files=["src/services/deepread_handoff_artifacts.py"],
            cross_paper_files=["tests/test_deepread_handoff_artifacts.py"],
            ignored_doc_files=[],
        ),
    )
    monkeypatch.setattr(
        mod.sys,
        "argv",
        ["recommend_deepread_handoff_gate_mode.py", "--files", "dummy.py", "--json"],
    )

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"mode": "cross-paper"' in captured.out
    normalized_stderr = " ".join(captured.err.split())
    assert "[recommend_deepread_handoff_gate_mode]" in captured.err
    assert "mode=cross-paper" in normalized_stderr
    assert "relevant=2" in normalized_stderr
    assert "continuity=1" in normalized_stderr
    assert "cross_paper=1" in normalized_stderr
