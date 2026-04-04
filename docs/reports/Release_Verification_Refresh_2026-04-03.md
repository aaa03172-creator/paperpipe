# Release Verification Refresh (2026-04-03)

Status: Active release evidence note
Date: 2026-04-03
Owner: Runtime/product maintainers
Canonical parents:
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`

## Purpose

Record a fresh bounded release verification pass on the clean `codex/escalation-metadata-runtime` branch after the external-reference follow-up lane merged.

This note answers:
- does the current base branch still pass the bounded verification set closely enough to preserve the current stop/continue judgment?
- did the refresh uncover a new blocker-shaped feature lane?
- if something failed, was it product/runtime behavior or clean-install / local-runner setup drift?

This note is not:
- a new roadmap
- a reason to reopen OCR, reader attempt-order, `Project`, or generalized workspace lanes
- a claim that all machine-local smoke flows are now clean-branch portable

## Branch and scope

- branch under test: `codex/escalation-metadata-runtime`
- clean worktree: `/private/tmp/paperpipe-escalation-runtime-next-20260403-zanXah`
- starting HEAD: `8856ed5`

## Verification run

### Passed directly

- `./scripts/run_backend_api_smoke.sh`
- `pytest -q tests/test_research_dna_service.py tests/test_evaluate_search.py tests/test_research_dna_cli.py`
- `./scripts/run_meeting_pack_verify.sh`
- `python3 scripts/lint_docs.py`

### Passed after clean-worktree environment bootstrap

- `cd frontend && npm ci`
- `cd frontend && npm run verify:frontend:backend`
- `cd frontend && npm run e2e:backend`
- `cd frontend && npm run e2e:backend:parser-worker`
- fresh editable-install check:
  - `python3 -m venv <tmp>`
  - `pip install -e .`
  - import check for `docker`, `multipart`, `langgraph`, `src.sandbox.docker_runner`, and `src.agents.stats_agent`

Why the extra bootstrap was needed:
- the clean worktree had no frontend node_modules yet
- a clean editable Python install from repo metadata initially missed backend/runtime imports that the browser-backed checks actually need

### Clean-install dependency gap observed and repaired

A clean editable install surfaced missing declared dependencies before the frontend backend checks could run:
- `docker` was imported by `src/sandbox/docker_runner.py` but not declared in repo install metadata
- `langgraph` was imported by `src/agents/stats_agent.py` and exercised by the parser-worker path but not declared in repo install metadata
- `python-multipart` was already called out in `backend/requirements.txt` but was still missing from the main project metadata used by `pip install -e .`

Applied bounded fix:
- add `docker`, `langgraph`, and `python-multipart` to `pyproject.toml`
- align `requirements.txt` and `backend/requirements.txt` with the same runtime expectation

## Real-smoke result

`cd frontend && npm run e2e:backend:real-smoke` did not run in the clean worktree as-is.

Observed failure:
- `PaperPipe config not found: config.yaml`

Interpretation:
- this is a machine-local proof step, not a clean-branch-portable harness
- `frontend/README.md` already documents that `e2e:backend:real-smoke` uses the current `PAPERPIPE_CONFIG_PATH` / storage / db / artifacts environment directly
- therefore this refresh does not treat the clean-worktree failure as a new product/runtime blocker

## Current judgment

Current result:
- the bounded verification slice still supports the existing stop/continue posture
- no new blocker-shaped feature lane emerged
- one real clean-install hygiene gap did emerge, and it was a dependency declaration gap rather than a product-boundary problem

## Consequence

Use this note as the latest bounded release verification proof for the current tree.

What changed relative to the previous release proof:
- backend/browser verification remains green on the seeded harness
- parser-worker fallback coverage also remains green once the missing declared dependencies are restored
- real-smoke remains a runner-local / machine-local proof step and should be described that way rather than as a branch-portable default command

## Non-recommendations

Do not use this refresh as a reason to:
- reopen PaddleOCR integration
- reopen default reader attempt-order work
- reopen `Project` / chat / memory platform lanes
- widen the current proof set into a general environment bootstrap project

## Bottom line

The current repo still looks release-proof enough on the bounded seeded verification slice.

The fresh finding was narrower:
- fix clean-install dependency declarations
- keep real-smoke framed as a local-runner proof, not as a guaranteed clean-worktree command
