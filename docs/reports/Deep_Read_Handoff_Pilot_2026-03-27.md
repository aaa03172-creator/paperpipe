Status: Active bounded pilot note
Date: 2026-03-27
Owner: Lattice runtime maintainers
Purpose: record the smallest pilot that borrows structured-handoff and bounded quality-gate ideas for the deep-read lane without introducing a generic planner/generator/evaluator framework.

## Scope

This pilot is intentionally narrow.

It adds two additive artifacts to the existing deep-read run bundle:
- `acceptance_contract.json`
- `quality_gate.json`

It does not:
- change canonical product shape
- add a planner agent
- add a generic multi-agent runner
- reopen chat or memory lanes
- replace existing `run_meta.json`, `bootstrap_meta.json`, `reader_eval.json`, or note-side `state.json`

## Current Contract

The pilot is bounded to the deep-read lane in:
- `backend/services/job_runner.py`
- `src/services/deepread_state_projection.py`

Current intent:
- make the current acceptance shape more legible
- compact existing verification/readiness signals into one additive quality summary
- preserve the current promotion rule instead of silently tightening it

## Artifact Semantics

### `acceptance_contract.json`

This file records:
- requested scope
- expected outputs
- bounded acceptance checks
- the current promotion and review-ready rule

It is not a new source of truth.
It is a run-local handoff contract for operator/debug use.

### `quality_gate.json`

This file records:
- compact pass/warn/fail-like check results
- whether the run is a `current_promotion_candidate`
- whether it is `review_ready`
- reason codes for the bounded gate summary

This file is additive observability metadata.
It does not replace `run_meta.json`, `bootstrap_meta.json`, `reader_eval.json`, or canonical paper state.

## Current Rules

- `current_promotion_candidate` follows the current runtime rule:
  - run succeeded
  - `claimset.resolved.json` exists
- `review_ready` is stricter:
  - promotion candidate
  - `claimset_ready = true`
  - verifier completed when `run_verify=true`

This means the pilot can distinguish:
- promotable but not review-ready
- review-ready
- not promotable

without changing the existing runtime promotion boundary.

## Why this fits the repo

- It reuses the current paper/job/artifact model.
- It reinforces structured handoff over chat memory.
- It strengthens verifier visibility without introducing a generic evaluator framework.
- It keeps the product paper-centered and biomedical-workflow-centered.

## Verification

Targeted verification for this pilot:

```bash
pytest -q tests/test_deepread_handoff_artifacts.py tests/test_worker_job_runner_chain.py tests/test_deepread_state_projection.py
python3 scripts/lint_docs.py
```

Runtime validation on a representative real paper also passed:

- paper: `zotero:coricTargetingProdromalAlzheimer2015`
- run: `run_20260327_025914`
- job: `427b4b09-c92c-4a5c-9983-fa1bd2765839`
- result: `completed`
- bundle path:
  - `storage/artifacts/zotero:coricTargetingProdromalAlzheimer2015/run_20260327_025914/`
- observed pilot outputs:
  - `acceptance_contract.json`
  - `quality_gate.json`
- observed gate summary:
  - `overall_status = pass`
  - `review_ready = true`
  - `current_promotion_candidate = true`
- observed promoted state summary:
  - note-side `.pp/<slug>/state.json` contains
    - `artifact_acceptance_contract_written = true`
    - `artifact_quality_gate_written = true`
    - `quality_gate_status = "pass"`
    - `quality_gate_review_ready = true`
    - `quality_gate_current_promotion_candidate = true`

This runtime validation confirms that the pilot artifacts are not only test-backed but also emitted and surfaced in the current real deep-read path.

## Next Reopen Condition

Only broaden this pilot if the additive artifacts clearly improve:
- promotion diagnosis
- retry stability
- operator trust in why a run is usable or not

Without that evidence, keep the pilot bounded to deep-read only.
