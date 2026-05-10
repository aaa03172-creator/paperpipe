# Clinical Evidence Extraction Stage Set

Status: exact stage boundary
Date: 2026-04-09
Lane: `clinical-evidence-extraction/runtime-split`
Parent notes:
- [DeepRead_Handoff_Quality_Loop_Stage_Set_2026-04-09.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Quality_Loop_Stage_Set_2026-04-09.md)
- [Runtime_Readiness_Lane_Packaging_2026-04-07.md](/Users/jangseongjin/paperpipe/docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md)

## Purpose

Freeze the next safe git-stage boundary for the remaining clinical extraction and evidence-extraction runtime slice after the deep-read handoff quality-loop lane was committed separately.

This note does not stage or commit anything.
It answers one narrower question:

- if the next lane is cut from the current mixed dirty tree, which files are whole-file safe, which files require hunk-splitting, and which files should stay out?

## Diff Re-check Summary

The current remaining diffs were re-read directly for:

- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [citation_grounding.py](/Users/jangseongjin/paperpipe/src/services/citation_grounding.py)
- [deepread_note_writer.py](/Users/jangseongjin/paperpipe/src/services/deepread_note_writer.py)
- [evidence_extraction.py](/Users/jangseongjin/paperpipe/src/schemas/evidence_extraction.py)
- [evidence_extraction_sidecar.py](/Users/jangseongjin/paperpipe/src/services/evidence_extraction_sidecar.py)
- [test_citation_grounding.py](/Users/jangseongjin/paperpipe/tests/test_citation_grounding.py)
- [test_deepread_note_writer.py](/Users/jangseongjin/paperpipe/tests/test_deepread_note_writer.py)
- [test_evidence_extraction_sidecar.py](/Users/jangseongjin/paperpipe/tests/test_evidence_extraction_sidecar.py)
- [test_job_runner_clinical_extraction.py](/Users/jangseongjin/paperpipe/tests/test_job_runner_clinical_extraction.py)
- [test_biomedical_clinical_extraction_schema.py](/Users/jangseongjin/paperpipe/tests/test_biomedical_clinical_extraction_schema.py)
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py)
- [config.py](/Users/jangseongjin/paperpipe/src/config.py)
- [llm_provider.py](/Users/jangseongjin/paperpipe/src/llm_provider.py)
- [core.py](/Users/jangseongjin/paperpipe/src/schemas/core.py)
- [__init__.py](/Users/jangseongjin/paperpipe/src/schemas/__init__.py)
- [README.md](/Users/jangseongjin/paperpipe/docs/README.md)
- [README.md](/Users/jangseongjin/paperpipe/docs/reports/README.md)

Current judgment:

- the dedicated evidence-bundle schema/service files, the clinical note markdown helper, and their dedicated tests are coherent enough to review as one lane
- the document-block bbox enrichment in [citation_grounding.py](/Users/jangseongjin/paperpipe/src/services/citation_grounding.py) is coherent with the same lane, but it should move in lockstep with the matching `document_artifact=` hunk in [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py) is mixed and must not be staged wholesale from the current dirty tree
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py) is mixed with already-committed deep-read handoff follow-up assertions and must not be staged wholesale
- [config.py](/Users/jangseongjin/paperpipe/src/config.py), [llm_provider.py](/Users/jangseongjin/paperpipe/src/llm_provider.py), [core.py](/Users/jangseongjin/paperpipe/src/schemas/core.py), and [__init__.py](/Users/jangseongjin/paperpipe/src/schemas/__init__.py) are currently mixed with install-layout, escalation-judge, schema-barrel, and other unrelated runtime changes, so they should stay out of the smallest safe split
- the docs index files are still mixed with unrelated canonical-doc and runtime-index additions and should stay out

## Whole-File Safe For This Lane

These files can be staged as whole files for the clinical extraction and evidence-bundle lane:

