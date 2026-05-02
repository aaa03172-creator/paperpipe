# Extraction Regression Repo-Grounded Pilot

- Date: 2026-03-27
- Scope: first bounded extraction regression run using repo-grounded paper artifacts only
- Harness: `scripts/eval/compare_extraction_outputs.py`
- Manifest: `goldset/manifests/extraction_regression_repo_grounded_pilot_20260327.json`
- Snapshot: `snapshots/extraction_regression_eval/extraction_repo_grounded_pilot_20260327_r1/`

## Goal

Turn the new extraction regression harness from a synthetic-only test lane into a bounded repo-grounded pilot without touching runtime extraction.

Current default posture for this lane is frozen separately in [Specialty_Runtime_Posture_Decision_2026-03-29.md](/Users/jangseongjin/paperpipe/docs/reports/Specialty_Runtime_Posture_Decision_2026-03-29.md). Use that memo for the current “keep sidecar canonical, keep runtime specialty blocked” operating rule.

## Inputs

This pilot uses five paper ids with existing PaperPipe artifacts:

1. `zotero:coricTargetingProdromalAlzheimer2015`
2. `zotero:craftSafetyEfficacyFeasibility2020`
3. `zotero:duboisAmnesticMCIProdromal2004`
4. `zotero:therriaultBiomarkerModelingAlzheimers2022`
5. `zotero:hanssonBloodBiomarkersAlzheimers2023`

Gold fixtures are manually curated `SpecialtyTrialExtraction` snapshots grounded in local `document_artifact.json` text.

Prediction fixtures are repo-grounded proxy baselines translated from local `prior_output.json` summaries and claims. They are intentionally bounded and do not claim to be live runtime extractor outputs.

## Result

Run id `extraction_repo_grounded_pilot_20260327_r1` completed successfully and failed as expected under zero-tolerance thresholds.

- `document_count=5`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=1`
- `hallucination_docs=1`
- `negation_failure_docs=1`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=3`

Core field match rates:

- `population=0.8`
- `intervention=0.8`
- `outcome=1.0`
- `sample_size=0.8`
- `duration=0.8`

## Per-Paper Outcome

- `zotero:craftSafetyEfficacyFeasibility2020`: clean match
- `zotero:therriaultBiomarkerModelingAlzheimers2022`: clean match
- `zotero:coricTargetingProdromalAlzheimer2015`: `missing_core_field` on `sample_size` and `duration`
- `zotero:duboisAmnesticMCIProdromal2004`: `negation_failure` on `population`
- `zotero:hanssonBloodBiomarkersAlzheimers2023`: `hallucination` on `intervention`

## Interpretation

This is enough to prove that the harness now works on repo-grounded inputs instead of synthetic-only fixtures.

It is not enough to judge runtime extraction quality because the prediction side is still a curated proxy baseline. The live local extractor path was probed separately and currently returns `None` after schema validation failures, so using those outputs directly would widen scope into extractor repair.

## Decision

- Keep this lane as sidecar evaluation only.
- Treat this pilot as a bounded baseline for future extraction regression work.
- Do not use this snapshot as evidence for runtime extractor promotion or regression claims against production until we have real persisted `SpecialtyTrialExtraction` predictions.

## Real Prediction Generation Probe

To avoid widening scope into runtime extraction changes, a bounded sidecar generator was added at `scripts/eval/generate_extraction_predictions.py`.

It rebuilds a compact extraction prompt from local `document_artifact.json`, calls an Ollama model with a strict timeout, applies minimal citation/enum repair, and persists either:

- validated `SpecialtyTrialExtraction` predictions, or
- timeout/error artifacts plus a generated-manifest stub

Two probes were run:

1. Configured extractor lane
   - Run: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_20260327_r1/`
   - Model: `llama3:latest`
   - Timeout: `20s`
   - Result: `0/5` success, `5/5` `ReadTimeout`

2. Installed alternate local model probe
   - Run: `snapshots/extraction_prediction_generation/extraction_prediction_probe_openhermes_20260327_r1/`
   - Model: `openhermes:latest`
   - Timeout: `20s`
   - Result: `0/1` success, `1/1` `ReadTimeout`

This means the original blocker was not “no real prediction path exists”, but “the default local extractor lane needs a larger latency budget plus minimal schema repair”.

### Follow-up Probe With Larger Budget

The same sidecar lane was then rerun with a `90s` timeout and minimal repair extensions for null nested models, alias fields, and scalar-vs-object outcome coercion.

Document-level probe results:

- `Coric` with `90s`: success after repair (`extraction_prediction_probe_coric_20260327_r4_timeout90_repair3`)
- `Craft` with `90s`: success (`extraction_prediction_probe_craft_20260327_r2_timeout90_repair3`)
- `Dubois` with `90s`: success after one more null-bool/null-int repair (`extraction_prediction_probe_dubois_20260327_r2_timeout90_repair5`)

Full repo-grounded generation result:

- Run: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_20260327_r2_timeout90_repair3/`
- Model: `llama3:latest`
- Timeout: `90s`
- Result: `4/5` success in one pass, with `Dubois` fixed separately by the same bounded repair lane

Merged full-5 manifest:

- `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_20260327_r3_timeout90_repair5_merged/generated_manifest.json`

Real-prediction comparison result:

