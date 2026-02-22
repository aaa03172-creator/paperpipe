from pathlib import Path

from scripts.code_health_report import build_report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_report_calculates_ratio_and_detects_duplicates(tmp_path):
    _write(
        tmp_path / "src" / "a.py",
        "def foo():\n    return 1\n\ndef only_a():\n    return 2\n",
    )
    _write(
        tmp_path / "src" / "b.py",
        "def foo():\n    return 3\n",
    )
    _write(
        tmp_path / "tests" / "test_a.py",
        "def test_dummy():\n    assert True\n",
    )

    report = build_report(repo_root=tmp_path, max_lines=3, top_n=5)

    assert report["src_total_lines"] > 0
    assert report["tests_total_lines"] > 0
    assert report["test_to_src_ratio"] > 0

    names = {item["name"] for item in report["duplicate_function_names_top10"]}
    assert "foo" in names
    assert any(lines > 3 for _, lines in report["oversize_files"])
