# Local Deep Read Runtime Measurement

Status: Active measurement note
Date: 2026-03-28
Owner: Runtime/product maintainers
Canonical parents:
- `docs/reports/TurboQuant_Fit_Review_2026-03-27.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/Product_Positioning_Principles.md`

Related note:
- `docs/reports/Reader_Attempt_Profile_2026-03-28.md`

## Purpose

Measure the current local deep-read/runtime path before considering any low-level inference optimization work.

This note is intentionally narrow.

It does not claim that KV-cache pressure, long-context pressure, or vector-memory pressure is solved or absent.
It records what the current saved runs actually show.

## Measurement method

- Source of truth:
  - `storage/state.db` `job_events`
  - saved run artifacts under `storage/artifacts/<paper_id>/<run_id>/`
- Measurement script:
  - `scripts/measure_deepread_runtime.py`
- Timing method:
  - phase wall time is derived from progress-event timestamps
  - stage counts and artifact sizes are derived from saved run artifacts
- Important limitation:
  - this pass does **not** measure VRAM, KV-cache usage, token counts, or GPU utilization
  - it is a pipeline/runtime timing summary, not a serving profiler

## Sample selection

### 1. Fresh representative real-paper rerun

- paper: `zotero:coricTargetingProdromalAlzheimer2015`
- run: `run_20260327_022030`
- current relevance:
  - fresh
  - representative of the current paper-first deep-read path
  - no verify step

### 2. Latest verify-backed real-paper sample in current local data

- paper: `zotero:parkDiscoveryDualactionSmall2022`
- run: `run_20260313_110600`
- current relevance:
  - older than the fresh rerun
  - still useful for seeing the verify-inclusive phase shape

### 3. Fresh post-instrumentation representative rerun

- paper: `zotero:coricTargetingProdromalAlzheimer2015`
- run: `run_20260327_170242`
- current relevance:
  - same representative paper as the fresh rerun above
  - first local run after additive `reader_analysis` instrumentation
  - useful for seeing whether the new reader metrics are materially informative

### 4. Fresh post-composition-instrumentation representative rerun

- paper: `zotero:coricTargetingProdromalAlzheimer2015`
- run: `run_20260327_171016`
- current relevance:
  - same representative paper as the two fresh reruns above
  - first local run after adding attempt-level context composition metrics
  - useful for seeing whether selected-attempt chunk/section composition is visible enough to guide the next profiling pass

## Measured results

| Run | Paper | Verify | Pages | Chunks | Claims | Stats checks | Total sec | Ingest sec | Index sec | Read sec | Verify sec |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `run_20260327_022030` | `zotero:coricTargetingProdromalAlzheimer2015` | `false` | `10` | `77` | `3` | `-` | `131.275` | `1.490` | `18.841` | `110.959` | `-` |
| `run_20260313_110600` | `zotero:parkDiscoveryDualactionSmall2022` | `true` | `12` | `93` | `1` | `1` | `43.766` | `2.952` | `3.475` | `36.186` | `1.150` |
| `run_20260327_170242` | `zotero:coricTargetingProdromalAlzheimer2015` | `false` | `10` | `77` | `4` | `-` | `150.546` | `0.843` | `3.940` | `145.779` | `-` |
| `run_20260327_171016` | `zotero:coricTargetingProdromalAlzheimer2015` | `false` | `10` | `77` | `3` | `-` | `242.350` | `1.453` | `8.106` | `232.854` | `-` |

## Repo-grounded findings

### 1. Reader time dominates the sampled local runtime

In both sampled runs, the `read` phase is the largest wall-time component.

- fresh representative rerun:
  - `read = 110.959s`
  - `index = 18.841s`
  - `ingest = 1.490s`
- older verify-backed sample:
  - `read = 36.186s`
  - `verify = 1.150s`
  - `index = 3.475s`
  - `ingest = 2.952s`

This means the current runtime is more likely to benefit from better visibility into reader behavior than from immediate low-level serving changes.

### 1.1 The new reader instrumentation is informative enough to guide next decisions

The fresh post-instrumentation rerun recorded:

- `reader_attempt_count = 2`
- `reader_return_mode = success`
- `reader_selected_attempt_label = focused`
- estimated prompt tokens across attempts: `10004`
- estimated response tokens across attempts: `1356`

Attempt shape:

