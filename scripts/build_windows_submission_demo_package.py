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


def _copytree_clean(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _write_env(path: Path, *, paper_id: str) -> None:
    path.write_text(
        "\n".join(
            [
                "# Lattice Windows contest submission demo mode.",
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


def _zip_folder(folder: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=folder.parent, base_dir=folder.name)


def build_windows_submission_package(
    *,
    source_exe: Path,
    native_launcher_dir: Path | None,
    output_dir: Path,
    snapshot_dir: Path,
    handoff_dir: Path,
    paper_id: str,
) -> Path:
    if not source_exe.is_file():
        raise SystemExit(
            f"Missing Windows executable: {source_exe}. "
            "Run `py -3 scripts/build_personal_runtime_bundle.py --skip-frontend-build --bundle-profile cloud-ui` "
            "on a Windows host first."
        )
    if source_exe.suffix.lower() != ".exe":
        raise SystemExit(f"Expected a Windows .exe, got: {source_exe}")
    if not (snapshot_dir / "cloud_papers" / paper_id / "bundle.json").is_file():
        raise SystemExit(f"Submission snapshot is missing bundle.json for paper id: {paper_id}")

    package_root = output_dir / "Lattice-Windows-Contest-Submission"
    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_exe, package_root / "LatticeRuntime.exe")
    if native_launcher_dir is not None and (native_launcher_dir / "Lattice.exe").is_file():
        for child in native_launcher_dir.iterdir():
            destination = package_root / child.name
            if child.is_dir():
                _copytree_clean(child, destination)
            elif child.is_file():
                shutil.copy2(child, destination)
    else:
        shutil.copy2(source_exe, package_root / "lattice.exe")
    shutil.copy2(_repo_root() / "config.example.yaml", package_root / "config.example.yaml")
    _copytree_clean(snapshot_dir, package_root / "submission_demo")
    for filename in ["README_FIRST.txt", "Start-Lattice-Demo.ps1", "Start Lattice Demo.cmd"]:
        shutil.copy2(handoff_dir / filename, package_root / filename)
    _write_env(package_root / "submission-demo.env", paper_id=paper_id)

    zip_path = output_dir / "Lattice-Windows-Contest-Submission.zip"
    _zip_folder(package_root, zip_path)
    return zip_path


def main() -> int:
    repo_root = _repo_root()
    parser = argparse.ArgumentParser(description="Build the Windows offline contest submission demo package.")
    parser.add_argument("--source-exe", type=Path, default=repo_root / "dist" / "lattice.exe")
    parser.add_argument("--native-launcher-dir", type=Path, default=repo_root / "dist" / "windows-native-launcher")
    parser.add_argument("--output-dir", type=Path, default=repo_root / "dist")
    parser.add_argument("--snapshot-dir", type=Path, default=repo_root / "packaging" / "submission_demo")
    parser.add_argument("--handoff-dir", type=Path, default=repo_root / "packaging" / "windows_submission_handoff")
    parser.add_argument("--paper-id", default=DEFAULT_PAPER_ID)
    parser.add_argument(
        "--build-exe",
        action="store_true",
        help="Build dist/lattice.exe first. This must run on Windows.",
    )
    parser.add_argument("--skip-frontend-build", action="store_true")
    args = parser.parse_args()

    if args.build_exe:
        if sys.platform != "win32":
            raise SystemExit("--build-exe must run on a Windows host.")
        command = [sys.executable, str(repo_root / "scripts" / "build_personal_runtime_bundle.py"), "--bundle-profile", "cloud-ui"]
        if args.skip_frontend_build:
            command.append("--skip-frontend-build")
        subprocess.run(command, cwd=repo_root, check=True)

    zip_path = build_windows_submission_package(
        source_exe=args.source_exe.resolve(),
        native_launcher_dir=args.native_launcher_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        snapshot_dir=args.snapshot_dir.resolve(),
        handoff_dir=args.handoff_dir.resolve(),
        paper_id=args.paper_id,
    )
    print(f"windows_submission_zip={zip_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
