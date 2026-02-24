# Post-Merge Operations Note (2026-02-19)

## What Landed
- PR #19: Runtime hardening (`worker.py -> job_runner.py` real chain), v2 compatibility, regression guards.
- PR #20: P2 hardening execution/docs packets and personas audit.

## Operational Baseline
- DeepRead backend path is now:
  - `src/jobs/worker.py`
  - `backend/services/job_runner.py`
- Ingest runtime uses `process_v2` and passes v2 artifact downstream.
- Reader/Indexer/Stats accept `DocumentArtifactV2` input path.

## Verified Smoke (Post-Merge)
- `pytest -q tests/test_worker_job_runner_chain.py tests/test_jobs_api_smoke.py`
- `pytest -q tests/test_stats_agent.py tests/test_artifact_bridge.py`
- Result: all passed on local `master` synced to `origin/master`.

## Regression Guard Files
- `/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py`
- `/Users/jangseongjin/paperpipe/tests/test_jobs_api_smoke.py`
- `/Users/jangseongjin/paperpipe/tests/test_stats_agent.py`
- `/Users/jangseongjin/paperpipe/tests/test_artifact_bridge.py`

## Known Boundaries
- This merge does not add cloud/API dependency.
- Additive job schema only (`persona_id`, `run_verify` path).
- Placeholder risk on worker path is resolved by chain smoke coverage.

## Next Feature Start Point
- Working branch prepared: `codex/post-merge-next-step`
- Use this branch for subsequent feature work to keep `master` clean.

## Update (2026-02-24)
- PR #50 merged: downloader runtime chain attach + CLI compatibility helper restore.
- PR #51 merged: CLI `test-unpaywall` smoke regression + queue status sync.
- PR #52 merged: `/jobs/{id}/events` + `JobQueue` persistence regression guards.
- PR #53 merged: queue close update for PR #52.
- PR #54 merged: SSE boundary guards (cancel/not-found/reconnect terminal replay).
- PR #60 merged: downloader attempt persistence + PR scope guard workflow.

## Handoff (5 lines)
- Runtime baseline remains `worker -> job_runner` with API-first job surfaces.
- `/papers` and `/jobs` contract smoke/regression are green on local `master`.
- Downloader defaults now include `direct_link -> arxiv -> pmc -> unpaywall`.
- SSE consumers can rely on terminal `done` for completed/cancelled + not-found `error`.
- PR hygiene now has a CI guard (`pr-scope-guard`) to block mixed docs/code scopes by default.
