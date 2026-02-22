# Pending PR Queue

## PR-DOC-Blueprint-v2
- Title: `docs(blueprint): review and promote pragmatic blueprint v2`
- Priority: Medium
- Purpose: Keep the proposed v2 blueprint isolated from active runtime refactors.
- Source Draft: `docs/drafts/PaperPipe_v3_Pragmatic_Blueprint_v2_2026-02-22.md`
- Current Baseline (kept on main flow): `docs/PaperPipe_v3_Pragmatic_Blueprint_2026-02-22.md`
- Scope (docs-only):
  - Compare v1/v2 sections and resolve policy conflicts.
  - Decide replacement strategy for the baseline file.
  - Add a short migration note for changed PR sequencing.
- Merge Gate:
  - No runtime code changes in the PR.
  - Reviewer sign-off required (Antigravity + Codex).

## PR-BE-JobContract-Hardening
- Title: `fix(api-jobs): persist clean_reindex and harden startup/db paths`
- Priority: High
- Purpose: Remove API contract drift (`clean_reindex` dropped) and harden startup behavior in empty/new DB environments.
- Scope:
  - `backend/main.py`
  - `src/db_bootstrap.py`
  - `src/jobs/queue.py`
  - `src/jobs/schemas.py`
  - `tests/test_jobs_api_smoke.py`
  - `tests/test_papers_api.py`
- Merge Gate:
  - `pytest -q` must remain green.
  - `/jobs/deepread` must persist `clean_reindex` in `/jobs/{id}` payload.

## PR-BE-Queue-Claim-Atomic
- Title: `fix(jobs): make claim_next_job transactional and add queue claim tests`
- Priority: High
- Purpose: Prevent duplicate claim windows under parallel worker polling.
- Scope:
  - `src/jobs/queue.py`
  - `tests/test_jobs_queue_claim_next.py`
- Merge Gate:
  - `tests/test_jobs_queue_claim_next.py` passes.
  - `pytest -q` full suite passes.
