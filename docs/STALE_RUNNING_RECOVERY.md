# Lattice Stale Running Recovery

Status: Active
Date: 2026-04-23
Owner: Runtime/ops maintainers
Canonical runbook: `docs/STALE_RUNNING_RECOVERY.md`
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Purpose

Use this runbook when a PaperPipe job appears to be stuck in `running` long enough that the operator suspects a worker crash, local stall, or abandoned process.

This runbook is intentionally narrow:

- it explains the current single-node SQLite queue behavior
- it uses the existing diagnostics and reclaim surfaces
- it defines a safe manual recovery path

This runbook does not define lease expiry or automatic reclaim.

The current runtime now records a best-effort local `heartbeat_at` for `running` jobs, but reclaim is still diagnostics-first and operator-triggered.

## Current Runtime Semantics

As of 2026-04-23, the runtime exposes these bounded operator signals:

- `GET /health/ready`
  - includes `queue_health`
  - `queue_health` warns when either:
    - `stale_running_suspected_total > 0`
    - `oldest_queued_age_seconds >= 900`
- `GET /ops/stale-jobs`
  - defaults to `stale_after_seconds=900`
  - returns stale candidates where:
    - `jobs.status == "running"`
    - `COALESCE(heartbeat_at, started_at, created_at)` is older than the requested threshold
- `POST /ops/jobs/{job_id}/stale-incident-snapshot`
  - writes a bounded local support artifact under `storage/stale_running_incidents/`
  - captures job/run metadata, recent job events, and log/artifact path observations
  - does not copy PDF, log, or artifact contents
  - does not mutate canonical job/run status
- `GET /ops/stale-incidents`
  - lists local stale-running incident snapshot summaries
  - returns support-artifact metadata only, not embedded run params or event payload bodies
- `POST /ops/jobs/{job_id}/reclaim-stale`
  - only succeeds when the target job is still `running`
  - only succeeds when the current heartbeat-backed anchor is older than the requested threshold
  - marks the job `failed`
  - writes `error_code = "STALE_RUNNING_RECLAIMED"`
  - appends a `job_reclaimed_stale_running` event and mirrors terminal failure into `execution_runs`
- `POST /ops/jobs/{job_id}/requeue-reclaimed`
  - only succeeds for a terminal `failed` job that was reclaimed from stale `running`
  - enqueues a fresh replacement job for the same `paper_id`
  - preserves the original persona/profile flags and requested parser backend where available
  - appends link events on the original and replacement jobs

Important boundary:

- a stale candidate is an operator warning, not a heartbeat-backed proof that the worker is dead
- the runtime does not auto-reclaim stale `running` rows
- a `paper_id` with an open `queued` or `running` job cannot be enqueued again until that open job leaves the open set
- requeue is explicit and operator-triggered; reclaim does not silently start a replacement run

## Typical Symptoms

- `/health/ready` or `/api/health/ready` reports `queue_health.status == "warn"`
- `queue_health.metadata.stale_running_suspected_total > 0`
- `queue_health.metadata.oldest_queued_age_seconds` keeps increasing
- `GET /ops/stale-jobs` returns one or more `stale_jobs`
- a re-run for the same `paper_id` is blocked by an existing open job

## Check Path

If `LATTICE_API_KEY` is set, use a same-origin browser `/api/*` request or provide `X-API-Key` for direct backend calls.

### 1. Confirm the queue-level warning

- `GET /health/ready`
- browser-safe path: `GET /api/health/ready`

Look at:

- `queue_health.status`
- `queue_health.metadata.queued_jobs_total`
- `queue_health.metadata.running_jobs_total`
- `queue_health.metadata.oldest_queued_age_seconds`
- `queue_health.metadata.stale_running_suspected_total`
- `queue_health.metadata.stale_running_reclaimed_total`
- `queue_health.metadata.last_stale_running_reclaimed_at`
- `queue_health.metadata.stale_running_requeued_total`
- `queue_health.metadata.last_stale_running_requeued_at`
- `queue_health.metadata.recent_stale_running_reclaims`
  - detailed/internal responses include replacement `job_id` / `run_id` when a reclaimed job has already been explicitly requeued

### 2. Identify the stale-running candidates

- `GET /ops/stale-jobs?stale_after_seconds=900&limit=50`

Capture:

- `job_id`
- `paper_id`
- `run_id`
- `running_for_seconds`
- `recommended_action`
- whether `log_exists` or `artifact_dir_exists` is `true`
- top-level reclaim summary:
  - `stale_running_reclaimed_total`
  - `last_stale_running_reclaimed_at`
  - `stale_running_requeued_total`
  - `last_stale_running_requeued_at`
  - `recent_stale_running_reclaims`
    - includes `replacement_job_id`, `replacement_run_id`, and `requeued_at` after `POST /ops/jobs/{job_id}/requeue-reclaimed`

### 3. Inspect the bounded job/run surfaces before mutating state

