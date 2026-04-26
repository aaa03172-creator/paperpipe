# Queue Lease And Reclaim RFC

Status: Partially implemented
Date: 2026-04-22
Owner: Runtime/queue maintainers
Type: Bounded RFC
Related:
- `docs/STALE_RUNNING_RECOVERY.md`
- `docs/reports/PaperPipe_Current_Runtime_Review_2026-04-22.md`
- `src/jobs/queue.py`
- `src/jobs/worker.py`

## Purpose

Define the smallest safe next step for stale `running` job recovery without rewriting the current SQLite queue or silently changing operator-visible job semantics.

This RFC does not adopt a runtime change by itself.

Note:

- the original Phase A heartbeat foundation proposed here has now landed in the current branch
- the original Phase B manual reclaim path proposed here has now landed in the current branch
- the explicit fresh re-enqueue follow-up proposed here has now landed in the current branch
- this RFC now serves as the bounded design note for any remaining reclaim follow-up

## Current Baseline

Current runtime facts:

- jobs are persisted in SQLite
- `claim_next_job()` moves the oldest `queued` row to `running`
- `claim_next_job()` initializes `heartbeat_at`
- the worker updates `heartbeat_at` periodically while a job remains `running`
- `POST /jobs/deepread` rejects a second open job for the same `paper_id`
- `POST /jobs/{job_id}/cancel` can move `queued|running` to `cancelled`
- `GET /ops/stale-jobs` surfaces stale `running` candidates using `COALESCE(heartbeat_at, started_at, created_at)`
- `/health/ready` exposes `queue_health`

Current gap:

- a worker crash can leave a `running` row behind
- stale rows now have a bounded reclaim path, but the operator still has to invoke it explicitly
- reclaim visibility is still split across stale-job diagnostics, job status, and run timeline surfaces

Current safe recovery:

- inspect stale candidate surfaces
- reclaim stale running rows through the bounded ops endpoint
- explicitly enqueue a fresh replacement run, either through the standard deep-read enqueue endpoint or the reclaimed-job replacement helper

That baseline is now documented in `docs/STALE_RUNNING_RECOVERY.md`.

## Problem To Solve

We want a reclaim path that:

- clears abandoned `running` rows more safely than direct DB edits
- preserves current FastAPI-first and job-event-first boundaries
- does not overload `cancelled` semantics
- does not silently mark live work dead just because one stage is long-running

## Non-Goals

- no Redis/Celery migration in this RFC
- no multi-worker distributed ownership protocol
- no new end-user UI workflow
- no hidden auto-reclaim in the first reclaim patch
- no new public top-level job status unless forced by evidence later

## Design Constraints

Any adopted reclaim design should preserve these current contracts:

- open-job exclusion still keys off `queued|running`
- `cancelled` keeps meaning operator-requested cooperative stop
- partial artifacts and logs remain inspectable
- reclaim actions must leave a durable audit trail in job events and execution runs

## Rejected Shortcuts

### 1. Mutate stale `running` rows directly in SQLite

Reject.

Reason:

- bypasses audit surfaces
- easy to do inconsistently
- teaches operators to edit state outside the API boundary

### 2. Reuse `cancelled` for stale reclaim

Reject.

Reason:

- `cancelled` currently means operator-requested stop on an open job
- reclaim is a post-hoc abnormal-runtime diagnosis, not cooperative cancellation
- overloading `cancelled` would blur incident analysis

### 3. Add auto-reclaim before heartbeat exists

Reject.

Reason:

- current stale detection is duration-based suspicion only
- long-running quiet stages would be at risk of false reclaim

## Recommended Sequence

### Phase 0. Keep current diagnostics and manual recovery

Already in place:

- `GET /ops/stale-jobs`
- `queue_health`
- `docs/STALE_RUNNING_RECOVERY.md`

This remains the baseline until a stronger truth source exists.

### Phase 1. Add heartbeat-backed running freshness

Recommended smallest runtime addition:

- add `heartbeat_at` to `jobs`

Worker behavior:

- set `heartbeat_at` periodically while a job is actively owned by the worker
- do not rely only on progress callbacks for freshness
- use a dedicated periodic heartbeat so quiet stages do not look abandoned

Staleness rule after adoption:

- stale anchor becomes `COALESCE(heartbeat_at, started_at, created_at)`

Why only `heartbeat_at` first:

- `started_at` already acts as claim time today
- provenance for reclaim can use existing `job_events`, `error_code`, `error_message`, and `finished_at`
- this keeps schema drift small

Current status:

- implemented

### Phase 2. Add operator-triggered reclaim endpoint

Recommended first reclaim mutation:

- add a bounded ops endpoint such as `POST /ops/jobs/{job_id}/reclaim-stale`

