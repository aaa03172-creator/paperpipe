# Escalation Judge Smoke Staging Prep

Date: 2026-03-27
Status: Ready for isolated packaging
Owner: Runtime maintainers

## Goal

Add a bounded smoke harness for the escalation judge model, with representative fixture cases and summary-count regression coverage.

## Include

- `scripts/check_escalation_judge_smoke.py`
- `tests/fixtures/escalation_judge_case/cases.json`
- `tests/test_escalation_judge_smoke.py`
- `docs/reports/Escalation_Judge_Smoke_Staging_Prep_2026-03-27.md`

## Verification

Current worktree:
- `pytest -q tests/test_escalation_judge_smoke.py`
- `python3 scripts/check_escalation_judge_smoke.py --help >/dev/null`
- `python3 scripts/lint_docs.py`

Clean temp closure:
- apply staged bundle on top of `HEAD`
- run the same pytest set
- run the same help check
- run `python3 scripts/lint_docs.py`

## Commit Message

`test(llm): add escalation judge smoke harness`
