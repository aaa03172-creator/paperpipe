# Slot Classification Goldset Audit Baseline

## Goal

Establish a reproducible classification-accuracy surface for slot prediction without changing runtime truth paths, provider routing, or DB ownership.

This report is intentionally narrower than runtime-readiness or intake-override work. It defines the first durable audit contract for slot-classification accuracy and records the bootstrap artifact produced from that contract.

## Why This Lane Was Missing

The repo already had:

- prompt- and metric-level unit tests around `LLMProvider.classify_slot`
- a lightweight goldset template at `/Users/jangseongjin/paperpipe/tests/gold_set/gold_standard_template.csv`

But it did not yet have:

- a dedicated summary/detail artifact lane for slot-classification accuracy
- a confusion/coverage report surface that could be regenerated from inputs
- a safe boundary between "prediction generation" and "accuracy accounting"

The existing goldset template is also too shallow for a truthful live replay baseline on its own. It currently records `title` and `gold_slot`, but the live classifier is optimized for `title + summary` and can optionally benefit from full-text evidence chunks.

## Implementation

Added files:

- schema: [slot_classification_audit.py](/Users/jangseongjin/paperpipe/src/schemas/slot_classification_audit.py)
- service: [slot_classification_audit.py](/Users/jangseongjin/paperpipe/src/services/slot_classification_audit.py)
- eval entrypoint: [audit_slot_classification_goldset.py](/Users/jangseongjin/paperpipe/scripts/eval/audit_slot_classification_goldset.py)
- prediction generator: [generate_slot_classification_predictions.py](/Users/jangseongjin/paperpipe/scripts/eval/generate_slot_classification_predictions.py)
- tests: [test_slot_classification_audit.py](/Users/jangseongjin/paperpipe/tests/test_slot_classification_audit.py)
- prediction-generator tests: [test_generate_slot_classification_predictions.py](/Users/jangseongjin/paperpipe/tests/test_generate_slot_classification_predictions.py)
- curated fixture goldset: [slot_classification_goldset_curated_20260421.csv](/Users/jangseongjin/paperpipe/tests/fixtures/slot_classification_goldset_curated_20260421.csv)
- curated fixture predictions: [slot_classification_predictions_curated_20260421.jsonl](/Users/jangseongjin/paperpipe/tests/fixtures/slot_classification_predictions_curated_20260421.jsonl)
- expanded repo template: [gold_standard_template.csv](/Users/jangseongjin/paperpipe/tests/gold_set/gold_standard_template.csv)

The lane is additive only:

- it reads goldset rows
- it can either join precomputed prediction rows by `paper_id`, `doi`, or normalized `title`, or generate those prediction rows from the current provider path
- it writes summary/detail/markdown artifacts
- it does not alter runtime state, provider ownership, or DB records

The generator records `prediction_status` and `input_richness`, so rows with missing `current_slot`, missing provider availability, or shallow inputs are visible instead of silently disappearing.

The generator also supports a neutral `Unknown` fallback seed for `current_slot`. This is important for the default repo template because it allows live replay without injecting the gold label back into the input slot.

## Bootstrap Artifact

Generated artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_curated_bootstrap_20260421_r1/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_curated_bootstrap_20260421_r1/details.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_curated_bootstrap_20260421_r1/audit.md)

Current curated bootstrap values:

- `document_count=4`
- `evaluated_count=3`
- `matched_count=2`
- `mismatch_count=1`
- `missing_prediction_count=1`
- `accuracy=0.6667`
- `prediction_coverage_rate=0.75`

Per-slot snapshot:

- `clinical`: accuracy `1.0`, coverage `1.0`
- `mechanism`: accuracy `1.0`, coverage `0.5`
- `methods`: accuracy `0.0`, coverage `1.0`

Known mismatch/missing rows:

- mismatch: `paper-methods-001`
- missing prediction: `paper-mechanism-002`

## Live Curated Replay

Generated live prediction artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_curated_generation_20260421_r1/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_curated_generation_20260421_r1/details.json)
- [predictions.jsonl](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_curated_generation_20260421_r1/predictions.jsonl)

Paired live audit artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_curated_live_20260421_r2/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_curated_live_20260421_r2/details.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_curated_live_20260421_r2/audit.md)

Current live curated values:

- generation summary: `provider_available=true`, `runtime_feature_enabled=true`, `prediction_written_count=4`
- generation input richness: `{"title_summary": 3, "title_summary_full_text": 1}`
- audit summary: `evaluated_count=4`, `matched_count=4`, `accuracy=1.0`, `prediction_coverage_rate=1.0`

This proves the lane can run against the current local provider path on this machine. It does not mean production slot accuracy is solved; the set is still tiny and curated.

## Default Template Enrichment

The default repo goldset template now includes concise abstract-grounded `summary` fields for its four existing DOI rows. The summaries were backfilled from the linked paper abstracts or publisher summaries rather than invented from the gold labels.

Source pages used for that backfill:

