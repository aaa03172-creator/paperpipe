# Evidence Grounding Performance Roadmap

Status: Development planning note
Date: 2026-05-22
Owner: Runtime/quality maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/Evidence_and_Uncertainty_Rules.md`

Related implementation anchors:
- `docs/teacher_quality_loop.md`
- `docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md`
- `evals/paper_skill_gym/README.md`
- `src/services/reader_eval_sidecar.py`
- `src/services/claimset_coverage_sidecar.py`
- `src/services/evidence_extraction_sidecar.py`
- `backend/routers/feedback.py`
- `backend/services/job_runner.py`
- `goldset/`

## Purpose

PaperPipe's core performance should be measured by how accurately it stores paper claims in verifiable context, not by how fluent its summaries sound.

The target capability is:

1. read PDF/source material reliably
2. extract the paper's important claims without inventing unsupported claims
3. link each claim to concrete evidence
4. separate method, result, limitation, gap, and contextual notes
5. preserve the state so search, comparison, figures, talks, notes, and handoff artifacts can reuse it

This note separates what already exists from what still needs to be built. It is not a new runtime contract by itself. Schema, API, and persisted artifact changes still need their own bounded implementation PRs and tests.

## Product Performance Thesis

PaperPipe performance comes from storing claims and evidence as a verifiable structured state.

The main score is not "summary quality." The main score is whether the system can say:

- what the paper actually claims
- where each claim is supported
- whether the locator is precise enough to review
- whether the statement overstates the evidence
- whether limitations and negative/uncertain results remain visible
- whether downstream artifacts can trace back to the structured state and source evidence

## Current Layer Classification

Use the existing repository layer taxonomy when implementing this roadmap.

| Item | Layer | Canonical posture |
| --- | --- | --- |
| PDF, Zotero metadata, source excerpts | raw source | preserved as source owner input |
| `DocumentArtifact`, chunks, `ClaimSet`, resolved claimset | run-local structured artifact; canonical only after the owning paper-state projection/promotion path adopts it | primary reviewable evidence state for the run, not automatically a stronger truth owner |
| `reader_eval.json`, `claimset_coverage.json`, teacher review evals | review/gate artifact | additive checks, not replacement truth |
| `goldset/accepted`, deterministic splits | eval/reference artifact | fixed comparison baseline, not runtime paper truth |
| feedback logs and feedback index | raw memory / improvement data | support future runs, not stronger than evidence state |
| paper synthesis, meeting pack, chart pack, Obsidian exports | compiled/user-facing artifact | derived from upstream state and lineage |

## Already Done

### 1. Canonical claim/evidence contract exists

`docs/Lattice_v3_Master_Spec.md` already defines `ClaimSet` and `EvidenceSpan` as the reader output contract.

Existing intended behavior:

- claims carry evidence spans
- limitations, heterogeneity, and gaps also require evidence
- evidence can be a `chunk_id` or page/character locator
- evidence includes a rationale
- claims without evidence are downgraded to low confidence or "unverifiable"

### 2. Evidence and uncertainty policy exists

`docs/Evidence_and_Uncertainty_Rules.md` already makes the core rule explicit:

- promoted scientific claims must be evidence-linked
- missing support and missing location must remain visible
- failed or ambiguous grounding must not be hidden
- presentation modes cannot loosen truth policy
- compiled knowledge remains derivative

### 3. Reader evaluation sidecar exists

`src/services/reader_eval_sidecar.py` already computes claim-level reader quality signals, including:

- supported / unsupported / unknown claim counts
- missing evidence and missing location reasons
- evidence span counts
- grounded, unresolved, ambiguous, and failed grounding span counts
- bbox/text-match/approx evidence source counts
- grounded limitation counts
- statement/evidence token overlap warnings

This is already close to a grounding-quality signal, but it is not yet promoted into a single product scorecard.

### 4. Claimset coverage sidecar exists

`src/services/claimset_coverage_sidecar.py` already computes coverage and review signals, including:

- claim count
- evidence span count
- grounded evidence ratio
- page coverage ratio
- missing/undercovered page ranges
- unique section count
- duplicate claim warnings
- missing topic signal count

The deepread worker attempts to write this artifact during job execution and records success/failure in run metadata. Downstream logic must treat a missing sidecar as an explicit warning, not as a clean zero.

### 5. Evidence extraction sidecar exists

`src/services/evidence_extraction_sidecar.py` and `src/schemas/evidence_extraction.py` already provide an evidence extraction bundle with:

- claim, clinical field, entity, and relation records
- evidence-backed / artifact-backed / derived status
- locators for page, chunk, span, section, table, cell, and bbox
- grounded evidence ref counts

This gives a reusable structure for extraction-quality reporting.

### 6. Gold set and teacher quality loop exist

`goldset/` already contains accepted records, deterministic splits, extraction regression sets, and repo-grounded eval fixtures.

`docs/teacher_quality_loop.md` already defines:

- candidate extraction
- local-first teacher output generation
- verification and accepted/quarantine routing
- human quarantine review
- deterministic train/eval split
- quality eval
- baseline compare and optional promotion

Scripts already exist for:

- `scripts/extract_teacher_candidates.py`
- `scripts/generate_teacher_outputs.py`
- `scripts/verify_teacher_output.py`
- `scripts/review_teacher_quarantine.py`
- `scripts/build_goldset.py`
- `scripts/eval/run_eval.py`
- `scripts/eval/compare_eval.py`

### 7. Human feedback and dynamic few-shot injection exist

`backend/routers/feedback.py` already stores `FeedbackCase` records and indexes accepted feedback.

`src/agents/feedback_retriever.py` already keeps a local-first feedback index.

`backend/services/job_runner.py` already injects top-3 similar feedback examples into future deepread runs when available.

### 8. Paper Skill Gym exists as eval-only probe harness

`evals/paper_skill_gym/` already has deterministic probes for:

- figure grounding
- table interpretation
- claim/evidence separation
- method reconstruction
- limitation detection
- reproducibility
- citation/page grounding
- unsupported/unknown logging

This is a useful guardrail for prompt/skill changes, but it is explicitly eval-only and not a runtime skill.

### 9. Visual and figure/table evidence work exists

The repo already contains visual evidence and image evidence contracts, including `docs/VISUAL_EVIDENCE_LEDGER_CONTRACT.md`, `docs/IMAGE_EVIDENCE.md`, and related services/tests.

These are relevant for future figure/table grounding metrics.

## Main Gaps

### Gap 1. No single Evidence Grounding Scorecard

The repository has the needed raw signals, but they are spread across sidecars, eval scripts, goldset folders, and job metadata.

Missing:

- one report that summarizes core quality for a run, batch, model, prompt, or parser
- stable metric names for product-level comparison
- threshold policy for pass/warn/fail
- baseline comparison output focused on evidence grounding

### Gap 2. Gold set is broad but not yet normalized around claim/evidence KPI

There are accepted records and multiple repo-grounded eval sets, but the central paper-understanding gold schema should be made explicit.

Missing:

- normalized gold claim shape
- normalized gold evidence locator shape
- explicit method/result/limitation/gap labels
- figure/table references as first-class gold evidence locators
- per-paper domain tags and paper type
- clear split between seed, train, eval, and holdout sets

### Gap 3. Failure taxonomy is not unified at product level

Failure codes exist in several lanes, but the core paper-understanding taxonomy should be standardized.

Target product-level failure codes:

- `MISSING_CLAIM`
- `UNSUPPORTED_CLAIM`
- `WRONG_EVIDENCE`
- `WEAK_OR_AMBIGUOUS_EVIDENCE`
- `WRONG_LOCATOR`
- `OVERSTATED_RESULT`
- `CONTRADICTED_RESULT`
- `METHOD_AS_RESULT`
- `RESULT_AS_METHOD`
- `LIMITATION_MISSED`
- `GAP_MISSED`
- `TABLE_PARSE_FAILED`
- `FIGURE_CAPTION_MISLINKED`
- `FIGURE_TABLE_CONFLICT_MISSED`
- `DOI_MISMATCH`
- `METADATA_MISMATCH`

### Gap 4. Claim/evidence correction logging is too loose

The existing feedback path captures corrections, but not enough structured fields for systematic claim/evidence learning.

Missing:

- previous claim text
- corrected claim text
- previous evidence refs
- corrected evidence refs
- correction reason code
- parser version
- LLM provider/model/version
- prompt or reader profile version
- user/reviewer identity
- timestamp
- whether the correction should become training/eval material

### Gap 5. LLM roles are conceptually clear but not scored independently

Extractor, Classifier, Grounding Checker, Consistency Checker, and Formatter should be evaluated separately where possible.

Missing:

- stage-level metrics
- stage-level artifacts
- stage-level failure routing
- ability to compare one model only as a grounding checker without changing the extractor

### Gap 6. Figure/table grounding is not yet a first-class product KPI

Figure captions, visual evidence, and image evidence lanes exist, but the main scorecard should include figure/table support quality.

Missing:

- figure/table locator precision
- caption-to-claim link accuracy
- table cell locator accuracy
- figure/table conflict detection
- parser failure attribution for figure/table extraction

## Target Metrics

Metrics must be split into two families:

- `runtime_proxy_metrics`: computed from existing artifacts without human/gold labels. These are useful readiness and regression signals, but they are not true precision/recall.
- `gold_scored_metrics`: computed only when gold or human-reviewed labels are available. These are the metrics that may be used for model/prompt/parser comparison and promotion decisions.

Do not report a gold-scored metric as `0` when gold labels are missing. Use `not_available` plus a warning so the scorecard does not turn missing labels into fake quality evidence.

### P0 Metrics

These should become the first scorecard metrics.

| Metric | Meaning | Direction |
| --- | --- | --- |
| `claim_precision` | extracted claims that are actually supported by the paper | higher is better |
| `evidence_support_precision` | evidence refs that genuinely support their claim | higher is better |
| `locator_precision` | evidence locators that point to the right page/chunk/span/figure/table | higher is better |
| `unsupported_claim_rate` | claims promoted without sufficient support | lower is better |
| `overstatement_rate` | claims stronger than the evidence permits | lower is better |
| `limitation_recall` | gold limitations found by the system | higher is better |
| `method_result_confusion_rate` | methods/results mislabeled across the boundary | lower is better |

Gold labels or structured human review are required for all P0 precision/recall/confusion metrics above. Without gold labels, the scorecard may expose related proxy signals such as unresolved span count, low statement/evidence overlap count, missing location count, and unsupported/unknown claim count.

### P1 Metrics

| Metric | Meaning | Direction |
| --- | --- | --- |
| `claim_recall` | gold core claims recovered | higher is better |
| `gap_recall` | gold gaps/future work recovered | higher is better |
| `contradiction_rate` | claims that conflict with reviewer-marked contradiction labels | lower is better |
| `figure_reference_precision` | figure refs linked to the right claim/evidence | higher is better |
| `table_reference_precision` | table refs linked to the right claim/evidence | higher is better |
| `metadata_match_rate` | DOI/PMID/title/author/year matching accuracy | higher is better |
| `parser_section_accuracy` | methods/results/figures/tables extracted into correct sections | higher is better |

### P2 Metrics

| Metric | Meaning | Direction |
| --- | --- | --- |
| `downstream_traceability_rate` | generated artifacts can trace statements back to canonical state | higher is better |
| `correction_reuse_gain` | accepted feedback improves later evals | higher is better |
| `review_burden_per_paper` | human corrections needed per paper | lower is better |
| `time_to_reviewable_state` | time until useful, evidence-linked paper card exists | lower is better |

## Development Tasks

### Task 1. Create Evidence Grounding Scorecard schema

Goal:

Define a stable scorecard that aggregates existing sidecar and goldset signals into one report.

Suggested files:

- `src/schemas/evidence_grounding_scorecard.py`
- `src/services/evidence_grounding_scorecard.py`
- `tests/test_evidence_grounding_scorecard.py`

Inputs:

- `reader_eval.json`
- `claimset_coverage.json`
- `evidence_extraction_bundle.json`
- gold claim/evidence annotations when available
- run metadata

Output:

- `evidence_grounding_scorecard.json`

Acceptance criteria:

- scorecard has explicit `layer="review_gate_artifact"` and `canonical_status="non_canonical"`
- scorecard can be built from an existing run directory without rerunning deepread
- scorecard separates `runtime_proxy_metrics` from `gold_scored_metrics`
- scorecard reports available proxy metrics when optional gold inputs are missing
- gold-scored precision/recall metrics are `not_available` when gold labels are missing
- missing inputs are warnings, not silent zeros
- tests cover full input, partial input, and malformed input cases

Implementation note:

- The FastAPI scorecard build endpoint is covered for both explicit `out` writes and its default additive write to `evidence_grounding_scorecard.json` inside the run directory. The default-output path preserves source sidecar contents, `layer="review_gate_artifact"`, `canonical_status="non_canonical"`, runtime proxy input-health metrics, and core input diagnostics while leaving gold-scored metrics `not_available` when no gold labels are attached.
- The PR1 scorecard build endpoint is owned by the scorecard-only FastAPI router `backend.routers.evidence_grounding_scorecards`, and the full app exposes exactly one `POST /evidence-grounding/scorecards/build` route from that module. This keeps the additive scorecard API separate from later benchmark, threshold, and roadmap-completion API surfaces.
- The operator CLI uses the same default-output posture: without `--out`, it writes only the run-directory `evidence_grounding_scorecard.json` additive artifact and leaves the loaded deepread sidecars unchanged.
- Explicit API/CLI scorecard output paths are now guarded so `out` cannot target existing run-directory source artifacts such as `reader_eval.json`, create nested run-directory artifacts, point at directories, or create arbitrary top-level run-directory files such as `scorecard-copy.json`. Inside a source run directory, the only allowed scorecard output is the top-level `evidence_grounding_scorecard.json`; external explicit file outputs remain allowed.
- Malformed core sidecars stay diagnostic at the FastAPI and CLI default-output boundaries: the original malformed file is left unchanged, the bad sidecar is not counted as a source artifact, input diagnostics carry `status="load_failed"`, and input-health metrics report both missing and malformed core input counts.
- The downstream traceability proxy excludes `evidence_grounding_scorecard.json` from acceptance-contract expected-output counting. This prevents a previous or in-progress scorecard output from inflating the traceability proxy for the scorecard currently being built.
- If no non-scorecard expected outputs remain after that exclusion, downstream traceability is reported as `not_available` rather than as a misleading `0.0` failure signal.
- Scorecard builds now fail closed when `run_dir` itself is not an existing directory, and the default writer helper also requires an existing artifact directory. This preserves the "build from existing deepread artifacts" boundary and prevents the service, FastAPI default-output path, CLI default-output path, or direct writer helper from creating a new run directory with a scorecard that has no source run artifacts.
- Run-directory scorecard rebuilds now also require at least one loadable core scorecard sidecar (`reader_eval.json`, `claimset_coverage.json`, `evidence_extraction_bundle.json`, or `visual_evidence_ledger.json`). Partial runs with any loaded core sidecar still produce warning-rich scorecards, but empty run directories fail before any scorecard output is written.
- The lower-level scorecard builder enforces the same loaded-core-input invariant from actual core sidecar objects, not caller-supplied diagnostics alone, so direct service callers cannot bypass the "build from existing deepread artifacts" boundary by constructing a no-source scorecard with only paper/run identifiers or spoofed loaded diagnostics.
- When caller-supplied input diagnostics disagree with actual loaded core sidecar objects, the builder reconciles the four core diagnostics from the actual objects while preserving non-core diagnostics and malformed `load_failed` evidence. This keeps input-health metrics aligned with real loaded deepread artifacts rather than stale or misleading diagnostic payloads.
- Contract compatibility now rejects stale raw scorecards whose loaded core input diagnostics are not backed by matching core filenames in `source_artifacts`, so an externally reviewed scorecard cannot claim it loaded a deepread sidecar without carrying the corresponding source-artifact trace.
- The FastAPI scorecard build endpoint now reports fail-closed operator input errors such as missing run directories, invalid external gold files, and protected source-artifact output paths as `400` client errors instead of `500` server failures, while still preserving the no-partial-write guarantees.
- The standalone scorecard CLI now reports the same fail-closed operator input errors as a concise one-line `[evidence_grounding_scorecard] error=...` stderr message with exit code `2`, avoiding traceback-style output for user-correctable build inputs while preserving the no-partial-write guarantees.
- Scorecard API and CLI operator-facing messages preserve actionable filenames while masking local absolute filesystem prefixes, so build success output and input-error messages do not leak personal workspace or temporary paths.
- The scorecard build route also masks local absolute path prefixes before writing warning/error log messages, keeping API responses and backend logs aligned with the local-path privacy posture.
- When the FastAPI scorecard build response includes external source artifacts, the response copy masks local absolute path prefixes while the persisted scorecard JSON keeps the real source paths for non-canonical lineage review.
- Invalid external `paper_understanding_gold` inputs fail before the API or CLI writes the scorecard output, so malformed eval-only gold files cannot leave partial additive artifacts beside otherwise unchanged deepread sidecars.
- The scorecard schema family is strict about unknown fields across the artifact, nested metric/summary models, candidate configuration, and build request, so contract drift is rejected instead of silently ignored. The FastAPI build endpoint rejects unknown request fields and nested candidate-config fields before any scorecard output is written. The CLI also rejects external candidate-config JSON files with unknown fields before writing an output. Contract compatibility rejects standalone scorecards that contain extra fields such as canonical shadow state.
- Run-local optional `candidate_config.json` sidecars keep the additive posture across the service and FastAPI build endpoint: malformed sidecars are reported as non-core `load_failed` input diagnostics and warnings, are not added to `source_artifacts`, do not mutate source sidecars, and do not block scorecard construction from the remaining deepread artifacts. When the FastAPI request supplies an explicit `candidate_config`, that request-level config overrides any run-local sidecar and the optional sidecar is not loaded, warned on, or reported as source evidence.
- Scorecard artifact identity fields (`paper_id`, `doc_id`, `run_id`) and `recommended_next_action` are normalized and required to be non-empty, so malformed scorecards cannot pass validation without a usable paper/run identity or operator next step.

### Task 2. Normalize paper-understanding gold schema

Goal:

Make the central goldset shape explicit for claim/evidence/method/result/limitation evaluation.

Suggested files:

- `src/schemas/paper_understanding_gold.py`
- `scripts/eval/validate_paper_understanding_gold.py`
- `tests/test_paper_understanding_gold_schema.py`

Core fields:

- `paper_id`
- `doi`, `pmid`, `title`, `authors`, `year`
- `paper_type`
- `domain_tags`
- `gold_claims[]`
- `gold_methods[]`
- `gold_results[]`
- `gold_limitations[]`
- `gold_gaps[]`
- `important_figures[]`
- `important_tables[]`

Gold evidence locator fields:

- `page`
- `chunk_id`
- `char_start`, `char_end`
- `quote`
- `section`
- `figure_id`
- `table_id`
- `cell_id`
- `bbox_pdf`
- `bbox_pct`

Acceptance criteria:

- existing `goldset/accepted` records can be audited or mapped into the new shape without deleting the old format
- validator catches missing evidence for gold claims
- validator catches unsupported figure/table refs
- schema explicitly distinguishes method/result/limitation/gap

### Task 3. Add product-level failure taxonomy

Goal:

Unify paper-understanding failure codes across scorecards, correction logs, and review queues.

Suggested files:

- `src/schemas/paper_understanding_failures.py`
- update relevant scorecard/correction schemas to use the enum
- `tests/test_paper_understanding_failures.py`

Acceptance criteria:

- failure enum includes the P0/P1 codes listed in this document
- each code has a short definition and smallest-fix direction
- scorecard output can count failures by code
- correction logs can attach one or more failure codes
- no existing lane-specific failure codes are deleted without a migration plan

### Task 4. Add Claim/Evidence CorrectionCase

Goal:

Capture human corrections in a structured form suitable for prompt improvement, model comparison, and future eval data.

Suggested files:

- `src/schemas/claim_evidence_correction.py`
- `backend/routers/claim_evidence_corrections.py`
- `src/services/claim_evidence_corrections.py`
- `tests/test_claim_evidence_corrections_api.py`

Fields:

- `correction_id`
- `paper_id`
- `run_id`
- `claim_id`
- `field_path`
- `before_claim_text`
- `after_claim_text`
- `before_evidence_refs`
- `after_evidence_refs`
- `reason_codes`
- `reviewer_id`
- `parser_version`
- `llm_provider`
- `llm_model`
- `prompt_version`
- `created_at`
- `accepted_for_eval`
- `metadata`

Acceptance criteria:

- route is FastAPI-first
- writes are append-only or guarded
- records do not become canonical claim truth automatically
- accepted corrections can be exported as eval candidates
- accepted structured corrections either extend the existing `/feedback` improvement path or explicitly link back to the `FeedbackCase`/feedback-index flow so correction memory and few-shot memory do not diverge
- tests cover create/list/filter and malformed correction payloads

### Task 5. Build batch model/prompt/parser comparison runner

Goal:

Run the same goldset through different parser/model/prompt configurations and compare the fixed metrics.

Suggested files:

- `scripts/eval/run_evidence_grounding_benchmark.py`
- `scripts/eval/compare_evidence_grounding_scorecards.py`
- `tests/test_evidence_grounding_benchmark.py`

Comparison dimensions:

- parser backend
- LLM provider/model
- prompt version
- grounding checker version
- resolver version

Acceptance criteria:

- same gold split can be replayed across candidates
- output includes per-paper and aggregate metrics
- comparison is deterministic for saved artifacts
- regressions in P0 metrics fail the comparison
- output gives concrete failure summaries by code

### Task 6. Separate stage-level evaluation

Goal:

Evaluate extractor, classifier, grounding checker, consistency checker, and formatter separately when artifacts permit it.

Suggested approach:

- keep stages as services or pipeline steps, not user-facing personas
- store stage outputs as run-local artifacts
- evaluate each stage against the same goldset where possible

Stage goals:

- Extractor: high candidate recall, low invention
- Classifier: method/result/limitation/gap boundary accuracy
- Grounding Checker: high support and locator precision
- Consistency Checker: catches overstatement, contradiction, missing limitation
- Formatter: preserves traceability into cards, notes, packs, and handoffs

Acceptance criteria:

- at least extractor/classifier/grounding metrics can be reported separately
- scorecard identifies which stage likely caused a failure
- downstream formatting cannot hide unsupported claims

### Task 7. Promote figure/table grounding into the main scorecard

Goal:

Make figure/table evidence quality visible alongside text evidence quality.

Inputs:

- document artifact figures/tables
- figure caption sidecar
- visual evidence ledger
- image evidence records
- claim/evidence locators

Acceptance criteria:

- scorecard reports figure/table reference precision when gold refs exist
- missing or ambiguous caption links are counted
- table cell locator failures are counted separately from text locator failures
- figure/table conflict failures are counted when detected

### Task 8. Add minimal UI/API visibility after backend metrics stabilize

Goal:

Expose grounding quality to the operator without turning the UI into a noisy audit console.

Prerequisite:

- scorecard schema and generation must exist first

Initial UI/API surface:

- paper/run scorecard summary
- unsupported claim count
- wrong or unresolved locator count
- limitation missing warning
- link to detailed review artifact

Acceptance criteria:

- UI uses existing PaperPipe/Lattice dark-first token system
- UX review artifacts are created before UI changes
- no unsupported claim is visually promoted as final truth
- frontend build and relevant Playwright coverage pass

## Suggested PR Sequence

### PR 1. Scorecard from existing artifacts

Scope:

- schema and service for `evidence_grounding_scorecard.json`
- build from existing `reader_eval.json` and `claimset_coverage.json`
- no new runtime generation path yet

Goal:

Create a single run-level grounding readiness/proxy summary without changing deepread behavior. This PR must not claim true precision/recall unless gold labels are provided.

Implementation note:

- Started on branch `codex/evidence-grounding-performance-roadmap`.
- Added `EvidenceGroundingScorecard` as an additive `review_gate_artifact`.
- Initial builder reads existing `reader_eval.json`, `claimset_coverage.json`, and `evidence_extraction_bundle.json` artifacts and keeps gold-scored metrics `not_available` unless labels are provided.
- Added run-level input completeness proxy metrics, `input_artifact_coverage_rate` and `missing_input_artifact_count`, so scorecard and benchmark outputs can distinguish weak evidence-grounding quality from an under-instrumented run where core sidecars are absent.
- Added the FastAPI endpoint `POST /evidence-grounding/scorecards/build` with a typed `EvidenceGroundingScorecardBuildRequest`. Operators can now rebuild an additive `evidence_grounding_scorecard.v1` from a saved run directory without rerunning deepread, optionally injecting an external `paper_understanding_gold.v1` file for eval-only gold-scored metrics instead of copying gold into the run directory.
- Added `scripts/eval/build_evidence_grounding_scorecard.py` as a thin operator CLI over the same scorecard service. It rebuilds a non-canonical scorecard from an existing deepread run directory, can attach an external eval-only gold file, and can record an explicit candidate-config JSON file as source evidence without introducing a new deepread runtime generation path.
- Gold-scored metrics now fail closed when `paper_understanding_gold.v1` belongs to a different paper. A mismatched `paper_id` records `paper_understanding_gold_paper_id_mismatch`, leaves gold metrics `not_available`, and fails scorecard readiness instead of scoring one paper against another paper's gold labels. Regression coverage now includes the direct service path, run-local `paper_understanding_gold.json`, and FastAPI external-gold build path.
- Reviewed claim/evidence eval fixtures are now scoped to the scorecard's `paper_id` and `run_id` before they can act as gold-like labels. Out-of-scope fixtures are skipped, recorded with `reviewed_eval_fixture_scope_mismatch`, and fail readiness so a mixed fixture package cannot inflate or corrupt run-level gold-scored metrics.
- Scorecard generation now detects identity mismatches across loaded input sidecars (`reader_eval.json`, `claimset_coverage.json`, `evidence_extraction_bundle.json`, and `visual_evidence_ledger.json`) and records explicit warnings plus reason codes instead of silently trusting the first available sidecar identity. Mismatched sidecar identities now force scorecard readiness to `fail`, so a mixed-paper or stale-run artifact set cannot pass just because its proxy metrics look clean.
- Runtime integration into deepread generation remains a later PR.

### PR 2. Gold schema validator

Scope:

- `paper_understanding_gold` schema
- validator script
- map or audit existing gold records

Goal:

Make the fixed comparison target explicit before comparing models. Gold-scored metrics become valid only after this contract exists and the selected gold split validates.

Implementation note:

- Added `PaperUnderstandingGold` schema with explicit claim/method/result/limitation/gap statement groups.
- Added evidence locator validation for page/chunk/span/figure/table/bbox signals.
- Added validator script at `scripts/eval/validate_paper_understanding_gold.py`.
- Current validator is additive and does not migrate or rewrite existing `goldset/accepted` records.
- Added `PaperUnderstandingGoldManifest` for fixed goldset bundles. A manifest declares `goldset_id`, `goldset_split`, and relative `gold_path` items, and the shared validation service checks each referenced gold file, duplicate paper IDs, and manifest/gold paper ID mismatches.
- Added `scripts/eval/build_paper_understanding_gold_manifest.py` to build a fixed split manifest from validated `paper_understanding_gold.v1` records. The generated manifest preserves relative paths from the manifest location and re-validates itself before returning success.
- Added paper-understanding gold readiness checks. Validation summaries and generated manifest item metadata now distinguish schema-valid records from eval-ready records using `readiness_status` and `readiness_reason_codes` for claim-count range, method/result/limitation presence, domain tags, paper type, important visuals, and DOI/PMID metadata.
- Added `--require-ready` gates to the gold validator and fixed-split manifest builder. This lets routine schema validation stay permissive while eval/benchmark bundle creation can fail on schema-valid but not-yet-ready gold records.
- Added FastAPI endpoints `POST /paper-understanding-gold/validate` and `POST /paper-understanding-gold/manifests/build`. The fixed-goldset validation and manifest build path is now API-first as well as CLI-accessible, with optional non-canonical JSON output for operator review.
- Added `PaperUnderstandingGoldCurationReport`, `scripts/eval/audit_paper_understanding_goldset_curation.py`, and the FastAPI endpoint `POST /paper-understanding-gold/curation/audit`. The audit checks ready-record coverage by fixed split, domain tag, and paper type against explicit targets such as `split=eval,domain=biomarker,min=10`, and writes or returns a non-canonical review artifact so goldset curation gaps are visible before running model comparisons.
- Added `PaperUnderstandingGoldReleaseReadinessReport`, `scripts/eval/audit_paper_understanding_gold_release_readiness.py`, and the FastAPI endpoint `POST /paper-understanding-gold/release-readiness/audit`. A seed/eval/holdout manifest bundle can now be checked as one non-canonical release candidate, including required split coverage, per-split ready counts, single `goldset_id` posture, invalid referenced gold records, and duplicate papers across splits.
- Added `scripts/eval/package_paper_understanding_gold_release_from_staged_gold.py` and the FastAPI endpoint `POST /paper-understanding-gold/release-readiness/package-from-staged-gold`. Reviewed staged gold manifests can now publish fixed seed/eval/holdout split manifests and immediately produce the non-canonical `paper_understanding_gold_release_readiness.v1` gate in one typed package, reducing hand-edited path wiring while preserving ready-only validation.
- Added `build_paper_understanding_gold_release_split_plan_from_staging_manifest()`, `scripts/eval/build_paper_understanding_gold_release_split_plan_from_staged_gold.py`, and the FastAPI endpoint `POST /paper-understanding-gold/release-readiness/split-plan-from-staged-gold`. A single ready staged-gold manifest can now be deterministically assigned into seed/eval/holdout split staging manifests and release-package build items. The generated `paper_understanding_gold_release_split_plan.v1` remains a non-canonical review artifact and does not promote any staged record into canonical truth.
- Added `build_paper_understanding_gold_release_package_from_split_plan()`, `scripts/eval/package_paper_understanding_gold_release_from_split_plan.py`, and the FastAPI endpoint `POST /paper-understanding-gold/release-readiness/package-from-split-plan`. Operators can now take the saved split-plan report and publish the fixed release package/readiness gate without copying `split_manifests` by hand, while still preserving ready-only validation and non-canonical review-artifact status.
- Added `scripts/eval/draft_paper_understanding_gold_from_reviewed_fixtures.py`, `src/services/paper_understanding_gold_drafts.py`, and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/from-reviewed-fixtures`. Approved reviewed claim/evidence fixtures can now be grouped into non-canonical `paper_understanding_gold_candidate_draft.v1` envelopes under `goldset/reviews/paper_understanding_gold_drafts/`, with readiness diagnostics preserved for human curation before accepted gold promotion.
- Added `scripts/eval/draft_paper_understanding_gold_from_teacher_verification.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/from-teacher-verification`. Accepted `teacher_verification.v1` files, including the existing `goldset/accepted` teacher outputs, can now be converted into non-canonical `paper_understanding_gold_candidate_draft.v1` envelopes. This carries forward grounded claim/evidence spans as a curation aid while leaving missing method/result/limitation/citation coverage visible through readiness diagnostics.
- Added `scripts/eval/package_paper_understanding_gold_teacher_verification_curation.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/from-teacher-verification/curation-package`. This one-step package writes non-canonical teacher-derived candidate drafts and a curation report together, making the current legacy accepted teacher outputs directly reviewable as fixed-gold candidates while still blocking promotion until readiness gaps are resolved.
- Added `scripts/eval/audit_paper_understanding_gold_candidate_drafts.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/curation/audit`. Candidate drafts can now be summarized into a non-canonical curation report with readiness status, blocker reason-code counts, statement/visual/table counts, concrete next actions per paper, and per-field curation tasks that name the target field, current count, minimum required count, instruction, and evidence hint. This keeps the fixed-goldset build queue reviewable before any draft is staged or promoted.
- Added `scripts/eval/patch_paper_understanding_gold_candidate_draft.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/patch`. A reviewer can now apply a structured curation patch to a candidate draft, replacing curated citation metadata, paper type, domain tags, statements, and visual/table inventory, then receive a non-canonical patch result with before/after readiness and the patched draft. This gives the curation task queue a typed path into the ready-only staging flow without making candidate drafts canonical truth.
- Added `scripts/eval/audit_paper_understanding_gold_candidate_draft_curation_progress.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/curation/progress`. The progress audit joins a teacher-verification curation package, optional patch-template manifests/templates, optional patch results, and optional staged gold files, then reports paper-level status as `not_started`, `templated`, `patched_not_ready`, `ready_to_stage`, or `staged` with remaining task counts. This makes fixed-goldset curation progress auditable before benchmark manifests are built, including the handoff point where reviewers have editable patch scaffolds but no accepted patch result yet.
- Added `scripts/eval/build_paper_understanding_gold_candidate_draft_patch_template.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/patch-template`. The template builder turns a candidate draft into a valid structured patch-request scaffold, prefilled with current draft values plus reviewer/output metadata and open readiness tasks, so human curators can edit the missing evidence-backed fields without hand-authoring the patch contract.
- Added `scripts/eval/build_paper_understanding_gold_candidate_draft_patch_templates.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/patch-templates/build`. This batch builder consumes a teacher-verification curation package and writes one non-canonical patch-template JSON file per candidate draft, plus a manifest that summarizes template count, open task count, and readiness status across the queue.
- Added `scripts/eval/apply_paper_understanding_gold_candidate_draft_patch_templates.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/patch-templates/apply`. This batch apply lane consumes edited patch-template files or a patch-template manifest, applies each embedded structured patch request, writes one non-canonical patch-result JSON per draft, and emits a patch-result manifest with readiness counts. It lets reviewers move a whole queue from edited templates into patch results without bypassing readiness checks or staging gates.
- Added `scripts/eval/export_paper_understanding_gold_curation_tasks.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/curation/tasks/export`. The export flattens current curation-progress `open_tasks` into a non-canonical `paper_understanding_gold_curation_task_export.v1` reviewer handoff artifact, with optional CSV output, so remaining fixed-gold work can be triaged by paper/reason/target field without treating tasks as canonical truth. Exported tasks now also carry `curation_stage` and `review_priority`, JSON/CSV exports are sorted by priority, and top-level `curation_stage_counts` / `review_priority_counts` summarize the remaining work so reviewers can see the curation backlog without scanning every item. The export, one-step reviewer handoff, reviewer-handoff apply, and reviewer-handoff stage CLIs also print those counts to stdout next to `open_task_count` or `remaining_task_count`, so backlog composition stays visible across the reviewer loop without opening JSON.
- Contract compatibility now verifies curation task export counts against the embedded task rows: open-task total and task breakdown maps must match row counts, while unique paper total and status counts must match the paper/status view represented by the rows. This keeps reviewer queue summaries from drifting away from the actual rows reviewers will edit.
- Added `scripts/eval/package_paper_understanding_gold_reviewer_handoff.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/from-teacher-verification/reviewer-handoff-package`. This one-step handoff writes teacher-derived candidate drafts, the curation package, patch-template manifest, progress report, task export JSON/CSV, and a Markdown reviewer guide into one non-canonical `paper_understanding_gold_reviewer_handoff_package.v1`, reducing reviewer setup work while keeping accepted fixed gold gated on human edits.
- Current local execution wrote the active reviewer handoff package to `goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json` and the reviewer guide to `goldset/reviews/paper_understanding_gold_reviewer_handoff/reviewer_guide.md`. The package contains 8 teacher-derived drafts, 8 editable patch templates, and 54 open curation tasks, with `curation_ready=false`. The open task distribution is: `CLAIM_COUNT_OUT_OF_RANGE=6`, `METHOD_MISSING=8`, `RESULT_MISSING=8`, `LIMITATION_MISSING=8`, `PAPER_TYPE_OTHER=8`, `IMPORTANT_VISUALS_MISSING=8`, and `EXTERNAL_ID_MISSING=8`. The regenerated task export and guide start with priority-10 metadata tasks for `EXTERNAL_ID_MISSING`, then proceed through paper type, claim count, method, result, limitation, and visual inventory; stage counts are `metadata=16`, `claim_set=6`, `method_context=8`, `result_context=8`, `limitation_context=8`, and `visual_inventory=8`. The guide also includes a `Tasks By Stage` section with every open task, instruction, evidence hint, and patch-template path grouped by `claim_set`, `limitation_context`, `metadata`, `method_context`, `result_context`, and `visual_inventory`, so reviewers do not have to infer later-stage work from the top-priority table alone. The next required action is human editing of the patch templates, followed by `scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py`, ready-only staging, and seed/eval/holdout release packaging.
- Contract compatibility now verifies reviewer-handoff package headline counts against the embedded curation package, patch-template manifest, progress report, and task export. This keeps the reviewer guide/template packet from passing contract review if its wrapper counts drift away from the embedded artifacts reviewers will use.
- Added `scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/reviewer-handoff/apply`. A reviewer can now take a saved handoff package after editing its patch templates, apply the embedded structured patch requests, and refresh the patch-result manifest, curation-progress report, task export JSON, and task export CSV into a non-canonical `paper_understanding_gold_reviewer_handoff_apply_package.v1`; this shortens the review loop without promoting patched drafts into accepted fixed gold. Running the current unedited handoff through the apply CLI now writes the blocked workspace package at `goldset/reviews/paper_understanding_gold_reviewer_handoff_apply/package.json` and reports `edited_result_count=0`, `unedited_result_count=8`, `ready_to_stage_count=0`, and `remaining_task_count=54` with the same stage/priority distribution, confirming that prefilled patch scaffolds are not mistaken for human edits and that the apply step does not hide unresolved human curation work.
- Added `scripts/eval/stage_paper_understanding_gold_reviewer_handoff.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/reviewer-handoff/stage`. A ready handoff apply package can now be staged through the existing ready-only `paper_understanding_gold_staging_manifest.v1` gate, then refresh progress and task-export sidecars in a non-canonical `paper_understanding_gold_reviewer_handoff_stage_package.v1`; this closes the typed reviewer handoff path from edited templates to staged review gold without writing to accepted gold.
- Reviewer-handoff apply now exposes an opt-in edited-template guard (`--require-edited` / `require_edited=true`) and roadmap next-action command hints use it for apply-package repair. The guard preflights the saved patch templates before refreshing apply sidecars, preventing scripted handoff apply runs from writing another `paper_understanding_gold_reviewer_handoff_apply_package.v1` or updated patch-result/progress/task-export files while all templates are still scaffold values.
- Reviewer-handoff apply failure diagnostics are now structured on both API and CLI surfaces. `require_edited=true` FastAPI failures return stable `findings`, and the CLI prints `finding_count` plus numbered `finding.N` rows such as `no_edited_patch_results` and `unedited_patch_result_count=<n>`, preserving the fail-closed error line while making operator handoff machine-readable.
- Reviewer-handoff apply diagnostics now also include `unedited_patch_template_path_count` plus a bounded `unedited_patch_template_paths_sample` finding when `--require-edited` fails on unedited scaffold templates. The CLI/API still refuse to write apply sidecars, but reviewers can see how many patch-template files remain and concrete examples to edit without opening the package JSON first.
- Roadmap completion inventory and next-action text now carry reviewer-handoff patch-template count/sample details. The standalone and package-derived roadmap CLIs print `gold_reviewer_handoff_patch_template_path_count` plus `gold_reviewer_handoff_patch_template_paths_sample`, and the immediate human-review action names the total template count and one concrete template path.
- Roadmap completion inventory now also compares current reviewer patch templates against their source drafts and records edited, unedited, unknown edit-state counts plus a bounded unedited-template sample. After the Bialystok template edit, the workspace audit reports `gold_reviewer_handoff_edited_patch_template_count=1` and `gold_reviewer_handoff_unedited_patch_template_count=7`, and the next-action text points at the remaining unedited templates instead of stale all-unedited apply evidence.
- As of 2026-05-24, the Dubois 2024 IWG recommendation patch template has also been evidence-edited from local extracted article chunks. Isolated patch application recalculates it as readiness-passing, and the workspace audit now reports `gold_reviewer_handoff_edited_patch_template_count=2` and `gold_reviewer_handoff_unedited_patch_template_count=6` while still blocking full handoff apply until the remaining six templates are edited.
- As of 2026-05-24, the Furtado 2018 BBB/nanomaterials review patch template has also been evidence-edited from local extracted article chunks. Isolated patch application recalculates it as readiness-passing, guarded full handoff apply now blocks on `unedited_patch_result_count=5`, and the workspace audit reports `gold_reviewer_handoff_edited_patch_template_count=3`, `gold_reviewer_handoff_unedited_patch_template_count=5`, and `gold_reviewer_handoff_unknown_patch_template_edit_state_count=0`. The next reviewer target is `zotero_hanssonBloodBiomarkersAlzheimers2023.patch_template.json`.
- As of 2026-05-24, the Hansson 2023 blood-biomarker review patch template has also been evidence-edited from local extracted article chunks. Isolated patch application recalculates it as readiness-passing, guarded full handoff apply now blocks on `unedited_patch_result_count=4`, and the workspace audit reports `gold_reviewer_handoff_edited_patch_template_count=4`, `gold_reviewer_handoff_unedited_patch_template_count=4`, and `gold_reviewer_handoff_unknown_patch_template_edit_state_count=0`. The next reviewer target is `zotero_kistemakerVascularizedHumanBrain2025.patch_template.json`.
- As of 2026-05-24, the Kistemaker 2025 vascularized human brain organoids review/opinion patch template has also been evidence-edited from local extracted article chunks. Isolated patch application recalculates it as readiness-passing, guarded full handoff apply now blocks on `unedited_patch_result_count=3`, and the workspace audit reports `gold_reviewer_handoff_edited_patch_template_count=5`, `gold_reviewer_handoff_unedited_patch_template_count=3`, and `gold_reviewer_handoff_unknown_patch_template_edit_state_count=0`. The remaining reviewer targets are `zotero_pichetbinetteConfoundingFactorsAlzheimers2023.patch_template.json`, `zotero_therriaultBiomarkerModelingAlzheimers2022.patch_template.json`, and `zotero_zhouGliatoNeuronConversionCRISPRCasRx2020.patch_template.json`.
- As of 2026-05-24, the Pichetbinette 2023 Alzheimer's disease plasma-biomarker primary-research patch template has also been evidence-edited from local extracted article chunks. Isolated patch application recalculates it as readiness-passing, guarded full handoff apply now blocks on `unedited_patch_result_count=2`, and the workspace audit reports `gold_reviewer_handoff_edited_patch_template_count=6`, `gold_reviewer_handoff_unedited_patch_template_count=2`, and `gold_reviewer_handoff_unknown_patch_template_edit_state_count=0`. The remaining reviewer targets are `zotero_therriaultBiomarkerModelingAlzheimers2022.patch_template.json` and `zotero_zhouGliatoNeuronConversionCRISPRCasRx2020.patch_template.json`.
- As of 2026-05-24, the Therriault 2022 PET-based Braak staging primary-research patch template has also been evidence-edited from local extracted article chunks. Isolated patch application recalculates it as readiness-passing, guarded full handoff apply now blocks on `unedited_patch_result_count=1`, and the workspace audit reports `gold_reviewer_handoff_edited_patch_template_count=7`, `gold_reviewer_handoff_unedited_patch_template_count=1`, and `gold_reviewer_handoff_unknown_patch_template_edit_state_count=0`. The remaining reviewer target is `zotero_zhouGliatoNeuronConversionCRISPRCasRx2020.patch_template.json`.
- As of 2026-05-24, the Zhou 2020 Cell glia-to-neuron CRISPR-CasRx primary-research patch template has also been evidence-edited from local extracted article chunks. Isolated patch application recalculates it as readiness-passing, and all 8 reviewer handoff patch templates are now edited: `gold_reviewer_handoff_edited_patch_template_count=8`, `gold_reviewer_handoff_unedited_patch_template_count=0`, and `gold_reviewer_handoff_unknown_patch_template_edit_state_count=0`.
- The local reviewer handoff apply, stage, and release-prep packages have been refreshed from those 8 edited templates. Guarded handoff apply reports `curation_ready_count=8`, `ready_to_stage_count=8`, `remaining_task_count=0`, `edited_result_count=8`, and `unedited_result_count=0`; staging reports `staged_count=8`, `curation_complete=True`, and `remaining_task_count=0`; release-prep reports `split_count=3`, `release_ready_candidate=True`, and `release_ready=True`. A roadmap audit with the generated release-readiness report and release package passed `fixed_goldset_release_readiness` and `fixed_goldset_release_package_consistency`, moving the immediate roadmap blocker to fixed-goldset baseline/candidate benchmark execution and complete configuration lineage.
- A follow-up eval split run-readiness audit against the current local `storage/artifacts` still blocks fixed-goldset comparison with `goldset_item_count=3`, `fail_count=6`, and `comparison_run_ready=False`. The roadmap audit now summarizes missing core scorecard sidecars from run-readiness evidence, so the next fixed-goldset action explicitly asks for scorecard-aware baseline/candidate run directories rather than implying gold release curation is still the blocker.
- A temp-copy eval fixed-goldset execution probe confirms the existing sidecar builders can derive scorecard core inputs from current `document_artifact.json`, `index_artifact.json`, and `claimset.json` without external inference. With those derived sidecars, fixed-goldset run-readiness passes and the roadmap audit advances to `pass_count=7`, `fail_count=7`; remaining fixed-run blockers are embedded scorecard readiness failures and missing P0 `overstatement_rate`, not release curation.
- Added `evidence_grounding_scorecard_input_backfill.v1`, `scripts/eval/backfill_evidence_grounding_scorecard_inputs.py`, and `POST /evidence-grounding/scorecards/input-backfill`. This reproducible eval lane copies existing deepread run dirs into a caller-chosen output root and derives scorecard core inputs from saved `document_artifact.json`, `index_artifact.json`, and `claimset.json`, leaving source runs untouched and keeping the report non-canonical. Running it on the current eval split produced `pass_count=3`, `fail_count=0`; the resulting fixed-goldset comparison reached run-readiness success and then honestly failed on embedded scorecard readiness quality.
- Roadmap audit next actions now preserve the `overstatement_rate` contract explicitly: when that P0 metric is missing, the audit asks for explicit `OVERSTATED_RESULT` review labels or structured human review evidence before rerunning the scorecard-aware fixed-goldset comparison. Missing overstatement labels are not treated as zero overstatement.
- Roadmap audit evidence now also summarizes embedded not-ready scorecard reason codes for the per-run/aggregate scorecard check, filtering out non-blocking success markers such as `gold_metrics_scored`. This makes the current fixed-goldset blocker point to concrete coverage/readiness causes like low grounded-evidence ratio, low page coverage, missing major topic signals, and near-duplicate claims.
- Workspace inventory now treats a consistent `paper_understanding_gold_release_package.v1` as the active fixed-gold boundary for roadmap completion evidence. Legacy teacher files and other non-gold review artifacts under `goldset/` remain visible in inventory counts, but once a ready release package exists they no longer block `workspace_evidence_inventory_ready` solely because they are not `paper_understanding_gold.v1` records.
- When paper gold is attached but lacks explicit consistency labels, scorecards can now use non-canonical `claim_evidence_reviewed_eval_fixtures.json` as a supplement for only the missing consistency metrics (`overstatement_rate` and `contradiction_rate`). This preserves paper-gold precision/recall and other fixed-gold metrics while giving structured human review evidence a bounded path to make P0 overstatement available.
- Roadmap completion next-action text now also summarizes nonreplayable correction-log repair details when source diagnostics are available. The structured-correction action carries the invalid accepted-record count, the first repair target, and the first missing replay-field set, while the CLI still prints the complete bounded repair-target and missing-field diagnostics.
- Roadmap completion human-review routing now treats structured correction-log repair actions as human/evidence-bound when accepted eval rows require real parser/provider/model/model-version/prompt/profile lineage repair. Pure export/regeneration handoffs remain CLI-backed preparation actions, but source-row repair now appears in `human_review_action` output alongside reviewer-handoff template editing.
- Roadmap completion reports and CLIs now expose `blocked_without_next_action_count` and `blocked_without_next_action_ids`. This makes prerequisite-gated downstream failures explicit when the audit has more failed checks than immediate next actions; contract compatibility now rejects stale or malformed values so API/JSON consumers and CLI users see the same blocker summary.
- Generated reviewer handoff guides also include the guarded apply command, so the human-facing curation instructions do not drift from the fail-closed automation path.
- Added `scripts/eval/prep_paper_understanding_gold_reviewer_handoff_release.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/reviewer-handoff/release-prep`. A staged reviewer handoff package can now build a release split plan and, when the split plan is release-ready, emit the linked fixed manifest package and release-readiness gate in a non-canonical `paper_understanding_gold_reviewer_handoff_release_prep_package.v1`; this connects curated review gold to fixed-goldset benchmark preparation without skipping split coverage checks.
- The current `goldset/accepted` teacher-verification curation queue now audits as `draft_count=8`, `templated_count=8`, `patched_count=0`, `ready_to_stage_count=0`, `staged_count=0`, and `remaining_task_count=54` when the generated patch-template manifest is supplied. This means reviewer scaffolds exist for all local legacy teacher outputs, but accepted `paper_understanding_gold.v1` records and fixed-goldset runs are still blocking.
- Batch-applying those current unedited templates produces 8 patch-result files but `edited_result_count=0`, `unedited_result_count=8`, `curation_ready_count=0`, and `not_ready_count=8`; progress then reports `patched_count=8` with `ready_to_stage_count=0` and `remaining_task_count=54`. This confirms the batch lane is wired while preserving the requirement that human edits resolve the open curation tasks before staging.
- As of 2026-05-24, one local reviewer patch template (`zotero_bialystokBilingualismConsequencesMind2012.patch_template.json`) has been evidence-edited from local `document_artifact.json` / `index_artifact.json` chunks. Applying that single template in isolation produces a readiness-passing non-canonical patched draft with DOI, review paper type, three claims, method/result/limitation coverage, and Figure 1 inventory. The guarded full handoff apply still correctly refuses to write refreshed apply sidecars because the other seven templates remain unedited scaffolds.
- Added `scripts/eval/stage_paper_understanding_gold_from_candidate_drafts.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/stage`. Human-curated candidate drafts can now be staged as `paper_understanding_gold.v1` files under `goldset/reviews/paper_understanding_gold_staged/`; the staging path is non-canonical and rejects not-ready drafts by default.
- Added `scripts/eval/stage_paper_understanding_gold_from_patch_results.py` and the FastAPI endpoint `POST /paper-understanding-gold/candidate-drafts/stage-from-patch-results`. This consumes patch-result files, directories, or a patch-result manifest, extracts the patched candidate draft paths, and reuses the same ready-only staging gate. A regression fixture now exercises edited patch template -> patch-result manifest -> staged review gold -> progress audit `curation_complete=true`, proving the reviewer handoff path is complete without promoting unreviewed drafts.
- `validate_gold_paths()` and the fixed manifest builder now accept `paper_understanding_gold_staging_manifest.v1` inputs by expanding them to their staged review gold files, while directory scans skip the non-gold `staging_manifest.json` sidecar. Service, CLI, and FastAPI regression coverage verifies that staged review gold can publish into a fixed `paper_understanding_gold_manifest.v1` bundle with `require_ready=true`, closing the handoff from human-reviewed staging into fixed-goldset benchmark preparation.
- Reviewed staged gold can now be packaged into seed/eval/holdout fixed manifests plus a release-readiness report in one operation through `paper_understanding_gold_release_package.v1`. The package remains a non-canonical review gate and still blocks missing required splits, duplicate papers across splits, invalid referenced gold, or not-ready records before downstream benchmark/completion artifacts can use the fixed bundle.
- Ready staged gold can now move from one combined staging manifest to release-package inputs without manual split-file assembly through `paper_understanding_gold_release_split_plan.v1`. This closes the operator handoff from staged review gold to seed/eval/holdout release packaging while preserving the ready-only validation and non-canonical review boundary.
- A saved release split plan can now build the release package directly. The split-plan-to-package service, CLI, and FastAPI path consume `paper_understanding_gold_release_split_plan.v1`, reject non-ready split plans by default, write fixed seed/eval/holdout manifests, and emit the linked release-readiness report plus `paper_understanding_gold_release_package.v1` without manual JSON path transfer.
- Added eval-only gold scoring in `src/services/evidence_grounding_gold_scoring.py`.
- Scorecards can now fill available gold-scored metrics when both `paper_understanding_gold.json` and `claimset.resolved.json` are present.
- Current scoring covers claim precision, claim recall, evidence support precision, locator precision, unsupported claim rate, limitation recall, gap recall, method/result confusion, figure reference precision, table reference precision, table-cell locator precision, and figure-caption link accuracy using bounded deterministic matching.
- Scorecards now compute `metadata_match_rate` when `document_artifact.json` and `paper_understanding_gold.json` are both available. The metric compares title plus available DOI, PMID, year, and author signals, and routes mismatches to `DOI_MISMATCH` or `METADATA_MISMATCH` under the metadata resolver stage.
- Scorecards now compute `parser_section_accuracy` when `document_artifact.json` contains section text and gold evidence locators carry explicit `section` labels. The scorer requires the gold quote to be recoverable from the matched section text when a quote is available, using page range only as a fallback for quote-less locators.
- `overstatement_rate` remains `not_available` by default, but becomes available when the gold/eval fixture carries explicit `OVERSTATED_RESULT` review labels.
- Added `CONTRADICTED_RESULT` as a product-level consistency failure code and `contradiction_rate` as an eval-only gold-scored metric. It becomes available when gold or reviewed eval fixtures carry explicit contradiction review labels, or when a matched gold/system claim pair has bounded direct text-polarity conflict such as one side asserting an effect and the other side negating it. It is attributed to the consistency checker stage when present.
- Scorecard generation can also score against non-canonical reviewed claim/evidence correction fixtures from `claim_evidence_reviewed_eval_fixtures.json` when `paper_understanding_gold.json` is absent. These fixtures are treated as structured human-review labels and are reported with `reviewed_eval_fixture_metrics_scored`, not as canonical paper truth.
- Scorecards now include `failure_counts_by_code` so product-level failure codes can be summarized from proxy artifacts and, when available, gold scoring results.
- Gold-scored `MISSING_CLAIM` and `GAP_MISSED` counts supersede runtime proxy counts when gold labels are attached, so proxy coverage warnings do not double-count or override a fixed gold comparison result.
- Scorecards now include `stage_failure_summary`, mapping failure codes to likely extractor, classifier, grounding checker, consistency checker, parser, or metadata resolver ownership without changing runtime truth.
- Scorecards now include `stage_metric_summary`, which re-exposes existing runtime proxy and gold-scored metrics by pipeline stage. This gives extractor, classifier, grounding checker, consistency checker, and parser views without creating new canonical truth.
- Scorecards now read existing deep-read handoff artifacts (`acceptance_contract.json` and `quality_gate.json`) when present and expose additive downstream/handoff proxy metrics: `downstream_traceability_rate`, `handoff_review_ready`, `handoff_check_pass_rate`, and `handoff_hard_fail_count`. These are formatter-stage review signals and do not prove semantic statement-level traceability.
- Scorecards now expose correction-loop proxy metrics when claim/evidence correction cases or reviewed eval fixtures are attached: `review_burden_per_paper`, `accepted_correction_rate`, `correction_reuse_candidate_rate`, `correction_feedback_link_rate`, and `reviewed_eval_fixture_count`. These measure review burden and eval-readiness of human corrections, not automatic gold promotion.

