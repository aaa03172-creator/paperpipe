#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

RESOLVER_RUNNER="$(command -v python3 || command -v python)"
if [[ -z "${RESOLVER_RUNNER}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi

PYTHON_BIN="$("${RESOLVER_RUNNER}" "${REPO_ROOT}/scripts/resolve_verification_python.py" --require-module yaml --require-module fastapi --require-module uvicorn)"

exec "${PYTHON_BIN}" ./scripts/check_frontend_real_smoke_env.py --require-candidates "$@"
