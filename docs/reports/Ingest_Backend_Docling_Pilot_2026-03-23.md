# Ingest Backend Docling Pilot

Status: bounded evaluation report  
Date: 2026-03-23  
Lane: `ingest-backend-eval`

## Purpose

Run the new bounded ingest backend comparison harness on a small real local PDF set and determine whether `docling` is ready for a parser pilot in this environment.

## Bounded Manifest

The reusable manifest for this pilot is:

- [ingest_backend_pilot_20260323.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_20260323.json)

It exists to avoid:
- empty placeholder PDFs
- ad hoc sample drift
- overreading the entire local library

## Command

```bash
python3 scripts/eval/compare_ingest_backends.py \
  --manifest goldset/manifests/ingest_backend_pilot_20260323.json \
  --out-dir snapshots/ingest_backend_eval \
  --run-id docling_pilot_manifest_20260323_r9
```

## Output Artifacts

Durable final artifacts:
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r8/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r8/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r8/detailed_results.jsonl`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r9/summary.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r9/metrics.json`
- `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r9/detailed_results.jsonl`

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

## Next Action

Do the next parser pilot only after:
1. keeping `goldset/manifests/ingest_backend_pilot_20260323.json` as the bounded fixture set
2. treating the current `docling` path as a hybrid optional backend, not as proof that pure docling table extraction is sufficient
3. expanding the fixture set before any runtime-default discussion
4. keeping both raw and meaningful table metrics, plus fallback metadata, in future reruns so count noise and rescue frequency stay visible
