#!/usr/bin/env bash
set -euo pipefail
set +m

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This proof wrapper is macOS-only." >&2
  exit 1
fi

PORT="${PAPERPIPE_MACOS_CLOUD_DEMO_PROOF_PORT:-8046}"
CONFIG_PATH="${PAPERPIPE_CONFIG_PATH:-${ROOT_DIR}/config.example.yaml}"
EXECUTABLE="${PAPERPIPE_MACOS_CLOUD_DEMO_EXECUTABLE:-${ROOT_DIR}/dist/Lattice.app/Contents/MacOS/Lattice}"
LOG_PATH="${PAPERPIPE_MACOS_CLOUD_DEMO_LOG:-/tmp/lattice-cloud-demo-proof.log}"
PROJECT_ID="${PAPERPIPE_GCP_PROJECT_ID:-knudc-a01068202087}"
RAW_BUCKET="${PAPERPIPE_GCS_RAW_PDF_BUCKET:-paperpipe-raw-pdf-dev-knudc-a01068202087}"
PAGE_BUCKET="${PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET:-paperpipe-page-artifacts-dev-knudc-a01068202087}"
METADATA_COLLECTION="${PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION:-cloud_papers_demo}"
SEARCH_QUERY="${PAPERPIPE_DEMO_SEARCH_QUERY:-amyloid}"
EXPECTED_PAPER_ID="${PAPERPIPE_DEMO_EXPECTED_PAPER_ID:-cloudpdf_lab_001_fe476330a3bd}"
EXPECTED_PAGE_TEXT="${PAPERPIPE_DEMO_EXPECTED_PAGE_TEXT:-More than 50 million people worldwide}"
API_KEY="${LATTICE_API_KEY:-demo-secret}"

if [[ ! -x "${EXECUTABLE}" ]]; then
  echo "Packaged executable not found or not executable: ${EXECUTABLE}" >&2
  echo "Build the bundle first with: uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean" >&2
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
  set -e
}
trap cleanup EXIT

echo "==> Starting packaged Lattice cloud demo runtime"
PAPERPIPE_INSTALL_LAYOUT=1 \
PAPERPIPE_CONFIG_PATH="${CONFIG_PATH}" \
LATTICE_API_KEY="${API_KEY}" \
PAPERPIPE_CLOUD_ADAPTER=gcs \
PAPERPIPE_CLOUD_METADATA_STORE=firestore \
PAPERPIPE_GCP_PROJECT_ID="${PROJECT_ID}" \
PAPERPIPE_GCS_RAW_PDF_BUCKET="${RAW_BUCKET}" \
PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET="${PAGE_BUCKET}" \
PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION="${METADATA_COLLECTION}" \
PAPERPIPE_DEMO_EXPECTED_PAPER_ID="${EXPECTED_PAPER_ID}" \
PAPERPIPE_DEMO_SEARCH_QUERY="${SEARCH_QUERY}" \
LATTICE_START_PATH="/ui/papers/${EXPECTED_PAPER_ID}?source=cloud" \
"${EXECUTABLE}" start --no-open --host 127.0.0.1 --port "${PORT}" >"${LOG_PATH}" 2>&1 &
APP_PID=$!

for _ in {1..40}; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/tmp/lattice-cloud-demo-proof-health.json 2>/dev/null; then
    break
  fi
  sleep 1
done

