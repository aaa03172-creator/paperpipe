# Reader Attempt Profile

Status: bounded profiling note
Date: 2026-03-28
Owner: runtime/product maintainers
Canonical parents:
- `docs/reports/Local_Deep_Read_Runtime_Measurement_2026-03-28.md`
- `docs/reports/TurboQuant_Fit_Review_2026-03-27.md`
- `docs/Product_Positioning_Principles.md`

Related note:
- `docs/reports/Focused_First_Reader_Benchmark_2026-03-28.md`

## Purpose

Read one representative real-paper run closely enough to answer a narrow question:

> is the current reader slowdown better explained by low-level serving pressure, or by bounded multi-attempt prompt/context strategy?

This note does not propose a runtime rewrite.
It only profiles the attempt-level evidence already stored in `run_meta.json`.

## Sample

- paper: `zotero:coricTargetingProdromalAlzheimer2015`
- run: `run_20260327_171016`
- path:
  - `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:coricTargetingProdromalAlzheimer2015/run_20260327_171016`

## Attempt breakdown

| Attempt | Status | Mode | Chunks | Sections | Claims | Prompt tokens | Tokens / claim | Claims / 1k prompt tokens |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `primary` | `parsed` | `chunk_context` | `16` | `3` | `0` | `5451` | `-` | `0.000` |
| `focused` | `parsed` | `chunk_context` | `12` | `2` | `3` | `4553` | `1517.667` | `0.659` |

## Repo-grounded findings

### 1. The representative cost is still in reader work, not verified serving pressure

For this run:

- total runtime = `242.35s`
- read phase = `232.854s`
- index phase = `8.106s`
- ingest phase = `1.453s`

That confirms the runtime is still dominated by `read`, but by itself it does not identify a KV-cache or VRAM bottleneck.

### 2. The narrower focused attempt is materially more productive than the wider primary attempt

Observed behavior:

- the `primary` attempt used more prompt budget:
  - `5451` estimated prompt tokens
  - `16` chunks
  - `3` sections
- but returned `0` parsed claims

- the `focused` attempt used less prompt budget:
  - `4553` estimated prompt tokens
  - `12` chunks
  - `2` sections
- and returned `3` parsed claims

Current inference:

- the immediate inefficiency is not “the model cannot run at all”
- it is more likely that the first attempt is spending prompt budget on context that is too broad or too weakly prioritized for extraction

### 3. Sentence-focus is still unused on the representative successful path

The selected successful attempt is still:

- `context_mode = chunk_context`
- `sentence_focus_count = 0`

So there is not yet repo-grounded evidence that sentence-focused extraction helps this representative path.
It remains a fallback path, not a demonstrated optimization.

### 4. This still does not justify TurboQuant

This profile is useful because it narrows the likely next bottleneck candidate:

- attempt policy
- section prioritization
- chunk selection quality

It still does **not** prove:

- KV-cache pressure
- GPU memory pressure
- vector-memory pressure
- self-hosted serving throughput collapse

So the correct decision remains:

> keep TurboQuant on the watchlist; do not integrate it now.

## Smallest justified next step

The next bounded evaluation should stay at the reader strategy layer:

1. compare `primary -> focused` against a narrower-first policy on one representative paper
2. inspect whether the current priority-section heuristic is bringing in too many low-yield chunks
3. keep the change offline or benchmark-only unless the same pattern repeats

## Not justified yet

- provider/runtime architecture changes
- KV-cache optimization work
- vector-search quantization work
- product-facing claims about faster local inference

## Reproduction

```bash
python3 scripts/measure_deepread_runtime.py --run-id run_20260327_171016
```
