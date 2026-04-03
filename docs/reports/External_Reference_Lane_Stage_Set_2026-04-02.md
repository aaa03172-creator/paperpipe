# External Reference Lane Stage Set

Status: exact stage boundary
Date: 2026-04-02
Lane: `external-reference/followups`
Parent notes:
- [External_Reference_Lane_Packaging_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/External_Reference_Lane_Packaging_2026-04-01.md)
- [External_Reference_Followups_Closeout_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/External_Reference_Followups_Closeout_2026-04-01.md)

## Purpose

Freeze the smallest practical git-stage boundary for the concluded external-reference follow-up lane.

This note does not stage or commit anything.
It answers one narrower question:

- if this lane is packaged next, which files are whole-file safe, which files require patch staging, and which files should stay out?

## Diff Re-check Summary

The current remaining diffs were re-read directly for:

- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py)
- [ocr_fallback.py](/Users/jangseongjin/paperpipe/src/ingest/ocr_fallback.py)
- [reader_eval_sidecar.py](/Users/jangseongjin/paperpipe/src/services/reader_eval_sidecar.py)
- [Pending_PR_Queue.md](/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md)
- [README.md](/Users/jangseongjin/paperpipe/docs/reports/README.md)

Current judgment:

- the OCR fallback and compare-harness files are whole-file safe for this lane
- the external-reference docs, queue, and frozen manifest are whole-file safe for this lane
- the new deep-read handoff schema/artifact files are whole-file safe for this lane
- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py) is mixed and requires patch staging
- [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py) is mixed with clinical-extraction projection work and should stay out of the smallest safe stage set

## Whole-File Safe For This Lane

These files can be staged as whole files for the external-reference lane:

- [External_Reference_Action_Order_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/External_Reference_Action_Order_2026-04-01.md)
- [External_Reference_Followups_Closeout_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/External_Reference_Followups_Closeout_2026-04-01.md)
- [External_Reference_Lane_Packaging_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/External_Reference_Lane_Packaging_2026-04-01.md)
- [External_Reference_Lane_Stage_Set_2026-04-02.md](/Users/jangseongjin/paperpipe/docs/reports/External_Reference_Lane_Stage_Set_2026-04-02.md)
- [Hard_PDF_Evaluation_Slice_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/Hard_PDF_Evaluation_Slice_2026-04-01.md)
- [PaddleOCR_Fallback_Pilot_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/PaddleOCR_Fallback_Pilot_2026-04-01.md)
- [Reader_Attempt_Order_Reopen_Check_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/Reader_Attempt_Order_Reopen_Check_2026-04-01.md)
- [Pending_PR_Queue.md](/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md)
- [README.md](/Users/jangseongjin/paperpipe/docs/reports/README.md)
- [hard_pdf_eval_slice_20260401.json](/Users/jangseongjin/paperpipe/goldset/manifests/hard_pdf_eval_slice_20260401.json)
- [ocr_fallback.py](/Users/jangseongjin/paperpipe/src/ingest/ocr_fallback.py)
- [compare_ocr_backends.py](/Users/jangseongjin/paperpipe/scripts/eval/compare_ocr_backends.py)
- [reader_eval.py](/Users/jangseongjin/paperpipe/src/schemas/reader_eval.py)
- [deepread_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/deepread_handoff.py)
- [reader_eval_sidecar.py](/Users/jangseongjin/paperpipe/src/services/reader_eval_sidecar.py)
- [deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py)
- [test_ocr_fallback.py](/Users/jangseongjin/paperpipe/tests/test_ocr_fallback.py)
- [test_ocr_backend_eval.py](/Users/jangseongjin/paperpipe/tests/test_ocr_backend_eval.py)
- [test_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_artifacts.py)
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py)

Why these are safe together:

- they all support the same bounded story:
  - hard-PDF measurement
  - OCR fallback pilot hardening
  - reader-eval / handoff observability
  - explicit hold conclusions in queue/docs
- none of these files currently require a storage migration or default runtime policy change

## Split-Required File

- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)

Only the external-reference lane hunks belong here:

- import of `write_deepread_handoff_artifacts`
- helper `_persist_reader_analysis_metrics(...)`
- `reader_attempt_order` bootstrap/run-meta persistence
- `ReaderAgent(..., attempt_order=reader_attempt_order)`
- `_persist_reader_analysis_metrics(reader_agent)` calls on timeout and success
- additive `reader_eval_*_span_count` bootstrap-meta writes
- success/failure handoff artifact writes:
  - `acceptance_contract.json`
  - `quality_gate.json`
  - `context_manifest.json`