- `primary`
  - context chars: `15568`
  - estimated prompt tokens: `5451`
  - parsed claim count: `0`
- `focused`
  - context chars: `11976`
  - estimated prompt tokens: `4553`
  - parsed claim count: `4`

This is useful because it narrows the next question.

The current evidence now suggests:

- the reader is doing substantial prompt-budget work inside bounded multi-attempt extraction
- the first issue to inspect is reader prompt/context strategy or model behavior
- not low-level KV-cache optimization by default

### 1.2 Attempt composition is now visible on the real path

The fresh post-composition-instrumentation rerun recorded:

- `reader_attempt_count = 2`
- `reader_selected_attempt_label = focused`
- total estimated prompt tokens across attempts: `10004`
- selected attempt `context_mode = chunk_context`
- selected attempt `included_chunk_count = 12`
- selected attempt `unique_section_count = 2`
- selected attempt `sentence_focus_count = 0`
- selected attempt `truncated_chunk_count = 0`

Attempt shape:

- `primary`
  - estimated prompt tokens: `5451`
  - included chunks: `16`
  - unique sections: `3`
  - parsed claim count: `0`
- `focused`
  - estimated prompt tokens: `4553`
  - included chunks: `12`
  - unique sections: `2`
  - parsed claim count: `3`

This narrows the current profiling target further:

- the runtime cost is still in the reader
- the next meaningful question is how chunk selection and section focus affect extraction quality
- the evidence still does **not** prove a KV-cache or serving-memory problem

### 2. Verify is not the dominant cost in the sampled verify-backed run

The only sampled verify-backed real-paper run shows:

- `verify = 1.150s`
- `read = 36.186s`

That does not support a claim that verify/sandbox cost is currently dominating the local deep-read path.

### 3. Current measurements still do not prove a KV-cache bottleneck

The sampled runtimes are informative, but they do not measure:

- VRAM usage
- KV-cache memory pressure
- context eviction
- token throughput
- GPU utilization

So the correct judgment is:

- `reader latency is visible`
- `KV-cache compression need is not yet proven`
- `reader attempt/prompt-budget behavior is now observable enough to profile further`

### 4. Current measurements also do not prove a vector-memory bottleneck

The sampled runs show chunk counts (`77`, `93`), but this note does not show:

- Chroma collection size pressure
- index memory exhaustion
- ANN latency collapse at scale

So retrieval quantization remains a conditional future idea, not a justified present implementation target.

## Implication for TurboQuant-style work

Current best inference:

- TurboQuant is still technically interesting.
- But this measurement pass does **not** justify adoption.
- The current evidence supports:
  - reader/runtime measurement first
  - maybe deeper serving profiling later
  - no current runtime integration
  - prompt-budget and attempt-level reader profiling before any infra work

## What this measurement does justify

### Immediate justified next step

- add more explicit reader/runtime measurement before any inference-optimization pilot

Good candidates:
- token-count estimation per reader attempt
- model request count per run
- per-step timeout/retry counts
- optional local memory/VRAM measurement when available
- attempt-level context composition metrics such as:
  - selected chunk count
  - unique section count
  - sentence-focus usage
  - truncated chunk count

Follow-up status:

- a bounded additive follow-up is now in place for future runs:
  - `ReaderAgent` persists `reader_analysis`
  - `run_meta.json` now has room for:
    - attempt count
    - return mode
    - selected attempt label
    - estimated prompt/response token totals
  - `scripts/measure_deepread_runtime.py` will surface those fields when newer runs include them
- this does **not** change the current measurement conclusion because the sampled runs in this note predate that additive instrumentation
- the fresh post-instrumentation rerun now confirms that those metrics are populated and usable on the real representative path
- the fresh post-composition-instrumentation rerun now confirms that attempt-level context composition is also populated and usable on the same representative path

### Not yet justified

- introducing TurboQuant into the current runtime
- changing provider/runtime architecture for serving efficiency
- retrieval quantization work

## Recommended decision

Current best judgment:

> keep TurboQuant as a watchlist item; do not integrate it now. The current local runtime measurements show reader latency dominance, but they do not yet prove that KV-cache compression or vector quantization is the right fix.

## Reproduction

```bash
python3 scripts/measure_deepread_runtime.py \
  --run-id run_20260327_022030 \
  --run-id run_20260313_110600 \
  --run-id run_20260327_170242 \
  --run-id run_20260327_171016
```
