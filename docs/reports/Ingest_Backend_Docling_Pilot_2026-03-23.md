# Ingest Backend Docling Pilot

Status: bounded evaluation report  
Date: 2026-03-23  
Lane: `ingest-backend-eval`

## Purpose

Run the new bounded ingest backend comparison harness on a small real local PDF set and determine whether `docling` is ready for a parser pilot in this environment.

## Bounded Manifest

The reusable manifest for this pilot is:

- [ingest_backend_pilot_20260323.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_20260323.json)
- [ingest_backend_pilot_expanded_20260323.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_expanded_20260323.json)
- [ingest_backend_pilot_expanded_broad_20260324.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_expanded_broad_20260324.json)

It exists to avoid:
- empty placeholder PDFs
- ad hoc sample drift
- overreading the entire local library

## Command

```bash
python3 scripts/eval/compare_ingest_backends.py \
  --pdf Library/1411.2441.pdf \
  --pdf Library/2023/2023_Smith_Deep_Learning_for_Medical_Imaging.pdf \
  --pdf Library/2026/2026_Unknown_Unknown_Paper.pdf \
  --pdf docs/Stats_Verification_Agent_Spec.pdf \
  --out-dir snapshots/ingest_backend_eval \
  --run-id docling_pilot_20260323_r2
```

## Output Artifacts

- `snapshots/ingest_backend_eval/docling_pilot_20260323_r2/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_20260323_r2/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_20260323_r2/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r3/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r3/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r3/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r4/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r4/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r4/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r5/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r5/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r5/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r6/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r6/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r6/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r7/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r7/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r7/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r8/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r8/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r8/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r9/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r9/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r9/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_20260323_r10/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_20260323_r10/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_20260323_r10/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_20260323_r11/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_20260323_r11/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_20260323_r11/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_20260323_r12/summary.json`
- `snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_20260323_r12/details.json`
- `snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_20260324_r13/summary.json`
- `snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_20260324_r13/details.json`
- `snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_20260324_r14/summary.json`
- `snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_20260324_r14/details.json`
- `snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_20260324_r15/summary.json`
- `snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_20260324_r15/details.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_broad_20260324_r16/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_broad_20260324_r16/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_broad_20260324_r16/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_broad_20260324_r17/summary.json`
- `snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_broad_20260324_r17/details.json`
- `snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_broad_20260324_r18/summary.json`
- `snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_broad_20260324_r18/details.json`

## Sample Set

- `Library/1411.2441.pdf`
- `Library/barulliEfficiencyCapacityCompensation2013.pdf`
- `Library/chandraGutMicrobiomeAlzheimers2023.pdf`
- `Library/hanssonBloodBiomarkersAlzheimers2023.pdf`
- `Library/pichetbinetteConfoundingFactorsAlzheimers2023.pdf`
- `Library/therriaultBiomarkerModelingAlzheimers2022.pdf`

Observed sample caveats:
- this manifest intentionally excludes empty placeholder PDFs discovered during the first ad hoc probe
- baseline extraction found tables in at least two documents, so this sample is better than the initial ad hoc set for parser-side sanity checks

## Result

Latest verdict should be read from `r9`, which keeps the `r8` hybrid table behavior and restores page-aware docling text sections instead of collapsing each document to one section.

- overall decision: `passed`
- failed check: none
- baseline backend: `fitz_pdfplumber`
- candidate backend: `docling`
- baseline success count: `6 / 6`
- candidate success count: `6 / 6`
- candidate backend unavailable count: `0 / 6`
- baseline docs with DOI: `6 / 6`
- candidate docs with DOI: `6 / 6`
- baseline docs with extracted tables: `2 / 6`
- candidate docs with extracted tables: `4 / 6`
- raw table loss docs: `1`
- meaningful table loss docs: `0`

Expanded follow-up on `r11`:
- overall decision: `passed`
- failed check: none
- document count: `18`
- candidate docs with table fallback: `1 / 18`
- meaningful table loss docs: `0`
- raw table loss docs: `6`
- meaningful page-loss docs: `0`
- same-page merge docs: `2`

## Interpretation

This run is evidence that `docling` is now importable and participating in real parser comparison.

It is evidence that:
- the harness works on a bounded real local sample
- the current environment can import and initialize `docling`
- the earlier DOI regression can be eliminated with a bounded fallback patch
- the new manifest is a reusable non-empty parser eval set for future reruns
- the optional backend can clear the bounded fixture gate when structured docling tables are combined with a page-aware meaningful-table rescue from `fitz/pdfplumber`
- fallback use is now explicit in the eval artifacts instead of being hidden inside the parser path
- docling text extraction no longer collapses every document to a single section; `r9` preserves page-aware sections on the bounded fixture set

The current `r9` run should be interpreted as a bounded hybrid parser-backend comparison, not as evidence that pure docling alone resolves all table cases.

The current `r11` run should be interpreted as a stronger stress test of fallback frequency and table segmentation behavior.
It does not show broad page-level coverage failure.
It shows that same-page merged tables are common enough to deserve their own category instead of being treated as hard table-loss failures.

