# Schemas Export Skill-State Staging Prep (2026-03-23)

## Goal
Split a narrow schema-export lane that makes the expanded schema surface available from `src.schemas` and locks the related skill-state fallback contract with tests.

## Included
- `/Users/jangseongjin/paperpipe/src/schemas/__init__.py`
- `/Users/jangseongjin/paperpipe/tests/test_skill_state_contract.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Schemas_Export_Skill_State_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- The source change is limited to `src.schemas` re-exports.
- The new test file covers skill-state contract expectations already implemented in committed runtime code.
- No frontend, config, or ingest workflow changes are required.

## Verification Plan
In a temp worktree containing only this patch:
- `pytest -q tests/test_skill_state_contract.py`
- `python3 scripts/lint_docs.py`

## Expected Outcome
The schema package exposes the newer paper-notes, chart-pack, image-evidence, meeting-pack, method-comparison, research-dna, chat, and skills models, and skill-state regression coverage is pinned.
