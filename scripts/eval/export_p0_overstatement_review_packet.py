#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_p0_overstatement_review_packet_from_benchmark_reports,
    write_evidence_grounding_p0_overstatement_review_packet,
    write_evidence_grounding_p0_overstatement_review_packet_csv,
    write_evidence_grounding_p0_overstatement_review_packet_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a non-canonical P0 overstatement review packet from evidence-grounding benchmark reports."
        )
    )
    parser.add_argument(
        "--benchmark-report",
        action="append",
        required=True,
        help="evidence_grounding_benchmark.v1 report path. May be repeated for seed/eval/holdout.",
    )
    parser.add_argument("--out", required=True, help="Output packet JSON path.")
    parser.add_argument("--csv-out", default=None, help="Optional reviewer CSV output path.")
    parser.add_argument("--markdown-out", default=None, help="Optional Markdown packet output path.")
    args = parser.parse_args()

    benchmark_reports = [Path(path).expanduser().resolve() for path in args.benchmark_report]
    packet = build_evidence_grounding_p0_overstatement_review_packet_from_benchmark_reports(
        benchmark_report_paths=benchmark_reports,
    )
    out = write_evidence_grounding_p0_overstatement_review_packet(packet, Path(args.out))
    csv_out = (
        write_evidence_grounding_p0_overstatement_review_packet_csv(packet, Path(args.csv_out))
        if args.csv_out
        else None
    )
    markdown_out = (
        write_evidence_grounding_p0_overstatement_review_packet_markdown(
            packet,
            Path(args.markdown_out),
            json_path=out,
            csv_path=csv_out,
        )
        if args.markdown_out
        else None
    )

    print(f"[p0_overstatement_review_packet] paper_count={packet.paper_count}")
    print(f"[p0_overstatement_review_packet] claim_review_row_count={packet.claim_review_row_count}")
    print(f"[p0_overstatement_review_packet] warning_count={len(packet.warnings)}")
    print(f"[p0_overstatement_review_packet] out={out}")
    if csv_out:
        print(f"[p0_overstatement_review_packet] csv_out={csv_out}")
    if markdown_out:
        print(f"[p0_overstatement_review_packet] markdown_out={markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
