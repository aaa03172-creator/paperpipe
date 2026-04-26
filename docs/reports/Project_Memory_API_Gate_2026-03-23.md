# Project Memory API Gate (2026-03-23)

Status: Active
Date: 2026-03-23
Owner: Lattice runtime maintainers
Canonical parent: `docs/archive/Project_Memory_Layer_RFC_2026-03-18.md`

## Purpose

Record whether `Project Memory` should move from the new file-backed backend slice into a thin API lane immediately.

This is a product-shape decision note, not a new runtime spec.

## Current implemented state

Implemented in workspace:
- `src/schemas/project_memory.py`
- `src/project_memory/store.py`
- `src/services/runtime_paths.py::project_memory_root()`
- focused schema/store/runtime-path regression tests

Current storage shape:

```text
storage/project_memory/<project_id>/
  project.json
  memory.jsonl
```

Current bundle contract:
- bounded `pmproj_*` workspace identity
- bounded `pmitem_*` memory-item identity
- explicit `layer="raw_memory"` marker on workspace and item records
- explicit `canonical_status="non_canonical"` marker on workspace and item records
- typed entity links to existing runtime artifacts
- workspace required before item writes
- duplicate `item_id` values rejected
- stray directories without `project.json` ignored by listing

## Decision

Do not open a `Project Memory` API yet.

Keep the lane backend-only at the current schema/store stage until there is an explicit product decision that a project-scoped runtime surface belongs in Lattice.

## Why the API should stay closed for now

### 1. An API would implicitly create a product surface

Even a narrow API such as:
- `POST /projects`
- `GET /projects`
- `GET /projects/{project_id}`
- `POST /projects/{project_id}/memory-items`

would functionally introduce a first-class project workspace model.

That is a bigger product move than the current file-store slice.

### 2. The repo still lacks a canonical project root

Current core runtime remains:
- `papers`
- `jobs`
- `artifacts`
- paper notes
- bounded downstream artifact families

There is still no approved top-level project/workspace contract in the master spec.

Opening a `Project Memory` API now would backdoor that model through implementation momentum instead of an explicit architecture decision.

### 3. Current adjacent systems already own nearby concerns

Current boundaries remain:
- `Research DNA` owns search-design state
- paper notes own paper-scoped knowledge
- `Meeting Pack` owns presentation artifacts
- bounded viewers own review surfaces for their saved artifacts

`Project Memory` is still only a potential cross-artifact decision layer.

That layer has not yet proved enough repeated value to justify immediate runtime surface area.

### 4. File-store maturity does not automatically justify API maturity

The current file-backed slice proves that the schema and storage model are coherent.

It does not yet prove:
- what the minimal request/response surface should be
- whether writes should be append-only or whole-bundle
- whether linked entities need stronger canonicalization before exposure
- whether operators actually need a project-scoped read surface next

## What is safe to do now

Safe now:
- keep the file-backed backend slice
- use it as a bounded implementation reference
- harden schema/store behavior if bugs appear
- keep the lane explicitly marked as raw-memory support data rather than canonical scientific state
- evaluate real use cases against the current bundle shape

Not safe yet:
- opening `/projects` or `/project-memory` routes
- adding a project-memory viewer
- treating `Project Memory` as the owner of cross-artifact truth
- letting this lane silently redefine the product around workspaces

## Reopen conditions

Revisit the API only if at least one of these becomes true:

1. repeated operator workflows need stable project-scoped read/write access across papers, protocol cards, meeting packs, and notes
2. the master spec explicitly approves a bounded project/workspace concept
3. the file-store bundle proves insufficient for real usage and the missing capability is clearly API-shaped rather than viewer-shaped

## Recommended next move

Do not implement `PR-BE-ProjectMemory-API-v0` yet.

Preferred next move:
- hold `Project Memory` at backend file-store v0
- revisit later with a small follow-up decision note once real usage evidence exists

## Conclusion

`Project Memory` now has a defensible backend storage contract.

That is enough to keep the lane alive.

It is not yet enough to justify a first-class API surface.
