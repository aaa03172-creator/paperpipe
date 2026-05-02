# Deep Read Rerun Integrity Check (2026-03-27)

Status: Active release evidence note
Date: 2026-03-27
Owner: Runtime/product maintainers
Canonical parents:
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md`

## Purpose

Run one bounded representative rerun after canonical note-side state already exists and check a narrower question:

- does a fresh deep-read rerun silently corrupt the current saved state or artifact lineage?

This is not:
- a new feature lane
- a broad multi-paper rerun campaign
- a new truth-policy proposal

## Representative Target

- `paper_id = zotero:coricTargetingProdromalAlzheimer2015`
- `slug = zoterocoricTargetingProdromalAlzheimer2015`

Why this paper:
- it is the current representative paper already used in the fresh successful rerun note
- it already had canonical note-side state before this pass
- it is already part of the bounded release/demo slice

## Integrity Criteria

For this pass, integrity meant:
- canonical `.pp/<slug>/state.json` still exists after rerun
- top run id in the sidecar updates to the new run
- `/papers/{paper_id}` and `/paper-notes/{slug}` still open and point at the new run
- previous artifact run directories are preserved
- artifact run count increases by exactly one
- note markdown does not duplicate the Deep Read section

## Method

Execution path:
1. inspect pre-rerun state through `TestClient`, SQLite, and local filesystem
2. enqueue one fresh job with `JobQueue.enqueue(...)`
3. claim and run it through `Worker.process_job(...)`
4. inspect post-rerun state using the same checks

Representative command shape:

```bash
python3 - <<'PY'
from src.jobs.queue import JobQueue
from src.jobs.worker import Worker

queue = JobQueue()
job_id = queue.enqueue(
    paper_id="zotero:coricTargetingProdromalAlzheimer2015",
    clean_reindex=False,
    run_verify=False,
    persona_id="default",
)
claimed = queue.claim_next_job()
Worker().process_job(claimed)
PY
```

## Pre-Run State

- canonical sidecar existed:
  - `/Users/jangseongjin/Documents/Obsidian/MyVault/.pp/zoterocoricTargetingProdromalAlzheimer2015/state.json`
- pre-rerun state hash:
  - `805135bdf6fdd23c07ed91ff3dbfc643501f7529`
- top run id in sidecar:
  - `run_20260324_143902`
- `/papers/{paper_id}` top-level `latest_run_id`:
  - `run_20260324_143902`
- existing artifact run dirs:
  - `run_20260223_134233`
  - `run_20260324_032707`
  - `run_20260324_143902`

## Rerun Result

Fresh rerun job:
- `job_id = b32581f7-a0f8-4124-a0c0-532eac559f53`
- `run_id = run_20260327_022030`
- terminal status = `completed`

Observed runtime facts:
- reader completed successfully on attempt `1`
- canonical sidecar still existed after rerun
- post-rerun state hash changed to:
  - `0869a54c2b599308cc160a9c87a3e2cac5da0f73`
- sidecar `updated_at` advanced to:
  - `2026-03-27T02:22:41.690724+00:00`
- sidecar top run id changed to:
  - `run_20260327_022030`
- `/papers/{paper_id}` top-level `latest_run_id` changed to:
  - `run_20260327_022030`
- `/paper-notes/{slug}` still surfaced `structured_state`
- note markdown still contained exactly one `## 🤖 Agent Deep Read` section
- a new artifact run directory was added:
  - `run_20260327_022030`

## Integrity Judgment

### Passed

- canonical note-side state was not lost
- API surfaces remained healthy and pointed at the new run
- prior artifact lineage was preserved
- no duplicate Deep Read section appeared in the note markdown
- the rerun produced one new artifact run instead of overwriting the older saved bundles silently

### Important nuance

The rerun changed the projected sidecar content:
- claim count moved from `4` to `3`

That is **not** treated as corruption by itself in this pass because:
- the new run completed successfully
- prior artifact runs remain inspectable
- the canonical sidecar is expected to represent the latest successful projection, not a historical append log

## Practical Consequence

This closes the narrower release question:

- the representative deep-read rerun path now looks non-destructive enough for the bounded launch slice

It does **not** prove:
- multi-paper rerun stability across all historical bundles
- that every rerun preserves identical claim counts
- that citation grounding is fully verified

## Verification Used

- SQLite inspection of `jobs`
- FastAPI `TestClient` requests against:
  - `/paper-notes/resolve-by-paper-id`
  - `/paper-notes/{slug}`
  - `/papers/{paper_id}`
- direct filesystem checks for:
  - canonical `.pp/<slug>/state.json`
  - `storage/artifacts/<paper_id>/run_*`
  - note markdown duplication

## Conclusion

Current best judgment:
- the representative deep-read rerun path is now credible enough to narrow the remaining launch risk
- Meeting Pack regenerate/rollback was already strong
- this new evidence means the release-facing rerun/regenerate integrity question is no longer waiting on an unproven deep-read rerun path
