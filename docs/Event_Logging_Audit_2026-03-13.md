# Event Logging Audit

Status: Working infrastructure audit  
Date: 2026-03-13  
Scope: runtime job execution logging, run timeline reconstruction, SSE job events, artifact meta snapshots, and adjacent log surfaces

## 0. Executive Summary

The current runtime does have execution observability, but it is not the memory-ready event log architecture discussed in the H1 plan.

What exists today is a hybrid of:

1. a SQLite `jobs` table for coarse state
2. worker-owned JSONL log files for step-by-step progress
3. API-side SSE replay built from DB polling plus log-file reads
4. artifact-scoped snapshot files such as `bootstrap_meta.json` and `run_meta.json`
5. separate domain-specific JSONL logs under Research DNA

What does not exist today:

1. a DB-backed `job_events` table
2. a DB-backed `user_actions` table
3. a unified execution-level `runs` table for job orchestration
4. a buffered event writer
5. a single append-only audit trail that memory/recall could consume directly

Current judgment:

- the runtime is operational and observable enough for current UI/API flows
- the event model is still file-log centric, not contract centric
- this is adequate for the present product baseline, but it is not yet the foundation needed for memory-ready hooks

## 1. Current Event Surfaces

### 1.1 SQLite `jobs` table

Current runtime persistence is centered on the `jobs` table in `/Users/jangseongjin/paperpipe/src/db_utils.py`.

Persisted fields include:

- `job_id`
- `run_id`
- `paper_id`
- `persona_id`
- `run_verify`
- `clean_reindex`
- `status`
- `progress`
- `stage`
- `created_at`
- `started_at`
- `finished_at`
- `artifact_dir`
- `log_path`
- `error_code`
- `error_message`

Assessment:

- this is a coarse job state row, not an event log
- it supports queueing, claiming, status display, and restart visibility
- it does not preserve execution history at the event level

### 1.2 Worker JSONL job logs

The active event stream is primarily written by the worker in `/Users/jangseongjin/paperpipe/src/jobs/worker.py`.

Current behavior:

- worker claims a queued job
- worker creates `logs/jobs/{job_id}.jsonl`
- worker stores that path into `jobs.log_path`
- each `progress_callback` event is appended as one JSON line

Event payload shape typically includes:

- `job_id`
- `run_id`
- `stage`
- `progress`
- `message`
- `level`
- `timestamp`

Assessment:

- this is the effective step-by-step execution log today
- persistence depends on the worker path actually passing a `progress_callback`
- it is append-only enough for replay, but it is file-based and not queryable in SQLite

### 1.3 SSE job events endpoint

`/Users/jangseongjin/paperpipe/backend/main.py` exposes `/jobs/{job_id}/events` as the live event stream.

Important detail:

- the endpoint does not read a DB event table
- it polls `queue.get_job(job_id)`
- it replays `job.log_path`
- it synthesizes a terminal `done` event from the job row

Current emitted event types:

- `status`
- `artifact_ready`
- `log`
- `done`
- `error` for unknown job

Replay behavior:

- supports `Last-Event-ID`
- replays only missing `log-*` and `done-*` events
- treats stale cursors as replay-from-head

Assessment:

- the SSE surface is robust enough for the current frontend/tests
- it is a projection over file logs and job rows, not a primary event store

### 1.4 Run timeline endpoint

`/Users/jangseongjin/paperpipe/backend/main.py` exposes `/runs/{run_id}` and `/runs/{run_id}/timeline`.

Current reality:

- `run_id` lookup is just `SELECT * FROM jobs WHERE run_id = ?`
- timeline reconstruction is `job.log_path` replay plus one synthetic terminal event
- there is no execution `runs` table behind this API path

Assessment:

- the `/runs/*` API is a convenience projection over `jobs`
- it is not backed by a first-class run event model

### 1.5 Artifact snapshot metadata

`/Users/jangseongjin/paperpipe/backend/services/job_runner.py` writes:

- `bootstrap_meta.json`
- `run_meta.json`

Current purpose:

- summarize notable pipeline facts
- expose claimset readiness and related badges
- preserve config/profile snapshots for a given artifact directory