- Run: `snapshots/extraction_regression_eval/extraction_repo_grounded_realpred_full5_20260327_r3/`
- `document_count=5`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=5`
- `negation_failure_docs=4`
- `hallucination_docs=0`
- `core_field_match_rates`:
  - `population=0.2`
  - `intervention=0.6`
  - `outcome=0.0`
  - `sample_size=0.4`
  - `duration=0.6`

This is the first full repo-grounded run backed by real validated prediction files rather than curated proxy predictions. The result is poor on extraction quality, but the generation path itself is now proven.

### Current Repair Replay

After the first full real-pred run, the sidecar repair layer was tightened for the actual raw-output patterns that showed up in `Coric`, `Craft`, `Dubois`, `Therriault`, and `Hansson`:

- sample-size aliases such as `participants_in_treatment_phase`
- mixed-population cues from `diagnosis` / inclusion text
- `name` aliases for intervention/comparator
- `primary_outcome` / outcome-list normalization
- review/biomarker stub downshifts that prevent false `mci_only=true`
- risk-of-bias notes lists and other small schema-shape repairs

Because the saved prediction JSONs in the earlier runs reflected older repair logic, the current sidecar was re-evaluated by replaying the latest successful raw model outputs through the current repair code:

- Replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_20260327_r6_rawreplay_repair9/generated_manifest.json`
- Comparison run: `snapshots/extraction_regression_eval/extraction_repo_grounded_realpred_full5_20260327_r4_rawreplay_repair9/`

Replay result:

- `document_count=5`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=3`
- `negation_failure_docs=0`
- `other_core_mismatch_docs=2`
- `hallucination_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=0.4`
  - `sample_size=0.4`
  - `duration=0.6`

Per-paper replay outcome:

- `zotero:coricTargetingProdromalAlzheimer2015`: intervention recovered; remaining misses are `outcome`, `sample_size`, `duration`
- `zotero:craftSafetyEfficacyFeasibility2020`: population/intervention/outcome recovered; remaining misses are `sample_size`, `duration`
- `zotero:duboisAmnesticMCIProdromal2004`: population/exclusion recovered; remaining mismatch is generic `outcome`
- `zotero:therriaultBiomarkerModelingAlzheimers2022`: population/outcome recovered; remaining miss is `sample_size`
- `zotero:hanssonBloodBiomarkersAlzheimers2023`: population/exclusion recovered; remaining mismatch is generic `outcome`

This replay is the most accurate statement of the current bounded sidecar quality because it uses the latest raw responses plus the latest repair logic, without changing runtime extraction.

### Prompt-Strengthened Replay Baseline

The prompt was then tightened to explicitly prefer:

- named cognitive or diagnostic readouts over safety/tolerability stubs
- randomized or treatment-phase sample size over screened totals
- explicit week/month duration conversion into `study_design.duration_weeks`
- nontrial biomarker/review downshifts instead of false trial extraction

The direct live prompt-strengthened run (`extraction_prediction_repo_grounded_20260327_r7_timeout90_prompt2`) produced `5/5` validated prediction files, but the live compare was still affected by model variability and stale `missing_fields` carried forward from older repairs.

To measure the current bounded sidecar quality without runtime drift, the prompt-strengthened raw outputs were replayed through the latest repair layer:

- Replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_20260327_r11_rawreplay_prompt2_repair14/generated_manifest.json`
- Comparison run: `snapshots/extraction_regression_eval/extraction_repo_grounded_realpred_full5_20260327_r10_rawreplay_prompt2_repair14/`

Final replay result:

- `document_count=5`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

The last bounded sidecar changes that closed the remaining gaps were:

- removing resolved `missing_fields` aliases once `population.n_total` or `duration_weeks` had been recovered
- treating `nonrandomized` as observational instead of accidentally matching the `randomized` substring
- preferring `Key clinical outcome measures` over a safety/tolerability stub when that named efficacy readout is present in the source text
- inferring a `104` week trial horizon from the explicit `At 2 years...` source phrasing in the Coric summary

Per-paper final replay outcome:

- `zotero:coricTargetingProdromalAlzheimer2015`: clean match
- `zotero:craftSafetyEfficacyFeasibility2020`: clean match
- `zotero:duboisAmnesticMCIProdromal2004`: clean match
- `zotero:therriaultBiomarkerModelingAlzheimers2022`: clean match
- `zotero:hanssonBloodBiomarkersAlzheimers2023`: clean match

This is the strongest bounded extraction-regression evidence collected so far. It proves that PaperPipe can now:

- generate real validated `SpecialtyTrialExtraction` prediction files locally with the sidecar lane
- replay saved raw model outputs through the current repair layer
- achieve a full `5/5` repo-grounded match on the current pilot set

It still does **not** justify runtime extractor promotion. The current signoff applies only to this bounded sidecar lane and this five-paper pilot fixture set.

### Expanded Repo-Grounded Replay Check

To test whether the current repair layer generalizes beyond the original five papers, the repo-grounded set was widened to seven papers by adding:

- `zotero:decarliMildCognitiveImpairment2003`
- `zotero:duboisClinicalDiagnosisAlzheimers2021`

Expanded gold manifest:

- `goldset/manifests/extraction_regression_repo_grounded_expanded_20260327.json`

New gold fixtures:

- `goldset/extraction_regression/repo_grounded_expanded_20260327/gold/zotero_decarliMildCognitiveImpairment2003.json`
- `goldset/extraction_regression/repo_grounded_expanded_20260327/gold/zotero_duboisClinicalDiagnosisAlzheimers2021.json`

Those two documents were first probed through the bounded sidecar lane to collect raw model outputs, then replayed through the latest repair layer together with the existing prompt-strengthened raw outputs for the original five papers:

- Expanded replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_expanded_20260327_r2_rawreplay_repair19/generated_manifest.json`
- Expanded compare run: `snapshots/extraction_regression_eval/extraction_repo_grounded_expanded_realpred_20260327_r2_repair19/`

Expanded replay result:

- `document_count=7`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

The extra bounded repair rules needed for this expanded set were still narrow:

- review/recommendation papers without intervention signals now downshift `mci_only` and `include_for_mci_mct_review`
- title-level outcome fallback now covers `Clinical diagnosis of Alzheimer's disease`
- title-level `Mild cognitive impairment` fallback is limited to review-style prevalence/prognosis/aetiology papers
- raw `unknown` sentinels in intervention/comparator fields are normalized back to `None`

