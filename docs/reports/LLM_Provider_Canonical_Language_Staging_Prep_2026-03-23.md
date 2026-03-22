# LLM Provider Canonical Language Staging Prep (2026-03-23)

## Goal
Split a narrow `llm_provider` lane that standardizes canonical summary language prompts to English and wires the teacher-review request path into the provider contract.

## Included
- `/Users/jangseongjin/paperpipe/src/llm_provider.py`
- `/Users/jangseongjin/paperpipe/tests/test_llm_provider_canonical_language.py`
- `/Users/jangseongjin/paperpipe/docs/reports/LLM_Provider_Canonical_Language_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- `src/quality/teacher_review.py` already expects `review_claimset_bundle(...)` on the provider.
- The current dirty change in `/Users/jangseongjin/paperpipe/src/llm_provider.py` supplies that contract, the `teacher_review` model mapping, and the canonical-English prompt wording.
- The new test file only asserts the canonical prompt language contract and does not pull in unrelated runtime changes.

## Explicitly Excluded
- `/Users/jangseongjin/paperpipe/src/config.py`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- `/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py`
- `/Users/jangseongjin/paperpipe/frontend/**`
- `cloud_table_fallback`, viewer-shell, and ingest-backend-eval work

## Verification Plan
In a temp worktree containing only this patch:
- `pytest -q /Users/.../tests/test_llm_provider_canonical_language.py /Users/.../tests/test_teacher_review.py /Users/.../tests/test_librarian_advanced.py`
- `python3 /Users/.../scripts/lint_docs.py`

## Expected Outcome
A self-contained runtime lane that preserves existing behavior, adds the provider entry point expected by teacher review, and makes one-liner/deep-read canonical outputs English by default.