Assessment:

- these files are useful execution snapshots
- they are not append-only event streams
- they should be treated as derived metadata, not as a replacement for an event log

### 1.6 Research DNA JSONL logs

Research DNA has its own structured log system in `/Users/jangseongjin/paperpipe/src/profiles/research_dna_store.py`.

Current log families:

- `interview.jsonl`
- `runs.jsonl`
- `screening.jsonl`
- `approval_audit.jsonl`

Assessment:

- this is a real domain-specific log surface
- it is not integrated with the runtime `jobs` event model
- it proves that append-only JSONL logging already exists in the codebase, but in a siloed form

## 2. Persistence Matrix

| Surface | Persisted | Queryable | Scope | Current role |
| --- | --- | --- | --- | --- |
| `jobs` table | yes | yes | runtime job state | queue + status backbone |
| `logs/jobs/{job_id}.jsonl` | yes | file only | worker execution | effective progress/event history |
| `JOB_QUEUES` in memory | no durable persistence | no | transient runner pubsub | effectively unused in API path |
| `bootstrap_meta.json` | yes | file only | artifact snapshot | enriched job/detail metadata |
| `run_meta.json` | yes | file only | artifact snapshot | per-run summary snapshot |
| Research DNA logs | yes | file only | domain workflow | DNA-specific audit/log trail |
| `review_queue` table | yes | yes | issue/review workflow | follow-up queue, not execution log |

## 3. Verified Runtime Semantics

### 3.1 Jobs are the canonical runtime state, not events

The queue layer in `/Users/jangseongjin/paperpipe/src/jobs/queue.py` persists a single mutable row per job.

Implications:

- state transitions are visible only as the latest row values
- prior intermediate states are lost unless they were also written to `log_path`
- there is no way to answer "what happened at step N" from SQLite alone

### 3.2 The worker path is what makes event replay possible

`/Users/jangseongjin/paperpipe/src/jobs/worker.py` is the component that bridges runner events into durable logs.

Implications:

- if `run_deepread_job()` runs through the worker, progress is replayable
- if `run_deepread_job()` runs without `progress_callback`, the durable event history largely disappears
- this is a strong sign that the event contract is attached to a caller pattern, not to the runtime core itself

### 3.3 `JOB_QUEUES` is not the live backbone it appears to be

`/Users/jangseongjin/paperpipe/backend/services/job_runner.py` still defines `JOB_QUEUES` and `emit()` can publish into it.

But repository search on 2026-03-13 found:

- `JOB_QUEUES[job_id] = ...` is not written anywhere in the active code path
- `/jobs/{job_id}/events` does not read `JOB_QUEUES`

Assessment:

- `JOB_QUEUES` is effectively dead or vestigial in the current runtime
- the real event surface is DB row polling plus log-file replay

### 3.4 `/runs/{run_id}` is not a first-class execution object

The API suggests a run resource, but implementation shows a projection over `jobs`.

Implications:

- there is no place to store execution-level metadata separate from a job row
- future `runs -> jobs -> job_events` layering would need a naming/compatibility plan
- this matters because `/Users/jangseongjin/paperpipe/src/db.py` already has a legacy `runs` table keyed by `date`

### 3.5 `review_queue` is workflow state, not an execution log

The runtime uses `review_queue` for follow-up actions such as manual review requests.

Assessment:

- useful operationally
- not suitable as a memory-ready trace of user intent or execution events

## 4. What Is Actually Covered By Tests

Verified test surfaces:

- `/Users/jangseongjin/paperpipe/tests/test_jobs_events_persistence.py`
- `/Users/jangseongjin/paperpipe/tests/test_artifacts_runs_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_jobs_api_smoke.py`
- `/Users/jangseongjin/paperpipe/tests/test_jobs_restart_persistence.py`

These tests confirm:

- SSE emits `status`, `log`, `done`, and `artifact_ready`
- `Last-Event-ID` replay works for terminal jobs
- `/runs/{run_id}/timeline` is reconstructed from `job.log_path`
- bootstrap meta enrichment is exposed on `/jobs/{job_id}` and `/jobs/{job_id}/events`
- job status survives across queue instances because the source of truth is SQLite