- [Clinical_Evidence_Extraction_Stage_Set_2026-04-09.md](/Users/jangseongjin/paperpipe/docs/reports/Clinical_Evidence_Extraction_Stage_Set_2026-04-09.md)
- [evidence_extraction.py](/Users/jangseongjin/paperpipe/src/schemas/evidence_extraction.py)
- [evidence_extraction_sidecar.py](/Users/jangseongjin/paperpipe/src/services/evidence_extraction_sidecar.py)
- [citation_grounding.py](/Users/jangseongjin/paperpipe/src/services/citation_grounding.py)
- [deepread_note_writer.py](/Users/jangseongjin/paperpipe/src/services/deepread_note_writer.py)
- [test_citation_grounding.py](/Users/jangseongjin/paperpipe/tests/test_citation_grounding.py)
- [test_biomedical_clinical_extraction_schema.py](/Users/jangseongjin/paperpipe/tests/test_biomedical_clinical_extraction_schema.py)
- [test_evidence_extraction_sidecar.py](/Users/jangseongjin/paperpipe/tests/test_evidence_extraction_sidecar.py)
- [test_job_runner_clinical_extraction.py](/Users/jangseongjin/paperpipe/tests/test_job_runner_clinical_extraction.py)
- [test_deepread_note_writer.py](/Users/jangseongjin/paperpipe/tests/test_deepread_note_writer.py)

Why these are safe together:

- they all support the same bounded story:
  - optional biomedical clinical extraction for clinical notes
  - additive evidence-extraction bundle generation from existing resolved claimsets and optional clinical artifacts
  - bounded note rendering for clinical extraction output
- they do not require a DB migration or a new runtime owner
- they do not, by themselves, reopen workspace, packaging, or escalation-judge semantics

## Split-Required Files

- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)

Only the clinical/evidence lane hunks belong here:

- `resolve_clinical_extraction_feature` import only if required by the staged clinical extraction block
- `DocumentArtifactV2`, `get_artifact_header`, `iter_text_sections`, `get_llm_provider`, `BiomedicalClinicalExtraction`, `build_clinical_extraction_markdown`, `build_evidence_extraction_bundle`, and `write_evidence_extraction_bundle` imports
- `_is_clinical_note(...)`
- `_build_biomedical_clinical_extraction_inputs(...)`
- `artifact_clinical_extraction_written`, `clinical_extraction_status`, and `clinical_extraction_note_type` bootstrap/run-meta fields
- the clinical extraction artifact write block after document ingest
- `resolve_claimset_grounding(..., document_artifact=...)` only when [citation_grounding.py](/Users/jangseongjin/paperpipe/src/services/citation_grounding.py) is staged in the same lane for document-block bbox enrichment
- the `evidence_extraction_bundle.json` build/write block
- `clinical_md` rendering into `build_deepread_markdown(...)`

Leave out from this file in the smallest safe split:

- `_persist_reader_analysis_metrics(...)` placement and related `reader_analysis` persistence hunks
- `reader_attempt_order` / timeout-budget wiring that belongs with the already-committed deep-read quality-loop lane
- optional `StatsVerificationAgent` import hardening
- any unrelated note-upsert or runtime-shape changes not required for clinical extraction or evidence bundle output

- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py)

Only include hunks that are directly about:

- `evidence_extraction_bundle.json` existence
- evidence-bundle metrics written into `bootstrap_meta.json`
- evidence-bundle content assertions

Leave out from this file:

- `step_stability_summary`
- `failure_recovery_summary`
- `goal_drift_summary`
- `hard_fail_codes`

Why these files must be split:

- both files still contain follow-on assertions or helper changes from the deep-read quality-loop lane that was already committed separately
- blind whole-file staging would recreate cross-lane coupling instead of shrinking it

## Keep-Out Files

Do not include these in the same smallest stage set:

- [config.py](/Users/jangseongjin/paperpipe/src/config.py)
- [llm_provider.py](/Users/jangseongjin/paperpipe/src/llm_provider.py)
- [core.py](/Users/jangseongjin/paperpipe/src/schemas/core.py)
- [__init__.py](/Users/jangseongjin/paperpipe/src/schemas/__init__.py)
- [README.md](/Users/jangseongjin/paperpipe/docs/README.md)
- [README.md](/Users/jangseongjin/paperpipe/docs/reports/README.md)
- [deepread_handoff_eval](/Users/jangseongjin/paperpipe/snapshots/deepread_handoff_eval)
- [deepread_handoff_gate](/Users/jangseongjin/paperpipe/snapshots/deepread_handoff_gate)
- [deepread_handoff_gate_runs](/Users/jangseongjin/paperpipe/snapshots/deepread_handoff_gate_runs)
- [2026-04-08_reference-fit-review](/Users/jangseongjin/paperpipe/.codex/work/2026-04-08_reference-fit-review)

