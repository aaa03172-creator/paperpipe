# Slot Classification Real-Paper Review Resource Follow-up

Status: operational report; additive real-paper companion
Date: 2026-04-29
Lane: slot classification tuning review
Scope: real-paper follow-up for review/resource taxonomy boundaries

## Purpose

Complement the synthetic review/resource boundary companion with a small real-paper surface before considering any broader deterministic fallback, source strategy, or taxonomy change.

This is a review/gate artifact. It does not change runtime prompt, deterministic fallback, schema, database, export, stored labels, or inference routing.

## Companion CSV

Goldset:

- `tests/gold_set/slot_classification_review_resource_real_papers_20260429.csv`

Rows:

- `real_clinical_review_001`: `clinical`
- `real_methods_guideline_001`: `methods`
- `real_methods_preanalytic_001`: `methods`
- `real_methods_metabolomics_review_001`: `methods`
- `real_methods_database_001`: `methods`
- `real_mechanism_atlas_001`: `mechanism`

Gold distribution:

- `clinical=1`
- `mechanism=1`
- `methods=4`

## Source Papers

- Clinical review anchor: `10.3390/nu17193125`, "Clinical Benefits of Exogenous Ketosis in Adults with Disease: A Systematic Review".
- Methods guideline: `10.1186/s13024-024-00711-1`, "Alzheimer blood biomarkers: practical guidelines for study design, sample collection, processing, biobanking, measurement and result reporting".
- Methods preanalytical paper: `10.1016/j.dadm.2019.02.002`, "Preanalytical sample handling recommendations for Alzheimer's disease plasma biomarkers".
- Methods metabolomics review: `10.3390/metabo14010036`, "Critical Factors in Sample Collection and Preparation for Clinical Metabolomics of Underexplored Biological Specimens".
- Methods database/resource: `10.1038/s41467-024-49133-z`, "A single-cell and spatial RNA-seq database for Alzheimer's disease (ssREAD)".
- Mechanism atlas/resource contrast: `10.1038/s41586-024-07606-7`, "Single-cell multiregion dissection of Alzheimer's disease".

## Evidence

First runtime run:

- `snapshots/slot_classification_predictions/slot_classification_review_resource_real_papers_generation_20260429_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_review_resource_real_papers_audit_20260429_r1/summary.json`

Result:

- accuracy `1.0`
- mismatch count `0`
- prediction coverage `1.0`

Same-code rerun:

- `snapshots/slot_classification_predictions/slot_classification_review_resource_real_papers_generation_20260429_r2/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_review_resource_real_papers_audit_20260429_r2/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_review_resource_real_papers_delta_20260429_r1/summary.json`

Result:

- accuracy `1.0`
- mismatch count `0`
- drift count `0`
- drift rate `0.0`

## Interpretation

The prompt-only runtime patch generalized beyond the synthetic companion on this small real-paper surface:

- disease-focused clinical evidence review stayed `clinical`
- guideline-like blood-biomarker workflow paper stayed `methods`
- preanalytical handling paper stayed `methods`
- clinical metabolomics sample-preparation review stayed `methods`
- database/resource paper centered on data curation and analysis tooling stayed `methods`
- single-cell atlas/resource paper centered on disease biology and mechanistic interpretation stayed `mechanism`

This supports the current prompt-only boundary clarification, but it does not justify a broader deterministic fallback or taxonomy expansion.

## Verification Commands

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
from src.services.slot_classification_audit import load_slot_classification_goldset_csv
rows = load_slot_classification_goldset_csv(Path('tests/gold_set/slot_classification_review_resource_real_papers_20260429.csv'))
print('rows', len(rows))
print('gold_distribution', Counter(r['gold_slot'] for r in rows))
print('ids', [r['paper_id'] for r in rows])
PY
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_review_resource_real_papers_20260429.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_review_resource_real_papers_generation_20260429_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_review_resource_real_papers_20260429.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_review_resource_real_papers_generation_20260429_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_review_resource_real_papers_audit_20260429_r1
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_review_resource_real_papers_20260429.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_review_resource_real_papers_generation_20260429_r2 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_review_resource_real_papers_20260429.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_review_resource_real_papers_generation_20260429_r2/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_review_resource_real_papers_audit_20260429_r2
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_review_resource_real_papers_audit_20260429_r1 --new-run snapshots/slot_classification_goldset_audits/slot_classification_review_resource_real_papers_audit_20260429_r2 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_review_resource_real_papers_delta_20260429_r1
```

## Source Links

- `10.3390/nu17193125`: https://pubmed.ncbi.nlm.nih.gov/41097203/
- `10.1186/s13024-024-00711-1`: https://pubmed.ncbi.nlm.nih.gov/38750570/
- `10.1016/j.dadm.2019.02.002`: https://pubmed.ncbi.nlm.nih.gov/30984815/
- `10.3390/metabo14010036`: https://www.mdpi.com/2218-1989/14/1/36
- `10.1038/s41467-024-49133-z`: https://www.nature.com/articles/s41467-024-49133-z
- `10.1038/s41586-024-07606-7`: https://www.nature.com/articles/s41586-024-07606-7

## Remaining Risk

- The real-paper follow-up surface is intentionally small.
- The methods rows are still hand-adjudicated and should be expanded with more independently reviewed real examples before policy broadening.
- Source abstracts and publisher metadata were used only to prepare a compact goldset fixture; canonical runtime state remains schema-backed pipeline state, not this report.
