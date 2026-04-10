# Deep Read State Projection Clinical Handoff Stage Set

Status: exact stage boundary
Date: 2026-04-10
Lane: `deepread-state-projection/clinical-handoff`
Parent notes:
- [DeepRead_Context_Manifest_Artifact_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Context_Manifest_Artifact_2026-04-01.md)
- [Clinical_Evidence_Extraction_Stage_Set_2026-04-09.md](/Users/jangseongjin/paperpipe/docs/reports/Clinical_Evidence_Extraction_Stage_Set_2026-04-09.md)

## Purpose

Freeze the remaining `deepread_state_projection` follow-up that makes canonical state promotion aware of handoff review artifacts, optional clinical extraction output, and visible-state filtering.

This note does not stage or commit anything.
It answers one narrower question:

- which remaining projection hunks form one safe whole-file micro-lane?

## Diff Re-check Summary

Current re-read result:

- the remaining diff is only two source files plus this note
- it projects `quality_gate.json`, `context_manifest.json`, and optional `clinical_extraction.json` into run artifacts, run data, and top-level signals
- it enriches the projected run summary with handoff gate and clinical condition cues
- it filters existing structured state through `visible_structured_state(...)` before deciding whether promotion should refresh or skip
- it preserves existing `reading_assists` when a promoted deep-read refresh replaces a prior visible promoted state

Current judgment:

- this is one bounded micro-lane
- it is additive and review-friendly
- it strengthens canonical-state projection without changing runtime ownership
- it does not require patch-stage handling from the current dirty tree

## Files In Scope

These files belong to this lane:

- [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py)
- [test_deepread_state_projection.py](/Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py)
- [DeepRead_State_Projection_Clinical_Handoff_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_State_Projection_Clinical_Handoff_Stage_Set_2026-04-10.md)

All of these can be staged as whole files for this micro-lane.

## What Belongs In This Lane

Keep from [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py):

- optional `BiomedicalClinicalExtraction` loading from `clinical_extraction.json`
- optional `quality_gate.json` loading and projection
- optional `context_manifest.json` artifact-path projection
- projected run summary additions for gate and clinical condition
- projected run `artifacts` additions for acceptance contract, quality gate, context manifest, and clinical extraction
- projected run `data` additions for gate and clinical extraction fields
- projected top-level `signals` additions for gate and clinical extraction fields
- `visible_structured_state(...)` filtering before promotion ownership checks
- preservation of existing `reading_assists` during promoted deep-read refresh
- `_load_biomedical_clinical_extraction(...)`
- `_build_clinical_extraction_summary(...)`

Keep from [test_deepread_state_projection.py](/Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py):

- fixture coverage for `quality_gate.json`, `context_manifest.json`, and `clinical_extraction.json`
- assertions that projected run artifacts include clinical and context-manifest paths
- assertions that projected run data and top-level signals include gate and clinical extraction fields
- assertions that promoted state keeps the projected clinical summary
- regression coverage that refresh preserves existing `reading_assists`
- regression coverage that hidden fixture state is ignored by promotion

## Out Of Scope

Do not include these in the same stage set:

- [main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- [project_memory.py](/Users/jangseongjin/paperpipe/src/schemas/project_memory.py)
- [test_project_memory_schema.py](/Users/jangseongjin/paperpipe/tests/test_project_memory_schema.py)
- [test_project_memory_store.py](/Users/jangseongjin/paperpipe/tests/test_project_memory_store.py)

Why these stay out:

- `main.py` and `cli.py` still carry broad mixed tails unrelated to state projection
- `Project Memory` was already split into its own raw-memory boundary lane

## Architecture Check

Why this split is safe:

- it keeps schema-backed structured state as the canonical projection target
- it treats handoff review artifacts as additive projected metadata, not replacement truth
- it keeps clinical extraction optional and derived from existing run artifacts
- it avoids promoting hidden fixture state into visible canonical ownership
- it preserves visible `reading_assists` instead of discarding user-facing reading help on refresh

## Verification Re-check

Run these commands for this lane:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q tests/test_deepread_state_projection.py
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
```

## Manual Stage Recipe

If this lane is staged next, use:

```bash
git add /Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py
git add /Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py
git add /Users/jangseongjin/paperpipe/docs/reports/DeepRead_State_Projection_Clinical_Handoff_Stage_Set_2026-04-10.md
```

## Short Version

The remaining `deepread_state_projection` follow-up is a clean whole-file lane:

- project handoff gate and context artifacts into canonical state metadata
- project optional clinical extraction summary into run data and state signals
- ignore hidden fixture state during promotion
- preserve visible `reading_assists` during deep-read refresh

This lane is separate from the broad `main.py` and `cli.py` tails.
