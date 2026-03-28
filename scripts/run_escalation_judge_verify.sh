#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

pytest -q \
  tests/test_escalation_prompt_policy.py \
  tests/test_llm_provider_task_temperature.py \
  tests/test_escalation_judge_smoke.py

python3 scripts/check_escalation_judge_smoke.py --max-mismatches 0
python3 scripts/check_escalation_judge_smoke.py \
  --fixture tests/fixtures/escalation_judge_case/real_cases_20260327.json \
  --max-mismatches 0
python3 scripts/check_escalation_judge_smoke.py \
  --fixture tests/fixtures/escalation_judge_case/real_cases_extended_20260327.json \
  --max-mismatches 0
python3 scripts/lint_docs.py
