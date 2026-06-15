from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_validation import (  # noqa: E402
    iter_gold_paths,
    validate_gold_path,
    validate_gold_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate paper-understanding gold JSON files.")
    parser.add_argument("paths", nargs="+", help="Gold JSON files or directories to validate.")
    parser.add_argument("--out", default="", help="Optional path to write validation summary JSON.")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero when a schema-valid gold record is not eval-ready.",
    )
    args = parser.parse_args()

    summary = validate_gold_paths([Path(path) for path in args.paths], require_ready=args.require_ready)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).expanduser().write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if summary["invalid_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