### PR 3. Failure taxonomy and correction schema

Scope:

- product-level failure enum
- `ClaimEvidenceCorrectionCase`
- append/list API

Goal:

Turn human corrections into reusable structured improvement data.

Implementation note:

- Added product-level `PaperUnderstandingFailureCode` definitions with smallest-fix directions.
- Added `ClaimEvidenceCorrectionCase` with before/after claim text, before/after evidence refs, model/parser/prompt lineage, reviewer, eval-acceptance, and feedback linkage fields.
- Correction lineage now separates `llm_model_version` and `reader_profile_version` from `llm_model` and `prompt_version`, so accepted corrections can be replayed against a specific model/profile configuration instead of only a provider/model family.
- Added append/list API at `/claim-evidence-corrections`.
- Corrections are stored as additive JSONL review/improvement data and do not become canonical claim truth automatically.
- Accepted eval-candidate corrections now create a linked `artifact_review_feedback` row for the `evidence_grounding_scorecard` artifact type when no `related_feedback_id` is already present, and the artifact-review schema explicitly allows that artifact family. This keeps the correction log and existing artifact review feedback memory from diverging while preserving both as non-canonical review/eval artifacts.
- The correction list endpoint can filter by `accepted_for_eval` and `feedback_export_status`, which is the narrow backend hook for later eval-candidate review queues.
- Added `ClaimEvidenceCorrectionEvalCandidate` / `ClaimEvidenceCorrectionEvalCandidateExport` contracts, a FastAPI export view at `/claim-evidence-corrections/eval-candidates`, and `scripts/eval/export_claim_evidence_eval_candidates.py`. Accepted corrections can now be exported as non-canonical eval candidates in JSON or JSONL without promoting them to paper truth.
- Added `ClaimEvidenceCorrectionEvalReviewRecord` / `ClaimEvidenceCorrectionEvalReviewManifest`, `scripts/eval/import_claim_evidence_eval_candidates.py`, and the FastAPI endpoint `POST /claim-evidence-corrections/eval-review-queue/import`. Exported candidates can now be imported into `goldset/reviews/claim_evidence_eval_candidates/` as pending review records without touching `goldset/accepted`.
- Added `POST /claim-evidence-corrections/eval-review-queue/import-from-corrections`, which builds the same pending review intake directly from accepted correction-log filters. This keeps the API-only human-review loop usable without requiring clients to materialize an intermediate export file.
- Roadmap completion now requires structured correction evidence to validate as accepted `ClaimEvidenceCorrectionCase` rows, as the `claim_evidence_eval_candidate_export.v1` artifact emitted by the export CLI, or as the packaged `claim_evidence_reviewed_eval_fixtures_bundle.v1` sidecar created from approved human review fixtures. All accepted forms must retain before/after evidence refs plus parser/provider/model/model-version/prompt/profile lineage. Empty evidence refs, blank lineage, schema-invalid rows, non-eval correction rows, stale export counts, or stale fixture counts no longer satisfy the structured correction-log gate.
- New claim/evidence correction intake now rejects `accepted_for_eval=true` unless before/after evidence refs and parser/provider/model/model-version/prompt/profile lineage are present. Existing incomplete raw-memory rows remain blocked until repaired or re-exported from complete review evidence, but future accepted corrections cannot silently enter the log in a non-replayable form.
- The Workbench correction form now fails earlier in the user flow by disabling eval acceptance when the visible scorecard does not carry complete parser/model/prompt/profile lineage. Operators can still save ordinary non-canonical correction memory, and the UI explains that replayable eval reuse needs lineage first.
- The structured-correction next-action command now points to the export CLI's default JSON artifact (`claim_evidence_eval_candidates.json`) instead of implying JSONL output without `--jsonl`; regression coverage verifies that default export output can satisfy the completion gate when the exported candidates are replayable.
- Contract compatibility now supports `claim_evidence_eval_candidate_export.v1` as a non-canonical review artifact and rejects stale candidate counts, non-replayable exported candidates, missing source-log diagnostic fields, or invalid-row diagnostic count mismatches. This keeps correction-loop evidence visible to external-contract review without promoting corrections into canonical paper truth or letting stale exports pass through schema defaults.
- Roadmap completion now also requires contract-readiness coverage for the JSON review artifact used as structured correction evidence, either `claim_evidence_eval_candidate_export.v1` or `claim_evidence_reviewed_eval_fixtures_bundle.v1`. The completion package builders pass review artifacts into generated compatibility review automatically; JSONL correction logs remain correction-loop evidence and do not expand the required external schema family.
- Roadmap completion now loads `claim_evidence_eval_candidate_export.v1` correction evidence into the additive/non-canonical posture check as `correction_evidence_export`, keeping JSON correction exports visible as non-canonical review artifacts in the final audit rather than only as replayable correction counts.
- The structured correction completion evidence now labels the correction input kind and posture. Raw JSONL correction logs are reported as `raw_memory_noncanonical`, while exported eval-candidate JSON artifacts are reported as `review_gate_artifact_non_canonical`, preserving the raw-memory/review-artifact boundary without changing the raw correction-log contract.
- Eval-candidate correction exports now carry bounded source-log diagnostics: source record count, valid/invalid source rows, skipped non-eval rows, filtered rows, limit-skipped rows, invalid source row line numbers/error classes, the first validation detail, and missing replay-field names for accepted eval rows. The roadmap completion gate counts declared invalid source rows as blocking correction evidence and carries the bounded line-level detail into structured-correction audit evidence, so malformed legacy correction memory cannot disappear behind an otherwise schema-valid export.
- The eval-candidate export CLI/API now has an opt-in replayability guard (`--require-replayable` / `require_replayable=true`) that exits nonzero or returns HTTP 409 when the export would not satisfy the roadmap correction-evidence gate. The default export path still writes diagnostic review artifacts, but automation can fail early instead of passing zero-candidate or source-invalid exports downstream.
- When `--require-replayable` fails because accepted source correction rows are missing replay fields, the export CLI now prints bounded `source_invalid_record_missing_replay_fields` diagnostics keyed by source line number so operators can repair parser/provider/model/model-version/prompt/profile lineage without opening the JSON artifact first. It also prints `source_invalid_record_repair_targets` with any available correction, paper, run, and claim identifiers from invalid raw rows, so operators can locate the exact source correction records that need real replay lineage without treating inferred values as evidence.
- Eval-review intake imports now also accept the opt-in replayability guard, so scripted review-queue creation can refuse zero-candidate, source-invalid, stale-count, or non-replayable exports before writing an empty/non-actionable intake manifest.
- Correction-loop next-action command hints now include `--require-replayable` when they suggest `export_claim_evidence_eval_candidates.py`, aligning the operator handoff with the same fail-closed replayability contract.
- The roadmap completion request schemas and the standalone/comparison-suite-package/threshold-adoption-package audit CLIs now describe correction evidence as either raw `ClaimEvidenceCorrectionCase` JSONL or a `claim_evidence_eval_candidate_export.v1` JSON review artifact, so API/CLI operators no longer see stale JSONL-only guidance.
- Structured-correction next actions now distinguish missing evidence from malformed/non-replayable supplied evidence. A present raw correction log with invalid rows now asks operators to repair or re-export accepted eval records with before/after evidence refs and parser/model/prompt/profile lineage, while a missing correction path still asks for structured correction evidence.
- Structured-correction audit evidence now records the supplied `correction_evidence_path`, and raw correction-log repair/export command hints include `--log-path <supplied_log_path>`. This keeps failed live audits actionable when the current `storage/claim_evidence_corrections.jsonl` exists but is not replayable.
- Contract compatibility now rejects roadmap-completion audit artifacts with structured-correction evidence but no `correction_evidence_path`, keeping correction-loop review artifacts traceable to the exact raw log or exported eval-candidate artifact they evaluated.
- Contract compatibility also rejects roadmap-completion audit artifacts where `correction_evidence_path` has no matching `input_paths.correction_log_path` or disagrees with it, keeping the declared audit input and the structured-correction gate evidence aligned.
- Contract compatibility also rejects roadmap-completion audit artifacts where the human-readable bare structured-correction evidence path disagrees with the keyed `correction_evidence_path`, keeping display evidence and machine-readable trace evidence consistent.
- Contract compatibility now rejects roadmap-completion audit artifacts with missing, non-integer, negative, or status-inconsistent structured-correction `valid_count` / `invalid_count` evidence, so correction replayability counts cannot be stale-edited away from the check status or next-action logic.
- Contract compatibility now verifies roadmap-completion headline pass/warn/fail counts and blocker lists against embedded check statuses even when `roadmap_complete=false`, so incomplete reports cannot hide failed checks by editing summary fields.
- Roadmap completion checks now carry explicit evidence for missing upstream reports and missing correction evidence, and contract compatibility rejects any roadmap-completion check with empty or omitted evidence. This keeps completion audits reviewable without letting stale artifacts hide why a gate passed or failed.
- Contract compatibility now also rejects roadmap-completion checks that report `pass` or `warn` while carrying per-check next actions, keeping operator handoff actions tied to failed gates instead of stale passed checks.
- Contract compatibility now also rejects blank per-check roadmap-completion next-action strings, keeping failed-check handoff sources meaningful and preventing blank action rows from escaping both the top-level queue and blocked-without-action summary.
- Contract compatibility now also rejects top-level roadmap-completion next-action rows that have no matching failed check/per-check action source, so stale artifacts cannot inject ghost operator handoff work while keeping summary counts internally consistent.
- Contract compatibility now also recomputes top-level roadmap-completion next-action phase, human-review flag, and command hint from the embedded failed check evidence, so stale handoff metadata cannot drift while preserving self-consistent counts.
- Contract compatibility now also rejects top-level roadmap-completion next-action rows with omitted phase or human-review metadata when those omitted fields no longer match the service-derived values, so stale artifacts cannot hide handoff priority or review ownership by editing summary counts consistently.
- Contract compatibility now also verifies `human_review_unique_next_actions` against the full first service-derived human-review row for each unique action/command pair, so stale artifacts cannot preserve the visible action text while changing the requirement id, phase, or human-review flag shown in the operator checklist.
- Roadmap completion CLIs now mask local absolute paths in stdout next-action, human-review, correction-repair, handoff-template, and output-path lines while preserving real paths in the generated non-canonical JSON artifacts for lineage review. The shared path-masking helper now treats comma/semicolon-separated path lists as separate local paths, so multi-path evidence samples do not leak later entries.
- Roadmap completion FastAPI responses now apply the same local-path masking posture to response-only copies of the audit report for standalone, comparison-suite-package, and threshold-adoption-package audit routes. Persisted `out` JSON artifacts still keep real paths for non-canonical lineage review.
- Contract compatibility now also rejects duplicate top-level roadmap-completion next-action rows by `(requirement_id, action)`, matching the service queue's dedupe contract so stale artifacts cannot inflate operator work while keeping counts self-consistent.
- Contract compatibility now also rejects reordered top-level roadmap-completion next-action rows, preserving the service-derived failed-check order so operator handoff priority cannot be stale-edited while keeping counts self-consistent.
- Contract compatibility now rejects stale `evidence_grounding_roadmap_completion_audit.v1` artifacts that carry structured-correction evidence without the correction evidence kind/posture fields, so external compatibility review cannot bless an older completion report that hides the raw-memory/review-artifact boundary.
- Contract compatibility also rejects invalid or mismatched correction evidence kind/posture values inside roadmap-completion audits, so arbitrary labels such as `paper_truth` / `canonical` cannot masquerade as a valid correction-evidence boundary.
- Added `ClaimEvidenceCorrectionEvalReviewDecision` / `ClaimEvidenceCorrectionReviewedEvalFixture` and `scripts/eval/review_claim_evidence_eval_candidates.py`. Human review can now approve, reject, or request more evidence for an intake record. Approval creates a non-canonical reviewed eval fixture under `goldset/reviews/claim_evidence_eval_candidates/reviewed/`; it still does not write to `goldset/accepted`.
- Added `scripts/eval/package_claim_evidence_reviewed_fixtures.py` and a service writer for `claim_evidence_reviewed_eval_fixtures.json`, so approved reviewed fixtures can be packaged into a run directory and consumed by scorecard/benchmark generation without manual file assembly.
- The packaged reviewed-fixture sidecar is now schema-backed as `claim_evidence_reviewed_eval_fixtures_bundle.v1` and is accepted by roadmap structured-correction and contract-compatibility checks as a non-canonical review artifact. This lets the same human-approved fixture path support overstatement-rate scorecard enrichment and structured correction-log completion evidence without promoting it to canonical paper truth.
- Added a FastAPI packaging endpoint at `/claim-evidence-corrections/reviewed-fixtures/package` with explicit non-canonical response metadata, keeping the reviewed-fixture sidecar path API-first instead of CLI-only.
- Scorecard input backfill can now take an optional reviewed-fixtures directory and package matching approved fixtures into copied output run dirs before scorecard generation. This gives the fixed-goldset backfill/comparison workflow a batch path for `claim_evidence_reviewed_eval_fixtures.json` without mutating source runs or treating reviewed fixtures as canonical paper truth.
- Added FastAPI review-queue endpoints at `/claim-evidence-corrections/eval-review-queue` and `/claim-evidence-corrections/eval-review-queue/resolve`, so pending eval candidates can be listed and approved/rejected/requested-for-more-evidence through the API as well as the CLI.

