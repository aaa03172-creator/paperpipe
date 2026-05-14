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

"${PYTHON_BIN}" scripts/check_legacy_trial_extraction_alias.py --root .

if ! command -v ruff >/dev/null 2>&1; then
  echo "ruff is required. Install it with: python3 -m pip install ruff" >&2
  exit 127
fi

RUFF_TARGETS=(
  backend/main.py
  backend/routers/paper_notes.py
  scripts/eval/check_intake_override_coverage_gate.py
  scripts/eval/check_internal_data_readiness.py
  scripts/eval/inventory_parser_eval_artifacts.py
  scripts/eval/check_parser_baseline_readiness.py
  scripts/eval/check_same_page_table_rescue_readiness.py
  scripts/eval/check_slot_classification_tuning_visibility.py
  scripts/eval/audit_same_page_table_rescue_candidates.py
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
  tests/test_intake_override_coverage_gate.py
  tests/test_internal_data_readiness.py
  tests/test_parser_eval_artifact_inventory.py
  tests/test_parser_baseline_readiness.py
  tests/test_same_page_table_rescue_readiness.py
  tests/test_slot_classification_tuning_visibility.py
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
  tests/test_intake_override_coverage_gate.py
  tests/test_internal_data_readiness.py
  tests/test_parser_baseline_readiness.py
  tests/test_same_page_table_rescue_readiness.py
  tests/test_slot_classification_tuning_visibility.py
  tests/test_obsidian_save.py
  tests/test_processor_gate_integration.py
  tests/test_processor_pdf_context.py
)

ruff check "${RUFF_TARGETS[@]}" --select F,E701,E9

# Running all backend smoke targets in one pytest process has been flaky in this
# environment; keep the smoke contract identical, but execute file-by-file so
# resource spikes in one aggregate process do not mask which target failed.
for target in "${PYTEST_TARGETS[@]}"; do
  "${PYTHON_BIN}" -m pytest -q "${target}"
done

SMOKE_TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/paperpipe_backend_smoke.XXXXXX")"
trap 'rm -rf "${SMOKE_TMP_DIR}"' EXIT

INTERNAL_DATA_RUN_ID="backend_api_smoke_internal_data_readiness"
PARSER_BASELINE_RUN_ID="backend_api_smoke_parser_baseline_readiness"
PARSER_EVAL_INVENTORY_RUN_ID="backend_api_smoke_parser_eval_artifact_inventory"
SAME_PAGE_TABLE_RESCUE_RUN_ID="backend_api_smoke_same_page_table_rescue_readiness"
SLOT_TUNING_VISIBILITY_RUN_ID="backend_api_smoke_slot_tuning_visibility"

"${RESOLVER_RUNNER}" scripts/eval/check_internal_data_readiness.py \
  --run-id "${INTERNAL_DATA_RUN_ID}" \
  --out-dir "${SMOKE_TMP_DIR}/internal_data_readiness"

"${RESOLVER_RUNNER}" scripts/eval/check_slot_classification_tuning_visibility.py \
  --internal-data-summary "${SMOKE_TMP_DIR}/internal_data_readiness/${INTERNAL_DATA_RUN_ID}" \
  --out-dir "${SMOKE_TMP_DIR}/slot_classification_tuning_visibility" \
  --run-id "${SLOT_TUNING_VISIBILITY_RUN_ID}"

"${RESOLVER_RUNNER}" scripts/eval/check_parser_baseline_readiness.py \
  --out-dir "${SMOKE_TMP_DIR}/parser_baseline_readiness" \
  --run-id "${PARSER_BASELINE_RUN_ID}" \
  --allow-advisory-hold

"${RESOLVER_RUNNER}" scripts/eval/inventory_parser_eval_artifacts.py \
  --out-dir "${SMOKE_TMP_DIR}/parser_eval_artifact_inventory" \
  --run-id "${PARSER_EVAL_INVENTORY_RUN_ID}"

"${RESOLVER_RUNNER}" scripts/eval/check_same_page_table_rescue_readiness.py \
  --out-dir "${SMOKE_TMP_DIR}/same_page_table_rescue_readiness" \
  --run-id "${SAME_PAGE_TABLE_RESCUE_RUN_ID}"
