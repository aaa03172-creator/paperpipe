#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.biored_adapter import project_biored_to_evidence_extraction_bundle  # noqa: E402
from src.services.biored_eval import load_biored_document  # noqa: E402
from src.services.evidence_extraction_sidecar import write_evidence_extraction_bundle  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a BioRED-style JSON document into evidence_extraction_bundle.json format.",
    )
    parser.add_argument("--input", required=True, help="Path to a BioRED-style JSON document.")
    parser.add_argument("--out-dir", required=True, help="Directory where evidence_extraction_bundle.json will be written.")
    parser.add_argument("--paper-id", default=None, help="Optional paper_id override for the generated bundle.")
    parser.add_argument("--run-id", default="biored_adapter", help="Run identifier to store in the generated bundle.")
    parser.add_argument(
        "--source-artifact",
        default="biored_document.json",
        help="Source artifact label to embed in the generated bundle.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    document = load_biored_document(Path(args.input).expanduser().resolve())
    bundle = project_biored_to_evidence_extraction_bundle(
        document,
        paper_id=args.paper_id,
        run_id=args.run_id,
        source_artifact=args.source_artifact,
    )
    write_evidence_extraction_bundle(bundle, Path(args.out_dir).expanduser().resolve())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
