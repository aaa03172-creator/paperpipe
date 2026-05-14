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
SLOT_TUNING_REVIEW_RUN_ID="backend_api_smoke_slot_tuning_review"
SLOT_TUNING_REVIEW_ROOT="${SMOKE_TMP_DIR}/slot_classification_tuning_review"
SLOT_TUNING_REVIEW_RUN_ROOT="${SLOT_TUNING_REVIEW_ROOT}/${SLOT_TUNING_REVIEW_RUN_ID}"
PARSER_FIXTURE_ROOT="${SMOKE_TMP_DIR}/parser_eval_fixtures"
PARSER_COMPARE_METRICS="${PARSER_FIXTURE_ROOT}/compare/metrics.json"
PARSER_SECTION_SUMMARY="${PARSER_FIXTURE_ROOT}/section/summary.json"
PARSER_TABLE_SUMMARY="${PARSER_FIXTURE_ROOT}/table/summary.json"
PARSER_BLOCKER_TRIAGE_SUMMARY="${PARSER_FIXTURE_ROOT}/blocker_triage/summary.json"
PARSER_RESCUE_CANDIDATE_SUMMARY="${PARSER_FIXTURE_ROOT}/rescue_candidates/summary.json"
mkdir -p "${SLOT_TUNING_REVIEW_RUN_ROOT}"
mkdir -p "$(dirname "${PARSER_COMPARE_METRICS}")" "$(dirname "${PARSER_SECTION_SUMMARY}")" \
  "$(dirname "${PARSER_TABLE_SUMMARY}")" "$(dirname "${PARSER_BLOCKER_TRIAGE_SUMMARY}")" \
  "$(dirname "${PARSER_RESCUE_CANDIDATE_SUMMARY}")"
cat > "${SLOT_TUNING_REVIEW_RUN_ROOT}/summary.json" <<JSON
{
  "schema_version": "slot_classification_tuning_review.v1",
  "generated_at": "2026-05-14T00:00:00+00:00",
  "run_id": "${SLOT_TUNING_REVIEW_RUN_ID}",
  "advisory_only": true,
  "inputs": {
    "paired_compare_summary_path": null,
    "default_rerun_drift_summary_path": null,
    "boundary_rerun_drift_summary_path": null,
    "max_default_rerun_drift_rate": 0.0,
    "max_boundary_rerun_drift_rate": 0.0
  },
  "decision": {
    "recommended_action": "hold_current_prompt_policy",
    "review_ready": false,
    "decision_reason": "Backend smoke fixture keeps the advisory surface visible without promoting slot tuning.",
    "next_step": "Use real slot tuning review artifacts for release evidence.",
    "latest_compare_run_id": null,
    "paired_compare_status": "missing",
    "default_rerun_status": "missing",
    "boundary_rerun_status": "missing",
    "prompt_change_ready": false,
    "prompt_change_status": "blocked",
    "prompt_change_blocker": "smoke_fixture_advisory_only",
    "tuning_targets": ["slot_classification"],
    "tuning_actions": [],
    "action_plan": [],
    "tuning_recommendations": []
  },
  "signal_summary": {
    "fixture": true,
    "surface": "backend_api_smoke"
  }
}
JSON
cat > "${SLOT_TUNING_REVIEW_RUN_ROOT}/audit.md" <<MD
# Backend API Smoke Slot Tuning Review Fixture