- ketone cognition meta-analysis: [PubMed](https://pubmed.ncbi.nlm.nih.gov/41001501/)
- clinical exogenous ketosis review: [PubMed](https://pubmed.ncbi.nlm.nih.gov/41097203/)
- peiminine stroke mechanism paper: [PubMed](https://pubmed.ncbi.nlm.nih.gov/41614275/)
- Epg5 Vici syndrome mouse model paper: [Nature](https://www.nature.com/articles/s12276-026-01644-z)

The default template now also includes a real `methods` example:

- plasma p-Tau217 immunoassay validation paper: [Frontiers](https://www.frontiersin.org/journals/neurology/articles/10.3389/fneur.2025.1568971/full)

The template intentionally still leaves `current_slot` blank. Live replay now uses a neutral `Unknown` fallback seed instead.

## Default Template Live Replay

Generated default-template live prediction artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r2/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r2/details.json)
- [predictions.jsonl](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r2/predictions.jsonl)

Paired default-template live audit artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r3/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r3/details.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r3/audit.md)

Current default-template live values:

- generation summary: `provider_available=true`, `runtime_feature_enabled=true`, `prediction_written_count=4`, `fallback_current_slot="unknown"`
- generation input richness: `{"title_summary": 4}`
- audit summary: `evaluated_count=4`, `matched_count=4`, `accuracy=1.0`, `prediction_coverage_rate=1.0`

This is a stronger baseline than the curated stub because it exercises the repo-default goldset file, but it is still only a four-row smoke baseline.

## Default Template Live Replay (Expanded 3-Way)

After adding the methods-focused p-Tau217 validation paper, the default template was rerun:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r3/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r3/details.json)
- [predictions.jsonl](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r3/predictions.jsonl)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r4/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r4/details.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r4/audit.md)

Expanded default-template values:

- generation summary: `document_count=5`, `prediction_written_count=5`, `input_richness_counts={"title_summary": 5}`
- audit summary: `clinical=2`, `mechanism=2`, `methods=1`
- audit summary: `matched_count=5`, `accuracy=1.0`, `prediction_coverage_rate=1.0`

This is still a tiny baseline, but it is materially better than the earlier default-template version because all three slot classes are now represented.

## Default Template Live Replay (Expanded Borderline Biomarker Mix)

To make the repo-default baseline less toy-like, the default template was expanded again with three biomarker-heavy borderline papers that could plausibly be confused between `methods` and `clinical`:

- assay-development paper: `10.1002/dad2.12204`
- clinical cohort utility paper: `10.1212/WNL.0000000000201479`
- preclinical screening-utility paper: `10.1001/jamaneurol.2025.3217`

Source pages used for the new summaries:

- plasma p217+tau assay development: [PubMed](https://pubmed.ncbi.nlm.nih.gov/34095436/)
- clinic-based dementia-risk cohort: [PubMed](https://pubmed.ncbi.nlm.nih.gov/36261295/)
- preclinical plasma p-tau217 screening paper: [JAMA Neurology](https://jamanetwork.com/journals/jamaneurology/fullarticle/10.1001/jamaneurol.2025.3217)

Generated expanded default-template live artifacts:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r6/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r6/details.json)
- [predictions.jsonl](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r6/predictions.jsonl)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r7/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r7/details.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r7/audit.md)

Expanded borderline-mix values:

- generation summary: `document_count=8`, `prediction_written_count=8`, `input_richness_counts={"title_summary": 8}`
- audit summary: `clinical=4`, `mechanism=2`, `methods=2`
- audit summary: `matched_count=8`, `accuracy=1.0`, `prediction_coverage_rate=1.0`

This is still not a representative production benchmark, but it is a more credible smoke baseline than the earlier five-row mix because the default repo file now includes multiple biomarker-heavy borderline papers on both sides of the `methods`/`clinical` boundary.

## Default Template Live Replay (Harder Assay-Performance Ambiguity Pass)

The default template was then pushed one step further with three assay-performance papers whose titles and summaries are more genuinely ambiguous between `methods` and `clinical`:

- real-world memory-clinic utility paper: `10.1016/j.ebiom.2024.105345`
- fully automated Lumipulse assay-performance paper: `10.1186/s13195-022-01116-2`
- novel plasma p-tau217 assay comparison paper: `10.1186/s13195-022-01005-8`

Source pages used for these additional summaries:

- memory-clinic pTau181 utility paper: [PubMed](https://pubmed.ncbi.nlm.nih.gov/39299003/)
- fully automated Lumipulse p-tau181 assay paper: [Alzheimer's Research & Therapy](https://alzres.biomedcentral.com/articles/10.1186/s13195-022-01116-2)
- novel plasma p-tau217 assay comparison paper: [Alzheimer's Research & Therapy](https://alzres.biomedcentral.com/articles/10.1186/s13195-022-01005-8)

Generated harder-pass artifacts:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r7/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r7/details.json)
- [predictions.jsonl](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r7/predictions.jsonl)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r8/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r8/details.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r8/audit.md)

Harder-pass values:

- generation summary: `document_count=11`, `prediction_written_count=11`, `input_richness_counts={"title_summary": 11}`
- audit summary: `clinical=5`, `mechanism=2`, `methods=4`
- audit summary: `matched_count=10`, `mismatch_count=1`, `accuracy=0.9091`, `prediction_coverage_rate=1.0`
- confusion detail: `methods->clinical = 1`
- mismatched row: `10.1186/s13195-022-01005-8`

This is the first default-template replay that produced a real disagreement instead of a perfect score. That is useful: the baseline now has at least one genuine stress point on the `methods`/`clinical` boundary, so it is less likely to overstate classifier readiness.

## Gold Label Rationale Annotation

To make the disagreement auditable rather than merely visible, the goldset contract now accepts an optional `gold_slot_rationale` column and carries that field into the audit detail and markdown artifacts.

Updated rationale-aware audit artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r9/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r9/details.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r9/audit.md)

Current effect:

- the summary metrics are unchanged from the harder-pass audit (`accuracy=0.9091`, `mismatch_count=1`)
- the mismatched row now carries explicit gold-label rationale in both `details.json` and `audit.md`
- the markdown artifact now also includes a `Gold Label Rationales` section so hard-case labeling decisions remain visible even when a future run has no mismatches

This keeps the lane additive: the rationale is review metadata attached to the goldset, not a new runtime truth path.

## Targeted Boundary-Policy Prompt Tuning

After the rationale and full-text companion work made the boundary failure concrete, the next bounded step was a prompt-only policy adjustment in [llm_provider.py](/Users/jangseongjin/paperpipe/src/llm_provider.py).

The change was intentionally small:

- Methods language now explicitly includes assay/platform comparison and benchmarking papers
- deterministic signal summary now exposes assay-comparison cue terms
- adjudication guidance now says that human cohorts alone do not force `Clinical` when the main novelty is benchmarking or validating a measurement platform

Boundary reference created during this pass:

- [Slot_Classification_Boundary_Rubric_2026-04-22.md](/Users/jangseongjin/paperpipe/docs/reports/Slot_Classification_Boundary_Rubric_2026-04-22.md)

Prompt-regression verification:

- `pytest -q tests/test_llm_provider_canonical_language.py tests/test_generate_slot_classification_predictions.py tests/test_slot_classification_audit.py`
- `python3 -m py_compile src/llm_provider.py tests/test_llm_provider_canonical_language.py`

### Default Template After Prompt Tuning

Regenerated default-template artifacts:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260422_r1/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r1/summary.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r1/audit.md)

Outcome on the eleven-row default template:

- previous harder-pass baseline: `matched_count=10`, `mismatch_count=1`, `accuracy=0.9091`
- tuned prompt baseline: `matched_count=11`, `mismatch_count=0`, `accuracy=1.0`
- the previously stubborn row `10.1186/s13195-022-01005-8` now lands in `methods`
- neighboring rows `10.1212/WNL.0000000000201479`, `10.1016/j.ebiom.2024.105345`, and `10.1186/s13195-022-01116-2` remain correct

This is a real improvement on the default repo baseline.

### Boundary Companion After Prompt Tuning

Regenerated boundary-companion artifacts:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_boundary_companion_generation_20260422_r3/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r3/summary.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r3/audit.md)

