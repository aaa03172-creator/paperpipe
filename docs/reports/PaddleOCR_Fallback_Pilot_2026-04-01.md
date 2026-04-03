# PaddleOCR Fallback Pilot (2026-04-01)

Status: Concluded bounded pilot note
Date: 2026-04-01
Owner: Lattice runtime maintainers
Canonical: `docs/reports/PaddleOCR_Fallback_Pilot_2026-04-01.md`

Related notes:
- `docs/reports/External_Reference_Action_Order_2026-04-01.md`
- `docs/reports/Hard_PDF_Evaluation_Slice_2026-04-01.md`
- `goldset/manifests/hard_pdf_eval_slice_20260401.json`
- `scripts/eval/compare_ocr_backends.py`
- `docs/ocr_fallback.md`

## Purpose

Open the PaddleOCR follow-up as a bounded pilot harness, not as a runtime default.

This note does not:
- change the current OCR fallback owner path
- add PaddleOCR as an automatic runtime dependency
- claim PaddleOCR is already validated on this machine

It answers one narrower question:
- how should PaperPipe compare `ocrmypdf` against a future optional `paddleocr` candidate on the frozen hard-PDF slice?

## Current status

Current machine status:
- baseline path:
  - `ocrmypdf 17.4.0` is now installed via Homebrew
- candidate path:
  - `paddleocr 3.4.0` and `paddlepaddle 3.3.1` are installable on this machine
  - they currently require an isolated pilot-only Python environment:
    - `.codex/work/2026-04-01_ocr-pilot-env/.venv`

Compatibility fixes made during the pilot:
- `src/ingest/ocr_fallback.py`
  - removed the invalid `ocrmypdf` flag combination `--skip-text` plus `--force-ocr`
- `scripts/eval/compare_ocr_backends.py`
  - updated PaddleOCR result parsing for the current API
  - updated compare-gate logic so backend execution failures no longer appear as a false `passed=true` result

Saved runs:
- `snapshots/ocr_backend_eval/paddleocr_hard_pdf_slice_r1/metrics.json`
- `snapshots/ocr_backend_eval/paddleocr_hard_pdf_slice_r2/metrics.json`

Observed results:
- `r1`
  - both backends unavailable
  - useful only as an environment-status snapshot
- `r2`
  - environment was prepared, but the first real run exposed two harness/runtime compatibility bugs:
    - baseline `ocrmypdf` invocation was invalid
    - candidate `paddleocr` call path used an outdated API shape
- after the fixes:
  - baseline `ocrmypdf` now produces OCR output PDFs across the frozen hard slice
  - candidate `paddleocr` initializes and downloads models successfully
  - but full-slice and single-doc candidate probes were still too slow for the current bounded pilot:
    - `paddleocr_hard_pdf_slice_r3`
      - baseline side wrote all `ocrmypdf` outputs
      - candidate side was manually stopped after an extended CPU-bound run with no completed candidate output artifact yet
    - `paddleocr_craft_probe_r1`
      - same pattern on the smallest current hard-case paper: baseline artifact written, candidate probe remained too slow and was stopped

So the blocker has changed:
- no longer `not installable`
- now `runtime/ops cost is too high for the current bounded fallback pilot`

Current repo-stage decision:
- keep the current runtime OCR path unchanged
- do not add `paddleocr` as a default dependency or automatic fallback backend
- treat this candidate as a measured hold for the current local-first fallback lane
- only reopen if a materially faster configuration or a much narrower hard-case lane appears

## Pilot harness

Current harness:
- `scripts/eval/compare_ocr_backends.py`

What it does now:
- reads one or more PDFs directly or from a manifest
- runs baseline OCR with `ocrmypdf`
- attempts candidate OCR with `paddleocr` when installed
- records:
  - backend availability
  - success/error
  - text-char recovery
  - page-level text-char counts
  - elapsed seconds

What it does not do yet:
- table-structure comparison
- downstream claim/evidence comparison
- searchable-PDF generation from PaddleOCR output

That limitation is intentional.

This is a pilot harness, not a hidden ingest architecture change.

## Why this shape

Reason for using a harness first:
- current runtime already has a safe OCR fallback path
- a direct runtime integration now would create code and ops drift without acceptable bounded-run cost

Reason for using page-image OCR for the candidate path:
- recent public issue history around PDF handling in PaddleOCR suggests that direct PDF input behavior can be fragile or page-incomplete
- the pilot harness avoids that ambiguity by rasterizing PDF pages locally and OCR-ing page images one by one

This keeps the comparison narrower and more diagnosable.

## Frozen input slice

Use only:
- `goldset/manifests/hard_pdf_eval_slice_20260401.json`

Do not:
- add new PDFs mid-pilot
- silently widen from layout/table cases into a generic OCR benchmark

## Suggested commands

```bash
/Users/jangseongjin/paperpipe/.codex/work/2026-04-01_ocr-pilot-env/.venv/bin/python scripts/eval/compare_ocr_backends.py \
  --manifest goldset/manifests/hard_pdf_eval_slice_20260401.json \
  --out-dir snapshots/ocr_backend_eval \
  --run-id paddleocr_hard_pdf_slice_r1
```

Single-doc viability probe:

```bash
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
/Users/jangseongjin/paperpipe/.codex/work/2026-04-01_ocr-pilot-env/.venv/bin/python scripts/eval/compare_ocr_backends.py \
  --pdf '/Users/jangseongjin/Zotero/storage/WM2TPU62/Craft 등 - 2020 - Safety, Efficacy, and Feasibility of Intranasal Insulin for the Treatment of Mild Cognitive Impairme.pdf' \
  --out-dir snapshots/ocr_backend_eval \
  --run-id paddleocr_craft_probe_r1
```

## Success bar for reopening deeper integration

Only reopen a deeper PaddleOCR integration if all of these become true:
- PaddleOCR is actually installable on the target local machine
- the candidate run completes on the frozen hard-PDF slice
- candidate runtime cost is acceptable enough to fit the current fallback lane
- candidate text recovery is not materially worse on hard pages
- the added ops burden looks acceptable

## Decision for the current repo stage

This pilot is now bounded and closed for the current stage.

What was learned:
- the baseline `ocrmypdf` path is now working again on this machine
- the candidate `paddleocr` path can be installed and initialized in an isolated env
- the pilot harness uncovered and fixed real compatibility issues in both baseline and candidate execution paths
- but the candidate still does not fit the current fallback lane well enough because runtime/ops cost remains too high

What this means in practice:
- do not wire PaddleOCR into `src/agents/ingest_agent.py`
- do not add a runtime config switch that implies production readiness
- do not widen this into a generic OCR-platform or document-AI lane

The current recommendation is a hold, not an adoption.

## Non-goals

Do not use this note to justify:
- default OCR backend replacement
- browser OCR work
- model-serving/platform work
- reopening scanned/image-based subtypes before they are separately frozen

## Bottom line

The honest current result is not “PaddleOCR is ready.”

It is:
- the hard-PDF slice is frozen
- the OCR compare harness now works against current local dependencies
- the baseline `ocrmypdf` path is now usable again on this machine
- the candidate `paddleocr` path is installable and initializable
- but current candidate runtime cost is too high to justify moving beyond a bounded pilot
- so the candidate should remain on hold unless a materially faster bounded configuration appears
