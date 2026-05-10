# PR-E1 Additive Event Log

Status: Implemented  
Date: 2026-03-13  
Parent roadmap: `/Users/jangseongjin/paperpipe/docs/Audit_Driven_Roadmap_2026-03-13.md`

## Goal

Add a DB-backed execution event layer without breaking the current `jobs` table, JSONL logs, or SSE behavior.

## Implemented scope

Updated files:

- `/Users/jangseongjin/paperpipe/src/db_utils.py`
- `/Users/jangseongjin/paperpipe/src/services/event_log.py`
- `/Users/jangseongjin/paperpipe/src/jobs/queue.py`
- `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`
- `/Users/jangseongjin/paperpipe/src/jobs/worker.py`
- `/Users/jangseongjin/paperpipe/src/schemas/ops.py`
- `/Users/jangseongjin/paperpipe/backend/main.py`
- `/Users/jangseongjin/paperpipe/tests/test_event_log_db.py`

## Added tables

### `execution_runs`

Stores one additive execution record per `run_id`.

Key fields:

- `run_id`
- `paper_id`
- `trigger_source`
- `pipeline_profile`
- `status`
- `created_at`
- `started_at`
- `finished_at`
- `params_json`
- `metrics_json`

### `job_events`

Stores structured append-only execution events.

Key fields:

- `event_id`
- `job_id`
- `run_id`
- `ts`
- `level`
- `event_type`
- `message`
- `payload_json`

### `user_actions`

Stores explicit user intent/action records for later reuse.

Key fields:

- `action_id`
- `ts`
- `paper_id`
- `action_type`
- `source`
- `payload_json`

## DB runtime behavior

`/Users/jangseongjin/paperpipe/src/db_utils.py`

- enables `PRAGMA journal_mode=WAL`
- enables `PRAGMA synchronous=NORMAL`
- enables `PRAGMA foreign_keys=ON`
- creates additive indices for runs/events/actions lookups

## Logging behavior

### 1. Queue layer

`/Users/jangseongjin/paperpipe/src/jobs/queue.py`

- enqueue creates `execution_runs` row
- enqueue writes `job_enqueued`
- claim writes `job_started`
- status transitions sync `execution_runs.status`
- cancel writes `job_cancelled`

### 2. Runtime progress layer

`/Users/jangseongjin/paperpipe/backend/services/job_runner.py`

- every emitted progress event is also persisted into `job_events`

### 3. Worker terminal layer

`/Users/jangseongjin/paperpipe/src/jobs/worker.py`

- writes structured terminal events for:
  - completed
  - failed
  - cancelled during execution
  - worker interrupt
  - worker exception

## API behavior

### Preserved

- `/jobs/{job_id}/events` SSE remains JSONL/file-log based
- existing artifact/job APIs remain unchanged

### Added

- `/runs/{run_id}/timeline` now reads structured DB events when they exist
- JSONL log lines are still included, so legacy timeline expectations are preserved

## Verification

Targeted tests:

- `/Users/jangseongjin/paperpipe/tests/test_event_log_db.py`
- `/Users/jangseongjin/paperpipe/tests/test_jobs_events_persistence.py`
- `/Users/jangseongjin/paperpipe/tests/test_artifacts_runs_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_jobs_api_smoke.py`

Result:

- `27 passed`

Full suite:

- `544 passed, 1 skipped`

## Non-goals in this PR

- no replacement of the existing `jobs` table
- no removal of JSONL job logs
- no new public user-action API surface
- no migration of `/jobs/{job_id}/events` away from SSE/log replay
- no output contract or citation resolver work

## Next step

The next structurally correct follow-up is:

- `PR-O1` output contract convergence
or
- `PR-C1` citation grounding resolver if contract bridge work is intentionally bundled