Outcome on the four-row full-text companion:

- previous companion baseline: `matched_count=3`, `mismatch_count=1`, `accuracy=0.75`, with `10.1186/s13195-022-01005-8` misclassified as `clinical`
- tuned prompt baseline: still `matched_count=3`, `mismatch_count=1`, `accuracy=0.75`
- but the error moved: `10.1186/s13195-022-01005-8` is now correct, while `10.1212/WNL.0000000000201479` flips from `clinical` to `methods`

Interpretation:

- the prompt change successfully corrected the default-template assay-comparison miss
- but it did not solve the broader boundary problem; instead it shifted the remaining error to a different hard clinical-utility paper in the full-text companion set
- that means the repo now has evidence of a real tradeoff surface rather than a one-off typo in the prompt

### Second Tie-Breaker Follow-Up

The next bounded follow-up was a narrower prompt refinement that tried to separate true assay/platform benchmarking papers from patient-facing screening and prognostic papers more explicitly.

Regenerated second-pass artifacts:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260422_r2/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r2/summary.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r2/audit.md)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_boundary_companion_generation_20260422_r4/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r4/summary.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r4/audit.md)

Outcome after the second tie-breaker:

- the eleven-row default template regressed from `matched_count=11`, `accuracy=1.0` to `matched_count=10`, `accuracy=0.9091`
- the new default-template mismatch is `10.1101/2025.09.17.25335999`, which is gold-labeled `clinical` but now lands in `mechanism`
- the four-row boundary companion stayed at `matched_count=3`, `accuracy=0.75`
- the remaining companion mismatch moved again, from `10.1212/WNL.0000000000201479` to `10.1016/j.ebiom.2024.105345`

This matters because it means the second prompt refinement did not merely "fail to help." It introduced a new default-template miss while also moving the surviving hard-case mismatch on the boundary companion.

### Paired Compare Lane

To stop reading these prompt changes one artifact at a time, the repo now also has an additive paired-compare lane:

