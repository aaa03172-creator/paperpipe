# Reader Attempt Order Reopen Check (2026-04-01)

Status: concluded bounded reopen check
Date: 2026-04-01
Owner: runtime/agent maintainers
Canonical parents:
- `docs/reports/External_Reference_Action_Order_2026-04-01.md`
- `docs/reports/Reader_Attempt_Order_Drift_Review_2026-03-28.md`
- `docs/reports/Focused_First_Gated_Pilot_Acceptance_2026-03-28.md`
- `docs/reports/Focused_First_Reader_Benchmark_2026-03-28.md`

## Purpose

Decide whether action 4 from the 2026-04-01 external-reference review should actually be reopened now.

This note does not:
- change the default reader attempt order
- reopen a broad runtime-policy lane
- claim that `focused_first` is no longer useful

It answers one narrower question:
- after the OCR pilot closeout, is there fresh repo-grounded evidence that justifies reopening a new bounded `focused_first` pilot?

## Fresh check scope

Reused the existing first-class benchmark harness:
- `scripts/benchmark_reader_attempt_order.py`

Fresh same-machine reruns used:
- model:
  - `llama3:latest`
- runtime:
  - repo `.venv`
- warm-up:
  - `Reply with OK only.`
- samples:
  - `zotero:parkDiscoveryDualactionSmall2022`
  - `zotero:leeDeepLearningbasedBrain2022`

Working proof outputs:
- `.codex/work/2026-04-01_reference-fit-review/reader_attempt_order/park_20260401.md`
- `.codex/work/2026-04-01_reference-fit-review/reader_attempt_order/lee_20260401.md`

Those files are execution evidence, not canonical runtime docs.

## Commands used

```bash
./.venv/bin/python scripts/benchmark_reader_attempt_order.py \
  --run-id run_20260324_032111 \
  --paper-id zotero:parkDiscoveryDualactionSmall2022 \
  --policy current \
  --policy focused_first \
  --include-provider-metrics \
  --warmup-prompt 'Reply with OK only.' \
  --out .codex/work/2026-04-01_reference-fit-review/reader_attempt_order/park_20260401.md

./.venv/bin/python scripts/benchmark_reader_attempt_order.py \
  --run-id run_20260223_140928 \
  --paper-id zotero:leeDeepLearningbasedBrain2022 \
  --policy current \
  --policy focused_first \
  --include-provider-metrics \
  --warmup-prompt 'Reply with OK only.' \
  --out .codex/work/2026-04-01_reference-fit-review/reader_attempt_order/lee_20260401.md
```

## Observed result

| Sample | Current | Focused first | Reading |
| --- | --- | --- | --- |
| `park` | `sentence_focus`, `1` claim, `289.606s` | `focused`, `2` claims, `67.135s` | `focused_first` clearly better on this rerun, but only because `current` hit two upstream timeouts before falling through |
| `lee` | `focused`, `3` claims, `223.002s` | `focused`, `1` claim, `47.590s` | `focused_first` was much faster, but claim yield regressed on the same rerun |

Important attempt-level detail:

- `park`, `current`
  - `primary`: `ReadTimeout` at about `120s`
  - `focused`: `ReadTimeout` at about `120s`
  - `sentence_focus`: succeeded in about `49s`
- `park`, `focused_first`
  - `focused`: succeeded directly in about `67s`
- `lee`, `current`
  - `primary`: `ReadTimeout` at about `120s`
  - `focused`: succeeded in about `103s` with `3` claims
- `lee`, `focused_first`
  - `focused`: succeeded directly in about `48s`, but returned only `1` claim

## Repo-grounded meaning

### 1. The fresh reruns still do not show a globally better default order

The two samples point in different directions:
- `park` favors `focused_first`
- `lee` favors `current` on extraction yield even though `focused_first` is faster

That is enough to keep the default order unchanged.

### 2. The real unstable factor is still first-request tail behavior

The `park` win is real, but it is not a clean “focused_first is better” story.

It is mainly:
- `current` hit two consecutive `120s` timeouts before reaching a narrower fallback
- `focused_first` got a clean first success and avoided the timeout ladder

That is useful telemetry, but it still points to runtime/request instability more than to a universally better attempt order.

### 3. Faster is still not enough if claim yield falls

The `lee` rerun is the stronger brake on reopening:
- `focused_first` cut elapsed time sharply
- but it also dropped selected claim count from `3` to `1`

That is exactly the kind of tradeoff that should block any default-order promotion at the current repo stage.

## Decision

Do not reopen action 4 as a new bounded pilot right now.

Keep:
- default reader attempt order unchanged
- `focused_first` available only as a config-gated opt-in path
- future attention on provider/request tail behavior, not on default-order flipping

## Why not now

The current repo still lacks the evidence needed for a broader change:
- no fresh representative slice shows a stable same-direction winner
- the opposite-winner pattern is still real on the current machine
- speed-only wins are not sufficient when claim yield can drop

So this lane should remain a measured hold, not an active reopen.

## Smallest future reopen condition

Only reopen this lane if all of these are true:
- fresh representative papers still show unresolved reader tail pain
- the comparison uses a fixed multi-document slice rather than a single winner case
- downstream quality is judged by claim/evidence outputs, not latency alone

## Bottom line

The fresh 2026-04-01 reruns strengthen the same conservative judgment:
- `focused_first` remains useful as an opt-in tool
- but current evidence still does not justify reopening default attempt-order work