Why it must be split:

- the same file currently contains unrelated clinical-extraction work
- it also contains optional verifier import hardening that is not part of this lane
- blind whole-file staging would widen this patch beyond the external-reference boundary

## Keep-Out Files

Do not include these in the same stage set:

- [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py)
- [test_deepread_state_projection.py](/Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py)
- [DeepRead_Context_Manifest_Artifact_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Context_Manifest_Artifact_2026-04-01.md)
- `snapshots/ocr_backend_eval/`
- `.codex/work/2026-04-01_reference-fit-review/`
- `.codex/work/2026-04-01_ocr-pilot-env/`

Why they stay out:

- [deepread_state_projection.py](/Users/jangseongjin/paperpipe/src/services/deepread_state_projection.py) is currently mixed with clinical-extraction projection additions, not only context-manifest wiring
- [test_deepread_state_projection.py](/Users/jangseongjin/paperpipe/tests/test_deepread_state_projection.py) mirrors that same mixed boundary
- [DeepRead_Context_Manifest_Artifact_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Context_Manifest_Artifact_2026-04-01.md) explicitly describes the mixed state-projection integration and would overclaim if staged without it
- the remaining paths are generated pilot evidence, working files, or local environments

## Manual Stage Recipe

If this lane is staged next, the safest sequence is:

```bash
git add \
  /Users/jangseongjin/paperpipe/docs/reports/External_Reference_Action_Order_2026-04-01.md \
  /Users/jangseongjin/paperpipe/docs/reports/External_Reference_Followups_Closeout_2026-04-01.md \
  /Users/jangseongjin/paperpipe/docs/reports/External_Reference_Lane_Packaging_2026-04-01.md \
  /Users/jangseongjin/paperpipe/docs/reports/External_Reference_Lane_Stage_Set_2026-04-02.md \
  /Users/jangseongjin/paperpipe/docs/reports/Hard_PDF_Evaluation_Slice_2026-04-01.md \
  /Users/jangseongjin/paperpipe/docs/reports/PaddleOCR_Fallback_Pilot_2026-04-01.md \
  /Users/jangseongjin/paperpipe/docs/reports/Reader_Attempt_Order_Reopen_Check_2026-04-01.md \
  /Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md \
  /Users/jangseongjin/paperpipe/docs/reports/README.md \
  /Users/jangseongjin/paperpipe/goldset/manifests/hard_pdf_eval_slice_20260401.json \
  /Users/jangseongjin/paperpipe/src/ingest/ocr_fallback.py \
  /Users/jangseongjin/paperpipe/scripts/eval/compare_ocr_backends.py \
  /Users/jangseongjin/paperpipe/src/schemas/reader_eval.py \
  /Users/jangseongjin/paperpipe/src/schemas/deepread_handoff.py \
  /Users/jangseongjin/paperpipe/src/services/reader_eval_sidecar.py \
  /Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/tests/test_ocr_fallback.py \
  /Users/jangseongjin/paperpipe/tests/test_ocr_backend_eval.py \
  /Users/jangseongjin/paperpipe/tests/test_deepread_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py
git add -p /Users/jangseongjin/paperpipe/backend/services/job_runner.py
```

When patch-staging [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py), include only:

- reader-analysis persistence hunks
- reader-attempt-order hunks
- reader-eval locator-count hunks
- deep-read handoff artifact write hunks

Leave out:

- clinical-extraction imports
- clinical note detection / extraction helper functions
- clinical extraction runtime writes
- clinical markdown note rendering additions
- optional verifier import hardening

## Smallest Relevant Verification Before Staging

Run:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q tests/test_ocr_backend_eval.py tests/test_ocr_fallback.py
cd /Users/jangseongjin/paperpipe && pytest -q tests/test_reader_eval_sidecar.py tests/test_deepread_handoff_artifacts.py tests/test_deepread_state_projection.py tests/test_worker_job_runner_chain.py
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
cd /Users/jangseongjin/paperpipe && git diff --check
```

Current result at re-check time:

- OCR/test bundle passed: `10 passed`
- reader/handoff verification bundle passed: `15 passed`
- docs lint passed

## Short Version

The external-reference lane is stageable next, but not as a blind whole-file runtime patch.

The safe boundary is:

- whole-file stage the docs, frozen manifest, OCR hardening files, reader-eval/handoff schema files, and related tests
- patch-stage only the external-reference-specific hunks in [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- keep mixed clinical projection files and local pilot artifacts out
