# Reader Eval Sidecar Real Replay (Park)

Status: Completed bounded replay
Date: 2026-03-23
Branch observed: `codex/agents-smoke-ci-check`

## 0. Purpose

Validate the newly added reader evaluation sidecar on one existing real artifact run without reopening runtime scope.

This replay is bounded to an existing deep-read artifact and uses offline artifact inputs only.

## 1. Replay Target

Paper:
- `zotero:parkDiscoveryDualactionSmall2022`

Run:
- `run_20260313_110600`

Artifact directory:
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_110600`

Inputs consumed:
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_110600/claimset.json`
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_110600/claimset.resolved.json`
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_110600/index_artifact.json`

Output written:
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_110600/reader_eval.json`

## 2. Result

Replay succeeded.

Observed metrics:
- `claim_count=1`
- `supported_claim_count=1`
- `unsupported_claim_count=0`
- `unknown_claim_count=0`
- `heuristic_backfill_claim_count=0`
- `evidence_span_count=1`
- `grounded_span_count=1`
- `unresolved_span_count=0`
- `ambiguous_span_count=0`
- `failed_grounding_span_count=0`
- `limitation_count=0`
- `grounded_limitation_count=0`
- `low_overlap_claim_count=0`

Claim-level result:
- `claim_id=CLM-001`
- `grounding_resolutions=["OK"]`
- `statement_evidence_overlap_ratio=0.8`
- `low_statement_evidence_overlap=false`

## 3. Interpretation

This run is a good bounded smoke for the new sidecar because:
- it uses an existing real artifact rather than a synthetic-only fixture
- it confirms that the sidecar can be derived entirely from offline artifacts
- it produces a grounded and supported claim path with no heuristic backfill

This run is not enough to validate the full usefulness of the sidecar because:
- it contains only one claim
- it does not exercise unsupported claims
- it does not exercise ambiguous grounding
- it does not exercise heuristic fallback or policy-driven `unknown_reason`

## 4. What This Validates

Validated now:
- offline replay path works
- sidecar schema is usable on a real artifact run
- grounded/support metrics line up with the existing resolved claimset
- sidecar generation does not require changing the core reader runtime design

Not yet validated:
- unsupported-claim detection on a real run
- heuristic backfill accounting on a real run
- limitation grounding on a real run
- usefulness of aggregate metrics across multiple papers

## 5. Immediate Next Step

The next bounded step should be one of these:
1. replay the sidecar across a small curated set that includes at least one `unknown` or heuristic-fallback case
2. start `Workstream 2` and add stats fallback taxonomy sidecars in the same bounded fashion

Recommended order remains:
1. expand reader sidecar replay to a small mixed-quality sample
2. then start stats fallback taxonomy logging
