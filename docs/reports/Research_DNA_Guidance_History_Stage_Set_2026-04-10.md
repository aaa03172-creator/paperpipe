# Research DNA Guidance History Stage Set

Status: exact stage boundary
Date: 2026-04-10
Lane: `research-dna/guidance-history`
Parent notes:
- [Research_DNA_Rerank_Operator_Guidance_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Research_DNA_Rerank_Operator_Guidance_Stage_Set_2026-04-10.md)
- [RESEARCH_DNA.md](/Users/jangseongjin/paperpipe/docs/RESEARCH_DNA.md)

## Purpose

Freeze the remaining Research DNA follow-up that improves how screening-guidance audit snapshots are materialized and retained.

This note does not stage or commit anything.
It answers one narrower question:

- after the committed rerank/operator-guidance lane, which remaining Research DNA hunks still form one coherent micro-lane?

## Diff Re-check Summary

Current re-read result:

- the remaining diff is small and self-contained
- it changes guidance materialization from a single overwritten file into timestamped snapshots
- it adds a simple run-local history index for those snapshots
- it keeps manifest and metrics pointed at the latest snapshot while preserving older snapshots in the run directory
- it adds a guard that rejects invalid or mismatched guidance-index identity

Current judgment:

- this is one bounded micro-lane
- it is additive and review-friendly
- it does not change the canonical owner model for `ResearchDNA`
- it does not reopen the broader rerank/operator-guidance lane

## Files In Scope

These files belong to this lane:

- [RESEARCH_DNA.md](/Users/jangseongjin/paperpipe/docs/RESEARCH_DNA.md)
- [research_dna_schema.py](/Users/jangseongjin/paperpipe/src/profiles/research_dna_schema.py)
- [research_dna_service.py](/Users/jangseongjin/paperpipe/src/profiles/research_dna_service.py)
- [test_research_dna_service.py](/Users/jangseongjin/paperpipe/tests/test_research_dna_service.py)
- [Research_DNA_Guidance_History_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Research_DNA_Guidance_History_Stage_Set_2026-04-10.md)

All of these can be staged as whole files for this micro-lane.

## What Belongs In This Lane

Keep from [research_dna_schema.py](/Users/jangseongjin/paperpipe/src/profiles/research_dna_schema.py):

- `ResearchDNAScreeningGuidanceIndexEntry`
- `ResearchDNAScreeningGuidanceIndexArtifact`

Keep from [research_dna_service.py](/Users/jangseongjin/paperpipe/src/profiles/research_dna_service.py):

- timestamped `screening_guidance_<timestamp>.json` path generation
- collision-safe fallback when a timestamped filename already exists
- `screening_guidance_index.json` read/validate/update flow
- manifest updates for:
  - latest guidance snapshot path
  - guidance index path
  - guidance history count
- metrics updates for:
  - latest guidance snapshot path
  - guidance index path
  - guidance history count
- invalid-index guard when stored run identity does not match the current run

Keep from [test_research_dna_service.py](/Users/jangseongjin/paperpipe/tests/test_research_dna_service.py):

- assertions that the guidance artifact path becomes timestamped
- assertions that a second materialization preserves the first snapshot and creates a new one
- assertions that manifest and metrics now point at the latest snapshot and index
- assertions that the new history index contains both snapshots
- assertions that an invalid guidance index raises `ResearchDNAStateError`

Keep from [RESEARCH_DNA.md](/Users/jangseongjin/paperpipe/docs/RESEARCH_DNA.md):

- the operator note that guidance materialization now writes timestamped snapshots
- the note that manifest/metrics point to the latest snapshot
- the note that `screening_guidance_index.json` keeps bounded history

## Out Of Scope

Do not include these in the same stage set:

- [main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- [project_memory.py](/Users/jangseongjin/paperpipe/src/schemas/project_memory.py)
- [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py)
- [test_project_memory_schema.py](/Users/jangseongjin/paperpipe/tests/test_project_memory_schema.py)
- [test_project_memory_store.py](/Users/jangseongjin/paperpipe/tests/test_project_memory_store.py)
- [test_deepread_state_projection.py](/Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py)

Why these stay out:

- `main.py` and `cli.py` are already aligned with the previous committed operator-guidance lane and their current dirty tails belong elsewhere
- `project_memory` is a separate raw-memory boundary
- deep-read projection changes touch canonical structured-state promotion rather than Research DNA guidance audit history

## Architecture Check

Why this split is safe:

- it keeps `ResearchDNA` as the same canonical owner
- it treats guidance snapshots as additive audit artifacts
- it does not add a new dependency
- it does not change API surface shape
- it preserves the current FastAPI-first and Pydantic-first contract

## Verification Re-check

Run these commands for this lane:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_research_dna_service.py::test_materialize_reranked_screening_queue_writes_sibling_artifacts
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
```

## Manual Stage Recipe

If this lane is staged next, use:

```bash
git add /Users/jangseongjin/paperpipe/docs/RESEARCH_DNA.md
git add /Users/jangseongjin/paperpipe/src/profiles/research_dna_schema.py
git add /Users/jangseongjin/paperpipe/src/profiles/research_dna_service.py
git add /Users/jangseongjin/paperpipe/tests/test_research_dna_service.py
git add /Users/jangseongjin/paperpipe/docs/reports/Research_DNA_Guidance_History_Stage_Set_2026-04-10.md
```

## Short Version

The remaining Research DNA follow-up after `9f9d3e9` is a small guidance-history lane:

- preserve each guidance snapshot as a timestamped file
- keep a bounded history index
- keep manifest and metrics pointed at the latest snapshot
- reject mismatched guidance-index identity

This is a clean whole-file micro-lane and does not need patch-stage handling.
