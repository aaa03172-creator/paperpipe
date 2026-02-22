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
- `PR-BE-Discover-Queue-v1`
- `PR-BE-Stats-Trigger-v1`
- `PR-BE-Observability-Rollup`
- `PR-BE-V2-Identity-EventLog`
- `PR-BE-EventWriter-Buffered`

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

## PR-BE-V2-Identity-EventLog (Deferred)
- Title: `feat(core): paper_key identity + event log tables`
- Priority: Medium
- Purpose: v2-only migration (`paper_key`, `runs/jobs/job_events/user_actions`) after docs approval.
- Merge Gate:
  - Runtime bootstrap includes paper_key backfill and event tables.
  - Worker lifecycle emits event logs without breaking fail-safe path.
  - `pytest -q` full suite green.

## PR-BE-ArtifactPath-PaperKey
- Title: `refactor(artifacts): migrate path key from paper_id to paper_key`
- Priority: Medium
- Purpose: Align artifact storage with deterministic filesystem-safe identity.
- Scope (expected):
  - `backend/services/job_runner.py`
  - path resolver helpers + backward compatibility lookup
  - tests for legacy artifact path fallback
- Merge Gate:
  - Existing artifact lookup remains compatible.
  - New runs write under `{paper_key}/{run_id}`.