### PR 4. Benchmark runner and comparison gate

Scope:

- batch scorecard runner
- baseline-vs-candidate comparison
- P0 regression gate

Goal:

Compare parser/model/prompt changes against the same goldset.

Implementation note:

- Added benchmark manifest/report contracts in `src/schemas/evidence_grounding_benchmark.py`.
- Added `src/services/evidence_grounding_benchmark.py` to build aggregate benchmark reports from saved run directories without rerunning deepread.
- Added `scripts/eval/run_evidence_grounding_benchmark.py` and the FastAPI endpoint `POST /evidence-grounding/benchmarks/run` for deterministic batch scorecard generation from a saved benchmark manifest.
- Added `scripts/eval/compare_evidence_grounding_scorecards.py` and the FastAPI endpoint `POST /evidence-grounding/scorecards/compare` to compare scorecards or benchmark reports and surface metric regressions through a non-canonical comparison report.
- Benchmark manifests and reports now preserve `goldset_id`, `goldset_split`, and `goldset_manifest_path`. Comparisons fail when benchmark reports declare different goldset IDs or splits, so candidate metrics cannot be treated as comparable when they were scored against different fixed targets.
- The paper-understanding gold validation service can now validate the `goldset_manifest_path` target itself when it uses `paper_understanding_gold_manifest.v1`, giving the benchmark context an auditable source rather than only free-text IDs. Benchmark reports warn when the referenced manifest is missing, invalid, or declares a different `goldset_id` / `goldset_split` than the benchmark manifest.
- Benchmark reports now also record fixed-goldset coverage fields: `goldset_item_count`, `goldset_covered_paper_count`, `goldset_missing_paper_ids`, and `goldset_extra_paper_ids`. A candidate report warns when scored run directories do not cover every paper declared by the selected goldset manifest or include extra papers outside that fixed target.
- Benchmark comparisons now treat fixed-goldset coverage gaps as context failures. A candidate with missing or extra goldset papers cannot pass merely because the available aggregate metrics look improved.
- Benchmark reports now carry fixed-goldset readiness counts and `goldset_not_ready_paper_ids` from the selected paper-understanding manifest. Benchmark comparisons treat not-ready goldset papers as context failures, so model/prompt comparisons cannot pass against weak gold records merely because the metrics are available.
- Added `scripts/eval/build_evidence_grounding_benchmark_manifest.py`, `build_evidence_grounding_benchmark_manifest_from_goldset()`, and the FastAPI endpoint `POST /evidence-grounding/benchmark-manifests/from-goldset`. A benchmark manifest can now be generated from a fixed `paper_understanding_gold_manifest.v1` plus a run root; it requires eval-ready gold records and existing run directories by default, with explicit flags for review-only relaxed modes.
- Added `scripts/eval/build_evidence_grounding_benchmark_manifest_from_staged_gold.py`, `build_evidence_grounding_benchmark_manifest_from_staged_gold()`, and the FastAPI endpoint `POST /evidence-grounding/benchmark-manifests/from-staged-gold`. This API-first handoff accepts a `paper_understanding_gold_staging_manifest.v1`, writes the intermediate fixed `paper_understanding_gold_manifest.v1`, then writes the `evidence_grounding_benchmark_manifest.v1` for the declared run root with optional typed candidate lineage. It keeps staged review gold non-canonical while making benchmark preparation repeatable.
- Benchmark reports now preserve scorecard readiness at the aggregate level through pass/warn/fail counts, `scorecard_not_ready_candidate_ids`, and warnings for failed embedded scorecards. This keeps scorecard-level identity/readiness failures visible in fixed-goldset benchmark outputs instead of hiding them behind averaged metrics.
- Benchmark run packages now preserve those scorecard readiness summaries across split benchmark reports through package-level pass/warn/fail counts, scoped `benchmark_id:candidate_id` not-ready candidate IDs, and top-level warnings. A seed/eval/holdout package can therefore expose a failed or warning split scorecard without requiring operators to inspect every embedded benchmark report by hand.
- Fixed-goldset comparison-suite packages now preserve baseline/candidate run-package scorecard readiness context, including explicit-field presence, pass/warn/fail counts, not-ready candidate IDs, and warnings for stale or non-passing run packages. This prevents split comparison package handoffs from hiding whether their input benchmark run packages were generated with the readiness-aware contract.
- Threshold-adoption packages now carry that comparison-suite package scorecard context forward, including explicit-field presence, pass/warn/fail counts, not-ready candidate IDs, and warnings for stale suite-package context. This prevents package-wide threshold adoption from hiding whether the underlying split comparison evidence came from readiness-aware benchmark handoffs.
- Roadmap completion's package-wide threshold-adoption gate now also checks that threshold package scorecard context fields are explicitly present, that the source suite/run-package readiness context was present, and that baseline/candidate package scorecard failure counts are zero. Stale threshold packages or failed package scorecard context now block `fixed_goldset_threshold_adoption_package_ready`.
- Benchmark comparison now rejects benchmark reports with failed embedded scorecards through `benchmark_context.<side>_scorecard_readiness_failures`, preventing failed identity/readiness checks from being masked by aggregate metric averages.
- Roadmap completion audit now checks benchmark `scorecard_readiness_fail_count` values directly in the per-run/aggregate scorecard requirement, so failed embedded scorecards still block completion even if a comparison report was generated before the readiness failure was introduced.
- Roadmap completion audit now also requires those benchmark scorecard readiness fields to be explicitly present, not merely filled by schema defaults, so stale benchmark reports generated before readiness aggregation cannot satisfy the final completion gate.
- Contract compatibility audit now requires `evidence_grounding_benchmark.v1` artifacts to include the scorecard readiness fields before they can pass compatibility review, keeping stale benchmark reports out of the external-contract adoption lane as well as the final completion gate.
- Contract compatibility audit now also rejects stale benchmark manifest-package summaries. Package `manifest_count` must match manifest paths and, when embedded benchmark manifests are present, `manifest_count` and `item_count` must match the embedded manifests and their items.
- Contract compatibility audit now also checks benchmark manifest-package linked manifest sidecars. Manifest-package compatibility cannot pass if manifest or item counts drift away from the linked benchmark manifest files.
- Contract compatibility audit now also checks gold release-package linked readiness sidecars. A release package cannot pass package-only compatibility if its linked `paper_understanding_gold_release_readiness.v1` payload, manifest count, or readiness manifest paths drift away from the package envelope.
- Contract compatibility audit now also checks reviewer-handoff package/apply/stage linked task-export sidecars. A handoff package cannot pass package-only compatibility if the linked `paper_understanding_gold_curation_task_export.v1` file drifts away from the package counts or, when fully embedded, from the embedded task-export payload. Apply and stage packages now also reject stale linked task-export files whose open-task counts, task summaries, or full typed payloads drift from the package envelope.
- Contract compatibility audit now also checks reviewer-handoff apply-package linked handoff packages. Apply-package compatibility cannot pass if the linked `paper_understanding_gold_reviewer_handoff_package.v1` file drifts from apply result counts or has stale handoff package summaries.
- Contract compatibility audit now also checks reviewer-handoff apply-package linked patch-result manifests. Apply-package compatibility cannot pass if the linked `paper_understanding_gold_candidate_draft_patch_result_manifest.v1` file drifts from package result/readiness/edit counts, patch-result path counts, or a fully embedded typed manifest payload.
- Contract compatibility audit now also checks reviewer-handoff apply-package linked progress reports. Apply-package compatibility cannot pass if the linked `paper_understanding_gold_candidate_draft_curation_progress.v1` file drifts from package draft/result, ready-to-stage, or remaining-task counts; timestamp-only embedded/linked progress differences are ignored.
- Contract compatibility audit now also checks reviewer-handoff stage-package linked apply packages. Stage-package compatibility cannot pass if the linked `paper_understanding_gold_reviewer_handoff_apply_package.v1` file has insufficient ready-to-stage records, stale not-ready counts, or remaining-task counts that drift from the stage envelope.
- Contract compatibility audit now also checks reviewer-handoff stage-package linked handoff packages. Stage-package compatibility cannot pass if the linked `paper_understanding_gold_reviewer_handoff_package.v1` file has stale source draft counts or internally inconsistent handoff package summaries.
- Contract compatibility audit now also checks reviewer-handoff stage-package linked progress reports. Stage-package compatibility cannot pass if the linked `paper_understanding_gold_candidate_draft_curation_progress.v1` file drifts from package staged, completion, or remaining-task counts; timestamp-only embedded/linked progress differences are ignored.
- Contract compatibility audit now also checks reviewer-handoff stage-package linked staging manifests. Stage-package compatibility cannot pass if the linked `paper_understanding_gold_staging_manifest.v1` file drifts from package staged counts, staged-path counts, or a fully embedded typed staging manifest payload.
- Contract compatibility audit now also checks reviewer-handoff release-prep linked split plans. Release-prep compatibility cannot pass if the linked `paper_understanding_gold_release_split_plan.v1` file drifts from package staged/split/candidate counts or from a fully embedded typed split-plan payload.
- Contract compatibility audit now also checks reviewer-handoff release-prep linked release packages. Release-prep compatibility cannot pass if the linked `paper_understanding_gold_release_package.v1` file drifts from package split/release-ready summaries or from a fully embedded typed release-package payload.
- Contract compatibility audit now also checks reviewer-handoff release-prep linked release-readiness reports. Release-prep compatibility cannot pass if the linked `paper_understanding_gold_release_readiness.v1` file drifts from package split/release-ready summaries or from a fully embedded typed readiness payload.
- Contract compatibility audit now also checks reviewer-handoff release-prep linked stage packages. Release-prep compatibility cannot pass if the linked `paper_understanding_gold_reviewer_handoff_stage_package.v1` file drifts from package staged count, completion, remaining-task readiness, or the stage package's own linked sidecar checks.
- Contract compatibility audit now also checks reviewer-handoff release-prep linked staging manifests. Release-prep compatibility cannot pass if the linked `paper_understanding_gold_staging_manifest.v1` file drifts from package staged count or staged-path count.
- Contract compatibility audit now also rejects stale benchmark run-package summaries. `report_count` must match `benchmark_report_paths`, and embedded benchmark reports, when present, must agree with package `item_count`, `scorecard_count`, scorecard readiness pass/warn/fail counts, and scoped not-ready candidate IDs.
- Contract compatibility audit now also checks benchmark run-package linked report sidecars. Run-package compatibility cannot pass if aggregate item, scorecard, scorecard-readiness, or not-ready candidate summaries drift away from the linked benchmark report files.
- Contract compatibility audit now also checks comparison-suite package linked baseline/candidate run-package sidecars. Suite-package compatibility cannot pass if preserved scorecard readiness counts or not-ready candidate IDs drift away from the linked run-package files.
- Contract compatibility audit now also rejects stale threshold-calibration recommendation counts. Calibration report counts, per-recommendation report counts, available counts, observed values, and source-report lists must agree before a calibration artifact can pass external-contract review.
- Contract compatibility audit now also rejects stale threshold-adoption review summaries. Review pass/warn/fail counts, blockers, and `production_threshold_ready` must agree with the embedded checks before an adoption artifact can pass external-contract review.
- Contract compatibility audit now also rejects stale threshold-adoption package summaries. Package suite counts must match threshold-checked comparison paths, adoption-review paths, and embedded adoption reviews when present, and production-threshold ready/blocked counts must match embedded review statuses.
- Contract compatibility audit now also checks linked threshold-adoption package review sidecars. Package-only compatibility cannot pass from embedded adoption summaries if the linked review files have drifted readiness status, stale counts, blockers, or invalid summaries.
- Contract compatibility audit now also rejects stale comparison decision summaries. Comparison `decision.passed`, `compared_metric_count`, `failed_checks`, and `regressions` must agree with embedded metric comparisons, stage comparisons, failure-count comparisons, threshold checks, and benchmark context before a comparison artifact can pass external-contract review.
- Contract compatibility generated from a threshold-adoption package now also includes the linked baseline/candidate benchmark run packages and their benchmark-manifest packages, and final external-contract readiness requires benchmark-manifest, benchmark-run, comparison-suite-package, and threshold-adoption-package schema coverage whenever threshold-package evidence is supplied.
- Contract readiness now rejects stale linked compatibility summaries before allowing external readiness. Compatibility artifact/pass/warn/fail counts, warning markers, item statuses, item findings, and self-promotion posture must agree with embedded items before a readiness report or final completion audit can rely on it.
- Roadmap completion external-contract readiness now also requires the linked compatibility report to cover the same artifact paths supplied to the completion audit. Schema-family coverage alone no longer passes if the compatibility report reviewed different benchmark, comparison, calibration, adoption, release, package, or correction-export files.
- Roadmap completion audit now also rejects stale contract-readiness summaries. Contract-readiness pass/warn/fail counts, blockers, warning markers, artifact count, and `external_contract_ready` must agree with embedded checks and the linked compatibility report before `external_contract_readiness_reviewed` can pass.
- Added `EvidenceGroundingFixedGoldsetRunReadinessReport`, `scripts/eval/audit_evidence_grounding_fixed_goldset_run_readiness.py`, and the FastAPI endpoint `POST /evidence-grounding/fixed-goldset-run-readiness/audit`. Before running a real baseline/candidate comparison, operators can now check that both run roots cover the fixed goldset and contain required sidecars such as `reader_eval.json`, `claimset_coverage.json`, `evidence_extraction_bundle.json`, and `claimset.resolved.json`. The run-readiness gate also validates run identity metadata when present, blocking stale, conflicting, or malformed `paper_id` declarations before the comparison suite can be treated as fixed-goldset evidence. Required sidecars must also be parseable JSON before an item passes; malformed required sidecars are recorded per item and summarized per lane.
- Benchmark generation now uses the referenced `paper_understanding_gold_manifest.v1` records as the actual gold source for scorecard generation when the benchmark item declares a `paper_id`. This means fixed-goldset benchmark reports can produce gold-scored metrics without copying `paper_understanding_gold.json` into every run directory; the source artifact records the manifest path plus paper ID.
- Added `run_evidence_grounding_fixed_goldset_comparison_suite()`, `scripts/eval/run_evidence_grounding_fixed_goldset_comparison.py`, and the FastAPI endpoint `POST /evidence-grounding/fixed-goldset-comparison/run`. The suite builds baseline/candidate benchmark manifests from the same fixed goldset, writes `run_readiness_report.json`, runs both benchmark reports, compares them, and writes `baseline_benchmark_report.json`, `candidate_benchmark_report.json`, `comparison_report.json`, and `comparison_suite.json` in one repeatable eval lane.
- Added `EvidenceGroundingFixedGoldsetComparisonSuite` so the saved `comparison_suite.json` handoff is also a typed non-canonical Pydantic review artifact instead of an ad hoc JSON summary.
- Added `run_evidence_grounding_fixed_goldset_comparison_suite_from_staged_gold()`, `scripts/eval/run_evidence_grounding_fixed_goldset_comparison_from_staged_gold.py`, and the FastAPI endpoint `POST /evidence-grounding/fixed-goldset-comparison/run-from-staged-gold`. This wrapper accepts a staged review-gold manifest, publishes the intermediate fixed paper-understanding manifest, performs the same run-readiness audit, builds baseline/candidate benchmark manifests and reports, compares them, and writes the typed non-canonical `comparison_suite.json`. It keeps staged review gold non-canonical while giving operators one repeatable lane from reviewed gold to comparison evidence.
- Fixed-goldset manifest generation and comparison-suite CLI paths now accept typed candidate configuration fields, so real baseline/candidate runs can be labeled with parser/model/prompt/profile lineage at creation time instead of requiring hand-edited manifests before completion audit.
- Comparison covers available runtime proxy metrics and gold-scored P0 metrics separately. Missing gold metrics remain `gold_metrics_unavailable` rather than fake zeros.
- Benchmark aggregation and comparisons also carry available P1 gold-scored `claim_recall`, `gap_recall`, `metadata_match_rate`, and `parser_section_accuracy` metrics. A production policy can keep the hard regression gate focused on P0 metrics by passing an explicit gate list, then promote selected P1 metrics when the gold labels are mature enough.
- Comparison reports now record `gate_policy` and `gate_metric_names`. The CLI supports `--gate-preset p0-gold` for a P0-only metric gate and repeated `--gate-metric` flags for explicit metric promotion. All comparable metrics are still reported, but only the selected metric gate participates in the metric regression decision. Failure-count regressions remain hard failures. This lets reviewers explicitly promote selected P1 metrics such as `figure_reference_precision` or `parser_section_accuracy` without changing runtime truth.
- Comparison reports now record `threshold_policy` and `threshold_checks`. The CLI supports `--threshold-preset p0-gold-minimum` for an initial absolute promotion policy over P0 gold metrics, plus repeated `--threshold-metric NAME=VALUE` flags for explicit candidate-quality thresholds. Higher-is-better metrics use the value as a minimum, lower-is-better metrics use it as a maximum. Missing threshold metrics fail the threshold check instead of being treated as zeros or silently ignored.
- Added `build_evidence_grounding_threshold_calibration_report()`, `scripts/eval/calibrate_evidence_grounding_thresholds.py`, and the FastAPI endpoint `POST /evidence-grounding/threshold-calibration/build`. Saved scorecard or benchmark reports can now produce a non-canonical `evidence_grounding_threshold_calibration.v1` review artifact with conservative observed threshold recommendations: higher-is-better metrics use the observed minimum and lower-is-better metrics use the observed maximum. These recommendations are evidence for review, not automatic production policy.
- Added `build_evidence_grounding_threshold_calibration_report_from_comparison_suite()`, `scripts/eval/calibrate_evidence_grounding_thresholds_from_comparison_suite.py`, and the FastAPI endpoint `POST /evidence-grounding/threshold-calibration/build-from-comparison-suite`. A typed fixed-goldset `comparison_suite.json` can now feed threshold calibration directly by resolving the suite's candidate benchmark report by default, with an explicit option to include the baseline benchmark report.
- Added `compare_evidence_grounding_scorecard_reports_from_comparison_suite()`, `scripts/eval/compare_evidence_grounding_scorecards_from_comparison_suite.py`, and the FastAPI endpoint `POST /evidence-grounding/scorecards/compare-from-comparison-suite`. After an initial fixed-goldset suite run, operators can now apply a later threshold calibration report to the suite's baseline/candidate benchmark reports and write a threshold-checked comparison report without rebuilding the benchmarks.
- Comparison API/CLI paths now accept explicit threshold calibration reports. Passing a calibration report applies its available recommendations as explicit threshold checks, while explicit threshold metric overrides can replace individual recommendations. This keeps threshold adoption deliberate and traceable to a review artifact.
- Added `EvidenceGroundingThresholdAdoptionReviewReport`, `scripts/eval/review_evidence_grounding_threshold_adoption.py`, and the FastAPI endpoint `POST /evidence-grounding/threshold-adoption/review`. This adoption review consumes a threshold calibration report, a threshold-checked comparison report, and a fixed-goldset run-readiness report, then blocks `production_threshold_ready` unless the comparison passes, threshold checks pass, calibrated required metrics are available, every P0 grounding metric has a calibrated threshold value, the fixed-goldset run preflight is ready, human approval is referenced, and explicit opt-in is provided. It can also resolve the comparison and run-readiness report paths directly from `comparison_suite.json`, while explicit paths remain supported as overrides. It does not mutate runtime threshold policy.
- Added `build_evidence_grounding_threshold_adoption_review_report_from_comparison_suite()`, `scripts/eval/review_evidence_grounding_threshold_adoption_from_comparison_suite.py`, and the FastAPI endpoint `POST /evidence-grounding/threshold-adoption/review-from-comparison-suite`. A fixed-goldset comparison suite can now produce the calibration report, threshold-checked comparison report, and threshold adoption review in one operator handoff, while preserving the explicit human approval and production-threshold opt-in gates.
- Added `EvidenceGroundingContractCompatibilityReport`, `scripts/eval/check_evidence_grounding_contract_compatibility.py`, and the FastAPI endpoint `POST /evidence-grounding/contract-compatibility/audit`. The compatibility check verifies supported evidence-grounding artifact schema versions and the required `review_gate_artifact` / `non_canonical` posture before any scorecard, benchmark, comparison, threshold-calibration, threshold-adoption, fixed-goldset run-readiness, or fixed-goldset suite output is treated as an external integration candidate. Raw scorecard artifacts are also validated against the scorecard schema, so unknown failure codes cannot pass compatibility review as external-contract candidates. It deliberately keeps `external_contract_ready=false`; migration/backfill review is still required before external stability claims.
- Added `build_evidence_grounding_contract_compatibility_report_from_comparison_suite()`, `scripts/eval/check_evidence_grounding_contract_compatibility_from_comparison_suite.py`, and the FastAPI endpoint `POST /evidence-grounding/contract-compatibility/audit-from-comparison-suite`. A typed fixed-goldset `comparison_suite.json` can now feed compatibility review directly by resolving suite-linked benchmark, comparison, and run-readiness reports, optional threshold calibration/adoption reports, and embedded benchmark scorecards.
- Contract compatibility now also supports `paper_understanding_gold_release_readiness.v1` and `paper_understanding_gold_release_package.v1` as non-canonical review artifacts. Roadmap completion requires external-contract coverage for the gold release-readiness schema and, when a release package is supplied, the release-package schema as well. The comparison-suite completion package passes the effective gold-release readiness/package artifacts into the generated contract compatibility report so this coverage is not skipped in the one-step completion lane.
- Contract compatibility now also supports `paper_understanding_gold_release_split_plan.v1` as a non-canonical operator handoff artifact. The roadmap workspace inventory reports split-plan counts and ready/invalid split-plan counts, making the staged-gold-to-release-package handoff visible without making the split plan a canonical truth store or a completion-required contract schema.
- Added `EvidenceGroundingContractReadinessReport`, `scripts/eval/audit_evidence_grounding_contract_readiness.py`, and the FastAPI endpoint `POST /evidence-grounding/contract-readiness/audit`. This second-stage audit consumes a compatibility report and blocks `external_contract_ready` unless migration review, backfill review, public contract documentation, explicit human approval, and an explicit opt-in are all present. The report remains a non-canonical review artifact; it does not promote evidence-grounding outputs into canonical truth.
- Added `build_evidence_grounding_contract_readiness_report_from_comparison_suite()`, `scripts/eval/audit_evidence_grounding_contract_readiness_from_comparison_suite.py`, and the FastAPI endpoint `POST /evidence-grounding/contract-readiness/audit-from-comparison-suite`. A fixed-goldset comparison suite can now write the compatibility report and run the contract-readiness audit in one operator handoff, while preserving the migration/backfill/public-contract document, human approval, and explicit opt-in gates.
- Added `EvidenceGroundingRoadmapCompletionAuditReport`, `scripts/eval/audit_evidence_grounding_roadmap_completion.py`, and the FastAPI endpoint `POST /evidence-grounding/roadmap-completion/audit`. This audit checks the roadmap Definition of Done against current fixed-goldset, benchmark, comparison, threshold, contract, correction, and candidate-configuration artifacts. It can resolve baseline/candidate benchmark reports, the comparison report, and run-readiness report directly from `comparison_suite.json`; the fixed-goldset run check now requires that suite to be loadable, non-canonical, and path-consistent with the reports being audited. The audit also requires a passing paper-understanding gold release-readiness report covering the seed/eval/holdout fixed-goldset bundle before the roadmap can be complete. The threshold-adoption completion check requires calibration and adoption coverage for every P0 grounding metric rather than accepting a partial threshold review. The external-contract completion check now requires the referenced compatibility review to cover the required evidence-grounding artifact schema family, including scorecard, benchmark, comparison, threshold, run-readiness, and fixed-goldset suite artifacts. It fails closed when real evidence or typed parser/model/prompt/profile lineage is missing, so it is a completion guardrail rather than a self-promotion mechanism.
- Added `build_evidence_grounding_roadmap_completion_audit_report_from_comparison_suite_package()`, `scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py`, and the FastAPI endpoint `POST /evidence-grounding/roadmap-completion/audit-from-comparison-suite-package`. A fixed-goldset comparison suite can now generate the threshold-adoption package, contract-readiness package, optional gold release-readiness report from seed/eval/holdout manifest paths, and final roadmap completion audit in one operator handoff, while still failing closed unless gold release-readiness, correction logs, P0 thresholds, migration/backfill/public-contract evidence, human approvals, and explicit opt-ins are present.
- Roadmap completion audit and the comparison-suite package now also accept a typed `paper_understanding_gold_release_package.v1` path. When supplied, the audit validates the package as non-canonical review evidence and resolves its linked release-readiness report, so the staged-gold release package can flow into the final completion gate without hand-copying the readiness path.
- The comparison-suite completion package can now also build that gold release package directly from reviewed staged split manifests. Operators can supply seed/eval/holdout `paper_understanding_gold_staging_manifest.v1` inputs plus fixed manifest/package/readiness output paths, and the package will publish fixed split manifests, write `paper_understanding_gold_release_package.v1`, resolve its readiness report, then run the final completion audit.
- The comparison-suite completion package can now also consume a saved `paper_understanding_gold_release_split_plan.v1` directly. Operators can pass the split-plan path plus package/readiness output paths, and the package will build the fixed release package, include the split plan in contract compatibility review, resolve the linked release-readiness report, and run the final completion audit without hand-copying `split_manifests`.
- The staged-gold release package now preserves `source_split_manifests` lineage for the seed/eval/holdout staged inputs. The completion audit validates that those source split `manifest_out` paths still match the package fixed-manifest list and that current source staging manifests still rebuild the same fixed manifest content when lineage is present, so staged-review source drift is visible before any roadmap-complete decision.
- Added `build_evidence_grounding_benchmark_manifest_package_from_release_package()`, `scripts/eval/build_evidence_grounding_benchmark_manifests_from_release_package.py`, and the FastAPI endpoint `POST /evidence-grounding/benchmark-manifests/from-release-package`. A ready paper-understanding release package can now emit one `evidence_grounding_benchmark_manifest.v1` per fixed split plus a non-canonical `evidence_grounding_benchmark_manifest_package.v1`, preserving candidate parser/model/prompt/profile lineage and existing-run checks before benchmark execution.
- Added `run_evidence_grounding_benchmark_package_from_manifest_package()`, `scripts/eval/run_evidence_grounding_benchmark_package.py`, and the FastAPI endpoint `POST /evidence-grounding/benchmarks/run-package`. A saved benchmark-manifest package can now run each split manifest into an `evidence_grounding_benchmark.v1` report and emit a non-canonical `evidence_grounding_benchmark_run_package.v1`, including package-level scorecard readiness counts and warnings, reducing the manual handoff from fixed gold release packages to per-split benchmark evidence.
- Added `run_evidence_grounding_fixed_goldset_comparison_suite_package_from_benchmark_run_packages()`, `scripts/eval/run_evidence_grounding_fixed_goldset_comparison_from_benchmark_run_packages.py`, and the FastAPI endpoint `POST /evidence-grounding/fixed-goldset-comparison/run-from-benchmark-run-packages`. Baseline/candidate benchmark run packages can now produce one typed `evidence_grounding_fixed_goldset_comparison_suite.v1` per fixed split plus a non-canonical `evidence_grounding_fixed_goldset_comparison_suite_package.v1`, preserving run-readiness checks, comparison outputs, and input run-package scorecard readiness context without hand-assembling split paths.
- Added `build_evidence_grounding_threshold_adoption_review_package_from_comparison_suite_package()`, `scripts/eval/review_evidence_grounding_threshold_adoption_from_comparison_suite_package.py`, and the FastAPI endpoint `POST /evidence-grounding/threshold-adoption/review-from-comparison-suite-package`. A split comparison-suite package can now calibrate thresholds across selected baseline/candidate benchmark reports, write threshold-checked comparison reports per split, and emit a non-canonical `evidence_grounding_threshold_adoption_review_package.v1` with per-split adoption-review evidence plus the source suite package's scorecard readiness context.
- Added `build_evidence_grounding_contract_readiness_report_from_threshold_adoption_package()`, `scripts/eval/audit_evidence_grounding_contract_readiness_from_threshold_adoption_package.py`, and the FastAPI endpoint `POST /evidence-grounding/contract-readiness/audit-from-threshold-adoption-package`. A threshold-adoption package can now expand its linked calibration, threshold-checked comparisons, adoption reviews, comparison-suite package, split suites, linked benchmark reports, run-readiness reports, and embedded scorecards into one compatibility review before running the explicit migration/backfill/public-contract readiness gate.
- Contract compatibility now treats reviewer-handoff guide and apply edit-state fields as part of the supported review-artifact surface. A `paper_understanding_gold_reviewer_handoff_package.v1` must expose `reviewer_guide_path`, and a `paper_understanding_gold_reviewer_handoff_apply_package.v1` must embed `patch_result_manifest.edited_result_count` and `patch_result_manifest.unedited_result_count`; older handoff/apply packages without those fields fail compatibility instead of silently looking equivalent to human-reviewable or human-reviewed curation evidence.
- Contract compatibility now also rejects internally inconsistent reviewer-handoff apply counts. Package readiness counts, ready-to-stage counts, embedded patch-result counts, edited/unedited totals, and embedded task-export open-task counts must agree when present. This keeps stale apply artifacts from passing contract review while preserving the distinction between an honest blocked package and a ready package.
- Contract compatibility now also rejects internally inconsistent reviewer-handoff stage and release-prep counts. Stage packages must keep staged/progress/task-export counts aligned, and release-prep packages must keep staged count, split count, split-plan readiness, split-item totals, release-package manifest count, and embedded release-readiness status aligned.
- Contract compatibility now also rejects internally inconsistent fixed-gold release-readiness, release split-plan, and release package artifacts. Headline release counts must match split summaries, ready release artifacts cannot carry blockers/invalid/non-passing split evidence, split-plan staged totals must match ready inputs, and release packages must keep manifest/source-lineage counts aligned with embedded readiness. This keeps stale fixed-gold release JSON from passing external-contract review before it reaches the stricter completion audit.
- Added `build_evidence_grounding_roadmap_completion_audit_report_from_threshold_adoption_package()`, `scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py`, and the FastAPI endpoint `POST /evidence-grounding/roadmap-completion/audit-from-threshold-adoption-package`. A threshold-adoption package can now select a representative split suite, reuse the linked calibration/adoption review, build package-wide contract readiness, include optional gold release package/readiness evidence in compatibility coverage, and write the final non-canonical roadmap-completion audit without manually selecting per-split files. When that package path is supplied, the completion audit also adds `fixed_goldset_threshold_adoption_package_ready`, which requires seed/eval/holdout split coverage, production-threshold-ready adoption reviews, package scorecard-context fields, and zero package scorecard readiness failures across the package rather than accepting one representative split as proof of the fixed-goldset threshold gate. The package gate also verifies that declared package counts, embedded adoption reviews, linked adoption-review sidecars, comparison-suite paths, and scorecard context still agree, so stale or hand-edited package summaries fail closed.
- Roadmap completion now requires that package-wide threshold-adoption evidence instead of treating a single suite/review as sufficient. Standalone and comparison-suite-package completion lanes still write their intermediate review artifacts, but `roadmap_complete=true` is blocked until a loadable `evidence_grounding_threshold_adoption_review_package.v1` covers ready seed/eval/holdout adoption reviews.
- The standalone roadmap completion audit service, CLI, and FastAPI endpoint now also have coverage for `gold_release_package_path`, so an already-built release package can be reused in later completion audits without re-running the package builder or manually copying its linked readiness report path.
- When a release package is supplied, roadmap completion now also checks that the package's embedded release-readiness payload, linked release-readiness sidecar, fixed manifest path list, release `goldset_id`, and current fixed manifest contents match. The audit recomputes release readiness from the package's manifest paths, using a stable fingerprint that ignores generated timestamps and explanatory detail text, so stale or edited manifest files cannot support `roadmap_complete=true`.
- The roadmap completion audit can also scan a supplied workspace `goldset_root` and `run_root`. That inventory reports ready `paper_understanding_gold.v1` counts separately from legacy `teacher_verification.v1`, candidate draft, staging files, reviewer handoff packages, task exports, release-readiness reports, and release packages, and counts run directories that actually contain the required grounding sidecars. The inventory gate now also requires complete run evidence to match the ready gold `paper_id` set, preferring paper IDs declared inside scorecard/run metadata before falling back to deepread sidecar paper IDs and then raw or safe path segments. If a run directory's own metadata declares conflicting paper IDs, or if present identity metadata is malformed, the directory is counted as invalid identity evidence and cannot satisfy the fixed-gold execution check. Required run sidecars must also be parseable JSON before a directory counts as ready; malformed or unreadable required sidecars are reported separately and produce a regeneration next action. Release-package inventory distinguishes valid packages, embedded ready packages, and packages whose linked readiness report plus fixed manifests still reproduce a consistent release result. This keeps the current local evidence state visible without promoting it into canonical truth.
- Workspace roadmap inventory now also reports loadable `evidence_grounding_scorecard.v1` files under the configured run root. When the additive non-canonical artifact check is missing an explicit scorecard input but the run root already contains a valid `evidence_grounding_scorecard.json`, the next-action queue points operators at that existing path and a `--scorecard` audit handoff instead of always suggesting a rebuild.
- Roadmap completion checks now emit additive `next_actions` when a requirement fails, and the completion audit report also includes a top-level deduplicated `next_actions` queue keyed by `requirement_id`. Queue items carry a `phase`, a `requires_human_review` flag, and optional `command_hint` values pointing to the relevant non-canonical handoff script. The report summarizes `next_action_phase_counts`, `human_review_next_action_count`, `human_review_unique_next_action_count`, and the derived `human_review_unique_next_actions` list, making the remaining fixed-gold, baseline/candidate run, threshold adoption, correction-log, and contract-readiness workload visible in CLI/API outputs while distinguishing row count from unique review tasks. These actions are operator guidance derived from the same blocker evidence, not completion evidence.
- When workspace inventory proves that ready fixed-gold records are still below the configured requirement, the top-level roadmap `next_actions` queue now defers downstream fixed-gold run, threshold, package, and contract commands while preserving the failed checks and blockers. This keeps the operator checklist on immediately actionable curation/correction work without treating hidden downstream actions as satisfied completion evidence.
- Workspace run-evidence actions in roadmap completion now point to the existing fixed-goldset run-readiness audit command, so missing or mismatched run directories can be checked with a typed non-canonical preflight before a baseline/candidate comparison is attempted.
- Threshold-package actions in roadmap completion now separate comparison-suite package construction from threshold-adoption review: the package-build action points to the fixed-goldset comparison-suite package CLI, while the review action points to the threshold-adoption package CLI.
- Production-threshold adoption actions in roadmap completion now separate threshold calibration from adoption review: the calibration action points to the comparison-suite calibration CLI, while the review action points to the threshold-adoption package CLI with explicit approval and opt-in flags.
- Roadmap completion human-review routing now treats threshold calibration and comparison-suite package construction as automated/operator preparation rather than human review. The paired threshold-adoption review, threshold-package review, contract approval, and gold-curation actions remain marked `requires_human_review=true`.
- The additive/non-canonical artifact action now points operators at `build_evidence_grounding_scorecard.py` and is treated as CLI-backed preparation rather than human review. The `review_gate_artifact` layer name is taxonomy, not evidence of human approval.
- Workspace inventory run-readiness and gold-release package actions are also treated as CLI-backed preparation instead of human review. The reviewer handoff edit/apply action remains marked `requires_human_review=true`, preserving the curation boundary while keeping runnable inventory checks out of the review workload count.
- Gold release-readiness audit and contract compatibility/readiness execution actions are likewise counted as audit preparation rather than human review. The separate threshold review, threshold-package review, handoff curation, and migration/backfill/public-contract approval actions remain the human-review workload.
- External-contract next-action hints now split compatibility checking from external-readiness approval: the compatibility-prep action points to `check_evidence_grounding_contract_compatibility.py`, while the approval action still points to the threshold-adoption-package readiness audit with migration/backfill/public-contract and reviewer-approval inputs.
- The roadmap completion next-action queue now advances the gold-curation command hint from the current workspace inventory instead of always suggesting handoff creation. It is readiness-aware rather than existence-only: apply packages must have `ready_to_stage_count > 0`, `not_ready_count = 0`, and `remaining_task_count = 0`; stage packages must have `staged_count > 0`, `curation_complete = true`, and `remaining_task_count = 0`; release-prep packages must have `release_ready = true`. Blocked apply/stage/release-prep packages keep the next action on the unresolved review step instead of allowing the checklist to skip ahead.
- That handoff inventory readiness check now treats apply/stage package counters as typed JSON integers and reports malformed apply/stage package counts separately. Stringified values such as `"1"` no longer count as ready handoff evidence or advance the queue to staging/release-prep.
- Release-prep inventory now follows the same strict typing rule: `staged_count` and `split_count` must be positive JSON integers, and `release_ready_candidate` plus `release_ready` must both be true before a release-prep package is counted as ready. Malformed release-prep counts are surfaced separately and keep the fixed-gold release handoff blocked.
- Release artifact workspace inventory now also applies the raw count-consistency checks used by contract compatibility before counting split plans, release-readiness reports, or release packages as valid/ready. Pydantic-coercible strings or mismatched counts are treated as invalid release inventory rather than proof of fixed-gold release readiness.
- Release package consistency inventory now also validates the linked release-readiness sidecar's raw counts before incrementing `consistent_gold_release_package_count`, and the workspace next-action queue treats only consistent release packages as satisfying the release-package handoff.
- The workspace inventory now verifies that reviewer-handoff packages point to an existing reviewer guide. It reports `gold_reviewer_handoff_guide_path_count`, `existing_gold_reviewer_handoff_guide_count`, and `missing_gold_reviewer_handoff_guide_count`; missing guide files add a regeneration next action instead of letting the human-curation queue look ready for review on package presence alone.
- The workspace inventory now also reads reviewer-handoff apply edit-state counts from the embedded patch-result manifest. It reports `gold_reviewer_handoff_apply_edited_result_count`, `gold_reviewer_handoff_apply_unedited_result_count`, `unedited_gold_reviewer_handoff_apply_package_count`, `partially_unedited_gold_reviewer_handoff_apply_package_count`, and `unknown_edit_state_gold_reviewer_handoff_apply_package_count`. A reviewer-handoff apply package is only counted as ready when the usual ready-to-stage criteria are met and, when edit-state fields are present, `edited_result_count > 0` and `unedited_result_count = 0`; unedited-only apply packages keep the next action on patch-template editing/re-apply instead of stage.
- The reviewer-handoff apply FastAPI endpoint now returns structured `findings` when `require_edited=true` blocks unedited templates, matching the CLI's fail-closed guard while keeping the API-first repair path machine-readable. Typical findings include `no_edited_patch_results` and `unedited_patch_result_count=<n>`.
- The standalone roadmap-completion CLI can print the full queue with `--print-next-actions` plus optional `--next-action-limit`, and can print only the derived unique human-review queue with `--print-human-review-actions`, making local blocked audits directly usable as an operator checklist without opening the JSON sidecar. The package-derived completion CLIs now also print `next_action_count`, `human_review_next_action_count`, `human_review_unique_next_action_count`, and `next_action_phase_counts`, and accept both `--print-next-actions` and `--print-human-review-actions` for the same full and unique human-review checklists.
- After the current handoff package was generated, the standalone completion audit still correctly reports `roadmap_complete=false`, `fail_count=13`, `next_action_count=21`, `human_review_next_action_count=5`, and `human_review_unique_next_action_count=4`. This is expected: creating reviewer scaffolds moves the queue into human curation, but it does not prove ready `paper_understanding_gold.v1` seed/eval/holdout release evidence or fixed-goldset baseline/candidate benchmark evidence. Threshold-prep, additive scorecard-evidence, workspace run-readiness, release-package, release-readiness audit, and contract compatibility/readiness execution actions are no longer counted as human review because they are generated CLI-backed preparation steps; the unique list removes the duplicate reviewer-handoff edit action that appears under both fixed-gold release and workspace inventory provenance while still preserving both blocker rows in `next_actions`.
- Added `EvidenceGroundingCandidateConfig` to benchmark manifests, per-scorecard benchmark items, and aggregate benchmark reports. Candidate evals can now carry typed parser/model/prompt/profile lineage (`parser_version`, `llm_provider`, `llm_model`, `llm_model_version`, `prompt_version`, `reader_profile_version`) instead of burying that comparison context in ad hoc metadata.
- `evidence_grounding_scorecard.v1` now also carries optional typed `candidate_config` lineage. The standalone scorecard build API and benchmark runner pass this through without changing canonical runtime truth, so downstream review UI can distinguish ordinary correction memory from replayable eval-candidate corrections when lineage is available.
- Run-local scorecard rebuilds now also load an optional `candidate_config.json` sidecar when no explicit config is supplied. Valid sidecars are recorded in scorecard `source_artifacts` and input diagnostics, keeping lineage artifact-driven without inferring missing prompt/profile/model-version data from partial `run_meta.json`.
- Roadmap completion now requires complete candidate replay lineage for every scored benchmark item (`parser_version`, `llm_provider`, `llm_model`, `llm_model_version`, `prompt_version`, and `reader_profile_version`) rather than accepting a partial config with only one populated field.
- Benchmark manifest builders and fixed-goldset comparison runners now support opt-in `require_complete_candidate_config` / `--require-complete-candidate-config` checks. Roadmap-oriented runs fail fast when parser/provider/model/model-version/prompt/profile lineage is incomplete, before writing benchmark manifests, run-readiness sidecars, comparison outputs, or manifest packages that would later fail completion. Exploratory non-roadmap manifests can still carry partial lineage.
- Roadmap completion next-action command hints for fixed-goldset benchmark runs now include the full baseline and candidate parser/model/prompt/profile CLI flags accepted by `run_evidence_grounding_fixed_goldset_comparison.py` plus `--require-complete-candidate-config`, so following the hint can satisfy the candidate replay-lineage gate instead of only setting parser versions.
- Roadmap completion audit requests, the FastAPI audit endpoint, and the standalone audit CLI now accept an optional standalone `scorecard_path` / `--scorecard`. A loadable `evidence_grounding_scorecard.v1` can therefore satisfy the additive/non-canonical artifact posture check directly, while the broader roadmap still remains blocked until fixed-goldset, correction, threshold, and contract evidence are present. When a run root is supplied and no explicit scorecard path is given, the audit selects the first loadable run-root scorecard as additive review evidence and records `scorecard_path_selected_from_run_root`, avoiding a separate operator handoff for an artifact already present in the audited workspace.
- Workspace roadmap inventory now reports existing structured correction evidence paths alongside scorecard paths. When a `claim_evidence_corrections.jsonl`, `claim_evidence_eval_candidates.json`, or `claim_evidence_reviewed_eval_fixtures.json` artifact is present but not yet replayable, the structured-correction next action points to that path with an appropriate repair/export handoff instead of implying the workspace has no correction evidence.
- When a run root is supplied and no explicit correction evidence path is given, the roadmap audit now selects the first workspace structured correction evidence path for the `structured_correction_log` check and records `correction_log_path_selected_from_workspace`. Nonreplayable raw logs still fail the gate, but the failure evidence now includes the concrete path, artifact kind/posture, and invalid-record counts instead of a path-missing placeholder.
- When a temp run root is supplied together with a real `goldset_root`, structured-correction auto-discovery also checks the workspace `storage/` sibling for `claim_evidence_corrections.jsonl`. This keeps temp scorecard/backfill audits connected to the real correction loop and surfaces repair targets without requiring operators to pass `--correction-log` by hand.
- For raw `claim_evidence_corrections.jsonl` evidence, the roadmap audit now reuses the correction-log source diagnostics directly. The `structured_correction_log` check records source invalid line numbers, missing replay fields, and correction/paper/run/claim repair targets without requiring operators to first export a failed `claim_evidence_eval_candidate_export.v1` sidecar.
- The claim/evidence correction FastAPI replayability guards now return the same source-record diagnostics exposed by the CLI. When `require_replayable=true` fails, export and eval-review intake endpoints include `source_invalid_record_count` plus line-level `source_invalid_record_diagnostics`, including missing parser/model/prompt/profile lineage fields and any available correction/paper/run/claim identifiers, so API-first operators can repair the raw correction source without falling back to CLI-only diagnostics.
- Roadmap completion audits now preserve those correction repair targets when the supplied correction evidence is a `claim_evidence_eval_candidate_export.v1` artifact. The `structured_correction_log` check evidence includes `source_invalid_record_repair_targets`, and the failed next action distinguishes listed source correction records from a generic re-export instruction while keeping the replayability gate failed.
- The standalone and package-derived roadmap-completion CLIs also print `structured_correction_repair_targets`, `structured_correction_missing_replay_fields`, and `structured_correction_invalid_details` when `--print-next-actions` is used and the correction check has invalid source-record diagnostics. Operators can now see the exact correction rows, missing parser/model/prompt/profile lineage fields, and validation error details from stdout without opening the audit JSON, while the audit still exits nonzero.
- Claim/evidence eval-candidate exports now carry optional `source_correction_log_path` provenance. The export CLI prints it, FastAPI replayability failures include it with normal response path masking, and roadmap completion uses it to restore a concrete `--log-path ... --require-replayable` command hint even when the audit input is the exported `claim_evidence_eval_candidate_export.v1` artifact rather than the raw correction JSONL.
- Workspace roadmap completion inventory now also resolves reviewer-handoff patch-template manifests and records `gold_reviewer_handoff_patch_template_path_count` plus `gold_reviewer_handoff_patch_template_paths_sample`. The standalone and package-derived roadmap-completion CLIs print both values with `--print-next-actions`, so the current human-edit blocker exposes how many patch templates remain and concrete examples directly from any audit handoff while preserving the fail-closed apply gate.
- Benchmark reports now aggregate `failure_counts_by_code` and stage failure summaries across included scorecards, so reviewers can see not only that a candidate regressed but which failure classes accumulated.
- Benchmark reports now aggregate `stage_metric_summary` across scorecards, preserving stage-level extractor/classifier/grounding/parser quality views at batch-eval time.
- Benchmark reports now aggregate downstream/handoff proxy metrics, including formatter-stage `downstream_traceability_rate` and `handoff_check_pass_rate` signals, when deep-read handoff artifacts are present in run directories.
- Benchmark reports and stage metric comparisons now include correction-loop proxy metrics, so increased review burden or lower correction reuse/linkage can fail candidate comparisons when those signals are available.
- Comparison reports now include a `correction_reuse_gain` summary. When the candidate carries correction reuse signals and comparable P0 gold-scored metrics exist, the report computes direction-normalized P0 metric deltas as paired-eval evidence of reuse gain. This still does not prove any single correction caused the improvement.
- Comparison reports now include failure-count comparisons by product failure code and by pipeline stage. Candidate runs fail the comparison when failure counts increase, even if the available numeric metrics are unchanged.
- Comparison reports now include `stage_metric_comparisons`, so stage-qualified metrics such as `grounding_checker.runtime_proxy_metrics.grounded_evidence_ratio` can fail the gate even when a reviewer needs stage-local attribution.

