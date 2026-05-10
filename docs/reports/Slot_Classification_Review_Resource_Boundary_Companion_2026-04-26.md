# Slot Classification Review Resource Boundary Companion

Status: operational report; additive boundary companion
Date: 2026-04-26
Lane: slot classification tuning review
Scope: review/resource taxonomy boundary rows for the current three-slot rubric

## Purpose

Add a small labeled companion surface for review, guideline, resource, atlas, and methods-review cases before broadening any runtime fallback rule.

This is a review/gate artifact. It does not create a new `review` or `resource` slot, and it does not change runtime prompt, schema, database, export, or historical labels.

## Companion CSV

Goldset:

- `tests/gold_set/slot_classification_review_resource_boundary_20260426.csv`

Rows:

- `review_clinical_benefit_001`: `clinical`
- `review_mechanism_001`: `mechanism`
- `guideline_clinical_001`: `clinical`
- `resource_methods_001`: `methods`
- `resource_mechanism_001`: `mechanism`
- `review_methods_001`: `methods`

The labels keep the current three-slot taxonomy:

- disease-focused clinical evidence synthesis and clinical guidance stay `clinical`
- causal biology/pathway synthesis and mechanism-oriented atlases stay `mechanism`
- assay benchmark resources and pre-analytical workflow reviews stay `methods`

## Evidence

First run:

- `snapshots/slot_classification_predictions/slot_classification_review_resource_boundary_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_review_resource_boundary_audit_20260426_r1/summary.json`

Result:

- accuracy `1.0`
- mismatch count `0`
- prediction coverage `1.0`

Same-code rerun:

- `snapshots/slot_classification_predictions/slot_classification_review_resource_boundary_generation_20260426_r2/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_review_resource_boundary_audit_20260426_r2/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_review_resource_boundary_delta_20260426_r1/summary.json`

Result:

- accuracy `0.8333`
- mismatch count `1`
- drift count `1`
- drift rate `0.1667`
- drifted row: `review_methods_001`

Expanded methods-review/resource follow-up:

- `tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv`
- `snapshots/slot_classification_predictions/slot_classification_review_resource_boundary_expanded_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_review_resource_boundary_expanded_audit_20260426_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_review_resource_boundary_expanded_generation_20260426_r2/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_review_resource_boundary_expanded_audit_20260426_r2/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_review_resource_boundary_expanded_delta_20260426_r1/summary.json`

Expanded result:

- rows: `11`
- gold distribution: `clinical=2`, `mechanism=2`, `methods=7`
- r1 accuracy `0.9091`, mismatch count `1`
- r2 accuracy `0.9091`, mismatch count `1`
- drift count `2`
- drift rate `0.1818`
- drifted rows: `review_methods_001`, `review_methods_004`

## Interpretation

The current runtime prompt handles the clinical-review, mechanistic-review, guideline, benchmark-resource, and mechanism-atlas examples on both runs.

The unstable row is a methods-focused systematic review of pre-analytical assay workflows:

- gold: `methods`
- first run: `methods`
- rerun: `mechanism`

This suggests the next risk is not the narrow clinical-review fallback already added. The more fragile boundary is methods-review/resource language where "biomarker", "neurodegeneration", "metabolomic", or disease context can pull the model away from the methods center of gravity.

The expanded follow-up strengthens that interpretation. Additional methods/resource rows mostly stayed `methods`, but the unstable failures remained concentrated in systematic methods-review rows:

- `review_methods_001`: pre-analytical plasma neurodegeneration biomarker workflow review
- `review_methods_004`: mass-spectrometry metabolomic biomarker sample-preparation review

## Decision

Do not broaden the runtime fallback from this evidence.

Before any runtime policy change, test a non-runtime prompt candidate that explicitly says methods-focused systematic reviews of assay handling, calibration, quality control, sample preparation, image-analysis, preprocessing, or analytical workflow reliability remain `methods` even when the review mentions disease context, biomarkers, omics, or neurodegeneration.

Do not add a broad deterministic fallback from this evidence. The failure is specific enough to evaluate as a prompt-boundary clarification first.

## Prompt Candidate R1

Candidate:

- `snapshots/slot_classification_prompt_candidates/slot_classification_methods_review_boundary_candidate_20260426_r1/candidate_prompt.md`

Evaluation:

- `snapshots/slot_classification_predictions/slot_classification_methods_review_boundary_candidate_expanded_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_methods_review_boundary_candidate_expanded_audit_20260426_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_methods_review_boundary_candidate_default_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_methods_review_boundary_candidate_default_audit_20260426_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_methods_review_boundary_candidate_boundary_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_methods_review_boundary_candidate_boundary_audit_20260426_r1/summary.json`

Result:

- review/resource expanded companion: accuracy `1.0`, mismatch count `0`
- expanded boundary companion: accuracy `1.0`, mismatch count `0`
- default template: accuracy `0.9091`, mismatch count `1`
- blocking mismatch: `10.3390/nu17193125`

Interpretation:

The r1 prompt candidate proves the methods-review clarification can fix the target surface, but it is not safe for runtime promotion because it regresses the clinical-benefit systematic-review hard case. The next candidate should preserve the methods-review boundary while strengthening the clinical-benefit review hard stop.

## Prompt Candidate R2

Candidate:

- `snapshots/slot_classification_prompt_candidates/slot_classification_methods_review_boundary_candidate_20260426_r2/candidate_prompt.md`

Evaluation:

- `snapshots/slot_classification_predictions/slot_classification_methods_review_boundary_candidate_r2_default_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_methods_review_boundary_candidate_r2_default_audit_20260426_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_methods_review_boundary_candidate_r2_boundary_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_methods_review_boundary_candidate_r2_boundary_audit_20260426_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_methods_review_boundary_candidate_r2_expanded_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_methods_review_boundary_candidate_r2_expanded_audit_20260426_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_methods_review_boundary_candidate_r2_expanded_generation_20260426_r2/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_methods_review_boundary_candidate_r2_expanded_audit_20260426_r2/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_methods_review_boundary_candidate_r2_expanded_delta_20260426_r1/summary.json`
- `snapshots/slot_classification_paired_compares/slot_classification_methods_review_boundary_candidate_r2_pair_compare_20260426_r1/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_methods_review_boundary_candidate_r2_default_delta_20260426_r1/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_methods_review_boundary_candidate_r2_boundary_delta_20260426_r1/summary.json`
- `snapshots/slot_classification_tuning_review/slot_classification_methods_review_boundary_candidate_r2_tuning_review_20260426_r1/summary.json`

Result:

- default template: accuracy `1.0`, mismatch count `0`
- expanded boundary companion: accuracy `1.0`, mismatch count `0`
- review/resource expanded companion: accuracy `1.0`, mismatch count `0`
- review/resource expanded companion rerun: accuracy `1.0`, mismatch count `0`
- review/resource expanded drift count `0`, drift rate `0.0`
- paired compare passed with no default or boundary regression
- tuning review: `review_ready=true`, `prompt_change_ready=true`

Decision:

The r2 prompt candidate repaired the r1 clinical-benefit review regression while preserving the methods-review/resource boundary improvement. This candidate is safe to promote as a prompt-only runtime change. It does not justify broadening the deterministic fallback.

## Runtime Prompt-Only Promotion

Runtime patch:

- `src/llm_provider.py`
- `tests/test_llm_provider_canonical_language.py`

Runtime evaluation:

- `snapshots/slot_classification_predictions/slot_classification_runtime_methods_review_boundary_default_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_runtime_methods_review_boundary_default_audit_20260426_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_runtime_methods_review_boundary_boundary_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_runtime_methods_review_boundary_boundary_audit_20260426_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_runtime_methods_review_boundary_review_resource_expanded_generation_20260426_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_runtime_methods_review_boundary_review_resource_expanded_audit_20260426_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_runtime_methods_review_boundary_review_resource_expanded_generation_20260426_r2/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_runtime_methods_review_boundary_review_resource_expanded_audit_20260426_r2/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_runtime_methods_review_boundary_review_resource_expanded_delta_20260426_r1/summary.json`
- `snapshots/slot_classification_paired_compares/slot_classification_runtime_methods_review_boundary_pair_compare_20260426_r1/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_runtime_methods_review_boundary_default_delta_20260426_r1/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_runtime_methods_review_boundary_boundary_delta_20260426_r1/summary.json`
- `snapshots/slot_classification_tuning_review/slot_classification_runtime_methods_review_boundary_tuning_review_20260426_r1/summary.json`

