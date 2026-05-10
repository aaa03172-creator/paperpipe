from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.llm_provider import get_llm_provider
from src.quality.teacher_review import build_prediction_row, review_teacher_bundle


def _discover_bundle_dirs(bundles_root: Path) -> list[Path]:
    if not bundles_root.exists():
        raise FileNotFoundError(f"bundles_root_not_found={bundles_root}")
    return sorted(path for path in bundles_root.iterdir() if path.is_dir())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local-first teacher outputs from extracted teacher bundles.")
    parser.add_argument("--bundle-dir", action="append", dest="bundle_dirs", help="One teacher bundle directory (repeatable)")
    parser.add_argument("--bundles-root", default="", help="Directory containing multiple teacher bundle directories")
    parser.add_argument("--pred-jsonl", default="", help="Optional consolidated predictions JSONL output path")
    parser.add_argument("--max-claims", type=int, default=6, help="Maximum claims to keep per bundle")
    parser.add_argument("--max-chunks", type=int, default=18, help="Maximum source chunks to send per bundle")
    parser.add_argument("--max-chars", type=int, default=18000, help="Maximum total snippet characters per bundle")
    parser.add_argument("--fail-fast", action="store_true", help="Stop immediately on first bundle failure")
    args = parser.parse_args()

    cfg = load_config()
    provider = get_llm_provider(cfg.llm, getattr(cfg, "entity_aliases", None))
    if provider is None or not provider.is_available():
        raise SystemExit("local LLM provider unavailable")

    bundle_dirs: list[Path] = []
    if args.bundle_dirs:
        bundle_dirs.extend(Path(item).expanduser().resolve() for item in args.bundle_dirs if item)
    if args.bundles_root:
        bundle_dirs.extend(_discover_bundle_dirs(Path(args.bundles_root).expanduser().resolve()))

    seen: set[Path] = set()
    unique_bundle_dirs: list[Path] = []
    for path in bundle_dirs:
        if path in seen:
            continue
        seen.add(path)
        unique_bundle_dirs.append(path)

    if not unique_bundle_dirs:
        raise SystemExit("no bundle directories provided")

    pred_rows: list[dict] = []
    failures: list[dict[str, str]] = []

    for bundle_dir in unique_bundle_dirs:
        try:
            result = review_teacher_bundle(
                bundle_dir=bundle_dir,
                provider=provider,
                max_claims=max(1, args.max_claims),
                max_chunks=max(1, args.max_chunks),
                max_chars=max(4000, args.max_chars),
            )
            pred_rows.append(build_prediction_row(result))
            claim_count = len(result["claimset"].claims)
            print(f"[teacher-generate] ok bundle={bundle_dir} claims={claim_count} output={result['output_path']}")
        except Exception as exc:
            failures.append({"bundle_dir": str(bundle_dir), "error": str(exc)})
            print(f"[teacher-generate] fail bundle={bundle_dir} error={exc}")
            if args.fail_fast:
                break

    if args.pred_jsonl:
        pred_path = Path(args.pred_jsonl).expanduser().resolve()
        pred_path.parent.mkdir(parents=True, exist_ok=True)
        with pred_path.open("w", encoding="utf-8") as handle:
            for row in pred_rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[teacher-generate] pred_jsonl={pred_path}")

    print(f"[teacher-generate] success={len(pred_rows)} failed={len(failures)}")
    if failures:
        for failure in failures[:20]:
            print(f"  - fail {failure['bundle_dir']} :: {failure['error']}")
        if args.fail_fast:
            return 1
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
