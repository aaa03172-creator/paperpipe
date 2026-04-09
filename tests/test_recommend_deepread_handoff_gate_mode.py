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
