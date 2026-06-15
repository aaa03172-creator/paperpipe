#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_candidate_lineage_patch_template_from_manifest_package,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a non-canonical candidate lineage patch template from an "
            "evidence_grounding_benchmark_manifest_package.v1 artifact."
        )
    )
    parser.add_argument(
        "--benchmark-manifest-package",
        required=True,
        help="evidence_grounding_benchmark_manifest_package.v1 JSON path.",
    )
    parser.add_argument("--out", required=True, help="Output candidate lineage patch template JSON path.")
    args = parser.parse_args()

    try:
        template = build_evidence_grounding_candidate_lineage_patch_template_from_manifest_package(
            benchmark_manifest_package_path=Path(args.benchmark_manifest_package),
            out=Path(args.out),
        )
    except Exception as exc:
        print(
            f"[evidence_grounding_candidate_lineage_patch_template] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1
    print(f"[evidence_grounding_candidate_lineage_patch_template] target_count={template.target_count}")
    print(
        "[evidence_grounding_candidate_lineage_patch_template] "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    if template.warnings:
        print(f"[evidence_grounding_candidate_lineage_patch_template] warnings={','.join(template.warnings)}")
    return 0 if template.target_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