- schema: [slot_classification_paired_compare.py](/Users/jangseongjin/paperpipe/src/schemas/slot_classification_paired_compare.py)
- service: [slot_classification_paired_compare.py](/Users/jangseongjin/paperpipe/src/services/slot_classification_paired_compare.py)
- eval entrypoint: [compare_slot_classification_paired_benchmarks.py](/Users/jangseongjin/paperpipe/scripts/eval/compare_slot_classification_paired_benchmarks.py)
- tests: [test_slot_classification_paired_compare.py](/Users/jangseongjin/paperpipe/tests/test_slot_classification_paired_compare.py)

This lane does not create another truth path. It reads two existing default-template audit summaries plus two existing boundary-companion audit summaries and records:

- metric regressions across the pair
- mismatch-count regressions across the pair
- mismatch migration, meaning a hard error disappeared in one place only to reappear as a different hard error elsewhere

#### Compare: Untuned -> First Prompt Policy Pass

Generated compare artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_paired_compares/slot_classification_prompt_policy_compare_20260422_r1/summary.json)
- [compare.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_paired_compares/slot_classification_prompt_policy_compare_20260422_r1/compare.md)

Compare outcome:

- default-template metrics improved (`accuracy 0.9091 -> 1.0`, `mismatch_count 1 -> 0`)
- boundary-companion metrics stayed flat (`accuracy 0.75 -> 0.75`, `mismatch_count 1 -> 1`)
- but the compare still does not pass because the mismatch identity moved on the boundary companion:
  - resolved: `10.1186/s13195-022-01005-8`
  - new: `10.1212/WNL.0000000000201479`

So the first prompt change is best read as "default improvement with boundary mismatch migration," not as a clean win.

#### Compare: First Prompt Policy Pass -> Second Tie-Breaker

Generated compare artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_paired_compares/slot_classification_tie_breaker_compare_20260422_r1/summary.json)
- [compare.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_paired_compares/slot_classification_tie_breaker_compare_20260422_r1/compare.md)

Compare outcome:

- default-template regressed (`accuracy 1.0 -> 0.9091`, `mismatch_count 0 -> 1`)
- boundary-companion metrics again stayed flat (`accuracy 0.75 -> 0.75`, `mismatch_count 1 -> 1`)
- the companion mismatch identity still moved:
  - resolved: `10.1212/WNL.0000000000201479`
  - new: `10.1016/j.ebiom.2024.105345`

This is the strongest current evidence that prompt-only tuning has become a mismatch-migration problem rather than a missing-context problem.

## Expanded Boundary Companion

The original four-row full-text companion was deliberately tiny. To make the boundary surface less brittle without mutating the original artifact history, a second additive companion file was created:

- [slot_classification_boundary_companion_expanded_20260422.csv](/Users/jangseongjin/paperpipe/tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv)

This expanded companion keeps the original four hard rows and adds three more adjudicated boundary papers already present in the default goldset:

- `10.3389/fneur.2025.1568971` (`methods`)
- `10.1002/dad2.12204` (`methods`)
- `10.1001/jamaneurol.2025.3217` (`clinical`)

Generated expanded-companion artifacts:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_boundary_companion_expanded_generation_20260422_r1/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_expanded_live_20260422_r2/summary.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_expanded_live_20260422_r2/audit.md)

Expanded-companion outcome on the current local provider path:

- `document_count=7`
- `matched_count=7`
- `mismatch_count=0`
- `accuracy=1.0`
- `prediction_coverage_rate=1.0`
- `input_richness_counts={"title_summary_full_text": 7}`

This is encouraging because it shows the current prompt and rubric can agree on a broader seven-row boundary set, not only on the easier default-template rows.

It is still not a promotion-grade benchmark on its own:

- the set is small
- every row is hand-adjudicated
- and, as shown below, the live provider path is not perfectly stable across reruns even with the same code and benchmark inputs

## Rerun Drift

The expanded companion unexpectedly exposed a more important caveat: the slot-classification live replay path is not perfectly stable under rerun, even with the same prompt code and zero-temperature task settings.

To make that visible, the repo now also has a rerun-drift lane:

- schema: [slot_classification_rerun_drift.py](/Users/jangseongjin/paperpipe/src/schemas/slot_classification_rerun_drift.py)
- service: [slot_classification_rerun_drift.py](/Users/jangseongjin/paperpipe/src/services/slot_classification_rerun_drift.py)
- eval entrypoint: [audit_slot_classification_rerun_drift.py](/Users/jangseongjin/paperpipe/scripts/eval/audit_slot_classification_rerun_drift.py)
- tests: [test_slot_classification_rerun_drift.py](/Users/jangseongjin/paperpipe/tests/test_slot_classification_rerun_drift.py)

This lane compares two audit runs over the same benchmark surface and records row-level prediction drift, mismatch-status changes, and accuracy deltas.

### Boundary Companion Rerun Drift

Generated drift artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_rerun_drift/slot_classification_boundary_rerun_drift_20260422_r1/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_rerun_drift/slot_classification_boundary_rerun_drift_20260422_r1/details.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_rerun_drift/slot_classification_boundary_rerun_drift_20260422_r1/audit.md)

