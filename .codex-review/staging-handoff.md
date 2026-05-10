# Staging Handoff

Recommended handling:
Do not create a mixed commit from the current index. The index currently contains 15 staged files from another lane, and this review/backfill lane has 9 unstaged/untracked files.

Current staged files from another lane:
- `backend/main.py`
- `backend/routers/paper_notes.py`
- `backend/services/job_runner.py`
- `frontend/src/app/lib/types.ts`
- `src/db_utils.py`
- `src/jobs/queue.py`
- `src/jobs/worker.py`
- `src/services/identity.py`
- `src/services/stale_jobs.py`
- `tests/test_db_utils_download_attempts.py`
- `tests/test_db_utils_sync_zotero_issue_state.py`
- `tests/test_frontend_api_contracts.py`
- `tests/test_paper_notes_api.py`
- `tests/test_stale_jobs_api.py`
- `tests/test_worker_heartbeat.py`

Review/backfill lane files:
- `.codex-review/conflicts.md`
- `.codex-review/disconnected-code.md`
- `.codex-review/findings.md`
- `.codex-review/flow-traces.md`
- `.codex-review/functional-wiring-map.md`
- `.codex-review/report.md`
- `.codex-review/staging-handoff.md`
- `scripts/backfill_operational_outputs.py`
- `tests/test_backfill_operational_outputs.py`

Latest checks for this lane:
- `git diff --check -- <review/backfill files>`: passed.
- `pytest -q tests/test_backfill_operational_outputs.py`: passed, `6 passed, 5 warnings in 2.72s`.
- `ruff check scripts/backfill_operational_outputs.py tests/test_backfill_operational_outputs.py --select F,E701,E9`: passed.

Current readiness snapshot:
- Existing staged files from another lane: 15.
- This lane: 8 tracked modified files plus this untracked handoff file.
- This lane diffstat excluding this handoff file: `8 files changed, 447 insertions(+), 155 deletions(-)`.
- No staged file currently overlaps this lane's 9 files.

Safe staging command for this lane after the existing index is cleared or committed:
Before running it, re-check `git diff --cached --name-status`; the staged set changed during this handoff more than once already.

```bash
git add \
  .codex-review/conflicts.md \
  .codex-review/disconnected-code.md \
  .codex-review/findings.md \
  .codex-review/flow-traces.md \
  .codex-review/functional-wiring-map.md \
  .codex-review/report.md \
  .codex-review/staging-handoff.md \
  scripts/backfill_operational_outputs.py \
  tests/test_backfill_operational_outputs.py
```
