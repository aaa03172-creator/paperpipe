# Worktree Lane Separation

Purpose:
Separate the current mixed dirty worktree into review/staging lanes without reverting unrelated work. This is a handoff map, not a commit record.

## Current Staging State

There are already staged changes in the index. They are not part of the D4 helper extraction lane and should be reviewed before any commit is made:

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

Suggested action:
Do not commit from the current index as-is. Either intentionally keep these as a separate staged lane, or unstage and re-stage by lane with `git restore --staged <path>` and targeted `git add <path>` commands.

## Lane A: Dead-Code Audit Artifacts

Files:

- `.codex-review/dead-code-audit/code-inventory.md`
- `.codex-review/dead-code-audit/unused-code.md`
- `.codex-review/dead-code-audit/unreachable-code.md`
- `.codex-review/dead-code-audit/duplicate-logic.md`
- `.codex-review/dead-code-audit/obsolete-legacy-code.md`
- `.codex-review/dead-code-audit/removal-risk-matrix.md`
- `.codex-review/dead-code-audit/cleanup-plan.md`
- `.codex-review/dead-code-audit/report.md`
- `.codex-review/dead-code-audit/d4-store-differences.md`
- `.codex-review/dead-code-audit/worktree-lanes.md`

Suggested commit shape:
Docs/review artifact only.

Verification:

```sh
git diff --check -- .codex-review/dead-code-audit
```

## Lane B: D4 Simple Text Transaction Helper

Files:

- `src/services/artifact_transactions.py`
- `src/meeting_packs/store.py`
- `src/method_comparisons/store.py`
- `src/paper_syntheses/store.py`
- `src/project_memory/store.py`
- `tests/test_meeting_pack_store.py`
- `tests/test_method_comparison_store.py`
- `tests/test_paper_synthesis_store.py`
- `tests/test_project_memory_store.py`
- `tests/test_protocol_attachment_store.py`

Suggested commit shape:
One production helper extraction plus focused rollback-preservation tests. Keep managed stale-file stores out of this lane.

Verification:

```sh
python3 -m py_compile src/services/artifact_transactions.py src/meeting_packs/store.py src/method_comparisons/store.py src/paper_syntheses/store.py src/project_memory/store.py
.venv/bin/python -m pytest -q tests/test_meeting_pack_store.py tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_project_memory_store.py
.venv/bin/python -m pytest -q tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_image_evidence_store.py tests/test_talk_pack_store.py tests/test_chart_pack_store.py tests/test_meeting_pack_store.py tests/test_protocol_card_store.py tests/test_project_memory_store.py tests/test_protocol_attachment_store.py
```

Last result:
`py_compile` passed; simple text tests passed with `28 passed`; full D4 gate passed with `64 passed`.

## Lane C: Previously Completed Dead-Code Cleanup

Files likely in this lane include:

- Deleted `src/test_download.py`
- Deleted root probe scripts: `inspect_*.py`, `copy_case.py`
- Deleted tracked MagicMock Chroma artifacts
- `src/db.py`
- `src/db_utils.py`
- `src/fetchers.py`
- `src/fetch/arxiv.py`
- `frontend/src/app/lib/ui.ts`
- `frontend/src/app/lib/types.ts`
- `frontend/src/app/lib/paperNoteOps.ts`

Suggested action:
Stage separately from D4 helper extraction. Re-run the specific cleanup verification noted in `report.md` before committing.

## Lane D: Duplicate-Logic Follow-Up Refactors

Files likely in this lane include:

- `backend/main.py`
- `backend/routers/obsidian.py`
- `backend/routers/paper_notes.py`
- `src/services/identity.py`
- `frontend/src/app/lib/api.ts`
- `frontend/src/app/lib/mock.ts`
- `frontend/src/app/lib/paperNoteOps.ts`
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `tests/test_identity_helpers.py`
- `tests/test_paper_notes_api.py`
- `tests/test_browser_request_audit_api.py`
- `tests/test_paper_ops_summary.py`

Suggested action:
Keep D1/D2/D3/D5 follow-ups separate from Lane B unless a specific test or helper crosses the boundary.

## Lane E: Other Dirty Work Not Owned By This Audit Lane

Examples visible in the current worktree:

- Existing `.codex-review/*.md` review packet files outside `dead-code-audit/`
- UI reference docs and UX reports
- Frontend E2E snapshots
- Worker/job/stale-job changes
- Backfill/vector-index rebuild scripts and tests
- Broad backend/router/service changes not tied to D4

Suggested action:
Do not stage with dead-code audit or D4 helper work until each lane has its own verification record.

## Practical Next Step

For the next cleanup/staging pass, review the existing staged index first:

```sh
git diff --cached --name-status
```

Then choose one lane and stage only that lane. Avoid committing from the current mixed index.
