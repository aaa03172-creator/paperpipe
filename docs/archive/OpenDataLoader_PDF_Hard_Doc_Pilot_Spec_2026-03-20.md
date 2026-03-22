# OpenDataLoader PDF Hard-Doc Pilot Spec

Status: Historical bounded pilot spec  
Date: 2026-03-20  
Owner: Repository maintainers  
Canonical parent: `docs/archive/OpenDataLoader_PDF_Fit_Review_2026-03-20.md`

## 1. Purpose

Define the safest possible pilot for evaluating `OpenDataLoader PDF` on hard-document subsets without reopening parser replacement scope.

This is a bounded experiment spec, not an approved migration plan.

## 2. Non-Goals

This pilot must **not**:

- replace the current default parser
- remove or bypass the current OCR fallback lane
- replace `DocumentArtifactV2`
- rewrite downstream extraction or RAG behavior
- introduce a new storage truth model
- turn hybrid mode into the default runtime path

## 3. Trigger Condition

Only run this pilot when the parser-adjacent reopen condition is explicitly met:

- a hard-document subset exists that is materially under-served by the current parser/OCR baseline
- the subset is identifiable before the pilot starts
- success can be judged on bounded parser-side outcomes rather than broad product claims

## 4. Pilot Shape

Keep the experiment constrained to:

- `limited pilot`
- `hard-document subset only`
- `deterministic local mode first`
- `batch-first execution`
- `sidecar artifacts only`

Explicitly exclude:

- always-on runtime integration
- single-file hot-path invocation during normal ingest
- hybrid mode as the primary pilot path

## 5. Candidate Corpus

Target size:

- `20–30` PDFs

Required hard-document categories:

- `scanned` or `image-based`
- `table-heavy`
- `formula-heavy`
- `text-poor`
- `layout-broken`

Optional priority signals from current runtime:

- `NO_TABLE_FOUND`
- `OCR_LOW_CONF`
- low usable text despite successful ingest
- table output present but degenerate or low-utility

Document manifest fields:

- `paper_id`
- `source_path`
- `subset_reason`
- `current_parser_backend`
- `ocr_applied`
- `table_failure_taxonomy`
- `text_len_baseline`
- `notes`

Use the bounded manifest shape from:

- `docs/archive/OpenDataLoader_PDF_Hard_Doc_Manifest_Spec_2026-03-20.md`

## 6. Comparison Matrix

Baseline arm:

- current `fitz_pdfplumber`
- current OCR fallback path where already applicable

Candidate arm:

- `OpenDataLoader PDF` local deterministic mode
- output formats: `markdown,json`
- batch execution only

Optional second-phase arm:

- `OpenDataLoader PDF` hybrid mode
- only if local deterministic mode leaves a clear remaining gap on the same hard-document subset

## 7. Output Handling

Do not replace current artifacts.

Store candidate outputs as sidecars only:

- `opendataloader_pdf/markdown/*.md`
- `opendataloader_pdf/json/*.json`
- optional normalized summary files for evaluation only

Suggested per-document sidecar metadata:

- `parser_name`
- `parser_mode`
- `batch_id`
- `source_pdf_path`
- `generated_at`
- `upstream_version`
- `quality_flags`
- `provenance`

Important:

- keep upstream raw JSON intact for inspection
- do not coerce it directly into canonical runtime schema during the pilot

## 8. Evaluation Dimensions

Primary parser-side metrics:

- text coverage / extracted text length
- heading recovery usefulness
- usable table recovery
- formula/caption presence where relevant
- bbox/provenance inspectability
- batch runtime

Operator-facing metrics:

- human debug usefulness
- easier source-block inspection
- easier table/caption validation

Downstream-adjacent but still bounded metrics:

- whether sidecar provenance would plausibly help evidence grounding
- whether Markdown output is chunk-friendly without extra cleanup

Do not use as primary pilot metrics:

- final RAG answer quality
- retrieval precision
- overall research-agent quality

## 9. Success Criteria

A pilot is successful only if all of these hold:

1. the hard-document subset shows repeatable parser-quality gains against the current baseline
2. the gains are visible on inspectable outputs, not just anecdotal impressions
3. the experiment does not require canonical schema replacement
4. rollback remains trivial because the outputs are sidecars only

Useful practical success signals:

- more usable tables on table-heavy PDFs
- better reading order on multi-column papers
- better structured text recovery on text-poor/scanned PDFs
- better block-level provenance for later manual review

## 10. Stop Conditions

Stop the pilot early if:

- deterministic local mode does not outperform the current baseline on the selected hard-doc subset
- batch execution overhead is too high for the observed quality gain
- output normalization becomes necessary just to make the pilot runnable
- reviewers start treating the sidecar as a replacement canonical artifact
- the pilot begins to drift into reader/RAG redesign

## 11. Hybrid Mode Gate

Hybrid mode may be evaluated only if:

- the local deterministic pilot already showed promise
- the remaining failures are mostly complex tables, OCR-heavy scans, or chart/formula cases
- the added backend/server complexity is acceptable for a bounded experiment

Hybrid mode must remain:

- opt-in
- subset-only
- batch-only
- easily removable

## 12. Rollback Plan

Rollback must be immediate and low-risk:

- disable the pilot flag
- stop generating sidecars
- keep the default parser path unchanged
- ignore existing sidecar outputs without touching canonical artifacts

If rollback requires schema or runtime surgery, the pilot was designed incorrectly.

## 13. Do Not Rewrite These Parts

- `src/ingest/parser_backends.py`
- `src/agents/ingest_agent.py`
- `src/contracts/document_artifact_v2.py`
- `docs/ocr_fallback.md`
- downstream reader / extraction / grounding / RAG layers

## 14. Safest Next 3 Experiments

1. Build a hard-document manifest from current parser/OCR failure signals and freeze that subset before any tool comparison.
2. Run a batch-only `fitz/pdfplumber` vs `OpenDataLoader PDF` local deterministic comparison and save raw outputs plus a simple score sheet.
3. Review only the hard-document subset with human inspection focused on tables, multi-column reading order, and provenance usefulness before considering any hybrid follow-up.