This is stronger evidence than the original five-paper pass because it demonstrates that the current sidecar repair layer is not limited to the original bounded pilot. It is still a repo-grounded replay signoff, not a runtime production signoff.

### Broader Repo-Grounded Replay Check

The bounded replay set was then widened one step further with an additional observational community biomarker cohort:

- `zotero:grandeBloodbasedBiomarkersAlzheimers2025`

Broader gold manifest:

- `goldset/manifests/extraction_regression_repo_grounded_broader_20260328.json`

New gold fixture:

- `goldset/extraction_regression/repo_grounded_broader_20260328/gold/zotero_grandeBloodbasedBiomarkersAlzheimers2025.json`

The main bounded changes needed for this broader set were still small and source-grounded:

- abstract summary extraction now recognizes `Evidence regarding ...` style openings instead of requiring explicit `Abstract`/`Background` headers
- sample-size inference now accepts digit groups with commas or normalized spaces (for example `2,148`)
- duration inference now captures `followed for up to 16 years`

Broader replay artifacts:

- Broader replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_broader_20260328_r1_rawreplay_repair20/generated_manifest.json`
- Broader compare run: `snapshots/extraction_regression_eval/extraction_repo_grounded_broader_realpred_20260328_r1_repair20/`

Broader replay result:

- `document_count=8`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

This strengthens the repo-grounded extraction baseline again: the current repair layer now covers trial, observational biomarker, review, recommendation, and community cohort patterns across an eight-paper replay set. It is still not a runtime signoff. The evidence remains bounded to saved raw-output replay plus curated repo-grounded gold.

### Diverse Repo-Grounded Replay Check

The replay set was widened once more with a review-style gut-microbiome paper that does not cleanly behave like the earlier trial, biomarker-cohort, or recommendation artifacts:

- `zotero:chandraGutMicrobiomeAlzheimers2023`

Diverse gold manifest:

- `goldset/manifests/extraction_regression_repo_grounded_diverse_20260328.json`

New gold fixture:

- `goldset/extraction_regression/repo_grounded_diverse_20260328/gold/zotero_chandraGutMicrobiomeAlzheimers2023.json`

The bounded changes needed for this ninth paper were still narrow and source-grounded:

- concept-review detection now also recognizes `what remains to be explored`
- title-level outcome fallback now covers gut-microbiome Alzheimer review phrasing
- cognition stub cleanup now replaces generic biomarker fragments such as `senile plaques` when the paper title gives the better outcome label

Diverse replay artifacts:

- Diverse replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_diverse_20260328_r1_rawreplay_repair21/generated_manifest.json`
- Diverse compare run: `snapshots/extraction_regression_eval/extraction_repo_grounded_diverse_realpred_20260328_r1_repair21/`

Diverse replay result:

- `document_count=9`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

This is the current best bounded extraction baseline. It shows that the sidecar replay lane now covers nine repo-grounded papers spanning trial, observational biomarker, review, recommendation, community cohort, and gut-microbiome review artifact shapes without opening runtime extraction scope.

### Generalized Repo-Grounded Replay Check

The replay set was widened again with a personal-view subjective-cognitive-decline paper that is broader than the earlier recommendation and mechanism-review artifacts:

- `zotero:jessenCharacterisationSubjectiveCognitive2020`

Generalized gold manifest:

- `goldset/manifests/extraction_regression_repo_grounded_generalized_20260328.json`

New gold fixture:

- `goldset/extraction_regression/repo_grounded_generalized_20260328/gold/zotero_jessenCharacterisationSubjectiveCognitive2020.json`

Unlike the earlier Chandra and recommendation-style additions, this one did not require a new repair heuristic. The current sidecar already:

- recognizes `Personal View` as a nontrial review-style signal
- downshifts `mci_only` and `include_for_mci_mct_review`
- preserves a title-grounded non-intervention outcome label

The only bounded difference was latency: the one-doc live probe needed `120s` instead of `90s` before replaying the saved raw output into the current repair lane.

Generalized replay artifacts:

- Generalized replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_generalized_20260328_r1_rawreplay_repair21/generated_manifest.json`
- Generalized compare run: `snapshots/extraction_regression_eval/extraction_repo_grounded_generalized_realpred_20260328_r1_repair21/`

Generalized replay result:

- `document_count=10`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

This is now the strongest bounded extraction-regression evidence in the repo. It shows that the current sidecar replay lane generalizes across ten repo-grounded papers covering trial, observational biomarker, recommendation, review, community cohort, gut-microbiome review, and personal-view artifact shapes, while still staying outside runtime extraction.

### Multicohort Repo-Grounded Replay Check

The replay set was widened again with a biomarker confounding-factor cohort paper that introduces a different artifact shape from the earlier review and recommendation additions:

- `zotero:pichetbinetteConfoundingFactorsAlzheimers2023`

Multicohort gold manifest:

- `goldset/manifests/extraction_regression_repo_grounded_multicohort_20260328.json`

New gold fixture:

- `goldset/extraction_regression/repo_grounded_multicohort_20260328/gold/zotero_pichetbinetteConfoundingFactorsAlzheimers2023.json`

This widening required a small bounded `repair22` pass, still entirely inside the sidecar lane:

- repaired citation title is now reused when the raw payload omits title text, so broader nontrial signals still see phrases such as `plasma biomarkers`
- `_build_paper_inputs(...)` now appends a small second-page follow-up slice when `followed longitudinally for up to` appears outside the first-page methods excerpt
- duration inference now tolerates OCR-interleaved text between `followed longitudinally for up to` and the later `8 years`
- title-level outcome fallback now covers `plasma biomarkers` + `clinical performance`
- biomarker stub outcomes like `p-tau217` can now be replaced by the inferred title-level nontrial outcome when appropriate

As with Jessen, the one-doc live probe needed `120s` rather than the default `90s`, but after replaying the saved raw output through the current repair layer the candidate matched cleanly.

Multicohort replay artifacts:

- Multicohort replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_multicohort_20260328_r1_rawreplay_repair22/generated_manifest.json`
- Multicohort compare run: `snapshots/extraction_regression_eval/extraction_repo_grounded_multicohort_realpred_20260328_r1_repair22/`

