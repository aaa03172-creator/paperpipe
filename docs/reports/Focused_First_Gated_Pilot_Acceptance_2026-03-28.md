# Focused-First Gated Pilot Acceptance

Status: tiny opt-in pilot recorded, default unchanged
Date: 2026-03-28
Owner: runtime/product maintainers
Canonical parents:
- `docs/reports/Reader_Attempt_Order_RFC_2026-03-28.md`
- `docs/reports/Focused_First_Gated_Pilot_Acceptance_Checklist_2026-03-28.md`
- `docs/reports/Focused_First_Reader_Benchmark_2026-03-28.md`
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`

## Purpose

Record the smallest real opt-in pilot for `focused_first` attempt order without changing the default runtime behavior.

This note is not:

- a default-order adoption note
- a product-facing speed claim
- a reason to reopen TurboQuant

## Pilot shape

- config gate:
  - `llm.reader_attempt_order: focused_first`
- config file used:
  - `.codex/work/2026-03-28_focused-first-pilot-acceptance/config.focused_first.yaml`
- default runtime order outside the pilot:
  - unchanged
- pilot scope:
  - `2` representative papers
  - `1` downstream `Meeting Pack` generation

## Pilot set

### Paper A

- `paper_id`:
  - `zotero:coricTargetingProdromalAlzheimer2015`
- baseline run:
  - `run_20260327_171016`
- pilot run:
  - `run_20260328_002407`

### Paper B

- `paper_id`:
  - `zotero:parkDiscoveryDualactionSmall2022`
- baseline run:
  - `run_20260324_032111`
- pilot run:
  - `run_20260328_002659`

## Acceptance result

### 1. Claim yield

#### Paper A

- baseline order:
  - `current`
- pilot order:
  - `focused_first`
- baseline selected attempt:
  - `focused`
- pilot selected attempt:
  - `focused`
- baseline claim count:
  - `3`
- pilot claim count:
  - `5`

Result:

- no claim-yield regression

#### Paper B

- baseline order:
  - `current`
- pilot order:
  - `focused_first`
- baseline selected attempt:
  - not recorded in the older baseline run metadata
- pilot selected attempt:
  - `focused`
- baseline resolved evidence span count:
  - `3`
- pilot claim count:
  - `3`

Result:

- no observed claim-yield regression relative to the stored baseline artifact

### 2. Evidence linkage quality

#### Paper A

- baseline resolved evidence span count:
  - `3`
- pilot resolved evidence span count:
  - `5`

Result:

- no weakening observed

#### Paper B

- baseline resolved evidence span count:
  - `3`
- pilot resolved evidence span count:
  - `3`

Result:

- no weakening observed

### 3. Note-side state quality

#### Paper A

- state path:
  - `.pp/zoterocoricTargetingProdromalAlzheimer2015/state.json`
- state exists:
  - `yes`
- latest run id:
  - `run_20260328_002407`
- state source:
  - `deep_read_promotion`
- deep-read section count in note:
  - `1`

#### Paper B

- state path:
  - `.pp/zoteroparkDiscoveryDualactionSmall2022/state.json`
- state exists:
  - `yes`
- latest run id:
  - `run_20260328_002659`
- state source:
  - `deep_read_promotion`
- deep-read section count in note:
  - `1`

Result:

- note-side promotion remained non-destructive on both pilot papers

### 4. Downstream artifact quality

Pilot downstream artifact:

- type:
  - `Meeting Pack`
- source slug:
  - `zoterocoricTargetingProdromalAlzheimer2015`
- mode:
  - `journal_club`
- generated pack id:
  - `meetingpack_20260328T002905485413Z_journal_club_0409564f`
- temp root:
  - `tmp/focused_first_pilot_meeting_pack`
- readiness:
  - `evidence_backed`
- slide count:
  - `6`
- evidence refs:
  - `5`
- one-page uncertainties:
  - `2`
- key-point uncertainty notes:
  - `2`
- markdown sync:
  - `in_sync`

Result:

- downstream artifact generation succeeded
- uncertainty remained visible
- no obvious trust regression was observed

### 5. Operational trust

Observed:

- pilot runs are distinguishable via:
  - `run_meta.json`
  - `bootstrap_meta.json`
  - `reader_analysis.configured_attempt_order`
  - `reader_attempt_order`
- default runtime order outside the pilot was not changed

Result:

- operator can explain what changed without hidden reconstruction

## Decision

Current best judgment:

1. the tiny opt-in pilot passed its acceptance bar
2. the default runtime order should still remain unchanged
3. `focused_first` may stay available as an explicit opt-in path
4. broader adoption still requires more than this tiny pilot

## Not concluded from this pilot

This note does not prove:

- that `focused_first` should become the default runtime order
- that broader corpus quality is already known
- that product-facing speed claims are justified

## Reproduction sketch

Use:

- `PAPERPIPE_CONFIG_PATH=.codex/work/2026-03-28_focused-first-pilot-acceptance/config.focused_first.yaml`
- `PAPERPIPE_PROFILES_PATH=config/profiles.yaml`

Run:

- `backend.services.job_runner.run_deepread_job(...)` for the two paper ids above
- `src.meeting_packs.service.generate_meeting_pack(...)` for the recorded slug above