### PR 5. Deepread integration

Scope:

- write scorecard during deepread runs
- include summary fields in run metadata
- preserve existing sidecars

Goal:

Make every new deepread run produce the same quality summary.

Implementation note:

- `backend/services/job_runner.py` now writes `evidence_grounding_scorecard.json` after the existing `claimset_coverage`, `reader_eval`, and `evidence_extraction_bundle` sidecars are attempted.
- Scorecard generation is additive: failures are logged in `bootstrap_meta` and do not change deepread job success/failure semantics.
- Scorecards now include `input_artifact_diagnostics` plus `malformed_input_artifact_count`, making loaded, missing, and load-failed sidecars machine-queryable instead of burying malformed input state only in warning text. The malformed-input count is staged under `unknown` with the other instrumentation-coverage metrics because it reflects scorecard input health rather than a single model role. Benchmark reports aggregate it and comparisons treat it as lower-is-better, so a candidate can regress on malformed input health even if semantic metrics are unchanged. Contract compatibility rejects scorecard artifacts that omit those fields and benchmark artifacts that omit aggregate malformed-input counts, and roadmap completion requires that aggregate metric to be available on both audited benchmark reports, so stale reports cannot pass by relying on schema defaults or generic aggregate metric presence.
- Scorecard compatibility now also verifies that input diagnostics cover all four core scorecard inputs as core diagnostics, closing the stale-artifact gap where a scorecard could contain an empty or partial diagnostics list while still satisfying the field-presence check.
- Scorecard compatibility also requires the input-health runtime proxy metrics for coverage, missing inputs, and malformed inputs, then verifies those values against the core diagnostics. That keeps instrumentation health explicit and prevents stale scorecards from claiming clean or complete inputs while their diagnostics say otherwise.
- Scorecards now also carry an additive `input_artifact_summary` derived from `source_artifacts` and `input_artifact_diagnostics`. The schema rejects stale supplied summaries, and contract compatibility reports a stable `scorecard_input_artifact_summary_mismatch` finding when a standalone or benchmark-embedded scorecard's summary diverges from the raw input evidence. Older scorecards that omit the additive summary remain compatible.
- Benchmark compatibility now requires the same input-health metric family after aggregation and, when embedded scorecards are present, checks aggregate values and item counts against those scorecards. Benchmark artifacts therefore cannot silently drop or stale-copy scorecard input coverage, missing-input, or malformed-input evidence when rolling up per-run scorecards.
- Completion inventory now separates complete run directories with declared paper identity from complete-but-opaque run directories. It uses scorecard/run metadata first and falls back to existing deepread sidecar `paper_id` fields only when stronger run identity artifacts are absent, preserving stale-identity checks while making reusable run evidence easier to audit before fixed gold is curated.
- The same inventory now emits bounded ready-gold, declared-run, and matched-run paper-id samples so blocked audits can show which fixed-gold curation or rerun alignment is actually missing without treating the workspace scan as canonical truth.
- Completion inventory now requires required run sidecars to be parseable JSON before counting a run directory as ready. Malformed or unreadable required sidecars increment `ready_run_required_artifact_error_count` and add a regeneration next action, so present-but-broken sidecars cannot satisfy the fixed-gold execution proof.
- Fixed-goldset run-readiness reports now carry the same malformed-required-sidecar proof explicitly through `malformed_required_artifacts` and `malformed_required_artifact_count`; contract compatibility rejects stale run-readiness artifacts that omit those fields, so external review cannot treat file presence alone as run readiness.
- Fixed-goldset run-readiness compatibility and roadmap completion now also verify pass/fail summary counts against lane summaries and item statuses. This prevents a hand-edited run-readiness report from claiming `comparison_run_ready=true` while embedded lane or item evidence still contains failures.
- Fixed-goldset comparison-suite compatibility and roadmap completion now compare suite-level readiness summaries against the linked run-readiness report, so `comparison_suite.json` cannot claim a different `comparison_run_ready` or `run_readiness_fail_count` than the sidecar it references.
- Fixed-goldset comparison-suite package compatibility now checks package summary counts against path lists and, when embedded split suites are present, against embedded suite pass/fail and run-readiness failure counts. This keeps split-package threshold-adoption inputs from hiding stale or contradictory suite-package summaries.
- Benchmark manifest-package compatibility now checks manifest summary counts against manifest paths and embedded benchmark manifests when present. This keeps stale baseline/candidate manifest package summaries from passing external-contract review before benchmark run packages are generated.
- Benchmark manifest-package compatibility now also checks linked benchmark manifest sidecars in addition to embedded manifest copies. This keeps manifest-package evidence from passing compatibility after the manifest files operators will use drift from the package envelope.
- Gold release-package compatibility now checks the linked release-readiness sidecar in addition to the embedded readiness copy. This keeps fixed-gold release evidence from passing compatibility after the sidecar operators will inspect has drifted from the package envelope.
- Reviewer-handoff package/apply/stage compatibility now checks linked task-export sidecars in addition to embedded task-export counts. This keeps human curation queue and post-apply/stage evidence from passing compatibility after the task-export file reviewers will inspect has drifted from the package envelope.
- Reviewer-handoff apply compatibility now checks the linked handoff package in addition to post-apply sidecars. This keeps apply evidence from passing compatibility after the source reviewer-handoff package has drifted from the package envelope.
- Reviewer-handoff apply compatibility now checks the linked patch-result manifest in addition to the embedded manifest counts. This keeps post-apply handoff evidence from passing compatibility after the patch-result manifest reviewers will stage from has drifted from the package envelope.
- Reviewer-handoff apply compatibility now checks the linked progress report in addition to task-export and patch-result sidecars. This keeps post-apply handoff evidence from passing compatibility after the progress report reviewers inspect has drifted from the package envelope.
- Reviewer-handoff stage compatibility now checks the linked apply package in addition to stage task/progress/manifest sidecars. This keeps stage evidence from passing compatibility after the apply package it depends on has drifted from the stage envelope.
- Reviewer-handoff stage compatibility now checks the linked source handoff package in addition to apply/progress/manifest sidecars. This keeps stage evidence from passing compatibility after the source handoff package has drifted from the staged record envelope.
- Reviewer-handoff stage compatibility now checks the linked progress report in addition to task-export sidecars and embedded progress counts. This keeps staged handoff evidence from passing compatibility after the progress report reviewers inspect has drifted from the package envelope.
- Reviewer-handoff stage compatibility now checks the linked staging manifest in addition to embedded staging-manifest counts. This keeps staged handoff evidence from passing compatibility after the staging manifest reviewers will release from has drifted from the package envelope.
- Reviewer-handoff release-prep compatibility now checks the linked split plan in addition to embedded split-plan counts. This keeps release-prep evidence from passing compatibility after the split plan reviewers will package from has drifted from the package envelope.
- Reviewer-handoff release-prep compatibility now checks the linked release package in addition to embedded release-package counts. This keeps release-prep evidence from passing compatibility after the release package reviewers will audit from has drifted from the package envelope.
- Reviewer-handoff release-prep compatibility now checks the linked release-readiness report in addition to release package and split-plan sidecars. This keeps release-prep evidence from passing compatibility after the readiness report reviewers will use for fixed-gold release proof has drifted from the package envelope.
- Reviewer-handoff release-prep compatibility now checks the linked stage package and that stage package's linked sidecars in addition to downstream release sidecars. This keeps release-prep evidence from passing compatibility after the upstream staged-review handoff has drifted from the package envelope.
- Reviewer-handoff release-prep compatibility now checks the linked staging manifest in addition to the upstream stage package. This keeps release-prep evidence from passing compatibility after the staged gold file used for split planning has drifted from the package envelope.
- Benchmark run-package compatibility now checks package summary counts against report paths and embedded benchmark reports when present. This keeps baseline/candidate split packages from hand-editing report, item, scorecard, readiness, or not-ready-candidate totals before they feed comparison-suite packages.
- Benchmark run-package compatibility now also checks linked benchmark report sidecars in addition to embedded report copies. This keeps package-level split evidence from passing compatibility after the report files operators will inspect have drifted from the package envelope.
- Comparison-suite package compatibility now checks linked baseline/candidate run-package sidecars in addition to preserved package context. This keeps package-wide fixed-gold comparison evidence from passing compatibility when the underlying run-package readiness context has drifted.
- Threshold-calibration compatibility now checks recommendation evidence counts against observed values and source reports. This keeps proposed threshold evidence from passing compatibility after hand-edited report or availability counts drift away from the actual benchmark observations.
- Threshold-adoption review compatibility now checks summary counts, blockers, and production-ready status against embedded checks. This keeps a threshold adoption review from passing compatibility after only top-level fields are hand-edited.
- Threshold-adoption package compatibility now checks package summary counts against threshold comparison/review path lists and embedded adoption-review statuses when present. This keeps a hand-edited adoption package from passing external-contract review with stale suite, ready, or blocked counts.
- Threshold-adoption package compatibility now checks linked adoption-review sidecars in addition to embedded summaries. This keeps a package from passing compatibility when the files it points operators to no longer match the package's production-ready summary.
- Comparison compatibility now checks decision summary consistency against embedded metric, stage, failure-count, threshold, and benchmark-context evidence. This keeps a hand-edited comparison report from passing external-contract review after `decision.passed`, `failed_checks`, `regressions`, or `compared_metric_count` drift away from the underlying checks.
- Contract-readiness now checks linked compatibility summary consistency against embedded compatibility items before external readiness can pass. This keeps a hand-edited compatibility report from satisfying migration/backfill/public-contract review after its counts, warning markers, item statuses, findings, or self-promotion posture drift away from the actual item rows.
- Contract-readiness completion now checks linked compatibility path coverage for the concrete artifacts under audit. This keeps a compatibility report for one threshold calibration, comparison suite, benchmark, release package, or correction export from satisfying completion for a different artifact with the same schema version.
- Contract-readiness completion now checks summary consistency against embedded readiness checks and the linked compatibility report. This keeps a hand-edited readiness report from satisfying final roadmap completion after `external_contract_ready`, blockers, counts, warning markers, or artifact counts drift away from the migration/backfill/public-contract review evidence.
- Roadmap completion next actions now use that workspace handoff state to refine the fixed-gold release-readiness blocker. If a reviewer handoff package is already present, the queued action points to the concrete edit/apply, unblock, stage, or release-prep step needed next instead of leaving operators at a generic "curate ready gold" instruction.
- Roadmap completion check-level actions now use the same workspace-aware refinement as the top-level queue, so JSON consumers reading the failed `fixed_goldset_release_readiness` check see the concrete reviewer-template edit/re-apply step when unedited handoff apply packages are present.
- Workspace handoff inventory also keeps apply/stage package readiness counters typed as JSON integers and reports malformed apply/stage package counts, so stringified handoff summaries cannot be counted as ready fixed-gold release evidence.
- Workspace handoff inventory also keeps release-prep package readiness typed: release-prep requires true candidate/release status plus positive integer staged/split counts, and malformed release-prep count fields are reported rather than counted ready.
- Workspace release inventory now mirrors contract-compatibility count validation for split-plan, release-readiness, and release-package artifacts before incrementing valid/ready release counts, preventing malformed release sidecars from satisfying workspace evidence.
- Workspace release-package handoff now requires a raw-valid linked release-readiness sidecar before a package is counted consistent, preventing embedded-ready packages with malformed linked sidecars from suppressing the build/release-package next action.
- Contract compatibility now requires roadmap completion audit artifacts to carry their structured next-action queue, phase counts, and human-review count, and verifies that the summary counts still match the embedded queue. This keeps stale or hand-edited completion audits from passing compatibility while omitting or misreporting the non-canonical operator handoff needed to resolve blocked fixed-gold evidence.
- Compatibility also validates roadmap completion audits against the Pydantic schema and fails closed when `roadmap_complete=true` coexists with nonzero failures, blockers, or failed checks, so a hand-edited completion flag cannot bypass the requirement-by-requirement audit evidence.
- Roadmap completion compatibility also requires next-action entries to remain actionable: each queued item must retain non-empty requirement and action text, and a completed audit cannot still carry queued next actions.
- Roadmap completion compatibility also fails closed on the inverse stale flag: `roadmap_complete=false` with zero failures, no blockers, no failed checks, and no queued next actions is rejected as internally inconsistent.
- That inverse stale-flag check now requires typed integer `fail_count` evidence rather than coercing strings, so malformed count fields cannot prove a clean-but-incomplete artifact.
- Roadmap completion compatibility also checks `roadmap_completion_blocked` and `roadmap_completion_warnings_present` warning markers against embedded check statuses, so stale summary warnings cannot make a blocked or clean audit look like a different operator state.
- Roadmap completion compatibility also reports malformed top-level audit identity fields with stable findings, keeping `audit_id` and `generated_at` as typed review-artifact provenance.
- Roadmap completion compatibility also reports malformed top-level `input_paths` provenance with a stable finding, keeping evidence path lineage as typed string-to-string data instead of generic schema-error text.
- Roadmap completion compatibility also reports malformed top-level artifact posture with a stable finding when a completion audit is not `review_gate_artifact` / `non_canonical`, keeping the final roadmap gate additive rather than canonical runtime truth.
- Roadmap completion compatibility also rejects non-boolean `roadmap_complete` values in raw JSON, preventing schema coercion from accepting string status flags as completion evidence.
- Roadmap completion compatibility also gives malformed embedded check rows a stable invalid-checks finding, so non-object entries in `checks` cannot depend only on schema error wording.
- Roadmap completion compatibility also gives malformed embedded check fields a stable finding, so non-string/blank `requirement_id` or `requirement` values, unknown status values, and malformed evidence/next-action arrays cannot feed summary counts, blockers, or review proof through stringification.
- Roadmap completion compatibility also rejects non-integer or negative raw completion summary counts, keeping `pass_count`, `warn_count`, and `fail_count` as typed audit evidence rather than coercible strings.
- Roadmap completion compatibility also rejects non-integer or negative raw next-action summary counts, keeping phase counts and human-review counts as typed operator-handoff evidence rather than coercible strings.
- Roadmap completion compatibility also rejects non-boolean `requires_human_review` values inside next-action items, keeping human-review routing as typed queue evidence instead of truthiness-coerced strings.
- Roadmap completion compatibility also gives malformed next-action queue text fields a stable finding, so non-string `requirement_id`, `action`, or `phase` values cannot depend only on schema error wording.
- Roadmap completion compatibility also gives malformed non-string `command_hint` values the same stable next-action finding, keeping optional operator commands typed when present.
- Roadmap completion compatibility also reports non-string top-level blocker ids as invalid blockers instead of stringifying them during summary comparison.
- Roadmap completion compatibility also reports non-string top-level warning markers as invalid warnings instead of stringifying them during summary comparison.
- Roadmap completion compatibility also reports non-string structured-correction evidence rows and non-string correction input paths as stable correction-evidence findings instead of reducing them to stringified path mismatches.
- `bootstrap_meta` records the scorecard artifact path, readiness status, and reason codes.
- `run_meta` records a compact `evidence_grounding_scorecard` summary.
- Deepread handoff acceptance contracts now list `evidence_grounding_scorecard.json` as an optional expected output when it is written.

