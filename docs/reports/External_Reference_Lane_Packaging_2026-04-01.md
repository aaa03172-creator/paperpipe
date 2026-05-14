# External Reference Lane Packaging (2026-04-01)

Status: Active packaging note
Date: 2026-04-01
Owner: Lattice runtime maintainers
Canonical: `docs/reports/External_Reference_Lane_Packaging_2026-04-01.md`

Related notes:
- `docs/reports/External_Reference_Action_Order_2026-04-01.md`
- `docs/reports/External_Reference_Followups_Closeout_2026-04-01.md`
- `docs/reports/External_Reference_Lane_Stage_Set_2026-04-02.md`
- `docs/reports/PaddleOCR_Fallback_Pilot_2026-04-01.md`
- `docs/reports/Reader_Attempt_Order_Reopen_Check_2026-04-01.md`
- `docs/Pending_PR_Queue.md`

## Purpose

Package the 2026-04-01 external-reference follow-up tail as one bounded measurement/observability lane inside the mixed dirty tree.

This note is not:
- a new runtime roadmap
- a parser-adoption note
- a default reader-policy change note

Its job is narrower:
- show what belongs to the concluded external-reference follow-up bundle
- keep that bundle separate from unrelated runtime, UI, and packaging tails
- keep generated pilot evidence out of source-oriented staging by default

## Current judgment

This lane is real work, but it is already concluded to a useful stop point.

The right packaging read is:
- keep the source/doc changes together as one bounded hardening lane
- do not reinterpret the lane as approval for broader runtime adoption
- do not mix in generated pilot artifacts or unrelated dirty-tree work

Important current worktree note:
- some tracked owner files inside the conceptual lane are mixed with unrelated changes
- use `docs/reports/External_Reference_Lane_Stage_Set_2026-04-02.md` for the exact staging boundary rather than blindly staging the full included-source list below

## Included source tail

### A. Runtime and evaluation hardening changes

- `backend/services/job_runner.py`
- `src/schemas/reader_eval.py`
- `src/schemas/deepread_handoff.py`
- `src/services/reader_eval_sidecar.py`
- `src/services/deepread_handoff_artifacts.py`
- `src/services/deepread_state_projection.py`
- `src/ingest/ocr_fallback.py`
- `scripts/eval/compare_ocr_backends.py`
- `tests/test_ocr_fallback.py`
- `tests/test_ocr_backend_eval.py`

Interpretation:
- these changes add bounded observability and pilot support
- they do not change the default OCR runtime path
- they do not change the default reader attempt order

### B. Docs, queue, and bounded review records

- `docs/reports/External_Reference_Action_Order_2026-04-01.md`
- `docs/reports/External_Reference_Followups_Closeout_2026-04-01.md`
- `docs/reports/Hard_PDF_Evaluation_Slice_2026-04-01.md`
- `docs/reports/PaddleOCR_Fallback_Pilot_2026-04-01.md`
- `docs/reports/Reader_Attempt_Order_Reopen_Check_2026-04-01.md`
- `docs/reports/DeepRead_Context_Manifest_Artifact_2026-04-01.md`
- `docs/Pending_PR_Queue.md`
- `docs/reports/README.md`

Interpretation:
- these files record what was opened, what was learned, and what remains on hold
- they keep the queue posture aligned with the actual measured stop point

### C. Frozen fixture input

- `goldset/manifests/hard_pdf_eval_slice_20260401.json`

Interpretation:
- this manifest is a bounded source input for future hard-PDF evaluation
- it is part of the lane because the OCR pilot and its docs depend on it

## Explicit exclusions

Do not stage these as part of the source-oriented lane by default:

- `snapshots/ocr_backend_eval/`
- `.codex/work/2026-04-01_reference-fit-review/`
- `.codex/work/2026-04-01_ocr-pilot-env/`
- `storage/`
- unrelated runtime/frontend/docs dirty paths outside the file list above

Why:
- these are generated pilot outputs, working notes, local environments, runtime state, or a different lane
- they are useful as local evidence, but they should not define the source packaging boundary

## Current recommendation

If this lane is reviewed or staged later, treat it as one bounded external-reference hardening bundle.

The intended reading is:
1. better hard-case measurement
2. better evidence/context observability
3. two measured holds:
   - PaddleOCR integration
   - broader default attempt-order work

Do not split this lane in a way that hides those conclusions.

## Verification

Minimum verification already exercised on the current tree:

```bash
pytest -q tests/test_ocr_backend_eval.py tests/test_ocr_fallback.py
pytest -q tests/test_reader_eval_sidecar.py tests/test_deepread_handoff_artifacts.py tests/test_deepread_state_projection.py tests/test_worker_job_runner_chain.py
python3 scripts/lint_docs.py
```

## Relationship to current packaging notes

- `docs/reports/Current_State_Packaging_2026-03-24.md` remains the top-level mixed-worktree separation note
- `docs/reports/Current_State_Staging_Guide_2026-03-24.md` remains the general staging rule
- this note only packages the bounded external-reference follow-up tail inside that larger model

## Bottom line

Treat this lane as:
- small
- real
- already measured
- already concluded

Do not widen it from packaging momentum alone.
