#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.bc5cdr_eval import load_evidence_extraction_bundle  # noqa: E402
from src.services.biored_eval import evaluate_biored_bundle, load_biored_document, write_biored_eval_report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate an evidence_extraction_bundle.json against a BioRED-style gold document.",
    )
    parser.add_argument("--gold", required=True, help="Path to a BioRED-style gold JSON document.")
    parser.add_argument(
        "--prediction-bundle",
        required=True,
        help="Path to evidence_extraction_bundle.json.",
    )
    parser.add_argument("--out", required=True, help="Path where the BioRED eval report should be written.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gold_document = load_biored_document(Path(args.gold).expanduser().resolve())
    bundle = load_evidence_extraction_bundle(Path(args.prediction_bundle).expanduser().resolve())
    report = evaluate_biored_bundle(gold_document=gold_document, bundle=bundle)
    write_biored_eval_report(report, Path(args.out).expanduser().resolve())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
