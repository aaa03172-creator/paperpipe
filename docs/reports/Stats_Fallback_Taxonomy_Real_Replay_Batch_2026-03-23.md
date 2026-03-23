# Stats Fallback Taxonomy Real Replay Batch

Status: Completed bounded replay batch
Date: 2026-03-23
Branch observed: `codex/agents-smoke-ci-check`

## 0. Purpose

Validate the new stats fallback taxonomy sidecar on a small mixed-quality set of existing real artifact runs.

This batch is additive only.
It does not alter stats verification semantics.
It only derives a sidecar from `stats_report.json` and `bootstrap_meta.json`.

## 1. Batch Composition

Included runs:
1. `zotero:parkDiscoveryDualactionSmall2022 / run_20260313_110600`
2. `1411.2441 / run_real_20260305_153128_fallback`
3. `1411.2441 / run_real_20260306_023042_notable_short`
4. `1411.2441 / run_live_sample`
5. `paper_anchor_meta_001 / run_anchor_meta` (targeted recheck for `NO_API_CONTEXT` inference)

Selection rationale:
- one `degenerate_table_shape` auto-fallback case
- one `no_extractable_stats` auto-fallback case
- one `no_table_data` case
- one mixed `verified + no_api_context` case

## 2. Outputs Written

- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_110600/stats_fallback_eval.json`
- `/Users/jangseongjin/paperpipe/storage/artifacts/1411.2441/run_real_20260305_153128_fallback/stats_fallback_eval.json`
- `/Users/jangseongjin/paperpipe/storage/artifacts/1411.2441/run_real_20260306_023042_notable_short/stats_fallback_eval.json`
- `/Users/jangseongjin/paperpipe/storage/artifacts/1411.2441/run_live_sample/stats_fallback_eval.json`
- `/Users/jangseongjin/paperpipe/storage/artifacts/paper_anchor_meta_001/run_anchor_meta/stats_fallback_eval.json`

## 3. Batch Results

### 3.1 Degenerate table shape

Run:
- `zotero:parkDiscoveryDualactionSmall2022 / run_20260313_110600`

Observed:
- `table_extraction_pass=pass1`
- `table_failure_taxonomy=[DEGENERATE_SHAPE]`
- `fallback_used=false`
- `unverifiable_count=1`
- `auto_fallback_count=1`
- `degenerate_table_shape_count=1`

Interpretation:
- this bucket is cleanly identifiable from existing artifacts
- the sidecar makes it explicit that the failure is table-shape related, not a generic model miss

### 3.2 No extractable stats

Run:
- `1411.2441 / run_real_20260305_153128_fallback`

Observed:
- `table_extraction_pass=pass1`
- `table_failure_taxonomy=[NO_TABLE_FOUND]`
- `fallback_used=false`
- `check_count=3`
- `unverifiable_count=3`
- `auto_fallback_count=3`
- `no_extractable_stats_count=3`

Interpretation:
- this bucket is distinct from `no_table_data`
- the claim list exists, but the stats path still could not extract executable statistical structure

### 3.3 No table data

Run:
- `1411.2441 / run_real_20260306_023042_notable_short`

Observed:
- `table_extraction_pass=pass3`
- `table_failure_taxonomy=[NO_TABLE_FOUND]`
- `fallback_used=false`
- `check_count=3`
- `unverifiable_count=3`
- `no_table_count=3`
- `auto_fallback_count=0`

Interpretation:
- this bucket is correctly separated from auto-fallback taxonomy
- important nuance: `pass3` being recorded does not mean a useful fallback table was recovered
- `fallback_used=false` remains the key signal for that distinction

### 3.4 No API context mixed with verified

Run:
- `1411.2441 / run_live_sample`
- `paper_anchor_meta_001 / run_anchor_meta`

Observed:
- `table_extraction_pass=pass1`
- `table_failure_taxonomy=[NO_TABLE_FOUND]`
- `fallback_used=false`
- `check_count=2`
- `verified_count=1`
- `unverifiable_count=1`
- `no_api_context_count=1`
- `unspecified_unverifiable_count=0`

Interpretation:
- the previous `UNSPECIFIED_UNVERIFIABLE` bucket was too coarse for these runs
- bounded recheck shows these cases can be more accurately labeled as `NO_API_CONTEXT`
- this keeps the stats taxonomy more useful without changing verifier behavior

## 4. What the Batch Validates

Validated now:
- stats sidecar can distinguish multiple fallback buckets from existing artifacts
- `auto_fallback` and `no_table_data` are now separate measurable classes
- `NO_API_CONTEXT` can be inferred from existing `anchor_verify_api` / `anchor_verify_summary` metadata
- ingest-layer signals (`table_extraction_pass`, `table_failure_taxonomy`, `fallback_used`) are usable context for stats review
- the sidecar is already useful enough to support bounded failure analysis without changing verifier behavior

Not yet validated:
- cloud fallback cases where `fallback_used=true` and usable tables were actually recovered
- whether bucket frequencies are stable across a larger sample
- whether remaining future `UNSPECIFIED_UNVERIFIABLE` cases can all be reduced through existing metadata inference alone

## 5. Practical Conclusion

The stats taxonomy sidecar is already useful.

The most actionable current gap is not parser replacement or model retraining.
It is:
- keeping `no_table_data`, `no_extractable_stats`, and `degenerate_table_shape` explicitly separated
- reducing any remaining truly unexplained `UNSPECIFIED_UNVERIFIABLE` cases

## 6. Recommended Next Step

1. Add one bounded follow-up only if new artifacts still produce unexplained `UNSPECIFIED_UNVERIFIABLE` cases.
2. Then pause broad stats changes and assess whether the current bucket frequencies justify parser-side work.

Current evidence does not justify parser replacement or training-first work.
It does justify tighter fallback reason logging.