What they do not confirm:

- DB-backed event history
- user action persistence
- buffered event writing
- unified event correlation across Meeting Pack, Research DNA, and Deep Read

## 5. Gaps Relative To The Memory-Ready Hook Plan

### 5.1 Missing `job_events`

There is no append-only runtime event table in SQLite.

Consequence:

- event replay is tied to log files, not relational queries
- cross-job analytics and memory extraction require file parsing or custom projections

### 5.2 Missing `user_actions`

There is no unified persisted table for actions such as:

- `important`
- `remember`
- `pin`
- `tag_add`
- `tag_remove`
- future UI approvals or memory write signals

Consequence:

- user intent is not a durable first-class signal yet

### 5.3 Missing execution-level `runs`

There is no modern run entity that can hold:

- pipeline profile
- trigger source
- execution params
- aggregate metrics
- run-level status independent from a single job row

Consequence:

- `run_id` exists, but run semantics do not

### 5.4 Missing unified correlation across subsystems

Research DNA logging, Deep Read jobs, review queue decisions, and Meeting Pack generation all have adjacent traces, but no shared event registry.

Consequence:

- later memory writer/recall systems would need subsystem-specific adapters
- there is no single timeline for "user asked X, system ran Y, produced Z"

## 6. Current Risks

### 6.1 Event durability depends on the worker path

If the worker is bypassed, event history can degrade to the final `jobs` row plus artifact metadata.

Priority: P1

### 6.2 `JOB_QUEUES` creates misleading architectural expectations

The code still describes an in-memory PubSub backbone, but the real API path does not use it.

Priority: P1

### 6.3 Path masking does not obviously cover SSE log payload content

`/Users/jangseongjin/paperpipe/backend/main.py` masks `artifact_dir`, `log_path`, and `bootstrap_meta_path` in structured job responses.

But the SSE `log` event emits raw line content from `job.log_path`.

Consequence:

- if a log message contains an absolute local path, that path can be streamed to clients unchanged
- current path masking tests do not cover this surface

Priority: P1

### 6.4 Legacy `runs` naming collision remains

`/Users/jangseongjin/paperpipe/src/db.py` already defines a legacy `runs` table keyed by date.

Consequence:

- adopting a new execution-level `runs` table later needs migration or a different name

Priority: P2

## 7. Recommended Next Sequence

### Step 1. Freeze current behavior as the baseline

Do not rewrite the SSE/timeline surface first.

First preserve the current contract:

- `jobs` row remains the status backbone
- `log_path` replay remains supported
- `bootstrap_meta.json` enrichment remains supported
- `/runs/{run_id}` stays backward-compatible

### Step 2. Add a real DB event layer without breaking current APIs

Recommended new tables:

- `execution_runs` or another name that avoids collision with legacy `runs`
- `job_events`
- `user_actions`

Initial bridge strategy:

- keep writing JSONL job logs for backward compatibility
- also append structured rows into `job_events`
- keep `/jobs/{job_id}/events` able to replay from DB first and fall back to file logs

### Step 3. Move event production into a shared writer contract

Instead of relying on the worker-only `progress_callback` path, create a shared event logger used by:

- worker pipeline jobs
- Meeting Pack generation jobs
- Research DNA pilot/screening workflows where relevant
- future skills/actions runs

### Step 4. Persist user intent explicitly

Introduce `user_actions` for signals such as:

- `important`
- `remember`
- `pin`
- `meeting_pack_generate`
- `stats_verify_request`

This is the minimum viable substrate for a future memory writer.

## 8. Final Judgment

Current event logging is good enough for the present execution baseline.

It is not yet the event system described in the memory-ready hook plan.

The most accurate description of the current architecture is:

- SQLite job state
- worker-owned JSONL progress logs
- SSE replay over DB + files
- artifact snapshot metadata
- siloed Research DNA JSONL logs

That means the next event-log PR should be treated as additive infrastructure, not as a cleanup of something that already exists.