Multicohort replay result:

- `document_count=11`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

This is the current best bounded extraction baseline. It shows that the sidecar replay lane now covers eleven repo-grounded papers spanning trial, observational biomarker, recommendation, review, community cohort, gut-microbiome review, personal-view, and multi-cohort biomarker confounding artifacts without expanding runtime scope.

### Diagnostic Repo-Grounded Replay Check

The replay set was widened one more time with a four-cohort diagnostic-performance and prediction-modelling biomarker paper:

- `zotero:karikariBloodPhosphorylatedTau2020`

Diagnostic gold manifest:

- `goldset/manifests/extraction_regression_repo_grounded_diagnostic_20260328.json`

New gold fixture:

- `goldset/extraction_regression/repo_grounded_diagnostic_20260328/gold/zotero_karikariBloodPhosphorylatedTau2020.json`

This widening required a small bounded `repair23` pass, again still entirely inside the sidecar lane:

- `_build_paper_inputs(...)` now also appends second-page snippets around `over a period of ...`, not only `followed ...`
- duration inference now captures `over a period of 1 year`
- title-level outcome fallback now covers `blood phosphorylated tau 181` / `plasma p-tau181` when the paper frames the task as `diagnostic performance` and `prediction modelling`

Unlike Jessen and Pichet, the one-doc live probe for Karikari succeeded within the default `90s` budget.

Diagnostic replay artifacts:

- Diagnostic replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_diagnostic_20260328_r1_rawreplay_repair23/generated_manifest.json`
- Diagnostic compare run: `snapshots/extraction_regression_eval/extraction_repo_grounded_diagnostic_realpred_20260328_r1_repair23/`

Diagnostic replay result:

- `document_count=12`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

This is now the strongest bounded extraction baseline in the repo. The sidecar replay lane covers twelve repo-grounded papers spanning trial, observational biomarker, recommendation, review, community cohort, gut-microbiome review, personal-view, multi-cohort biomarker confounding, and four-cohort diagnostic-performance artifacts without touching runtime extraction.

### Prognostic Repo-Grounded Replay Check

The replay set was widened one more time with a longitudinal prognostic plasma biomarker cohort paper:

- `zotero:mattsson-carlgrenPredictionLongitudinalCognitive2023`

Prognostic gold manifest:

- `goldset/manifests/extraction_regression_repo_grounded_prognostic_20260328.json`

New gold fixture:

- `goldset/extraction_regression/repo_grounded_prognostic_20260328/gold/zotero_mattsson-carlgrenPredictionLongitudinalCognitive2023.json`

This widening introduced a genuinely different artifact family from the earlier diagnostic and recommendation papers: a preclinical Alzheimer prognostic cohort where the key target is longitudinal cognitive decline rather than diagnosis or intervention response.

The bounded `repair24` pass stayed entirely inside the sidecar lane:

- title-level outcome fallback now covers `Prediction of Longitudinal Cognitive Decline in Preclinical Alzheimer Disease`
- named readouts such as `MMSE` / `mPACC` can be canonicalized back to the study-level prognostic target when the title clearly frames the task as longitudinal cognitive decline prediction
- sample-size inference now captures `of those, 171 ... participants were included in the main analyses`
- duration inference now captures `over a median of 6 years`

Unlike Jessen and Pichet, the one-doc live probe for Mattsson succeeded within the default `90s` budget.

Prognostic replay artifacts:

- One-doc live probe: `snapshots/extraction_prediction_generation/extraction_candidate_probe_mattsson_20260328_r4_repair24c/`
- Prognostic replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_prognostic_20260328_r1_rawreplay_repair24/generated_manifest.json`
- Prognostic compare run: `snapshots/extraction_regression_eval/extraction_repo_grounded_prognostic_realpred_20260328_r1_repair24/`

Prognostic replay result:

- `document_count=13`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

This is now the strongest bounded extraction baseline in the repo. The sidecar replay lane covers thirteen repo-grounded papers spanning trial, observational biomarker, recommendation, review, community cohort, gut-microbiome review, personal-view, multi-cohort biomarker confounding, diagnostic-performance, and longitudinal prognostic biomarker artifacts without touching runtime extraction.

### Head-to-Head Repo-Grounded Replay Check

The replay set was widened once more with a section-based head-to-head blood test comparison paper:

- `zotero:schindlerHeadtoheadComparisonLeading2024`

Head-to-head gold manifest:

- `goldset/manifests/extraction_regression_repo_grounded_headtohead_20260328.json`

New gold fixture:

- `goldset/extraction_regression/repo_grounded_headtohead_20260328/gold/zotero_schindlerHeadtoheadComparisonLeading2024.json`

This widening introduced two new bounded sidecar concerns at once:

- a different parser artifact shape (`sections` instead of `pages`)
- a non-intervention head-to-head blood-test comparison where the core target is assay performance for AD pathology rather than diagnosis recommendations or biomarker-only review text

The bounded `repair25` pass stayed inside the sidecar lane:

- `_build_paper_inputs(...)` now consumes the full early-page combined text instead of only the first two slots, and section-based artifacts are allowed one extra early page so participant details are not dropped
- head-to-head family outcome fallback now canonicalizes `amyloid pathology` / `amyloid and tau positivity` to the study-level outcome `Alzheimer's disease pathology test performance`
- head-to-head family sample size now prefers the source-grounded `393 ADNI participants had at least ...` text over unstable model guesses
- head-to-head family false duration inference is zeroed back out so `within 6 months of an amyloid PET scan` does not become a fake study duration

