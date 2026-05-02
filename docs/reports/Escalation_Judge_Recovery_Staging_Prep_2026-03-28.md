# Escalation Judge Recovery Staging Prep

Date: 2026-03-28
Status: Ready for isolated packaging after dependency closure recheck
Owner: Runtime maintainers

## Goal

Package the bounded escalation recovery lane that:

- keeps the escalation gate conservative while remaining biomedical-general by default
- keeps deterministic `temperature=0` gate decoding
- locks the recovered behavior with policy tests plus 10-case and 22-case real-history smoke fixtures
- includes the currently required config/schema/runtime-path dependency owners that `src/llm_provider.py` imports in the present worktree

## Include

- `scripts/run_escalation_judge_verify.sh`
- `src/llm_provider.py`
- `src/config.py`
- `src/services/runtime_paths.py`
- `src/schemas/core.py`
- `tests/test_escalation_prompt_policy.py`
- `tests/test_llm_provider_task_temperature.py`
- `tests/test_escalation_judge_smoke.py`
- `tests/fixtures/escalation_judge_case/real_cases_20260327.json`
- `tests/fixtures/escalation_judge_case/real_cases_extended_20260327.json`
- `docs/reports/Escalation_Judge_Policy_Review_2026-03-27.md`
- `docs/reports/Escalation_Judge_Recovery_Staging_Prep_2026-03-28.md`

## Dependency Note

This bundle assumes the earlier smoke harness already exists in the target base:

- `scripts/check_escalation_judge_smoke.py`
- `tests/fixtures/escalation_judge_case/cases.json`

If the target base does not have those files yet, land the smoke-harness bundle from `docs/reports/Escalation_Judge_Smoke_Staging_Prep_2026-03-27.md` first.

Recheck result:

- the first recovery include list was incomplete
- `src/llm_provider.py` currently imports `resolve_clinical_extraction_feature` / `resolve_specialty_trial_extraction_feature` from `src/config.py`
- the current `src/config.py` in turn imports `feedback_index_root`, `logs_root`, and `rag_root` from `src/services/runtime_paths.py`
- `src/llm_provider.py` also imports `BiomedicalClinicalExtraction` from `src.schemas`, which currently comes from `src/schemas/core.py`
- therefore a clean temp closure requires those three dependency files in addition to the escalation-specific files above

## Exclude

- broader biomedical clinical extraction changes unrelated to escalation recovery
- meeting-pack, deep-read, runtime-readiness, and profile lanes currently dirty in the worktree
- unrelated docs/reports created on 2026-03-27 and 2026-03-28

## Verification

Current worktree:

- `./scripts/run_escalation_judge_verify.sh`

Clean temp closure:

- apply only the include list on top of `HEAD`
- run `./scripts/run_escalation_judge_verify.sh`

Reproduced temp-closure check:

- first attempt with the escalation-only include list failed during test collection because `src/config.py` and `src/services/runtime_paths.py` dependencies were missing from the bundle
- second attempt with the full include list above passed:
  - `pytest tests/test_escalation_prompt_policy.py tests/test_llm_provider_task_temperature.py tests/test_escalation_judge_smoke.py -q`
  - result: `21 passed`

## Commit Message

`fix(llm): align escalation fast-lane with biomedical-general policy`
