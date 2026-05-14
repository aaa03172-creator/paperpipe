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

"${PYTHON_BIN}" -m pytest -q \
  tests/test_escalation_prompt_policy.py \
  tests/test_llm_provider_task_temperature.py \
  tests/test_escalation_judge_smoke.py

"${PYTHON_BIN}" scripts/check_escalation_judge_smoke.py --max-mismatches 0
"${PYTHON_BIN}" scripts/check_escalation_judge_smoke.py \
  --fixture tests/fixtures/escalation_judge_case/real_cases_20260327.json \
  --max-mismatches 0
"${PYTHON_BIN}" scripts/check_escalation_judge_smoke.py \
  --fixture tests/fixtures/escalation_judge_case/real_cases_extended_20260327.json \
  --max-mismatches 0
"${PYTHON_BIN}" scripts/lint_docs.py
