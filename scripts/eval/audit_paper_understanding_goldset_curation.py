#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.paper_understanding_gold import PaperUnderstandingGoldCurationTarget
from src.services.paper_understanding_gold_validation import build_paper_understanding_gold_curation_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit paper_understanding_gold manifests for split/domain/type readiness coverage. "
            "This writes a non-canonical review artifact; it does not promote gold records."
        )
    )
    parser.add_argument("paths", nargs="+", help="Gold JSON, directory, or paper_understanding_gold_manifest.v1 path")
    parser.add_argument("--out", required=True, help="Output paper_understanding_gold_curation_report.v1 JSON path")
    parser.add_argument("--report-id", default="paper-understanding-gold-curation")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help=(
            "Coverage target as comma-separated key=value pairs. Supported keys: "
            "split/goldset_split, domain/domain_tag, paper_type, min/min_ready_count. "
            "Example: split=eval,domain=biomarker,min=10"
        ),
    )
    args = parser.parse_args()

    targets = [_parse_target(raw) for raw in args.target]
    report = build_paper_understanding_gold_curation_report(
        [Path(path) for path in args.paths],
        report_id=args.report_id,
        targets=targets,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[paper_understanding_gold_curation] report_id={report.report_id}")
    print(f"[paper_understanding_gold_curation] manifest_count={report.manifest_count}")
    print(f"[paper_understanding_gold_curation] paper_count={report.paper_count}")
    print(f"[paper_understanding_gold_curation] ready_paper_count={report.ready_paper_count}")
    print(f"[paper_understanding_gold_curation] invalid_count={report.invalid_count}")
    print(f"[paper_understanding_gold_curation] curation_ready={report.curation_ready}")
    print(f"[paper_understanding_gold_curation] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.curation_ready else 1


def _parse_target(raw: str) -> PaperUnderstandingGoldCurationTarget:
    values: dict[str, str | int] = {}
    for item in raw.split(","):
        if "=" not in item:
            raise SystemExit(f"invalid --target item={item!r}; expected key=value")
        key, value = item.split("=", 1)
        key = key.strip().lower().replace("-", "_")
        value = value.strip()
        if key in {"split", "goldset_split"}:
            values["goldset_split"] = value
        elif key in {"domain", "domain_tag"}:
            values["domain_tag"] = value
        elif key == "paper_type":
            values["paper_type"] = value
        elif key in {"min", "min_ready_count"}:
            values["min_ready_count"] = int(value)
        else:
            raise SystemExit(f"unsupported --target key={key!r}")
    return PaperUnderstandingGoldCurationTarget.model_validate(values)


if __name__ == "__main__":
    raise SystemExit(main())