Comparing `slot_classification_boundary_companion_live_20260422_r4` to a same-code rerun `slot_classification_boundary_companion_live_20260422_r5`:

- surface metrics stayed flat (`accuracy=0.75`, `mismatch_count=1`)
- but `drift_count=1`, `drift_rate=0.25`
- the drifting row is `10.1016/j.ebiom.2024.105345`
- its predicted slot changed from `methods` to `mechanism` without becoming correct

So even where the overall metric is unchanged, the actual error identity can still move at the label level.

### Default Template Rerun Drift

Generated drift artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_rerun_drift/slot_classification_default_rerun_drift_20260422_r1/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_rerun_drift/slot_classification_default_rerun_drift_20260422_r1/details.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_rerun_drift/slot_classification_default_rerun_drift_20260422_r1/audit.md)

Comparing `slot_classification_default_template_live_20260422_r2` to a same-code rerun `slot_classification_default_template_live_20260422_r3`:

- `drift_count=1`, `drift_rate=0.0909`
- the drifting row is `10.1101/2025.09.17.25335999`
- its predicted slot changed from `mechanism` back to the gold label `clinical`
- the overall default-template audit therefore moved from `accuracy=0.9091` back to `accuracy=1.0`

This means the earlier apparent "second tie-breaker regression" was at least partly confounded by rerun instability in the live provider path.

Current best reading:

- the paired compare lane is still useful for surfacing drift and mismatch migration across prompt revisions
- but single-run live artifacts should be interpreted as advisory unless they are corroborated by rerun-stability evidence
- for hard boundary work, a prompt change that looks better or worse on one replay may still need a rerun-drift check before it is treated as a real policy improvement or regression

## Tuning Review Surface

Because the slot lane now has both paired-compare evidence and rerun-drift evidence, the repo also has a small advisory review layer that combines them into one decision surface:

- schema: [slot_classification_tuning_review.py](/Users/jangseongjin/paperpipe/src/schemas/slot_classification_tuning_review.py)
- service: [slot_classification_tuning_review.py](/Users/jangseongjin/paperpipe/src/services/slot_classification_tuning_review.py)
- eval entrypoint: [recommend_slot_classification_tuning_review.py](/Users/jangseongjin/paperpipe/scripts/eval/recommend_slot_classification_tuning_review.py)
- tests: [test_recommend_slot_classification_tuning_review.py](/Users/jangseongjin/paperpipe/tests/test_recommend_slot_classification_tuning_review.py)

This layer is still additive and advisory-only. It does not change runtime slot behavior. It answers a narrower question:

`Is there enough paired benchmark and rerun-stability evidence to treat a slot prompt or policy change as a real improvement?`

### Review: First Prompt Policy Pass

Generated review artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_tuning_review/slot_classification_tuning_review_prompt_policy_20260422_r1/summary.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_tuning_review/slot_classification_tuning_review_prompt_policy_20260422_r1/audit.md)

Current decision:

- `recommended_action=review_boundary_rubric_and_expand_goldset`
- `review_ready=false`
- `paired_compare_status=tradeoff`
- rerun-drift status is still `missing` for both surfaces in this older prompt pass

This is the expected call: the first prompt pass improved one benchmark surface, but mismatch migration was still present and rerun-stability evidence had not yet been collected.

### Review: Second Tie-Breaker Pass

Generated review artifact:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_tuning_review/slot_classification_tuning_review_20260422_r1/summary.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_tuning_review/slot_classification_tuning_review_20260422_r1/audit.md)

Current decision:

- `recommended_action=hold_current_prompt_policy`
- `review_ready=false`
- `paired_compare_status=regressed`
- `default_rerun_status=warn`
- `boundary_rerun_status=warn`

The action plan is intentionally strict:

1. hold the candidate prompt/policy because the paired benchmark regressed
2. collect or review default-benchmark rerun stability
3. collect or review boundary-benchmark rerun stability

This is the current strongest repo-grounded posture for slot prompt tuning. The review layer preserves the older compare artifacts, but it no longer treats them as sufficient by themselves.

For operator/debug readability, the tuning-review script now also emits a compact stderr line while keeping its JSON stdout payload unchanged, for example:

- `review_ready=False action=hold_current_prompt_policy paired_compare=regressed default_rerun=warn boundary_rerun=warn compare_run=slot_classification_tie_breaker_compare_20260422_r1`

### Operator Surface

The latest slot-tuning review is now also visible through the general runtime operator surfaces instead of only as a raw snapshot file:

- readiness service: [runtime_readiness.py](/Users/jangseongjin/paperpipe/src/services/runtime_readiness.py)
- CLI surface: [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)

This remains advisory-only. It does not change slot runtime behavior, and it does not create a second truth path. It simply exposes the latest tuning-review decision block through `runtime_readiness` and `paperpipe doctor`.

One small implementation detail mattered here: the latest-run selector for slot tuning review now prefers the artifact `generated_at` timestamp over a plain filesystem mtime/name tiebreak. Without that, same-second snapshots like:

