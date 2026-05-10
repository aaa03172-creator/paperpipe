# Method Comparison Core Staging Prep

Status: staging-prep manifest  
Date: 2026-03-20  
Lane: `method-comparison-core`

## Purpose

Define the self-contained backend core subset for Method Comparison so it can be committed without pulling the broader frontend viewer lane into the same change.

## In Scope

- `/Users/jangseongjin/paperpipe/backend/routers/method_comparisons.py`
- `/Users/jangseongjin/paperpipe/src/method_comparisons/service.py`
- `/Users/jangseongjin/paperpipe/tests/test_method_comparison_service.py`
- `/Users/jangseongjin/paperpipe/tests/test_method_comparisons_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_method_comparison_fixture_hardening.py`
- `/Users/jangseongjin/paperpipe/tests/fixtures/method_comparison_case/`
- `/Users/jangseongjin/paperpipe/docs/reports/Method_Comparison_Core_Staging_Prep_2026-03-20.md`

## Out Of Scope

Keep these out of this commit:

- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/MethodComparisonPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/e2e/method-comparison.mock.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/App.tsx`
- `/Users/jangseongjin/paperpipe/storage/method_comparisons/`
- docs RFC/implementation-plan files already archived and clean

## Behavior Covered

1. safer CSV export filename with `Content-Disposition`
2. slug resolution via normalized paper identifiers through shared note lookup
3. avoidance of non-paper note identifier collisions
4. repeatable fixture-backed saved artifact generation checks
5. stronger API response assertions for column order and source priority

## Verification Performed

1. `pytest -q`
   - `/Users/jangseongjin/paperpipe/tests/test_method_comparison_service.py`
   - `/Users/jangseongjin/paperpipe/tests/test_method_comparisons_api.py`
   - `/Users/jangseongjin/paperpipe/tests/test_method_comparison_fixture_hardening.py`
2. diff review to confirm no frontend/page dependency is required for this subset
3. fixture inventory check under `/Users/jangseongjin/paperpipe/tests/fixtures/method_comparison_case/`

## Safe Next Git Step

Stage only the paths listed in scope above and verify `git diff --cached --name-only` before commit.
