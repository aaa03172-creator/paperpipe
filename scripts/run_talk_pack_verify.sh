#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
RESOLVER_RUNNER="$(command -v python3 || command -v python)"
if [[ -z "${RESOLVER_RUNNER}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi
PYTHON_BIN="$("${RESOLVER_RUNNER}" "${ROOT_DIR}/scripts/resolve_verification_python.py" --require-module pytest --require-module yaml)"

if ! command -v ruff >/dev/null 2>&1; then
  echo "ruff is required. Install it with: python3 -m pip install ruff" >&2
  exit 127
fi

TALK_PACK_SMOKE_ROOT="tmp/talk_pack_render_smoke"
TALK_PACK_IMAGE_EVIDENCE_SMOKE_ROOT="tmp/talk_pack_render_smoke_image_evidence"

RUFF_TARGETS=(
  backend/routers/talk_packs.py
  scripts/check_talk_pack_render_smoke.py
  src/schemas/talk_pack.py
  src/talk_packs/pptx_export.py
  src/talk_packs/service.py
  tests/talk_pack_pptx_runtime.py
  tests/test_api_key_auth.py
  tests/test_talk_pack_render_smoke_script.py
  tests/test_talk_pack_schema.py
  tests/test_talk_pack_service.py
  tests/test_talk_pack_store.py
  tests/test_talk_packs_api.py
  tests/test_runtime_shell_scripts.py
)

PYTEST_TARGETS=(
  tests/test_api_key_auth.py
  tests/test_talk_pack_render_smoke_script.py
  tests/test_talk_pack_schema.py
  tests/test_talk_pack_service.py
  tests/test_talk_pack_store.py
  tests/test_talk_packs_api.py
  tests/test_runtime_shell_scripts.py
)

ruff check "${RUFF_TARGETS[@]}" --select F,E701,E9
"${PYTHON_BIN}" -m pytest -q "${PYTEST_TARGETS[@]}"
rm -rf "${TALK_PACK_SMOKE_ROOT}"
"${PYTHON_BIN}" scripts/check_talk_pack_render_smoke.py --root "${TALK_PACK_SMOKE_ROOT}"
rm -rf "${TALK_PACK_IMAGE_EVIDENCE_SMOKE_ROOT}"
"${PYTHON_BIN}" scripts/check_talk_pack_render_smoke.py \
  --root "${TALK_PACK_IMAGE_EVIDENCE_SMOKE_ROOT}" \
  --talk-pack-id "talkpack_smoke_render_image_evidence_demo" \
  --visual-source image_evidence
