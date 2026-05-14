# Specialty Runtime Posture Decision

Status: operational posture
Date: 2026-03-29
Lane: `smallest-safe-patch`

## Current Decision

- Treat the sixteen-document sidecar extraction baseline as the canonical extraction signoff lane.
- Keep runtime specialty promotion blocked.
- Reopen runtime specialty only through an explicit Coric-only RFC.

This is a posture decision, not a claim that runtime specialty repair is impossible.
It means the current evidence is strong enough to define what we should do by default:

- use the sidecar lane for extraction regression and quality signoff
- do not widen or promote the runtime specialty lane by default
- if runtime specialty is reopened, keep the scope bounded and staged

## Why This Is The Safe Default

Current runtime-promotion gate:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/extraction_runtime_promotion_gate/extraction_runtime_promotion_gate_20260329_r2/summary.json)

Current gate result:

- `decision.promotion_ready=false`
- blockers:
  - `no_persisted_runtime_specialty_artifact`
  - `no_materialized_specialty_shadow_artifact`
  - `materialized_shadow_schema_invalid`
  - `runtime_specialty_feature_disabled`

This means runtime specialty still fails the basic readiness test even after all bounded shadow diagnostics currently in place.

## What Is Already Proven

### Canonical Sidecar Baseline

Current canonical extraction baseline:

- [metrics.json](/Users/jangseongjin/paperpipe/snapshots/extraction_regression_eval/extraction_repo_grounded_preclinical_therapeutic_realpred_20260328_r1_repair29/metrics.json)

Bounded result:

- `document_count=16`
- mismatch buckets all `0`
- core field match rate `population/intervention/outcome/sample_size/duration = 1.0`

This is the strongest current extraction signoff lane.

### Coric-Only Shadow RFC Viability

Current Coric semantic shadow evidence:

- semantic shadow summary:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/extraction_runtime_shadow_semantic_repair/extraction_specialty_runtime_shadow_semantic_repair_20260329_r1/summary.json)
- semantic shadow compare:
  [metrics.json](/Users/jangseongjin/paperpipe/snapshots/extraction_regression_eval/extraction_specialty_runtime_shadow_semantic_repair_compare_20260329_r1/metrics.json)

What this proves:

- the Coric specialty output can be made schema-valid in a developer-only shadow lane
- a second source-grounded semantic pass can recover the missing core fields
- the current gate now records this as advisory evidence:
  - `semantic_shadow.semantic_prediction_written_count=1`
  - `semantic_shadow.compare_passed=true`
  - `semantic_shadow.two_step_rfc_viable=true`

What this does **not** prove:

- it does not make runtime specialty promotion-ready
- it does not mean the current runtime path can already persist a comparable specialty artifact on its own

## Default Operating Rule

Use this rule until the posture is explicitly changed:

1. For extraction regression signoff, use the sixteen-document sidecar baseline.
2. Do not promote runtime specialty based on shadow success alone.
3. Do not widen runtime specialty work to additional papers or general runtime paths by default.
4. Treat the promotion gate as authoritative for readiness, and the semantic-shadow section as advisory evidence only.

## Reopen Conditions

Runtime specialty may be reopened only if all of the following are true:

1. The work is explicitly scoped as a Coric-only RFC.
2. The RFC is split into two steps:
   - legacy shape adapter
   - source-grounded semantic repair
3. The result is re-evaluated against the existing promotion gate rather than assumed promotable from shadow evidence alone.

## Do Not Rewrite These Parts

- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [llm_provider.py](/Users/jangseongjin/paperpipe/src/llm_provider.py)
- current FastAPI API surface
- current Pydantic extraction contracts under [src/schemas](/Users/jangseongjin/paperpipe/src/schemas)
- the canonical sidecar extraction baseline and its current fixture set

## Short Version

PaperPipe should continue to treat the sidecar extraction lane as canonical and the runtime specialty lane as blocked.
If runtime specialty comes back onto the table, it should come back only as a Coric-only, two-step RFC.