Runtime result:

- default template: accuracy `1.0`, mismatch count `0`
- expanded boundary companion: accuracy `1.0`, mismatch count `0`
- review/resource expanded companion r1: accuracy `1.0`, mismatch count `0`
- review/resource expanded companion r2: accuracy `1.0`, mismatch count `0`
- review/resource expanded drift count `0`, drift rate `0.0`
- baseline-vs-runtime paired compare passed with no default or boundary regression
- default and boundary delta drift rates stayed `0.0`
- runtime tuning review: `review_ready=true`, `prompt_change_ready=true`

Implementation boundary:

The runtime change is prompt-only. It adds a clinical evidence review hard stop and a methods-review boundary check to `LLMProvider.classify_slot`, but it does not change the deterministic clinical-review fallback, API contracts, schemas, database/state, exports, stored labels, or inference-routing behavior.

## Verification Commands

```bash
.venv/bin/python -c 'from pathlib import Path; from src.services.slot_classification_audit import load_slot_classification_goldset_csv; rows=load_slot_classification_goldset_csv(Path("tests/gold_set/slot_classification_review_resource_boundary_20260426.csv")); print(len(rows)); print({r["paper_id"]: r["gold_slot"] for r in rows})'
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_20260426.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_review_resource_boundary_generation_20260426_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_20260426.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_review_resource_boundary_generation_20260426_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_review_resource_boundary_audit_20260426_r1
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_20260426.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_review_resource_boundary_generation_20260426_r2 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_20260426.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_review_resource_boundary_generation_20260426_r2/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_review_resource_boundary_audit_20260426_r2
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_review_resource_boundary_audit_20260426_r1 --new-run snapshots/slot_classification_goldset_audits/slot_classification_review_resource_boundary_audit_20260426_r2 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_review_resource_boundary_delta_20260426_r1
.venv/bin/python -c 'from pathlib import Path; from collections import Counter; from src.services.slot_classification_audit import load_slot_classification_goldset_csv; rows=load_slot_classification_goldset_csv(Path("tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv")); print(len(rows)); print(Counter(r["gold_slot"] for r in rows)); print([r["paper_id"] for r in rows])'
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_review_resource_boundary_expanded_generation_20260426_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_review_resource_boundary_expanded_generation_20260426_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_review_resource_boundary_expanded_audit_20260426_r1
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_review_resource_boundary_expanded_generation_20260426_r2 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_review_resource_boundary_expanded_generation_20260426_r2/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_review_resource_boundary_expanded_audit_20260426_r2
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_review_resource_boundary_expanded_audit_20260426_r1 --new-run snapshots/slot_classification_goldset_audits/slot_classification_review_resource_boundary_expanded_audit_20260426_r2 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_review_resource_boundary_expanded_delta_20260426_r1
.venv/bin/python scripts/eval/generate_slot_classification_prompt_candidate_predictions.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv --candidate-prompt snapshots/slot_classification_prompt_candidates/slot_classification_methods_review_boundary_candidate_20260426_r1/candidate_prompt.md --candidate-id slot_classification_methods_review_boundary_candidate_20260426_r1 --out-dir snapshots/slot_classification_predictions --run-id slot_classification_methods_review_boundary_candidate_expanded_generation_20260426_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_methods_review_boundary_candidate_expanded_generation_20260426_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_methods_review_boundary_candidate_expanded_audit_20260426_r1
.venv/bin/python scripts/eval/generate_slot_classification_prompt_candidate_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --candidate-prompt snapshots/slot_classification_prompt_candidates/slot_classification_methods_review_boundary_candidate_20260426_r1/candidate_prompt.md --candidate-id slot_classification_methods_review_boundary_candidate_20260426_r1 --out-dir snapshots/slot_classification_predictions --run-id slot_classification_methods_review_boundary_candidate_default_generation_20260426_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_methods_review_boundary_candidate_default_generation_20260426_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_methods_review_boundary_candidate_default_audit_20260426_r1
.venv/bin/python scripts/eval/generate_slot_classification_prompt_candidate_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --candidate-prompt snapshots/slot_classification_prompt_candidates/slot_classification_methods_review_boundary_candidate_20260426_r1/candidate_prompt.md --candidate-id slot_classification_methods_review_boundary_candidate_20260426_r1 --out-dir snapshots/slot_classification_predictions --run-id slot_classification_methods_review_boundary_candidate_boundary_generation_20260426_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_methods_review_boundary_candidate_boundary_generation_20260426_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_methods_review_boundary_candidate_boundary_audit_20260426_r1
.venv/bin/python -m pytest tests/test_llm_provider_canonical_language.py -k 'classify_slot'
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_runtime_methods_review_boundary_default_generation_20260426_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_runtime_methods_review_boundary_default_generation_20260426_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_runtime_methods_review_boundary_default_audit_20260426_r1
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_runtime_methods_review_boundary_boundary_generation_20260426_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_runtime_methods_review_boundary_boundary_generation_20260426_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_runtime_methods_review_boundary_boundary_audit_20260426_r1
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_runtime_methods_review_boundary_review_resource_expanded_generation_20260426_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_runtime_methods_review_boundary_review_resource_expanded_generation_20260426_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_runtime_methods_review_boundary_review_resource_expanded_audit_20260426_r1
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_runtime_methods_review_boundary_review_resource_expanded_generation_20260426_r2 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_review_resource_boundary_expanded_20260426.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_runtime_methods_review_boundary_review_resource_expanded_generation_20260426_r2/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_runtime_methods_review_boundary_review_resource_expanded_audit_20260426_r2
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_methods_review_boundary_review_resource_expanded_audit_20260426_r1 --new-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_methods_review_boundary_review_resource_expanded_audit_20260426_r2 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_runtime_methods_review_boundary_review_resource_expanded_delta_20260426_r1
.venv/bin/python scripts/eval/compare_slot_classification_paired_benchmarks.py --baseline-default snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_default_audit_20260425_r1 --baseline-boundary snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_boundary_audit_20260425_r1 --candidate-default snapshots/slot_classification_goldset_audits/slot_classification_runtime_methods_review_boundary_default_audit_20260426_r1 --candidate-boundary snapshots/slot_classification_goldset_audits/slot_classification_runtime_methods_review_boundary_boundary_audit_20260426_r1 --out-dir snapshots/slot_classification_paired_compares --run-id slot_classification_runtime_methods_review_boundary_pair_compare_20260426_r1
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_default_audit_20260425_r1 --new-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_methods_review_boundary_default_audit_20260426_r1 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_runtime_methods_review_boundary_default_delta_20260426_r1
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_boundary_audit_20260425_r1 --new-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_methods_review_boundary_boundary_audit_20260426_r1 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_runtime_methods_review_boundary_boundary_delta_20260426_r1
.venv/bin/python scripts/eval/recommend_slot_classification_tuning_review.py --paired-compare-summary snapshots/slot_classification_paired_compares/slot_classification_runtime_methods_review_boundary_pair_compare_20260426_r1 --default-rerun-drift-summary snapshots/slot_classification_rerun_drift/slot_classification_runtime_methods_review_boundary_default_delta_20260426_r1 --boundary-rerun-drift-summary snapshots/slot_classification_rerun_drift/slot_classification_runtime_methods_review_boundary_boundary_delta_20260426_r1 --out-dir snapshots/slot_classification_tuning_review --run-id slot_classification_runtime_methods_review_boundary_tuning_review_20260426_r1
```

Note: the first CSV parse attempt with system `python3` failed because that interpreter lacked `yaml`; the repo `.venv` parse check passed.

## Remaining Risk

- The companion rows are synthetic boundary fixtures rather than externally curated real-paper labels.
- The surface is intentionally small.
- The runtime patch is prompt-only and was initially tested on small synthetic gold surfaces.
- The follow-up real-paper companion is now tracked separately in `docs/reports/Slot_Classification_Real_Paper_Review_Resource_Followup_2026-04-29.md`.
- Do not broaden deterministic fallback or taxonomy from these small surfaces alone.