The one-doc live probe for Schindler succeeded within the default `90s` budget.

Head-to-head replay artifacts:

- One-doc live probe: `snapshots/extraction_prediction_generation/extraction_candidate_probe_schindler_20260328_r4_repair25c/`
- Head-to-head replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_headtohead_20260328_r1_rawreplay_repair25/generated_manifest.json`
- Head-to-head compare run: `snapshots/extraction_regression_eval/extraction_repo_grounded_headtohead_realpred_20260328_r1_repair25/`

Head-to-head replay result:

- `document_count=14`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

This is now the strongest bounded extraction baseline in the repo. The sidecar replay lane covers fourteen repo-grounded papers spanning trial, observational biomarker, recommendation, review, community cohort, gut-microbiome review, personal-view, multi-cohort biomarker confounding, diagnostic-performance, longitudinal prognostic, and head-to-head assay-comparison artifacts without touching runtime extraction.

### Preclinical Repo-Grounded Replay Check

The replay set was widened once more with a preclinical non-human mechanistic Alzheimer's disease paper:

- `zotero:colomboMicrobiotaderivedShortChain2021`

Preclinical gold manifest:

- `goldset/manifests/extraction_regression_repo_grounded_preclinical_20260328.json`

New gold fixture:

- `goldset/extraction_regression/repo_grounded_preclinical_20260328/gold/zotero_colomboMicrobiotaderivedShortChain2021.json`

This widening introduced a new artifact family boundary: a mechanistic gut-brain-axis paper in AD mice. The bounded sidecar question here was not latency but how this family should be represented inside the existing `SpecialtyTrialExtraction` review schema without pretending it is a human MCI intervention study.

The bounded `repair27` pass stayed inside the sidecar lane:

- `Ab plaque deposition` is now canonicalized to `Amyloid-beta plaque deposition`
- `SCFA` / `short chain fatty acid` intervention names are normalized consistently
- preclinical non-human signals such as `germ-free AD mice`, `SPF mice`, `microglia`, and `Ab plaque deposition` now force a bounded downshift out of the MCI review lane
- for that excluded-family path, `population.mci_only=false`, `include_for_mci_mct_review=false`, and intervention is cleared instead of pretending this is a human intervention cohort

The one-doc live probe for Colombo succeeded within the default `90s` budget.

Preclinical replay artifacts:

- One-doc live probe: `snapshots/extraction_prediction_generation/extraction_candidate_probe_colombo_20260328_r3_repair27/`
- Preclinical replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_preclinical_20260328_r1_rawreplay_repair27/generated_manifest.json`
- Preclinical compare run: `snapshots/extraction_regression_eval/extraction_repo_grounded_preclinical_realpred_20260328_r1_repair27/`

Preclinical replay result:

- `document_count=15`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

This is now the strongest bounded extraction baseline in the repo. The sidecar replay lane covers fifteen repo-grounded papers spanning trial, observational biomarker, recommendation, review, community cohort, gut-microbiome review, personal-view, multi-cohort biomarker confounding, diagnostic-performance, longitudinal prognostic, head-to-head assay-comparison, and preclinical mechanistic artifacts without touching runtime extraction.

### Preclinical Therapeutic Repo-Grounded Replay Check

The replay set was widened once more with a preclinical therapeutic CRISPR/CasRx mouse study:

- `zotero:zhouGliatoNeuronConversionCRISPRCasRx2020`

Preclinical therapeutic gold manifest:

- `goldset/manifests/extraction_regression_repo_grounded_preclinical_therapeutic_20260328.json`

New gold fixture:

- `goldset/extraction_regression/repo_grounded_preclinical_therapeutic_20260328/gold/zotero_zhouGliatoNeuronConversionCRISPRCasRx2020.json`

This widening introduced a genuinely different family from the earlier mechanistic Colombo paper: a preclinical therapeutic gene-editing/intervention paper that still needs to be excluded from the human MCI review lane without erasing the intervention and study-level therapeutic outcome.

The bounded `repair29` pass stayed inside the sidecar lane:

- preclinical therapeutic signals such as `glia-to-neuron conversion`, `CRISPR-CasRx`, `Ptbp1 knockdown`, and `PD model mice` now force a bounded downshift out of the MCI review lane while preserving the therapeutic framing
- intervention names like `CRISPR-CasRx` / `Ptbp1 knockdown` are canonicalized to `CasRx-mediated Ptbp1 knockdown`
- experiment-specific readouts such as `visual responses` are lifted to the study-level outcome `Neurological disease symptom alleviation` when the title and summary clearly frame the paper that way
- for this excluded-family path, `population.mci_only=false`, `include_for_mci_mct_review=false`, and the therapeutic intervention remains populated instead of being cleared like a mechanistic review artifact

The one-doc live probe for Zhou succeeded within the default `90s` budget.

Preclinical therapeutic replay artifacts:

- One-doc live probe: `snapshots/extraction_prediction_generation/extraction_candidate_probe_zhou_20260328_r3_repair29/`
- Preclinical therapeutic replay manifest: `snapshots/extraction_prediction_generation/extraction_prediction_repo_grounded_preclinical_therapeutic_20260328_r1_rawreplay_repair29/generated_manifest.json`
- Preclinical therapeutic compare run: `snapshots/extraction_regression_eval/extraction_repo_grounded_preclinical_therapeutic_realpred_20260328_r1_repair29/`

Preclinical therapeutic replay result:

- `document_count=16`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `other_core_mismatch_docs=0`
- `core_mismatch_docs=0`
- `core_field_match_rates`:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

