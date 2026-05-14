# Reader Eval Sidecar Mixed Replay Batch

Status: Completed bounded replay batch
Date: 2026-03-23
Branch observed: `codex/agents-smoke-ci-check`

## 0. Purpose

Extend the initial reader sidecar replay from a single clean run to a small mixed-quality sample.

This batch stays bounded to existing offline artifacts and does not reopen runtime scope.

## 1. Batch Composition

Included runs:
1. `1411.2441 / run_live_sample`
2. `zotero:parkDiscoveryDualactionSmall2022 / run_20260313_104454`
3. `zotero:parkDiscoveryDualactionSmall2022 / run_20260313_110307`

Selection rationale:
- one `unknown(EVIDENCE_MISSING)` case
- one `AMBIGUOUS_MATCH` grounding case
- one `FAILED_MATCH` grounding case

Note:
- no existing real artifact with `HEURISTIC_BACKFILL` was found in the current bounded scan
- this batch therefore does not yet validate the heuristic-backfill branch on real artifacts

## 2. Outputs Written

- `/Users/jangseongjin/paperpipe/storage/artifacts/1411.2441/run_live_sample/reader_eval.json`
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_104454/reader_eval.json`
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_110307/reader_eval.json`

Special note:
- `1411.2441/run_live_sample` did not contain `claimset.resolved.json`
- for that run, the replay used offline in-memory grounding from `claimset.json + index_artifact.json`
- no canonical runtime artifact was rewritten apart from the additive `reader_eval.json`

## 3. Batch Results

### 3.1 Unknown / unsupported case

Run:
- `1411.2441 / run_live_sample`

Observed metrics:
- `claim_count=1`
- `supported_claim_count=0`
- `unsupported_claim_count=1`
- `unknown_claim_count=1`
- `evidence_span_count=0`
- `grounded_span_count=0`
- `low_overlap_claim_count=1`

Claim-level result:
- `unknown_reason=EVIDENCE_MISSING`
- `grounding_resolutions=[]`
- `statement_evidence_overlap_ratio=0.0`

Interpretation:
- the sidecar correctly isolates the policy-driven unsupported path
- this is useful because it distinguishes missing evidence from grounding failure

### 3.2 Ambiguous grounding case

Run:
- `zotero:parkDiscoveryDualactionSmall2022 / run_20260313_104454`

Observed metrics:
- `claim_count=1`
- `supported_claim_count=1`
- `unsupported_claim_count=0`
- `unknown_claim_count=0`
- `grounded_span_count=0`
- `unresolved_span_count=1`
- `ambiguous_span_count=1`
- `failed_grounding_span_count=0`

Claim-level result:
- `grounding_resolutions=["AMBIGUOUS_MATCH"]`
- `statement_evidence_overlap_ratio=0.6`

Interpretation:
- the sidecar cleanly separates a supported claim from a failed final grounding decision
- this is the main reason the sidecar is useful: supported/unsupported and grounded/unresolved are not the same axis

### 3.3 Failed grounding case

Run:
- `zotero:parkDiscoveryDualactionSmall2022 / run_20260313_110307`

Observed metrics:
- `claim_count=1`
- `supported_claim_count=1`
- `unsupported_claim_count=0`
- `unknown_claim_count=0`
- `grounded_span_count=0`
- `unresolved_span_count=1`
- `ambiguous_span_count=0`
- `failed_grounding_span_count=1`

Claim-level result:
- `grounding_resolutions=["FAILED_MATCH"]`
- `statement_evidence_overlap_ratio=0.8`

Interpretation:
- this case shows that a high lexical overlap heuristic does not guarantee successful grounding
- that is expected and is a useful reminder that overlap should remain a heuristic, not a pass/fail replacement for grounding

## 4. What the Batch Validates

Validated now:
- the sidecar can distinguish unsupported claims from unresolved grounding
- the sidecar can distinguish ambiguous grounding from failed grounding
- the sidecar works both with stored resolved claimsets and with offline replay grounding
- the sidecar is already useful enough to support small-sample failure audits

Still not validated:
- real-artifact heuristic-backfill accounting
- limitation grounding on mixed-quality real runs
- aggregate usefulness over a larger curated sample

## 5. Practical Conclusion

The reader sidecar is now beyond a single clean smoke.
It is useful enough to keep.

The next bounded question is no longer "does the sidecar work at all?"
It is:
- whether a slightly larger curated batch surfaces repeated failure modes worth fixing before any training discussion

## 6. Recommended Next Step

1. Run one more bounded reader batch that explicitly includes a heuristic-backfill case if such an artifact can be produced or located.
2. Then start `Workstream 2` and add stats fallback taxonomy logging.

Given the current evidence, step `2` is now reasonable even if step `1` takes time.