- `GET /jobs/{job_id}`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/timeline`
- `GET /jobs/{job_id}/events`
- `POST /ops/jobs/{job_id}/stale-incident-snapshot`

Use these to answer:

- is progress still changing
- is the run timeline still receiving new events
- when was the last recorded heartbeat
- does the runtime still know where artifacts/logs live
- is there a preserved local evidence snapshot before any reclaim/requeue mutation

If `GET /jobs/{job_id}` shows `log_path` or `artifact_dir`, inspect those local files before recovery when that is safe in your environment. If path masking is enabled, prefer the timeline and events surfaces first.

The incident snapshot endpoint returns an `incident_path` pointing at a local JSON file. Treat that file as a review/support artifact, not source data and not canonical state. It is intended for later false-positive analysis and post-incident review.

To see accumulated stale-running evidence later:

- `GET /ops/stale-incidents?limit=50`

This listing is for operator review and trend gathering. It summarizes each local `incident.json` but does not replace the underlying snapshot file.

For direct local collection without opening the API, run:

- `.venv314/bin/python scripts/capture_stale_incident_snapshots.py --stale-after-seconds 900 --limit 50`

Use `--dry-run` to list candidates without writing snapshot files or job events. The script only captures current stale-running candidates; it does not reclaim, requeue, or edit canonical job status.

To summarize whether the accumulated evidence is ready for human false-positive review, run:

- `.venv314/bin/python scripts/check_stale_reclaim_readiness.py --stale-after-seconds 900 --limit 500`

This readiness gate never enables or runs auto-reclaim. Even when enough clean incidents exist, the highest result is `manual_review_ready`; an automatic reclaim path still requires a separate RFC and explicit implementation.

## Safe Manual Recovery

### 1. Do not edit the SQLite DB directly

The current supported recovery move is API-level reclaim, not manual row mutation.

### 2. Treat "stale" as suspicion first

If timeline events are still arriving, progress is still changing, or artifacts are still being written, do not reclaim yet. Long-running work can cross the stale threshold without being dead.

### 3. Reclaim only after the operator concludes the job is no longer making progress

- `POST /ops/jobs/{job_id}/reclaim-stale`

Current behavior:

- only stale `running` jobs can be reclaimed
- the job becomes `failed`
- `finished_at` is set
- `error_code` becomes `STALE_RUNNING_RECLAIMED`
- a `job_reclaimed_stale_running` event is recorded
- the matching `execution_runs` row is moved to `failed`
- existing artifacts or logs are not deleted by this API path

Related boundary:

- `POST /jobs/{job_id}/cancel` still exists for operator-requested cooperative stop on `queued|running`
- do not use `cancel` to mean post-hoc stale reclaim

### 4. Confirm the open-job lock is cleared

Re-check:

- `GET /jobs/{job_id}`
- `GET /health/ready`
- optionally `GET /ops/stale-jobs`

Expected result:

- the reclaimed job is no longer part of the open `queued`/`running` set
- the `paper_id` is eligible for an explicit re-run again

### 5. Re-run explicitly

Use either the standard enqueue path:

- `POST /jobs/deepread`

Or, when the old row was reclaimed with `STALE_RUNNING_RECLAIMED`, use the bounded replacement helper:

- `POST /ops/jobs/{job_id}/requeue-reclaimed`

The replacement helper copies the reclaimed job's `paper_id`, persona/profile flags, verification flags, clean-reindex flag, and requested parser backend where those values are still available. It still creates a new queued `job_id` / `run_id`; it does not resume the old row in place.

### 6. Watch the replacement run, not the cancelled row

After the new enqueue returns a new `job_id` / `run_id`, inspect:

- `GET /jobs/{job_id}`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/timeline`

## When To Stop And Escalate

Do not loop manual cancel-and-rerun indefinitely.

Escalate to runtime investigation when:

- the same paper stalls twice in a row
- multiple unrelated papers become stale at the same time
- queued age keeps growing even after cancellation
- the replacement run never reaches `running`
- the timeline is silent and there are no new job events across the queue

At that point, the likely problem is runtime/process health, not a single paper row.

## What This Runbook Does Not Promise

- automatic reclaim of stale `running` rows
- lease expiry semantics
- artifact cleanup or rollback
- multi-worker or distributed queue coordination

Any future auto-reclaim PR must explicitly update this runbook instead of silently changing these semantics.

## Verification Anchors

Current baseline coverage for this runbook's semantics:

- `tests/test_stale_jobs_api.py`
  - stale `running` candidate is surfaced by `GET /ops/stale-jobs`
  - stale incident snapshot writes a bounded local support artifact before mutation
  - stale reclaim marks the job failed and rejects a fresh-heartbeat candidate
  - explicit requeue creates a fresh replacement only for reclaimed stale-running failures
- `tests/test_api_key_auth.py`
  - protected `/ops` reclaim/requeue/snapshot writes require the API key
  - protected `/ops` snapshot/reclaim writes work through same-origin `/api/*` without exposing the API key
- `tests/test_runtime_readiness_external_roots.py`
  - `queue_health` warns when queued age and stale-running suspicion are present
