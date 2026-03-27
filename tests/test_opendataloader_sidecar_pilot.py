import json
from pathlib import Path

from scripts.eval.run_opendataloader_sidecar_pilot import (
    _collect_inputs,
    _expected_output_candidates,
    build_command,
    run_sidecar_pilot,
)


def test_collect_inputs_merges_pdf_flags_and_manifest_without_duplicates(tmp_path: Path) -> None:
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(b"A")
    pdf_b.write_bytes(b"B")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "documents": [
                    {"document_id": "doc-b", "local_path": str(pdf_b)},
                    {"document_id": "doc-a", "local_path": str(pdf_a)},
                ]
            }
        ),
        encoding="utf-8",
    )

    rows = _collect_inputs(pdfs=[str(pdf_a)], manifest=str(manifest))

    assert [row["document_id"] for row in rows] == [pdf_a.stem, "doc-b"]
    assert rows[0]["source_pdf_path"] == str(pdf_a.resolve())
    assert rows[1]["source_pdf_path"] == str(pdf_b.resolve())


def test_build_command_uses_single_batch_invocation() -> None:
    command = build_command(
        cli="/usr/local/bin/opendataloader-pdf",
        input_paths=["/tmp/a.pdf", "/tmp/b.pdf"],
        output_dir=Path("/tmp/out"),
        formats="json,markdown",
        use_struct_tree=True,
        image_output="external",
    )

    assert command == [
        "/usr/local/bin/opendataloader-pdf",
        "/tmp/a.pdf",
        "/tmp/b.pdf",
        "-o",
        "/tmp/out",
        "-f",
        "json,markdown",
        "--use-struct-tree",
        "--image-output",
        "external",
    ]


def test_expected_output_candidates_find_sidecar_files(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    (raw_root / "sample.json").write_text("{}", encoding="utf-8")
    (raw_root / "sample.md").write_text("# hi", encoding="utf-8")

    outputs = _expected_output_candidates(raw_root, Path("/input/sample.pdf"), ["json", "markdown", "pdf"])

    assert outputs["json"] == [str(raw_root / "sample.json")]
    assert outputs["markdown"] == [str(raw_root / "sample.md")]
    assert outputs["pdf"] == []


def test_run_sidecar_pilot_writes_summary_and_logs(tmp_path: Path, monkeypatch) -> None:
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(b"A")
    pdf_b.write_bytes(b"B")

    def fake_resolve_cli() -> str:
        return "/usr/local/bin/opendataloader-pdf"

    def fake_get_cli_version(cli: str) -> str:
        assert cli == "/usr/local/bin/opendataloader-pdf"
        return "opendataloader-pdf 2.0.0"

    class FakeResult:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""

    def fake_run(command, check, capture_output, text):
        out_dir = Path(command[command.index("-o") + 1])
        (out_dir / "a.json").write_text("{}", encoding="utf-8")
        (out_dir / "a.md").write_text("# A", encoding="utf-8")
        (out_dir / "b.json").write_text("{}", encoding="utf-8")
        (out_dir / "b.md").write_text("# B", encoding="utf-8")
        return FakeResult()

    monkeypatch.setattr("scripts.eval.run_opendataloader_sidecar_pilot._resolve_cli", fake_resolve_cli)
    monkeypatch.setattr("scripts.eval.run_opendataloader_sidecar_pilot._get_cli_version", fake_get_cli_version)
    monkeypatch.setattr("scripts.eval.run_opendataloader_sidecar_pilot.subprocess.run", fake_run)

    run_root = run_sidecar_pilot(
        pdf_rows=[
            {"document_id": "doc-a", "source_pdf_path": str(pdf_a.resolve()), "notes": "A"},
            {"document_id": "doc-b", "source_pdf_path": str(pdf_b.resolve()), "notes": "B"},
        ],
        out_dir=tmp_path / "snapshots",
        run_id="pilot_run",
        formats="json,markdown",
        use_struct_tree=False,
        image_output=None,
        manifest=None,
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "ok"
    assert summary["input_count"] == 2
    assert summary["cli_version"] == "opendataloader-pdf 2.0.0"
    assert all(doc["all_requested_outputs_present"] for doc in summary["documents"])
    assert (run_root / "stdout.log").read_text(encoding="utf-8") == "ok"
