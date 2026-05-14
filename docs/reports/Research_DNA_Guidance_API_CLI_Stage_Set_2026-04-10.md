# Research DNA Guidance API CLI Stage Set

Status: exact patch-stage boundary
Date: 2026-04-10
Lane: `research-dna/guidance-api-cli`
Parent notes:
- [Research_DNA_Rerank_Operator_Guidance_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Research_DNA_Rerank_Operator_Guidance_Stage_Set_2026-04-10.md)
- [Research_DNA_Guidance_History_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Research_DNA_Guidance_History_Stage_Set_2026-04-10.md)

## Purpose

Freeze the remaining `Research DNA` follow-up that exposes already-materialized guidance snapshots and guidance history through FastAPI and CLI read surfaces.

This note does not stage or commit anything.
It answers one narrower question:

- which remaining `main.py` and `cli.py` hunks form one safe patch-stage lane after the service/schema work is already committed?

## Diff Re-check Summary

Current re-read result:

- `backend/main.py` and `src/cli.py` still contain broad mixed tails
- one coherent subset remains around `guidance-artifact` and `guidance-history` read surfaces
- the underlying service helpers and schema envelopes are already present in committed code
- existing `Research DNA` roundtrip tests already expect these surfaces to exist

Current judgment:

- this is one bounded patch-stage lane
- it is read-only and additive
- it aligns API and CLI with already-committed `Research DNA` guidance materialization and history storage
- it must not be staged as whole files from the current dirty tree

## Files In Scope

These files belong to this lane:

- [main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- [Research_DNA_Guidance_API_CLI_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Research_DNA_Guidance_API_CLI_Stage_Set_2026-04-10.md)

Only the note is whole-file safe.
Both code files require hunk-splitting.

## What Belongs In This Lane

Keep from [main.py](/Users/jangseongjin/paperpipe/backend/main.py):

- `ResearchDNAScreeningGuidanceIndexEnvelope` import
- `load_latest_screening_guidance_artifact` import
- `load_screening_guidance_index_artifact` import
- `GET /research-dna/{dna_id}/runs/{run_id}/screening-guidance-artifact`
- `GET /research-dna/{dna_id}/runs/{run_id}/screening-guidance-history`

Keep from [cli.py](/Users/jangseongjin/paperpipe/src/cli.py):

- `research-dna guidance-artifact`
- `research-dna guidance-history`

## Out Of Scope

Do not include these in the same stage set:

- browser auth, audit logging, beta gate, proxy, rate limit, and host-validation hunks in [main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- runtime-readiness, `/health/ready`, workspace-summary, note-backed paper access, paper listing, PDF fallback, UI deep-link, frontend asset, and `paper_syntheses` router hunks in [main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- watchdog availability, fixture quarantine, runtime-readiness doctor output, logs-root, clinical print, or reset/log path hunks in [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)

Why these stay out:

- they belong to different runtime, security, or operator lanes
- mixing them would turn a narrow `Research DNA` follow-up into another broad tail commit

## Architecture Check

Why this split is safe:

- it does not create a new owner for `Research DNA`
- it only exposes already-committed guidance artifacts and history indexes
- it keeps the current API-first contract aligned with the CLI operator surface
- it does not change persistence or reranking logic

## Verification Re-check

Run these commands for this lane:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_research_dna_api.py::test_research_dna_api_roundtrip_and_pilot \
  tests/test_research_dna_cli.py::test_research_dna_cli_roundtrip
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
```

## Manual Stage Recipe

If this lane is staged next, patch-stage only:

```bash
git add -p /Users/jangseongjin/paperpipe/backend/main.py
git add -p /Users/jangseongjin/paperpipe/src/cli.py
git add /Users/jangseongjin/paperpipe/docs/reports/Research_DNA_Guidance_API_CLI_Stage_Set_2026-04-10.md
```

Accept only the hunks listed in `What Belongs In This Lane`.

## Short Version

The remaining clean `Research DNA` tail is not another whole-file lane.
It is one patch-stage follow-up:

- add API reads for the latest guidance artifact and guidance history
- add matching CLI reads for the latest guidance artifact and guidance history
- leave all other `main.py` and `cli.py` tails for later
