# PaperPipe Operations Runbook

Status: Active
Date: 2026-04-24
Owner: Operations maintainers
Canonical entrypoint: `docs/OPERATIONS_RUNBOOK.md`
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Purpose

Use this runbook as the first operational entrypoint for a local-first or personal-runtime PaperPipe instance.

This document does not replace the narrower canonical runbooks. It points operators to the current safe paths for startup checks, health/readiness, stuck jobs, logs, monitoring, secrets, deployment, and backup posture.

## Current Operating Shape

PaperPipe's current runtime shape is:

- FastAPI backend with Vite/React UI surfaces.
- SQLite-backed local runtime state.
- Background worker consumption for deep-read jobs.
- Local file roots for logs, artifacts, reports, and bounded support artifacts.
- Personal-runtime and close-person beta posture, not a shared multi-tenant production platform.

Operational decisions should preserve that boundary. Do not introduce shared-server, account/workspace, or centralized infrastructure assumptions through an ops shortcut.

## First Response Checklist

When the runtime looks unhealthy, start here:

1. Confirm whether the server is reachable.

```bash
curl -sS http://127.0.0.1:8000/health
```

2. Inspect runtime readiness.

```bash
curl -sS http://127.0.0.1:8000/health/ready
```

If `LATTICE_API_KEY` is set, provide `X-API-Key` for direct backend calls or use same-origin browser `/api/*` paths from the served UI.

3. Run the local self-test when available.

```bash
lattice self-test --json
```

4. If queue health is warning, inspect stale-job diagnostics before mutating anything.

```bash
curl -sS "http://127.0.0.1:8000/ops/stale-jobs?stale_after_seconds=900&limit=50"
```

5. If downloader failures are suspected, generate the downloader dashboard.

```bash
.venv314/bin/python scripts/downloader_ops_dashboard.py --db storage/state.db --out storage/reports/downloader_ops_dashboard.md
```

For one command that combines runtime readiness and downloader alert thresholds with stable exit codes:

```bash
.venv314/bin/python scripts/check_ops_readiness.py
```

6. Before any destructive or overwrite-prone local maintenance, confirm whether the script is dry-run by default and whether it creates a backup under `storage/backups/`.

## Health And Readiness

Use `/health` only as a lightweight liveness probe.

Use `/health/ready` for operational readiness. Current readiness checks include broader runtime state such as queue health and configured external roots. Browser-facing deployments may expose a narrowed readiness payload when the hosted beta gate is enabled.

Relevant references:

- `backend/main.py`
- `src/services/runtime_readiness.py`
- `docs/runtime_security_env.md`
- `docs/STALE_RUNNING_RECOVERY.md`

Important signals:

- `status`
- `queue_health.status`
- `queue_health.metadata.queued_jobs_total`
- `queue_health.metadata.running_jobs_total`
- `queue_health.metadata.oldest_queued_age_seconds`
- `queue_health.metadata.stale_running_suspected_total`

## Job Queue And Stuck Runs

Do not edit SQLite rows directly to clear a stuck job.

Use the stale-running recovery path:

1. Confirm the warning in `/health/ready`.
2. Inspect `GET /ops/stale-jobs`.
3. Inspect job, run, timeline, events, logs, and artifacts when available.
4. Capture a stale incident snapshot before mutation when the job appears abandoned.
5. Reclaim through `POST /ops/jobs/{job_id}/reclaim-stale` only after operator review.
6. Re-run explicitly through `POST /ops/jobs/{job_id}/requeue-reclaimed` or the standard deep-read enqueue path.

Canonical runbook:

- `docs/STALE_RUNNING_RECOVERY.md`

Current protected mutation endpoints:

- `POST /jobs/deepread`
- `POST /jobs/{job_id}/cancel`
- `POST /ops/jobs/{job_id}/stale-incident-snapshot`
- `POST /ops/jobs/{job_id}/reclaim-stale`
- `POST /ops/jobs/{job_id}/requeue-reclaimed`

## Logs And Support Artifacts

Current log and support-artifact roots are local. Treat them as operational evidence, not canonical truth.

Common locations:

- `logs/`
- `logs/jobs/{job_id}.jsonl`
- `storage/reports/`
- `storage/stale_running_incidents/`
- bounded artifact roots under `storage/`

Current boundaries:

- worker progress JSONL is useful for diagnosis, but canonical job state lives in the runtime DB.
- stale-running incident snapshots are review/support artifacts, not source data and not canonical state.
- request audits and job events are sanitized at storage/read boundaries, but operators should still avoid pasting secrets into payloads or logs.

## Monitoring And Alerting

The current repo has lightweight monitoring hooks, not a centralized observability stack.

Use the downloader dashboard for downloader-specific alerting:

```bash
.venv314/bin/python scripts/downloader_ops_dashboard.py \
  --db storage/state.db \
  --out storage/reports/downloader_ops_dashboard.md \
  --hours 24
```

Exit codes:

- `0`: no downloader threshold crossed.
- `2`: one or more downloader thresholds crossed.

Recommended near-term alert wiring:

- cron or systemd timer that fails on exit code `2`.
- GitHub Actions or local scheduler notification.
- Slack/email/webhook wrapper owned outside the PaperPipe runtime.

For a combined runtime/downloader check:

```bash
.venv314/bin/python scripts/check_ops_readiness.py --json
```

Exit codes:

- `0`: runtime readiness is ok and downloader thresholds are not crossed.
- `1`: runtime readiness has an error or the downloader check itself failed.
- `2`: runtime readiness is degraded or downloader thresholds crossed.