### PR 6. Figure/table grounding metrics

Scope:

- incorporate visual/figure/table evidence inputs
- add figure/table gold locator evaluation

Goal:

Move beyond text-only evidence grounding.

Implementation note:

- Scorecard generation now reads `visual_evidence_ledger.json` when available.
- Added runtime proxy metrics for visual evidence entry count, linked-claim rate, unknown/unsupported visual evidence rates, visual not-allowed claim count, visual direct contradiction count, caption-only figure count, ambiguous visual panel count, table parse failure count, parsed table-cell value count, and figure/table conflict count.
- Added gold-scored metrics for figure reference precision, figure visual text accuracy, table reference precision, table-cell locator precision, table-cell value accuracy, and figure-caption link accuracy. Figure/table IDs are not enough when gold locators provide page, chunk, or quote context; the scorer now requires that locator context to match as well.
- Added bounded figure visual text evaluation through `figure_visual_text_accuracy`. When gold evidence provides `figure_id` and quote, and the visual ledger has a matching figure entry, the scorecard checks figure caption, observed text, observed elements, and allowed claims for support and routes mismatches to `FIGURE_VISUAL_MISMATCH` under the grounding checker stage.
- Added bounded semantic table evaluation through `table_cell_value_accuracy`. When gold evidence provides `table_id`, `cell_id`, and quote, the scorecard checks `visual_evidence_ledger.entries[].extracted_values` for a matching table cell value and routes mismatches to `TABLE_VALUE_MISMATCH` under the parser stage.
- `visual_evidence_ledger.json` can now surface `figure_table_conflict` entries, which the scorecard counts as `figure_table_conflict_count` and routes to `FIGURE_TABLE_CONFLICT_MISSED` under the consistency checker stage.
- `visual_evidence_ledger.json` can now surface `ambiguous_panel` entries, which the scorecard counts as `ambiguous_visual_panel_count` and routes to `WEAK_OR_AMBIGUOUS_EVIDENCE` under the grounding checker stage.
- `visual_evidence_ledger.json` can now surface linked `not_allowed_claims`, which the scorecard counts as `visual_not_allowed_claim_count` and routes to `OVERSTATED_RESULT` under the consistency checker stage, excluding entries already classified as figure/table conflicts to avoid double-counting.
- When `claimset.resolved.json` is available, linked visual `not_allowed_claims` can now produce `visual_direct_contradiction_count` through a bounded direct polarity check against the linked claim statement. These cases route to `CONTRADICTED_RESULT` under the consistency checker stage.
- When `claimset.resolved.json` is available, claim statements can now be checked against their linked evidence quote/raw_text/rationale for bounded direct polarity conflicts through `claim_evidence_direct_contradiction_count`. These cases also route to `CONTRADICTED_RESULT` under the consistency checker stage and remain proxy review signals, not gold-scored contradiction adjudication.
- The scorecard schema now reuses the same central `PaperUnderstandingFailureCode` taxonomy as claim/evidence correction records. It rejects unknown `failure_counts_by_code` / stage `failure_codes`; benchmark reports apply the same taxonomy to aggregate failure counts, and comparison reports validate failure-count comparison names against known failure codes or stages. The scorecard service also checks that every schema-level failure code has a stage-routing entry, so new failure codes cannot silently fall into `unknown`, and contract compatibility validates raw scorecard/benchmark/comparison artifacts against those taxonomy-aware schemas.
- Deepread scorecard generation passes the in-memory visual evidence ledger produced during the run.
- Benchmark comparison can now gate available visual proxy and figure/table gold metrics without turning missing gold labels into zeros.
- Full vision-level panel/element interpretation remains a later evaluator task; current PR6 work makes figure/table locator, ambiguous panel, not-allowed visual claim, direct visual contradiction, figure visual text, table-cell value, and caption-link signals visible and comparable when present.

