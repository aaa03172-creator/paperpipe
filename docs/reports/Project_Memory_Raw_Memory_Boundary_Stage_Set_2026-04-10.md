# Project Memory Raw Memory Boundary Stage Set

Status: exact stage boundary
Date: 2026-04-10
Lane: `project-memory/raw-memory-boundary`
Parent notes:
- [Project_Memory_API_Gate_2026-03-23.md](/Users/jangseongjin/paperpipe/docs/reports/Project_Memory_API_Gate_2026-03-23.md)
- [docs/PaperPipe_Minimum_Operating_Principles.md](/Users/jangseongjin/paperpipe/docs/PaperPipe_Minimum_Operating_Principles.md)

## Purpose

Freeze the smallest remaining `Project Memory` follow-up that makes the lane's raw-memory and non-canonical status explicit in the schema-backed bundle itself.

This note does not stage or commit anything.
It answers one narrower question:

- which remaining `Project Memory` hunks form one safe whole-file micro-lane?

## Diff Re-check Summary

Current re-read result:

- the remaining diff is only three files
- it adds the same explicit boundary defaults to both workspace and item records
- the tests only assert schema normalization and store roundtrip behavior
- it does not open an API surface or a viewer surface

Current judgment:

- this is one bounded micro-lane
- it is additive and review-friendly
- it reinforces the repo's raw-memory versus canonical-state taxonomy
- it does not overlap with the current `deepread_state_projection` follow-up

## Files In Scope

These files belong to this lane:

- [project_memory.py](/Users/jangseongjin/paperpipe/src/schemas/project_memory.py)
- [test_project_memory_schema.py](/Users/jangseongjin/paperpipe/tests/test_project_memory_schema.py)
- [test_project_memory_store.py](/Users/jangseongjin/paperpipe/tests/test_project_memory_store.py)
- [Project_Memory_Raw_Memory_Boundary_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Project_Memory_Raw_Memory_Boundary_Stage_Set_2026-04-10.md)

All of these can be staged as whole files for this micro-lane.

## What Belongs In This Lane

Keep from [project_memory.py](/Users/jangseongjin/paperpipe/src/schemas/project_memory.py):

- `ProjectMemoryItem.layer: Literal["raw_memory"] = "raw_memory"`
- `ProjectMemoryItem.canonical_status: Literal["non_canonical"] = "non_canonical"`
- `ProjectMemoryWorkspace.layer: Literal["raw_memory"] = "raw_memory"`
- `ProjectMemoryWorkspace.canonical_status: Literal["non_canonical"] = "non_canonical"`

Keep from [test_project_memory_schema.py](/Users/jangseongjin/paperpipe/tests/test_project_memory_schema.py):

- assertions that normalized workspace records default to `raw_memory` and `non_canonical`
- assertions that normalized item records default to `raw_memory` and `non_canonical`

Keep from [test_project_memory_store.py](/Users/jangseongjin/paperpipe/tests/test_project_memory_store.py):

- assertions that loaded workspace records preserve `raw_memory` and `non_canonical`
- assertions that loaded item records preserve `raw_memory` and `non_canonical`

## Out Of Scope

Do not include these in the same stage set:

- [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py)
- [test_deepread_state_projection.py](/Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py)
- [main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)

Why these stay out:

- `deepread_state_projection` changes canonical structured-state promotion and artifact projection, so it is a larger separate lane
- `main.py` and `cli.py` still contain broad mixed tails that are not part of the `Project Memory` boundary

## Architecture Check

Why this split is safe:

- it matches the repo's layer taxonomy by making `Project Memory` explicitly raw memory
- it keeps `Project Memory` marked as non-canonical support state rather than scientific truth
- it does not change storage layout or add a new dependency
- it does not change the FastAPI surface

## Verification Re-check

Run these commands for this lane:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_project_memory_schema.py \
  tests/test_project_memory_store.py
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
```

## Manual Stage Recipe

If this lane is staged next, use:

```bash
git add /Users/jangseongjin/paperpipe/src/schemas/project_memory.py
git add /Users/jangseongjin/paperpipe/tests/test_project_memory_schema.py
git add /Users/jangseongjin/paperpipe/tests/test_project_memory_store.py
git add /Users/jangseongjin/paperpipe/docs/reports/Project_Memory_Raw_Memory_Boundary_Stage_Set_2026-04-10.md
```

## Short Version

The remaining `Project Memory` follow-up is a clean 3-file raw-memory boundary lane:

- mark workspace and item bundles as `raw_memory`
- mark workspace and item bundles as `non_canonical`
- verify the defaults survive schema normalization and store roundtrips

This is a whole-file micro-lane and should stay separate from `deepread_state_projection`.
