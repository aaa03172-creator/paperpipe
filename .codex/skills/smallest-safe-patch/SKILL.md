---
name: smallest-safe-patch
description: Strict workflow for making small, defensible PaperPipe changes without drifting into rewrites. Use for bugs or incremental features that need map-first scoping, minimal edits, architecture review, and smallest-relevant verification.
---

# Smallest Safe Patch

## Overview

Use this skill to keep implementation scoped and reversible.
It is for additive fixes and incremental features, not subsystem redesign.

## Trigger Conditions

Use this skill when:
- a user wants a bug fixed or a narrow feature added
- the change should preserve the current PaperPipe architecture
- there is a risk of editing too broadly or rewriting a working path

## Inputs And Expected Context

Start with:
- the target behavior
- the owning code path
- the intended user-visible or contract-visible outcome

If the owning code path is unclear, map it before editing.

## Output Contract

State these items during the work:
1. `Mapped scope`
2. `Planned patch`
3. `Architecture check`
4. `Verification`
5. `Remaining risk`

## Workflow

1. Map before editing.
   Use `code_mapper` or equivalent read-only exploration to identify the exact files, symbols, and boundaries that own the behavior.
2. Patch the owner, not the neighborhood.
   Edit the smallest set of files that can safely change the behavior.
3. Preserve contracts.
   Keep FastAPI-first logic, Pydantic schemas, note idempotency, and existing runtime boundaries intact unless the task explicitly authorizes a contract change.
4. Run an architecture check.
   Ask `architecture_guardian` or perform an equivalent conservative review for rewrite risk, schema drift, storage migration, or dependency creep.
5. Verify the smallest relevant behavior first.
   Prefer a targeted test, smoke check, or build step that matches the touched surface.

Read [references/patch-checklist.md](references/patch-checklist.md) before broad edits, contract-visible changes, or when the scope starts growing.

## Guardrails And Non-Goals

- Do not replace a working subsystem as the first move.
- Do not expand scope just because nearby cleanup is tempting.
- Do not turn a local Codex workflow file into runtime product logic.
- Do not claim verification that did not actually run.

## Verification Or Handoff

When closing the task, separate:
- what changed
- what was verified
- what was not verified
- how to roll back or disable the change if needed
