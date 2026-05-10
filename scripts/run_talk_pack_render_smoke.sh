#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
RESOLVER_RUNNER="$(command -v python3 || command -v python)"
if [[ -z "${RESOLVER_RUNNER}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi
PYTHON_BIN="$("${RESOLVER_RUNNER}" "${ROOT_DIR}/scripts/resolve_verification_python.py" --require-module yaml)"

"${PYTHON_BIN}" scripts/check_talk_pack_render_smoke.py "$@"
