# Slot Classification Resource/Mechanism Contrast

Status: Evidence-backed guardrail check
Date: 2026-04-29
Owner: Repository maintainers
Layer: Review/gate artifact
Canonical: No. This report records bounded evaluation evidence and does not replace runtime specs.

## Purpose

Check that the new methods/resource fallback does not overcorrect biology-first atlas papers into `methods`.

The companion contrasts two patterns:

- `methods`: database, knowledgebase, platform, and reusable resource papers where curation/access/schema is the center of gravity.
- `mechanism`: atlas or single-cell papers where the resource exists, but the central contribution is disease biology, cellular vulnerability, immune states, tissue remodeling, or pathological circuits.

## Inputs

- Contrast goldset: `tests/gold_set/slot_classification_resource_mechanism_real_papers_20260429.csv`
- Row count: `8`
- Gold distribution: `methods=4`, `mechanism=4`

Methods/resource controls:

- ssREAD database, DOI `10.1038/s41467-024-49133-z`
- ClinVar, DOI `10.1093/nar/gkv1222`
- Gene Ontology knowledgebase, DOI `10.1093/genetics/iyad031`
- Open Targets Platform, DOI `10.1093/nar/gkaa1027`

Mechanism-first atlas/biology controls:

- Single-cell multiregion dissection of Alzheimer's disease, DOI `10.1038/s41586-024-07606-7`
- Single-cell transcriptomic analysis of Alzheimer's disease, DOI `10.1038/s41586-019-1195-2`
- Single-cell map of diverse immune phenotypes in the breast tumor microenvironment, DOI `10.1016/j.cell.2018.05.060`
- A molecular single-cell lung atlas of lethal COVID-19, DOI `10.1038/s41586-021-03569-1`

## Results

R1 audit:

- Generation run: `slot_classification_resource_mechanism_real_papers_generation_20260429_r1`
- Audit run: `slot_classification_resource_mechanism_real_papers_audit_20260429_r1`
- Accuracy: `1.0`
- Mismatch count: `0`

R2 audit:

- Generation run: `slot_classification_resource_mechanism_real_papers_generation_20260429_r2`
- Audit run: `slot_classification_resource_mechanism_real_papers_audit_20260429_r2`
- Accuracy: `1.0`
- Mismatch count: `0`

Rerun drift:

- Drift run: `slot_classification_resource_mechanism_real_papers_delta_20260429_r1`
- Drift count: `0`
- Drift rate: `0.0`

## Interpretation

No runtime code change is needed from this check.

The current fallback is narrow enough for this contrast set: knowledgebase/database/resource papers stay `methods`, while biology-first atlas papers stay `mechanism`.

This supports keeping the fallback scoped to reporting standards and curated resource/database papers, rather than broadening it to every paper with atlas, resource, database, or omics language.

## Source Links

- ssREAD database: https://doi.org/10.1038/s41467-024-49133-z
- ClinVar: https://doi.org/10.1093/nar/gkv1222
- Gene Ontology 2023: https://doi.org/10.1093/genetics/iyad031
- Open Targets Platform: https://doi.org/10.1093/nar/gkaa1027
- Single-cell multiregion dissection of Alzheimer's disease: https://doi.org/10.1038/s41586-024-07606-7
- Single-cell transcriptomic analysis of Alzheimer's disease: https://doi.org/10.1038/s41586-019-1195-2
- Breast tumor microenvironment single-cell map: https://doi.org/10.1016/j.cell.2018.05.060
- Lethal COVID-19 lung atlas: https://doi.org/10.1038/s41586-021-03569-1

## Verification Commands

```bash
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py \
  --goldset-csv tests/gold_set/slot_classification_resource_mechanism_real_papers_20260429.csv \
  --out-dir snapshots/slot_classification_predictions \
  --run-id slot_classification_resource_mechanism_real_papers_generation_20260429_r1 \
  --fallback-current-slot unknown

.venv/bin/python scripts/eval/audit_slot_classification_goldset.py \
  --goldset-csv tests/gold_set/slot_classification_resource_mechanism_real_papers_20260429.csv \
  --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_resource_mechanism_real_papers_generation_20260429_r1/predictions.jsonl \
  --out-dir snapshots/slot_classification_goldset_audits \
  --run-id slot_classification_resource_mechanism_real_papers_audit_20260429_r1

.venv/bin/python scripts/eval/generate_slot_classification_predictions.py \
  --goldset-csv tests/gold_set/slot_classification_resource_mechanism_real_papers_20260429.csv \
  --out-dir snapshots/slot_classification_predictions \
  --run-id slot_classification_resource_mechanism_real_papers_generation_20260429_r2 \
  --fallback-current-slot unknown

.venv/bin/python scripts/eval/audit_slot_classification_goldset.py \
  --goldset-csv tests/gold_set/slot_classification_resource_mechanism_real_papers_20260429.csv \
  --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_resource_mechanism_real_papers_generation_20260429_r2/predictions.jsonl \
  --out-dir snapshots/slot_classification_goldset_audits \
  --run-id slot_classification_resource_mechanism_real_papers_audit_20260429_r2

.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py \
  --prior-run snapshots/slot_classification_goldset_audits/slot_classification_resource_mechanism_real_papers_audit_20260429_r1 \
  --new-run snapshots/slot_classification_goldset_audits/slot_classification_resource_mechanism_real_papers_audit_20260429_r2 \
  --out-dir snapshots/slot_classification_rerun_drift \
  --run-id slot_classification_resource_mechanism_real_papers_delta_20260429_r1
```

## Remaining Risk

This is a focused contrast set, not a full taxonomy benchmark. Keep expanding with biology-first atlas papers that include stronger database/platform language before changing the fallback again.
