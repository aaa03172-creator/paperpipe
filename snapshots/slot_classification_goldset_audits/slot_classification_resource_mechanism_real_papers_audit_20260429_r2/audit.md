# Slot Classification Goldset Audit: slot_classification_resource_mechanism_real_papers_audit_20260429_r2

- Generated At: 2026-04-29T00:11:21.671120+00:00
- Goldset Rows: 8
- Evaluated Rows: 8
- Matched Rows: 8
- Accuracy: 1.0000
- Prediction Coverage Rate: 1.0000

## Metrics
- Gold Slot Counts: {'methods': 4, 'mechanism': 4}
- Predicted Slot Counts: {'methods': 4, 'mechanism': 4}
- Confusion Counts: {'methods->methods': 4, 'mechanism->mechanism': 4}
- Per-Gold Accuracy: {'mechanism': 1.0, 'methods': 1.0}
- Per-Gold Coverage: {'mechanism': 1.0, 'methods': 1.0}
- Prediction Status Counts: {'ok': 8}
- Prediction Source Counts: {'live_provider': 8}
- Input Richness Counts: {'title_summary_full_text': 8}

## Examples
- No mismatches or missing predictions recorded.

## Gold Label Rationales
- real_methods_database_ssread_contrast_001 (methods): Labeled methods because the primary contribution is a reusable curated database and analysis resource, not a new causal disease-biology claim.
- real_methods_database_clinvar_contrast_001 (methods): Labeled methods because the contribution is a public data archive and informatics resource for variant interpretations.
- real_methods_database_go_contrast_001 (methods): Labeled methods because the contribution is a standardized gene-function knowledgebase and analysis resource.
- real_methods_database_opentargets_contrast_001 (methods): Labeled methods because the main contribution is an integrated platform/resource for target-disease evidence and prioritization.
- real_mechanism_atlas_ad_multiregion_contrast_001 (mechanism): Labeled mechanism because the resource is primarily used to make disease-biology claims about cell states, vulnerability, response, and resilience.
- real_mechanism_singlecell_ad_mathys_001 (mechanism): Labeled mechanism because the main contribution is disease-biology interpretation of cell-type-specific transcriptional programs, not resource curation.
- real_mechanism_breast_tme_immune_001 (mechanism): Labeled mechanism because the map is used to characterize tumor immune biology rather than to introduce a reusable database or reporting standard.
- real_mechanism_covid_lung_atlas_001 (mechanism): Labeled mechanism because the atlas supports causal disease-biology interpretation of pathological cell states and circuits.
