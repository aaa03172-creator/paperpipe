# Hard PDF Evaluation Slice (2026-04-01)

Status: Active bounded evaluation note
Date: 2026-04-01
Owner: Lattice runtime maintainers
Canonical: `docs/reports/Hard_PDF_Evaluation_Slice_2026-04-01.md`

Related notes:
- `docs/reports/External_Reference_Action_Order_2026-04-01.md`
- `docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md`
- `docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md`
- `docs/archive/OpenDataLoader_PDF_Hard_Doc_Manifest_Spec_2026-03-20.md`
- `docs/ocr_fallback.md`
- `goldset/manifests/hard_pdf_eval_slice_20260401.json`

## Purpose

Freeze the first current-runtime hard-PDF evaluation slice for future ingest-side comparisons.

This note is intentionally narrow.

It does not:
- change the default parser backend
- approve any new OCR dependency
- reopen browser inference or model-serving work
- treat external references as product-direction changes

It answers one narrower question:
- if a new OCR or parser-side candidate is tested, which real local PDFs should define the first hard-case batch?

## Current judgment

The repo already has bounded parser-eval assets, but the current external-reference follow-up needs a smaller and more honest hard-case slice.

The right first move is not a broad new corpus.

It is:
- freeze a tiny set of real local PDFs that already showed repeatable hard-case signals in current saved eval artifacts
- keep the set fixed across future candidate comparisons
- explicitly record what this slice covers and what it does not

## Selected slice

Frozen manifest:
- `goldset/manifests/hard_pdf_eval_slice_20260401.json`

Current scope:
- `6` biomedical PDFs
- layout-heavy and table-heavy cases only
- chosen from saved repo-grounded Docling compare and section-quality audit signals

Current deliberate limitation:
- this v0 slice does **not** yet include a frozen real scanned/image-based subset
- current repo evidence for real scanned candidates is weaker than the evidence for the six selected layout/table cases
- synthetic OCR tests still exist, but they are not enough to claim a real scanned-document evaluation slice

## Why these six documents

### 1. `hanssonBloodBiomarkersAlzheimers2023.pdf`

Why it is in:
- the saved candidate compare needed `table_fallback_used=true`
- fallback fired on page `4`
- this is the cleanest current example of a page-aware fallback-sensitive table document

What it guards against:
- claiming a candidate is “fine” when it only passes because a hidden fallback rescued one specific page

### 2. `benedictCognitiveImpairmentMultiple2020.pdf`

Why it is in:
- the saved candidate compare flagged it as a `same_page_merge_doc`
- meaningful table count dropped from `2` to `1` while staying on the same page

What it guards against:
- silent page-level table merge drift that does not register as total table loss

### 3. `duboisClinicalDiagnosisAlzheimers2021.pdf`

Why it is in:
- the saved candidate compare also flagged it as a `same_page_merge_doc`
- meaningful table count dropped from `3` to `2`

What it guards against:
- over-crediting a candidate for “keeping the page” while still flattening table structure

### 4. `therriaultBiomarkerModelingAlzheimers2022.pdf`

Why it is in:
- the saved section audit flagged page `4` as `low_page_text_ratio`
- review bucket: `table_heavy_page`

What it guards against:
- page-level content thinning on table-heavy pages that does not become a full-document failure

### 5. `craftSafetyEfficacyFeasibility2020.pdf`

Why it is in:
- the saved section audit flagged page `8` as `low_page_text_ratio`
- review bucket: `table_and_figure_heavy_page`

What it guards against:
- mixed table/figure layouts where candidate extraction keeps only a thin residue of the page text

### 6. `olssonCSFBloodBiomarkers2016.pdf`

Why it is in:
- the saved section audit flagged pages `5-8` as `low_page_text_ratio`
- review bucket: `figure_heavy_page`

What it guards against:
- long figure-heavy review pages where page fidelity collapses even when the run still “passes”

## Why this is not a full hard-doc corpus yet

Current honest gaps:
- no frozen real scanned-PDF subset
- no frozen image-only subset
- no formula-heavy/math-heavy subset

Reason:
- current saved repo artifacts give stronger, more reproducible evidence for layout/table hard cases than for those other subtypes

So the right reading is:
- this is a `v0 hard-layout/table slice`
- not a complete universal hard-document benchmark

## How to use this slice

Allowed use:
- bounded ingest-side comparisons only
- candidate-vs-baseline runs using the same frozen manifest
- OCR fallback or parser candidate work that stays subordinate to the current runtime owner path

Recommended current command shape:

```bash
python3 scripts/eval/compare_ingest_backends.py \
  --manifest goldset/manifests/hard_pdf_eval_slice_20260401.json \
  --out-dir snapshots/ingest_backend_eval \
  --run-id hard_pdf_eval_slice_20260401_r1
```

Important note:
- the current compare script is parser-backend oriented and today is best aligned with the existing baseline vs optional backend lane
- if a future PaddleOCR pilot is added, reuse this manifest as the frozen input slice even if the comparison harness needs a narrow OCR-specific wrapper

## What to measure on this slice

Minimum metrics:
- backend availability or fallback activation
- text-char ratio by document
- low-page-text-ratio pages
- meaningful table loss docs
- same-page merge docs
- fallback pages

Preferable next metrics when the OCR pilot opens:
- downstream claim/evidence yield on the same paper set
- locator quality differences:
  - bbox-backed evidence
  - text-match-only evidence
  - unresolved/ambiguous evidence

## Stop conditions

Stop the next pilot if:
- the candidate only “passes” by adding broad hidden fallback behavior
- the candidate improves one doc while introducing new low-page-text-ratio failures elsewhere
- the candidate raises integration/ops cost without a clear quality gain on this slice
- reviewers start adding or removing PDFs after seeing candidate outputs

## Non-goals

Do not use this note to justify:
- default parser replacement
- OCR-first ingest
- changes to canonical runtime state or schemas
- generalized chat/session memory work
- broader product claims beyond bounded ingest evaluation

## Next bounded follow-up

The next worthwhile move after this note is:
1. keep this manifest frozen
2. add locator-quality visibility in the existing gate/eval path
3. only then open a fallback-only OCR candidate pilot against this same slice

## Bottom line

The repo did not need a new ingest architecture note.

It needed one honest frozen hard-case slice.

This note and its paired manifest provide that for the current layout-heavy and table-heavy biomedical PDFs, while explicitly leaving scanned/image-based hard cases for a later separate freeze.
