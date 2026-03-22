import json
import subprocess
import sys
from pathlib import Path

import fitz

from scripts.eval.compare_ingest_backends import compare_backend_rows


def _make_pdf(path: Path, lines: list[str]) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 100
    for line in lines:
        page.insert_text((72, y), line)
        y += 18
    doc.save(path)
    doc.close()


def test_compare_backend_rows_flags_expected_regressions() -> None:
    baseline_rows = [
        {
            "pdf_path": "/tmp/a.pdf",
            "success": True,
            "error": None,
            "has_doi": True,
            "doi": "10.1/example",
            "table_count": 2,
            "text_char_count": 100,
        }
    ]
    candidate_rows = [
        {
            "pdf_path": "/tmp/a.pdf",
            "requested_backend": "docling",
            "effective_backend": "docling",
            "backend_available": False,
            "backend_fallback_note": "fallback",
            "success": False,
            "error": "boom",
            "has_doi": False,
            "doi": None,
            "table_count": 0,
            "text_char_count": 10,
        }
    ]

    report = compare_backend_rows(
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
        min_candidate_text_ratio=0.5,
        max_backend_unavailable_docs=0,
        max_error_increase_docs=0,
        max_empty_text_increase_docs=0,
        max_doi_loss_docs=0,
        max_table_loss_docs=0,
        max_low_text_ratio_docs=0,
    )

    assert report["decision"]["passed"] is False
    assert "backend_unavailable_docs" in report["decision"]["failed_checks"]
    assert "error_increase_docs" in report["decision"]["failed_checks"]
    assert "doi_loss_docs" in report["decision"]["failed_checks"]
    assert "table_loss_docs" in report["decision"]["failed_checks"]
    assert "low_text_ratio_docs" in report["decision"]["failed_checks"]


def test_compare_ingest_backends_cli_writes_metrics_and_rows(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "eval" / "compare_ingest_backends.py"
    out_dir = tmp_path / "snapshots"
    pdf_a = tmp_path / "doi_text.pdf"
    pdf_b = tmp_path / "plain_text.pdf"

    _make_pdf(pdf_a, ["Methods and results", "DOI: 10.1234/example.2026"])
    _make_pdf(pdf_b, ["This is a plain fixture page.", "No DOI or table present."])

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--pdf",
            str(pdf_a),
            "--pdf",
            str(pdf_b),
            "--out-dir",
            str(out_dir),
            "--run-id",
            "fixture_run",
        ],
        check=True,
        cwd=repo_root,
    )

    run_root = out_dir / "fixture_run"
    metrics = json.loads((run_root / "metrics.json").read_text(encoding="utf-8"))
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (run_root / "detailed_results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert metrics["document_count"] == 2
    assert metrics["baseline_backend"] == "fitz_pdfplumber"
    assert metrics["candidate_backend"] == "docling"
    assert summary["status"] == "ok"
    assert len(rows) == 4
    assert any(row["requested_backend"] == "fitz_pdfplumber" for row in rows)
    assert any(row["requested_backend"] == "docling" for row in rows)
    assert any(row["has_doi"] for row in rows)
