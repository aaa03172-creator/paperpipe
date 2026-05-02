#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
RESOLVER_RUNNER="$(command -v python3 || command -v python)"
if [[ -z "${RESOLVER_RUNNER}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi
PYTHON_BIN="$("${RESOLVER_RUNNER}" "${ROOT_DIR}/scripts/resolve_verification_python.py" --require-module pytest)"

if ! command -v ruff >/dev/null 2>&1; then
  echo "ruff is required. Install it with: python3 -m pip install ruff" >&2
  exit 127
fi

MEETING_PACK_SMOKE_ROOT="tmp/meeting_pack_real_smoke"
MEETING_PACK_SMOKE_VAULT="frontend/.e2e-backend-runtime/obsidian"
MEETING_PACK_BOOTSTRAP_SCRIPT="frontend/scripts/run_backend_for_e2e.sh"

RUFF_TARGETS=(
  backend/routers/meeting_packs.py
  scripts/check_meeting_pack_real_smoke.py
  scripts/check_meeting_pack_storage_sync.py
  src/meeting_packs/evidence.py
  src/meeting_packs/renderer.py
  src/meeting_packs/service.py
  src/meeting_packs/source_resolver.py
  src/meeting_packs/store.py
  src/schemas/meeting_pack.py
  tests/test_api_key_auth.py
  tests/meeting_pack_actual_paper_fixture.py
  tests/test_meeting_pack_api.py
  tests/test_meeting_pack_real_smoke_script.py
  tests/test_meeting_pack_schema.py
  tests/test_meeting_pack_service.py
  tests/test_meeting_pack_storage_sync_script.py
  tests/test_meeting_pack_source_resolver.py
  tests/test_meeting_pack_store.py
  tests/test_meeting_packs_api.py
  tests/test_runtime_paths_meeting_packs.py
)

PYTEST_TARGETS=(
  tests/test_api_key_auth.py
  tests/test_meeting_pack_api.py
  tests/test_meeting_pack_real_smoke_script.py
  tests/test_meeting_pack_schema.py
  tests/test_meeting_pack_service.py
  tests/test_meeting_pack_storage_sync_script.py
  tests/test_meeting_pack_source_resolver.py
  tests/test_meeting_pack_store.py
  tests/test_meeting_packs_api.py
  tests/test_runtime_paths_meeting_packs.py
)

ruff check "${RUFF_TARGETS[@]}" --select F,E701,E9
"${PYTHON_BIN}" -m pytest -q "${PYTEST_TARGETS[@]}"
if [[ ! -d "${MEETING_PACK_SMOKE_VAULT}" ]]; then
  echo "Meeting Pack verify: bootstrapping E2E runtime fixture..."
  E2E_BOOTSTRAP_ONLY=1 "./${MEETING_PACK_BOOTSTRAP_SCRIPT}"
fi
rm -rf "${MEETING_PACK_SMOKE_ROOT}"
"${PYTHON_BIN}" scripts/check_meeting_pack_real_smoke.py --root "${MEETING_PACK_SMOKE_ROOT}"
"${PYTHON_BIN}" scripts/check_meeting_pack_storage_sync.py --root "${MEETING_PACK_SMOKE_ROOT}" --vault-path "${MEETING_PACK_SMOKE_VAULT}" --require-regenerable
"${PYTHON_BIN}" scripts/lint_docs.py