Why they stay out:

- [config.py](/Users/jangseongjin/paperpipe/src/config.py) is mixed with install-layout defaults and reader-attempt-order config, not only clinical extraction gating
- [llm_provider.py](/Users/jangseongjin/paperpipe/src/llm_provider.py) is dominated by escalation-judge and specialty-trial diagnostic changes, not only the generic biomedical clinical extraction path
- [core.py](/Users/jangseongjin/paperpipe/src/schemas/core.py) is currently about escalation-result fields, not the evidence-bundle contract
- [__init__.py](/Users/jangseongjin/paperpipe/src/schemas/__init__.py) is a broad schema-barrel expansion covering multiple unrelated new schema families
- the two README files are mixed index updates for several other canonical docs and runtime notes
- the `snapshots/` paths are generated local evidence, not source-of-truth runtime files
- the `.codex/work/` path is task-local planning context only

## Safest Next Split Move

Do not stage this lane directly from the current dirty tree unless you are willing to patch-stage mixed owners carefully.

The safer path is:

1. start from the current HEAD that already includes `5b73a2b`
2. whole-file stage the dedicated schema/service/test files listed above
3. patch-stage [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py) for only the clinical extraction and evidence-bundle hunks
4. patch-stage [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py) only if you explicitly want the runtime smoke to cover the bundle output in the same commit
5. keep config/provider/schema-barrel/doc-index files out until they are split on their own lane

## Manual Stage Recipe

If this lane is staged next, the safest sequence is:

```bash
git add \
  /Users/jangseongjin/paperpipe/docs/reports/Clinical_Evidence_Extraction_Stage_Set_2026-04-09.md \
  /Users/jangseongjin/paperpipe/src/schemas/evidence_extraction.py \
  /Users/jangseongjin/paperpipe/src/services/evidence_extraction_sidecar.py \
  /Users/jangseongjin/paperpipe/src/services/citation_grounding.py \
  /Users/jangseongjin/paperpipe/src/services/deepread_note_writer.py \
  /Users/jangseongjin/paperpipe/tests/test_citation_grounding.py \
  /Users/jangseongjin/paperpipe/tests/test_biomedical_clinical_extraction_schema.py \
  /Users/jangseongjin/paperpipe/tests/test_evidence_extraction_sidecar.py \
  /Users/jangseongjin/paperpipe/tests/test_job_runner_clinical_extraction.py \
  /Users/jangseongjin/paperpipe/tests/test_deepread_note_writer.py
git add -p /Users/jangseongjin/paperpipe/backend/services/job_runner.py
```

Optional only if you explicitly want the smoke-path bundle assertions in the same commit:

```bash
git add -p /Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py
```

## Smallest Relevant Verification Before Staging

Run:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_citation_grounding.py \
  tests/test_biomedical_clinical_extraction_schema.py \
  tests/test_evidence_extraction_sidecar.py \
  tests/test_job_runner_clinical_extraction.py \
  tests/test_deepread_note_writer.py
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
cd /Users/jangseongjin/paperpipe && git diff --check
```

If the `job_runner.py` hunk split is included, add:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q tests/test_worker_job_runner_chain.py -k "clinical or evidence_extraction or deepread"
```

## Short Version

The next runtime-adjacent lane is probably the clinical extraction plus evidence-extraction bundle slice, but it is not safe to lift blindly from the current dirty tree.

The safe boundary is:

- whole-file stage the dedicated evidence-bundle schema/service files, optional citation-grounding bbox enrichment, bounded clinical note renderer changes, and dedicated tests
- patch-stage only the relevant clinical/evidence hunks in [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- optionally patch-stage the bundle assertions in [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py)
- keep config/provider/schema-barrel/doc-index files out because they are mixed with other lanes
