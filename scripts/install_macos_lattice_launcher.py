#!/usr/bin/env python3
"""Install a small macOS launcher app for the packaged Lattice runtime."""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


LAUNCHER_TEMPLATE = """#!/bin/zsh
set -u
PORT="${{LATTICE_PORT:-{port}}}"
HEALTH="http://127.0.0.1:${{PORT}}/health"
APP_EXEC="{app_exec}"

RUNTIME_ROOT="$HOME/Library/Application Support/Lattice"
CONFIG_DIR="$RUNTIME_ROOT/config"
CONFIG_PATH="$CONFIG_DIR/config.yaml"
ENV_FILE="$CONFIG_DIR/cloud-demo.env"
LOG_DIR="$HOME/Library/Logs/Lattice"
LOG="$LOG_DIR/launcher.log"

/bin/mkdir -p "$RUNTIME_ROOT" "$CONFIG_DIR" "$LOG_DIR"
cd "$RUNTIME_ROOT" || exit 1

show_dialog() {{
  /usr/bin/osascript -e "display dialog \\"$1\\" buttons {{\\"OK\\"}} default button \\"OK\\" with title \\"Lattice\\""
}}

if [ ! -f "$ENV_FILE" ]; then
  /bin/cat > "$ENV_FILE" <<'EOF'
PAPERPIPE_CLOUD_ADAPTER="gcs"
PAPERPIPE_CLOUD_METADATA_STORE="firestore"
PAPERPIPE_GCP_PROJECT_ID="knudc-a01068202087"
PAPERPIPE_GCS_RAW_PDF_BUCKET="paperpipe-raw-pdf-dev-knudc-a01068202087"
PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET="paperpipe-page-artifacts-dev-knudc-a01068202087"
PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION="cloud_papers_demo"
PAPERPIPE_DEMO_EXPECTED_PAPER_ID="cloudpdf_lab_001_fe476330a3bd"
PAPERPIPE_DEMO_SEARCH_QUERY="amyloid"
LATTICE_START_PATH="/ui/papers/cloudpdf_lab_001_fe476330a3bd?source=cloud"
EOF
  /bin/chmod 600 "$ENV_FILE"
fi
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

DEMO_PAPER_ID="${{PAPERPIPE_DEMO_EXPECTED_PAPER_ID:-cloudpdf_lab_001_fe476330a3bd}}"
START_PATH="${{LATTICE_START_PATH:-/ui/papers/${{DEMO_PAPER_ID}}?source=cloud}}"
URL="http://127.0.0.1:${{PORT}}${{START_PATH}}"

if /usr/bin/curl -fsS "$HEALTH" >/dev/null 2>&1; then
  /usr/bin/open "$URL"
  exit 0
fi

if [ ! -x "$APP_EXEC" ]; then
  show_dialog "Lattice.app is not installed in /Applications."
  exit 1
fi

export PAPERPIPE_INSTALL_LAYOUT="${{PAPERPIPE_INSTALL_LAYOUT:-1}}"
export PAPERPIPE_CONFIG_PATH="${{PAPERPIPE_CONFIG_PATH:-$CONFIG_PATH}}"
export LATTICE_API_KEY="${{LATTICE_API_KEY:-demo-secret}}"
export PAPERPIPE_CLOUD_ADAPTER="${{PAPERPIPE_CLOUD_ADAPTER:-gcs}}"
export PAPERPIPE_CLOUD_METADATA_STORE="${{PAPERPIPE_CLOUD_METADATA_STORE:-firestore}}"
export PAPERPIPE_GCP_PROJECT_ID="${{PAPERPIPE_GCP_PROJECT_ID:-knudc-a01068202087}}"
export PAPERPIPE_GCS_RAW_PDF_BUCKET="${{PAPERPIPE_GCS_RAW_PDF_BUCKET:-paperpipe-raw-pdf-dev-knudc-a01068202087}}"
export PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET="${{PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET:-paperpipe-page-artifacts-dev-knudc-a01068202087}}"
export PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION="${{PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION:-cloud_papers_demo}}"
export PAPERPIPE_DEMO_EXPECTED_PAPER_ID="${{PAPERPIPE_DEMO_EXPECTED_PAPER_ID:-cloudpdf_lab_001_fe476330a3bd}}"
export PAPERPIPE_DEMO_SEARCH_QUERY="${{PAPERPIPE_DEMO_SEARCH_QUERY:-amyloid}}"
export LATTICE_START_PATH="${{LATTICE_START_PATH:-$START_PATH}}"

/usr/bin/nohup "$APP_EXEC" start --host 127.0.0.1 --port "$PORT" > "$LOG" 2>&1 &

for i in {{1..30}}; do
  if /usr/bin/curl -fsS "$HEALTH" >/dev/null 2>&1; then
    /usr/bin/open "$URL"
    exit 0
  fi
  /bin/sleep 1
done

show_dialog "Lattice did not start within 30 seconds. Check $LOG."
exit 1
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app-bundle",
        type=Path,
        default=Path("/Applications/Lattice.app"),
        help="Installed Lattice.app bundle to launch.",
    )
    parser.add_argument(
        "--skip-app-validation",
        action="store_true",
        help="Do not require the target app bundle to exist while creating the launcher.",
    )
    parser.add_argument(
        "--launcher-bundle",
        type=Path,
        default=Path("/Applications/Lattice Launcher.app"),
        help="Launcher app bundle to create or replace.",
    )
    parser.add_argument(
        "--icon",
        type=Path,
        default=ROOT / "packaging" / "pyinstaller" / "lattice.icns",
        help="Icon file copied into the launcher bundle.",
    )
    parser.add_argument("--port", type=int, default=8046)
    parser.add_argument(
        "--sign",
        action="store_true",
        help="Ad-hoc sign the launcher bundle after writing it.",
    )
    return parser.parse_args()


def _write_launcher(args: argparse.Namespace) -> None:
    app_exec = args.app_bundle / "Contents" / "MacOS" / "Lattice"
    contents = args.launcher_bundle / "Contents"
    macos_dir = contents / "MacOS"
    resources_dir = contents / "Resources"
    executable = macos_dir / "LatticeLauncher"

    if not args.skip_app_validation and not app_exec.exists():
        raise SystemExit(f"Missing app executable: {app_exec}")
    if not args.icon.exists():
        raise SystemExit(f"Missing launcher icon: {args.icon}")

    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    plist = {
        "CFBundleDisplayName": "Lattice",
        "CFBundleExecutable": "LatticeLauncher",
        "CFBundleIconFile": "lattice.icns",
        "CFBundleIdentifier": "ai.paperpipe.lattice.launcher",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "Lattice",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "3.1.0-alpha",
        "CFBundleVersion": "3.1.0-alpha",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
    }
    with (contents / "Info.plist").open("wb") as fh:
        plistlib.dump(plist, fh)

    shutil.copy2(args.icon, resources_dir / "lattice.icns")
    executable.write_text(
        LAUNCHER_TEMPLATE.format(app_exec=app_exec, port=args.port),
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _sign(bundle: Path) -> None:
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(bundle)],
        check=True,
    )


def main() -> None:
    args = _parse_args()
    _write_launcher(args)
    if args.sign:
        _sign(args.launcher_bundle)
    print(f"Installed launcher: {args.launcher_bundle}")


if __name__ == "__main__":
    main()