HEALTH_STATUS="$(curl -sS -o /tmp/lattice-cloud-demo-proof-health.json -w '%{http_code}' "http://127.0.0.1:${PORT}/health")"
UI_STATUS="$(curl -sS -o /tmp/lattice-cloud-demo-proof-ui.html -w '%{http_code}' "http://127.0.0.1:${PORT}/ui")"
CLOUD_LIST_STATUS="$(curl -sS -o /tmp/lattice-cloud-demo-proof-list.json -w '%{http_code}' -H "origin: http://testserver" -H "x-api-key: ${API_KEY}" "http://127.0.0.1:${PORT}/api/cloud/papers")"
CLOUD_SEARCH_STATUS="$(curl -sS -G -o /tmp/lattice-cloud-demo-proof-search.json -w '%{http_code}' -H "origin: http://testserver" -H "x-api-key: ${API_KEY}" --data-urlencode "q=${SEARCH_QUERY}" "http://127.0.0.1:${PORT}/api/cloud/papers/search")"
CLOUD_PAGE_STATUS="$(curl -sS -o /tmp/lattice-cloud-demo-proof-page.json -w '%{http_code}' -H "origin: http://testserver" -H "x-api-key: ${API_KEY}" "http://127.0.0.1:${PORT}/api/cloud/papers/${EXPECTED_PAPER_ID}/page")"

if [[ "${HEALTH_STATUS}" != "200" ]]; then
  echo "Expected /health to return 200, got ${HEALTH_STATUS}" >&2
  exit 1
fi

if [[ "${UI_STATUS}" != "200" ]]; then
  echo "Expected /ui to return 200, got ${UI_STATUS}" >&2
  exit 1
fi

if [[ "${CLOUD_LIST_STATUS}" != "200" ]]; then
  echo "Expected /api/cloud/papers to return 200, got ${CLOUD_LIST_STATUS}" >&2
  cat /tmp/lattice-cloud-demo-proof-list.json >&2 || true
  exit 1
fi

if [[ "${CLOUD_SEARCH_STATUS}" != "200" ]]; then
  echo "Expected /api/cloud/papers/search to return 200, got ${CLOUD_SEARCH_STATUS}" >&2
  cat /tmp/lattice-cloud-demo-proof-search.json >&2 || true
  exit 1
fi

if [[ "${CLOUD_PAGE_STATUS}" != "200" ]]; then
  echo "Expected /api/cloud/papers/${EXPECTED_PAPER_ID}/page to return 200, got ${CLOUD_PAGE_STATUS}" >&2
  cat /tmp/lattice-cloud-demo-proof-page.json >&2 || true
  exit 1
fi

if ! grep -q "${EXPECTED_PAPER_ID}" /tmp/lattice-cloud-demo-proof-search.json; then
  echo "Expected cloud search response to include ${EXPECTED_PAPER_ID}" >&2
  cat /tmp/lattice-cloud-demo-proof-search.json >&2 || true
  exit 1
fi

if ! grep -q "${EXPECTED_PAGE_TEXT}" /tmp/lattice-cloud-demo-proof-page.json; then
  echo "Expected cloud page response to include real extracted text: ${EXPECTED_PAGE_TEXT}" >&2
  cat /tmp/lattice-cloud-demo-proof-page.json >&2 || true
  exit 1
fi

if grep -Eq "gs://|gcs_pdf_object_ref|gcs_page_artifact_object_ref|signed_url|service_account|${RAW_BUCKET}|${PAGE_BUCKET}" \
  /tmp/lattice-cloud-demo-proof-list.json /tmp/lattice-cloud-demo-proof-search.json /tmp/lattice-cloud-demo-proof-page.json; then
  echo "Cloud public payload leaked cloud/internal storage details." >&2
  exit 1
fi

cleanup
APP_PID=""

echo "==> Packaged cloud demo proof summary"
cat <<EOF
executable=${EXECUTABLE}
config_path=${CONFIG_PATH}
port=${PORT}
health_status=${HEALTH_STATUS}
ui_status=${UI_STATUS}
cloud_list_status=${CLOUD_LIST_STATUS}
cloud_search_status=${CLOUD_SEARCH_STATUS}
cloud_page_status=${CLOUD_PAGE_STATUS}
expected_paper_id=${EXPECTED_PAPER_ID}
expected_page_text=${EXPECTED_PAGE_TEXT}
start_path=/ui/papers/${EXPECTED_PAPER_ID}?source=cloud
metadata_collection=${METADATA_COLLECTION}
log_path=${LOG_PATH}
EOF
