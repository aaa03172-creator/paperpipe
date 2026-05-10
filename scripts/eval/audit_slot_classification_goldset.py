from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.slot_classification_audit import (
    build_slot_classification_goldset_audit,
    load_slot_classification_goldset_csv,
    load_slot_classification_predictions_jsonl,
    write_slot_classification_goldset_audit,
)


def run_audit(
    *,
    goldset_csv_path: Path,
    predictions_jsonl_path: Path | None,
    out_dir: Path,
    run_id: str,
) -> Path:
    goldset_rows = load_slot_classification_goldset_csv(goldset_csv_path)
    predictions_by_key = load_slot_classification_predictions_jsonl(predictions_jsonl_path)
    summary, details = build_slot_classification_goldset_audit(
        goldset_rows=goldset_rows,
        predictions_by_key=predictions_by_key,
        run_id=run_id,
        goldset_csv_path=goldset_csv_path,
        predictions_jsonl_path=predictions_jsonl_path,
    )
    return write_slot_classification_goldset_audit(summary=summary, details=details, out_dir=out_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit slot-classification predictions against a goldset CSV.")
    parser.add_argument(
        "--goldset-csv",
        default=str(ROOT / "tests" / "gold_set" / "gold_standard_template.csv"),
        help="Goldset CSV path with at least title and gold_slot columns, plus optional gold_slot_rationale.",
    )
    parser.add_argument(
        "--predictions-jsonl",
        default=None,
        help="Optional JSONL predictions keyed by paper_id, doi, or title.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "slot_classification_goldset_audits"),
        help="Output directory for audit artifacts.",
    )
    parser.add_argument("--run-id", required=True, help="Audit run identifier.")
    args = parser.parse_args()

    predictions_jsonl_path = Path(args.predictions_jsonl).expanduser() if args.predictions_jsonl else None
    run_root = run_audit(
        goldset_csv_path=Path(args.goldset_csv).expanduser(),
        predictions_jsonl_path=predictions_jsonl_path,
        out_dir=Path(args.out_dir).expanduser(),
        run_id=args.run_id,
    )
    payload = {
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "details_path": str(run_root / "details.json"),
        "markdown_path": str(run_root / "audit.md"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
