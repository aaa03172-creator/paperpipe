from pathlib import Path

from src.services.pr_scope_guard import classify_scope

from scripts.check_pr_scope import (
    _deepread_handoff_gate_annotation_line,
    _format_deepread_handoff_gate_scope,
    _format_scope,
    _write_deepread_handoff_gate_summary,
)


def test_format_scope_hides_blocked_docs_line_for_docs_only():
    output = _format_scope(classify_scope(["docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md"]))

    assert "[PR-SCOPE] doc_files=1 code_files=0" in output
    assert "blocked_docs_with_code" not in output
    assert "allowed_docs_with_code" not in output


def test_format_deepread_handoff_gate_scope_reports_not_applicable_for_docs_only():
    output = _format_deepread_handoff_gate_scope(["docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md"])

    assert "[DEEPREAD-HANDOFF-GATE] mode=not_applicable" in output
    assert "ignored_doc_files=docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md" in output
    assert "next=" not in output


def test_format_deepread_handoff_gate_scope_reports_continuity_next_step():
    output = _format_deepread_handoff_gate_scope(
        ["goldset/manifests/deepread_handoff_coric_regression_20260408.json"]
    )

    assert "[DEEPREAD-HANDOFF-GATE] mode=continuity" in output
    assert "continuity_files=goldset/manifests/deepread_handoff_coric_regression_20260408.json" in output
    assert "run_recommended_deepread_handoff_gate.py" in output


def test_format_deepread_handoff_gate_scope_reports_cross_paper_next_step():
    output = _format_deepread_handoff_gate_scope(["src/services/deepread_handoff_artifacts.py"])

    assert "[DEEPREAD-HANDOFF-GATE] mode=cross-paper" in output
    assert "cross_paper_files=src/services/deepread_handoff_artifacts.py" in output
    assert "--multicase-new <multicase_audit_dir>" in output


def test_write_deepread_handoff_gate_summary_appends_markdown(tmp_path, monkeypatch):
    summary_path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    _write_deepread_handoff_gate_summary(["src/services/deepread_handoff_artifacts.py"])

    content = summary_path.read_text(encoding="utf-8")
    assert "## DeepRead Handoff Gate Advisory" in content
    assert "- mode: `cross-paper`" in content
    assert "run_recommended_deepread_handoff_gate.py" in content


def test_write_deepread_handoff_gate_summary_noops_without_env(tmp_path, monkeypatch):
    summary_path = tmp_path / "summary.md"
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    _write_deepread_handoff_gate_summary(["src/services/deepread_handoff_artifacts.py"])

    assert not Path(summary_path).exists()


def test_deepread_handoff_gate_annotation_line_returns_none_for_not_applicable():
    assert _deepread_handoff_gate_annotation_line(["docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md"]) is None


def test_deepread_handoff_gate_annotation_line_reports_cross_paper_notice():
    line = _deepread_handoff_gate_annotation_line(["src/services/deepread_handoff_artifacts.py"])

    assert line is not None
    assert line.startswith("::notice title=DeepRead Handoff Gate::")
    assert "mode=cross-paper" in line
    assert "run_recommended_deepread_handoff_gate.py" in line