- `slot_classification_tuning_review_prompt_policy_20260422_r1`
- `slot_classification_tuning_review_20260422_r1`

could surface in the wrong order even though the second artifact is the later, more complete review.

### Broader Reporting Surface

The same advisory state is now also visible in the broader internal-data reporting lane rather than only the runtime/operator lane:

- eval summary script: [check_internal_data_readiness.py](/Users/jangseongjin/paperpipe/scripts/eval/check_internal_data_readiness.py)
- latest summary artifact: [summary.json](/Users/jangseongjin/paperpipe/snapshots/internal_data_readiness/internal_data_with_slot_tuning_review_20260422_r1/summary.json)

Current repo-grounded reporting posture there is:

- `surfaces.slot_classification_tuning_review.status=present`
- `category_status.classification_tuning_review=advisory_hold`
- the latest linked review is still `slot_classification_tuning_review_20260422_r1`

This is intentionally not folded into runtime-promotion decision logic. It is a reporting/advisory surface that makes the current slot tuning posture visible alongside the rest of the classification baseline, while leaving `internal_data_bootstrap_ready` and runtime-promotion policy semantics unchanged.

For CI/debug readability, the internal-data summary script now also emits a compact stdout line with the current classification posture, for example:

- `bootstrap_ready=True runtime_promotion_ready=False policy=manual_review_only classification_audit=bootstrap_ready classification_runtime_producer=repair_only classification_tuning_review=advisory_hold blockers=1`

### Narrow Visibility Rule

The next conservative step was not to promote `classification_tuning_review` into a hard acceptance gate. Instead, the repo now has a narrow visibility rule that only checks whether this advisory surface remains visible in broader reporting:

- visibility check script: [check_slot_classification_tuning_visibility.py](/Users/jangseongjin/paperpipe/scripts/eval/check_slot_classification_tuning_visibility.py)
- latest visibility artifact: [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_tuning_visibility/slot_classification_tuning_visibility_20260422_r1/summary.json)

Current visibility result:

- `passed=true`
- `surface_status=present`
- `classification_tuning_review_status=advisory_hold`
- `recommended_action=hold_current_prompt_policy`

The important contract is narrow on purpose:

- `advisory_hold` is allowed and still passes
- `review_ready` is also allowed
- `missing` or `invalid` visibility is what fails

That makes this a CI/reporting visibility rule, not a policy-promotion gate. It guards against the slot tuning surface silently disappearing from broader reporting while preserving the current advisory-only posture.

This rule is now exercised in the backend smoke lane in a bounded way:

- `scripts/run_backend_api_smoke.sh` regenerates a temporary `internal_data_readiness` summary
- then runs the slot-tuning visibility checker against that temporary summary

So the smoke contract now checks the reporting chain end-to-end, not just the checker unit tests.

That bounded smoke path has now been rerun end-to-end successfully after the compact reporting updates. The current local smoke output still shows:

- `classification_tuning_review=advisory_hold`
- `passed=True status=advisory_hold action=hold_current_prompt_policy surface=present`

For CI/debug readability, the checker now emits a compact status line such as:

- `passed=True status=advisory_hold action=hold_current_prompt_policy surface=present`

That keeps the smoke logs readable without changing the underlying visibility contract.

## Boundary Full-Text Companion

The next bounded follow-up was a tiny companion goldset built specifically to test whether the hardest `methods` versus `clinical` disagreement was just a shallow `title + summary` problem.

Companion file:

- [slot_classification_boundary_companion_20260422.csv](/Users/jangseongjin/paperpipe/tests/gold_set/slot_classification_boundary_companion_20260422.csv)

This companion set contains four hard boundary rows and gives each one a short `full_text` evidence field:

- `10.1186/s13195-022-01005-8` (`methods`)
- `10.1186/s13195-022-01116-2` (`methods`)
- `10.1016/j.ebiom.2024.105345` (`clinical`)
- `10.1212/WNL.0000000000201479` (`clinical`)

Generated companion artifacts:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_boundary_companion_generation_20260422_r2/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_boundary_companion_generation_20260422_r2/details.json)
- [predictions.jsonl](/Users/jangseongjin/paperpipe/snapshots/slot_classification_predictions/slot_classification_boundary_companion_generation_20260422_r2/predictions.jsonl)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r2/summary.json)
- [details.json](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r2/details.json)
- [audit.md](/Users/jangseongjin/paperpipe/snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r2/audit.md)

Companion values:

- generation summary: `document_count=4`, `prediction_written_count=4`, `input_richness_counts={"title_summary_full_text": 4}`
- audit summary: `matched_count=3`, `mismatch_count=1`, `accuracy=0.75`, `prediction_coverage_rate=1.0`
- confusion detail: `methods->clinical = 1`
- mismatched row: `10.1186/s13195-022-01005-8`

This is the important result:

- the same hard row that missed in the title-summary baseline still misses in the full-text companion baseline
- therefore, the disagreement is not well explained by shallow input alone
- the current local classifier appears to have a real decision-boundary preference toward `clinical` for at least some assay-comparison papers, even when extra evidence text is supplied

## Interpretation