### PR 7. Operator visibility

Scope:

- API endpoint or artifact listing
- minimal viewer summary
- UX review report

Goal:

Make grounding quality visible and actionable to the user.

Implementation note:

- Added `evidence_grounding_scorecard` to the existing artifacts API bundle/file map.
- Operators can now retrieve the scorecard through `/artifacts/{paper_id}/{run_id}/grounding-scorecard` or see it in the run artifact bundle when present.
- Added `claim_evidence_reviewed_eval_fixtures` to the same artifacts API bundle/file map, so operators can trace reviewed fixture inputs that later populate scorecard reviewed-eval metrics without treating them as accepted gold.
- Added `docs/UX_REVIEW_REPORT_grounding-scorecard-visibility.md` for the workbench scorecard visibility flow.
- Added a read-only `Evidence grounding` summary card to the Workbench artifact panel. It surfaces readiness, non-canonical review-gate status, runtime proxy grounding metrics, available gold-scored metrics, failure-code counts, and the recommended next action.
- Mock artifact bundles now include a representative `evidence_grounding_scorecard` fixture so the frontend path can render the scorecard without relying on raw JSON only.
- Added mock E2E coverage for the warning scorecard path and the failing failure-code path in `frontend/e2e/mock.spec.ts`.
- Seeded the backend E2E live artifact fixture with `evidence_grounding_scorecard.json` and added Workbench coverage that confirms the live artifact bundle renders the scorecard summary.
- `/jobs` / `/jobs/{job_id}` status payloads now project the scorecard artifact-written flag, readiness status, and reason codes from `bootstrap_meta` alongside the existing claimset/stats artifact flags.
- Added `docs/UX_REVIEW_REPORT_claim-evidence-correction-log.md` and a collapsed Workbench `Log correction case` section under the scorecard. It submits append-only claim/evidence correction records without rewriting canonical claim state.
- The correction section now reloads and displays recent correction records for the selected claim, so human review input is visible after it is saved rather than disappearing into a log file.
- Accepted eval-candidate corrections now show whether the saved case was linked to review feedback, and backend E2E covers the live Workbench submit/list loop against the FastAPI `/claim-evidence-corrections` route and JSONL-backed correction log.
- Invalid accepted correction rows can now be exported as a non-canonical `claim_evidence_correction_repair_plan.v1` handoff through FastAPI and CLI. The plan preserves line numbers, source IDs, and missing replay-lineage fields for human repair without mutating raw correction memory or canonical structured state. Roadmap audits recognize it as correction-loop handoff evidence, not replayable correction evidence, and contract compatibility validates the artifact/counts before it is used in review.

