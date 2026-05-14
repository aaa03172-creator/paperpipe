# Stats Docker Timeout Staging Prep

Status: staging manifest  
Date: 2026-03-22  
Branch: `codex/agents-smoke-ci-check`

## Intent

Freeze the stats-verification hardening lane that adds degenerate-table fallback, sandbox image bootstrapping, and adaptive timeout/batch verification helpers.

## Included scope

- `src/agents/stats_agent.py`
- `src/sandbox/docker_runner.py`
- `scripts/full_verify_worker.py`
- `scripts/run_full_verify_timeout_batch.py`
- `tests/test_stats_agent.py`
- `tests/test_stats_agent_fallback.py`
- `tests/test_stats_agent_no_table.py`
- `tests/test_docker_runner.py`
- `tests/test_timeout_policy.py`
- `docs/reports/Stats_Docker_Timeout_Staging_Prep_2026-03-22.md`

## Explicitly excluded

- `src/config.py`
- `src/services/cli_workflows.py`
- `src/agents/ingest_agent.py`
- `src/ingest/cloud_table_fallback.py`
- `tests/test_job_runner_table_meta.py`
- `tests/test_job_runner_ingest_backend.py`

## Verification

1. targeted pytest for stats/docker/timeout tests
2. temp worktree import of touched modules if needed
3. `python3 scripts/lint_docs.py`

## Commit target

`feat(stats): harden docker sandbox and timeout verification`
