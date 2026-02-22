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

## PR-BE-Observability-Rollup
- Title: `feat(obs): expose grounded ratio + stats cache rollup metrics`
- Priority: High
- Purpose: Surface runtime quality counters for operations dashboard without changing core execution semantics.
- Scope (expected):
  - `backend/main.py` (or dedicated metrics route)
  - QA/report scripts
  - tests for metric calculation and API response
- Merge Gate:
  - `evidence_grounded_ratio` and stats cache-hit rollup are queryable.
  - `pytest -q` full suite green.

## PR-BE-V2-Identity-EventLog (Deferred)
- Title: `feat(core): paper_key identity + event log tables`
- Priority: Medium
- Purpose: v2-only migration (`paper_key`, `runs/jobs/job_events/user_actions`) after docs approval.
- Merge Gate:
  - No adoption before `PR-DOC-Blueprint-v2` approval.