For local schedulers that need a latest report file plus a short notification-friendly summary:

```bash
.venv314/bin/python scripts/run_ops_readiness_monitor.py
```

By default this writes:

- `storage/reports/ops_readiness_latest.json`
- `storage/reports/ops_readiness_latest.txt`

Use the process exit code for cron, launchd, systemd, or an external notification wrapper. The script does not send Slack, email, webhook, or analytics events by itself.

Do not introduce heavy centralized logging or analytics dependencies unless the deployment posture changes beyond the current personal-runtime shape.

Canonical runbook:

- `docs/downloader_monitoring.md`

## Environment And Secrets

Use environment variables for secrets and runtime controls. Do not put backend secrets in `VITE_*` browser variables.

Recommended local baseline:

```bash
export LATTICE_API_KEY="change-me"
export LATTICE_CORS_ALLOW_ORIGINS="http://localhost:8000"
export LATTICE_MAX_CONCURRENT_JOBS="1"
export LATTICE_MAX_QUEUED_JOBS="20"
```

Protected direct backend calls require `X-API-Key` when `LATTICE_API_KEY` is set. The backend-served UI should call same-origin `/api/*`; FastAPI injects the backend API key server-side for protected backend routes.

Hosted close-person beta controls include:

- `LATTICE_BETA_PASSWORD`
- `LATTICE_BETA_USERNAME`
- `LATTICE_ALLOWED_HOSTS`
- `LATTICE_BETA_ALLOWED_IPS`
- `LATTICE_TRUSTED_PROXY_IPS`
- browser read/write rate-limit variables

Canonical runbook:

- `docs/runtime_security_env.md`

## Backup And Restore Posture

Current PaperPipe has meaningful local safety patterns, but not a unified backup/restore runtime.

Current safe claims:

- some DB mutation scripts are dry-run by default and create SQLite backups before `--apply`.
- several bounded artifact stores perform rollback-aware writes.
- local branch-backup retention is documented separately.
- some artifacts are rerenderable from saved request state.

Current unsafe claims:

- do not claim every runtime asset has direct restore support.
- do not claim one generic backup status means the same thing for DB state, file bundles, and rerenderable artifacts.
- do not introduce a top-level backup API without reopening the deferred backup/restore lane.

Before running a mutation script, check:

- Is dry-run the default?
- Is there an explicit `--apply`?
- Is a backup path printed or configurable?
- Does the script use a transaction or rollback-aware write?
- Is there a summary artifact or clear stdout result?

To test whether a script-created SQLite backup is at least readable and structurally restorable without touching the live runtime DB:

```bash
.venv314/bin/python scripts/check_sqlite_restore_drill.py --backup storage/backups/<backup>.db
```

If `--backup` is omitted, the command checks the latest `storage/backups/*.db` file. The drill copies the backup to a temporary path, runs SQLite `integrity_check`, verifies required tables, and exits non-zero on failure. It does not replace `storage/state.db`.

References:

- `docs/MUTATION_SCRIPT_SAFETY_INVENTORY.md`
- `docs/RESTORE_READINESS_MATRIX.md`
- `docs/reports/Local_Backup_Restore_Gate_2026-03-24.md`
- `docs/archive/Local_Backup_and_Restore_Semantics_RFC_2026-03-18.md`
- `docs/Local_Backup_Branch_Retention_2026-02-24.md`

## Deployment And Rollback

Current deployment posture is personal-runtime first.

Use the personal-runtime docs for packaging and release checks:

- `docs/DEPLOYMENT_ROLLBACK_CHECKLIST.md`
- `docs/PERSONAL_RUNTIME_INSTALL.md`
- `docs/PERSONAL_RUNTIME_USER_KITS.md`
- `docs/MACOS_PERSONAL_RUNTIME_RELEASE.md`
- `docs/MACOS_PERSONAL_RUNTIME_ALPHA_HANDOFF.md`
- `docs/WINDOWS_PERSONAL_RUNTIME_ALPHA.md`

Before sharing or updating a runtime:

1. Run the smallest relevant backend and frontend verification gates for the touched surface.
2. Run `lattice self-test --json` or the packaged app self-test when using a bundled runtime.
3. Preserve the old distribution artifact or local branch until the new runtime has passed smoke checks.
4. Keep branch naming and CI target-branch differences explicit. The repository default branch is `main`, while some current PR checks still target `master`.
5. For privacy or external-inference pilots, prefer env rollback flags such as `LATTICE_PRIVACY_PREFLIGHT_MODE="off"` when available.

Rollback should be specific to the touched layer:

- config/env rollback for runtime controls.
- branch or package rollback for release artifacts.
- script-created SQLite backup rollback for bounded DB maintenance.
- rerender/regenerate path for artifact families that document rerenderability.
- manual inspection for asset families that do not yet advertise direct restore.

## Manual Risk Rules

Follow these rules during operations:

- Do not directly edit `storage/state.db` to clear queues, jobs, papers, or run state.
- Do not delete artifacts or logs while diagnosing an active failure.
- Do not run `--apply` scripts until the dry-run output is understood.
- Do not expose `LATTICE_API_KEY`, provider API keys, cookies, signed URLs, or local private paths in shared screenshots or copied logs.
- Do not treat support artifacts, logs, or reports as canonical state.
- Do not loop reclaim/requeue indefinitely; repeated stalls are runtime incidents, not single-job cleanup.

## Next PR-Sized Ops Improvements

1. Add an external notification wrapper only after the preferred local scheduler/channel is chosen.
2. Keep Windows packaged-alpha claims blocked until a real Windows packaged smoke pass is recorded.
