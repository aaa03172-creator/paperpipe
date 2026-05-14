# Research DNA Rerank Operator Guidance Stage Set

Status: exact stage boundary
Date: 2026-04-10
Lane: `research-dna/rerank-operator-guidance`
Parent notes:
- [Biomedical_Public_Data_Strategy_Review_2026-04-04.md](/Users/jangseongjin/paperpipe/docs/reports/Biomedical_Public_Data_Strategy_Review_2026-04-04.md)
- [Research_DNA_Artifacts_Staging_Prep_2026-03-22.md](/Users/jangseongjin/paperpipe/docs/reports/Research_DNA_Artifacts_Staging_Prep_2026-03-22.md)

## Purpose

Freeze the next safe boundary for the tracked Research DNA lane that adds:

- reranked screening queue materialization as an additive sibling artifact
- screening guidance materialization as an additive run-local audit snapshot
- bounded operator reads for queue, next-candidate, session, recommendation, guidance, and rerank-gate
- a current-next screening shortcut that returns the refreshed session plus the same advisory guidance payload

This note does not stage or commit anything.
It answers one narrower question:

- after the already-landed clinical extraction and deep-read handoff slices, which current Research DNA hunks still form one coherent next lane?

## Diff Re-check Summary

Current re-read result:

- the tracked Research DNA diff is coherent around one operator-facing slice:
  - materialize `reranked_screening_queue.jsonl` plus `rerank_report.json`
  - read `original | reranked` queue variants without changing owner/default status
  - expose advisory recommendation and gate payloads with stable reason and summary fields
  - return the same guidance bundle from session and screening write flows so operators need fewer round-trips
- the same slice is reflected consistently across:
  - service models and helpers
  - API envelopes and endpoints
  - CLI commands
  - dedicated docs and roundtrip tests

Current judgment:

- this is one bounded lane
- it stays additive and advisory-only
- it does not promote a reranked queue into canonical ownership
- it should stay separate from raw-memory, deep-read state-projection, and extraction replay/bootstrap work

## Files In Scope

These files belong to this lane:

- [research_dna_schema.py](/Users/jangseongjin/paperpipe/src/profiles/research_dna_schema.py)
- [research_dna_service.py](/Users/jangseongjin/paperpipe/src/profiles/research_dna_service.py)
- [research_dna.py](/Users/jangseongjin/paperpipe/src/schemas/research_dna.py)
- [test_research_dna_service.py](/Users/jangseongjin/paperpipe/tests/test_research_dna_service.py)
- [test_research_dna_api.py](/Users/jangseongjin/paperpipe/tests/test_research_dna_api.py)
- [test_research_dna_cli.py](/Users/jangseongjin/paperpipe/tests/test_research_dna_cli.py)
- [RESEARCH_DNA.md](/Users/jangseongjin/paperpipe/docs/RESEARCH_DNA.md)
- [CLI_WORKFLOW_REFERENCE.md](/Users/jangseongjin/paperpipe/docs/CLI_WORKFLOW_REFERENCE.md)
- [Research_DNA_Rerank_Operator_Guidance_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Research_DNA_Rerank_Operator_Guidance_Stage_Set_2026-04-10.md)

These files are also in scope, but patch-stage-only:

- [main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)

## What Belongs In This Lane

Keep from [research_dna_schema.py](/Users/jangseongjin/paperpipe/src/profiles/research_dna_schema.py):

- `ScreeningQueueVariant` and `RerankGateStatus`
- rerank report and rerank artifacts models
- screening guidance artifact model
- screening queue, next-candidate, session, recommendation, and rerank-gate models

Keep from [research_dna_service.py](/Users/jangseongjin/paperpipe/src/profiles/research_dna_service.py):

- reranked queue materialization:
  - `materialize_reranked_screening_queue(...)`
- guidance audit snapshot materialization:
  - `materialize_screening_guidance_artifact(...)`
- queue/session/guidance readers:
  - `load_screening_queue_artifact(...)`
  - `load_next_screening_candidate(...)`
  - `load_screening_session(...)`
  - `load_screening_recommendation(...)`
  - `load_rerank_gate_report(...)`
  - `load_screening_operator_guidance(...)`
- screening write helpers that return refreshed session state:
  - `submit_screening_decision_and_load_session(...)`
  - `screen_current_candidate_and_load_session(...)`
- stable recommendation and gate summary logic:
  - `primary_reason_code`
  - `primary_warning_code`
  - `recommendation_summary`
  - `gate_summary`

Keep from [research_dna.py](/Users/jangseongjin/paperpipe/src/schemas/research_dna.py):

- additive request and envelope models for:
  - rerank
  - guidance materialization
  - next-candidate
  - screening session
  - screening recommendation
  - screening guidance
  - rerank gate
  - screening advance
  - screening current

Keep from [main.py](/Users/jangseongjin/paperpipe/backend/main.py) as patch hunks only:

