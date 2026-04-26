#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_extraction_sidecar import write_evidence_extraction_bundle  # noqa: E402
from src.services.pubtator_adapter import load_pubtator_document, project_pubtator_to_evidence_extraction_bundle  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a PubTator-style JSON document into evidence_extraction_bundle.json format as a silver bootstrap sidecar.",
    )
    parser.add_argument("--input", required=True, help="Path to a PubTator-style JSON document or single-document BioC collection.")
    parser.add_argument("--out-dir", required=True, help="Directory where evidence_extraction_bundle.json will be written.")
    parser.add_argument("--paper-id", default=None, help="Optional paper_id override for the generated bundle.")
    parser.add_argument("--run-id", default="pubtator_adapter", help="Run identifier to store in the generated bundle.")
    parser.add_argument(
        "--source-artifact",
        default="pubtator_document.json",
        help="Source artifact label to embed in the generated bundle.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    document = load_pubtator_document(Path(args.input).expanduser().resolve())
    bundle = project_pubtator_to_evidence_extraction_bundle(
        document,
        paper_id=args.paper_id,
        run_id=args.run_id,
        source_artifact=args.source_artifact,
    )
    write_evidence_extraction_bundle(bundle, Path(args.out_dir).expanduser().resolve())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
