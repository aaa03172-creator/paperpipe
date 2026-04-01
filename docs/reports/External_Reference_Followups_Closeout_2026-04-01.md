# External Reference Follow-Ups Closeout (2026-04-01)

Status: concluded
Date: 2026-04-01
Owner: Lattice runtime maintainers
Canonical parent:
- `docs/reports/External_Reference_Action_Order_2026-04-01.md`

Related notes:
- `docs/reports/Hard_PDF_Evaluation_Slice_2026-04-01.md`
- `docs/reports/PaddleOCR_Fallback_Pilot_2026-04-01.md`
- `docs/reports/Reader_Attempt_Order_Reopen_Check_2026-04-01.md`
- `docs/reports/DeepRead_Context_Manifest_Artifact_2026-04-01.md`
- `docs/Pending_PR_Queue.md`

## Purpose

Record the actual stop point of the external-reference-driven follow-up lane.

This note is not:
- a new roadmap
- a reason to reopen a bounded pilot
- a replacement for the current runtime/product SSOT

It answers one narrower question:
- after the 2026-04-01 reference review and its bounded follow-ups, what actually changed and what should remain closed?

## What changed

### 1. Hard-case ingest measurement was made concrete

- `goldset/manifests/hard_pdf_eval_slice_20260401.json` is now frozen
- `docs/reports/Hard_PDF_Evaluation_Slice_2026-04-01.md` records the selection logic

Meaning:
- future OCR/parser comparisons can be judged against a fixed slice instead of anecdotes

### 2. Locator-quality visibility was added without tightening default gates

- locator-source counts are now surfaced in `reader_eval.json`
- deep-read `quality_gate.json` now exposes `evidence_locator_quality`

Meaning:
- operators can see more clearly when a claim is extracted but weakly grounded

### 3. PaddleOCR was evaluated as a bounded fallback candidate and left on hold

- the compare harness now exists at `scripts/eval/compare_ocr_backends.py`
- the pilot repaired a real baseline compatibility bug in `src/ingest/ocr_fallback.py`
- the pilot also repaired outdated candidate-side API assumptions and compare-gate logic
- the honest current result is still a hold:
  - `ocrmypdf` baseline works on this machine
  - `paddleocr` is installable and initializable in an isolated env
  - but candidate runtime/ops cost remains too high for the current local-first fallback lane

Meaning:
- keep runtime OCR behavior unchanged

### 4. Reader attempt-order work was fresh-checked and left on hold

- the repo already had the config gate, benchmark path, RFC, and tiny acceptance note
- fresh 2026-04-01 reruns on `park` and `lee` still showed opposite-winner behavior
- `focused_first` remains useful as an opt-in path, but not as a justified default-order change

Meaning:
- keep default attempt order unchanged
- keep `focused_first` config-gated only

### 5. Deep-read context composition is now easier to inspect

- `context_manifest.json` is now emitted as an additive deep-read artifact when `reader_analysis` exists

Meaning:
- future prompt/cost debugging can start from a compact artifact rather than raw logs

## What did not change

Do not reinterpret this lane as approval for:
- browser-first inference
- generalized multi-agent runtime work
- unofficial Claude/Claw-style harness adoption
- new default OCR backends
- new default reader attempt order
- broader `Project` / chat / memory platform work

## Current hold posture

Current bounded holds are:
- PaddleOCR fallback integration
- broader default attempt-order work

Both are now measured holds, not “not yet looked at” holds.

## Reopen conditions

Only reopen one of these holds if fresh evidence appears:

- OCR lane:
  - a materially faster bounded PaddleOCR configuration appears
  - or a narrower hard-case lane shows a meaningful downstream benefit
- reader attempt-order lane:
  - a fixed multi-document slice shows representative unresolved tail pain
  - and downstream claim/evidence quality remains stable enough to justify another pilot

## Bottom line

The 2026-04-01 external-reference work is now closed to a useful stop point.

The durable repo-grounded outcome is:
- add better measurement
- add better observability
- keep both speculative runtime changes on hold