This is a bootstrap contract artifact, not a production accuracy claim.

What it proves:

- the repo now has a durable, regeneratable classification-audit surface
- the surface captures both agreement and missing-prediction coverage
- the surface is stable under deterministic test fixtures
- the surface can also be fed by a bounded live provider-backed generator instead of only handcrafted prediction JSONL
- the default repo goldset template can now be replayed live with a neutral `Unknown` seed rather than a handpicked slot seed
- the default repo goldset now covers all three slot classes instead of omitting `methods`
- the default repo goldset is less vulnerable to trivial overfitting because it now includes multiple biomarker-heavy borderline papers rather than only one obvious `methods` example
- the expanded eleven-row default template now surfaces a real `methods -> clinical` disagreement, which makes the baseline more informative than the earlier all-green smoke runs
- the disagreement is now explained in-artifact rather than only in prose, reducing ambiguity about why a hard case was labeled `methods` or `clinical`
- a small prompt-only policy adjustment can improve the default baseline materially
- the same adjustment still shows a tradeoff on the full-text companion set, so the remaining issue is now better understood as boundary policy tuning rather than simple missing context
- the full-text companion set shows that the hardest disagreement persists even with richer evidence, so the remaining issue is not just title-summary sparsity
- the second, narrower tie-breaker did not stabilize that tradeoff; it introduced a new default-template miss and moved the surviving boundary miss again
- the paired-compare lane now makes that migration explicit instead of leaving it buried across separate audit runs
- future prompt or policy edits can now be judged against both surfaces together, which is safer than reading the default or companion artifact in isolation
- the new rerun-drift lane shows that some of the observed movement is not only prompt-tradeoff but also same-code live-provider instability on specific hard rows
- the new tuning-review lane now combines paired compare and rerun drift into a single advisory decision, which makes it easier to say “not enough evidence yet” without inventing another runtime truth path

What it does not yet prove:

- actual live accuracy of the current runtime classifier on a representative paper set
- stable runtime provider availability or performance across machines
- whether this eleven-row default template is representative enough for a reliable biomedical slot baseline

## Verification

Ran:

- `pytest -q tests/test_generate_slot_classification_predictions.py tests/test_slot_classification_audit.py`
- `python3 -m py_compile src/schemas/slot_classification_audit.py src/services/slot_classification_audit.py scripts/eval/audit_slot_classification_goldset.py scripts/eval/generate_slot_classification_predictions.py`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/fixtures/slot_classification_goldset_curated_20260421.csv --predictions-jsonl tests/fixtures/slot_classification_predictions_curated_20260421.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_curated_bootstrap_20260421_r1`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/fixtures/slot_classification_goldset_curated_20260421.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_curated_generation_20260421_r1`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/fixtures/slot_classification_goldset_curated_20260421.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_curated_generation_20260421_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_curated_live_20260421_r2`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_default_template_generation_20260421_r2`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r2/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_default_template_live_20260421_r3`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_default_template_generation_20260421_r3`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r3/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_default_template_live_20260421_r4`
- `pytest -q tests/test_generate_slot_classification_predictions.py tests/test_slot_classification_audit.py`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_default_template_generation_20260421_r6`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r6/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_default_template_live_20260421_r7`
- `pytest -q tests/test_generate_slot_classification_predictions.py tests/test_slot_classification_audit.py`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_default_template_generation_20260421_r7`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r7/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_default_template_live_20260421_r8`
- `pytest -q tests/test_slot_classification_audit.py tests/test_generate_slot_classification_predictions.py`
- `python3 -m py_compile src/schemas/slot_classification_audit.py src/services/slot_classification_audit.py scripts/eval/audit_slot_classification_goldset.py`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260421_r7/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_default_template_live_20260421_r9`
- `pytest -q tests/test_slot_classification_audit.py tests/test_generate_slot_classification_predictions.py`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_20260422.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_boundary_companion_generation_20260422_r2`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_boundary_companion_generation_20260422_r2/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_boundary_companion_live_20260422_r2`
- `pytest -q tests/test_llm_provider_canonical_language.py tests/test_generate_slot_classification_predictions.py tests/test_slot_classification_audit.py`
- `python3 -m py_compile src/llm_provider.py tests/test_llm_provider_canonical_language.py`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_20260422.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_boundary_companion_generation_20260422_r3`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_boundary_companion_generation_20260422_r3/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_boundary_companion_live_20260422_r3`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_default_template_generation_20260422_r1`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260422_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_default_template_live_20260422_r1`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_default_template_generation_20260422_r2`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260422_r2/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_default_template_live_20260422_r2`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_20260422.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_boundary_companion_generation_20260422_r4`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_boundary_companion_generation_20260422_r4/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_boundary_companion_live_20260422_r4`
- `pytest -q tests/test_slot_classification_paired_compare.py`
- `python3 -m py_compile src/schemas/slot_classification_paired_compare.py src/services/slot_classification_paired_compare.py scripts/eval/compare_slot_classification_paired_benchmarks.py`
- `.venv/bin/python scripts/eval/compare_slot_classification_paired_benchmarks.py --baseline-default snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260421_r9 --baseline-boundary snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r2 --candidate-default snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r1 --candidate-boundary snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r3 --out-dir snapshots/slot_classification_paired_compares --run-id slot_classification_prompt_policy_compare_20260422_r1`
- `.venv/bin/python scripts/eval/compare_slot_classification_paired_benchmarks.py --baseline-default snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r1 --baseline-boundary snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r3 --candidate-default snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r2 --candidate-boundary snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r4 --out-dir snapshots/slot_classification_paired_compares --run-id slot_classification_tie_breaker_compare_20260422_r1`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_boundary_companion_expanded_generation_20260422_r1`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_boundary_companion_expanded_generation_20260422_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_boundary_companion_expanded_live_20260422_r2`
- `pytest -q tests/test_slot_classification_rerun_drift.py`
- `python3 -m py_compile src/schemas/slot_classification_rerun_drift.py src/services/slot_classification_rerun_drift.py scripts/eval/audit_slot_classification_rerun_drift.py`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_20260422.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_boundary_companion_generation_20260422_r5`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_boundary_companion_generation_20260422_r5/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_boundary_companion_live_20260422_r5`
- `.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --fallback-current-slot unknown --out-dir snapshots/slot_classification_predictions --run-id slot_classification_default_template_generation_20260422_r3`
- `.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260422_r3/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_default_template_live_20260422_r3`
- `.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r4 --new-run snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_live_20260422_r5 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_boundary_rerun_drift_20260422_r1`
- `.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r2 --new-run snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r3 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_default_rerun_drift_20260422_r1`
- `pytest -q tests/test_recommend_slot_classification_tuning_review.py`
- `python3 -m py_compile src/schemas/slot_classification_tuning_review.py src/services/slot_classification_tuning_review.py scripts/eval/recommend_slot_classification_tuning_review.py`
- `.venv/bin/python scripts/eval/recommend_slot_classification_tuning_review.py --paired-compare-summary snapshots/slot_classification_paired_compares/slot_classification_prompt_policy_compare_20260422_r1 --out-dir snapshots/slot_classification_tuning_review --run-id slot_classification_tuning_review_prompt_policy_20260422_r1`
- `.venv/bin/python scripts/eval/recommend_slot_classification_tuning_review.py --paired-compare-summary snapshots/slot_classification_paired_compares/slot_classification_tie_breaker_compare_20260422_r1 --default-rerun-drift-summary snapshots/slot_classification_rerun_drift/slot_classification_default_rerun_drift_20260422_r1 --boundary-rerun-drift-summary snapshots/slot_classification_rerun_drift/slot_classification_boundary_rerun_drift_20260422_r1 --out-dir snapshots/slot_classification_tuning_review --run-id slot_classification_tuning_review_20260422_r1`

