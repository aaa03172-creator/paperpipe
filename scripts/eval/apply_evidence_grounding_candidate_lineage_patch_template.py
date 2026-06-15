#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_benchmark_manifest_package_from_candidate_lineage_patch_template,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a filled candidate lineage patch template and write a repaired "
            "evidence-grounding benchmark manifest package."
        )
    )
    parser.add_argument("--patch-template", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--package-id",
        default="evidence-grounding-candidate-lineage-repaired-manifest-package",
    )
    parser.add_argument("--out", help="Optional output path for the repaired manifest package JSON.")
    args = parser.parse_args()

    try:
        package = build_evidence_grounding_benchmark_manifest_package_from_candidate_lineage_patch_template(
            patch_template_path=Path(args.patch_template),
            out_dir=Path(args.out_dir),
            package_id=args.package_id,
            out=Path(args.out).expanduser().resolve() if args.out else None,
        )
    except Exception as exc:
        print(
            f"[evidence_grounding_candidate_lineage_patch_apply] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1
    print(f"[evidence_grounding_candidate_lineage_patch_apply] package_id={package.package_id}")
    print(f"[evidence_grounding_candidate_lineage_patch_apply] manifest_count={package.manifest_count}")
    print(f"[evidence_grounding_candidate_lineage_patch_apply] item_count={package.item_count}")
    print(
        "[evidence_grounding_candidate_lineage_patch_apply] "
        f"out_dir={mask_local_paths_in_text(package.out_dir)}"
    )
    if args.out:
        print(
            "[evidence_grounding_candidate_lineage_patch_apply] "
            f"package={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
        )
    return 0 if package.manifest_count > 0 and package.item_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
