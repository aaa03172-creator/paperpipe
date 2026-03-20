#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v ruff >/dev/null 2>&1; then
  echo "ruff is required. Install it with: python3 -m pip install ruff" >&2
  exit 127
fi

RUFF_TARGETS=(
  backend/main.py
  backend/routers/paper_notes.py
  src/downloads_watcher.py
  src/llm_provider.py
  src/obsidian.py
  src/processor.py
  src/jobs/schemas.py
  src/schemas/chat.py
  src/schemas/ops.py
  src/schemas/paper_notes.py
  src/schemas/skills.py
  src/watcher.py
  tests/test_chat_api_stub.py
  tests/test_personas_api.py
  tests/test_paper_notes_api.py
  tests/test_obsidian_artifacts_api.py
  tests/test_ops_repair_stats_api.py
  tests/test_jobs_api_smoke.py
  tests/test_artifacts_runs_api.py
  tests/test_api_key_auth.py
  tests/full_integration_test.py
  tests/test_llm_provider_json.py
  tests/test_downloads_watcher.py
  tests/test_obsidian_save.py
  tests/test_processor_gate_integration.py
  tests/test_processor_pdf_context.py
)

PYTEST_TARGETS=(
  tests/test_chat_api_stub.py
  tests/test_personas_api.py
  tests/test_paper_notes_api.py
  tests/test_obsidian_artifacts_api.py
  tests/test_ops_repair_stats_api.py
  tests/test_jobs_api_smoke.py
  tests/test_artifacts_runs_api.py
  tests/test_api_key_auth.py
  tests/full_integration_test.py
  tests/test_llm_provider_json.py
  tests/test_downloads_watcher.py
  tests/test_obsidian_save.py
  tests/test_processor_gate_integration.py
  tests/test_processor_pdf_context.py
)

ruff check "${RUFF_TARGETS[@]}" --select F,E701,E9
pytest -q "${PYTEST_TARGETS[@]}"