The `r12` same-page merge audit should be interpreted as a content-preservation check on that new bucket.
It shows that the current `Benedict 2020` and `Dubois 2021` merge cases preserve normalized baseline cell coverage.

The `r15` section-quality audit should be interpreted as a page-aware text coverage check with clarified doc-vs-page bucket counts and overlap classification on the expanded set.
It does not show missing substantive pages, total-text collapse, or one-section collapse.
It surfaces three low page-text-ratio review docs, and all of their flagged pages still classify into layout-heavy buckets rather than `needs_manual_review`.

The `r16` through `r18` broad-manifest reruns should be interpreted as a second generalization pass on a disjoint 12-document set.
That pass did not introduce new fallback use, same-page merge cases, or section-quality review buckets.

Pilot control path:
- bounded runtime pilot requests can now carry `parser_backend` through [main.py](/Users/jangseongjin/paperpipe/backend/main.py), [queue.py](/Users/jangseongjin/paperpipe/src/jobs/queue.py), and [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- the current caller-side entry point is [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx), which accepts a route-level query param such as `/workbench/<paper_id>?parser_backend=docling`
- workbench rail navigation preserves that bounded query param so pilot mode is not silently dropped while reviewing neighboring papers
- queued job status exposes the requested backend from execution-run params
- completed job status and bootstrap metadata expose the effective backend resolved by the runner
- requesting `docling` does not bypass `config.ingest.enable_docling`; when that flag is off, the effective backend still resolves to `fitz_pdfplumber`

## Safe Conclusion

Current classification for `docling` in this environment:
- bounded behind-flag parser pilot candidate
- not ready for default runtime adoption

Reason:
- import and converter initialization now work
- DOI preservation is back to parity
- structured docling tables plus one page-aware fallback merge now clear the bounded fixture gate
- the pass still depends on a hybrid rescue path, so the current parser stack should remain the runtime default

## Double-check Notes

Manual follow-up on the two raw table-loss cases showed they are not equivalent:

- `Hansson et al. 2023`
  - baseline extracted 3 meaningful tables
  - pure docling exposed 2 tables
  - direct content inspection showed:
    - docling `T1` corresponds to baseline page 2 biomarker modality table
    - docling `T2` corresponds to baseline page 8 `Box 1` robustness matrix
    - the missing structure is baseline page 4 clinical-stage decision table (`Cognitively unimpaired / MCI / Dementia`)
    - after the structured-table patch, docling still exposes only two `TableItem`s for this paper, on pages 2 and 8
    - page 4 appears in docling as picture/caption/text items rather than a table item, and markdown export contains the decision content only as flattened narrative/figure text
  - the optional backend now merges the meaningful page-4 fallback table from `fitz/pdfplumber`
  - `r8` records this explicitly with `table_fallback_used=true` and `table_fallback_pages=[4]`

- `Therriault et al. 2022`
  - baseline extracted 7 tables, but several are clearly fragmented or degenerate artifacts such as DOI/header fragments, repeated zero grids, and tiny 1x2 snippets
  - docling extracted 1 substantial demographic table
  - this looks more like a raw-count over-penalty than a clean quality loss

Interpretation:
- the raw `table_loss_docs` verdict is directionally useful but too coarse
- page-aware fallback can eliminate the one meaningful blocker without broad parser replacement
- raw-count noise still remains on `Therriault 2022`

## Metric Update

The harness now records both:
- raw table count changes
- meaningful table count changes

Meaningful table heuristic:
- at least 2 rows
- at least 2 columns
- at least 6 non-empty cells
- at least 2 alphabetic cells

This now leaves:
- no meaningful table-loss blocker on the bounded fixture set
- `Therriault 2022` as raw-count-only noise, because the baseline over-count is mostly fragment noise

## Hybrid Fallback Follow-up

The optional docling backend now:
- prefers structured table extraction when `conversion.document.tables` is available
- merges meaningful fallback tables only from pages that docling left uncovered
- records fallback usage in the eval artifacts
- rebuilds page-aware text sections from docling item provenance when `document.pages` is dict-backed

What changed:
- source pages are preserved from docling provenance instead of defaulting parsed markdown tables to page 1
- captions come from docling table metadata when present
- markdown parsing remains only as a fallback when structured tables are unavailable
- meaningful fallback rescue is page-aware rather than global, so it does not pull in the fragmented `Therriault 2022` noise pages
- eval rows now expose `table_fallback_used` and `table_fallback_pages`
- docling rows now preserve page-level `section_count` again instead of collapsing to one `docling_document` section

What did not change:
- the current parser stack should remain the runtime default
- the current evidence set is still only six local PDFs
- `Therriault 2022` still shows a raw table-count gap that should not be used alone for promotion

## Expanded Manifest Follow-up

The expanded manifest adds 12 more non-empty local PDFs for a total of 18.

Latest expanded result:
- `docling` still succeeds on all 18 documents
- `docs_with_table_fallback_count` is only `1`, and that one case is still `Hansson 2023`
- page-aware sectioning remains intact across the expanded set
- the run now passes after reclassifying same-page merged-table cases separately from true page-loss cases

Important nuance:
- neither expanded blocker is a page-level table miss
- both look like same-page multi-table merge cases
- ad hoc page-coverage check on `r10` and the formal `r11` metric both show `meaningful page-loss docs = 0`

Observed patterns:
- `Benedict 2020`: baseline has two meaningful tables on page 7; docling emits one larger meaningful table on page 7
- `Dubois 2021`: baseline has three meaningful tables on page 8; docling emits one large page-8 table plus one page-3 table

Interpretation:
- fallback frequency is low on the expanded set
- no expanded document shows missing substantive pages, total-text collapse, or one-section collapse in the formal section audit
- current blocker has shifted from missing-page recovery to content-level confidence about same-page merged tables

## Same-page Merge Audit

The new sidecar audit script:
- [audit_table_merge_semantics.py](/Users/jangseongjin/paperpipe/scripts/eval/audit_table_merge_semantics.py)

Latest audit artifacts:
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_20260323_r12/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_20260323_r12/details.json)