## Definition of Done for This Roadmap

The roadmap is complete when PaperPipe can:

1. run a fixed paper-understanding goldset through a candidate parser/model/prompt configuration
2. generate per-run and aggregate evidence grounding scorecards
3. report P0 metrics for claim precision, evidence support precision, locator precision, unsupported claim rate, overstatement rate, limitation recall, and method/result confusion
4. fail a candidate when P0 grounding metrics regress
5. store human claim/evidence corrections in a structured, replayable form
6. attribute failures to extractor, classifier, grounding, consistency, parser, or formatter stages where possible
7. preserve all scorecards and correction logs as additive review/eval artifacts, not replacement canonical truth
8. pass an explicit compatibility/migration review before exposing any evidence-grounding artifact as a stable external contract

## Non-Goals

Do not use this roadmap to:

- replace `docs/Lattice_v3_Master_Spec.md`
- introduce a broad generic object registry
- make every claim/evidence item part of a universal approval workflow
- treat feedback memory as stronger truth than canonical state and source evidence
- adopt external scientific skills without `config/skills_policy.yaml`
- make downstream artifacts look polished while hiding unsupported claims

## Short Operating Rule

When improving PaperPipe reading quality, start with the evidence state and scorecard.

If a change makes summaries prettier but worsens claim/evidence grounding, it is a product performance regression.
