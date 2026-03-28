# Deepread Handoff Artifacts Closeout (2026-03-28)

Status: docs-only closeout  
Date: 2026-03-28  
Owner: Lattice runtime maintainers  
Runtime slice anchor: merged PR `#201` (`feat(runtime): write deepread handoff artifacts`)

## Purpose

Close the shared-docs gap for the already-merged deepread handoff artifact slice.

This note exists to make the new handoff contract legible without reopening broader deepread/runtime design.

This is not:
- a new deepread spec
- a new promotion policy
- a reason to reopen parser, note-viewer, or installability lanes

## What the merged slice writes

For successful deepread runs, the runtime now writes two additional artifact sidecars under:

`storage/artifacts/<paper_id>/<run_id>/`

- `acceptance_contract.json`
- `quality_gate.json`

These are written by:
- [deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py)
- [deepread_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/deepread_handoff.py)

The handoff sidecars do not replace the existing artifact bundle. They sit next to:
- `document_artifact.json`
- `index_artifact.json`
- `claimset.json`
- `claimset.resolved.json`
- `reader_eval.json`
- `run_meta.json`
- `bootstrap_meta.json`
- `stats_report.json` when verification was requested

## Current contract summary

### `acceptance_contract.json`

This sidecar records the bounded promotion contract for the current deepread run:
- requested scope such as `run_verify`, `clean_reindex_requested`, `persona_id`, and `parser_backend`
- expected outputs for the run
- acceptance checks that define whether the artifact bundle reached the minimum handoff state

Current acceptance checks include:
- `run_succeeded`
- `claimset_resolved_written`
- `claimset_ready`
- `reader_eval_written` (optional)
- `verification_completed` when `run_verify=true`

### `quality_gate.json`

This sidecar records the current promotion/review gate summary for the same run:
- `overall_status`
- `current_promotion_candidate`
- `review_ready`
- `reason_codes`
- per-check statuses such as `run_succeeded`, `claimset_resolved_written`, `claimset_ready`, `reader_eval_written`, and `verification_completed`

The current gate semantics are intentionally narrow:
- `current_promotion_candidate` means the run succeeded and `claimset.resolved.json` exists
- `review_ready` means promotion-candidate plus `claimset_ready`, plus completed verification when verification was requested

## Shared metadata impact

`bootstrap_meta.json` now carries explicit booleans so downstream consumers can observe whether these handoff sidecars were written:
- `artifact_claimset_resolved_written`
- `artifact_reader_eval_written`
- `artifact_acceptance_contract_written`
- `artifact_quality_gate_written`

This docs closeout updates [bootstrap_meta_schema.md](/Users/jangseongjin/paperpipe/docs/bootstrap_meta_schema.md) so those fields are no longer runtime-only knowledge.

## Downstream consumer impact

The current deepread state-projection path already consumes the new handoff artifacts.

Specifically, [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py):
- records `acceptance_contract_path` and `quality_gate_path` in the run artifact map
- surfaces `quality_gate_status`, `review_ready`, and `current_promotion_candidate`
- carries the new bootstrap-meta booleans into projected signals

This means the new handoff sidecars are:
- part of runtime observability
- part of bounded deepread promotion/state visibility
- not yet a separate product-facing workflow

## Verification anchors

Code/test anchors for this merged slice:
- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py)
- [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py)
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py)
- [test_deepread_state_projection.py](/Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py)

Docs-only verification for this closeout:
- `git diff --check`
- touched-doc docs reference audit: `NO_NEW_MISSING_DOC_REFS`

## Out of scope

- changing the deepread runtime contract
- adding new gate semantics
- promoting these sidecars to a new canonical product surface
- reopening broader deepread UX or orchestration work

## Bottom line

The deepread handoff artifact lane is now shared-doc visible.

Future work should treat `acceptance_contract.json` and `quality_gate.json` as current runtime observability artifacts for deepread promotion/state projection, not as a reason to reopen broader runtime redesign.
