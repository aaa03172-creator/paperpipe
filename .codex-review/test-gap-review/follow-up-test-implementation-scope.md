# Follow-up Test Implementation Scope

## Scope reviewed

This follow-up summarizes the test additions made after the initial test-gap review and the verification commands used to check them.

## Review artifacts

The original review artifacts remain present and non-empty:

- `test-inventory.md`
- `behavior-map.md`
- `coverage-gaps.md`
- `weak-tests.md`
- `flaky-risk-tests.md`
- `mock-risk.md`
- `high-value-test-plan.md`
- `report.md`

## High-value tests added or extended in this lane

### Worker/job-runner/API contract

- `tests/test_deepread_worker_contract.py`
- `tests/test_worker_job_runner_chain.py`
- `tests/test_openapi_contract.py`

Covered risks:
- API enqueue to worker to `run_deepread_job` wiring.
- Worker fallback compatibility with older job-runner signatures.
- OpenAPI response schema drift for core job/artifact/readiness surfaces.

### External provider contracts

- `tests/test_external_provider_contracts.py`
- `tests/test_downloader.py`
- `tests/test_fetch_providers.py`
- `tests/test_bibliometrics.py`

Covered risks:
- PubMed, Unpaywall, arXiv, and OpenAlex response shape drift.
- Invalid PDF content not being retained or copied.
- Bibliometric scoring and OpenAlex mapping remaining deterministic.

### Artifact and path safety APIs

- `tests/test_artifacts_runs_api.py`
- `tests/test_chart_packs_api.py`
- `tests/test_meeting_packs_api.py`
- `tests/test_protocol_cards_api.py`
- `tests/test_protocol_attachments_api.py`

Covered risks:
- Encoded traversal IDs not reading outside configured artifact roots.
- Malformed artifact JSON preserving response contract with `_parse_error`.
- DB artifact pointers outside the artifacts root not being served.

### Research DNA and profile projection

- `tests/test_research_dna_api.py`
- `tests/test_research_dna_projection.py`
- `tests/test_profile_projection_guard.py`

Covered risks:
- Locked Research DNA write failures do not mutate profile state or audit logs.
- Current-candidate mismatch does not append screening logs.
- `latest_run=true` requires an existing pilot run.
- Projection profile ID collision does not overwrite a manual profile or log `project_profile`.

### Project memory and frontend/backend contracts

- `tests/test_project_context_link_api.py`
- `tests/test_project_memory_store.py`
- `tests/test_project_memory_schema.py`
- `tests/test_frontend_api_contracts.py`

Covered risks:
- Invalid project context-link requests do not append logs.
- Missing workspace requests do not create context-link logs.
- Frontend TypeScript interfaces stay aligned with backend OpenAPI fields for paper notes and artifacts.

## Verification performed

Latest focused and cumulative verification:

- `tests/test_frontend_api_contracts.py`: `3 passed`
- Review artifacts existence/non-empty check: all 8 original artifacts OK
- Cumulative high-risk test bundle: `200 passed, 6 warnings`

Warnings observed:
- Existing SWIG import deprecation warnings.
- Existing ChromaDB `asyncio.iscoroutinefunction` deprecation warning.

## Worktree scope note

The repository currently has a broad dirty worktree, including source and frontend files outside this test-review lane. This scope review did not classify those broader source/frontend diffs as part of the follow-up test implementation. Before staging or committing, separate the test-review lane from unrelated dirty changes and stage only the intended files.

## Suggested staging boundary

Do not stage automatically from this worktree. The current dirty tree includes unrelated source, frontend, docs, generated artifacts, and deletion changes.

Known test-gap review artifacts for this lane:

- `.codex-review/test-gap-review/test-inventory.md`
- `.codex-review/test-gap-review/behavior-map.md`
- `.codex-review/test-gap-review/coverage-gaps.md`
- `.codex-review/test-gap-review/weak-tests.md`
- `.codex-review/test-gap-review/flaky-risk-tests.md`
- `.codex-review/test-gap-review/mock-risk.md`
- `.codex-review/test-gap-review/high-value-test-plan.md`
- `.codex-review/test-gap-review/report.md`
- `.codex-review/test-gap-review/follow-up-test-implementation-scope.md`

Known high-value tests added or extended in this lane:

- `tests/test_deepread_worker_contract.py`
- `tests/test_external_provider_contracts.py`
- `tests/test_frontend_api_contracts.py`
- `tests/test_openapi_contract.py`
- `tests/test_worker_job_runner_chain.py`
- `tests/test_bibliometrics.py`
- `tests/test_chart_packs_api.py`
- `tests/test_meeting_packs_api.py`
- `tests/test_protocol_cards_api.py`
- `tests/test_protocol_attachments_api.py`
- `tests/test_research_dna_api.py`
- `tests/test_project_context_link_api.py`
- `tests/test_artifacts_runs_api.py`
- `tests/test_downloader.py`

Files that appear in `tests/` but were not classified as this test-gap lane should be reviewed separately before staging. In particular, do not automatically include broad pre-existing test changes, untracked test files outside the list above, production/source edits, frontend edits, MagicMock artifact deletions, or unrelated `.codex-review/*` directories.

## Remaining recommended verification

1. Consider a later implementation fix for downloader partial-file cleanup on mid-stream network exceptions, then add a failing regression test for that behavior.
2. If this lane is prepared for commit, separate it carefully from the broader dirty worktree before staging.

## Full-suite double-check on 2026-05-10

Initial command:

```bash
.venv314/bin/python -m pytest -q
```

Initial result:

- Failed during collection before running the suite.
- `tests/test_docker_runner.py` and `tests/test_docker_sandbox.py` import `docker`.
- The current `.venv314` environment does not have the Python `docker` package installed.
- Repository dependency search did not find a `docker` entry in `pyproject.toml`, `requirements*.txt`, `setup.cfg`, `tox.ini`, or `pytest.ini`.
- `.github/workflows/agents-smoke.yml` does document `pip install ruff pytest docker`, so installing the Python `docker` package for local verification is consistent with the existing CI workflow.

Environment follow-up:

```bash
.venv314/bin/python -m ensurepip --upgrade
.venv314/bin/python -m pip install docker
```

Result:

- `pip` was bootstrapped into `.venv314`.
- `docker==7.1.0` was installed into `.venv314`.

Focused blocker rerun:

```bash
.venv314/bin/python -m pytest -q tests/test_docker_runner.py tests/test_docker_sandbox.py tests/test_no_new_trial_extraction_alias.py tests/test_packaging_entrypoints.py
```

Result:

- `6 passed, 4 skipped`
- Docker daemon-dependent cases skipped in this local environment.

Final full-suite command:

```bash
.venv314/bin/python -m pytest -q
```

Final result:

- `2047 passed, 5 skipped, 7 warnings`
- Runtime: `427.81s`

Warnings observed:

- Existing SWIG import deprecation warnings.
- Existing ChromaDB `asyncio.iscoroutinefunction` deprecation warning.
- Existing `src.db` deprecation warning in `tests/test_db_get_paper_by_id.py`.

Interpretation:

- The full repository pytest suite is green in the current environment after bootstrapping `pip` and installing the workflow-documented Python `docker` package.
- Skips are expected for Docker daemon-dependent tests when Docker is unavailable locally.
