#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_manifest_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents = payload.get("documents") or []
    rows: list[dict[str, Any]] = []
    for doc in documents:
        if isinstance(doc, dict):
            rows.append(dict(doc))
    return rows


def _collect_inputs(*, pdfs: list[str], manifest: str | None) -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []

    def _append_row(raw_path: str, *, document_id: str | None = None, notes: str | None = None) -> None:
        resolved = Path(raw_path).expanduser().resolve()
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "document_id": document_id or resolved.stem,
                "source_pdf_path": key,
                "notes": notes,
            }
        )

    for raw in pdfs:
        _append_row(raw)

    if manifest:
        for row in _load_manifest_rows(Path(manifest).expanduser().resolve()):
            local_path = str(row.get("local_path") or row.get("source_pdf_path") or "").strip()
            if not local_path:
                continue
            _append_row(
                local_path,
                document_id=str(row.get("document_id") or "").strip() or None,
                notes=str(row.get("notes") or "").strip() or None,
            )

    return rows


def _resolve_cli() -> str:
    cli = shutil.which("opendataloader-pdf")
    if cli:
        return cli
    raise FileNotFoundError(
        "opendataloader-pdf CLI not found in PATH. Install OpenDataLoader PDF separately before running this bounded pilot."
    )


def _get_cli_version(cli: str) -> str | None:
    try:
        result = subprocess.run(
            [cli, "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    text = (result.stdout or result.stderr or "").strip()
    return text or None


def build_command(
    *,
    cli: str,
    input_paths: list[str],
    output_dir: Path,
    formats: str,
    use_struct_tree: bool = False,
    image_output: str | None = None,
) -> list[str]:
    command = [cli, *input_paths, "-o", str(output_dir), "-f", formats]
    if use_struct_tree:
        command.append("--use-struct-tree")
    if image_output:
        command.extend(["--image-output", image_output])
    return command


def _expected_output_candidates(output_dir: Path, pdf_path: Path, formats: list[str]) -> dict[str, list[str]]:
    stem = pdf_path.stem
    normalized_formats = [fmt.strip().lower() for fmt in formats if fmt.strip()]
    suffix_map = {
        "json": ".json",
        "markdown": ".md",
        "html": ".html",
        "pdf": ".pdf",
        "text": ".txt",
    }
    candidates: dict[str, list[str]] = {}
    for fmt in normalized_formats:
        suffix = suffix_map.get(fmt)
        if suffix is None:
            candidates[fmt] = []
            continue
        matches = sorted(
            {
                str(path)
                for path in output_dir.rglob(f"{stem}{suffix}")
            }
        )
        candidates[fmt] = matches
    return candidates


def run_sidecar_pilot(
    *,
    pdf_rows: list[dict[str, Any]],
    out_dir: Path,
    run_id: str,
    formats: str,
    use_struct_tree: bool,
    image_output: str | None,
    manifest: str | None,
) -> Path:
    if not pdf_rows:
        raise ValueError("Provide at least one --pdf or a manifest with documents[].local_path entries.")

    cli = _resolve_cli()
    run_root = out_dir / run_id
    raw_root = run_root / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)

    missing_inputs = [
        row["source_pdf_path"] for row in pdf_rows if not Path(str(row["source_pdf_path"])).exists()
    ]
    if missing_inputs:
        raise FileNotFoundError(f"Missing input PDFs: {missing_inputs}")

    input_paths = [str(row["source_pdf_path"]) for row in pdf_rows]
    command = build_command(
        cli=cli,
        input_paths=input_paths,
        output_dir=raw_root,
        formats=formats,
        use_struct_tree=use_struct_tree,
        image_output=image_output,
    )
    result = subprocess.run(command, check=False, capture_output=True, text=True)

    (run_root / "stdout.log").write_text(result.stdout or "", encoding="utf-8")
    (run_root / "stderr.log").write_text(result.stderr or "", encoding="utf-8")

    normalized_formats = [fmt.strip().lower() for fmt in formats.split(",") if fmt.strip()]
    documents: list[dict[str, Any]] = []
    for row in pdf_rows:
        pdf_path = Path(str(row["source_pdf_path"]))
        outputs = _expected_output_candidates(raw_root, pdf_path, normalized_formats)
        documents.append(
            {
                "document_id": row["document_id"],
                "source_pdf_path": str(pdf_path),
                "notes": row.get("notes"),
                "outputs": outputs,
                "all_requested_outputs_present": all(bool(paths) for paths in outputs.values()),
            }
        )

    summary = {
        "schema_version": "opendataloader_sidecar_pilot.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "status": "ok" if result.returncode == 0 else "failed",
        "return_code": result.returncode,
        "manifest": manifest,
        "cli_path": cli,
        "cli_version": _get_cli_version(cli),
        "formats": normalized_formats,
        "use_struct_tree": use_struct_tree,
        "image_output": image_output,
        "input_count": len(pdf_rows),
        "command": command,
        "documents": documents,
    }
    _write_json(run_root / "summary.json", summary)
    _write_json(
        run_root / "run_manifest.json",
        {
            "schema_version": "opendataloader_sidecar_manifest.v1",
            "generated_at": _utc_now_iso(),
            "manifest": manifest,
            "documents": pdf_rows,
        },
    )

    if result.returncode != 0:
        raise RuntimeError(f"OpenDataLoader PDF sidecar pilot failed with exit code {result.returncode}")

    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run OpenDataLoader PDF as a bounded batch-sidecar pilot without changing PaperPipe runtime parsing."
    )
    parser.add_argument("--pdf", action="append", default=[], help="PDF path to evaluate. Repeat as needed.")
    parser.add_argument(
        "--manifest",
        default="",
        help="Optional manifest with documents[].local_path entries.",
    )
    parser.add_argument(
        "--out-dir",
        default="snapshots/opendataloader_sidecar_eval",
        help="Output root directory for sidecar pilot runs.",
    )
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    parser.add_argument(
        "--formats",
        default="json,markdown",
        help="Requested OpenDataLoader output formats, comma-separated.",
    )
    parser.add_argument(
        "--use-struct-tree",
        action="store_true",
        help="Enable tagged-PDF structure tree support for the batch run.",
    )
    parser.add_argument(
        "--image-output",
        default="",
        help="Optional image output mode passed through to OpenDataLoader (e.g. external).",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    pdf_rows = _collect_inputs(pdfs=list(args.pdf), manifest=(str(args.manifest).strip() or None))
    run_id = args.run_id or datetime.now(timezone.utc).strftime("opendataloader_sidecar_%Y%m%d_%H%M%S")
    run_root = run_sidecar_pilot(
        pdf_rows=pdf_rows,
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=run_id,
        formats=str(args.formats or "json,markdown"),
        use_struct_tree=bool(args.use_struct_tree),
        image_output=(str(args.image_output).strip() or None),
        manifest=(str(args.manifest).strip() or None),
    )
    print(f"[run_opendataloader_sidecar_pilot] out={run_root}")
    print(f"[run_opendataloader_sidecar_pilot] summary={run_root / 'summary.json'}")


if __name__ == "__main__":
    main()
