#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This proof wrapper is macOS-only." >&2
  exit 1
fi

RESOLVER_RUNNER="$(command -v python3 || command -v python)"
if [[ -z "${RESOLVER_RUNNER}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi

PYTHON_BIN="$("${RESOLVER_RUNNER}" "${ROOT_DIR}/scripts/resolve_verification_python.py" --require-module yaml --require-module fastapi --require-module uvicorn)"

RELEASE_DIR=""
PORT="${PAPERPIPE_MACOS_RELEASE_PROOF_PORT:-8031}"
CONFIG_PATH="${PAPERPIPE_CONFIG_PATH:-${ROOT_DIR}/config.example.yaml}"
BUILD_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release-dir)
      RELEASE_DIR="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --config-path)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --build|--clean|--skip-frontend-build)
      BUILD_ARGS+=("$1")
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "Config not found: ${CONFIG_PATH}" >&2
  exit 1
fi

if [[ -z "${RELEASE_DIR}" ]]; then
  RELEASE_DIR="$(mktemp -d /tmp/lattice-release-proof.XXXXXX)"
fi
mkdir -p "${RELEASE_DIR}"

APP_PID=""
cleanup() {
  if [[ -n "${APP_PID}" ]] && kill -0 "${APP_PID}" 2>/dev/null; then
    pkill -TERM -P "${APP_PID}" 2>/dev/null || true
    kill -TERM "${APP_PID}" 2>/dev/null || true
    for _ in {1..10}; do
      if ! kill -0 "${APP_PID}" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "${APP_PID}" 2>/dev/null; then
      pkill -KILL -P "${APP_PID}" 2>/dev/null || true
      kill -KILL "${APP_PID}" 2>/dev/null || true
    fi
    wait "${APP_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "==> Local release packaging"
RELEASE_CMD=("${PYTHON_BIN}" "${ROOT_DIR}/scripts/release_macos_personal_runtime.py" --release-dir "${RELEASE_DIR}")
if ((${#BUILD_ARGS[@]})); then
  RELEASE_CMD+=("${BUILD_ARGS[@]}")
fi
"${RELEASE_CMD[@]}"

echo "==> Packaged CLI self-test"
PAPERPIPE_CONFIG_PATH="${CONFIG_PATH}" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/lattice self-test --json

echo "==> Packaged app self-test"
PAPERPIPE_CONFIG_PATH="${CONFIG_PATH}" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/Lattice.app/Contents/MacOS/Lattice self-test --json

echo "==> Packaged app launch probe"
PAPERPIPE_CONFIG_PATH="${CONFIG_PATH}" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/Lattice.app/Contents/MacOS/Lattice start --no-open --port "${PORT}" >"${RELEASE_DIR}/app-start.log" 2>&1 &
APP_PID=$!

for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >"${RELEASE_DIR}/health.json"; then
    break
  fi
  sleep 1
done

HEALTH_STATUS="$(curl -sS -o "${RELEASE_DIR}/health.json" -w '%{http_code}' "http://127.0.0.1:${PORT}/health")"
UI_STATUS="$(curl -sS -o "${RELEASE_DIR}/ui.html" -w '%{http_code}' "http://127.0.0.1:${PORT}/ui")"

if [[ "${HEALTH_STATUS}" != "200" ]]; then
  echo "Expected /health to return 200, got ${HEALTH_STATUS}" >&2
  exit 1
fi

if [[ "${UI_STATUS}" != "200" ]]; then
  echo "Expected /ui to return 200, got ${UI_STATUS}" >&2
  exit 1
fi

cleanup
APP_PID=""

echo "==> Local proof summary"
cat <<EOF
release_dir=${RELEASE_DIR}
config_path=${CONFIG_PATH}
port=${PORT}
health_status=${HEALTH_STATUS}
ui_status=${UI_STATUS}
EOF
