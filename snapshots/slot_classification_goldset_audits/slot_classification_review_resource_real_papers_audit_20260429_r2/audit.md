# Slot Classification Goldset Audit: slot_classification_review_resource_real_papers_audit_20260429_r2

- Generated At: 2026-04-28T23:42:22.522828+00:00
- Goldset Rows: 6
- Evaluated Rows: 6
- Matched Rows: 6
- Accuracy: 1.0000
- Prediction Coverage Rate: 1.0000

## Metrics
- Gold Slot Counts: {'clinical': 1, 'methods': 4, 'mechanism': 1}
- Predicted Slot Counts: {'clinical': 1, 'methods': 4, 'mechanism': 1}
- Confusion Counts: {'clinical->clinical': 1, 'methods->methods': 4, 'mechanism->mechanism': 1}
- Per-Gold Accuracy: {'clinical': 1.0, 'mechanism': 1.0, 'methods': 1.0}
- Per-Gold Coverage: {'clinical': 1.0, 'mechanism': 1.0, 'methods': 1.0}
- Prediction Status Counts: {'ok': 6}
- Prediction Source Counts: {'live_provider': 6}
- Input Richness Counts: {'title_summary_full_text': 6}

## Examples
- No mismatches or missing predictions recorded.

## Gold Label Rationales
- real_clinical_review_001 (clinical): Labeled clinical because the main question is clinical benefit and evidence quality in adult disease populations; mechanistic rationale is not the primary contribution.
- real_methods_guideline_001 (methods): Labeled methods because the center of gravity is standardizing biomarker study workflow, collection, processing, biobanking, measurement, and reporting.
- real_methods_preanalytic_001 (methods): Labeled methods because the paper evaluates sample-handling variables and measurement reliability rather than clinical prognosis or Alzheimer mechanism.
- real_methods_metabolomics_review_001 (methods): Labeled methods because the review synthesizes sample collection, extraction, and preparation practices for metabolomics rather than clinical outcome evidence or disease mechanism.
- real_methods_database_001 (methods): Labeled methods because the paper's primary contribution is a reusable database and analysis resource, not a new causal pathway or patient-facing clinical claim.
- real_mechanism_atlas_001 (mechanism): Labeled mechanism because the resource is primarily used to make mechanistic disease-biology claims about cell states, vulnerability, response, and resilience in Alzheimer disease.