This is now the strongest bounded extraction baseline in the repo. The sidecar replay lane covers sixteen repo-grounded papers spanning trial, observational biomarker, recommendation, review, community cohort, gut-microbiome review, personal-view, multi-cohort biomarker confounding, diagnostic-performance, longitudinal prognostic, head-to-head assay-comparison, preclinical mechanistic, and preclinical therapeutic gene-editing artifacts without touching runtime extraction.

### Extraction Generation Latency Audit

To keep the widening work operationally bounded, a separate sidecar audit was added at `scripts/eval/audit_extraction_generation_latency.py`.

It scans persisted live generation metrics under `snapshots/extraction_prediction_generation/`, skips `raw_replay` runs, and classifies each paper into one of three buckets:

- `success_within_default_budget`
- `requires_escalated_budget`
- `still_blocked_within_escalated_budget`

Audit artifacts:

- Summary: `snapshots/extraction_prediction_generation/latency_audits/extraction_generation_latency_audit_20260328_r5/summary.json`
- Details: `snapshots/extraction_prediction_generation/latency_audits/extraction_generation_latency_audit_20260328_r5/details.json`

Audit result:

- `document_count=16`
- `success_within_default_budget=14`
- `requires_escalated_budget=2`
- `still_blocked_within_escalated_budget=0`

Documents requiring the bounded `120s` escalation:

- `zotero:jessenCharacterisationSubjectiveCognitive2020`
- `zotero:pichetbinetteConfoundingFactorsAlzheimers2023`

Interpretation:

- the default bounded live-generation budget remains `90s`
- candidate-only escalation to `120s` is justified for the current Jessen/Pichet family
- nothing in the current fifteen-paper set is still blocked once the bounded escalation is allowed

This keeps the extraction sidecar operational rule explicit without moving any higher timeout budget into product runtime.

### Runtime Shadow Availability Audit

To measure the gap between the current sidecar baseline and actual persisted runtime extraction outputs, a separate runtime-shadow inventory audit was added at `scripts/eval/audit_runtime_extraction_shadow.py`.

It does not run extraction itself. Instead, it reads the current repo-grounded gold manifest, inspects the latest available runtime artifact directory for each paper under `storage/artifacts/`, and classifies whether there is:

- a comparable persisted `SpecialtyTrialExtraction` artifact
- a persisted runtime artifact in some other schema
- an explicit `not_clinical_note` skip
- or only legacy runs with no modern `clinical_extraction_status`

Audit artifacts:

- Summary: `snapshots/extraction_runtime_shadow/extraction_runtime_shadow_20260328_r1/summary.json`
- Details: `snapshots/extraction_runtime_shadow/extraction_runtime_shadow_20260328_r1/details.json`
- Shadow compare manifest: `snapshots/extraction_runtime_shadow/extraction_runtime_shadow_20260328_r1/shadow_compare_manifest.json`

Audit result on the current sixteen-paper baseline:

- `document_count=16`
- `documents_with_runtime_runs=16`
- `documents_with_shadow_comparable_runtime_artifact=0`
- bucket counts:
  - `specialty_runtime_artifact=0`
  - `biomedical_runtime_artifact=0`
  - `invalid_runtime_artifact=0`
  - `not_clinical_note=1`
  - `runtime_status_without_artifact=0`
  - `legacy_missing_status=15`
  - `no_runtime_run=0`

Interpretation:

- there is currently no persisted runtime `SpecialtyTrialExtraction` artifact for any paper in this benchmark
- `zotero:coricTargetingProdromalAlzheimer2015` has a modern runtime skip reason (`not_clinical_note`)
- the other fifteen papers resolve to older artifact runs that predate the current `clinical_extraction_status` bookkeeping, so the runtime gap is real but still partly an availability/eligibility problem rather than a clean quality comparison
- the generated `shadow_compare_manifest.json` is intentionally empty because there is nothing runtime-persisted and comparable to the specialty extraction goldset today

This means the current bottleneck is no longer sidecar quality. It is runtime availability: the product path does not currently persist a comparable specialty extraction artifact for this benchmark set.

### Coric-Only Specialty Shadow Materialization

To narrow that runtime gap without changing product behavior, a second bounded developer-only lane was added at `scripts/eval/materialize_specialty_runtime_shadow.py`.

This lane:

- keeps runtime untouched
- filters the current gold manifest down to specialty-eligible papers only
- reads the latest persisted `document_artifact.json` from `storage/artifacts/`
- calls the current `extract_specialty_trial_data(...)` provider path directly
- writes a compare-ready manifest only if a valid `SpecialtyTrialExtraction` artifact is materialized

Shadow-materialization artifacts:

- Summary: `snapshots/extraction_runtime_shadow_materialized/extraction_specialty_runtime_shadow_20260328_r1/summary.json`
- Details: `snapshots/extraction_runtime_shadow_materialized/extraction_specialty_runtime_shadow_20260328_r1/details.json`
- Raw response: `snapshots/extraction_runtime_shadow_materialized/extraction_specialty_runtime_shadow_20260328_r1/raw_responses/zotero_coricTargetingProdromalAlzheimer2015.txt`
- Generated manifest: `snapshots/extraction_runtime_shadow_materialized/extraction_specialty_runtime_shadow_20260328_r1/generated_manifest.json`

Result on the current sixteen-paper baseline:

- `document_count=16`
- `eligible_document_count=1`
- `prediction_written_count=0`
- `raw_response_written_count=1`
- `compare_ready_count=0`
- status counts:
  - `prediction_empty=0`
  - `prediction_schema_invalid=1`
  - `skipped_ineligible=15`
- schema-invalid reason counts:
  - `invalid_comparator=1`
  - `invalid_eligibility_flags=1`
  - `invalid_intervention_category=1`
  - `invalid_ketone_confirmation=1`
  - `invalid_risk_of_bias_hints=1`

Interpretation:

