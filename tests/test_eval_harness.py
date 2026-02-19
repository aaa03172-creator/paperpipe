import json
import subprocess
import sys
from pathlib import Path


def _write_goldset(goldset_dir: Path, local_pdf: Path, query_text: str = "test query") -> None:
    (goldset_dir / "pdfs").mkdir(parents=True, exist_ok=True)
    (goldset_dir / "queries.jsonl").write_text(
        json.dumps({"query_id": "q-001", "query": query_text}) + "\n",
        encoding="utf-8",
    )
    (goldset_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "documents": [
                    {
                        "document_id": "doc-001",
                        "local_path": str(local_pdf),
                        "notes": "fixture",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _run_eval(repo_root: Path, goldset_dir: Path, snapshots_dir: Path, run_id: str) -> None:
    script = repo_root / "scripts" / "eval" / "run_eval.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--goldset-dir",
            str(goldset_dir),
            "--snapshots-dir",
            str(snapshots_dir),
            "--run-id",
            run_id,
        ],
        check=True,
        cwd=repo_root,
    )


def _run_diff(repo_root: Path, base: Path, target: Path, out: Path) -> None:
    script = repo_root / "scripts" / "eval" / "diff_snapshots.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--base",
            str(base),
            "--target",
            str(target),
            "--out",
            str(out),
        ],
        check=True,
        cwd=repo_root,
    )


def test_eval_harness_determinism_stable_ids_and_keys(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    goldset_dir = tmp_path / "goldset"
    snapshots_dir = tmp_path / "snapshots"
    local_pdf = tmp_path / "doc1.pdf"
    local_pdf.write_bytes(b"%PDF-1.4 fake fixture")

    _write_goldset(goldset_dir, local_pdf, query_text="alpha query")
    _run_eval(repo_root, goldset_dir, snapshots_dir, "run_a")
    _run_eval(repo_root, goldset_dir, snapshots_dir, "run_b")

    a_ingest = json.loads((snapshots_dir / "run_a" / "ingest" / "doc-001.json").read_text(encoding="utf-8"))
    b_ingest = json.loads((snapshots_dir / "run_b" / "ingest" / "doc-001.json").read_text(encoding="utf-8"))

    assert a_ingest["document_id"] == "doc-001"
    assert b_ingest["document_id"] == "doc-001"
    assert set(a_ingest.keys()) == set(b_ingest.keys())
    assert a_ingest["output_keys"] == b_ingest["output_keys"]


def test_eval_harness_snapshot_integrity_for_fixture_doc(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    goldset_dir = tmp_path / "goldset"
    snapshots_dir = tmp_path / "snapshots"
    local_pdf = tmp_path / "doc1.pdf"
    local_pdf.write_bytes(b"%PDF-1.4 fake fixture")

    _write_goldset(goldset_dir, local_pdf, query_text="beta query")
    _run_eval(repo_root, goldset_dir, snapshots_dir, "run_integrity")

    run_root = snapshots_dir / "run_integrity"
    assert (run_root / "summary.json").exists()
    assert (run_root / "ingest" / "doc-001.json").exists()
    assert (run_root / "reader" / "doc-001.json").exists()
    assert (run_root / "index" / "doc-001.json").exists()
    assert (run_root / "stats" / "doc-001.json").exists()
    assert (run_root / "queries" / "q-001.json").exists()


def test_eval_harness_diff_report_sanity_counts(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    goldset_dir = tmp_path / "goldset"
    snapshots_dir = tmp_path / "snapshots"
    local_pdf = tmp_path / "doc1.pdf"
    local_pdf.write_bytes(b"%PDF-1.4 fake fixture")

    _write_goldset(goldset_dir, local_pdf, query_text="gamma query")
    _run_eval(repo_root, goldset_dir, snapshots_dir, "run_1")

    # Change query text to force at least one changed file.
    _write_goldset(goldset_dir, local_pdf, query_text="gamma query updated")
    _run_eval(repo_root, goldset_dir, snapshots_dir, "run_2")

    diff_out = snapshots_dir / "diff_run_1_2.json"
    _run_diff(repo_root, snapshots_dir / "run_1", snapshots_dir / "run_2", diff_out)

    diff = json.loads(diff_out.read_text(encoding="utf-8"))
    assert isinstance(diff["added"], int)
    assert isinstance(diff["removed"], int)
    assert isinstance(diff["changed"], int)
    assert diff["changed"] >= 1
    assert (snapshots_dir / "diff_run_1_2.txt").exists()
