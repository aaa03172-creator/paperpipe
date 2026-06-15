#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This proof wrapper is macOS-only." >&2
  exit 1
fi

ZIP_PATH="${PAPERPIPE_MACOS_ALPHA_ZIP:-${ROOT_DIR}/dist/release/Lattice-macos-arm64.zip}"
MANIFEST_PATH="${PAPERPIPE_MACOS_ALPHA_MANIFEST:-${ROOT_DIR}/dist/release/Lattice-macos-arm64.manifest.json}"
EXPECTED_SHA="${PAPERPIPE_MACOS_ALPHA_ZIP_SHA256:-}"
KEEP_EXTRACTED="${PAPERPIPE_KEEP_EXTRACTED_ALPHA_ZIP:-0}"

if [[ ! -f "${ZIP_PATH}" ]]; then
  echo "Release zip not found: ${ZIP_PATH}" >&2
  exit 1
fi

if [[ -z "${EXPECTED_SHA}" && -f "${MANIFEST_PATH}" ]]; then
  EXPECTED_SHA="$(
    python3 - "${MANIFEST_PATH}" <<'PY'
import json
import sys

manifest = json.loads(open(sys.argv[1], encoding="utf-8").read())
print(manifest.get("hashes", {}).get("release_zip_sha256", ""))
PY
  )"
fi

ACTUAL_SHA="$(shasum -a 256 "${ZIP_PATH}" | awk '{print $1}')"
if [[ -n "${EXPECTED_SHA}" && "${ACTUAL_SHA}" != "${EXPECTED_SHA}" ]]; then
  echo "Release zip SHA256 mismatch." >&2
  echo "expected=${EXPECTED_SHA}" >&2
  echo "actual=${ACTUAL_SHA}" >&2
  exit 1
fi

LAUNCHER_ZIP_PATH=""
LAUNCHER_EXPECTED_SHA=""
if [[ -f "${MANIFEST_PATH}" ]]; then
  LAUNCHER_ZIP_PATH="$(
    python3 - "${MANIFEST_PATH}" "${ROOT_DIR}" <<'PY'
import json
import pathlib
import sys

manifest_path = pathlib.Path(sys.argv[1])
root = pathlib.Path(sys.argv[2])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
launcher = manifest.get("launcher") or {}
zip_value = launcher.get("zip")
if launcher.get("included") and zip_value:
    path = pathlib.Path(zip_value)
    print(path if path.is_absolute() else root / path)
PY
  )"
  LAUNCHER_EXPECTED_SHA="$(
    python3 - "${MANIFEST_PATH}" <<'PY'
import json
import sys

manifest = json.loads(open(sys.argv[1], encoding="utf-8").read())
print(manifest.get("hashes", {}).get("launcher_zip_sha256", "") or "")
PY
  )"
fi

if [[ -n "${LAUNCHER_ZIP_PATH}" ]]; then
  if [[ ! -f "${LAUNCHER_ZIP_PATH}" ]]; then
    echo "Launcher zip declared in manifest but not found: ${LAUNCHER_ZIP_PATH}" >&2
    exit 1
  fi
  LAUNCHER_ACTUAL_SHA="$(shasum -a 256 "${LAUNCHER_ZIP_PATH}" | awk '{print $1}')"
  if [[ -n "${LAUNCHER_EXPECTED_SHA}" && "${LAUNCHER_ACTUAL_SHA}" != "${LAUNCHER_EXPECTED_SHA}" ]]; then
    echo "Launcher zip SHA256 mismatch." >&2
    echo "expected=${LAUNCHER_EXPECTED_SHA}" >&2
    echo "actual=${LAUNCHER_ACTUAL_SHA}" >&2
    exit 1
  fi
fi

EXTRACT_DIR="$(mktemp -d /tmp/lattice-alpha-zip-proof.XXXXXX)"
cleanup() {
  if [[ "${KEEP_EXTRACTED}" != "1" ]]; then
    rm -rf "${EXTRACT_DIR}"
  fi
}
trap cleanup EXIT

echo "==> Extracting alpha release zip"
ditto -x -k "${ZIP_PATH}" "${EXTRACT_DIR}"

EXTRACTED_EXECUTABLE="${EXTRACT_DIR}/Lattice.app/Contents/MacOS/Lattice"
if [[ ! -x "${EXTRACTED_EXECUTABLE}" ]]; then
  echo "Extracted Lattice executable not found: ${EXTRACTED_EXECUTABLE}" >&2
  exit 1
fi

if [[ -n "${LAUNCHER_ZIP_PATH}" ]]; then
  LAUNCHER_EXTRACT_DIR="${EXTRACT_DIR}/launcher"
  mkdir -p "${LAUNCHER_EXTRACT_DIR}"
  echo "==> Extracting assisted launcher zip"
  ditto -x -k "${LAUNCHER_ZIP_PATH}" "${LAUNCHER_EXTRACT_DIR}"
  if [[ ! -x "${LAUNCHER_EXTRACT_DIR}/Lattice Launcher.app/Contents/MacOS/LatticeLauncher" ]]; then
    echo "Extracted Lattice Launcher executable not found or not executable." >&2
    exit 1
  fi
  if [[ ! -f "${LAUNCHER_EXTRACT_DIR}/Lattice Launcher.app/Contents/Resources/lattice.icns" ]]; then
    echo "Extracted Lattice Launcher icon is missing." >&2
    exit 1
  fi
fi

PROOF_PORT="${PAPERPIPE_MACOS_ALPHA_ZIP_PROOF_PORT:-8047}"
PROOF_LOG="${PAPERPIPE_MACOS_ALPHA_ZIP_PROOF_LOG:-/tmp/lattice-alpha-zip-cloud-demo-proof.log}"

echo "==> Running cloud demo proof from extracted app"
PAPERPIPE_MACOS_CLOUD_DEMO_EXECUTABLE="${EXTRACTED_EXECUTABLE}" \
PAPERPIPE_MACOS_CLOUD_DEMO_PROOF_PORT="${PROOF_PORT}" \
PAPERPIPE_MACOS_CLOUD_DEMO_LOG="${PROOF_LOG}" \
"${ROOT_DIR}/scripts/run_macos_personal_runtime_cloud_demo_proof.sh"

echo "==> Extracted alpha zip proof summary"
cat <<EOF
zip_path=${ZIP_PATH}
manifest_path=${MANIFEST_PATH}
zip_sha256=${ACTUAL_SHA}
launcher_zip_path=${LAUNCHER_ZIP_PATH}
launcher_zip_sha256=${LAUNCHER_ACTUAL_SHA:-}
extract_dir=${EXTRACT_DIR}
keep_extracted=${KEEP_EXTRACTED}
proof_port=${PROOF_PORT}
proof_log=${PROOF_LOG}
EOF
