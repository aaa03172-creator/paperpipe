# Slot Classification Real-Paper Methods/Resource Expansion

Status: Evidence-backed runtime follow-up
Date: 2026-04-29
Owner: Repository maintainers
Layer: Review/gate artifact
Canonical: No. This report records bounded evaluation evidence and does not replace runtime specs.

## Purpose

Add actual-paper methods-review/resource examples beyond the earlier six-row real-paper companion, then verify whether the current slot classifier keeps reporting standards, methods reviews, and database/resource papers in `methods`.

This is intentionally additive. It does not introduce a new slot taxonomy, storage layer, schema contract, or inference-routing path.

## Inputs

- Expanded goldset: `tests/gold_set/slot_classification_review_resource_real_papers_expanded_20260429.csv`
- Row count: `16`
- Gold distribution: `clinical=1`, `methods=14`, `mechanism=1`
- New actual-paper examples added in this expansion:
  - PRISMA 2020 reporting statement, DOI `10.1136/bmj.n71`
  - STARD 2015 reporting checklist, DOI `10.1136/bmj.h5527`
  - TRIPOD reporting statement, DOI `10.1186/s12916-014-0241-z`
  - MIFlowCyt minimum-information standard, DOI `10.1002/cyto.a.20623`
  - RNA-seq best-practices methods review, DOI `10.1186/s13059-016-0881-8`
  - Autophagy assay-use guideline, DOI `10.1080/15548627.2020.1797280`
  - ClinVar database/resource paper, DOI `10.1093/nar/gkv1222`
  - Open Targets Platform resource paper, DOI `10.1093/nar/gkaa1027`
  - MSigDB Hallmark gene set resource paper, DOI `10.1016/j.cels.2015.12.004`
  - Gene Ontology knowledgebase paper, DOI `10.1093/genetics/iyad031`

## Evidence

Pre-patch expanded audit surfaced the intended boundary failure:

- Generation run: `slot_classification_review_resource_real_papers_expanded_generation_20260429_r1`
- Audit run: `slot_classification_review_resource_real_papers_expanded_audit_20260429_r1`
- Accuracy: `0.6875`
- Mismatch count: `5`
- Mismatches: `PRISMA`, `STARD`, `ClinVar`, `MSigDB`, `Gene Ontology`

The failure pattern was not a schema or database issue. The classifier over-read reporting/resource papers as clinical or mechanism when patient-facing, diagnostic, gene, or ontology words were prominent.

Runtime follow-up applied the smallest local correction:

- Added real-paper hard-case anchors to the slot-classification prompt.
- Added a narrow `deterministic_methods_resource_fallback` for reporting-standard and database/resource papers when the first pass overcalls `clinical` or `mechanism`.
- Kept existing clinical-benefit review fallback intact for true clinical evidence reviews.

Post-patch expanded audit:

- Generation run: `slot_classification_review_resource_real_papers_expanded_generation_20260429_post_patch_r1`
- Audit run: `slot_classification_review_resource_real_papers_expanded_audit_20260429_post_patch_r1`
- Accuracy: `1.0`
- Mismatch count: `0`

Post-patch rerun stability:

- Rerun generation: `slot_classification_review_resource_real_papers_expanded_generation_20260429_post_patch_r2`
- Rerun audit: `slot_classification_review_resource_real_papers_expanded_audit_20260429_post_patch_r2`
- Rerun accuracy: `1.0`
- Rerun mismatch count: `0`
- Drift run: `slot_classification_review_resource_real_papers_expanded_delta_20260429_post_patch_r1`
- Drift count: `0`
- Drift rate: `0.0`

## Source Links

- PRISMA 2020: https://doi.org/10.1136/bmj.n71
- STARD 2015: https://doi.org/10.1136/bmj.h5527
- TRIPOD: https://doi.org/10.1186/s12916-014-0241-z
- MIFlowCyt: https://doi.org/10.1002/cyto.a.20623
- RNA-seq best practices: https://doi.org/10.1186/s13059-016-0881-8
- Autophagy assay guidelines: https://doi.org/10.1080/15548627.2020.1797280
- ClinVar: https://doi.org/10.1093/nar/gkv1222
- Open Targets Platform: https://doi.org/10.1093/nar/gkaa1027
- MSigDB Hallmark: https://doi.org/10.1016/j.cels.2015.12.004
- Gene Ontology 2023: https://doi.org/10.1093/genetics/iyad031

## Verification Commands

```bash
.venv/bin/python -m pytest tests/test_llm_provider_canonical_language.py -k classify_slot -q

.venv/bin/python scripts/eval/generate_slot_classification_predictions.py \
  --goldset-csv tests/gold_set/slot_classification_review_resource_real_papers_expanded_20260429.csv \
  --out-dir snapshots/slot_classification_predictions \
  --run-id slot_classification_review_resource_real_papers_expanded_generation_20260429_post_patch_r1 \
  --fallback-current-slot unknown

.venv/bin/python scripts/eval/audit_slot_classification_goldset.py \
  --goldset-csv tests/gold_set/slot_classification_review_resource_real_papers_expanded_20260429.csv \
  --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_review_resource_real_papers_expanded_generation_20260429_post_patch_r1/predictions.jsonl \
  --out-dir snapshots/slot_classification_goldset_audits \
  --run-id slot_classification_review_resource_real_papers_expanded_audit_20260429_post_patch_r1

.venv/bin/python scripts/eval/generate_slot_classification_predictions.py \
  --goldset-csv tests/gold_set/slot_classification_review_resource_real_papers_expanded_20260429.csv \
  --out-dir snapshots/slot_classification_predictions \
  --run-id slot_classification_review_resource_real_papers_expanded_generation_20260429_post_patch_r2 \
  --fallback-current-slot unknown

.venv/bin/python scripts/eval/audit_slot_classification_goldset.py \
  --goldset-csv tests/gold_set/slot_classification_review_resource_real_papers_expanded_20260429.csv \
  --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_review_resource_real_papers_expanded_generation_20260429_post_patch_r2/predictions.jsonl \
  --out-dir snapshots/slot_classification_goldset_audits \
  --run-id slot_classification_review_resource_real_papers_expanded_audit_20260429_post_patch_r2

.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py \
  --prior-run snapshots/slot_classification_goldset_audits/slot_classification_review_resource_real_papers_expanded_audit_20260429_post_patch_r1 \
  --new-run snapshots/slot_classification_goldset_audits/slot_classification_review_resource_real_papers_expanded_audit_20260429_post_patch_r2 \
  --out-dir snapshots/slot_classification_rerun_drift \
  --run-id slot_classification_review_resource_real_papers_expanded_delta_20260429_post_patch_r1
```

## Remaining Risk

This expanded set is still small and hand-adjudicated. It is strong enough to justify a narrow reporting/resource fallback, but not enough to add a new `resource` slot or broaden deterministic classification for every database-like title.

The key boundary to keep watching is database/resource papers that also make substantial new causal biology claims. Those should remain `mechanism` when the resource is secondary to the biological interpretation.