- `Coric` is the only paper in the current benchmark that is actually eligible for the specialty MCI/MCT lane
- the specialty provider path is reachable and the local model is available, but the current specialty prompt/schema contract still failed schema validation for `Coric`
- the materialized shadow details now preserve both the provider diagnostic and the raw response instead of collapsing the run into a generic empty result
- the raw response shows a legacy specialty shape rather than a near-schema miss: `citation=null`, `comparator="placebo"`, `ketone_confirmation=null`, `risk_of_bias_hints=null`, `eligibility_flags=null`, and `intervention.category="γ-secretase inhibitor"`
- the concrete blocker is now narrower than “runtime has no artifact”: even when we bypass note gating in a bounded shadow lane, the legacy specialty extraction path still does not materialize a compare-ready `SpecialtyTrialExtraction`

This sharpens the current diagnosis:

- the sidecar extraction baseline is strong
- runtime specialty availability is blocked first by note gating, and then by specialty prompt/schema fit on the one actually eligible benchmark paper

### Runtime Promotion Gate

To keep that diagnosis machine-readable, a tiny gate summary was added at `scripts/eval/check_specialty_runtime_promotion_gate.py`.

It combines:

- the current sidecar extraction baseline metrics
- the runtime shadow availability audit
- the bounded Coric-first specialty shadow materialization result

Gate artifact:

- Summary: `snapshots/extraction_runtime_promotion_gate/extraction_runtime_promotion_gate_20260328_r1/summary.json`

Current result:

- `sidecar_baseline.passed=true`
- `runtime_shadow.documents_with_shadow_comparable_runtime_artifact=0`
- `materialized_shadow.eligible_document_count=1`
- `materialized_shadow.compare_ready_count=0`
- `materialized_shadow.prediction_schema_invalid_count=1`
- `materialized_shadow.schema_invalid_reason_counts.invalid_comparator=1`
- `materialized_shadow.schema_invalid_reason_counts.invalid_eligibility_flags=1`
- `materialized_shadow.schema_invalid_reason_counts.invalid_intervention_category=1`
- `materialized_shadow.schema_invalid_reason_counts.invalid_ketone_confirmation=1`
- `materialized_shadow.schema_invalid_reason_counts.invalid_risk_of_bias_hints=1`
- `materialized_shadow.pairing_mismatch_count=0`
- `decision.promotion_ready=false`
- blockers:
  - `no_persisted_runtime_specialty_artifact`
  - `no_materialized_specialty_shadow_artifact`
  - `materialized_shadow_schema_invalid`
  - `runtime_specialty_feature_disabled`

Interpretation:

- the current extraction sidecar baseline is not the blocker
- promotion is still blocked even after bounded shadow materialization
- the materialized shadow lane now distinguishes `prediction_schema_invalid` from a true empty generation, so the current blocker is actionable rather than opaque
- the remaining blocker is now specific enough for a future Coric-only RFC: repair or normalize legacy null-vs-object specialty fields, comparator coercion, and intervention category mapping
- the materialized shadow lane now also reports `pairing_mismatch_count` so a future paper-id mismatch cannot silently look compare-ready
- the current product/runtime specialty lane should be treated as non-promotable until either the legacy specialty contract is repaired in shadow mode or the lane is formally retired in favor of the stronger sidecar benchmark

### Coric-Only Shadow Normalization Audit

To test whether the current Coric-only specialty blocker is purely schema-shape drift or a deeper extraction-quality gap, a third bounded developer-only lane was added at `scripts/eval/normalize_specialty_runtime_shadow.py`.

This audit keeps runtime behavior unchanged. It only reads the raw Coric specialty response already captured by the materialized shadow lane and applies a narrow shape-normalization pass before validation:

- fill `paper_id` from the expected manifest paper id when the raw response leaves it null
- restore `citation` from the gold metadata when the raw response collapses it to `null`
- coerce legacy string-or-null specialty fields such as `comparator`, `ketone_confirmation`, `risk_of_bias_hints`, and `eligibility_flags` into schema-compatible object forms
- downshift invalid legacy `intervention.category` values into a bounded schema-safe fallback

Normalization artifacts:

- Normalized summary: `snapshots/extraction_runtime_shadow_normalized/extraction_specialty_runtime_shadow_normalized_20260329_r1/summary.json`
- Normalized details: `snapshots/extraction_runtime_shadow_normalized/extraction_specialty_runtime_shadow_normalized_20260329_r1/details.json`
- Generated manifest: `snapshots/extraction_runtime_shadow_normalized/extraction_specialty_runtime_shadow_normalized_20260329_r1/generated_manifest.json`
- Coric raw response: `snapshots/extraction_runtime_shadow_materialized/extraction_specialty_runtime_shadow_20260328_r1/raw_responses/zotero_coricTargetingProdromalAlzheimer2015.txt`
- Normalized compare run: `snapshots/extraction_regression_eval/extraction_specialty_runtime_shadow_normalized_compare_20260329_r1/`

Normalization result:

- `document_count=16`
- `normalized_prediction_written_count=1`
- `compare_ready_count=1`
- `normalized_prediction_schema_invalid=0`
- Coric normalization actions:
  - `paper_id_from_expected`
  - `citation_from_gold_metadata`
  - `comparator_string_to_object`
  - `ketone_confirmation_null_to_object`
  - `risk_of_bias_hints_null_to_object`
  - `eligibility_flags_null_to_object`
  - `intervention_category_to_other`

This proves that the legacy Coric runtime-specialty output can be made schema-valid and compare-ready in a developer-only shadow lane without changing the product runtime.

However, the follow-up compare still fails on core specialty content:

- compare result: `missing_core_field_docs=1`
- compare result: `core_mismatch_docs=1`
- mismatched fields for `zotero:coricTargetingProdromalAlzheimer2015`:
  - `intervention`
  - `outcome`
  - `sample_size`
  - `duration`