Guard conditions:

- job must still be `running`
- job must be stale by the configured threshold
- reclaim remains operator-triggered only in the first patch

Recommended mutation:

- set `status = "failed"`
- set `finished_at = now`
- set `error_code = "STALE_RUNNING_RECLAIMED"`
- set `error_message` to a compact operator-readable explanation
- increment a reclaim counter if such a field exists later
- append a dedicated `job_reclaimed_stale_running` event
- mirror the terminal failure into `execution_runs`

Why `failed`, not `cancelled`:

- reclaim means the runtime concluded the execution was abandoned or no longer trustworthy
- this is closer to abnormal termination than cooperative stop

### Phase 3. Re-enqueue remains explicit

Even after manual reclaim lands:

- the operator should still start a fresh run explicitly
- reclaim should not auto-spawn a replacement run in the first version
- `POST /ops/jobs/{job_id}/requeue-reclaimed` is now the bounded helper for this explicit replacement step
- `POST /ops/jobs/{job_id}/stale-incident-snapshot` is the bounded helper for preserving pre-mutation incident evidence
- `GET /ops/stale-incidents` is the bounded read surface for reviewing accumulated snapshot summaries
- `scripts/capture_stale_incident_snapshots.py` is the direct local sweep for capturing all current stale candidates without reclaiming them
- `scripts/check_stale_reclaim_readiness.py` is the non-mutating gate for deciding whether accumulated evidence is ready for human false-positive review

Reason:

- it keeps diagnosis and re-execution separate
- it avoids retry storms on a bad local runtime
- it gives future false-positive analysis a concrete support artifact without promoting that artifact to canonical state
- it lets operators count and inspect incident examples before deciding whether auto-reclaim is justified
- it prevents a metrics-only check from being mistaken for permission to enable auto-reclaim

### Phase 4. Revisit auto-reclaim only after manual reclaim proves stable

Auto-reclaim should be deferred until all of the following are true:

- heartbeat-based freshness exists
- manual reclaim has proven low-risk in local operator use
- reclaim audit trails are visible in ops surfaces
- false-positive analysis is available from real incidents
- stale incident snapshots have enough real examples to distinguish worker death from long but healthy work

If auto-reclaim is adopted later, it should start as a bounded janitor path, not as an unconditional inline mutation inside `claim_next_job()`.

## Recommended Defaults

These are proposal defaults, not current runtime behavior:

- heartbeat interval: 30 seconds
- stale diagnostic threshold: 900 seconds
- manual reclaim threshold: 900 seconds at first, because that already matches the current operator diagnostic lane
- auto-reclaim threshold: not adopted yet

## Open Questions

### 1. Should reclaim add a dedicated counter field immediately

My recommendation:

- not in the first patch unless repeated reclaim history becomes operationally important

### 2. Should queued jobs ever be reclaimed automatically

My recommendation:

- no
- queued age should remain a warning signal, not a destructive path

### 3. Should worker identity or PID be tracked

My recommendation:

- maybe later
- useful for stronger local liveness checks, but not required for the first heartbeat-backed manual reclaim patch

## Proposed PR Breakdown

### PR A. Heartbeat foundation

Scope:

- add `heartbeat_at`
- write periodic heartbeats from the worker
- teach stale diagnostics to prefer heartbeat freshness

Status:

- implemented

### PR B. Manual stale reclaim

Scope:

- add reclaim endpoint
- mark reclaimed jobs as `failed`
- emit reclaim event and execution-run update
- add targeted tests for guard conditions and terminal mutation

Status:

- implemented

### PR C. Ops polish

Scope:

- surface reclaim metadata in stale-job diagnostics and queue health summaries
- add an explicit replacement enqueue helper for reclaimed stale-running failures
- link recent reclaim summaries to replacement job/run identifiers after explicit requeue
- surface aggregate replacement counts and last replacement time in queue-health metadata
- optionally add a runbook addendum for reclaim-specific operator steps

Status:

- implemented for reclaim metadata, explicit replacement enqueue, recent reclaim-to-replacement linkage, and aggregate replacement visibility

## Decision

Recommended next implementation is:

1. later ops polish around reclaim visibility
2. defer any auto-reclaim decision until local incident evidence exists

Recommended non-decision for now is:

- no silent auto-reclaim
- no broker migration
- no new top-level job status

## Verification Anchors

Current code and docs this RFC is grounded on:

- `src/jobs/queue.py`
- `src/jobs/worker.py`
- `backend/main.py`
- `docs/STALE_RUNNING_RECOVERY.md`
- `tests/test_stale_jobs_api.py`
- `tests/test_runtime_readiness_external_roots.py`
