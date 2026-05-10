# Reader Attempt Order Drift Review

Status: completed
Date: 2026-03-28
Owner: Runtime/agent maintainers
Canonical parent:
- `scripts/benchmark_reader_attempt_order.py`
- `scripts/measure_deepread_runtime.py`

## Purpose

Use the new reader/provider timing metadata to decide whether same-day attempt-order drift is caused by the attempt policy itself or by local Ollama response variability.

## Scope

Reviewed persisted artifacts:

- `storage/artifacts/zotero:coricTargetingProdromalAlzheimer2015/run_20260328_042202/run_meta.json`
- `storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260328_041433/run_meta.json`

Reran provider-aware live benchmarks against saved `document_artifact.json` inputs for:

- `zotero:coricTargetingProdromalAlzheimer2015`
- `zotero:parkDiscoveryDualactionSmall2022`
- `zotero:grandeBloodbasedBiomarkersAlzheimers2025`
- `zotero:leeDeepLearningbasedBrain2022`

Commands used:

```bash
pytest -q tests/test_reader_runtime_metrics.py
python3 scripts/measure_deepread_runtime.py --run-id run_20260328_042202
python3 scripts/measure_deepread_runtime.py --run-id run_20260328_041433
python3 -u - <<'PY'
# ad hoc harness mirroring scripts/benchmark_reader_attempt_order.py
# and printing adapter.last_request_meta for each attempt
PY
```

Addendum commands used on 2026-03-30:

```bash
./scripts/run_agents_smoke.sh
python3 scripts/benchmark_reader_attempt_order.py --run-id run_20260223_140928 --paper-id zotero:leeDeepLearningbasedBrain2022 --policy focused_first --include-provider-metrics --warmup-prompt 'Reply with OK only.'
python3 scripts/benchmark_reader_attempt_order.py --run-id run_20260223_140928 --paper-id zotero:leeDeepLearningbasedBrain2022 --policy focused_first --repeats 2 --include-provider-metrics --warmup-prompt 'Reply with OK only.'
python3 scripts/benchmark_reader_attempt_order.py --run-id run_20260223_140928 --paper-id zotero:leeDeepLearningbasedBrain2022 --policy current --policy focused_first --repeats 2 --include-provider-metrics --warmup-prompt 'Reply with OK only.'
python3 scripts/benchmark_reader_attempt_order.py --run-id run_20260328_002659 --paper-id zotero:parkDiscoveryDualactionSmall2022 --policy current --policy focused_first --repeats 2 --include-provider-metrics --warmup-prompt 'Reply with OK only.'
python3 scripts/benchmark_reader_attempt_order.py --run-id run_20260328_002407 --paper-id zotero:coricTargetingProdromalAlzheimer2015 --policy current --policy focused_first --repeats 2 --include-provider-metrics --warmup-prompt 'Reply with OK only.'
```

## Results

Persisted artifacts show both stable success and tail-timeout modes:

- `coric` success run `run_20260328_042202`
  - `primary`: `24.623s`, `prompt_eval_count=4096`, `eval_count=30`, `0 claims`
  - `focused`: `110.923s`, `prompt_eval_count=4096`, `eval_count=1263`, `4 claims`
- `park` timeout run `run_20260328_041433`
  - `primary`: `360.106s`, `provider_status=timeout`, `provider_error_type=ReadTimeout`

Fresh same-day rerun on saved artifacts:

| Sample | Current | Focused first | Faster policy on rerun |
| --- | --- | --- | --- |
| `coric` | `101.987s`, `3 claims`, `eval_count=1064` | `84.934s`, `3 claims`, `eval_count=843` | `focused_first` |
| `park` | `113.662s`, `4 claims`, `eval_count=1303` | `82.519s`, `3 claims`, `eval_count=868` | `focused_first` |
| `grande` | `96.380s`, `3 claims`, `eval_count=1080` | `74.296s`, `2 claims`, `eval_count=819` | `focused_first` |
| `lee` | `76.683s`, `2 claims`, `eval_count=786` | `83.160s`, `3 claims`, `eval_count=872` | `current` |

Earlier on the same day, live reruns had already shown the opposite winner for some samples:

- `coric`: `current 99.1s` vs `focused_first 243.5s`
- `grande`: `current 96.7s` vs `focused_first 197.3s`

## 2026-03-30 Addendum

The benchmark path was operationalized so the same checks no longer require an ad hoc harness:

- `--include-provider-metrics` surfaces provider status, request wall time, eval count, and done reason in the markdown output
- `--warmup-prompt` runs one untimed warm-up request before each timed policy run
- `--repeats` runs the selected policy set multiple times and emits both an aggregate summary table and repeat-level detail sections

Repeated same-machine reruns continued to show that policy label alone does not determine the winner:

- `lee` remained a stable counterexample in provider-aware reruns without warm-up
  - repeat 1: `current 77.836s / eval_count 625` vs `focused_first 89.693s / eval_count 876`
  - repeat 2: `current 71.434s / eval_count 620` vs `focused_first 89.965s / eval_count 898`
- `coric` remained the unstable sentinel
  - repeat 1: `current 260.638s` via `primary 25.933s -> focused timeout 120.007s -> sentence_focus 114.656s`
  - repeat 1: `focused_first 219.911s` via `focused timeout 120.003s -> primary 99.850s`
  - repeat 2: `current 233.216s` via `primary timeout 120.003s -> focused 113.121s`
  - repeat 2: `focused_first 94.139s` via `focused 94.080s`
- `park` showed the opposite pattern, with consistent `focused_first` wins
  - repeat 1: `current 118.497s / 4 claims` vs `focused_first 66.898s / 2 claims`
  - repeat 2: `current 196.484s` via `primary timeout 120.006s -> focused 76.437s` vs `focused_first 57.938s / 2 claims`

Warm-model control still did not remove drift:

- `lee` warm-up repeat 1: `current 86.722s` vs `focused_first 80.225s`
- `lee` warm-up repeat 2: `current 190.275s` via `primary timeout 120s -> focused 70.226s` vs `focused_first 87.164s`
- `lee` warm-up recheck: `current 122.361s` via `primary parse_failed after 58.312s -> focused 63.999s` vs `focused_first 84.110s`

The first-class repeated CLI path reproduced the same conclusion:

- `focused_first`, `lee`, `--repeats 2`
  - run 1 aggregate: `avg 93.724s`, `min 86.107s`, `max 101.341s`, `avg_claims 2.5`
  - run 2 aggregate: `avg 95.636s`, `min 91.697s`, `max 99.575s`, `avg_claims 3.0`

The broader scripted warm-up/repeat slice across three representative documents also preserved opposite winners by document:

| Sample | Current avg | Focused first avg | Interpretation |
| --- | --- | --- | --- |
| `lee` | `92.822s`, avg claims `2.5` | `139.852s`, avg claims `2.0` | `current` faster; `focused_first` repeat 2 hit `focused ReadTimeout` and fell back to `primary` |
| `park` | `152.404s`, avg claims `2.5` | `81.416s`, avg claims `2.5` | `focused_first` faster; `current` repeat 1 hit `primary ReadTimeout` and fell back to `focused` |
| `coric` | `94.094s`, avg claims `3.0` | `103.915s`, avg claims `4.0` | mixed; `current` average was lower, but `focused_first` kept the higher-claim `focused` path consistently |

That broader slice makes the policy boundary clearer:

- the scripted warm-up/repeat path reduces ad hoc measurement noise, but it does not remove document-specific winner flips
- `lee` and `park` still point in opposite directions under the same protocol
- `coric` remains the unstable sentinel because winner choice depends on whether `current` can accept the faster `primary` answer or has to pay for a second attempt

## Current Judgment

- Same-day winner flips are real. `focused_first` was not consistently faster across repeated local reruns on the same machine and model.
- Even under the scripted `--warmup-prompt` + `--repeats` path, winner choice is still document-dependent rather than globally stable.
- Prompt reduction alone does not explain latency. `focused_first` consistently reduced prompt size by roughly `900-1240` estimated prompt tokens, but runtime tracked completion length (`eval_count`) more closely than prompt size.
- The slowest pathological behavior is still tail latency in the first request, not a retry loop. The `park` persisted timeout remained a single-request `ReadTimeout` on `primary`.
- Warm-up improves load-state visibility, not policy stability. It can shrink the preflight request from a few seconds to a few hundred milliseconds, but it does not prevent timeout, parse-fail, or high-eval-count tails in the timed reader call.
- The new provider metadata is sufficient to explain most drift classes:
  - smaller prompt + smaller `eval_count` -> usually faster
  - smaller prompt + larger `eval_count` -> can still be slower (`lee`)
  - long tail request or timeout -> dominates policy outcome regardless of prompt savings

## Decision

Keep attempt order as-is for runtime defaults.

- do not switch the default reader policy based on same-day local reruns alone
- keep alternative attempt orders config-gated only
- treat provider/request telemetry as the primary lens for future attempt-order decisions

## Follow-up

1. Completed same day: `scripts/benchmark_reader_attempt_order.py --include-provider-metrics` now surfaces provider status, request seconds, eval count, and done reason in the markdown output.
2. Completed on 2026-03-30: the same script now supports `--warmup-prompt` and `--repeats`, so repeated warm-model checks can run without ad hoc shell loops.
3. Completed on 2026-03-30: a broader scripted slice across `lee`, `park`, and `coric` still showed opposite winners by document, so the config-gated judgment held under the new protocol.
4. If a default policy change is reconsidered, expand the scripted multi-document slice beyond the current three documents and compare aggregate outputs rather than one-off local reruns.