This is a temporary smoke-only advisory fixture. It verifies that internal data readiness keeps the slot classification tuning review surface visible without treating it as runtime promotion evidence.
MD
export PAPERPIPE_SLOT_CLASSIFICATION_TUNING_REVIEW_ROOT="${SLOT_TUNING_REVIEW_ROOT}"
cat > "${PARSER_COMPARE_METRICS}" <<JSON
{
  "schema_version": "ingest_backend_eval.v1",
  "generated_at": "2026-05-14T00:00:00+00:00",
  "run_id": "backend_api_smoke_parser_compare_fixture",
  "baseline_backend": "fitz_pdfplumber",
  "candidate_backend": "docling",
  "document_count": 53,
  "backend_metrics": {
    "fitz_pdfplumber": {
      "document_count": 53,
      "success_count": 53,
      "error_count": 0,
      "backend_unavailable_count": 0,
      "docs_with_doi_count": 53,
      "docs_with_tables_count": 10,
      "docs_with_meaningful_tables_count": 10,
      "docs_with_table_fallback_count": 0,
      "docs_with_text_count": 53,
      "avg_text_char_count": 1200.0
    },
    "docling": {
      "document_count": 53,
      "success_count": 53,
      "error_count": 0,
      "backend_unavailable_count": 0,
      "docs_with_doi_count": 53,
      "docs_with_tables_count": 11,
      "docs_with_meaningful_tables_count": 11,
      "docs_with_table_fallback_count": 0,
      "docs_with_text_count": 53,
      "avg_text_char_count": 1250.0,
      "docs_with_same_page_table_rescue_count": 1,
      "same_page_table_rescue_page_event_count": 1,
      "same_page_table_rescue_patched_cell_count": 1,
      "table_failure_taxonomy_counts": {
        "SAME_PAGE_TABLE_RESCUE_PATCHED_PREFIX_TRUNCATION": 1,
        "FALLBACK_TABLE_SKIPPED_PRIMARY_PAGE_COVERED": 0
      }
    }
  },
  "comparison": {
    "compared_document_count": 53,
    "backend_unavailable_docs": [],
    "error_increase_docs": [],
    "empty_text_increase_docs": [],
    "doi_loss_docs": [],
    "meaningful_table_loss_docs": [],
    "meaningful_table_gain_docs": [{}],
    "same_page_merge_docs": [{}],
    "low_text_ratio_docs": [],
    "decision": {
      "passed": true,
      "failed_checks": []
    }
  }
}
JSON
cat > "${PARSER_SECTION_SUMMARY}" <<JSON
{
  "run_id": "backend_api_smoke_parser_section_fixture",
  "status": "ok",
  "document_count": 53,
  "page_coverage_preserved_count": 53,
  "missing_page_docs_count": 0,
  "low_page_text_ratio_docs_count": 0,
  "low_page_text_ratio_doc_bucket_counts": {},
  "low_page_text_ratio_page_bucket_counts": {},
  "low_page_text_ratio_unclassified_docs_count": 0,
  "low_total_text_ratio_docs_count": 0,
  "section_collapse_docs_count": 0
}
JSON
cat > "${PARSER_TABLE_SUMMARY}" <<JSON
{
  "run_id": "backend_api_smoke_parser_table_fixture",
  "status": "ok",
  "document_count": 1,
  "semantic_merge_preserved_count": 1,
  "content_gap_count": 0
}
JSON
cat > "${PARSER_BLOCKER_TRIAGE_SUMMARY}" <<JSON
{
  "run_id": "backend_api_smoke_parser_blocker_triage_fixture",
  "aggregate": {
    "table_merge_content_gap_doc_count": 0,
    "table_candidate_truncation_pair_count": 0,
    "table_same_page_duplicate_risk_page_count": 0
  },
  "decision": {
    "candidate_action": "no_candidate_blockers_detected",
    "table_runtime_patch_action": "no_table_runtime_patch_needed"
  }
}
JSON
cat > "${PARSER_RESCUE_CANDIDATE_SUMMARY}" <<JSON
{
  "run_id": "backend_api_smoke_parser_rescue_candidate_fixture",
  "candidate_page_count": 0,
  "runtime_change_approved": false
}
JSON

"${RESOLVER_RUNNER}" scripts/eval/check_internal_data_readiness.py \
  --run-id "${INTERNAL_DATA_RUN_ID}" \
  --out-dir "${SMOKE_TMP_DIR}/internal_data_readiness"

"${RESOLVER_RUNNER}" scripts/eval/check_slot_classification_tuning_visibility.py \
  --internal-data-summary "${SMOKE_TMP_DIR}/internal_data_readiness/${INTERNAL_DATA_RUN_ID}" \
  --out-dir "${SMOKE_TMP_DIR}/slot_classification_tuning_visibility" \
  --run-id "${SLOT_TUNING_VISIBILITY_RUN_ID}"

"${RESOLVER_RUNNER}" scripts/eval/check_parser_baseline_readiness.py \
  --compare-metrics "${PARSER_COMPARE_METRICS}" \
  --section-summary "${PARSER_SECTION_SUMMARY}" \
  --table-merge-summary "${PARSER_TABLE_SUMMARY}" \
  --out-dir "${SMOKE_TMP_DIR}/parser_baseline_readiness" \
  --run-id "${PARSER_BASELINE_RUN_ID}" \
  --allow-advisory-hold

"${RESOLVER_RUNNER}" scripts/eval/check_same_page_table_rescue_readiness.py \
  --compare-metrics "${PARSER_COMPARE_METRICS}" \
  --table-merge-summary "${PARSER_TABLE_SUMMARY}" \
  --blocker-triage-summary "${PARSER_BLOCKER_TRIAGE_SUMMARY}" \
  --rescue-candidate-summary "${PARSER_RESCUE_CANDIDATE_SUMMARY}" \
  --parser-readiness-summary "${SMOKE_TMP_DIR}/parser_baseline_readiness/${PARSER_BASELINE_RUN_ID}" \
  --out-dir "${SMOKE_TMP_DIR}/same_page_table_rescue_readiness" \
  --run-id "${SAME_PAGE_TABLE_RESCUE_RUN_ID}"

"${RESOLVER_RUNNER}" scripts/eval/inventory_parser_eval_artifacts.py \
  --source-readiness-summary "${SMOKE_TMP_DIR}/parser_baseline_readiness/${PARSER_BASELINE_RUN_ID}" \
  --derived-rescue-readiness-summary "${SMOKE_TMP_DIR}/same_page_table_rescue_readiness/${SAME_PAGE_TABLE_RESCUE_RUN_ID}" \
  --derived-compare-metrics "${PARSER_COMPARE_METRICS}" \
  --out-dir "${SMOKE_TMP_DIR}/parser_eval_artifact_inventory" \
  --run-id "${PARSER_EVAL_INVENTORY_RUN_ID}"
