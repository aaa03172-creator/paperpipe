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

Latest verdict should be read from `r6`, which keeps the meaningful-table heuristic from `r5` and updates the docling backend to prefer structured `doc.tables` output over markdown parsing when available.

- overall decision: `failed`
- failed check: `meaningful_table_loss_docs`
- baseline backend: `fitz_pdfplumber`
- candidate backend: `docling`
- baseline success count: `6 / 6`
- candidate success count: `6 / 6`
- candidate backend unavailable count: `0 / 6`
- baseline docs with DOI: `6 / 6`
- candidate docs with DOI: `6 / 6`
- baseline docs with extracted tables: `2 / 6`
- candidate docs with extracted tables: `4 / 6`
- raw table loss docs: `2`
- meaningful table loss docs: `1`

## Interpretation

This run is evidence that `docling` is now importable and participating in real parser comparison.

It is evidence that:
- the harness works on a bounded real local sample
- the current environment can import and initialize `docling`
- the earlier DOI regression can be eliminated with a bounded fallback patch
- the new manifest is a reusable non-empty parser eval set for future reruns
- the remaining decision blocker is meaningful table loss on a subset of documents, not environment readiness

The current `r6` run should be interpreted as a real bounded parser quality comparison with one remaining regression class: meaningful table loss.

## Safe Conclusion

Current classification for `docling` in this environment:
- bounded parser pilot candidate
- not ready for runtime adoption

Reason:
- import and converter initialization now work
- DOI preservation is back to parity
- table extraction is mixed: gains on some documents, one meaningful loss remains
- zero-threshold policy still blocks promotion

## Double-check Notes

Manual follow-up on the two raw table-loss cases showed they are not equivalent:

- `Hansson et al. 2023`
  - baseline extracted 3 meaningful tables
  - docling extracted 2 tables
  - direct content inspection showed:
    - docling `T1` corresponds to baseline page 2 biomarker modality table
    - docling `T2` corresponds to baseline page 8 `Box 1` robustness matrix
    - the missing structure is baseline page 4 clinical-stage decision table (`Cognitively unimpaired / MCI / Dementia`)
    - after the structured-table patch, docling still exposes only two `TableItem`s for this paper, on pages 2 and 8
    - page 4 appears in docling as picture/caption/text items rather than a table item, and markdown export contains the decision content only as flattened narrative/figure text
  - this looks like a real loss of one meaningful table, not only a counting artifact

- `Therriault et al. 2022`
  - baseline extracted 7 tables, but several are clearly fragmented or degenerate artifacts such as DOI/header fragments, repeated zero grids, and tiny 1x2 snippets
  - docling extracted 1 substantial demographic table
  - this looks more like a raw-count over-penalty than a clean quality loss

Interpretation:
- the raw `table_loss_docs` verdict is directionally useful but too coarse
- at least one loss case is real
- at least one loss case suggests the next metric should distinguish meaningful tables from degenerate fragments

## Metric Update

The harness now records both:
- raw table count changes
- meaningful table count changes

Meaningful table heuristic:
- at least 2 rows
- at least 2 columns
- at least 6 non-empty cells
- at least 2 alphabetic cells

This leaves:
- `Hansson 2023` as a real remaining loss
- `Therriault 2022` outside the promotion blocker, because the baseline over-count was mostly fragment noise

## Structured Table Follow-up

The optional docling backend now prefers structured table extraction when `conversion.document.tables` is available.

What changed:
- source pages are preserved from docling provenance instead of defaulting parsed markdown tables to page 1
- captions come from docling table metadata when present
- markdown parsing remains only as a fallback when structured tables are unavailable

What did not change:
- the bounded manifest verdict still fails on `meaningful_table_loss_docs`
- the remaining blocker is still `Hansson 2023` page 4

## Next Action

Do the next parser pilot only after:
1. keeping `goldset/manifests/ingest_backend_pilot_20260323.json` as the bounded fixture set
2. investigating the remaining `Hansson 2023` meaningful table loss
3. deciding whether that single loss is acceptable for a behind-flag pilot or whether docling table parsing needs one more bounded adjustment
4. keeping both raw and meaningful table metrics in future reruns so count noise stays visible but does not dominate promotion logic
