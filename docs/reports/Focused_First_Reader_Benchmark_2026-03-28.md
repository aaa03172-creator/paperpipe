# Focused-First Reader Benchmark

Status: bounded benchmark note
Date: 2026-03-28
Owner: runtime/product maintainers
Canonical parents:
- `docs/reports/Reader_Attempt_Profile_2026-03-28.md`
- `docs/reports/Local_Deep_Read_Runtime_Measurement_2026-03-28.md`
- `docs/reports/TurboQuant_Fit_Review_2026-03-27.md`

Related note:
- `docs/reports/Reader_Attempt_Order_RFC_2026-03-28.md`

## Purpose

Run the smallest benchmark-only comparison between:

- current reader attempt order:
  - `primary -> focused -> sentence_focus`
- narrower-first attempt order:
  - `focused -> primary -> sentence_focus`

This note does not change runtime behavior.
It only checks whether a narrower-first order is plausible enough to justify a later offline experiment.

## Benchmark setup

- sample A:
  - paper: `zotero:coricTargetingProdromalAlzheimer2015`
  - run: `run_20260327_171016`
- sample B:
  - paper: `zotero:parkDiscoveryDualactionSmall2022`
  - run: `run_20260324_032111`
- sample C:
  - paper: `zotero:grandeBloodbasedBiomarkersAlzheimers2025`
  - run: `run_20260223_144102`
- sample D:
  - paper: `zotero:leeDeepLearningbasedBrain2022`
  - run: `run_20260223_140928`
- benchmark script:
  - `scripts/benchmark_reader_attempt_order.py`
- model path:
  - `llama3:latest`

Important limitation:

- this is a live local-model benchmark, not a deterministic replay
- response length and exact claim count can drift slightly between runs
- benchmark conclusions should be treated as directional, not final runtime proof
- some older run ids are not globally unique across paper ids, so benchmark reproduction should pass both:
  - `--paper-id`
  - `--run-id`

## Observed result

### Sample A: `zotero:coricTargetingProdromalAlzheimer2015`

| Policy | Selected attempt | Selected claims | Total elapsed sec | Total prompt tokens | Total response tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| `current` | `focused` | `4` | `150.821` | `10004` | `1209` |
| `focused_first` | `focused` | `4` | `117.413` | `4553` | `1278` |

### Attempt detail

#### current

| Attempt | Status | Chunks | Sections | Claims | Prompt tokens | Response tokens | Elapsed sec |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `primary` | `parsed` | `16` | `3` | `0` | `5451` | `15` | `41.640` |
| `focused` | `parsed` | `12` | `2` | `4` | `4553` | `1194` | `109.181` |

#### focused_first

| Attempt | Status | Chunks | Sections | Claims | Prompt tokens | Response tokens | Elapsed sec |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `focused` | `parsed` | `12` | `2` | `4` | `4553` | `1278` | `117.413` |

### Sample B: `zotero:parkDiscoveryDualactionSmall2022`

| Policy | Selected attempt | Selected claims | Total elapsed sec | Total prompt tokens | Total response tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| `current` | `focused` | `2` | `189.982` | `8340` | `613` |
| `focused_first` | `focused` | `2` | `65.828` | `3648` | `578` |

#### current

| Attempt | Status | Chunks | Sections | Claims | Prompt tokens | Response tokens | Elapsed sec |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `primary` | `error:ReadTimeout` | `15` | `2` | `0` | `4692` | `-` | `120.007` |
| `focused` | `parsed` | `11` | `2` | `2` | `3648` | `613` | `69.975` |

#### focused_first

| Attempt | Status | Chunks | Sections | Claims | Prompt tokens | Response tokens | Elapsed sec |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `focused` | `parsed` | `11` | `2` | `2` | `3648` | `578` | `65.828` |

### Sample C: `zotero:grandeBloodbasedBiomarkersAlzheimers2025`

| Policy | Selected attempt | Selected claims | Total elapsed sec | Total prompt tokens | Total response tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| `current` | `focused` | `3` | `239.516` | `8535` | `1007` |
| `focused_first` | `focused` | `3` | `116.989` | `3757` | `1143` |

#### current

| Attempt | Status | Chunks | Sections | Claims | Prompt tokens | Response tokens | Elapsed sec |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `primary` | `error:ReadTimeout` | `15` | `3` | `0` | `4778` | `-` | `120.004` |
| `focused` | `parsed` | `11` | `2` | `3` | `3757` | `1007` | `119.512` |

#### focused_first

| Attempt | Status | Chunks | Sections | Claims | Prompt tokens | Response tokens | Elapsed sec |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `focused` | `parsed` | `11` | `2` | `3` | `3757` | `1143` | `116.989` |

