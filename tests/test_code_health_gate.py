from pathlib import Path

from scripts.code_health_report import build_report


def test_code_health_gate_no_oversized_source_files():
    repo_root = Path(__file__).resolve().parents[1]
    report = build_report(repo_root=repo_root, max_lines=450, top_n=25)
    assert report["oversize_files"] == []


def test_code_health_gate_minimum_test_ratio():
    repo_root = Path(__file__).resolve().parents[1]
    report = build_report(repo_root=repo_root, max_lines=450, top_n=25)
    assert report["test_to_src_ratio"] >= 0.5
