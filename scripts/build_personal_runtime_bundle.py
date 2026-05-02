from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
SPEC_PATH = ROOT / "packaging" / "pyinstaller" / "lattice.spec"
PACKAGING_ASSET_ROOT = ROOT / "build" / "personal_runtime_assets"


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd is not None else None, env=env, check=True)


def cli_binary_output_path(root: Path = ROOT) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return (root / "dist" / f"lattice{suffix}").resolve()


def _cli_binary_cleanup_paths(root: Path = ROOT) -> list[Path]:
    candidates = [
        (root / "dist" / "lattice").resolve(),
        (root / "dist" / "lattice.exe").resolve(),
    ]
    deduped: list[Path] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _expected_bundle_outputs() -> list[Path]:
    outputs = [cli_binary_output_path()]
    if sys.platform == "darwin":
        outputs.append(ROOT / "dist" / "Lattice.app")
    return outputs


def _packaging_output_paths() -> list[Path]:
    outputs = _cli_binary_cleanup_paths()
    if sys.platform == "darwin":
        outputs.extend(
            [
                ROOT / "dist" / "Lattice",
                ROOT / "dist" / "Lattice-support",
                ROOT / "dist" / "Lattice.app",
            ]
        )
    return outputs


def _remove_previous_outputs() -> None:
    for path in _packaging_output_paths():
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _stage_packaging_assets() -> Path:
    if PACKAGING_ASSET_ROOT.exists():
        shutil.rmtree(PACKAGING_ASSET_ROOT)

    staged_frontend = PACKAGING_ASSET_ROOT / "frontend"
    staged_frontend.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FRONTEND_DIR / "dist", staged_frontend / "dist")
    shutil.copytree(FRONTEND_DIR / "styles", staged_frontend / "styles")
    return PACKAGING_ASSET_ROOT


def build_bundle(*, skip_frontend_build: bool, clean: bool) -> None:
    if not SPEC_PATH.exists():
        raise FileNotFoundError(f"PyInstaller spec not found: {SPEC_PATH}")

    if not skip_frontend_build:
        _run(["npm", "install"], cwd=FRONTEND_DIR)
        _run(["npm", "run", "build"], cwd=FRONTEND_DIR)

    if not (FRONTEND_DIR / "dist" / "index.html").exists():
        raise FileNotFoundError(
            "Built frontend bundle is missing. Run `cd frontend && npm run build` first."
        )

    if shutil.which("pyinstaller") is not None:
        cmd = ["pyinstaller", str(SPEC_PATH), "--noconfirm"]
    else:
        cmd = [sys.executable, "-m", "PyInstaller", str(SPEC_PATH), "--noconfirm"]

    if clean:
        cmd.append("--clean")

    _remove_previous_outputs()
    staged_asset_root = _stage_packaging_assets()
    env = os.environ.copy()
    env["PAPERPIPE_BUNDLE_ASSET_ROOT"] = str(staged_asset_root)

    _run(cmd, cwd=ROOT, env=env)

    missing_outputs = [path for path in _expected_bundle_outputs() if not path.exists()]
    if missing_outputs:
        missing_display = ", ".join(str(path) for path in missing_outputs)
        raise FileNotFoundError(f"Expected bundle output is missing: {missing_display}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the personal-runtime bundle around the existing Lattice launcher."
    )
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="Reuse the existing frontend/dist bundle instead of rebuilding it.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Ask PyInstaller to clean temporary build artifacts first.",
    )
    args = parser.parse_args()

    build_bundle(skip_frontend_build=args.skip_frontend_build, clean=args.clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
