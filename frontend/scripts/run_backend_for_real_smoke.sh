#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi

BACKEND_PORT="${E2E_BACKEND_PORT:-8000}"
CONFIG_PATH="${PAPERPIPE_CONFIG_PATH:-config.yaml}"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "PaperPipe config not found: ${CONFIG_PATH}" >&2
  exit 1
fi

if [[ -n "${PAPERPIPE_STORAGE_DIR:-}" && ! -d "${PAPERPIPE_STORAGE_DIR}" ]]; then
  echo "PAPERPIPE_STORAGE_DIR not found: ${PAPERPIPE_STORAGE_DIR}" >&2
  exit 1
fi

if [[ -n "${PAPERPIPE_DB_PATH:-}" && ! -f "${PAPERPIPE_DB_PATH}" ]]; then
  echo "PAPERPIPE_DB_PATH not found: ${PAPERPIPE_DB_PATH}" >&2
  exit 1
fi

if [[ -n "${PAPERPIPE_ARTIFACTS_DIR:-}" && ! -d "${PAPERPIPE_ARTIFACTS_DIR}" ]]; then
  echo "PAPERPIPE_ARTIFACTS_DIR not found: ${PAPERPIPE_ARTIFACTS_DIR}" >&2
  exit 1
fi

if [[ "${PAPERPIPE_REAL_SMOKE_REQUIRE_CANDIDATES:-0}" == "1" ]]; then
  "${PYTHON_BIN}" ./scripts/check_frontend_real_smoke_env.py --require-candidates
else
  "${PYTHON_BIN}" ./scripts/check_frontend_real_smoke_env.py
fi

echo "Starting backend real smoke server"
echo "  config: ${CONFIG_PATH##*/}"
if [[ -n "${PAPERPIPE_STORAGE_DIR:-}" ]]; then
  echo "  storage override: enabled"
fi
if [[ -n "${PAPERPIPE_DB_PATH:-}" ]]; then
  echo "  db override: enabled"
fi
if [[ -n "${PAPERPIPE_ARTIFACTS_DIR:-}" ]]; then
  echo "  artifacts override: enabled"
fi

exec "${PYTHON_BIN}" -m uvicorn backend.main:app --host 127.0.0.1 --port "${BACKEND_PORT}"
