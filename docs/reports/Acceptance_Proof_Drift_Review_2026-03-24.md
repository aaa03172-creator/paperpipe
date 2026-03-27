# Acceptance Proof Drift Review

Status: Active review note  
Date: 2026-03-24  
Owner: Runtime/product maintainers  
Scope: release-bar/checklist language vs actual verification anchors and newer release-scoped evidence notes

## Purpose

Check whether current release-facing docs cleanly distinguish:

- historical baseline proof
- current release-proof expectations
- blocker-identification notes
- concrete verification commands

This note is not a new ship decision.

## Executive Call

Current repo is close to aligned, but one kind of drift remained:

- older broad baseline-green evidence and newer release-scoped acceptance evidence were sitting too close together in the release checklist
- some release-proof expectations were still written as prose rather than concrete commands

The underlying release judgment was already conservative.

Main risk:
- not a false `green`
- but a reader could over-trust older baseline reports or under-specify the final rerun set

## 1. What Is Aligned

### A. The current release story is already narrower than the old baseline story

Repo anchors:
- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`
- `docs/reports/Current_Baseline_Recheck_2026-03-18.md`
- `docs/Pending_PR_Queue.md`

Why this is aligned:
- current release docs already keep the first-product promise narrow
- the checklist already leaves deep-read, provenance, and rerun behavior at `yellow` rather than falsely closing them

### B. The repo already has concrete verification entry points

Repo anchors:
- `scripts/run_backend_api_smoke.sh`
- `scripts/run_meeting_pack_verify.sh`
- `frontend/package.json`

Why this is aligned:
- backend smoke, Meeting Pack verification, docs lint, and frontend backend verification commands already exist
- the issue was mainly whether the release docs pointed to them directly enough

## 2. Drift Found

### A. Historical baseline proof and release-proof were not sharply separated enough

Repo evidence:
- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`
- `docs/reports/Current_Baseline_Recheck_2026-03-18.md`

Issue:
- the surviving release-facing evidence note still leans on the older baseline recheck as support, so the distinction between historical confidence and current release proof must stay explicit.

Why this matters:
- the 2026-03-18 baseline note is useful historical support
- it is not the same thing as the newer release-scoped deep-read acceptance evidence

Action taken:
- clarified in the checklist that older baseline-green reports support credibility only and do not override newer release-scoped blocker or acceptance notes

### B. Some release-proof checks were described, not command-anchored

Repo evidence:
- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`
- `frontend/package.json`

Issue:
- the checklist named required route coverage, but the frontend/backend verification step was not tied directly enough to the existing commands

Action taken:
- replaced the standalone frontend build line in the release command block with `cd frontend && npm run verify:frontend:backend`
- added the concrete real-paper smoke command `cd frontend && npm run e2e:backend:real-smoke`

## 3. Current Proof Hierarchy

### Historical support

- `docs/reports/Current_Baseline_Recheck_2026-03-18.md`

Role:
- shows the repo has had a broad green baseline before
- useful confidence input
- not sufficient by itself for a release claim

### Current release evidence note

- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`

Role:
- capture the bounded first-product rehearsal on current master
- carry the current release-facing evidence without pretending older baseline support is sufficient by itself

### Concrete rerun anchors

- `./scripts/run_backend_api_smoke.sh`
- `pytest -q tests/test_research_dna_service.py tests/test_evaluate_search.py tests/test_research_dna_cli.py`
- `cd frontend && npm run verify:frontend:backend`
- `cd frontend && npm run e2e:backend:real-smoke`
- `./scripts/run_meeting_pack_verify.sh`
- `python3 scripts/lint_docs.py`

## 4. Recommended Guardrail Going Forward

When a release-facing doc cites older green evidence:

1. say whether it is historical support or current release-proof
2. let newer spot checks and blocker notes take precedence when they conflict
3. prefer concrete rerun commands over prose-only verification expectations
4. do not let broad baseline-green language silently upgrade a still-yellow release row
