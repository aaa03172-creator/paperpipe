#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.bc5cdr_eval import (  # noqa: E402
    evaluate_bc5cdr_bundle,
    load_bc5cdr_document,
    load_evidence_extraction_bundle,
    write_bc5cdr_eval_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate an evidence_extraction_bundle.json against a BC5CDR-style gold document.",
    )
    parser.add_argument("--gold", required=True, help="Path to a BC5CDR-style gold JSON document.")
    parser.add_argument(
        "--prediction-bundle",
        required=True,
        help="Path to evidence_extraction_bundle.json.",
    )
    parser.add_argument("--out", required=True, help="Path to write the eval report JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gold_document = load_bc5cdr_document(Path(args.gold).expanduser().resolve())
    bundle = load_evidence_extraction_bundle(Path(args.prediction_bundle).expanduser().resolve())
    report = evaluate_bc5cdr_bundle(gold_document=gold_document, bundle=bundle)
    write_bc5cdr_eval_report(report, Path(args.out).expanduser().resolve())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
