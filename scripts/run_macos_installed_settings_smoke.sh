#!/usr/bin/env bash
set -euo pipefail
set +m

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This smoke wrapper is macOS-only." >&2
  exit 1
fi

APP_EXECUTABLE="${PAPERPIPE_INSTALLED_APP_EXECUTABLE:-/Applications/Lattice.app/Contents/MacOS/Lattice}"
CONFIG_PATH="${PAPERPIPE_CONFIG_PATH:-${ROOT_DIR}/config.example.yaml}"
PORT="${PAPERPIPE_INSTALLED_SETTINGS_SMOKE_PORT:-8056}"
API_KEY="${LATTICE_API_KEY:-demo-secret}"
LOG_PATH="${PAPERPIPE_INSTALLED_SETTINGS_SMOKE_LOG:-/tmp/lattice-installed-settings-smoke.log}"
UI_BUNDLE_DIR="/Applications/Lattice.app/Contents/Resources/frontend/dist"

if [[ ! -x "${APP_EXECUTABLE}" ]]; then
  echo "Installed Lattice executable not found or not executable: ${APP_EXECUTABLE}" >&2
  exit 1
fi

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "Config not found: ${CONFIG_PATH}" >&2
  exit 1
fi

APP_PID=""
cleanup() {
  set +e
  if [[ -n "${APP_PID}" ]] && kill -0 "${APP_PID}" 2>/dev/null; then
    pkill -INT -P "${APP_PID}" 2>/dev/null || true
    kill -INT "${APP_PID}" 2>/dev/null || true
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

echo "==> Starting installed Lattice settings smoke"
env \
  -u OPENAI_API_KEY \
  -u ANTHROPIC_API_KEY \
  -u GEMINI_API_KEY \
  -u GOOGLE_API_KEY \
  PAPERPIPE_INSTALL_LAYOUT=1 \
  PAPERPIPE_CONFIG_PATH="${CONFIG_PATH}" \
  LATTICE_API_KEY="${API_KEY}" \
  "${APP_EXECUTABLE}" start --no-open --host 127.0.0.1 --port "${PORT}" >"${LOG_PATH}" 2>&1 &
APP_PID=$!

for _ in {1..40}; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/tmp/lattice-installed-settings-health.json 2>/dev/null; then
    break
  fi
  sleep 1
done

HEALTH_STATUS="$(curl -sS -o /tmp/lattice-installed-settings-health.json -w '%{http_code}' "http://127.0.0.1:${PORT}/health")"
UI_STATUS="$(curl -sS -o /tmp/lattice-installed-settings-ui.html -w '%{http_code}' "http://127.0.0.1:${PORT}/ui/settings")"
SETTINGS_STATUS="$(curl -sS -o /tmp/lattice-installed-settings-llm.json -w '%{http_code}' -H "origin: http://testserver" -H "x-api-key: ${API_KEY}" "http://127.0.0.1:${PORT}/api/runtime-settings/llm")"

if [[ "${HEALTH_STATUS}" != "200" ]]; then
  echo "Expected /health to return 200, got ${HEALTH_STATUS}" >&2
  exit 1
fi

if [[ "${UI_STATUS}" != "200" ]]; then
  echo "Expected /ui/settings to return 200, got ${UI_STATUS}" >&2
  exit 1
fi

if [[ "${SETTINGS_STATUS}" != "200" ]]; then
  echo "Expected /api/runtime-settings/llm to return 200, got ${SETTINGS_STATUS}" >&2
  cat /tmp/lattice-installed-settings-llm.json >&2 || true
  exit 1
fi

python3 - /tmp/lattice-installed-settings-llm.json <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
assert payload["provider"] in {"openai", "anthropic", "gemini"}, payload
assert payload["api_key_source"] == "none", payload
assert payload["api_key_configured"] is False, payload
PY

if ! grep -R "Google Gemini" "${UI_BUNDLE_DIR}/assets" >/dev/null; then
  echo "Installed UI bundle does not contain the Google Gemini provider option." >&2
  exit 1
fi

if ! grep -R "Test live call" "${UI_BUNDLE_DIR}/assets" >/dev/null; then
  echo "Installed UI bundle does not contain the explicit live-call test action." >&2
  exit 1
fi

if ! grep -R "Paste key" "${UI_BUNDLE_DIR}/assets" >/dev/null; then
  echo "Installed UI bundle does not contain the API key paste action." >&2
  exit 1
fi

if grep -R "gemini-live-test-secret\\|gemini-doublecheck-secret\\|gemini-ui-smoke-secret" "${UI_BUNDLE_DIR}" >/dev/null; then
  echo "Installed UI bundle contains test secret material." >&2
  exit 1
fi

cleanup
APP_PID=""

echo "==> Installed settings smoke summary"
cat <<EOF
app_executable=${APP_EXECUTABLE}
config_path=${CONFIG_PATH}
port=${PORT}
health_status=${HEALTH_STATUS}
ui_status=${UI_STATUS}
settings_status=${SETTINGS_STATUS}
log_path=${LOG_PATH}
EOF
