#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This prereq wrapper is macOS-only." >&2
  exit 1
fi

RESOLVER_RUNNER="$(command -v python3 || command -v python)"
if [[ -z "${RESOLVER_RUNNER}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi

PYTHON_BIN="$("${RESOLVER_RUNNER}" "${ROOT_DIR}/scripts/resolve_verification_python.py")"

OUTPUT_PATH=""
IDENTITY="${PAPERPIPE_MACOS_SIGN_IDENTITY:-}"
NOTARY_PROFILE="${PAPERPIPE_MACOS_NOTARY_PROFILE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      OUTPUT_PATH="$2"
      shift 2
      ;;
    --identity)
      IDENTITY="$2"
      shift 2
      ;;
    --notary-profile)
      NOTARY_PROFILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${OUTPUT_PATH}" ]]; then
  OUTPUT_BASENAME="$(mktemp /tmp/lattice-gatekeeper-prereqs.XXXXXX)"
  rm -f "${OUTPUT_BASENAME}"
  OUTPUT_PATH="${OUTPUT_BASENAME}.json"
fi
mkdir -p "$(dirname "${OUTPUT_PATH}")"

CHECK_CMD=("${PYTHON_BIN}" "${ROOT_DIR}/scripts/release_macos_personal_runtime.py" --check-prereqs)
if [[ -n "${IDENTITY}" ]]; then
  CHECK_CMD+=("--identity" "${IDENTITY}")
fi
if [[ -n "${NOTARY_PROFILE}" ]]; then
  CHECK_CMD+=("--notary-profile" "${NOTARY_PROFILE}")
fi

set +e
"${CHECK_CMD[@]}" >"${OUTPUT_PATH}"
STATUS=$?
set -e

cat "${OUTPUT_PATH}"
echo "report_path=${OUTPUT_PATH}" >&2
exit "${STATUS}"
