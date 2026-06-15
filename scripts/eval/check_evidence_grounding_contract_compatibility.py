#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import build_evidence_grounding_contract_compatibility_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check evidence-grounding review artifacts for supported schema versions and "
            "non-canonical review-gate posture."
        )
    )
    parser.add_argument("--artifact", action="append", required=True, help="Evidence-grounding artifact JSON path")
    parser.add_argument("--out", required=True, help="Output compatibility report JSON path")
    parser.add_argument("--compatibility-id", default="evidence-grounding-contract-compatibility")
    args = parser.parse_args()

    report = build_evidence_grounding_contract_compatibility_report(
        artifact_paths=[Path(path) for path in args.artifact],
        compatibility_id=args.compatibility_id,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[evidence_grounding_contract_compatibility] compatibility_id={report.compatibility_id}")
    print(f"[evidence_grounding_contract_compatibility] artifact_count={report.artifact_count}")
    print(f"[evidence_grounding_contract_compatibility] fail_count={report.fail_count}")
    print(f"[evidence_grounding_contract_compatibility] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
