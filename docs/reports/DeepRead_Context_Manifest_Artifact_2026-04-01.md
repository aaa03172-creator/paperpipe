# Deep Read Context Manifest Artifact

Status: additive runtime observability note
Date: 2026-04-01
Owner: runtime/backend maintainers
Canonical parents:
- `docs/reports/External_Reference_Action_Order_2026-04-01.md`
- `docs/reports/Local_Deep_Read_Runtime_Measurement_2026-03-28.md`
- `docs/reports/Reader_Attempt_Order_RFC_2026-03-28.md`

## Purpose

Add a compact artifact that summarizes deep-read context assembly without changing runtime behavior.

This note is intentionally narrow.

It is not:
- a new runtime policy
- a replacement for `reader_analysis`
- a reason to reopen generalized session memory or agent orchestration work

It answers one smaller need:
- when a deep-read run is slow or fragile, can an operator quickly see what context was actually sent without digging through raw metrics?

## Current repo reality

Before this change, the repo already recorded:

- `reader_analysis` in:
  - `bootstrap_meta.json`
  - `run_meta.json`
- attempt-level fields such as:
  - `configured_attempt_order`
  - `effective_attempt_order`
  - `context_mode`
  - `included_chunk_count`
  - `unique_section_count`
  - `sentence_focus_count`
  - `truncated_chunk_count`

That was useful, but still awkward in practice because:

- operators had to inspect a large nested metrics object
- there was no single artifact dedicated to context composition
- state projection and handoff bundles could not point at a compact context summary directly

## What changed

Deep-read handoff writing now emits `context_manifest.json` when `reader_analysis` is present.

The artifact records:

- configured attempt order
- effective attempt order
- attempt count
- selected attempt index and label
- return mode
- final claim count
- heuristic fallback usage
- per-attempt context summary:
  - context mode
  - context chars
  - prompt chars
  - estimated prompt tokens
  - estimated response tokens
  - chunk count
  - section count
  - page-hint count
  - sentence-focus count
  - truncated chunk count

The selected attempt is also promoted into a top-level `selected_attempt_summary` entry so the common debugging path stays compact.

## Why this shape

This keeps the change inside the existing paper/run/artifact model:

- no runtime default changed
- no storage migration was introduced
- no canonical state rules changed
- no chat/session memory lane was opened

The new artifact is derived, not canonical.

`reader_analysis` remains the source metrics payload.
`context_manifest.json` is the bounded operator-facing projection.

## Integration points

- handoff writing:
  - `src/services/deepread_handoff_artifacts.py`
- schema:
  - `src/schemas/deepread_handoff.py`
- state projection:
  - `src/services/deepread_state_projection.py`

## Expected use

Use `context_manifest.json` first when checking:

- why a run selected `focused` vs `primary`
- whether truncation likely contributed to a weak run
- whether a run used sentence-focus context at all
- whether an outlier run had unusually high chunk or section breadth

Only fall back to full `reader_analysis` when the compact manifest is insufficient.

## Not concluded from this change

This does not prove:

- that current context assembly is optimal
- that `focused_first` should become the default order
- that local runtime bottlenecks are fully explained

It only makes the current bounded runtime easier to inspect.