Audit result on the two `same_page_merge_docs` from `r11`:
- document count: `2`
- semantic merge preserved count: `2`
- content gap count: `0`

What that means:
- `Benedict 2020` preserves normalized baseline cell coverage after the two page-7 tables are merged into one larger table
- `Dubois 2021` preserves normalized baseline cell coverage after the three page-8 decision tables are merged into one larger grouped table
- current evidence still supports “behind-flag optional hybrid pilot”, not “default parser replacement”

## Section Quality Audit

The new sidecar audit script:
- [audit_section_quality.py](/Users/jangseongjin/paperpipe/scripts/eval/audit_section_quality.py)

Latest audit artifacts:
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_20260324_r15/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_20260324_r15/details.json)

Audit result on the expanded `r11` fixture set:
- document count: `18`
- page coverage preserved count: `15`
- missing substantive page docs: `0`
- low page-text-ratio docs: `3`
- low page-text-ratio doc bucket counts: `table_heavy_page=1`, `table_and_figure_heavy_page=1`, `figure_heavy_page=1`
- low page-text-ratio page bucket counts: `table_heavy_page=1`, `table_and_figure_heavy_page=1`, `figure_heavy_page=4`
- low page-text-ratio unclassified docs: `0`
- low total-text-ratio docs: `0`
- section collapse docs: `0`

Automatic review-bucket classification on the low-ratio docs shows why they should stay in a review bucket instead of being treated as outright text-coverage failure:
- `Therriault 2022` page 4 overlaps a baseline table-heavy page; docling keeps the page but does not mirror the dense table-as-text payload that `fitz/pdfplumber` emits there
- `Craft 2020` page 8 is now explicitly classified as a `table_and_figure_heavy_page`, matching its mixed baseline signals
- `Olsson 2016` pages 5-8 are figure-heavy meta-analysis plots where baseline text includes large amounts of chart-label text and docling keeps mostly the figure captions

What that means:
- the earlier one-section collapse bug remains fixed
- docling keeps substantive page presence across the expanded set
- the remaining section/text review bucket is concentrated on layout-heavy pages where baseline text density is inflated by table or figure labels
- the current expanded review bucket no longer contains any unclassified low-ratio docs
- current evidence supports “optional hybrid pilot with explicit audits”, not “default parser replacement”

## Broad Manifest Follow-up

The second expanded manifest adds 12 more non-empty local PDFs outside the first 18-document set.

Artifacts:
- [ingest_backend_pilot_expanded_broad_20260324.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_expanded_broad_20260324.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_broad_20260324_r16/summary.json)
- [metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_broad_20260324_r16/metrics.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_broad_20260324_r17/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_broad_20260324_r18/summary.json)

Broad rerun result:
- compare decision: `passed`
- document count: `12`
- docs with table fallback: `0`
- meaningful table loss docs: `0`
- same-page merge docs: `0`
- low text ratio docs: `0`
- merge audit document count: `0`
- section audit page coverage preserved count: `12 / 12`
- section audit low page-text-ratio docs: `0`
- section audit unclassified docs: `0`

What that means:
- the clarified `r15` review-bucket logic does not immediately produce new review cases on the second broad fixture set
- the hybrid optional backend can clear a disjoint 12-document broad rerun without fallback use on this sample
- the current promotion limit is still architectural, not because of a newly observed regression on this broad set

## Next Action

Do the next parser pilot only after:
1. keeping `goldset/manifests/ingest_backend_pilot_20260323.json` as the bounded fixture set
2. treating the current `docling` path as a hybrid optional backend, not as proof that pure docling table extraction is sufficient
3. rerunning the same merge audit on future `same_page_merge_docs` buckets before any stronger promotion claim
4. keeping both raw and meaningful table metrics, plus fallback metadata, in future reruns so count noise and rescue frequency stay visible