- `POST /research-dna/{dna_id}/rerank`
- `POST /research-dna/{dna_id}/guidance/materialize`
- `GET /research-dna/{dna_id}/runs/{run_id}/screening-queue`
- `GET /research-dna/{dna_id}/runs/{run_id}/next-screening-candidate`
- `GET /research-dna/{dna_id}/runs/{run_id}/screening-session`
- `GET /research-dna/{dna_id}/runs/{run_id}/screening-guidance`
- `GET /research-dna/{dna_id}/runs/{run_id}/screening-recommendation`
- `GET /research-dna/{dna_id}/runs/{run_id}/rerank-gate`
- `POST /research-dna/{dna_id}/screening/advance`
- `POST /research-dna/{dna_id}/screening/current`

Leave out from [main.py](/Users/jangseongjin/paperpipe/backend/main.py):

- request-audit logging
- beta auth and browser-rate-limit work
- paper syntheses router work
- home workspace or runtime-readiness additions
- broader downloader or paper-summary changes

Keep from [cli.py](/Users/jangseongjin/paperpipe/src/cli.py) as patch hunks only:

- `paperpipe research-dna rerank`
- `paperpipe research-dna materialize-guidance`
- `paperpipe research-dna queue`
- `paperpipe research-dna next`
- `paperpipe research-dna session`
- `paperpipe research-dna recommend`
- `paperpipe research-dna guidance`
- `paperpipe research-dna rerank-gate`
- `paperpipe research-dna screen-next`
- `paperpipe research-dna screen-current`

Keep from the tests:

- rerank sidecar creation checks
- guidance artifact materialization checks
- queue/session/guidance roundtrip assertions
- stable reason-code and summary-field assertions
- session and current-next screening flow assertions

Keep from the docs:

- operator-surface descriptions for rerank, guidance materialization, queue inspection, recommendation, guidance, rerank-gate, session, screen-next, and screen-current
- the note that these surfaces are additive and advisory-only

## Out Of Scope

Do not include these in the same stage set:

- [project_memory.py](/Users/jangseongjin/paperpipe/src/schemas/project_memory.py)
- [test_project_memory_schema.py](/Users/jangseongjin/paperpipe/tests/test_project_memory_schema.py)
- [test_project_memory_store.py](/Users/jangseongjin/paperpipe/tests/test_project_memory_store.py)
- [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py)
- [test_deepread_state_projection.py](/Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py)
- untracked `BC5CDR` / `BioRED` / `PubTator` extraction replay and bootstrap files

Why these stay out:

- `project_memory` is a raw-memory boundary note, not a Research DNA rerank/operator lane
- deep-read projection changes touch canonical structured state and clinical summary projection, which is a different owner boundary
- extraction replay/bootstrap files widen a different biomedical public-data lane

## Architecture Check

Why this split is safe:

- it preserves the current owner queue as `original`
- it treats `reranked` as an additive sibling artifact
- it keeps the recommendation and gate read-only and advisory-only
- it does not add a new dependency
- it does not promote any new canonical truth store
- it stays within the existing FastAPI-first and Pydantic-first contract

## Verification Re-check

Run these commands for this lane:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_research_dna_service.py::test_materialize_reranked_screening_queue_writes_sibling_artifacts
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_research_dna_api.py::test_research_dna_api_roundtrip_and_pilot
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_research_dna_cli.py::test_research_dna_cli_roundtrip
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
```

## Manual Stage Recipe

If this lane is staged next, do not add `backend/main.py` or `src/cli.py` wholesale from this broad dirty tree.

Use:

```bash
git add /Users/jangseongjin/paperpipe/src/profiles/research_dna_schema.py
git add /Users/jangseongjin/paperpipe/src/profiles/research_dna_service.py
git add /Users/jangseongjin/paperpipe/src/schemas/research_dna.py
git add /Users/jangseongjin/paperpipe/tests/test_research_dna_service.py
git add /Users/jangseongjin/paperpipe/tests/test_research_dna_api.py
git add /Users/jangseongjin/paperpipe/tests/test_research_dna_cli.py
git add /Users/jangseongjin/paperpipe/docs/RESEARCH_DNA.md
git add /Users/jangseongjin/paperpipe/docs/CLI_WORKFLOW_REFERENCE.md
git add -p /Users/jangseongjin/paperpipe/backend/main.py
git add -p /Users/jangseongjin/paperpipe/src/cli.py
git add /Users/jangseongjin/paperpipe/docs/reports/Research_DNA_Rerank_Operator_Guidance_Stage_Set_2026-04-10.md
```

Accept only the Research DNA rerank/operator-guidance hunks described above.

## Short Version

The next coherent tracked lane is the Research DNA rerank/operator-guidance slice:

- materialize a reranked screening sibling artifact
- materialize a run-local screening guidance audit snapshot
- expose advisory recommendation and rerank-gate reads
- let session and screening write flows return the same guidance bundle

This is a real lane, but `backend/main.py` and `src/cli.py` are patch-stage-only because they are shared owner files inside a broad dirty tree.
