# Quality and Reference Docs Staging Prep

Status: staging manifest  
Date: 2026-03-22  
Branch: `codex/agents-smoke-ci-check`

## Intent

Freeze the remaining standalone documentation artifacts for the teacher quality loop and external operating-pattern review prompt.

## Included scope

- `docs/teacher_quality_loop.md`
- `docs/archive/Everything_Claude_Code_Review_Prompt_2026-03-22.md`
- `docs/reports/Quality_And_Reference_Docs_Staging_Prep_2026-03-22.md`

## Explicitly excluded

- `.codex/` local skill or agent files
- teacher-quality scripts/tests/goldset artifacts
- runtime/frontend code changes

## Verification

1. `python3 scripts/lint_docs.py`
2. staged diff stays docs-only

## Commit target

`docs(quality): add teacher loop and operating-pattern notes`
