#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_PAPER_ID = "cloudpdf_lab_001_fe476330a3bd"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write_submission_env(path: Path, *, paper_id: str) -> None:
    path.write_text(
        "\n".join(
            [
                "# Lattice contest submission demo mode.",
                "# This file intentionally avoids Google Cloud credentials and service account keys.",
                "PAPERPIPE_SUBMISSION_DEMO_BUNDLE=1",
                "PAPERPIPE_CLOUD_ADAPTER=mock",
                "PAPERPIPE_CLOUD_METADATA_STORE=memory",
                "PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE=memory",
                f"PAPERPIPE_DEMO_EXPECTED_PAPER_ID={paper_id}",
                "PAPERPIPE_DEMO_SEARCH_QUERY=amyloid",
                f"LATTICE_START_PATH=/ui/papers/{paper_id}?source=cloud",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _sign_app(app_path: Path) -> None:
    if sys.platform != "darwin" or shutil.which("codesign") is None:
        return
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app_path)],
        check=True,
    )


def build_submission_copy(
    *,
    source_app: Path,
    output_app: Path,
    snapshot_dir: Path,
    paper_id: str,
) -> None:
    if not source_app.is_dir():
        raise SystemExit(f"Source app does not exist: {source_app}")
    if not (source_app / "Contents" / "MacOS" / "Lattice").is_file():
        raise SystemExit(f"Source app is missing the native Lattice launcher: {source_app}")
    if not snapshot_dir.is_dir():
        raise SystemExit(f"Submission snapshot directory does not exist: {snapshot_dir}")
    if not (snapshot_dir / "cloud_papers" / paper_id / "bundle.json").is_file():
        raise SystemExit(f"Submission snapshot is missing bundle.json for paper id: {paper_id}")

    if output_app.exists():
        shutil.rmtree(output_app)
    output_app.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_app, output_app, symlinks=True)

    resources_dir = output_app / "Contents" / "Resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    bundled_snapshot_dir = resources_dir / "submission_demo"
    if bundled_snapshot_dir.exists():
        shutil.rmtree(bundled_snapshot_dir)
    shutil.copytree(snapshot_dir, bundled_snapshot_dir)
    _write_submission_env(resources_dir / "submission-demo.env", paper_id=paper_id)
    _sign_app(output_app)


def main() -> int:
    repo_root = _repo_root()
    parser = argparse.ArgumentParser(description="Copy Lattice.app into an offline contest submission demo app.")
    parser.add_argument("--source-app", type=Path, default=repo_root / "dist" / "Lattice.app")
    parser.add_argument("--output-app", type=Path, default=repo_root / "dist" / "Lattice-Contest-Submission.app")
    parser.add_argument("--snapshot-dir", type=Path, default=repo_root / "packaging" / "submission_demo")
    parser.add_argument("--paper-id", default=DEFAULT_PAPER_ID)
    args = parser.parse_args()

    build_submission_copy(
        source_app=args.source_app.resolve(),
        output_app=args.output_app.resolve(),
        snapshot_dir=args.snapshot_dir.resolve(),
        paper_id=args.paper_id,
    )
    print(f"submission_app={args.output_app.resolve()}")
    print(f"submission_env={args.output_app.resolve() / 'Contents' / 'Resources' / 'submission-demo.env'}")
    print(f"submission_snapshot={args.output_app.resolve() / 'Contents' / 'Resources' / 'submission_demo'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
