# Memory-Ready Hardening Staging Prep

Status: Staging-prep manifest  
Date: 2026-03-18  
Owner: Repository maintainers  
Canonical parents:
- `/Users/jangseongjin/paperpipe/docs/reports/Memory_Ready_Hardening_Baseline_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Current_Baseline_Recheck_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Safe_Worktree_Cleanup_Guardrails_2026-03-18.md`

## Purpose

Define the exact dirty-file subset that belongs to the memory-ready hardening lane after the safe cleanup pass.

This is not a commit plan for the entire repository.

It is a narrow staging-prep note so the next `git add` step does not accidentally absorb unrelated feature or archive work.

## Guardrail

Only stage files that are both:

1. listed in the memory-ready hardening baseline
2. currently dirty in the worktree

Do not stage files only because they are nearby in the tree.

## A. Dirty Files That Belong To This Lane

### A1. Runtime/backend

Tracked modifications:

- `/Users/jangseongjin/paperpipe/backend/main.py`
- `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`
- `/Users/jangseongjin/paperpipe/src/agents/indexer_agent.py`
- `/Users/jangseongjin/paperpipe/src/agents/reader_agent.py`
- `/Users/jangseongjin/paperpipe/src/contracts/artifact_views.py`
- `/Users/jangseongjin/paperpipe/src/db.py`
- `/Users/jangseongjin/paperpipe/src/db_utils.py`
- `/Users/jangseongjin/paperpipe/src/exporter.py`
- `/Users/jangseongjin/paperpipe/src/jobs/worker.py`
- `/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py`
- `/Users/jangseongjin/paperpipe/src/schemas/ops.py`
- `/Users/jangseongjin/paperpipe/src/services/event_log.py`

Untracked additions:

- `/Users/jangseongjin/paperpipe/src/services/citation_grounding.py`
- `/Users/jangseongjin/paperpipe/src/quality/teacher_review.py`
- `/Users/jangseongjin/paperpipe/src/quality/claimset_policy.py`
- `/Users/jangseongjin/paperpipe/src/verify/__init__.py`

### A2. Frontend/workbench

Tracked modifications:

- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ArtifactPanel.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/Rail.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/StatusChip.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/TerminalDrawer.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/TimelinePanel.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/api.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/mock.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/sse.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/types.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/store/useAppStore.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/mock.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_e2e.sh`

Untracked additions:

- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ContentReviewSummary.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/OperationalStateBadge.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/OperationalStateSummary.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/PanelErrorBoundary.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/StatusBadge.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ui/badge.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ui/button.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ui/card.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ui/separator.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ui/sheet.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/cn.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/contentReview.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/paperNoteOps.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/statusSystem.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx`

### A3. Tests

Tracked modifications:

- `/Users/jangseongjin/paperpipe/tests/test_api_key_auth.py`
- `/Users/jangseongjin/paperpipe/tests/test_event_log_db.py`

Untracked additions:

- `/Users/jangseongjin/paperpipe/tests/test_citation_grounding.py`
- `/Users/jangseongjin/paperpipe/tests/test_indexer_agent_chunk_ids.py`
- `/Users/jangseongjin/paperpipe/tests/test_reader_agent_reliability.py`

### A4. Baseline and UX docs

Tracked modifications:

- `/Users/jangseongjin/paperpipe/docs/reports/Current_Baseline_Recheck_2026-03-18.md`

Untracked additions:

- `/Users/jangseongjin/paperpipe/docs/reports/Memory_Ready_Hardening_Baseline_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Safe_Worktree_Cleanup_Guardrails_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_paper-notes-viewer.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_TEMPLATE.md`

## B. Baseline Files That Are Part Of The Lane But Are Not Dirty Right Now

These exist in the lane definition but do not currently appear as dirty in `git status`:

- `/Users/jangseongjin/paperpipe/src/services/identity.py`
- `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`
- `/Users/jangseongjin/paperpipe/src/services/paper_ops_summary.py`
- `/Users/jangseongjin/paperpipe/src/services/stats_repair.py`
- `/Users/jangseongjin/paperpipe/src/jobs/queue.py`
- `/Users/jangseongjin/paperpipe/src/jobs/schemas.py`
- `/Users/jangseongjin/paperpipe/backend/routers/obsidian.py`
- `/Users/jangseongjin/paperpipe/src/skills/runner.py`
- `/Users/jangseongjin/paperpipe/src/contracts/output_bridge.py`
- `/Users/jangseongjin/paperpipe/src/schemas/skills.py`

Do not force-touch or restage these just to make the manifest look complete.

## C. Closure Note

The first narrow allowlist was not yet commit-safe by itself.

These additional files are included here because staged memory-ready files import them directly and a partial commit without them would not survive a clean-checkout verification pass.

## D. Explicitly Exclude From This Lane

Even if they are dirty, do not stage them as part of the memory-ready hardening bundle:

- `/Users/jangseongjin/paperpipe/backend/routers/method_comparisons.py`
- `/Users/jangseongjin/paperpipe/src/method_comparisons/service.py`
- `/Users/jangseongjin/paperpipe/tests/test_method_comparison_service.py`
- `/Users/jangseongjin/paperpipe/tests/test_method_comparisons_api.py`
- `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`
- broad `docs/archive/` additions
- `Research DNA` runtime or evaluation lanes
- visual snapshot churn outside the timeline/user-action workbench checks

## E. Safe Next Git Step

If staging is done later, use this manifest as the allowlist and stage only these paths in grouped passes:

1. backend/runtime
2. frontend/workbench
3. tests
4. baseline docs

Stop after each pass and inspect `git diff --cached --name-only`.

## F. Why This Is The Right Next Step

The safe cleanup pass already removed obvious local/generated noise.

What remains in the dirty tree is mostly real work.

That means the next risk is no longer temporary file noise; it is accidental cross-lane staging.

This manifest addresses that risk without changing code or deleting additional files.
