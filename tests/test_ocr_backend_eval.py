import json
import subprocess
import sys
from pathlib import Path

import fitz

from scripts.eval import compare_ocr_backends as compare_mod


def _make_pdf(path: Path, lines: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 100
    for line in lines or []:
        page.insert_text((72, y), line)
        y += 18
    doc.save(path)
    doc.close()


def test_compare_ocr_rows_flags_candidate_unavailable_and_low_text_ratio() -> None:
    baseline_rows = [
        {
            "pdf_path": "/tmp/a.pdf",
            "success": True,
            "backend_available": True,
            "error": None,
            "text_char_count": 100,
        }
    ]
    candidate_rows = [
        {
            "pdf_path": "/tmp/a.pdf",
            "requested_backend": "paddleocr",
            "backend_available": False,
            "backend_fallback_note": "paddleocr_not_installed",
            "success": False,
            "error": "paddleocr_not_installed",
            "text_char_count": 0,
        }
    ]

    report = compare_mod.compare_ocr_rows(
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
        min_candidate_text_ratio=0.5,
        max_baseline_unavailable_docs=0,
        max_backend_unavailable_docs=0,
        max_baseline_error_docs=0,
        max_backend_error_docs=0,
        max_error_increase_docs=0,
        max_zero_text_docs=0,
        max_low_text_ratio_docs=0,
    )

    assert report["decision"]["passed"] is False
    assert "backend_unavailable_docs" in report["decision"]["failed_checks"]
    assert "error_increase_docs" in report["decision"]["failed_checks"]
    assert "low_text_ratio_docs" in report["decision"]["failed_checks"]


def test_compare_ocr_rows_flags_baseline_unavailable() -> None:
    baseline_rows = [
        {
            "pdf_path": "/tmp/a.pdf",
            "requested_backend": "ocrmypdf",
            "backend_available": False,
            "backend_fallback_note": "ocrmypdf_not_installed",
            "success": False,
            "error": "ocrmypdf_not_installed",
            "text_char_count": 0,
        }
    ]
    candidate_rows = [
        {
            "pdf_path": "/tmp/a.pdf",
            "requested_backend": "paddleocr",
            "backend_available": True,
            "success": True,
            "error": None,
            "text_char_count": 100,
        }
    ]

    report = compare_mod.compare_ocr_rows(
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
        min_candidate_text_ratio=0.5,
        max_baseline_unavailable_docs=0,
        max_backend_unavailable_docs=0,
        max_baseline_error_docs=0,
        max_backend_error_docs=0,
        max_error_increase_docs=0,
        max_zero_text_docs=0,
        max_low_text_ratio_docs=0,
    )

    assert report["decision"]["passed"] is False
    assert "baseline_unavailable_docs" in report["decision"]["failed_checks"]


def test_compare_ocr_rows_flags_backend_execution_errors_even_when_both_fail() -> None:
    baseline_rows = [
        {
            "pdf_path": "/tmp/a.pdf",
            "requested_backend": "ocrmypdf",
            "backend_available": True,
            "success": False,
            "error": "baseline_failed",
            "text_char_count": 0,
        }
    ]
    candidate_rows = [
        {
            "pdf_path": "/tmp/a.pdf",
            "requested_backend": "paddleocr",
            "backend_available": True,
            "success": False,
            "error": "candidate_failed",
            "text_char_count": 0,
        }
    ]

    report = compare_mod.compare_ocr_rows(
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
        min_candidate_text_ratio=0.5,
        max_baseline_unavailable_docs=0,
        max_backend_unavailable_docs=0,
        max_baseline_error_docs=0,
        max_backend_error_docs=0,
        max_error_increase_docs=0,
        max_zero_text_docs=0,
        max_low_text_ratio_docs=0,
    )

    assert report["decision"]["passed"] is False
    assert "baseline_error_docs" in report["decision"]["failed_checks"]
    assert "backend_error_docs" in report["decision"]["failed_checks"]


def test_flatten_paddleocr_page_result_supports_modern_dict_payload() -> None:
    payload = {
        "rec_texts": ["hello", "", "world"],
        "rec_scores": [0.9, 0.1, 0.8],
    }

    assert compare_mod._flatten_paddleocr_page_result(payload) == "hello\nworld"


def test_run_paddleocr_text_supports_modern_api_payload(tmp_path: Path, monkeypatch) -> None:
    src_pdf = tmp_path / "source.pdf"
    out_dir = tmp_path / "outputs"
    _make_pdf(src_pdf, ["first line", "second line"])

    class _FakePaddleOCR:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def ocr(self, _image_path: str):
            return [
                {
                    "rec_texts": ["alpha", "", "beta"],
                    "rec_scores": [0.9, 0.1, 0.8],
                }
            ]

    class _FakePaddleModule:
        PaddleOCR = _FakePaddleOCR

    monkeypatch.setattr(compare_mod.importlib, "import_module", lambda name: _FakePaddleModule())
    monkeypatch.setattr(compare_mod, "_paddleocr_version", lambda: "test-version")

    result = compare_mod.run_paddleocr_text(src_pdf, out_dir, lang="en")

    assert result["ocr_applied"] is True
    assert result["ocr_engine"] == "paddleocr"
    assert result["ocr_version"] == "test-version"
    assert result["error"] is None
    assert result["text_char_count"] > 0
    assert result["page_text_char_counts"] == [10]
    assert Path(str(result["text_output_path"])).read_text(encoding="utf-8") == "alpha\nbeta"
    details = json.loads((out_dir / "ocr_details.json").read_text(encoding="utf-8"))
    assert details["page_count"] == 1
    assert details["page_text_char_counts"] == [10]
    assert details["pages"][0]["text_preview"] == "alpha beta"


def test_evaluate_pdf_with_backend_ocrmypdf_uses_output_pdf_text(tmp_path: Path, monkeypatch) -> None:
    src_pdf = tmp_path / "source.pdf"
    out_pdf = tmp_path / "outputs" / "ocrmypdf" / "fake.pdf"
    _make_pdf(src_pdf, ["source"])
    _make_pdf(out_pdf, ["Recovered OCR text", "second line"])

    monkeypatch.setattr(
        compare_mod,
        "run_ocr",
        lambda pdf_in, pdf_out, lang: {
            "ocr_applied": True,
            "ocr_engine": "ocrmypdf",
            "ocr_version": "test-version",
            "ocr_lang": lang,
            "ocr_output_path": str(out_pdf),
            "error": None,
        },
    )
    monkeypatch.setattr(compare_mod, "_backend_available", lambda _name: (True, None))

    row = compare_mod.evaluate_pdf_with_backend(
        src_pdf,
        "ocrmypdf",
        output_root=tmp_path / "outputs",
        lang="eng",
    )

    assert row["success"] is True
    assert row["ocr_engine"] == "ocrmypdf"
    assert row["text_char_count"] > 0
    assert row["page_text_char_counts"]
    assert row["page_text_char_counts"][0] > 0


def test_compare_ocr_backends_cli_returns_nonzero_for_failed_gate(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "eval" / "compare_ocr_backends.py"
    pdf_a = tmp_path / "a.pdf"
    manifest = tmp_path / "manifest.json"
    out_dir = tmp_path / "snapshots"
    _make_pdf(pdf_a, ["Fixture text"])
    manifest.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "local_path": str(pdf_a),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--manifest",
            str(manifest),
            "--out-dir",
            str(out_dir),
            "--run-id",
            "ocr_fixture_run",
        ],
        cwd=repo_root,
        check=False,
    )

    run_root = out_dir / "ocr_fixture_run"
    metrics = json.loads((run_root / "metrics.json").read_text(encoding="utf-8"))
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (run_root / "detailed_results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert completed.returncode == 1
    assert metrics["baseline_backend"] == "ocrmypdf"
    assert metrics["candidate_backend"] == "paddleocr"
    assert summary["status"] == "failed"
    assert summary["passed"] is False
    assert len(rows) == 2
    assert "backend_unavailable_docs" in metrics["comparison"]["decision"]["failed_checks"]
    candidate_row = next(row for row in rows if row["requested_backend"] == "paddleocr")
    assert candidate_row["backend_available"] is False
    assert candidate_row["error"] == "paddleocr_not_installed"
