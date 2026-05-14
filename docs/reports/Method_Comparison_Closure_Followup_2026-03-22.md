# Method Comparison Closure Follow-up

Status: follow-up staging manifest  
Date: 2026-03-22  
Branch: `codex/agents-smoke-ci-check`

## Intent

Close the missing `src/skills/storage.py` helper dependency required by the already committed method-comparison backend lane.

## Included scope

- `src/skills/storage.py`
- `docs/reports/Method_Comparison_Closure_Followup_2026-03-22.md`

## Why this is separate

`612b3d4 feat(method-comparison): harden backend comparison core` depends on `resolve_note_slug_by_paper_id(...)`, but that helper was not included in the original commit.

## Verification

1. `PAPERPIPE_CONFIG_PATH=config.example.yaml python3 -c 'import backend.main'`
2. `pytest -q tests/test_method_comparison_service.py tests/test_method_comparisons_api.py`
3. `python3 scripts/lint_docs.py`

## Commit target

`fix(method-comparison): restore note slug resolution helpers`