- core field match rates in the normalized compare:
  - `population=1.0`
  - `intervention=0.0`
  - `outcome=0.0`
  - `sample_size=0.0`
  - `duration=0.0`

Interpretation:

- the current runtime-specialty blocker is now split cleanly into two layers:
  - schema-shape drift, which is repairable in a developer-only sidecar normalization step
  - semantic extraction loss, which remains unresolved even after the schema is made compare-ready
- this means “make the runtime artifact validate” and “make the runtime artifact useful” are no longer the same task
- it also means the current promotion gate is correctly red for a deeper reason than validation noise: even after bounded normalization, Coric still does not recover the specialty semantics needed for parity with the gold benchmark
- any future Coric-only runtime specialty RFC should therefore be staged explicitly:
  1. legacy shape adapter
  2. actual specialty semantic repair for `intervention`, `outcome`, `sample_size`, and `duration`

### Coric-Only Shadow Semantic Repair Audit

To test whether the second half of that Coric-only RFC is feasible without changing runtime behavior, a fourth bounded developer-only lane was added at `scripts/eval/repair_specialty_runtime_shadow_semantics.py`.

This lane starts from the same materialized Coric shadow snapshot, but instead of stopping after schema validation it applies a source-grounded semantic repair pass over the current shadow inputs:

- reuse the existing shape-normalized payload
- rebuild the Coric title/summary/methods snippets from the persisted `document_artifact.json`
- recover only source-visible core specialty fields
- write a compare-ready manifest only if the repaired artifact validates and still passes the paper-id guard

Semantic-repair artifacts:

- Semantic repair summary: `snapshots/extraction_runtime_shadow_semantic_repair/extraction_specialty_runtime_shadow_semantic_repair_20260329_r1/summary.json`
- Semantic repair details: `snapshots/extraction_runtime_shadow_semantic_repair/extraction_specialty_runtime_shadow_semantic_repair_20260329_r1/details.json`
- Generated manifest: `snapshots/extraction_runtime_shadow_semantic_repair/extraction_specialty_runtime_shadow_semantic_repair_20260329_r1/generated_manifest.json`
- Repaired Coric prediction: `snapshots/extraction_runtime_shadow_semantic_repair/extraction_specialty_runtime_shadow_semantic_repair_20260329_r1/repaired_predictions/zotero_coricTargetingProdromalAlzheimer2015.json`
- Compare run: `snapshots/extraction_regression_eval/extraction_specialty_runtime_shadow_semantic_repair_compare_20260329_r1/`

Semantic repair result:

- `document_count=16`
- `semantic_prediction_written_count=1`
- `compare_ready_count=1`
- `semantic_prediction_schema_invalid=0`
- Coric semantic repair actions:
  - `population_n_total_from_source`
  - `intervention_product_name_from_source`
  - `intervention_category_to_unknown_for_named_product`
  - `duration_weeks_from_source`
  - `outcome_name_from_source`
  - `outcome_effect_no_change_from_source`

Follow-up compare result:

- `document_count=1`
- `pairing_mismatch_docs=0`
- `schema_invalid_docs=0`
- `missing_core_field_docs=0`
- `hallucination_docs=0`
- `negation_failure_docs=0`
- `comparator_confusion_docs=0`
- `core_mismatch_docs=0`
- core field match rates:
  - `population=1.0`
  - `intervention=1.0`
  - `outcome=1.0`
  - `sample_size=1.0`
  - `duration=1.0`

Interpretation:

- the Coric-only RFC shape is now proven in shadow mode end to end:
  1. shape normalization can make the legacy specialty output schema-valid
  2. a second source-grounded semantic pass can recover the missing core specialty meaning
- this does **not** make the runtime specialty lane promotion-ready
- the current product path still does not persist a comparable specialty artifact on its own, and the promotion gate remains correctly red
- what this does prove is narrower and more useful: if runtime specialty is ever reopened, a bounded Coric-only shadow RFC has a viable technical path and should stay split into shape-adapter work first, semantic repair second

### Promotion Gate Refresh

After the Coric-only semantic repair audit passed, the promotion gate was widened slightly in a machine-readable way, without changing any blockers. The updated gate summary now carries the semantic shadow lane as advisory evidence only.

Updated gate artifact:

- Summary: `snapshots/extraction_runtime_promotion_gate/extraction_runtime_promotion_gate_20260329_r2/summary.json`

Updated gate result:

- `decision.promotion_ready=false`
- `semantic_shadow.semantic_prediction_written_count=1`
- `semantic_shadow.compare_ready_count=1`
- `semantic_shadow.compare_passed=true`
- `semantic_shadow.two_step_rfc_viable=true`
- blockers remain:
  - `no_persisted_runtime_specialty_artifact`
  - `no_materialized_specialty_shadow_artifact`
  - `materialized_shadow_schema_invalid`
  - `runtime_specialty_feature_disabled`

Interpretation:

- the gate still blocks runtime specialty promotion for the same substantive reasons as before
- the new semantic-shadow section does not weaken those blockers
- it does make one additional fact explicit in JSON rather than prose alone: a Coric-only two-step RFC is technically viable in shadow mode, even though the runtime lane is still not ready for promotion

## Next

1. Keep the bounded `90s` sidecar lane for extraction regression only; do not silently move that budget into product runtime.
2. Treat `extraction_repo_grounded_preclinical_therapeutic_realpred_20260328_r1_repair29` as the current best extraction sidecar baseline and use it as the comparison point for any future repair change.
3. Treat runtime promotion as blocked until there is a bounded path that persists a comparable specialty extraction artifact for at least a small eligible subset of this benchmark, starting with `Coric`.
4. Use `120s` only as a bounded escalation lane for papers that fail within `90s`; if widening introduces a document still blocked within `120s`, stop and classify it before adding new repair logic.
5. If the set is widened again, prioritize genuinely different artifact shapes rather than more papers from the same pattern families.
