# Focused-First Gated Pilot Acceptance Checklist

Status: bounded pilot checklist, config gate implemented, tiny pilot recorded, default unchanged
Date: 2026-03-28
Owner: runtime/product maintainers
Canonical parents:
- `docs/reports/Reader_Attempt_Order_RFC_2026-03-28.md`
- `docs/reports/Focused_First_Reader_Benchmark_2026-03-28.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`

## Purpose

Define the smallest safe acceptance bar for a possible `focused_first` reader pilot.

This checklist is for:

- deciding whether a config-gated pilot is safe to open
- deciding whether a pilot result is good enough to keep studying
- preventing a benchmark signal from becoming a silent runtime default change

This checklist is not:

- approval to change the default runtime behavior
- a product-facing performance claim
- a reason to reopen TurboQuant or serving-infrastructure work

## Executive Call

Safest current direction:

1. keep the runtime default unchanged
2. if a pilot is opened, make it config-gated and explicitly opt-in
3. the pilot must prove downstream quality is not worse, not just that benchmark latency is lower
4. if the pilot cannot meet the checklist below, close it and keep the current order

## Status update

As of `2026-03-28`:

- the config gate exists
- the default runtime order is still unchanged
- a tiny opt-in pilot result now exists in:
  - `docs/reports/Focused_First_Gated_Pilot_Acceptance_2026-03-28.md`

This checklist still controls whether any opt-in pilot should be considered trustworthy.

## Pilot shape

If opened, the pilot should be:

- bounded
- local-only
- explicitly non-default
- small-set only

Safest shape:

- current default remains:
  - `primary -> focused -> sentence_focus`
- pilot order becomes:
  - `focused -> primary -> sentence_focus`
- effective attempt order is recorded in runtime metadata
- no provider/runtime/serving changes happen in the same lane

## Pilot entry conditions

All of these must already be true before opening the pilot:

1. benchmark evidence exists on a small representative set
   - satisfied by `docs/reports/Focused_First_Reader_Benchmark_2026-03-28.md`
2. the benchmark includes at least one deliberately difficult outlier
   - satisfied by `zotero:leeDeepLearningbasedBrain2022`
3. runtime change is explicitly requested
4. the pilot remains config-gated or opt-in
5. the operator agrees that no product-facing speed claim will be made from pilot-only evidence

## Pilot sample size

Safest first pilot size:

- `2-4` representative papers

The set should include:

- one previously easy/clean representative paper
- one paper where current-order `primary` showed fragility or timeout
- one outlier with a different section/table mix

Do not:

- expand to broad corpus rollout
- mix provider/runtime changes into the same pilot
- use only one paper family

## Required runtime guardrails

The pilot is not acceptable unless all of these are true:

1. default runtime order remains unchanged for non-pilot runs
2. the effective attempt order is visible in:
   - `run_meta.json`
   - or `reader_analysis`
3. pilot runs remain fully inspectable through the current paper/run/artifact model
4. artifact lineage and note-side state promotion remain non-destructive
5. rollback is trivial:
   - disable the config gate
   - return to current default order

## Must-pass quality checks

These are the actual acceptance checks for the pilot.

### 1. Claim yield

For each pilot paper:

- compare pilot run vs current-order baseline
- any claim-count drop must be explained, not ignored

Pass rule:

- no unexplained claim-yield regression on the pilot set

### 2. Evidence linkage quality

For each pilot paper:

- compare resolved claim payloads
- inspect whether evidence spans remain present and believable

Minimum acceptance:

- no obvious loss of evidence spans
- no clear drift toward weaker or less-specific grounding

### 3. Note-side state quality

For each pilot paper:

- `.pp/<slug>/state.json` still resolves correctly
- `runs[0]` matches the latest pilot run
- `/paper-notes/{slug}` still surfaces structured state cleanly
- note markdown still keeps a single deep-read section

Pass rule:

- no corruption, duplication, or hidden partial-state behavior

### 4. Downstream artifact quality

For at least one pilot paper:

- regenerate one downstream artifact that depends on saved state
- preferred surface:
  - `Meeting Pack`

Minimum acceptance:

- artifact generation still succeeds
- uncertainty/provenance language is not weaker than current behavior
- no obvious drop in evidence-linked support quality

### 5. Operational trust

For the pilot set:

- no new hidden failure mode is introduced
- pilot runs are clearly distinguishable from current-order runs

Pass rule:

- operator can explain which order ran and what changed without hidden reconstruction

## Suggested comparison record

For each paper, record:

- `paper_id`
- baseline run id
- pilot run id
- baseline selected attempt
- pilot selected attempt
- baseline claim count
- pilot claim count
- baseline resolved evidence span count
- pilot resolved evidence span count
- note-side state healthy: `yes/no`
- downstream artifact check run: `yes/no`
- blocker found: `yes/no`
- notes

## Automatic fail conditions

Stop the pilot if any of these happen:

- pilot requires changing the default runtime order globally
- claim yield drops without a strong qualitative explanation
- evidence linkage clearly weakens
- note-side state promotion becomes unstable
- downstream artifacts become less trustworthy
- rollout discussion starts relying on benchmark speed numbers alone

## Exit conditions

### Pilot may stay open if:

- the config gate works
- the quality checks pass
- the evidence remains bounded and inspectable

### Pilot may be promoted to a stronger proposal only if:

- all quality checks pass on the tiny set
- the default remains unchanged during the pilot
- the resulting note can describe the change as:
  - safer or at least equally safe
  - not merely faster

### Pilot must close if:

- quality evidence is mixed
- operator trust is lower
- the change only improves benchmark numbers without stable downstream quality

## Current decision boundary

Current best judgment:

> a config-gated `focused_first` pilot may be discussable, but only if this checklist is used first. Benchmark wins alone are not enough.

## Reproduction inputs

Current benchmark evidence:

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