### Sample D: `zotero:leeDeepLearningbasedBrain2022`

| Policy | Selected attempt | Selected claims | Total elapsed sec | Total prompt tokens | Total response tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| `current` | `focused` | `3` | `226.016` | `8456` | `1094` |
| `focused_first` | `focused` | `3` | `92.185` | `3608` | `965` |

#### current

| Attempt | Status | Chunks | Sections | Claims | Prompt tokens | Response tokens | Elapsed sec |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `primary` | `error:ReadTimeout` | `16` | `3` | `0` | `4848` | `-` | `120.004` |
| `focused` | `parsed` | `11` | `2` | `3` | `3608` | `1094` | `106.012` |

#### focused_first

| Attempt | Status | Chunks | Sections | Claims | Prompt tokens | Response tokens | Elapsed sec |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `focused` | `parsed` | `11` | `2` | `3` | `3608` | `965` | `92.185` |

## Repo-grounded findings

### 1. On all four sampled papers, focused-first preserved claim yield

Observed:

- sample A
  - selected attempt = `focused`
  - selected claims = `4`
- sample B
  - selected attempt = `focused`
  - selected claims = `2`
- sample C
  - selected attempt = `focused`
  - selected claims = `3`
- sample D
  - selected attempt = `focused`
  - selected claims = `3`

So this benchmark did not show a loss in extraction yield from trying the narrower focused context first on any sampled paper.

### 2. Focused-first substantially reduced prompt budget on all four sampled papers

Observed prompt-token totals:

- sample A
  - current = `10004`
  - focused-first = `4553`
- sample B
  - current = `8340`
  - focused-first = `3648`
- sample C
  - current = `8535`
  - focused-first = `3757`
- sample D
  - current = `8456`
  - focused-first = `3608`

That is a reduction of about:

- `54.5%` on sample A
- `56.3%` on sample B
- `56.0%` on sample C
- `57.3%` on sample D

That is meaningful because the current evidence still points to prompt/context strategy as the most visible reader cost.

### 3. Focused-first also reduced wall time on all four sampled papers

Observed elapsed totals:

- sample A
  - current = `150.821s`
  - focused-first = `117.413s`
- sample B
  - current = `189.982s`
  - focused-first = `65.828s`
- sample C
  - current = `239.516s`
  - focused-first = `116.989s`
- sample D
  - current = `226.016s`
  - focused-first = `92.185s`

This is directionally strong, but it still needs careful interpretation.

Important nuance:

- sample B includes a `primary`-attempt timeout under the current order
- sample C also includes a `primary`-attempt timeout under the current order
- sample D also includes a `primary`-attempt timeout under the current order
- that makes the gap more dramatic, but it also means the benchmark is showing policy fragility, not just raw speed

So this benchmark is useful, but still not enough to justify a runtime change on its own because:

- the benchmark still covers only four papers
- the model path is not deterministic
- the current runtime contract has not yet been validated against broader paper variation
- downstream quality effects have still not been compared under a gated runtime pilot

### 4. This still does not justify TurboQuant

The benchmark strengthens the same current conclusion:

- likely next bottleneck candidate:
  - reader attempt order
  - chunk prioritization
  - section selection strategy
- not yet justified:
  - KV-cache optimization
  - inference-serving integration work
  - vector quantization work

## Smallest justified next step

If anything is explored next, it should stay benchmark-only:

1. the outlier benchmark bar is now satisfied
2. if reopened, the next step should be a config-gated pilot, not another benchmark of the same shape
3. compare downstream quality stability:
   - resolved evidence linkage
   - note-side state quality
   - artifact quality on a tiny representative set
4. only consider a runtime order change if those checks stay clean

## Not justified yet

- changing the default reader attempt order in product runtime
- product-facing claims about faster local inference
- any TurboQuant integration work

## Reproduction

```bash
python3 scripts/benchmark_reader_attempt_order.py \
  --paper-id 'zotero:coricTargetingProdromalAlzheimer2015' \
  --run-id run_20260327_171016
python3 scripts/benchmark_reader_attempt_order.py \
  --paper-id 'zotero:parkDiscoveryDualactionSmall2022' \
  --run-id run_20260324_032111
python3 scripts/benchmark_reader_attempt_order.py \
  --paper-id 'zotero:grandeBloodbasedBiomarkersAlzheimers2025' \
  --run-id run_20260223_144102
python3 scripts/benchmark_reader_attempt_order.py \
  --paper-id 'zotero:leeDeepLearningbasedBrain2022' \
  --run-id run_20260223_140928
```