## Remaining Risk

- The current machine's system `python3` still lacks `yaml`, so direct script execution outside the repo runtime can fail through transitive `src.schemas` imports. The audit works correctly under the repo `.venv`.
- The default goldset template now has summary coverage and harder assay-performance ambiguity, but the set is still only eleven papers and all rows remain `title_summary` inputs.
- The first harder-pass mismatch (`10.1186/s13195-022-01005-8`) is informative but still reflects one labeling decision on an intrinsically fuzzy boundary; if this row becomes contentious later, the right response is to annotate the goldset rationale rather than to silently delete the disagreement.
- The full-text companion set is deliberately tiny and hand-constructed, so it should not be overread as a general full-text benchmark.
- One quick loader check using system `python3` still fails outside `.venv` because that environment lacks `yaml`; the authoritative generation/audit runs here were done under `.venv`.
- The prompt-tuned default baseline is encouraging, but a single good replay is not enough to promote this to a gate. The boundary companion still shows a live tradeoff after the prompt change.
- The new paired-compare lane currently strengthens that caution rather than weakening it: both prompt revisions still require review because mismatch migration remains visible, and the second tie-breaker also regresses the default-template benchmark.
- The rerun-drift lane now adds a second caution: even same-code reruns can move a hard row's predicted slot, so single-run benchmark deltas should not be treated as promotion-grade evidence without stability confirmation.
- The new tuning-review lane adds a third guardrail: even when historical compare artifacts exist, the repo now has an explicit place to say that the evidence is still advisory-only and the prompt change should stay on hold.

## Recommended Next Step

Pick one bounded follow-up, not both at once:

1. keep using the paired-compare lane for any future prompt or policy tweak so migration is visible immediately rather than reconstructed later
2. pair any important live replay conclusion with a rerun-drift check on the same benchmark surface before treating it as a true improvement or regression
3. if this lane is expanded again, prefer adding more adjudicated boundary rows over more prompt churn, especially rows that separate true clinical utility from biomarker-platform benchmarking
4. do not turn this into a hard readiness gate yet; the benchmark is informative, but it is still too small and too rerun-sensitive for promotion-grade pass/fail use
5. when a future slot prompt or policy candidate is tested, generate the tuning-review artifact as the closeout step so the repo records one explicit advisory decision instead of relying on manual interpretation across multiple snapshots
