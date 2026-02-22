# Pending PR Queue

## Recently Completed (Runtime)
- `PR-BE-JobContract-Hardening`
- `PR-BE-Queue-Claim-Atomic`
- `PR-QA-JobRunner-FailurePaths`
- `PR-QA-JobCancel-Transitions`
- `PR-BE-Worker-CancelSync`
- `PR-BE-Queue-Legacy-Recovery`
- `PR-BE-JobRunner-StageSplit`
- `PR-BE-Evidence-Contract-v1`
- `PR-BE-Citation-Jump-MVP`
- `PR-BE-RunProfile-v1`

## PR-DOC-Blueprint-v2
- Title: `docs(blueprint): review and promote pragmatic blueprint v2`
- Priority: Medium
- Purpose: Keep v2 blueprint adoption isolated from runtime changes and formally approve migration strategy.
- Source Draft: `docs/drafts/PaperPipe_v3_Pragmatic_Blueprint_v2_2026-02-22.md`
- Current Baseline: `docs/PaperPipe_v3_Pragmatic_Blueprint_2026-02-22.md`
- Scope (docs-only):
  - Compare v1/v2 sections and resolve policy conflicts.
  - Decide replacement strategy for baseline file.
  - Add migration note for post-v1 execution order.
- Merge Gate:
  - Docs-only PR (no runtime files).
  - Reviewer sign-off required (Antigravity + Codex).

## PR-BE-Discover-Queue-v1
- Title: `feat(discover): seed expansion queue + obsidian upsert`
- Priority: High
- Purpose: Implement blueprint PR-1 (OpenAlex backward/forward expansion, dedupe, queue persistence, related works upsert).
- Scope (expected):
  - `src/fetch/openalex.py`
  - `backend/*` or `src/*` queue orchestration modules
  - Obsidian upsert path for `Related Works (Queue)`
  - tests (unit + integration)
- Merge Gate:
  - Seed 1개 기준 5~10 related works generation.
  - dedupe/idempotent rerun.
  - `pytest -q` full suite green.

## PR-BE-Stats-Trigger-v1
- Title: `feat(stats): trigger mapping + cache hit contract`
- Priority: High
- Purpose: Implement blueprint PR-4 (`run_verify` + tag/action trigger + cache/concurrency contract).
- Scope (expected):
  - `backend/services/job_runner.py`
  - `src/jobs/*`
  - stats cache utility module (new if needed)
  - tests for trigger/cached-skip paths
- Merge Gate:
  - stats only executes on trigger.
  - repeated request hits cache (`stats_cache_hit` observable).
  - `pytest -q` full suite green.

## PR-BE-V2-Identity-EventLog (Deferred)
- Title: `feat(core): paper_key identity + event log tables`
- Priority: Medium
- Purpose: v2-only migration (`paper_key`, `runs/jobs/job_events/user_actions`) after docs approval.
- Merge Gate:
  - No adoption before `PR-DOC-Blueprint-v2` approval.
