# Deepread Runtime Follow-Ups Closeout (2026-03-28)

Status: docs-only closeout  
Date: 2026-03-28  
Owner: Lattice runtime maintainers  
Runtime slice anchors:
- merged PR `#202` (`feat(runtime): persist deepread reader analysis metrics`)
- merged PR `#204` (`feat(runtime): write stats fallback eval sidecar`)
- merged PR `#205` (`refactor(runtime): normalize deepread persona selection`)

## Purpose

Close the shared-docs gap for the latest deepread runtime follow-ups that landed after the handoff-artifact closeout.

This note exists so these runtime observability additions do not remain code-only knowledge.

This is not:
- a new deepread master spec
- a new promotion policy
- a reason to reopen broader runtime, parser, or viewer lanes

## What changed in runtime

The recent merged slices added three bounded runtime follow-ups:

1. Persona selection normalization
   - deepread runtime now persists:
     - `persona_id`
     - `reasoning_persona`
     - `profile_id`
   - `persona_id` remains as a compatibility alias, while reasoning lane and profile context are recorded separately

2. Reader analysis metrics persistence
   - when the reader agent exposes `last_analysis_metrics`, the runtime now writes that payload into:
     - `bootstrap_meta.json`
     - `run_meta.json`
   - this keeps reader attempt behavior inspectable without reopening reader design

3. Verification fallback-eval sidecar
   - verifier runs now write:
     - `stats_fallback_eval.json`
   - the bootstrap metadata also records bounded summary counters for that sidecar

## Current shared-contract summary

### Persona selection fields

The current deepread selection metadata should be interpreted as:
- `persona_id`: compatibility alias for the selected request surface
- `reasoning_persona`: current reasoning lane
- `profile_id`: current profile-context overlay

This preserves older surfaces that still expect `persona_id` while making the split selection explicit for newer runtime consumers.

### `reader_analysis`

`reader_analysis` is a bounded runtime-observability payload copied from the reader agent when available.

Typical values include:
- `return_mode`
- `attempt_count`
- `selected_attempt`
- `selected_attempt_label`
- `final_claim_count`
- attempt-level parsed-status summaries

Current role:
- runtime inspection
- replay/debug visibility
- additive metadata only

It is not:
- a new canonical scientific artifact
- a replacement for `claimset.json`
- a reason to widen reader policy or UI scope

### `stats_fallback_eval.json`

The verification lane now emits `stats_fallback_eval.json` as a bounded sidecar summarizing fallback-related verification outcomes.

Current sidecar structure includes:
- run identity fields
- fallback context (`table_extraction_pass`, taxonomy, fallback pages)
- per-check entries with:
  - `check_id`
  - `verdict`
  - `method`
  - `notes`
  - `auto_fallback`
  - `fallback_reason`
- aggregate metrics such as:
  - `check_count`
  - `unverifiable_count`
  - `auto_fallback_count`
  - `no_table_count`
  - `no_api_context_count`

The bootstrap metadata now records summary booleans/counts for this sidecar:
- `artifact_stats_fallback_eval_written`
- `stats_fallback_eval_check_count`
- `stats_fallback_eval_unverifiable_count`
- `stats_fallback_eval_auto_fallback_count`

## Shared-doc updates in this closeout

This closeout updates [bootstrap_meta_schema.md](/Users/jangseongjin/paperpipe/docs/bootstrap_meta_schema.md) so the following are no longer runtime-only knowledge:
- persona selection split (`persona_id`, `reasoning_persona`, `profile_id`)
- bounded `reader_analysis` payload
- `stats_fallback_eval` bootstrap summary fields

## Verification anchors

Code/test anchors for these merged slices:
- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [stats_fallback_eval.py](/Users/jangseongjin/paperpipe/src/schemas/stats_fallback_eval.py)
- [stats_fallback_eval_sidecar.py](/Users/jangseongjin/paperpipe/src/services/stats_fallback_eval_sidecar.py)
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py)
- [test_stats_fallback_eval_sidecar.py](/Users/jangseongjin/paperpipe/tests/test_stats_fallback_eval_sidecar.py)
- [test_job_runner_persona.py](/Users/jangseongjin/paperpipe/tests/test_job_runner_persona.py)

Docs-only verification for this closeout:
- `git diff --check`
- touched-doc docs reference audit: `NO_NEW_MISSING_DOC_REFS`

## Out of scope

- changing deepread runtime behavior
- widening deepread promotion semantics
- adding new viewer/debug surfaces for reader analysis or fallback eval
- reopening parser, OpenDataLoader, Docling, or installability work

## Bottom line

The latest deepread runtime follow-ups are now shared-doc visible.

Future work should treat:
- `reader_analysis`
- `stats_fallback_eval.json`
- split persona selection metadata

as bounded runtime observability aids, not as new product centers.
