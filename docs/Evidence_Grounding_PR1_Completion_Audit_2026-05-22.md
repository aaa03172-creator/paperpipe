# Evidence Grounding PR1 Completion Audit

Status: Review artifact
Date: 2026-05-22
Branch: `codex/evidence-grounding-performance-roadmap`

## Purpose

This audit checks the current worktree against the original PR1 objective from `docs/Evidence_Grounding_Performance_Roadmap_2026-05-22.md`:

> Create an additive `evidence_grounding_scorecard.json` schema/service/test from existing deepread artifacts without changing canonical runtime truth.

This audit is a review artifact only. It does not redefine canonical PaperPipe state, promote scorecards to truth stores, or close the broader Evidence Grounding Performance roadmap.

## PR1 Acceptance Criteria

| Requirement | Status | Evidence |
| --- | --- | --- |
| Scorecard schema exists | Done | `src/schemas/evidence_grounding_scorecard.py` defines `EvidenceGroundingScorecard`. |
| Scorecard is additive review artifact | Done | Schema fixes `layer="review_gate_artifact"` and `canonical_status="non_canonical"`. |
| Builder service exists | Done | `src/services/evidence_grounding_scorecard.py` provides `build_evidence_grounding_scorecard`, `build_evidence_grounding_scorecard_from_run_dir`, and `write_evidence_grounding_scorecard`. |
| Scorecard API route exists | Done | `POST /evidence-grounding/scorecards/build` rebuilds a non-canonical scorecard from a saved run directory and can inject an external paper-understanding gold file for eval-only gold metrics while preserving the same identity fail-closed guards as the service path. |
| Builds from existing deepread artifacts | Done | Builder reads `reader_eval.json`, `claimset_coverage.json`, `evidence_extraction_bundle.json`, `visual_evidence_ledger.json`, `acceptance_contract.json`, `quality_gate.json`, `claimset.resolved.json`, optional gold labels, and correction/review sidecars. |
| Can build from run directory without rerunning deepread | Done | `build_evidence_grounding_scorecard_from_run_dir(run_dir)` loads saved sidecars and returns a scorecard. |
| Separates runtime proxies from gold metrics | Done | Schema has `runtime_proxy_metrics` and `gold_scored_metrics`; tests assert proxy/gold separation. |
| Reports proxy metrics when gold is missing | Done | Missing gold labels leave gold metrics `not_available`; proxy metrics still populate from sidecars. |
| Gold-scored precision/recall not faked without labels | Done | `_build_missing_gold_metrics()` marks required gold metrics `not_available`; metric validation rejects `not_available` metrics with values. |
| Refuses mismatched gold identity | Done | `paper_understanding_gold.v1` labels whose `paper_id` disagrees with the run are not scored; the scorecard records `paper_understanding_gold_paper_id_mismatch` and fails readiness across service, run-local, and FastAPI external-gold build paths. |
| Filters reviewed eval fixtures by run scope | Done | Non-canonical reviewed fixtures whose source candidate `paper_id`/`run_id` disagrees with the scorecard run are skipped, recorded as `reviewed_eval_fixture_scope_mismatch`, and fail readiness so mixed review fixtures cannot masquerade as gold-like labels. |
| Detects sidecar identity mismatch | Done | Scorecard generation records warnings and reason codes when loaded input sidecars disagree on `paper_id`, `run_id`, or `doc_id`, and fails readiness for mismatched identities even when other proxy metrics look clean. |
| Missing inputs are warnings, not silent zeros | Done | Missing/malformed sidecars append warnings and reason codes; malformed sidecar test covers this path. Scorecards now also expose `input_artifact_diagnostics`, `input_artifact_coverage_rate`, `missing_input_artifact_count`, and `malformed_input_artifact_count` as explicit run-level proxy evidence. |
| Tests cover full, partial, malformed inputs | Done | `tests/test_evidence_grounding_scorecard.py` covers full input, partial input, malformed input, gold-scored paths, mismatched gold identity, reviewed fixture scope, correction loop, metadata, parser section, and figure/table visual signals. |
| Does not replace canonical runtime truth | Done | Scorecard and correction/review fixture artifacts remain non-canonical review/eval artifacts; builder is additive and does not mutate `ClaimSet` or paper truth. |

## Beyond PR1 Already Implemented

Current work also goes beyond the original PR1 scope:

- Paper understanding gold schema and validator.
- Paper understanding gold manifest contract for fixed `goldset_id` / `goldset_split` bundles, with shared service validation for relative gold paths.
- Paper understanding gold manifest builder CLI for turning validated curated records into a fixed split manifest.
- Paper understanding gold readiness checks that mark schema-valid but not-yet-eval-ready records with explicit reason codes.
- Optional `--require-ready` gates for validator and manifest-builder CLI paths, so fixed benchmark bundles can reject not-yet-ready gold records.
- FastAPI endpoints for fixed paper-understanding gold validation and fixed-split manifest building, keeping the goldset preflight/build lane API-first instead of CLI-only.
- Non-canonical paper-understanding goldset curation audit report, CLI, and FastAPI endpoint for checking ready-record coverage by split/domain/type targets before fixed-goldset comparisons are run.
- Non-canonical paper-understanding gold release-readiness audit report, CLI, and FastAPI endpoint for checking a seed/eval/holdout manifest bundle as one fixed-goldset release candidate. The gate checks required split coverage, minimum ready records per split, single `goldset_id` posture, invalid referenced gold records, and duplicate papers across splits before the bundle is used for comparisons.
- Non-canonical paper-understanding gold release package from staged review gold, with service, CLI, and FastAPI entry points. The package consumes reviewed `paper_understanding_gold_staging_manifest.v1` files, writes fixed split `paper_understanding_gold_manifest.v1` bundles, and immediately writes the `paper_understanding_gold_release_readiness.v1` gate so seed/eval/holdout release evidence can be assembled without hand-edited path wiring.
- Non-canonical paper-understanding gold release split-plan service, CLI, and FastAPI endpoint. A single ready `paper_understanding_gold_staging_manifest.v1` can now be deterministically split into seed/eval/holdout staging manifests plus release-package build items, reducing the manual handoff between staged curated gold and the fixed-gold release package builder.
- Non-canonical split-plan-to-release-package service, CLI, and FastAPI endpoint. A saved `paper_understanding_gold_release_split_plan.v1` can now publish the fixed seed/eval/holdout manifests, linked release-readiness report, and `paper_understanding_gold_release_package.v1` without hand-copying `split_manifests`.
- The release package now preserves `source_split_manifests` lineage for each staged seed/eval/holdout input. Completion audit checks use that lineage when present, so a package whose source split manifest outputs no longer match the package's fixed manifest list, or whose current source staging manifest no longer rebuilds the same fixed manifest, cannot support `roadmap_complete=true`.
- Non-canonical paper-understanding gold candidate draft service, CLI, and FastAPI endpoints for reviewed claim/evidence fixtures, preserving readiness diagnostics for human curation before accepted gold promotion.
- Non-canonical paper-understanding gold candidate draft service, CLI, and FastAPI endpoints for accepted `teacher_verification.v1` outputs, preserving grounded claim/evidence spans as curation inputs while keeping missing method/result/limitation/citation coverage visible through readiness diagnostics.
- One-step teacher-verification curation package service, CLI, and FastAPI endpoint. It writes non-canonical candidate drafts from legacy `teacher_verification.v1` files and immediately emits a curation report, so accepted teacher outputs become an actionable review queue without being promoted to fixed gold.
- Structured candidate-draft patch service, CLI, and FastAPI endpoint. Reviewers can apply curated citation, paper type, domain tags, statements, and figure/table inventory to a non-canonical candidate draft, then receive a patch result with before/after readiness and the patched draft path. This creates a typed bridge from curation tasks to the existing ready-only staging lane without promoting unreviewed drafts into accepted gold.
- Candidate-draft patch-template service, CLI, and FastAPI endpoint. It turns a candidate draft plus its open readiness tasks into a valid `PaperUnderstandingGoldCandidateDraftPatchRequest` scaffold prefilled with current values and reviewer/output metadata, so reviewers can edit structured fields instead of hand-authoring patch JSON from scratch.
- Batch patch-template manifest service, CLI, and FastAPI endpoint. It builds one patch-template JSON file per candidate draft in a teacher-verification curation package, plus a non-canonical manifest with template count, open task count, and readiness summary.
- Batch patch-template apply service, CLI, and FastAPI endpoint. It consumes edited patch-template files or a patch-template manifest, applies each embedded `PaperUnderstandingGoldCandidateDraftPatchRequest`, writes one patch-result JSON per draft, and emits a non-canonical patch-result manifest with readiness counts. This gives reviewers a batch handoff from edited templates into the existing progress/staging lane without promoting any result into accepted gold.
- Candidate-draft curation progress audit service, CLI, and FastAPI endpoint. It joins a teacher-verification curation package with optional patch-template manifests/templates, patch results, and staged gold files, reporting each paper as `not_started`, `templated`, `patched_not_ready`, `ready_to_stage`, or `staged` with remaining task counts.
- Curation task export service, CLI, and FastAPI endpoint. It flattens current progress `open_tasks` into a non-canonical `paper_understanding_gold_curation_task_export.v1` JSON artifact and optional CSV reviewer handoff, keeping remaining human curation work explicit without promoting it into accepted gold.
- Reviewer handoff package service, CLI, and FastAPI endpoint. It creates teacher-derived drafts, the curation package, patch-template manifest, progress report, task export JSON, and task export CSV in one non-canonical `paper_understanding_gold_reviewer_handoff_package.v1`, so reviewers can start from a single package while fixed-gold acceptance still requires edited patches and staging.
- Reviewer handoff apply package service, CLI, and FastAPI endpoint. It consumes a saved reviewer handoff package after human patch-template edits, applies those templates into patch results, and refreshes progress/task-export sidecars in one non-canonical `paper_understanding_gold_reviewer_handoff_apply_package.v1`, keeping the ready-to-stage signal explicit without promoting patched drafts into accepted gold.
- Reviewer handoff apply now has an opt-in edited-template guard (`--require-edited` / `require_edited=true`) that refuses to write the apply package when all patch templates are still scaffold values or unedited results remain. Roadmap next-action command hints use this guard for the current blocked handoff path, so automation stops before creating another unedited apply package.
- Generated reviewer handoff guides now include `--require-edited` in their apply command block, keeping the human-facing guide aligned with the fail-closed apply path.
- Reviewer handoff stage package service, CLI, and FastAPI endpoint. It consumes a ready reviewer handoff apply package, stages ready patched drafts through the existing non-canonical staging manifest, and refreshes progress/task-export sidecars in `paper_understanding_gold_reviewer_handoff_stage_package.v1`, closing the reviewer loop from edited templates to staged review gold without bypassing release-readiness gates.
- Reviewer handoff release-prep package service, CLI, and FastAPI endpoint. It consumes a reviewer handoff stage package, writes a release split plan, and builds the fixed manifest/release-readiness package when split coverage is sufficient, returning `paper_understanding_gold_reviewer_handoff_release_prep_package.v1` as a non-canonical review gate for benchmark preparation.
- Non-canonical candidate-draft curation audit, CLI, and FastAPI endpoint that summarize readiness blockers, statement/visual/table counts, and next actions before any draft is staged as `paper_understanding_gold.v1`.
- Non-canonical staging service, CLI, and FastAPI endpoint from readiness-passing candidate drafts to `paper_understanding_gold.v1` files under review storage, not `goldset/accepted`.
- Non-canonical staging-from-patch-results service, CLI, and FastAPI endpoint. It consumes patch-result files, directories, or a patch-result manifest, extracts ready patched candidate drafts, and runs the same ready-only staging gate. This closes the typed reviewer path from edited patch template to patch result to staged `paper_understanding_gold.v1` review file without bypassing readiness checks.
- Paper-understanding gold validation and fixed manifest building now accept `paper_understanding_gold_staging_manifest.v1` as an input source, expanding it to the staged review gold files while skipping the non-gold staging sidecar during directory scans. This lets a reviewed/staged gold batch publish directly into a fixed `paper_understanding_gold_manifest.v1` bundle without hand-copying staged paths.
- Gold scoring for claim precision/recall, evidence support, locator precision, unsupported rate, limitation/gap recall, method/result confusion, overstatement/contradiction labels, metadata match, parser section accuracy, and figure/table locator context.
- Bounded table-cell semantic scoring through `table_cell_value_accuracy`, using gold `table_id`/`cell_id`/quote locators against visual evidence extracted table values and routing mismatches to `TABLE_VALUE_MISMATCH`.
- Bounded figure visual text scoring through `figure_visual_text_accuracy`, using gold `figure_id`/quote locators against visual evidence captions, observed text/elements, and allowed claims, routing mismatches to `FIGURE_VISUAL_MISMATCH`.
- Ambiguous visual panel proxy scoring through `ambiguous_visual_panel_count`, routing `visual_evidence_ledger` `ambiguous_panel` entries to `WEAK_OR_AMBIGUOUS_EVIDENCE` under the grounding checker stage.
- Visual not-allowed claim proxy scoring through `visual_not_allowed_claim_count`, routing linked `not_allowed_claims` entries to `OVERSTATED_RESULT` under the consistency checker stage while avoiding duplicate figure/table conflict counts.
- Direct visual contradiction proxy scoring through `visual_direct_contradiction_count`, using bounded polarity conflicts between linked claim statements and visual `not_allowed_claims` to route `CONTRADICTED_RESULT` under the consistency checker stage.
- Direct claim/evidence contradiction proxy scoring through `claim_evidence_direct_contradiction_count`, using bounded polarity conflicts between a claim statement and its linked evidence quote/raw_text/rationale to route `CONTRADICTED_RESULT` under the consistency checker stage without requiring gold labels.
- Product-level failure taxonomy and stage attribution. Scorecards, benchmark reports, comparison reports, and claim/evidence correction records now share the central `PaperUnderstandingFailureCode` taxonomy. `EvidenceGroundingScorecard` rejects unknown `failure_counts_by_code` / stage `failure_codes`, benchmark reports apply the same taxonomy to `aggregate_failure_counts_by_code`, comparison reports validate `failure_count_comparisons` against known failure codes/stages, the scorecard service fails at import time if the stage-routing map does not cover the schema-level taxonomy, and contract compatibility rejects raw scorecard, benchmark, or comparison artifacts that fail schema validation.
- Claim/evidence correction API, eval-candidate import/review queue, reviewed fixture packaging, and feedback linkage.
- Batch benchmark runner with CLI and FastAPI entry points, comparison report, FastAPI comparison endpoint, failure/stage aggregation, correction reuse summary, explicit metric gates, `p0-gold` gate preset, and additive threshold checks for absolute candidate-quality policy.
- Benchmark reports now surface embedded scorecard readiness as aggregate pass/warn/fail counts, a `scorecard_not_ready_candidate_ids` list, and top-level warnings when scorecard readiness failures are present, so failed per-run scorecards cannot disappear inside averaged metrics.
- Benchmark run packages now aggregate split benchmark scorecard readiness through package-level pass/warn/fail counts, scoped `benchmark_id:candidate_id` not-ready candidate IDs, and package warnings. This keeps seed/eval/holdout package summaries from hiding a failed or warning embedded scorecard.
- Fixed-goldset comparison-suite packages now preserve baseline/candidate run-package scorecard readiness context, including explicit-field presence, pass/warn/fail counts, not-ready candidate IDs, and warnings for stale or non-passing run packages. This keeps run-package readiness evidence visible when split benchmark packages are promoted into comparison-suite packages.
- Threshold-adoption packages now preserve the comparison-suite package's run-package scorecard readiness context, including explicit-field presence, pass/warn/fail counts, not-ready candidate IDs, and warnings for stale suite-package context. This keeps threshold adoption from hiding whether its package-wide comparison evidence came from readiness-aware benchmark handoffs.
- Roadmap completion's package-wide threshold-adoption gate now also requires that threshold package scorecard context fields are explicitly present, that the source suite package/run-package readiness context was present, and that baseline/candidate package scorecard failure counts are zero. This prevents final completion from relying on stale threshold packages or failed scorecard context even when split adoption counts look ready.
- Benchmark comparison now treats `scorecard_readiness_fail_count > 0` as a benchmark context failure, so a candidate cannot pass comparison when any embedded scorecard failed identity/readiness checks even if aggregate metric values look acceptable.
- Roadmap completion audit now also fails the `per_run_and_aggregate_scorecards` check when a benchmark report contains failed embedded scorecards, so stale comparison reports cannot hide scorecard readiness failures at the final audit step.
- Roadmap completion audit now requires benchmark reports to explicitly contain scorecard readiness fields before treating failed-scorecard count as proven zero, so older benchmark artifacts cannot pass by relying on schema defaults.
- Contract compatibility audit now also rejects `evidence_grounding_benchmark.v1` artifacts that omit scorecard readiness fields, so stale benchmark reports cannot pass external-contract review before final completion.
- Contract compatibility audit now also rejects stale benchmark manifest package counts. `manifest_count` must match `benchmark_manifest_paths`; when embedded benchmark manifests are present, `manifest_count` and `item_count` must match the embedded manifests and their items.
- Contract compatibility audit now also resolves benchmark manifest package sidecars and rejects stale linked manifest evidence. A manifest package cannot pass external-contract review if its manifest or item counts disagree with the linked `evidence_grounding_benchmark_manifest.v1` files, even when embedded manifest copies are absent.
- Contract compatibility audit now also rejects `evidence_grounding_benchmark_run_package.v1` artifacts that omit package-level scorecard readiness fields, so stale split-run packages cannot pass external-contract review by exposing only `scorecard_count`.
- Contract compatibility audit now also rejects stale benchmark run package counts. `report_count` must match `benchmark_report_paths`; when embedded benchmark reports are present, `item_count`, `scorecard_count`, readiness pass/warn/fail counts, and not-ready candidate IDs must match the embedded reports.
- Contract compatibility audit now also resolves benchmark run package report sidecars and rejects stale linked benchmark evidence. A run package cannot pass external-contract review if its aggregate item, scorecard, scorecard-readiness, or not-ready candidate summaries disagree with the linked `evidence_grounding_benchmark.v1` report files.
- Contract compatibility audit now also rejects `evidence_grounding_fixed_goldset_comparison_suite_package.v1` artifacts that omit run-package scorecard readiness context, so stale suite packages cannot pass external-contract review by exposing only suite counts.
- Contract compatibility audit now also rejects stale comparison-suite package summary counts. `suite_count` must match the comparison-suite, comparison-report, and run-readiness path lists; when embedded suite payloads are present, package pass/fail and run-readiness failure counts must match those embedded suites.
- Contract compatibility audit now also resolves comparison-suite package baseline/candidate run-package sidecars and rejects stale linked run-package readiness context. A suite package cannot pass external-contract review if its preserved scorecard readiness pass/warn/fail counts or not-ready candidate IDs disagree with the linked `evidence_grounding_benchmark_run_package.v1` files.
- Contract compatibility audit now also rejects stale threshold-calibration recommendation counts. Top-level `report_count`, recommendation `report_count`, `available_count`, `observed_values`, and `source_reports` must agree, so hand-edited calibration artifacts cannot overstate how much benchmark evidence supports a proposed threshold.
- Contract compatibility audit now also rejects stale threshold-adoption review summaries. Review `pass_count`, `warn_count`, `fail_count`, `blockers`, and `production_threshold_ready` must match the embedded checks, so a hand-edited adoption review cannot appear production-ready while its summary and checks disagree.
- Contract compatibility audit now also rejects stale comparison decision summaries. `decision.passed`, `compared_metric_count`, `failed_checks`, and `regressions` must match the embedded metric comparisons, stage comparisons, failure-count comparisons, threshold checks, and benchmark context, so a hand-edited comparison cannot hide failed gates while still passing schema validation.
- Contract compatibility audit now also rejects `evidence_grounding_threshold_adoption_review_package.v1` artifacts that omit comparison-suite package scorecard context, so stale threshold-adoption packages cannot pass external-contract review by exposing only adoption counts.
- Contract compatibility audit now also rejects stale threshold-adoption package summary counts. `comparison_suite_count` must match threshold-checked comparison paths, adoption-review paths, and embedded adoption reviews when present; production-threshold ready/blocked counts must match the embedded review statuses.
- Contract compatibility audit now also resolves threshold-adoption package review sidecars and rejects stale linked review evidence. A package cannot pass external-contract review solely from embedded adoption summaries if the linked `evidence_grounding_threshold_adoption_review.v1` files have drifted readiness status, stale counts, blockers, or invalid review summaries.
- Contract compatibility generated from a threshold-adoption package now includes the linked baseline/candidate benchmark run packages and their benchmark-manifest packages, and final external-contract readiness requires benchmark-manifest, benchmark-run, comparison-suite-package, and threshold-adoption-package schema coverage whenever threshold-package evidence is supplied.
- Contract readiness now rejects stale linked compatibility summaries before allowing external readiness. `evidence_grounding_contract_compatibility.v1` artifact/pass/warn/fail counts, warning markers, item statuses, item findings, and `external_contract_ready=false` posture must match embedded compatibility items before a readiness report or final completion audit can rely on it.
- Roadmap completion external-contract readiness now also requires the linked compatibility report to cover the actual artifact paths supplied to the completion audit. Schema-family coverage alone is no longer enough if the compatibility report reviewed a different threshold calibration, comparison, benchmark, release, package, or correction export artifact.
- Roadmap completion audit now also rejects stale contract-readiness summaries. `evidence_grounding_contract_readiness.v1` pass/warn/fail counts, blockers, warning markers, artifact count, and `external_contract_ready` must match embedded checks and the linked compatibility report before the external-contract requirement can pass.
- Threshold calibration review artifact, CLI, and FastAPI endpoint that summarize observed saved-report metric values into conservative threshold recommendations without automatically changing production policy.
- Threshold calibration can now be built directly from a typed fixed-goldset `comparison_suite.json`, with service, CLI, and FastAPI entry points. By default it calibrates from the suite's candidate benchmark report, with an explicit option to include the baseline report, reducing manual path wiring between fixed-goldset comparison evidence and threshold review.
- Comparison API/CLI and fixed-goldset suite CLI paths can now take an explicit threshold calibration report and apply available recommendations as threshold checks, with manual threshold overrides still possible.
- Comparison can now be rerun directly from a typed fixed-goldset `comparison_suite.json`, with service, CLI, and FastAPI entry points. This lets operators build calibration after an initial suite run, then produce a threshold-checked comparison report for threshold adoption review without rebuilding the benchmark reports or hand-copying baseline/candidate paths.
- Threshold adoption review artifact, CLI, and FastAPI endpoint that ties calibration, threshold-checked comparison output, fixed-goldset run readiness, human approval, and explicit opt-in into a non-canonical production-threshold readiness decision without mutating runtime threshold policy. The review can now resolve comparison and run-readiness report paths from `comparison_suite.json`, keeping the fixed-goldset suite as the main operator handoff. It also requires calibrated threshold values for every P0 grounding metric before `production_threshold_ready=true`.
- Threshold adoption review can now be built as a package directly from `comparison_suite.json`, with service, CLI, and FastAPI entry points. The package writes a calibration report, writes a threshold-checked comparison report, then writes the adoption review while still requiring explicit human approval and opt-in before `production_threshold_ready=true`.
- First-pass evidence-grounding contract compatibility audit artifact, CLI, and FastAPI endpoint. The audit checks supported scorecard/benchmark/comparison/threshold-calibration/threshold-adoption/fixed-goldset-suite schema versions, confirms review-gate/non-canonical posture, and validates raw scorecard, benchmark, and comparison artifacts against their schemas before any artifact is considered for external integration; it deliberately leaves `external_contract_ready=false`.
- Contract compatibility now also recognizes `claim_evidence_eval_candidate_export.v1` as a supported non-canonical review artifact. It validates export schema, candidate-count consistency, replayable candidate evidence, explicit source-log diagnostic fields, and invalid-row diagnostic count consistency so stale or non-replayable correction exports cannot pass contract review through schema defaults.
- Roadmap completion now requires external-contract coverage for `claim_evidence_eval_candidate_export.v1` whenever the structured correction evidence is supplied as that JSON export artifact. The comparison-suite and threshold-adoption completion package builders automatically include that export in their generated contract compatibility inputs, while JSONL correction logs remain structured correction evidence without widening the external contract schema family.
- Roadmap completion now also loads `claim_evidence_eval_candidate_export.v1` correction evidence as a typed review artifact for the additive/non-canonical posture check, so JSON correction exports are visible in `additive_noncanonical_artifacts` evidence rather than only counted by the structured-correction gate.
- The structured correction completion check now reports `correction_evidence_kind` and `correction_evidence_posture`, distinguishing raw JSONL correction memory (`raw_memory_noncanonical`) from exported eval-candidate review artifacts (`review_gate_artifact_non_canonical`) without changing the raw correction-log schema.
- The eval-candidate export CLI and FastAPI route now expose an explicit replayability guard (`--require-replayable` / `require_replayable=true`) that fails when the export has invalid source rows, stale candidate counts, no replayable candidates, or candidates missing before/after evidence refs plus parser/model/prompt/profile lineage. Diagnostic exports are still allowed by default, but automation can now stop before handing a non-replayable artifact to roadmap completion.
- Eval-review intake imports now expose the same opt-in replayability guard on the CLI and FastAPI import routes, preventing automation from turning a zero-candidate or source-invalid export into an empty review-intake manifest while preserving the default permissive review workflow.
- Structured-correction next-action command hints now include `--require-replayable` when pointing operators at `export_claim_evidence_eval_candidates.py`, so the suggested repair/export command fails early instead of producing a zero-candidate or source-invalid artifact that will fail later in roadmap completion.
- Claim/evidence eval-candidate exports now include bounded source-log diagnostics for total, valid, and invalid source records, skipped non-eval/filter/limit counts, and invalid row line numbers/error classes. Roadmap completion treats declared invalid source rows as blocking correction evidence, so malformed correction memory remains visible after export.
- The roadmap completion request schemas and the three audit CLI help surfaces now describe `--correction-log` / `correction_log_path` as accepting either raw `ClaimEvidenceCorrectionCase` JSONL or a `claim_evidence_eval_candidate_export.v1` JSON review artifact, keeping operator-facing contracts aligned with the implemented correction-evidence gate.
- Structured-correction next actions now distinguish missing correction evidence from supplied but malformed/non-replayable evidence. When a raw correction log is present but invalid, the completion audit points operators to repair or re-export accepted eval records with before/after evidence refs and parser/model/prompt/profile lineage rather than repeating the generic "provide evidence" action.
- Structured-correction evidence now also records `correction_evidence_path`, and raw correction-log next-action command hints include `--log-path <supplied_log_path>` when a non-replayable raw log was explicitly supplied. This keeps the repair/re-export action executable without making operators rediscover which log failed.
- Contract compatibility now rejects stale roadmap-completion audit artifacts whose structured-correction evidence omits `correction_evidence_path`, so externally reviewed completion artifacts cannot hide which raw correction log or export artifact the correction gate evaluated.
- Contract compatibility also rejects roadmap-completion audit artifacts whose structured-correction `correction_evidence_path` lacks a matching `input_paths.correction_log_path` or disagrees with it, preventing a completion report from externally reviewing one correction evidence path while declaring another or omitting the declared input.
- Contract compatibility also rejects roadmap-completion audit artifacts whose human-readable bare structured-correction evidence path disagrees with the keyed `correction_evidence_path`, so display evidence and machine-readable trace evidence stay aligned.
- Contract compatibility now rejects roadmap-completion audit artifacts whose structured-correction evidence omits `valid_count` / `invalid_count`, reports non-integer or negative counts, or carries count/status mismatches in either direction: a passing check with `valid_count <= 0` or `invalid_count != 0`, or a failing check with `valid_count > 0` and `invalid_count = 0`. This keeps correction replayability counts aligned with the check status and next-action logic.
- Contract compatibility now also verifies roadmap-completion headline `pass_count`, `warn_count`, `fail_count`, and `blockers` against the embedded check statuses for incomplete reports as well as complete reports. Stale artifacts can no longer hide failed checks by editing only the summary counts or blocker list.
- Contract compatibility now rejects stale roadmap-completion audit artifacts whose structured-correction check has evidence but omits `correction_evidence_kind` or `correction_evidence_posture`, keeping completion-review artifacts aligned with the raw-memory versus review-artifact boundary.
- Contract compatibility now also validates the controlled taxonomy and allowed pairings for roadmap-completion correction evidence kind/posture values. A completion audit cannot pass compatibility if it labels correction evidence with arbitrary values such as `paper_truth` / `canonical` or mismatches a raw correction log with a review-gate posture.
- Contract compatibility now rejects stale `evidence_grounding_scorecard.v1` artifacts that omit `input_artifact_diagnostics` or `runtime_proxy_metrics.malformed_input_artifact_count`, so older scorecards cannot appear compatible merely through schema defaults.
- Contract compatibility now also requires scorecard `input_artifact_diagnostics` to cover all four core scorecard inputs (`reader_eval.json`, `claimset_coverage.json`, `evidence_extraction_bundle.json`, and `visual_evidence_ledger.json`) as core diagnostics, so token or partial diagnostics cannot hide missing deepread evidence.
- Contract compatibility now requires the three scorecard input-health runtime proxy metrics (`input_artifact_coverage_rate`, `missing_input_artifact_count`, and `malformed_input_artifact_count`) and verifies their values against the core input diagnostics, so stale scorecards cannot report silent-zero input health.
- Benchmark aggregation and comparison now preserve `malformed_input_artifact_count` as a lower-is-better runtime proxy metric. A candidate that introduces malformed core scorecard inputs can fail comparison even if semantic grounding metrics are otherwise unchanged.
- Contract compatibility also rejects stale `evidence_grounding_benchmark.v1` artifacts that omit aggregate `malformed_input_artifact_count`, keeping the instrumentation-health signal explicit after scorecards are rolled up into benchmark reports.
- Contract compatibility now requires benchmark artifacts to carry all three aggregate input-health runtime proxy metrics (`input_artifact_coverage_rate`, `missing_input_artifact_count`, and `malformed_input_artifact_count`) and, when embedded scorecards are present, verifies the aggregate values and item counts against those scorecards. Benchmark rollups therefore cannot drop or stale-copy scorecard input-health evidence after aggregation.
- Roadmap completion audit now requires both baseline and candidate benchmark reports to expose an available aggregate `malformed_input_artifact_count`, so completion cannot be inferred from generic aggregate metric presence while this input-health signal is missing.
- Workspace completion inventory now reports declared and missing paper-id identity counts for complete run directories. It prefers scorecard/run metadata when present, but can use existing deepread sidecar `paper_id` fields as fallback non-canonical identity evidence, so opaque run directories are distinguished from curated-gold gaps.
- Workspace completion inventory now also includes bounded ready-gold, declared-run, and matched-run paper-id samples. These samples keep blocked audits operator-actionable without promoting workspace inventory into canonical fixed-gold truth.
- Workspace completion inventory now requires all required run sidecars to be parseable JSON before a run directory is counted as ready. Malformed or unreadable required sidecars are reported through `ready_run_required_artifact_error_count` and produce a regeneration next action, so file presence alone cannot satisfy reusable run-evidence proof.
- Roadmap completion next-action ordering now refines the generic fixed-gold release-readiness blocker using workspace handoff evidence. When a reviewer handoff package exists but no ready apply/stage/release-prep package exists, the first queued action names the concrete edit/apply or unblock/stage/prep step instead of saying only to curate ready gold.
- Workspace completion inventory now treats reviewer-handoff apply/stage readiness counters as typed JSON integers rather than coercible strings. Malformed count fields are reported as malformed package counts and keep apply/stage packages blocked, so stringified handoff summaries cannot advance the fixed-gold next-action queue.
- Workspace completion inventory now applies the same typed-count rule to reviewer-handoff release-prep packages. A release-prep package is ready only when `release_ready_candidate` and `release_ready` are true and `staged_count` / `split_count` are positive JSON integers; malformed counts are reported and keep the release-prep step blocked.
- Workspace completion inventory now also reuses the release artifact raw count-consistency checks before counting split plans, release-readiness reports, or release packages as valid or ready, so stringified or mismatched release counts cannot be promoted through Pydantic coercion during the live workspace scan.
- Workspace completion inventory now also requires the linked release-readiness sidecar for a release package to pass those raw count-consistency checks before incrementing `consistent_gold_release_package_count`; the release-package next action now keys off consistent package count rather than embedded package readiness alone.
- Contract compatibility now rejects stale `evidence_grounding_roadmap_completion_audit.v1` artifacts that omit `next_actions`, `next_action_phase_counts`, or `human_review_next_action_count`, or whose phase/human-review counts no longer match the embedded next-action queue, so blocked completion audits cannot appear externally reviewable while hiding or misreporting their operator handoff.
- Contract compatibility also validates roadmap completion audit artifacts against their Pydantic schema and rejects false-complete edits where `roadmap_complete=true` coexists with nonzero failures, blockers, or failed checks.
- Roadmap completion compatibility now also rejects malformed next-action queue entries with missing action text or requirement ids, and rejects `roadmap_complete=true` artifacts that still carry queued next actions.
- Roadmap completion compatibility now also rejects false-incomplete edits where `roadmap_complete=false` coexists with zero failures, no blockers, no failed checks, and no queued next actions.
- Roadmap completion compatibility now requires typed integer `fail_count` evidence before emitting that false-incomplete finding, so a string value such as `"0"` is rejected as an invalid count but not coerced into proof that the audit has no failures.
- Roadmap completion compatibility now verifies the builder-owned warning markers against embedded check statuses: blocked audits must carry `roadmap_completion_blocked`, audits with warn-status checks must carry `roadmap_completion_warnings_present`, and clean audits cannot carry those stale markers.
- Roadmap completion compatibility now also reports stable identity/provenance findings when top-level `audit_id` is missing/non-string/blank or `generated_at` is not a parseable timestamp string, so review artifact identity does not depend only on schema-validation wording.
- Roadmap completion compatibility now also reports a stable invalid-input-paths finding when top-level `input_paths` provenance is not a string-to-string mapping, so malformed evidence path lineage cannot rely only on schema-validation wording.
- Roadmap completion compatibility now also reports a stable invalid-posture finding when the artifact is not `review_gate_artifact` / `non_canonical`, keeping the final completion gate visibly non-canonical.
- Roadmap completion compatibility now rejects non-boolean `roadmap_complete` values in the raw JSON payload, so strings such as `"false"` cannot rely on schema coercion and weaken the completion signal.
- Roadmap completion compatibility now reports a stable invalid-checks finding when the top-level `checks` list contains non-object values, so malformed embedded check rows cannot rely only on schema-validation wording.
- Roadmap completion compatibility now also reports a stable malformed-check-item finding when embedded check rows have non-string/blank `requirement_id` or `requirement` values, unknown status values, or malformed evidence/next-action arrays, so summary counts, blockers, and review proof cannot be derived from malformed check fields.
- Roadmap completion compatibility now also rejects non-integer or negative raw `pass_count`, `warn_count`, and `fail_count` values instead of coercing strings such as `"13"`.
- Roadmap completion compatibility now also rejects non-integer or negative raw `next_action_phase_counts` and `human_review_next_action_count` values instead of coercing strings such as `"12"`.
- Roadmap completion compatibility now also rejects next-action items whose `requires_human_review` value is not a JSON boolean, so strings such as `"false"` cannot be counted through truthiness.
- Roadmap completion compatibility now also emits a stable malformed next-action finding when queue item text fields such as `requirement_id`, `action`, or `phase` are not strings, rather than relying only on schema-validation error wording.
- Roadmap completion compatibility now also emits that stable malformed next-action finding when optional `command_hint` is present but not a string, preserving command hints as typed operator guidance.
- Roadmap completion compatibility now also reports a stable invalid-blockers finding when the top-level `blockers` list contains non-string values, keeping blocker ids typed instead of stringified.
- Roadmap completion compatibility now also reports a stable invalid-warnings finding when the top-level `warnings` list contains non-string values, keeping completion warning markers typed instead of stringified.
- Roadmap completion compatibility now also reports stable structured-correction findings for non-string correction evidence rows and non-string `input_paths.correction_log_path`, so malformed correction evidence cannot pass as only a path mismatch after stringification.
- Contract compatibility now also recognizes `paper_understanding_gold_release_readiness.v1` and `paper_understanding_gold_release_package.v1` as supported review-gate artifacts. Roadmap completion requires contract coverage for the gold release-readiness schema, and additionally requires gold release-package schema coverage whenever a release package is supplied to the completion audit.
- Contract compatibility now rejects internally inconsistent fixed-gold release artifacts. Release-readiness reports must keep headline manifest/item/ready/invalid counts aligned with split summaries and cannot claim `release_ready=true` while carrying blockers, invalid items, missing splits, or non-passing splits. Split plans must keep ready-input counts, split names, staged split items, and release-ready-candidate status aligned. Release packages must keep their manifest list, source split-manifest lineage, and embedded release-readiness counts aligned.
- Contract compatibility now also resolves a release package's linked `release_readiness_report_path` sidecar. Package-only compatibility cannot pass if the linked readiness payload, manifest count, or readiness manifest paths drift away from the package envelope, even when the embedded readiness copy still looks internally valid.
- Contract compatibility now also resolves reviewer-handoff package/apply/stage `curation_task_export_path` sidecars. Handoff package compatibility cannot pass if the linked task export has stale paper/open task counts, invalid task-export summaries, or a full typed payload that differs from the embedded copy. Apply and stage package compatibility now also reject linked task-export sidecars whose open-task count, summary counts, or full typed payload drift away from the package envelope.
- Contract compatibility now also resolves reviewer-handoff apply-package `reviewer_handoff_package_path` sidecars. Apply-package compatibility cannot pass if the linked `paper_understanding_gold_reviewer_handoff_package.v1` file drifts from apply result counts or has stale handoff package summaries.
- Contract compatibility now also resolves reviewer-handoff apply-package `patch_result_manifest_path` sidecars. Apply-package compatibility cannot pass if the linked `paper_understanding_gold_candidate_draft_patch_result_manifest.v1` file drifts from package result/readiness/edit counts, patch-result path counts, or a fully embedded typed manifest payload.
- Contract compatibility now also resolves reviewer-handoff apply-package `curation_progress_report_path` sidecars. Apply-package compatibility cannot pass if the linked `paper_understanding_gold_candidate_draft_curation_progress.v1` file drifts from package draft/result, ready-to-stage, or remaining-task counts; timestamp-only embedded/linked progress differences are ignored so regenerated sidecars are not treated as semantic drift.
- Contract compatibility now also resolves reviewer-handoff stage-package `reviewer_handoff_apply_package_path` sidecars. Stage-package compatibility cannot pass if the linked `paper_understanding_gold_reviewer_handoff_apply_package.v1` file has insufficient ready-to-stage records, stale not-ready counts, or remaining-task counts that drift from the stage envelope.
- Contract compatibility now also resolves reviewer-handoff stage-package `reviewer_handoff_package_path` sidecars. Stage-package compatibility cannot pass if the linked `paper_understanding_gold_reviewer_handoff_package.v1` file has stale source draft counts or internally inconsistent handoff package summaries.
- Contract compatibility now also resolves reviewer-handoff stage-package `curation_progress_report_path` sidecars. Stage-package compatibility cannot pass if the linked `paper_understanding_gold_candidate_draft_curation_progress.v1` file drifts from package staged, completion, or remaining-task counts; timestamp-only embedded/linked progress differences are ignored.
- Contract compatibility now also resolves reviewer-handoff stage-package `staging_manifest_path` sidecars. Stage-package compatibility cannot pass if the linked `paper_understanding_gold_staging_manifest.v1` file drifts from the package staged count, staged-path count, or fully embedded typed staging manifest payload.
- Contract compatibility now also resolves reviewer-handoff release-prep `split_plan_path` sidecars. Release-prep compatibility cannot pass if the linked `paper_understanding_gold_release_split_plan.v1` file drifts from package staged/split/candidate counts or from a fully embedded typed split-plan payload.
- Contract compatibility now also resolves reviewer-handoff release-prep `release_package_path` sidecars. Release-prep compatibility cannot pass if the linked `paper_understanding_gold_release_package.v1` file drifts from package split/release-ready summaries or from a fully embedded typed release-package payload.
- Contract compatibility now also resolves reviewer-handoff release-prep `release_readiness_report_path` sidecars. Release-prep compatibility cannot pass if the linked `paper_understanding_gold_release_readiness.v1` file drifts from package split/release-ready summaries or from a fully embedded typed readiness payload.
- Contract compatibility now also resolves reviewer-handoff release-prep `reviewer_handoff_stage_package_path` sidecars. Release-prep compatibility cannot pass if the linked `paper_understanding_gold_reviewer_handoff_stage_package.v1` file drifts from package staged count, completion, remaining-task readiness, or the stage package's own linked sidecar checks.
- Contract compatibility now also resolves reviewer-handoff release-prep `staging_manifest_path` sidecars. Release-prep compatibility cannot pass if the linked `paper_understanding_gold_staging_manifest.v1` file drifts from package staged count or staged-path count.
- Contract compatibility now also recognizes `paper_understanding_gold_release_split_plan.v1` as a supported non-canonical review artifact. Workspace inventory reports split-plan count, valid split-plan count, ready split-plan count, and invalid split-plan count, so release handoff plans do not appear as opaque JSON files.
- Contract compatibility can now be audited directly from a typed fixed-goldset `comparison_suite.json`, with service, CLI, and FastAPI entry points. The suite path resolves baseline/candidate benchmark reports, comparison report, run-readiness report, optional threshold calibration/adoption artifacts, and embedded benchmark scorecards, reducing manual artifact-list assembly before external-contract review.
- Second-stage evidence-grounding contract readiness audit artifact, CLI, and FastAPI endpoint. The audit consumes a compatibility report and keeps `external_contract_ready=false` unless migration review, backfill review, public contract documentation, explicit human approval, and explicit opt-in evidence are all present.
- Contract readiness can now be audited as a package directly from `comparison_suite.json`, with service, CLI, and FastAPI entry points. The package writes the suite-derived compatibility report first, then runs the existing migration/backfill/public-contract/approval readiness gate without self-promoting external contract status.
- Roadmap completion audit artifact, CLI, and FastAPI endpoint. The audit maps the roadmap Definition of Done to current fixed-goldset, benchmark, comparison, threshold, contract, correction-log, and typed candidate-configuration evidence, and leaves `roadmap_complete=false` when any required proof is missing.
- Roadmap completion audit can now resolve baseline/candidate benchmark reports, the comparison report, and run-readiness report directly from `comparison_suite.json`, reducing manual path wiring for real fixed-goldset runs. The fixed-goldset completion check now also requires that suite to be loadable, non-canonical, and path-consistent with the audited reports.
- Roadmap completion audit now requires paper-understanding gold release-readiness evidence before `roadmap_complete=true`. A candidate comparison suite alone is not enough unless the seed/eval/holdout fixed-goldset bundle has passed its non-canonical release-readiness gate.
- Roadmap completion can now be audited as a package directly from `comparison_suite.json`, with service, CLI, and FastAPI entry points. The package writes threshold calibration, threshold-checked comparison, threshold adoption review, suite-derived contract compatibility, contract readiness, optional gold release-readiness from seed/eval/holdout manifest paths, and the final completion audit in one call, while preserving the gold-release, correction-log, P0-threshold, migration/backfill/public-contract, approval, and opt-in blockers.
- Roadmap completion audit and the comparison-suite package can now consume a typed `paper_understanding_gold_release_package.v1` directly. The audit validates the package posture, resolves its linked `paper_understanding_gold_release_readiness.v1` path, and includes both artifacts in the non-canonical posture check.
- Roadmap completion from a comparison suite can now build the gold release package directly from reviewed staged split manifests. Service, CLI, and FastAPI paths accept seed/eval/holdout `paper_understanding_gold_staging_manifest.v1` build specs, write the fixed split manifests, write `paper_understanding_gold_release_package.v1`, resolve the linked release-readiness report, and then run the final completion audit.
- Roadmap completion from a comparison suite can now also build that gold release package directly from a saved `paper_understanding_gold_release_split_plan.v1`. Service, CLI, and FastAPI paths accept the split-plan path, write the fixed release package/readiness sidecars, include the split plan in contract compatibility review, and then run the final completion audit without manual `split_manifests` transfer.
- Standalone roadmap completion audit now has service, CLI, and FastAPI regression coverage for `gold_release_package_path` as well, so the release package can be used either inside the comparison-suite completion package or as a later audit input without hand-copying the linked readiness path.
- Roadmap completion audit now fails closed when a supplied `paper_understanding_gold_release_package.v1` disagrees with its linked `paper_understanding_gold_release_readiness.v1` sidecar. The audit adds a `fixed_goldset_release_package_consistency` check whenever a release package is present, covering stale or mismatched release-readiness files, mismatched fixed-manifest lists, mismatched release `goldset_id`, and fixed manifest files whose current contents no longer reproduce the linked release-readiness result.
- The release-package consistency check now also validates package `source_split_manifests` lineage when present. Source split `manifest_out` paths must match the package's fixed manifest paths, and the current source staging manifests must still rebuild the same fixed manifest content, keeping staged-review inputs traceable through the final release package.
- Roadmap completion workspace inventory now also reports `paper_understanding_gold_release_readiness.v1` and `paper_understanding_gold_release_package.v1` counts. For release packages it distinguishes valid packages, embedded ready packages, and packages whose linked readiness report plus fixed manifests still reproduce a consistent release result, so package artifacts cannot be present-but-invisible in the final audit.
- Roadmap completion audit now requires production-threshold adoption evidence to cover every P0 grounding metric, so a review that adopts only `claim_precision` cannot satisfy the broader roadmap Definition of Done.
- Roadmap completion audit now requires external-contract readiness evidence to reference a compatibility review covering the required evidence-grounding schema family: scorecard, benchmark, comparison, threshold calibration/adoption, fixed-goldset run-readiness, and fixed-goldset suite artifacts.
- Roadmap completion audit can now optionally inventory the current workspace `goldset_root` and `run_root`. This exposes legacy `teacher_verification.v1` files, candidate drafts/staging manifests, reviewer handoff packages, task exports, missing ready `paper_understanding_gold.v1` records, and run directories with or without required grounding sidecars, so current local evidence cannot be confused with accepted fixed-gold completion evidence. The inventory gate also checks that complete run evidence matches the ready gold `paper_id` set, preferring paper IDs declared inside scorecard/run metadata, then falling back to deepread sidecar paper IDs and finally raw/safe path segments, while blocking run directories whose own metadata is malformed or declares conflicting paper IDs.
- Standalone scorecard rebuild CLI at `scripts/eval/build_evidence_grounding_scorecard.py`, reusing the existing scorecard service to write a non-canonical `evidence_grounding_scorecard.v1` from saved deepread artifacts with optional external eval-only gold and explicit candidate-config source evidence.
- Typed parser/model/prompt/profile lineage through `EvidenceGroundingCandidateConfig` on benchmark manifests, per-scorecard benchmark items, and benchmark reports, plus separated `llm_model_version` and `reader_profile_version` fields on claim/evidence correction records and eval candidates.
- The scorecard artifact itself now carries optional typed `candidate_config` lineage, and the standalone scorecard build API plus benchmark runner propagate it into `evidence_grounding_scorecard.v1` without changing canonical runtime truth.
- Scorecard rebuilds now require `run_dir` to be an existing directory before loading sidecars or writing default outputs, and the direct default-writer helper requires an existing artifact directory. The service, FastAPI endpoint, standalone CLI, and writer helper all fail before creating a missing run directory, preserving the existing-artifact boundary for non-canonical scorecards. FastAPI and CLI default-output paths also preserve malformed core sidecar files unchanged while reporting `load_failed` diagnostics and malformed-input runtime proxy metrics in the additive scorecard.
- The downstream traceability runtime proxy now excludes `evidence_grounding_scorecard.json` from acceptance-contract expected-output counting, so a stale or in-progress scorecard output cannot count as upstream handoff evidence for the scorecard being rebuilt.
- When the acceptance contract contains only scorecard outputs after filtering, the traceability metric is `not_available` with an explicit detail instead of a fake `0.0` measurement.
- Run-dir scorecard rebuilds now load an optional typed `candidate_config.json` sidecar when no explicit config is supplied. The sidecar is reported as a non-core loaded input and source artifact, so lineage can travel with the run artifacts without being invented from incomplete `run_meta.json`; malformed run-local sidecars remain non-core `load_failed` diagnostics and warnings instead of becoming source artifacts, mutating source sidecars, or blocking scorecard construction from the remaining deepread sidecars. The FastAPI build endpoint now has matching regression coverage for that default run-local sidecar behavior, and request-level explicit `candidate_config` overrides a stale or malformed run-local sidecar without loading, warning on, or sourcing the optional sidecar.
- Roadmap completion audit now accepts an optional standalone `scorecard_path` / CLI `--scorecard` / API `scorecard_path` input and loads `evidence_grounding_scorecard.v1` as additive, non-canonical evidence. This can satisfy the additive artifact posture check without implying that the fixed-goldset, correction, threshold, or contract gates are complete.
- The roadmap completion audit now treats partial candidate lineage as incomplete: every scored benchmark item must carry parser, provider, model, model-version, prompt, and reader-profile lineage before the `candidate_configuration_lineage` gate can pass.
- Roadmap completion now validates structured correction evidence through `ClaimEvidenceCorrectionCase` or `claim_evidence_eval_candidate_export.v1` instead of key presence alone. A raw correction row must be schema-valid and accepted for eval reuse; both raw rows and exported eval candidates must include before/after evidence refs plus parser/provider/model/model-version/prompt/profile lineage before they can satisfy the structured correction-log gate.
- Claim/evidence correction intake now also fails closed for new `accepted_for_eval=true` rows that omit before/after evidence refs or parser/provider/model/model-version/prompt/profile lineage. This prevents future accepted corrections from entering the raw memory log in a form that the roadmap completion gate cannot replay.
- The Workbench correction form now mirrors that contract: current scorecards can still save ordinary non-canonical correction cases, but the eval-acceptance checkbox is disabled until complete parser/model/prompt/profile lineage is available instead of submitting a late-failing accepted-eval request.
- Fixed-goldset manifest builder and comparison-suite CLI paths now accept the same typed candidate lineage fields, so operators can produce audit-ready manifests for real baseline/candidate runs without manual JSON editing.
- Fixed-goldset comparison suite now writes `run_readiness_report.json` and links it from `comparison_suite.json`, keeping the completion-audit preflight evidence next to the benchmark and comparison reports.
- Fixed goldset comparison context in benchmark manifests/reports through `goldset_id`, `goldset_split`, `goldset_manifest_path`, goldset paper coverage fields, and goldset readiness fields; comparisons fail when declared goldset IDs/splits differ, a candidate benchmark omits/adds fixed-goldset papers, or selected gold papers are not eval-ready.
- Fixed-goldset benchmark manifest builder from `paper_understanding_gold_manifest.v1` plus a saved run root, requiring eval-ready gold records and existing run directories by default, with both CLI and FastAPI entry points.
- Fixed-goldset benchmark manifest builder from staged review gold, with service, CLI, and FastAPI entry points. The builder first publishes a fixed `paper_understanding_gold_manifest.v1` from a `paper_understanding_gold_staging_manifest.v1`, then builds the evidence-grounding benchmark manifest against the declared run root. This closes the handoff from human-reviewed staged gold into benchmark preparation without requiring manual intermediate JSON editing.
- Fixed-goldset comparison suite runner from staged review gold, with service, CLI, and FastAPI entry points. The runner publishes the intermediate fixed paper-understanding manifest, performs run-readiness checks, builds baseline/candidate benchmark manifests and reports, compares them, and writes the typed non-canonical `comparison_suite.json` handoff. This closes the eval lane from staged human-reviewed gold to comparison evidence while preserving the ready-only and run-coverage gates.
- Fixed-goldset run-readiness audit artifact, CLI, and FastAPI endpoint for checking baseline/candidate run-root coverage and required sidecars before a real fixed-goldset comparison is attempted. The preflight now also fails on stale, conflicting, or malformed run identity metadata when present.
- Fixed-goldset run-readiness now also requires required run sidecars to be parseable JSON before an item can pass. The report records `malformed_required_artifacts` per item and `malformed_required_artifact_count` per lane, and contract compatibility rejects stale run-readiness artifacts that omit those explicit malformed-sidecar fields.
- Fixed-goldset run-readiness compatibility and roadmap completion now also verify top-level pass/fail counts against lane summaries and lane pass/fail counts against item statuses. A stale report cannot claim `comparison_run_ready=true` while embedded lane/item status still shows failures.
- Fixed-goldset comparison-suite compatibility and roadmap completion now also compare suite `comparison_run_ready` and `run_readiness_fail_count` against the linked `evidence_grounding_fixed_goldset_run_readiness.v1` report. A stale suite handoff cannot summarize run readiness differently from the sidecar it points to.
- Fixed-goldset benchmark scoring now injects the manifest's `paper_understanding_gold.v1` record into scorecard generation for each matching paper, so gold-scored metrics come from the declared fixed target rather than only from optional run-local copies.
- Fixed-goldset baseline/candidate comparison suite that builds both manifests, runs both benchmark reports, compares them, and writes a typed non-canonical `comparison_suite.json` Pydantic review artifact, with both CLI and FastAPI entry points.
- Deepread runtime scorecard generation and run metadata projection.
- Run-level scorecard input completeness metrics, aggregated through benchmark reports and staged under `unknown` because they describe instrumentation coverage rather than one LLM/pipeline role. Scorecards also preserve per-input load diagnostics so malformed core sidecars can be queried separately from absent sidecars.
- Definition-of-Done completion audit for the broader roadmap, including explicit checks for fixed-goldset execution evidence, per-run/aggregate scorecards, P0 metric availability, P0 regression gating, structured correction logs, stage attribution, non-canonical posture, production threshold adoption, and external contract readiness.
- Roadmap completion checks now include additive `next_actions` for failed requirements, and the audit report also exposes a top-level deduplicated `next_actions` queue with each action tied back to its `requirement_id`. Queue items include `phase` and `requires_human_review`, and can include `command_hint` values for the relevant non-canonical handoff script, such as reviewer handoff packaging, release-readiness audit, fixed-goldset comparison, threshold adoption, or contract readiness. The report also summarizes `next_action_phase_counts` and `human_review_next_action_count`, so reviewers can see whether remaining blockers are concentrated in gold curation, fixed runs, threshold adoption, or contract readiness. The actions do not relax any gate or mark work complete; they translate blocker evidence into reviewer/operator tasks such as curating ready gold records, publishing seed/eval/holdout manifests, running fixed-goldset baseline/candidate benchmarks, and resolving contract-readiness evidence.
- The top-level `next_actions` queue is dependency-aware when workspace inventory is supplied. If the inventory shows too few ready fixed-gold records, downstream fixed-gold run, threshold, package, and contract commands are deferred from the operator queue while their failed completion checks remain visible as blockers.
- The completion next-action queue now uses workspace inventory counts to advance gold-curation command hints through reviewer handoff, apply, stage, and release-prep. It only advances past apply when a package reports `ready_to_stage_count > 0`, `not_ready_count = 0`, and `remaining_task_count = 0`; past stage when `staged_count > 0`, `curation_complete = true`, and `remaining_task_count = 0`; and past release-prep when `release_ready = true`. With the current local reviewer handoff package present and no ready apply package, the first fixed-gold action now points to `apply_paper_understanding_gold_reviewer_handoff.py`. The gate still remains blocked until human-edited templates produce ready staged gold and release-readiness evidence.
- The per-check `next_actions` in roadmap completion audits now use the same workspace-aware handoff refinement as the top-level queue. When the current workspace has only unedited reviewer handoff apply packages, the failed `fixed_goldset_release_readiness` check itself points to editing patch templates before re-applying instead of preserving a generic "curate ready gold" instruction.
- The workspace run-evidence next action now carries a command hint for `scripts/eval/audit_evidence_grounding_fixed_goldset_run_readiness.py`, making the required run-sidecar preflight explicit before operators attempt a fixed-goldset comparison.
- The threshold-package next-action hints now distinguish the two required steps: building the seed/eval/holdout comparison-suite package with `scripts/eval/run_evidence_grounding_fixed_goldset_comparison_from_benchmark_run_packages.py`, then running threshold-adoption package review with `scripts/eval/review_evidence_grounding_threshold_adoption_from_comparison_suite_package.py`.
- The production-threshold next-action hints now distinguish calibration from adoption review: the calibration action points to `scripts/eval/calibrate_evidence_grounding_thresholds_from_comparison_suite.py`, while the review action points to `scripts/eval/review_evidence_grounding_threshold_adoption_from_comparison_suite_package.py`.
- Completion inventory now verifies reviewer-handoff guide presence with `gold_reviewer_handoff_guide_path_count`, `existing_gold_reviewer_handoff_guide_count`, and `missing_gold_reviewer_handoff_guide_count`. If a handoff package lacks an existing guide file, the audit adds a regeneration next action so human curation is not inferred from package JSON alone.
- Completion inventory now also reports reviewer-handoff apply edit-state counts from the embedded patch-result manifest: edited/unedited result totals, unedited-only package count, partially unedited package count, and unknown edit-state package count. When edit-state fields are present, an apply package must have `edited_result_count > 0` and `unedited_result_count = 0` before the inventory can count it as ready; unedited-only apply packages produce a patch-template editing/re-apply next action instead of allowing the checklist to advance to staging.
- The reviewer-handoff apply API now preserves the `require_edited=true` guard as a structured 409 response. It returns a stable message plus `findings` such as `no_edited_patch_results` and `unedited_patch_result_count=<n>`, so API callers can show the same repair guidance as the CLI without parsing a free-form error string.
- Claim/evidence correction replayability failures now expose source-record diagnostics through the FastAPI routes as well as the CLI. A `require_replayable=true` API failure includes `source_invalid_record_count` and line-level `source_invalid_record_diagnostics`, including missing parser/model/prompt/profile fields, so the correction repair path remains API-first.
- The standalone roadmap-completion CLI now supports `--print-next-actions` and `--next-action-limit`, so blocked local audits can print the next fixed-gold/run/threshold/contract actions directly to stdout while still writing the full non-canonical audit JSON.
- Formatter-stage handoff proxy scoring through `handoff_check_pass_rate`, summarizing existing `quality_gate.json` check statuses without changing downstream artifact contracts.
- Artifact API and Workbench visibility for scorecards and correction logging.
- Visual evidence proxy metrics including figure/table conflict count.

These are still additive review/eval or user-facing visibility artifacts. They do not promote scorecards, correction logs, or reviewed fixtures into canonical paper truth.

## Current Workspace Evidence Snapshot

`scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset/accepted --run-root storage/artifacts` now reports the current local evidence inventory as a blocking check:

- `goldset/accepted`: 8 JSON files checked; 0 valid `paper_understanding_gold.v1`; 0 ready gold records; 8 invalid for the new gold schema; 8 legacy `teacher_verification.v1` records; 0 release-readiness reports; 0 release packages.
- `storage/artifacts`: 90 run-like directories with at least one required sidecar signal; 4 directories contain the full required sidecar set (`reader_eval.json`, `claimset_coverage.json`, `evidence_extraction_bundle.json`, `claimset.resolved.json`).
- The one-step teacher curation package currently drafts 8 non-canonical candidate gold records from `goldset/accepted`; all 8 fail readiness, with blockers concentrated on missing method/result/limitation coverage, `paper_type`, important visual inventory, and DOI/PMID metadata. The generated curation report now expands those blockers into 54 per-field tasks with `target_field`, current count, minimum required count, instruction, and evidence hint fields for reviewer/UI handoff.
- Patch-template generation over a current teacher-derived draft produces a non-canonical patch request scaffold with the same open tasks preserved; for example the Bialystok draft currently yields 7 open tasks and `readiness=fail`, making the remaining human edits explicit without claiming the draft is ready.
- Batch patch-template generation over the current teacher curation package writes 8 template files and reports `open_task_count=54`, `pass_count=0`, `fail_count=8`, so the whole local curation queue can be handed to reviewers as editable patch-request scaffolds.
- Curation task export can now flatten that queue into a reviewer handoff JSON/CSV with paper IDs, reason codes, target fields, instructions, evidence hints, latest template/patch paths, `curation_stage`, and `review_priority`. The report also exposes top-level `curation_stage_counts` and `review_priority_counts`, and the task-export, one-step reviewer handoff, reviewer-handoff apply, and reviewer-handoff stage CLIs print those counts to stdout, so reviewer backlog composition is visible without scanning every item. Regression coverage verifies service, CLI, and FastAPI paths; the export remains non-canonical and does not make any draft ready.
- Contract compatibility now verifies curation task export counts against the embedded `items` list. `open_task_count` and task breakdown maps must match task rows, while `paper_count` and `status_counts` must match the unique paper/status view represented by those rows. This keeps a stale reviewer queue from misstating the remaining human workload while still passing contract review.
- The reviewer handoff package can now create the curation package, patch-template manifest, curation progress report, task export JSON/CSV, and Markdown reviewer guide in one call. Regression coverage verifies service, CLI, and FastAPI paths; the package exits nonzero while open tasks remain and does not promote any draft into accepted fixed gold.
- Contract compatibility now verifies reviewer-handoff package headline counts against the embedded curation package, patch-template manifest, progress report, and task export. `draft_count`, `open_task_count`, `curation_ready`, template counts, progress remaining-task counts, and task-export counts must agree, so stale wrapper JSON cannot misrepresent the reviewer guide/template packet.
- Current local reviewer handoff package has now been generated at `goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json`, with its guide at `goldset/reviews/paper_understanding_gold_reviewer_handoff/reviewer_guide.md`. It contains 8 teacher-derived candidate drafts, 8 patch templates, and 54 open review tasks, with `curation_ready=false`. Its JSON/CSV task exports and reviewer guide now sort by `review_priority` and include `curation_stage`, starting with metadata/DOI-PMID blockers before claim, method, result, limitation, and visual-inventory work. Current stage counts are `metadata=16`, `claim_set=6`, `method_context=8`, `result_context=8`, `limitation_context=8`, and `visual_inventory=8`. The guide now also includes a `Tasks By Stage` section with all open tasks, instructions, evidence hints, and patch-template paths grouped by curation stage, making method/result/limitation/visual work visible even when it is below the top-priority metadata table. This is the active human curation queue; it is non-canonical and does not satisfy fixed-gold release readiness until edited templates are applied, staged, and packaged into seed/eval/holdout release manifests.
- The curation progress audit over that package plus the generated patch-template manifest currently reports `draft_count=8`, `templated_count=8`, `patched_count=0`, `ready_to_stage_count=0`, `staged_count=0`, and `remaining_task_count=54`, confirming that every local legacy teacher output now has an editable patch scaffold but no fixed-gold candidate has yet been patched or staged.
- Batch-applying the current unedited patch-template manifest writes 8 non-canonical patch-result files, but reports `edited_result_count=0`, `unedited_result_count=8`, `curation_ready_count=0`, `not_ready_count=8`, and `fail_count=8`. Supplying those patch results to the progress audit changes the queue from `templated_count=8` to `patched_count=8`, while `ready_to_stage_count=0`, `staged_count=0`, and `remaining_task_count=54` stay blocked until humans edit the missing method/result/limitation/metadata/visual fields.
- A one-paper edited-template regression fixture now verifies the full review handoff path: edited patch template -> patch-result manifest -> staging-from-patch-results -> staged `paper_understanding_gold.v1` review file -> progress audit `curation_complete=true`. This proves the lane is wired, while the real local queue remains blocked because the 8 current templates are unedited and not ready.
- On 2026-05-24, the real local Bialystok reviewer template was evidence-edited from local extracted article chunks. Isolated patch application now changes citation, paper type, domain tags, claims, methods, results, limitations, important figures, and notes, and recalculates `after_readiness=pass`; full guarded handoff apply still blocks with `unedited_patch_result_count=7`, so no fixed-gold staging or release-readiness evidence is claimed yet.
- The roadmap completion audit now reflects that partial template progress directly: workspace inventory reports one edited reviewer patch template and seven remaining unedited templates, and the immediate gold-curation next action names the remaining unedited count/sample instead of saying all current apply evidence is unedited.
- The Dubois 2024 IWG recommendation template is now also evidence-edited from local extracted article chunks, filling DOI, guideline paper type, diagnostic/biomarker domain tags, PubMed evidence-review method, recommendation result, progression-evidence limitation, and diagnostic-approach table inventory. Isolated patch application passes; full guarded apply still blocks with six unedited templates remaining.
- Staged review gold can now be published into a fixed split manifest by passing `staging_manifest.json` directly to the existing validator/manifest builder. Regression coverage verifies service, CLI, and FastAPI paths with `require_ready=true`, preserving the ready-only gate before any fixed-goldset benchmark manifest is built.
- Fixed split manifests can now be audited as a seed/eval/holdout release candidate before benchmark use. Regression coverage verifies service, CLI, and FastAPI paths that keep this as a non-canonical review gate and block missing splits or duplicate paper IDs across splits.
- Reviewed staged gold can now be packaged into fixed seed/eval/holdout manifests plus the release-readiness report in one step. Regression coverage verifies service, CLI, and FastAPI paths for `paper_understanding_gold_release_package.v1`, while the real local queue remains blocked because there are still no ready curated split bundles.
- A ready combined staging manifest can now be transformed into split staging manifests and release-package build items through `paper_understanding_gold_release_split_plan.v1`. Regression coverage verifies service, CLI, and FastAPI paths, including feeding the produced split manifests into the existing release-package builder. The real local queue remains blocked because the current 8 teacher-derived drafts are still not readiness-passing.
- A saved split-plan report can now produce the release package directly through service, CLI, and FastAPI paths. Regression coverage verifies split-plan -> fixed split manifests -> release-readiness -> release-package without manual `split_manifests` transfer. The real local queue remains blocked because no ready combined staged-gold manifest exists yet.
- Release split plans are now visible in roadmap workspace inventory and accepted by the contract-compatibility audit as non-canonical review artifacts. They are not part of the completion-required schema family, but they are recognized as a supported operator handoff artifact rather than an unknown sidecar.
- Reviewer handoff apply packages are now accepted by the contract-compatibility audit as non-canonical review artifacts. Regression coverage verifies service, CLI, and FastAPI paths for handoff package -> edited patch templates -> patch-result manifest -> refreshed progress/task export package, while fixed-gold acceptance still requires ready-only staging and release packaging. Patch-result manifests now distinguish prefilled but unedited scaffolds from actual human edits by comparing the patch request back to the source draft, so unedited reviewer handoffs cannot look like completed edits.
- Contract compatibility now requires reviewer-handoff packages to expose `reviewer_guide_path` and reviewer-handoff apply packages to embed patch-result edit-state fields. Stale packages without `reviewer_guide_path`, `patch_result_manifest.edited_result_count`, or `patch_result_manifest.unedited_result_count` fail compatibility, keeping the completion inventory and contract-readiness checks aligned on whether a handoff artifact can support human curation and prove human-edited curation work.
- Contract compatibility now also checks reviewer-handoff apply package count consistency: `curation_ready_count + not_ready_count` must match `result_count`, `ready_to_stage_count` cannot exceed ready results, embedded patch-result manifest counts must match package counts when present, edited plus unedited results must match `result_count`, and embedded task-export `open_task_count` must match `remaining_task_count`. This rejects stale or contradictory apply artifacts while still allowing an honest blocked package with zero edited results to remain contract-compatible but not completion-ready.
- Contract compatibility now extends the same stale-artifact protection to reviewer-handoff stage and release-prep packages. Stage packages must keep staged/progress/task-export counts aligned, and release-prep packages must keep staged counts, split counts, split-plan readiness, split-item totals, release package manifest counts, and embedded release-readiness status consistent. This prevents a stale downstream handoff artifact from looking externally compatible after apply-package evidence changes.
- Reviewer handoff stage packages are now accepted by the contract-compatibility audit and visible in roadmap workspace inventory as non-canonical review artifacts. Regression coverage verifies apply package -> ready-only staged review gold -> refreshed progress/task export, while final roadmap completion still requires fixed seed/eval/holdout release packaging and real benchmark runs.
- Reviewer handoff release-prep packages are now accepted by the contract-compatibility audit and visible in roadmap workspace inventory as non-canonical review artifacts. Regression coverage verifies staged handoff package -> release split plan -> fixed manifest package/readiness for a release-ready split configuration, while the real local queue remains blocked until enough curated papers exist for the required seed/eval/holdout release.
- That release package can now be passed directly into the roadmap-completion audit package. Regression coverage verifies service, CLI, and FastAPI paths that resolve the linked release-readiness report from the package and keep both artifacts in the additive non-canonical check.
- The roadmap-completion audit package can now build the release package directly from staged split manifests as well. Regression coverage verifies service, CLI, and FastAPI paths for reviewed staged gold -> fixed split manifests -> release package/readiness -> final completion audit.
- A ready release package can now feed benchmark-manifest preparation directly. Regression coverage verifies service, CLI, and FastAPI paths for release package -> per-split `evidence_grounding_benchmark_manifest.v1` files -> non-canonical `evidence_grounding_benchmark_manifest_package.v1`, with parser/model/prompt/profile lineage and run-directory existence checks preserved.
- A saved benchmark-manifest package can now feed benchmark execution directly. Regression coverage verifies service, CLI, and FastAPI paths for manifest package -> per-split `evidence_grounding_benchmark.v1` reports -> non-canonical `evidence_grounding_benchmark_run_package.v1`, and the contract-compatibility audit recognizes the run package as a supported review artifact.
- Baseline/candidate benchmark run packages can now feed per-split fixed-goldset comparison directly. Regression coverage verifies service, CLI, and FastAPI paths for paired run packages -> split `evidence_grounding_fixed_goldset_comparison_suite.v1` files -> non-canonical `evidence_grounding_fixed_goldset_comparison_suite_package.v1`, and the contract-compatibility audit recognizes the suite package as a supported review artifact.
- Split fixed-goldset comparison-suite packages can now feed threshold adoption directly. Regression coverage verifies service, CLI, and FastAPI paths for suite package -> shared threshold calibration -> split threshold-checked comparison reports -> non-canonical `evidence_grounding_threshold_adoption_review_package.v1`, and the contract-compatibility audit recognizes the adoption package as a supported review artifact.
- Threshold-adoption packages can now feed contract readiness directly. Regression coverage verifies service, CLI, and FastAPI paths for adoption package -> expanded contract-compatibility report -> `evidence_grounding_contract_readiness.v1`, including linked split suites, benchmark reports, run-readiness reports, and embedded scorecards.
- Staged review gold can also feed benchmark preparation directly through the staged-gold benchmark manifest builder. Regression coverage verifies service, CLI, and FastAPI paths that write both the intermediate fixed paper-understanding manifest and the final `evidence_grounding_benchmark_manifest.v1` with typed candidate lineage.
- Staged review gold can now feed a full fixed-goldset comparison suite directly. Regression coverage verifies service, CLI, and FastAPI paths that publish the intermediate fixed manifest, run baseline/candidate scorecard benchmarks, write `run_readiness_report.json`, and save the typed non-canonical `comparison_suite.json`.
- A completed comparison suite can now feed threshold calibration directly. Regression coverage verifies service, CLI, and FastAPI paths that resolve the suite's baseline/candidate benchmark report paths and write a non-canonical `evidence_grounding_threshold_calibration.v1` artifact.
- A completed comparison suite can now feed a threshold-checked comparison rerun directly. Regression coverage verifies service, CLI, and FastAPI paths that resolve suite-linked baseline/candidate benchmark reports and apply calibration-derived thresholds into an `evidence_grounding_scorecard_comparison.v1` report with populated `threshold_checks`.
- A completed comparison suite can now feed a full threshold-adoption package directly. Regression coverage verifies service, CLI, and FastAPI paths that write calibration, threshold-checked comparison, and adoption-review artifacts in one call while preserving the explicit approval gate.
- A completed comparison suite can now feed contract compatibility review directly. Regression coverage verifies service, CLI, and FastAPI paths that resolve suite-linked artifacts plus embedded benchmark scorecards into a non-canonical `evidence_grounding_contract_compatibility.v1` report covering the required evidence-grounding schema family when threshold calibration/adoption artifacts are also supplied.
- A completed comparison suite can now feed contract readiness review directly. Regression coverage verifies service, CLI, and FastAPI paths that write the suite-derived compatibility report and then audit migration, backfill, public-contract, approval, and opt-in evidence before `external_contract_ready=true`.
- A completed comparison suite can now feed a final roadmap-completion package directly. Regression coverage verifies service, CLI, and FastAPI paths that write threshold adoption artifacts, contract readiness artifacts, optional gold release-readiness artifacts from manifest paths, and the final non-canonical completion audit from one suite handoff. That completion audit now also requires paper-understanding gold release-readiness evidence, so a single eval comparison cannot stand in for the seed/eval/holdout fixed-goldset release gate.
- A threshold-adoption package can now feed the final roadmap-completion audit directly. Regression coverage verifies service, CLI, and FastAPI paths that select a representative split suite, reuse the package-linked threshold calibration/adoption review, build package-wide contract readiness, carry optional gold release package/readiness evidence into compatibility coverage, and write the final non-canonical completion audit. The completion audit now adds a package-wide fixed-goldset threshold gate when that package is supplied, so roadmap completion requires seed/eval/holdout split coverage and ready adoption reviews across the package, not only one representative split. That gate also checks declared package counts, embedded reviews, linked adoption-review sidecars, and comparison-suite paths for consistency before allowing the package to satisfy completion.
- The final completion audit now fails closed when no threshold-adoption package is supplied. Single comparison-suite completion paths still produce calibration/adoption/contract artifacts, but they no longer prove `roadmap_complete=true` by themselves because they cannot demonstrate seed/eval/holdout threshold readiness across the fixed-goldset package.
- Result: `workspace_evidence_inventory_ready=fail`, so the roadmap remains incomplete until real accepted `paper_understanding_gold.v1` records and fixed-goldset baseline/candidate runs are produced and reviewed.

## Broader Roadmap Completion Status

The full Evidence Grounding Performance roadmap is not complete yet. Remaining work includes:

- Curating fixed seed/eval/holdout gold records across representative domains and publishing the selected bundles through `paper_understanding_gold_manifest.v1`.
- Running real parser/model/prompt candidates through that fixed gold set. The repeatable suite and a preflight run-readiness audit now exist, but they still need real candidate run outputs.
- Calibrating and adopting production threshold policy on real fixed-goldset runs. Additive threshold policy, calibration, and adoption-review artifacts now exist, but stable operating cutoffs still need real candidate evidence and human approval before being treated as production policy.
- Expanding consistency checks beyond the current explicit `OVERSTATED_RESULT` label, review-code contradiction labels, and bounded direct polarity proxies for visual not-allowed claims plus claim/evidence text. Richer contradiction evidence still needs adjudication from paired claims, source passages, figures, and tables.
- Expanding vision-level panel/element interpretation beyond bounded visual text, ambiguous-panel, not-allowed-claim, and direct-polarity checks; table-cell value, figure visual text, ambiguous panel, visual not-allowed claim, and direct visual contradiction signals now have first-pass metrics.
- Completing migration/backfill/public-contract review before treating any scorecard or benchmark-family output as a stable external contract. A second-stage readiness audit now encodes the required evidence gates, but the actual reviewed migration/backfill/public-contract artifacts and approval references still need to be produced from real release evidence.

## Verification Evidence

Latest relevant verification for this lane:

```bash
.venv/bin/python -m pytest tests/test_artifacts_runs_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py tests/test_claim_evidence_corrections_api.py tests/test_paper_understanding_gold.py tests/test_artifact_review_feedback_api.py tests/test_deepread_handoff_artifacts.py tests/test_visual_evidence_schema.py
# 328 passed, 5 warnings
```

Additional targeted check for the gold manifest validator:

```bash
.venv/bin/python -m pytest tests/test_paper_understanding_gold.py
# 75 passed, 5 warnings
```

Additional targeted check for fixed goldset manifest and benchmark context integration:

```bash
.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_evidence_grounding_benchmark.py
# 192 passed, 5 warnings
```

Additional targeted check for scorecard input diagnostics and compatibility:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 437 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "accepts_gold_release_artifacts or stale_handoff_stage_linked_handoff_package or stale_handoff_stage_linked_apply_package or stale_handoff_apply_linked_handoff_package or stale_handoff_stage_linked_staging_manifest or stale_handoff_stage_linked_progress_report or stale_handoff_apply_linked_progress_report or stale_handoff_apply_linked_patch_manifest or stale_handoff_apply_linked_task_export or stale_handoff_stage_linked_task_export or stale_handoff_package_linked_task_export"
# 11 passed, 258 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "accepts_gold_release_artifacts or stale_handoff_release_prep_linked_stage_package_sidecar or stale_handoff_release_prep_linked_staging_manifest or stale_handoff_release_prep_linked_stage_package or stale_handoff_release_prep_linked_readiness or stale_handoff_release_prep_linked_release_package or stale_handoff_release_prep_linked_split_plan or handoff_release_prep_count_mismatch"
# 8 passed, 262 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "handoff_package or handoff_stage or handoff_release_prep or handoff_apply or curation_task_export"
# 23 passed, 247 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_benchmark_manifest_package_counts or stale_benchmark_manifest_package_linked_manifest or stale_benchmark_run_package_counts or stale_benchmark_run_package_linked_report or stale_suite_package_linked_run_package or comparison_suite_package or threshold_adoption_package"
# 27 passed, 226 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_gold_release_package_linked_readiness"
# 1 passed, 253 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "gold_release_package or gold_release_readiness or gold_release_split_plan"
# 18 passed, 236 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "different_artifact or stale_compatibility_summary or stale_contract_compatibility_summary or stale_contract_readiness_summary or contract_readiness or roadmap_completion_audit_requires_contract_schema_coverage or roadmap_completion_audit_accepts_gold_release_package or correction_export_contract_schema_coverage"
# 17 passed, 232 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_threshold_package_counts or stale_threshold_package_linked_review or threshold_adoption_package or roadmap_completion_from_threshold_adoption_package"
# 13 passed, 237 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_compatibility_summary or stale_contract_compatibility_summary or stale_contract_readiness_summary or contract_readiness or roadmap_completion_audit_requires_contract_schema_coverage or roadmap_completion_audit_accepts_gold_release_package"
# 15 passed, 233 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_contract_readiness_summary or contract_readiness or roadmap_completion_audit_requires_contract_schema_coverage or roadmap_completion_audit_accepts_gold_release_package"
# 13 passed, 233 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_comparison_decision or compare_evidence_grounding_benchmark_reports or check_evidence_grounding_contract_compatibility_from_comparison_suite or rejects_unknown_comparison_failure_code"
# 19 passed, 226 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_threshold_adoption_review_counts or stale_threshold_calibration_counts or threshold_adoption_review_report or threshold_adoption_review_blocks_partial_p0_thresholds or check_evidence_grounding_contract_compatibility_from_comparison_suite"
# 7 passed, 237 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "threshold_calibration and (stale_threshold_calibration_counts or calibration_report_from_benchmark_reports or comparison_suite_defaults_to_candidate or applies_threshold_calibration_report or threshold_adoption_review)"
# 4 passed, 239 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_benchmark_manifest_package_counts or stale_benchmark_run_package_counts or stale_threshold_package_counts or roadmap_completion_from_threshold_adoption_package"
# 10 passed, 232 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_threshold_package_counts or stale_threshold_package_without_suite_context_fields or stale_comparison_suite_package_counts or roadmap_completion_from_threshold_adoption_package"
# 10 passed, 231 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_benchmark_run_package_counts or roadmap_completion_from_threshold_adoption_package or false_incomplete_roadmap_completion or unexpected_roadmap_completion_warnings or missing_warn_status_marker"
# 11 passed, 229 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_comparison_suite_package_counts or stale_suite_package_without_run_package_readiness_fields or stale_comparison_suite_readiness_summary"
# 4 passed, 235 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_comparison_suite_readiness_summary or stale_run_readiness_summary_counts or comparison_suite_covers_schema_family"
# 5 passed, 233 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "malformed_required_run_artifacts or requires_matched_gold_run_inventory or rejects_malformed_run_identity_metadata"
# 3 passed, 229 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "fixed_goldset_run_readiness_report_blocks_malformed_required_sidecar or stale_run_readiness_without_malformed_artifact_fields or fixed_goldset_run_readiness_report_blocks_missing_sidecar or fixed_goldset_run_readiness_report_blocks_malformed_identity"
# 4 passed, 230 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_run_readiness_summary_counts or stale_run_readiness_without_malformed_artifact_fields or fixed_goldset_run_readiness_report_blocks_malformed_required_sidecar"
# 4 passed, 232 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "canonical_roadmap_completion_posture or malformed_roadmap_completion_identity or malformed_roadmap_completion_input_paths"
# 3 passed, 224 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "malformed_handoff_inventory_counts or workspace_actions_do_not_stage_blocked_apply or workspace_actions_advance_existing_handoff"
# 3 passed, 225 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "malformed_release_prep_inventory_counts or malformed_handoff_inventory_counts or inventories_workspace_evidence"
# 3 passed, 226 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "malformed_gold_release_inventory_counts or inventories_gold_release_artifacts or gold_release_artifacts"
# 3 passed, 227 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "raw_valid_linked_release_readiness or malformed_gold_release_inventory_counts or inventories_gold_release_artifacts"
# 3 passed, 228 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 37 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "contract_compatibility or evidence_grounding_scorecard"
# 25 passed, 139 deselected, 5 warnings
```

Latest targeted check for paper-understanding reviewer handoff and benchmark completion audit integration:

```bash
.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_evidence_grounding_benchmark.py -q
# 257 passed, 5 warnings
```

Additional targeted check for reviewer-handoff apply edit-state inventory:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "inventories_workspace_evidence or workspace_actions_advance_existing_handoff or workspace_inventory_flags_missing_handoff_guide or workspace_actions_do_not_stage_blocked_apply"
# 4 passed, 159 deselected, 5 warnings
```

Additional targeted check for contract compatibility coverage:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "gold_release_artifacts or stale_handoff_apply_without_edit_counts or partial_handoff_apply_edit_counts or contract_compatibility"
# 18 passed, 144 deselected, 5 warnings
```

Additional targeted check for gold/scorecard/benchmark metric integration:

```bash
.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py
# 220 passed, 5 warnings
```

Additional targeted check for correction-loop and candidate-lineage integration:

```bash
.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py
# 304 passed, 5 warnings
```

Additional targeted check for correction/scorecard/benchmark taxonomy sharing:

```bash
.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py
# 211 passed, 5 warnings
```

Additional targeted check for accepted correction replay lineage guard:

```bash
.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py -q
# 18 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 437 passed, 5 warnings
```

Additional targeted check for Workbench correction lineage UX gate:

```bash
cd frontend && npm run build
# built successfully

cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "workbench can log a non-canonical correction case|workbench surfaces evidence grounding scorecard|workbench grounding scorecard surfaces failure codes"
# 3 passed

cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workbench shows evidence grounding scorecard from live artifact bundle|backend workbench saves and reloads claim evidence correction cases"
# 2 passed
```

Additional targeted check for scorecard candidate lineage propagation:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 40 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q -k "scorecard_cli or candidate_config_sidecar or build_api_writes_scorecard_with_external_gold"
# 3 passed, 37 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "run_evidence_grounding_benchmark_from_manifest_path or candidate_config_lineage or scorecard_compare_api_returns_noncanonical_report"
# 3 passed, 268 deselected, 5 warnings

cd frontend && npm run build
# built successfully

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q -k "candidate_config or build_api_writes_scorecard_with_external_gold"
# 2 passed, 37 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "standalone_scorecard or roadmap_completion_api_returns_noncanonical_report"
# 4 passed, 270 deselected, 5 warnings
```

Additional targeted check for benchmark generation/comparison:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 158 passed, 5 warnings
```

Additional targeted check for the current reviewer handoff lane:

```bash
.venv/bin/python scripts/eval/package_paper_understanding_gold_reviewer_handoff.py goldset/accepted --out-dir goldset/reviews/paper_understanding_gold_reviewer_handoff --out goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json
# exit code 1 expected while open review tasks remain
# draft_count=8, template_count=8, open_task_count=54, curation_ready=False
# reviewer_guide=goldset/reviews/paper_understanding_gold_reviewer_handoff/reviewer_guide.md

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py -q -k reviewer_handoff
# 13 passed, 81 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py -q -k "reviewer_handoff_apply_package_marks_unedited_scaffold_as_unedited or reviewer_handoff_apply_package_refreshes_progress_and_task_export or reviewer_handoff_apply_cli_refreshes_progress_and_task_export"
# 3 passed, 91 deselected, 5 warnings

.venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out-dir /tmp/paperpipe_handoff_apply_unedited_check --out /tmp/paperpipe_handoff_apply_unedited_check/package.json
# exit code 1 expected while open review tasks remain
# result_count=8, edited_result_count=0, unedited_result_count=8, remaining_task_count=54

.venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out-dir goldset/reviews/paper_understanding_gold_reviewer_handoff_apply --out goldset/reviews/paper_understanding_gold_reviewer_handoff_apply/package.json
# exit code 1 expected while open review tasks remain
# result_count=8, curation_ready_count=0, not_ready_count=8, ready_to_stage_count=0, remaining_task_count=54
# edited_result_count=0, unedited_result_count=8

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact goldset/reviews/paper_understanding_gold_reviewer_handoff_apply/package.json --out /tmp/paperpipe_handoff_apply_contract_compatibility.json
# fail_count=0; shape is contract-compatible, but completion inventory still blocks staging because the apply package is unedited

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact goldset/reviews/paper_understanding_gold_reviewer_handoff_apply/package.json --out /tmp/paperpipe_handoff_apply_contract_compatibility_after_count_gate.json
# fail_count=0; stricter apply-package count consistency checks pass for the current blocked package

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "contract_compatibility or workspace_actions_do_not_stage_blocked_apply or inventories_workspace_evidence or workspace_actions_advance_existing_handoff"
# 37 passed, 148 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact goldset/reviews/paper_understanding_gold_reviewer_handoff_apply/package.json --out /tmp/paperpipe_handoff_apply_contract_compatibility_after_stage_release_count_gate.json
# fail_count=0; downstream stage/release-prep count gates do not change the honest blocked apply-package shape result

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact goldset/reviews/paper_understanding_gold_reviewer_handoff/curation_tasks.json --artifact goldset/reviews/paper_understanding_gold_reviewer_handoff_apply/curation_tasks.json --out /tmp/paperpipe_curation_task_export_contract_compatibility.json
# fail_count=0; current handoff and apply task exports pass task-row and paper/status count consistency checks

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out /tmp/paperpipe_handoff_package_contract_compatibility_after_count_gate.json
# fail_count=0; current reviewer handoff package passes wrapper-to-embedded-artifact consistency checks

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "gold_release_artifacts or gold_release_readiness_count_mismatch or gold_release_split_plan_count_mismatch or gold_release_package_count_mismatch or contract_compatibility"
# 37 passed, 148 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "claim_evidence_eval_candidate_export or default_correction_export_cli_output or structured_correction_log or contract_compatibility_report_accepts_supported_review_artifacts"
# 4 passed, 186 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "contract_compatibility or claim_evidence_eval_candidate_export or default_correction_export_cli_output"
# 39 passed, 151 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "correction_export_contract_schema_coverage or package_includes_correction_export_contract_coverage or claim_evidence_eval_candidate_export or external_contract_readiness or structured_correction_log"
# 4 passed, 188 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "eval_candidate_export_as_correction_evidence or correction_export_contract_schema_coverage or package_includes_correction_export_contract_coverage or noncanonical_artifacts"
# 3 passed, 189 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "structured_correction_log or nonreplayable_correction_log or eval_candidate_export_as_correction_evidence or default_correction_export_cli_output or accepts_gold_release_package or can_pass_with_all_review_evidence or requires_gold_release_readiness"
# 10 passed, 178 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "can_pass_with_all_review_evidence or eval_candidate_export_as_correction_evidence or nonreplayable_correction_log or default_correction_export_cli_output"
# 4 passed, 188 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "nonreplayable_correction_log or structured_correction_log or eval_candidate_export_as_correction_evidence or default_correction_export_cli_output"
# 3 passed, 189 deselected, 5 warnings; non-replayable raw logs now produce a repair/re-export next action

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_roadmap_completion_correction_evidence or roadmap_completion_next_action or false_complete_roadmap_completion"
# 4 passed, 189 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_roadmap_completion_correction_evidence or invalid_roadmap_completion_correction_posture or roadmap_completion_next_action or false_complete_roadmap_completion"
# 5 passed, 189 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "correction_export_input or accepts_eval_candidate_export_as_correction_evidence or correction_export_contract_schema_coverage"
# 4 passed, 192 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "nonreplayable_correction_log or correction_export_input or accepts_eval_candidate_export_as_correction_evidence"
# 4 passed, 192 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "mismatched_roadmap_completion_bare_correction_path or missing_roadmap_completion_correction_input_path or mismatched_roadmap_completion_correction_path or stale_roadmap_completion_correction_path"
# 4 passed, 196 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "roadmap_completion_correction_count_mismatch or zero_valid_correction_count or roadmap_completion_correction_counts"
# 5 passed, 200 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "stale_roadmap_completion_check_counts or stale_roadmap_completion_next_action_counts or false_complete_roadmap_completion"
# 3 passed, 203 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "false_incomplete_roadmap_completion or false_complete_roadmap_completion or stale_roadmap_completion_check_counts"
# 3 passed, 204 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "roadmap_completion_warnings or false_incomplete_roadmap_completion or false_complete_roadmap_completion or stale_roadmap_completion_check_counts"
# 5 passed, 204 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "roadmap_completion_warnings or warn_status_marker"
# 3 passed, 207 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "non_boolean_roadmap_completion_status or false_incomplete_roadmap_completion or false_complete_roadmap_completion or roadmap_completion_warnings"
# 5 passed, 206 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "string_roadmap_completion_check_counts or stale_roadmap_completion_check_counts or non_boolean_roadmap_completion_status or false_complete_roadmap_completion"
# 4 passed, 208 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "string_roadmap_completion_next_action_counts or stale_roadmap_completion_next_action_counts or malformed_roadmap_completion_next_action_item"
# 3 passed, 210 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "non_boolean_roadmap_completion_next_action_review_flag or malformed_roadmap_completion_next_action_item or string_roadmap_completion_next_action_counts"
# 3 passed, 211 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "non_string_roadmap_completion_next_action_text_fields or non_boolean_roadmap_completion_next_action_review_flag or malformed_roadmap_completion_next_action_item"
# 3 passed, 212 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "non_string_roadmap_completion_next_action_command_hint or non_string_roadmap_completion_next_action_text_fields or non_boolean_roadmap_completion_next_action_review_flag"
# 3 passed, 213 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "malformed_roadmap_completion_input_paths or non_string_roadmap_completion_correction_input_path or missing_roadmap_completion_correction_input_path"
# 3 passed, 222 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "malformed_roadmap_completion_identity or malformed_roadmap_completion_input_paths or malformed_roadmap_completion_check_fields"
# 3 passed, 223 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "non_string_roadmap_completion_blockers or stale_roadmap_completion_check_counts or string_roadmap_completion_check_counts"
# 3 passed, 214 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "non_string_roadmap_completion_warnings or stale_roadmap_completion_warnings or unexpected_roadmap_completion_warnings or missing_warn_status_marker"
# 4 passed, 214 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "malformed_roadmap_completion_check_items or stale_roadmap_completion_check_counts or non_string_roadmap_completion_blockers or non_string_roadmap_completion_warnings"
# 4 passed, 215 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "malformed_roadmap_completion_check_fields or malformed_roadmap_completion_check_items or stale_roadmap_completion_check_counts"
# 3 passed, 219 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "does_not_coerce_false_incomplete_fail_count or false_incomplete_roadmap_completion or string_roadmap_completion_check_counts or false_complete_roadmap_completion"
# 4 passed, 219 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "malformed_roadmap_completion_check_evidence or malformed_roadmap_completion_check_fields or malformed_roadmap_completion_check_items"
# 3 passed, 221 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "non_string_roadmap_completion_correction_evidence or stale_roadmap_completion_correction_evidence or mismatched_roadmap_completion_bare_correction_path"
# 3 passed, 217 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "non_string_roadmap_completion_correction_input_path or missing_roadmap_completion_correction_input_path or mismatched_roadmap_completion_correction_path"
# 3 passed, 218 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out /tmp/paperpipe_handoff_package_contract_compatibility_after_release_count_gate.json
# fail_count=0; release-artifact count gates do not change the current reviewer handoff package result

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_handoff.json --print-next-actions --next-action-limit 8
# exit code 1 expected while roadmap blockers remain
# fail_count=13, next_action_count=21, human_review_next_action_count=12
# next_action.1 command_hint now points to apply_paper_understanding_gold_reviewer_handoff.py because the reviewer handoff package exists
# current workspace inventory reports gold_reviewer_handoff_apply_edited_result_count=0 and gold_reviewer_handoff_apply_unedited_result_count=8

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_contract_edit_state.json --print-next-actions --next-action-limit 5
# exit code 1 expected while roadmap blockers remain
# fail_count=13, next_action_count=21, human_review_next_action_count=12

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_reviewer_guide.json --print-next-actions --next-action-limit 5
# exit code 1 expected while roadmap blockers remain
# fail_count=13, next_action_count=21, human_review_next_action_count=12

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_blocked_handoff_apply.json --print-next-actions --next-action-limit 5
# exit code 1 expected while roadmap blockers remain
# fail_count=13, next_action_count=21, human_review_next_action_count=12
# next_action.1 now says to edit reviewer handoff patch templates before re-applying because the current workspace apply package contains only unedited scaffold values

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_stage_release_count_gate.json --print-next-actions --next-action-limit 5
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_task_export_count_gate.json --print-next-actions --next-action-limit 5
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_handoff_package_count_gate.json --print-next-actions --next-action-limit 5
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_release_contract_count_gate.json --print-next-actions --next-action-limit 5
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_log_replay_gate.json --print-next-actions --next-action-limit 5
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_export_gate.json --print-next-actions --next-action-limit 5
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_command_hint_gate.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.10 correction-loop command_hint now writes claim_evidence_eval_candidates.json, matching the default export shape

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_contract_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_contract_requirement.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_noncanonical_posture.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_evidence_posture.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --correction-log storage/claim_evidence_corrections.jsonl --out /tmp/paperpipe_roadmap_completion_with_storage_correction_log_repair_action.json --print-next-actions --next-action-limit 12
# exit code 1 expected while roadmap blockers remain
# structured correction evidence is present but not replayable: valid_count=0, invalid_count=2
# next_action.10 now says to repair or re-export the claim/evidence correction log with before/after evidence refs plus parser/model/prompt/profile lineage

.venv/bin/python scripts/eval/export_claim_evidence_eval_candidates.py --out /tmp/paperpipe_claim_evidence_eval_candidates_current_with_lines.json
# candidate_count=0
# source_record_count=3, source_invalid_record_count=2, skipped_not_accepted_count=1
# source_invalid_record_lines=1,2
# invalid source rows currently miss parser/provider/model/model-version/prompt/profile replay lineage

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard storage/artifacts/paper-e2e-001/run_e2e_fixture_001/evidence_grounding_scorecard.json --correction-log /tmp/paperpipe_claim_evidence_eval_candidates_current_with_lines.json --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_with_current_correction_export_lines.json --print-next-actions --next-action-limit 12
# exit code 1 expected while roadmap blockers remain
# pass_count=1, fail_count=12, roadmap_complete=False
# structured_correction_log evidence includes source_invalid_record_details=line_1:Value error, accepted_for_eval requires parser_version;line_2:Value error, accepted_for_eval requires parser_version
# structured_correction_log evidence includes source_invalid_record_missing_replay_fields=line_1:parser_version,llm_provider,llm_model,llm_model_version,prompt_version,reader_profile_version;line_2:parser_version,llm_provider,llm_model,llm_model_version,prompt_version,reader_profile_version
# current correction export still fails because source correction log lines 1 and 2 are invalid and there are no replayable eval candidates

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_structured_correction_repair_action.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# without an explicit correction evidence path, next_action.10 remains the generic export/provide instruction

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_eval_correction_lineage_guard.json --print-next-actions --next-action-limit 12
# exit code 1 expected while roadmap blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# existing storage/claim_evidence_corrections.jsonl rows remain non-replayable because they were written before lineage was required

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_eval_correction_lineage_ui_gate.json --print-next-actions --next-action-limit 12
# exit code 1 expected while roadmap blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action.10 remains structured_correction_log because existing accepted rows still need repair or replayable export evidence

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_scorecard_candidate_config.json --print-next-actions --next-action-limit 12
# exit code 1 expected while roadmap blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action.5 remains candidate_configuration_lineage until a real fixed-goldset benchmark package is generated with candidate_config on every item

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_complete_candidate_lineage_gate.json --print-next-actions --next-action-limit 12
# exit code 1 expected while roadmap blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action.5 remains candidate_configuration_lineage; partial candidate configs no longer satisfy this completion gate

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_candidate_config_sidecar.json --print-next-actions --next-action-limit 12
# exit code 1 expected while roadmap blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# current live run artifacts still lack complete candidate_config sidecars, so next_action.5 remains

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_scorecard_path_input.json --print-next-actions --next-action-limit 12
# exit code 1 expected while roadmap blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard storage/artifacts/paper-e2e-001/run_e2e_fixture_001/evidence_grounding_scorecard.json --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_with_standalone_scorecard.json --print-next-actions --next-action-limit 12
# exit code 1 expected while roadmap blockers remain
# pass_count=1, fail_count=12, roadmap_complete=False
# next_action_count=20, human_review_next_action_count=11
# standalone scorecard evidence satisfies additive_noncanonical_artifacts only

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_stale_correction_evidence_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_evidence_taxonomy_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_input_help_contract.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_path_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_path_input_consistency.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_input_path_presence.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_bare_path_consistency.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_count_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_fail_count_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_correction_zero_valid_count_regression.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_summary_count_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_false_incomplete_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_warning_marker_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_warn_marker_coverage.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_status_boolean_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_summary_count_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_next_action_count_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_next_action_review_flag_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_next_action_text_field_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_next_action_command_hint_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_blocker_ids_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_warning_entries_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_check_entries_compatibility.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_correction_evidence_types.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_check_field_types.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_status_fail_count_types.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_check_payload_fields.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_input_path_provenance.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_audit_identity.json --print-next-actions --next-action-limit 10
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.1 remains human patch-template editing before re-applying the blocked reviewer handoff package

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --correction-log storage/claim_evidence_corrections.jsonl --out /tmp/paperpipe_roadmap_completion_with_storage_correction_log_path_hint.json --print-next-actions --next-action-limit 12
# exit code 1 expected while roadmap blockers remain
# fail_count=13, roadmap_complete=False, next_action_count=21, human_review_next_action_count=12
# next_action.10 is the structured-correction repair/re-export action and its command hint includes --log-path /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_guide_inventory.json --print-next-actions --next-action-limit 5
# exit code 1 expected while roadmap blockers remain
# gold_reviewer_handoff_guide_path_count=1, existing_gold_reviewer_handoff_guide_count=1, missing_gold_reviewer_handoff_guide_count=0
```

Additional CLI inventory check for the current workspace:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset/accepted --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_inventory_check.json
# exit 1 as expected while blockers remain; workspace_evidence_inventory_ready reports 0 release-readiness reports and 0 release packages
```

Additional targeted check for scorecard and benchmark consistency-label integration:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py
# 195 passed, 5 warnings
```

Additional targeted check for contract compatibility failure-taxonomy validation:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "unknown_comparison_failure_code or unknown_benchmark_failure_code or unknown_scorecard_failure_code"
# 3 passed, 155 deselected, 5 warnings
```

Additional targeted check for roadmap-completion next-action surfacing:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "roadmap_completion_audit_requires_gold_release_readiness or roadmap_completion_cli_exits_nonzero_when_blocked or roadmap_completion_api_accepts_workspace_inventory_fields"
# 3 passed, 155 deselected, 5 warnings
```

Additional current-workspace next-action CLI check:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset/accepted --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_print_actions.json --print-next-actions --next-action-limit 5
# exit 1 as expected while blockers remain; prints next_action_count=22, human_review_next_action_count=13, phase counts, and the first five next_action rows with phase, requires_human_review, and command_hint values where available
```

Additional targeted check for contract compatibility coverage:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "contract_compatibility"
# 15 passed, 143 deselected, 5 warnings
```

Additional targeted check for scorecard visual/gold metrics:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py
# 37 passed, 5 warnings
```

Additional targeted check for scorecard failure-taxonomy validation:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q -k "unknown_failure_codes or metric_validation"
# 3 passed, 34 deselected, 5 warnings
```

Additional targeted check for bounded contradiction proxy routing:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q -k "claim_evidence_direct_contradiction or direct_text_polarity_contradiction or visual_direct_contradiction"
# 3 passed, 32 deselected, 5 warnings
```

Additional targeted check for benchmark regression gating on the new proxy:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "claim_evidence_contradiction_proxy_regression or contradiction_regression"
# 2 passed, 153 deselected, 5 warnings
```

Additional current-workspace completion audit after strict roadmap-completion posture compatibility:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_completion_posture.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict handoff inventory count typing:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_handoff_inventory_counts.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# current workspace handoff inventory reports malformed_gold_reviewer_handoff_apply_package_count=0 and malformed_gold_reviewer_handoff_stage_package_count=0
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict release-prep inventory count typing:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_release_prep_inventory_counts.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# current workspace reports gold_reviewer_handoff_release_prep_package_count=0 and malformed_gold_reviewer_handoff_release_prep_package_count=0
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict gold release inventory count typing:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_gold_release_inventory_counts.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# current workspace reports zero release split-plan/readiness/package artifacts, with zero valid/ready/invalid release artifact counts
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict linked release-readiness consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_linked_release_readiness_inventory.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# current workspace reports zero release split-plan/readiness/package artifacts, with zero consistent release package count
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict required-run-sidecar JSON inventory:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_run_artifact_inventory.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# workspace inventory evidence includes scanned_run_dir_count=90, ready_run_dir_count=4, matched_ready_gold_run_count=0, ready_run_required_artifact_error_count=0
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict fixed-goldset run-readiness required-sidecar fields:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_run_readiness_required_artifacts.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict fixed-goldset run-readiness count consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_run_readiness_count_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict fixed-goldset comparison-suite readiness consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_comparison_suite_readiness_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict fixed-goldset comparison-suite package counts:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_comparison_suite_package_counts.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict benchmark run-package counts:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_benchmark_run_package_counts.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict threshold-adoption package counts:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_threshold_package_counts.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict benchmark manifest-package counts:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_benchmark_manifest_package_counts.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict threshold-calibration counts:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_threshold_calibration_counts.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict threshold-adoption review counts:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_threshold_adoption_review_counts.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict comparison decision consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_comparison_decision_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict contract-readiness summary consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_contract_readiness_summary.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict contract-compatibility summary consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_contract_compatibility_summary.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict contract artifact-path coverage:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_contract_artifact_path_coverage.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict threshold-package linked review consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_threshold_package_linked_review_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict comparison-suite package linked run-package consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_suite_package_linked_run_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict benchmark run-package linked report consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_run_package_linked_report_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict benchmark manifest-package linked manifest consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_manifest_package_linked_manifest_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict gold release-package linked readiness consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_gold_release_package_linked_readiness_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff package linked task-export consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_handoff_package_linked_task_export_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff apply/stage linked task-export consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_apply_stage_linked_task_export_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff apply linked patch-result manifest consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_apply_linked_patch_manifest_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff apply linked progress-report consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_apply_linked_progress_report_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff stage linked progress-report consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_stage_linked_progress_report_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff stage linked staging-manifest consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_stage_linked_staging_manifest_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff release-prep linked split-plan consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_release_prep_linked_split_plan_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff release-prep linked release-package consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_release_prep_linked_release_package_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff release-prep linked readiness consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_release_prep_linked_readiness_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff release-prep linked stage-package consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_release_prep_linked_stage_package_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff release-prep linked stage-package sidecar consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_release_prep_linked_stage_sidecars.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff release-prep linked staging-manifest consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_release_prep_linked_staging_manifest_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff apply linked handoff-package consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_apply_linked_handoff_package_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff stage linked apply-package consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_stage_linked_apply_package_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional current-workspace completion audit after strict reviewer-handoff stage linked handoff-package consistency:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_after_strict_stage_linked_handoff_package_consistency.json --print-next-actions --next-action-limit 10
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=12
# next_action_phase_counts=completion_evidence:1,contract_readiness:2,correction_loop:1,fixed_goldset_run:8,gold_curation_and_release:5,threshold_adoption:2,threshold_package:2
# first next action remains human review: edit reviewer handoff patch templates before re-applying; current apply packages contain only unedited scaffold values
```

Additional check after refining per-check roadmap next actions:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 277 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_refined_checks.json --print-next-actions --next-action-limit 3
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# first top-level action remains human review: edit reviewer handoff patch templates before re-applying with --require-edited
# fixed_goldset_release_readiness.check.next_actions now carries the same concrete reviewer-template edit/re-apply action
```

Additional check after adding the workspace run-readiness command hint:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_run_readiness_hint.json --print-next-actions --next-action-limit 22
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# workspace run-directory next action now points to audit_evidence_grounding_fixed_goldset_run_readiness.py

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 277 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 437 passed, 5 warnings
```

Additional check after correcting the threshold-package build command hint:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_threshold_package_hint.json --print-next-actions --next-action-limit 18
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# fixed_goldset_threshold_adoption_package_ready build action now points to run_evidence_grounding_fixed_goldset_comparison_from_benchmark_run_packages.py
# fixed_goldset_threshold_adoption_package_ready review action still points to review_evidence_grounding_threshold_adoption_from_comparison_suite_package.py

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 277 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 437 passed, 5 warnings
```

Additional check after correcting the production-threshold calibration command hint:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_threshold_calibration_hint.json --print-next-actions --next-action-limit 16
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# production_threshold_adoption_reviewed calibration action now points to calibrate_evidence_grounding_thresholds_from_comparison_suite.py
# production_threshold_adoption_reviewed review action still points to review_evidence_grounding_threshold_adoption_from_comparison_suite_package.py

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 277 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 437 passed, 5 warnings
```

Additional check after refining human-review routing for automated threshold-prep actions:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_human_review_flags.json --print-next-actions --next-action-limit 18
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=10
# production_threshold_adoption_reviewed calibration action is requires_human_review=False and points to calibrate_evidence_grounding_thresholds_from_comparison_suite.py
# fixed_goldset_threshold_adoption_package_ready build action is requires_human_review=False and points to run_evidence_grounding_fixed_goldset_comparison_from_benchmark_run_packages.py
# the paired threshold-adoption and threshold-package review actions remain requires_human_review=True

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "requires_all_p0_threshold_adoption_metrics or can_pass_with_all_review_evidence"
# 2 passed, 275 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 277 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 437 passed, 5 warnings
```

Additional check after routing additive scorecard evidence as CLI-backed preparation:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_additive_scorecard_hint.json --print-next-actions --next-action-limit 14
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=9
# additive_noncanonical_artifacts action is requires_human_review=False and points to build_evidence_grounding_scorecard.py

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "guides_additive_scorecard_evidence or accepts_standalone_scorecard_evidence"
# 2 passed, 276 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 278 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 438 passed, 5 warnings
```

Additional check after routing workspace inventory prep actions out of the human-review count:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_workspace_prep_flags.json --print-next-actions --next-action-limit 24
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=7
# workspace run-directory action is requires_human_review=False and points to audit_evidence_grounding_fixed_goldset_run_readiness.py
# workspace release-package action is requires_human_review=False and points to package_paper_understanding_gold_release_from_staged_gold.py
# workspace reviewer-handoff template edit/re-apply action remains requires_human_review=True

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_malformed_gold_release_inventory_counts tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_api_accepts_workspace_inventory_fields -q
# 2 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 278 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 438 passed, 5 warnings
```

Additional check after routing release-readiness and contract audit prep out of the human-review count:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_audit_prep_flags.json --print-next-actions --next-action-limit 24
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=5
# fixed_goldset_release_readiness release-readiness audit action is requires_human_review=False
# external_contract_readiness_reviewed contract compatibility/readiness execution action is requires_human_review=False
# handoff template edit, threshold-adoption review, threshold-package review, and external approval actions remain requires_human_review=True

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_requires_gold_release_readiness tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_requires_contract_schema_coverage -q
# 2 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 278 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 438 passed, 5 warnings
```

Additional check after splitting external-contract compatibility and approval command hints:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_contract_hint_split.json --print-next-actions --next-action-limit 18
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=5
# external_contract_readiness_reviewed compatibility action points to check_evidence_grounding_contract_compatibility.py without approval flags
# external_contract_readiness_reviewed approval action still points to audit_evidence_grounding_contract_readiness_from_threshold_adoption_package.py with reviewer approval input

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_requires_contract_schema_coverage -q
# 1 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 278 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 438 passed, 5 warnings
```

Additional check after adding unique human-review next-action counts:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_unique_human_review_count.json --print-next-actions --next-action-limit 21
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=5, human_review_unique_next_action_count=4
# unique count deduplicates the repeated reviewer-handoff edit/re-apply task across fixed-gold and workspace-inventory blocker provenance

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_completion_without_next_actions tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_completion_next_action_counts tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_string_roadmap_completion_next_action_counts tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_exits_nonzero_when_blocked tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_workspace_actions_advance_existing_handoff -q
# 5 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 278 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 438 passed, 5 warnings
```

Additional check after adding the derived unique human-review task list:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_unique_human_review_actions.json --print-next-actions --next-action-limit 21
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=5, human_review_unique_next_action_count=4
# human_review_unique_next_actions lists the four distinct human tasks: reviewer-handoff edit/re-apply, threshold-adoption review, threshold-package review, and external approval/readiness evidence

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_completion_without_next_actions tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_completion_next_action_counts tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_string_roadmap_completion_next_action_counts tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_exits_nonzero_when_blocked tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_workspace_actions_advance_existing_handoff -q
# 5 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 278 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 438 passed, 5 warnings
```

Additional check after adding CLI printing for the unique human-review task list:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_completion_print_human_review_actions.json --print-human-review-actions
# exit 1 as expected while blockers remain
# pass_count=0, fail_count=13, roadmap_complete=False
# next_action_count=21, human_review_next_action_count=5, human_review_unique_next_action_count=4
# prints human_review_action.1 through human_review_action.4 for reviewer-handoff edit/re-apply, threshold-adoption review, threshold-package review, and external approval/readiness evidence

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_exits_nonzero_when_blocked -q
# 1 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_comparison_suite_package_cli tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package_cli -q
# 2 passed, 5 warnings
# package-derived CLIs now cover summary counts, phase counts, limited full next-action printing, and unique human-review printing

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 278 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q
# 438 passed, 5 warnings
```

Additional check after adding structured CLI findings for reviewer-handoff `--require-edited` failures:

```bash
.venv/bin/python -m py_compile scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py
# pass

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py::test_reviewer_handoff_apply_package_can_require_edited_templates tests/test_paper_understanding_gold.py::test_reviewer_handoff_apply_cli_can_require_edited_templates tests/test_paper_understanding_gold.py::test_reviewer_handoff_apply_api_can_require_edited_templates -q
# 3 passed, 5 warnings
# CLI failures now print finding_count and finding.N rows, matching the structured API findings while preserving the existing error line.

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py -q
# 97 passed, 5 warnings

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py tests/test_runtime_paths_logs.py -q
# 359 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue6_probe.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# pass_count=1, fail_count=12, roadmap_complete=False
# next_action_count=3, human_review_next_action_count=2, human_review_unique_next_action_count=1
# immediate actions remain: edit/re-apply reviewer handoff templates and repair/re-export replayable correction evidence
```

Additional check after adding correction-log repair targets to replayability diagnostics:

```bash
.venv/bin/python -m py_compile scripts/eval/export_claim_evidence_eval_candidates.py src/services/claim_evidence_corrections.py src/schemas/claim_evidence_correction.py
# pass

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py::test_claim_evidence_eval_candidates_export_route_can_require_replayable_evidence tests/test_claim_evidence_corrections_api.py::test_claim_evidence_eval_candidates_export_script_can_require_replayable_evidence -q
# 2 passed, 5 warnings

.venv/bin/python scripts/eval/export_claim_evidence_eval_candidates.py --log-path /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --out /tmp/paperpipe_claim_evidence_eval_candidates_repair_targets_probe.json --require-replayable
# exit 1 as expected while blocker remains
# candidate_count=0, source_record_count=3, source_invalid_record_count=2, skipped_not_accepted_count=1
# source_invalid_record_repair_targets identifies the two accepted invalid source records by correction_id, paper_id, run_id, and claim_id

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py -q
# 25 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py tests/test_runtime_paths_logs.py -q
# 431 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue7_probe.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# pass_count=1, fail_count=12, roadmap_complete=False
# next_action_count=3, human_review_next_action_count=2, human_review_unique_next_action_count=1
```

Additional check after carrying correction repair targets into roadmap completion audit evidence:

```bash
.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_eval_candidate_export_with_invalid_source_records -q
# 1 passed, 5 warnings

.venv/bin/python scripts/eval/export_claim_evidence_eval_candidates.py --log-path /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --out /tmp/paperpipe_claim_evidence_eval_candidates_repair_targets_for_audit.json --require-replayable
# exit 1 as expected while blocker remains
# source_invalid_record_repair_targets identifies correction IDs 79a4f99f-17da-4262-ac42-cd321ea30516 and 8de43cdd-6513-4e9f-8120-584131b6e887

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --correction-log /tmp/paperpipe_claim_evidence_eval_candidates_repair_targets_for_audit.json --out /tmp/paperpipe_roadmap_continue8_probe.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# structured_correction_log evidence includes source_invalid_record_repair_targets for the two invalid accepted source records
# structured_correction_log next action now says to repair the listed source claim/evidence correction records before re-exporting

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 289 passed, 5 warnings

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py -q
# 25 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_evidence_grounding_scorecard.py tests/test_runtime_paths_logs.py -q
# 142 passed, 5 warnings
```

Additional check after printing correction repair targets from the standalone roadmap-completion CLI:

```bash
.venv/bin/python -m py_compile scripts/eval/audit_evidence_grounding_roadmap_completion.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_prints_correction_repair_targets tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_eval_candidate_export_with_invalid_source_records -q
# 2 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --correction-log /tmp/paperpipe_claim_evidence_eval_candidates_repair_targets_for_audit.json --out /tmp/paperpipe_roadmap_continue9_probe.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# stdout now includes structured_correction_repair_targets for the two invalid accepted source records

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 290 passed, 5 warnings

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py tests/test_paper_understanding_gold.py tests/test_evidence_grounding_scorecard.py tests/test_runtime_paths_logs.py -q
# 167 passed, 5 warnings
```

Additional check after adding source correction-log provenance to eval-candidate exports and roadmap command hints:

```bash
.venv/bin/python -m py_compile src/schemas/claim_evidence_correction.py src/services/claim_evidence_corrections.py backend/routers/claim_evidence_corrections.py scripts/eval/export_claim_evidence_eval_candidates.py src/services/evidence_grounding_benchmark.py
# pass

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py::test_claim_evidence_eval_candidates_export_route_can_require_replayable_evidence tests/test_claim_evidence_corrections_api.py::test_claim_evidence_eval_candidates_export_script_can_require_replayable_evidence tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_eval_candidate_export_with_invalid_source_records tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_prints_correction_repair_targets -q
# 4 passed, 5 warnings

.venv/bin/python scripts/eval/export_claim_evidence_eval_candidates.py --log-path /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --out /tmp/paperpipe_claim_evidence_eval_candidates_source_path.json --require-replayable
# exit 1 as expected while blocker remains
# stdout includes source_correction_log_path plus missing replay fields and repair targets

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --correction-log /tmp/paperpipe_claim_evidence_eval_candidates_source_path.json --out /tmp/paperpipe_roadmap_continue10_probe.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# structured_correction_log command_hint now restores --log-path /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_benchmark.py -q
# 315 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_evidence_grounding_scorecard.py tests/test_runtime_paths_logs.py -q
# 142 passed, 5 warnings
```

Additional check after adding reviewer-handoff unedited patch-template path samples:

```bash
.venv/bin/python -m py_compile src/services/paper_understanding_gold_drafts.py scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py backend/routers/paper_understanding_gold.py
# pass

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py::test_reviewer_handoff_apply_package_can_require_edited_templates tests/test_paper_understanding_gold.py::test_reviewer_handoff_apply_cli_can_require_edited_templates tests/test_paper_understanding_gold.py::test_reviewer_handoff_apply_api_can_require_edited_templates -q
# 3 passed, 5 warnings

.venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out-dir /tmp/paperpipe_handoff_apply_probe --out /tmp/paperpipe_handoff_apply_probe/package.json --require-edited
# exit 1 as expected while human edits remain required
# stdout includes unedited_patch_result_count=8 and unedited_patch_template_paths_sample with five current patch-template paths

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py -q
# 97 passed, 5 warnings

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_benchmark.py tests/test_evidence_grounding_scorecard.py tests/test_runtime_paths_logs.py -q
# 360 passed, 5 warnings
```

Additional check after adding reviewer-handoff unedited patch-template path counts:

```bash
.venv/bin/python -m py_compile src/services/paper_understanding_gold_drafts.py scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py backend/routers/paper_understanding_gold.py
# pass

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py::test_reviewer_handoff_apply_package_can_require_edited_templates tests/test_paper_understanding_gold.py::test_reviewer_handoff_apply_cli_can_require_edited_templates tests/test_paper_understanding_gold.py::test_reviewer_handoff_apply_api_can_require_edited_templates -q
# 3 passed, 5 warnings

.venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out-dir /tmp/paperpipe_handoff_apply_probe_count --out /tmp/paperpipe_handoff_apply_probe_count/package.json --require-edited
# exit 1 as expected while human edits remain required
# stdout includes unedited_patch_template_path_count=8 alongside the five-path sample
```

Additional check after carrying reviewer-handoff patch-template path samples into roadmap inventory/stdout:

```bash
.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py scripts/eval/audit_evidence_grounding_roadmap_completion.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_workspace_actions_advance_existing_handoff tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_prints_handoff_template_paths -q
# 2 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue11_probe.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# stdout includes gold_reviewer_handoff_patch_template_paths_sample with five current patch-template paths and ...3_more

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 291 passed, 5 warnings

.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_runtime_paths_logs.py -q
# 167 passed, 5 warnings
```

Additional check after auto-selecting workspace correction evidence for the structured-correction audit check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "existing_workspace_correction_log or existing_workspace_scorecard or rejects_nonreplayable_correction_log or accepts_eval_candidate_export_as_correction_evidence or rejects_eval_candidate_export_with_invalid_source_records"
# 5 passed, 286 deselected, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue13_probe.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# warnings include correction_log_path_selected_from_workspace
# structured_correction_log evidence includes /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl, correction_evidence_kind=raw_correction_jsonl, correction_evidence_posture=raw_memory_noncanonical, valid_count=0, and invalid_count=3
```

Additional check after exposing raw correction-log source diagnostics directly in roadmap completion:

```bash
.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "existing_workspace_correction_log or rejects_nonreplayable_correction_log or rejects_eval_candidate_export_with_invalid_source_records"
# 3 passed, 288 deselected, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue14_after.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# stdout now includes structured_correction_repair_targets directly from the raw correction JSONL path
# structured_correction_log evidence includes source_invalid_record_count=2, source_invalid_record_lines=1,2, missing parser/provider/model/model-version/prompt/profile fields, and correction/paper/run/claim repair targets
```

Additional check after printing missing replay fields from the standalone roadmap-completion CLI:

```bash
.venv/bin/python -m py_compile scripts/eval/audit_evidence_grounding_roadmap_completion.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_prints_correction_repair_targets -q
# 1 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue15_after.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# stdout now includes structured_correction_missing_replay_fields for lines 1 and 2 alongside structured_correction_repair_targets
```

Additional check after printing correction invalid details from the standalone roadmap-completion CLI:

```bash
.venv/bin/python -m py_compile scripts/eval/audit_evidence_grounding_roadmap_completion.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_prints_correction_repair_targets -q
# 1 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue16_after.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# stdout now includes structured_correction_invalid_details for lines 1 and 2 alongside repair targets and missing replay fields
```

Additional check after carrying correction diagnostics into package-derived roadmap-completion CLIs:

```bash
.venv/bin/python -m py_compile scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package_cli tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_comparison_suite_package_cli -q
# 2 passed, 5 warnings
```

Additional check after carrying reviewer-handoff patch-template samples into package-derived roadmap-completion CLIs:

```bash
.venv/bin/python -m py_compile scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package_cli tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_comparison_suite_package_cli -q
# 2 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 291 passed, 5 warnings
```

Additional check after adding reviewer-handoff patch-template path counts to roadmap inventory/stdout:

```bash
.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py scripts/eval/audit_evidence_grounding_roadmap_completion.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_prints_handoff_template_paths tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_workspace_actions_advance_existing_handoff tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package_cli tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_comparison_suite_package_cli -q
# 4 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue17_after.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# stdout now includes gold_reviewer_handoff_patch_template_path_count=8 before the bounded path sample
```

Additional check after adding reviewer-handoff patch-template count/sample detail to roadmap next-action text:

```bash
.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py scripts/eval/audit_evidence_grounding_roadmap_completion.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_workspace_actions_advance_existing_handoff tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_workspace_actions_do_not_stage_blocked_apply -q
# 2 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue18_after.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# next_action.1 and next_action.3 include "8 patch templates" plus one concrete patch-template path
# stdout still includes structured correction repair targets, missing replay fields, invalid details, patch-template path count, and bounded path sample

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 291 passed, 5 warnings
```

Additional check after adding correction repair target/missing-field detail to roadmap next-action text:

```bash
.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_guides_existing_workspace_correction_log tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_nonreplayable_correction_log tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_eval_candidate_export_with_invalid_source_records -q
# 3 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue19_after.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# next_action.2 now includes "2 invalid accepted records", the first source correction target, and the first missing replay-field set

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 291 passed, 5 warnings
```

Additional check after routing structured-correction source repair as human/evidence-bound:

```bash
.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_guides_existing_workspace_correction_log tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_nonreplayable_correction_log tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_eval_candidate_export_with_invalid_source_records -q
# 3 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue20_after.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# human_review_next_action_count=3 and human_review_unique_next_action_count=2
# human_review_action.2 is the structured-correction source repair action with the invalid-row count, first repair target, and missing replay fields

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 291 passed, 5 warnings
```

Additional check after locking structured-correction prep/repair human-review routing boundaries:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_routes_structured_correction_export_as_prep tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_guides_existing_workspace_correction_log tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_nonreplayable_correction_log tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_eval_candidate_export_with_invalid_source_records -q
# 4 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue21_after.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# human_review_next_action_count=3 and human_review_unique_next_action_count=2 remain unchanged

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 292 passed, 5 warnings
```

Additional check after printing prerequisite-gated blocked checks without immediate actions:

```bash
.venv/bin/python -m py_compile scripts/eval/audit_evidence_grounding_roadmap_completion.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_exits_nonzero_when_blocked tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package_cli tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_comparison_suite_package_cli -q
# 3 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue22_after.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# stdout includes blocked_without_next_action_count=9 and the prerequisite-gated downstream blocker ids

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 292 passed, 5 warnings
```

Additional check after promoting prerequisite-gated blocked-check summary into the roadmap report contract:

```bash
.venv/bin/python -m py_compile src/schemas/evidence_grounding_benchmark.py src/services/evidence_grounding_benchmark.py scripts/eval/audit_evidence_grounding_roadmap_completion.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py
# pass

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_completion_without_next_actions tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_completion_next_action_counts tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_string_roadmap_completion_next_action_counts -q
# 3 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_exits_nonzero_when_blocked tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package_cli tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_comparison_suite_package_cli -q
# 3 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue23_after.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# JSON and stdout both report blocked_without_next_action_count=9 plus the same prerequisite-gated downstream blocker ids

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 292 passed, 5 warnings
```

Additional API-first check for the prerequisite-gated blocked-check summary:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_api_returns_noncanonical_report tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_completion_without_next_actions tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_exits_nonzero_when_blocked -q
# 3 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 292 passed, 5 warnings
```

Additional package-derived API check for the prerequisite-gated blocked-check summary:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_api_returns_noncanonical_report tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_from_threshold_adoption_package_api tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_from_comparison_suite_package_api -q
# 3 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 292 passed, 5 warnings
```

Additional positive contract-compatibility check for current roadmap completion artifacts:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/paperpipe_roadmap_continue24_live.json --print-next-actions --next-action-limit 20 --print-human-review-actions
# exit 1 as expected while blockers remain
# live roadmap artifact includes blocked_without_next_action_count=9

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/paperpipe_roadmap_continue24_live.json --out /tmp/paperpipe_roadmap_continue24_compat.json
# pass; fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_current_roadmap_completion tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_api_returns_noncanonical_report tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_completion_next_action_counts -q
# 3 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 293 passed, 5 warnings
```

Additional API-first scorecard default-output check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_defaults_to_run_dir_noncanonical_output -q
# 1 passed, 5 warnings
```

This locks the `POST /evidence-grounding/scorecards/build` default write path as an additive run-directory `evidence_grounding_scorecard.json` artifact, with source sidecars unchanged, `review_gate_artifact` / `non_canonical` posture, core input diagnostics, and input-health runtime proxy metrics.

Additional CLI default-output source-preservation check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_defaults_to_run_dir_without_mutating_sources -q
# 1 passed, 5 warnings
```

This keeps the operator CLI aligned with the API-first service contract: the default output is an additive scorecard sidecar, not a mutation of existing deepread inputs.

Additional invalid-gold failure-path check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_invalid_external_gold_without_partial_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_invalid_external_gold_without_partial_write -q
# 2 passed, 5 warnings
```

This verifies malformed external eval-only gold fails before either API or CLI writes the default run-directory scorecard output, while preserving source deepread sidecars.

Additional standalone scorecard compatibility check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_standalone_scorecard tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_from_comparison_suite_covers_schema_family -q
# 2 passed, 5 warnings
```

This keeps the raw `evidence_grounding_scorecard.v1` artifact path accepted by compatibility review directly, while the existing comparison-suite check continues to cover embedded scorecards.

Additional strict scorecard schema check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_scorecard_schema_rejects_unknown_top_level_fields tests/test_evidence_grounding_scorecard.py::test_scorecard_metric_schema_rejects_unknown_fields tests/test_evidence_grounding_scorecard.py::test_scorecard_build_request_rejects_unknown_fields -q
# 3 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_unknown_request_fields_without_partial_write tests/test_evidence_grounding_scorecard.py::test_scorecard_build_request_rejects_unknown_fields -q
# 2 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_unknown_candidate_config_fields_without_partial_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_unknown_candidate_config_fields_without_partial_write -q
# 2 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_extra_scorecard_fields tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_standalone_scorecard -q
# 2 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_scorecard_schema_rejects_blank_identity_fields tests/test_evidence_grounding_scorecard.py::test_scorecard_schema_rejects_blank_recommended_next_action -q
# 2 passed, 5 warnings

.venv/bin/python -m py_compile src/schemas/evidence_grounding_scorecard.py
# pass
```

This makes `evidence_grounding_scorecard.v1` and its build request reject unknown fields instead of silently accepting contract drift, including nested candidate configuration at the FastAPI and CLI boundaries before any scorecard output is written. It also keeps scorecard paper/run identity and the recommended next action non-empty.

Additional explicit-output source-artifact guard check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_source_sidecar_out_without_partial_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_source_sidecar_out_without_partial_write tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_writes_scorecard_with_external_gold tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_writes_noncanonical_scorecard_with_sources -q
# 4 passed, 5 warnings
```

This verifies explicit API/CLI output paths fail before write when they would overwrite an existing run source artifact such as `reader_eval.json`, while preserving normal external-output and non-canonical scorecard write paths.

Additional FastAPI client-error status check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_missing_run_directory_without_write tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_invalid_external_gold_without_partial_write tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_source_sidecar_out_without_partial_write -q
# 3 passed, 5 warnings
```

This keeps fail-closed scorecard build input errors API-first and operator-readable: missing run directories, malformed external gold files, and protected source-sidecar output paths now return `400` while preserving the same no-partial-write behavior.

Additional standalone CLI input-error output check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_missing_run_directory_without_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_invalid_external_gold_without_partial_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_source_sidecar_out_without_partial_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_unknown_candidate_config_fields_without_partial_write -q
# 4 passed, 5 warnings
```

This keeps standalone operator failures concise and replayable: the CLI exits with code `2`, prints a single `[evidence_grounding_scorecard] error=...` line, and avoids traceback output for user-correctable scorecard build inputs while preserving no-partial-write checks.

Additional API/CLI path-masked input-error check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_missing_run_directory_without_write tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_invalid_external_gold_without_partial_write tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_source_sidecar_out_without_partial_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_missing_run_directory_without_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_invalid_external_gold_without_partial_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_source_sidecar_out_without_partial_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_unknown_candidate_config_fields_without_partial_write -q
# 7 passed, 5 warnings
```

This verifies scorecard API/CLI input-error messages keep actionable filenames such as `missing-run`, `invalid_gold.json`, and `reader_eval.json`, while masking local absolute path prefixes from user-facing error payloads and stderr.

Additional standalone CLI success-output path-masking check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_defaults_to_run_dir_without_mutating_sources tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_missing_run_directory_without_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_invalid_external_gold_without_partial_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_source_sidecar_out_without_partial_write -q
# 4 passed, 5 warnings
```

This verifies the CLI still writes to the real scorecard output path, while the user-facing success `out=` line and input-error stderr mask local absolute path prefixes.

Additional FastAPI route log/detail path-masking check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_invalid_external_gold_without_partial_write tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_missing_run_directory_without_write tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_source_sidecar_out_without_partial_write -q
# 3 passed, 5 warnings
```

This verifies the scorecard route masks local absolute path prefixes before returning FastAPI error details and writing route warning logs, while still preserving actionable filenames and no-partial-write checks.

Additional FastAPI response source-artifact path-masking check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_writes_scorecard_with_external_gold tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_defaults_to_run_dir_noncanonical_output tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_explicit_candidate_config_overrides_run_local_sidecar -q
# 3 passed, 5 warnings
```

This verifies the API response masks local absolute prefixes in external `source_artifacts`, while the scorecard JSON written to disk keeps the real source path for non-canonical lineage review.

Additional empty-run-directory boundary check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_scorecard_from_run_dir_rejects_empty_run_directory tests/test_evidence_grounding_scorecard.py::test_evidence_grounding_scorecard_build_api_rejects_empty_run_directory_without_write tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_cli_rejects_empty_run_directory_without_write tests/test_evidence_grounding_scorecard.py::test_scorecard_uses_available_proxy_metrics_when_coverage_is_missing -q
# 4 passed, 5 warnings
```

This verifies run-directory rebuilds fail before output when no loadable core scorecard sidecar is present, while partial runs with at least one loaded core sidecar continue to produce warning-rich non-canonical scorecards.

Additional direct-builder no-core-input boundary check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_rejects_without_core_inputs tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_separates_proxy_from_gold_metrics tests/test_evidence_grounding_scorecard.py::test_scorecard_from_run_dir_rejects_empty_run_directory tests/test_evidence_grounding_scorecard.py::test_scorecard_uses_available_proxy_metrics_when_coverage_is_missing tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_refuses_mismatched_gold_identity -q
# 5 passed, 5 warnings
```

This verifies the lower-level scorecard builder shares the same loaded-core-input invariant as run-directory rebuilds, while preserving normal full, partial, and mismatched-gold behaviors.

Additional spoofed-diagnostics boundary check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_rejects_spoofed_loaded_core_diagnostics_without_core_inputs tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_rejects_without_core_inputs tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_separates_proxy_from_gold_metrics tests/test_evidence_grounding_scorecard.py::test_scorecard_from_run_dir_rejects_empty_run_directory tests/test_evidence_grounding_scorecard.py::test_scorecard_uses_available_proxy_metrics_when_coverage_is_missing -q
# 5 passed, 5 warnings
```

This verifies caller-supplied `input_artifact_diagnostics` cannot spoof a loaded core sidecar when the actual core sidecar objects are absent.

Additional core-diagnostics reconciliation check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_reconciles_core_diagnostics_with_actual_inputs tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_rejects_spoofed_loaded_core_diagnostics_without_core_inputs tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_separates_proxy_from_gold_metrics tests/test_evidence_grounding_scorecard.py::test_scorecard_from_run_dir_warns_on_malformed_sidecar -q
# 4 passed, 5 warnings
```

This verifies misleading caller-supplied core diagnostics are reconciled from actual loaded core sidecar objects, while malformed `load_failed` diagnostics and non-core diagnostics are preserved.

Additional contract-compatibility source-artifact trace check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_standalone_scorecard tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_loaded_core_diagnostic_without_source_artifact -q
# 2 passed, 5 warnings
```

This verifies standalone scorecard compatibility rejects stale scorecards whose loaded core input diagnostics are not backed by matching core filenames in `source_artifacts`.

Additional roadmap-completion check evidence check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_roadmap_check_without_evidence tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_current_roadmap_completion -q
# 2 passed, 5 warnings
```

This verifies current roadmap-completion artifacts still pass compatibility, and stale roadmap-completion artifacts with empty check evidence are rejected for any check status.

Additional roadmap-completion per-check next-action consistency check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_passed_roadmap_check_with_next_actions tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_current_roadmap_completion -q
# 2 passed, 5 warnings
```

This verifies stale roadmap-completion artifacts cannot attach per-check next actions to a check that no longer fails, while current roadmap-completion artifacts remain compatibility-clean.

Additional roadmap-completion top-level next-action provenance check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_top_level_roadmap_next_action_without_check_source tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_current_roadmap_completion -q
# 2 passed, 5 warnings
```

This verifies stale roadmap-completion artifacts cannot inject a top-level next-action row that no failed check requested, while current roadmap-completion artifacts remain compatibility-clean.

Additional roadmap-completion next-action metadata consistency check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_next_action_metadata tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_current_roadmap_completion -q
# 2 passed, 5 warnings
```

This verifies stale roadmap-completion artifacts cannot edit top-level next-action metadata such as `phase`, while current roadmap-completion artifacts remain compatibility-clean.

Additional roadmap-completion duplicate next-action check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_duplicate_top_level_roadmap_next_action tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_current_roadmap_completion -q
# 2 passed, 5 warnings
```

This verifies stale roadmap-completion artifacts cannot duplicate top-level operator handoff rows while keeping summary counts self-consistent.

Additional roadmap-completion next-action order check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_reordered_top_level_roadmap_next_actions tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_current_roadmap_completion -q
# 2 passed, 5 warnings
```

This verifies stale roadmap-completion artifacts cannot reorder top-level operator handoff rows away from the service-derived failed-check priority while keeping summary counts self-consistent.

Additional roadmap-completion per-check blank next-action check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_blank_roadmap_check_next_action tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_current_roadmap_completion -q
# 2 passed, 5 warnings
```

This verifies stale roadmap-completion artifacts cannot hide a failed check behind a blank per-check next-action string that is neither a useful handoff nor a true blocked-without-action state.

Additional roadmap-completion missing next-action metadata check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_missing_roadmap_next_action_metadata tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_next_action_metadata tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_current_roadmap_completion -q
# 3 passed, 5 warnings
```

This verifies stale roadmap-completion artifacts cannot omit top-level next-action `phase` or `requires_human_review` metadata and then repair the summary counts to look self-consistent.

Additional roadmap-completion unique human-review metadata check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_human_review_unique_metadata tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_rejects_stale_roadmap_completion_next_action_counts tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_contract_compatibility_report_accepts_current_roadmap_completion -q
# 3 passed, 5 warnings
```

This verifies stale roadmap-completion artifacts cannot keep the deduped human-review action text and command hint while editing the checklist row's requirement id, phase, or human-review flag.

Additional roadmap-completion CLI stdout path-masking check:

```bash
.venv/bin/python -m pytest tests/test_path_masking_api.py::test_mask_local_paths_in_text_handles_comma_separated_paths tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_prints_correction_repair_targets tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_cli_prints_handoff_template_paths tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package_cli tests/test_evidence_grounding_benchmark.py::test_audit_evidence_grounding_roadmap_completion_from_package_cli_builds_split_plan_release_package -q
# 5 passed, 5 warnings
```

This verifies roadmap-completion CLI stdout masks local absolute paths in operator handoff output, including comma-separated path samples, while the generated JSON artifact still keeps real lineage paths.

Additional roadmap-completion FastAPI response path-masking check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_api_accepts_standalone_scorecard tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_api_accepts_workspace_inventory_fields tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_from_threshold_adoption_package_api tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_from_comparison_suite_package_api tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_from_package_api_accepts_gold_release_package tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_from_package_api_builds_staged_gold_release_package tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_from_package_api_builds_split_plan_release_package tests/test_evidence_grounding_benchmark.py::test_evidence_grounding_roadmap_completion_api_accepts_gold_release_package -q
# 8 passed, 5 warnings
```

This verifies roadmap-completion FastAPI responses mask local absolute paths while persisted `out` artifacts still preserve real lineage paths.

Full focused-suite check after PR1 scorecard API/compatibility hardening:

```bash
.venv/bin/python -m pytest tests/test_path_masking_api.py -q
# 5 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 70 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 305 passed, 5 warnings
```

Additional reviewer handoff curation check after evidence-editing the Furtado 2018 BBB/nanomaterials patch template:

```bash
jq empty goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_furtadoOvercomingBloodBrain2018.patch_template.json
# passed

jq '.patch_request' goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_furtadoOvercomingBloodBrain2018.patch_template.json > /tmp/pp_furtado_patch_request.json
.venv/bin/python scripts/eval/patch_paper_understanding_gold_candidate_draft.py /tmp/pp_furtado_patch_request.json --out /tmp/pp_furtado_patched_candidate_draft.json --result-out /tmp/pp_furtado_patch_result.json
# after_readiness=pass; curation_ready=True

.venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out-dir /tmp/pp_reviewer_handoff_apply_probe_3 --out /tmp/pp_reviewer_handoff_apply_probe_3/package.json --require-edited
# exits nonzero as expected; unedited_patch_result_count=5

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/pp_continue_after_three_templates.json --print-next-actions --next-action-limit 3
# exits nonzero as expected; pass_count=1; fail_count=12; roadmap_complete=False
# workspace inventory: gold_reviewer_handoff_edited_patch_template_count=3, gold_reviewer_handoff_unedited_patch_template_count=5, gold_reviewer_handoff_unknown_patch_template_edit_state_count=0

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_continue_after_three_templates.json --out /tmp/pp_continue_after_three_templates_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 306 passed, 5 warnings
```

Additional reviewer handoff curation check after evidence-editing the Hansson 2023 blood-biomarker patch template:

```bash
jq empty goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_hanssonBloodBiomarkersAlzheimers2023.patch_template.json
# passed

jq '.patch_request' goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_hanssonBloodBiomarkersAlzheimers2023.patch_template.json > /tmp/pp_hansson_patch_request.json
.venv/bin/python scripts/eval/patch_paper_understanding_gold_candidate_draft.py /tmp/pp_hansson_patch_request.json --out /tmp/pp_hansson_patched_candidate_draft.json --result-out /tmp/pp_hansson_patch_result.json
# after_readiness=pass; curation_ready=True

.venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out-dir /tmp/pp_reviewer_handoff_apply_probe_4 --out /tmp/pp_reviewer_handoff_apply_probe_4/package.json --require-edited
# exits nonzero as expected; unedited_patch_result_count=4

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/pp_continue_after_four_templates.json --print-next-actions --next-action-limit 3
# exits nonzero as expected; pass_count=1; fail_count=12; roadmap_complete=False
# workspace inventory: gold_reviewer_handoff_edited_patch_template_count=4, gold_reviewer_handoff_unedited_patch_template_count=4, gold_reviewer_handoff_unknown_patch_template_edit_state_count=0

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_continue_after_four_templates.json --out /tmp/pp_continue_after_four_templates_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 306 passed, 5 warnings
```

Additional reviewer handoff curation check after evidence-editing the Kistemaker 2025 vascularized human brain organoids patch template:

```bash
jq empty goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_kistemakerVascularizedHumanBrain2025.patch_template.json
# passed

jq '.patch_request' goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_kistemakerVascularizedHumanBrain2025.patch_template.json > /tmp/pp_kistemaker_patch_request.json
.venv/bin/python scripts/eval/patch_paper_understanding_gold_candidate_draft.py /tmp/pp_kistemaker_patch_request.json --out /tmp/pp_kistemaker_patched_candidate_draft.json --result-out /tmp/pp_kistemaker_patch_result.json
# after_readiness=pass; curation_ready=True

.venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out-dir /tmp/pp_reviewer_handoff_apply_probe_5 --out /tmp/pp_reviewer_handoff_apply_probe_5/package.json --require-edited
# exits nonzero as expected; unedited_patch_result_count=3

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/pp_continue_after_five_templates.json --print-next-actions --next-action-limit 3
# exits nonzero as expected; pass_count=1; fail_count=12; roadmap_complete=False
# workspace inventory: gold_reviewer_handoff_edited_patch_template_count=5, gold_reviewer_handoff_unedited_patch_template_count=3, gold_reviewer_handoff_unknown_patch_template_edit_state_count=0

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_continue_after_five_templates.json --out /tmp/pp_continue_after_five_templates_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 306 passed, 5 warnings
```

Additional reviewer handoff curation check after evidence-editing the Pichetbinette 2023 Alzheimer's disease plasma-biomarker patch template:

```bash
jq empty goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_pichetbinetteConfoundingFactorsAlzheimers2023.patch_template.json
# passed

jq '.patch_request' goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_pichetbinetteConfoundingFactorsAlzheimers2023.patch_template.json > /tmp/pp_pichetbinette_patch_request.json
.venv/bin/python scripts/eval/patch_paper_understanding_gold_candidate_draft.py /tmp/pp_pichetbinette_patch_request.json --out /tmp/pp_pichetbinette_patched_candidate_draft.json --result-out /tmp/pp_pichetbinette_patch_result.json
# after_readiness=pass; curation_ready=True

.venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out-dir /tmp/pp_reviewer_handoff_apply_probe_6 --out /tmp/pp_reviewer_handoff_apply_probe_6/package.json --require-edited
# exits nonzero as expected; unedited_patch_result_count=2

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/pp_continue_after_six_templates.json --print-next-actions --next-action-limit 3
# exits nonzero as expected; pass_count=1; fail_count=12; roadmap_complete=False
# workspace inventory: gold_reviewer_handoff_edited_patch_template_count=6, gold_reviewer_handoff_unedited_patch_template_count=2, gold_reviewer_handoff_unknown_patch_template_edit_state_count=0

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_continue_after_six_templates.json --out /tmp/pp_continue_after_six_templates_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 306 passed, 5 warnings
```

Additional reviewer handoff curation check after evidence-editing the Therriault 2022 PET-based Braak staging patch template:

```bash
jq empty goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_therriaultBiomarkerModelingAlzheimers2022.patch_template.json
# passed

jq '.patch_request' goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_therriaultBiomarkerModelingAlzheimers2022.patch_template.json > /tmp/pp_therriault_patch_request.json
.venv/bin/python scripts/eval/patch_paper_understanding_gold_candidate_draft.py /tmp/pp_therriault_patch_request.json --out /tmp/pp_therriault_patched_candidate_draft.json --result-out /tmp/pp_therriault_patch_result.json
# after_readiness=pass; curation_ready=True

.venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out-dir /tmp/pp_reviewer_handoff_apply_probe_7 --out /tmp/pp_reviewer_handoff_apply_probe_7/package.json --require-edited
# exits nonzero as expected; unedited_patch_result_count=1

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --out /tmp/pp_continue_after_seven_templates.json --print-next-actions --next-action-limit 3
# exits nonzero as expected; pass_count=1; fail_count=12; roadmap_complete=False
# workspace inventory: gold_reviewer_handoff_edited_patch_template_count=7, gold_reviewer_handoff_unedited_patch_template_count=1, gold_reviewer_handoff_unknown_patch_template_edit_state_count=0

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_continue_after_seven_templates.json --out /tmp/pp_continue_after_seven_templates_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 306 passed, 5 warnings
```

Additional reviewer handoff curation and release-prep check after evidence-editing the Zhou 2020 Cell CRISPR-CasRx patch template:

```bash
jq empty goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_zhouGliatoNeuronConversionCRISPRCasRx2020.patch_template.json
# passed

jq '.patch_request' goldset/reviews/paper_understanding_gold_reviewer_handoff/patch_templates/zotero_zhouGliatoNeuronConversionCRISPRCasRx2020.patch_template.json > /tmp/pp_zhou_patch_request.json
.venv/bin/python scripts/eval/patch_paper_understanding_gold_candidate_draft.py /tmp/pp_zhou_patch_request.json --out /tmp/pp_zhou_patched_candidate_draft.json --result-out /tmp/pp_zhou_patch_result.json
# after_readiness=pass; curation_ready=True

.venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff/package.json --out-dir goldset/reviews/paper_understanding_gold_reviewer_handoff_apply --out goldset/reviews/paper_understanding_gold_reviewer_handoff_apply/package.json --require-edited
# result_count=8; curation_ready_count=8; ready_to_stage_count=8; remaining_task_count=0; edited_result_count=8; unedited_result_count=0

.venv/bin/python scripts/eval/stage_paper_understanding_gold_reviewer_handoff.py goldset/reviews/paper_understanding_gold_reviewer_handoff_apply/package.json --out-dir goldset/reviews/paper_understanding_gold_reviewer_handoff_stage --out goldset/reviews/paper_understanding_gold_reviewer_handoff_stage/package.json
# staged_count=8; curation_complete=True; remaining_task_count=0

.venv/bin/python scripts/eval/prep_paper_understanding_gold_reviewer_handoff_release.py goldset/reviews/paper_understanding_gold_reviewer_handoff_stage/package.json --out-dir goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep --goldset-id paper_understanding_reviewer_handoff_2026_05_24 --out goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/package.json
# staged_count=8; split_count=3; release_ready_candidate=True; release_ready=True

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --out /tmp/pp_continue_after_release_prep_explicit.json --print-next-actions --next-action-limit 5
# exits nonzero as expected; pass_count=3; fail_count=11; roadmap_complete=False
# passed checks include fixed_goldset_release_readiness, fixed_goldset_release_package_consistency, and additive_noncanonical_artifacts
# next action now starts with fixed-goldset baseline/candidate benchmark execution and complete configuration lineage

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_continue_after_release_prep_explicit.json --out /tmp/pp_continue_after_release_prep_explicit_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 306 passed, 5 warnings
```

Additional fixed-goldset run-readiness clarity check after release-prep:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_fixed_goldset_run_readiness.py --goldset-manifest goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/manifests/eval.json --baseline-run-root storage/artifacts --candidate-run-root storage/artifacts --out /tmp/pp_fixed_gold_eval_run_readiness_after_sidecar_evidence.json
# exits nonzero as expected; goldset_item_count=3; fail_count=6; comparison_run_ready=False

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --goldset-root goldset --run-root storage/artifacts --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --run-readiness-report /tmp/pp_fixed_gold_eval_run_readiness_after_sidecar_evidence.json --out /tmp/pp_continue_after_sidecar_evidence_audit.json --print-next-actions --next-action-limit 3
# exits nonzero as expected; pass_count=3; fail_count=11; roadmap_complete=False
# next_action.1 now explicitly names scorecard-aware baseline/candidate run directories because at least one run-readiness item is missing all core scorecard sidecars: claimset_coverage.json, evidence_extraction_bundle.json, reader_eval.json, visual_evidence_ledger.json

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_continue_after_sidecar_evidence_audit.json --out /tmp/pp_continue_after_sidecar_evidence_audit_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_surfaces_missing_scorecard_inputs tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_stale_run_readiness_summary_counts tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_rejects_stale_comparison_suite_readiness_summary -q
# 3 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 307 passed, 5 warnings
```

Additional temp fixed-goldset execution probe after deriving sidecars from current eval artifacts:

```bash
# On /tmp copies only, derive claimset.resolved.json, reader_eval.json,
# claimset_coverage.json, evidence_extraction_bundle.json, and
# visual_evidence_ledger.json from current document/index/claimset artifacts.
# The temp run root was /tmp/pp_eval_scorecard_runs.zkxPNu.

.venv/bin/python scripts/eval/run_evidence_grounding_fixed_goldset_comparison.py --goldset-manifest goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/manifests/eval.json --baseline-run-root /tmp/pp_eval_scorecard_runs.zkxPNu --candidate-run-root /tmp/pp_eval_scorecard_runs.zkxPNu --out-dir /tmp/pp_fixed_gold_eval_current_vs_current_comparison --gate-preset p0-gold --baseline-parser-version local-deepread-current --baseline-llm-provider local --baseline-llm-model paperpipe-current --baseline-llm-model-version 2026-05-24 --baseline-prompt-version current --baseline-reader-profile-version default --candidate-parser-version local-deepread-current --candidate-llm-provider local --candidate-llm-model paperpipe-current --candidate-llm-model-version 2026-05-24 --candidate-prompt-version current --candidate-reader-profile-version default --require-complete-candidate-config
# exits nonzero as expected; comparison_run_ready=true; run_readiness_fail_count=0
# comparison_failed_checks=benchmark_context.baseline_scorecard_readiness_failures,benchmark_context.candidate_scorecard_readiness_failures
# candidate scorecard readiness: pass=0, warn=2, fail=1

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --comparison-suite /tmp/pp_fixed_gold_eval_current_vs_current_comparison/comparison_suite.json --goldset-root goldset --run-root /tmp/pp_eval_scorecard_runs.zkxPNu --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --out /tmp/pp_after_temp_eval_comparison_roadmap_audit.json --print-next-actions --next-action-limit 5
# exits nonzero as expected; pass_count=7; fail_count=7; roadmap_complete=False
# pass checks now include fixed_goldset_candidate_run, candidate_configuration_lineage, p0_regression_gate, and stage_failure_attribution
# remaining fixed-run blockers: embedded scorecard readiness failures and missing P0 overstatement_rate

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_after_temp_eval_comparison_roadmap_audit.json --out /tmp/pp_after_temp_eval_comparison_roadmap_audit_compat.json
# fail_count=0
```

Additional reproducible scorecard-input backfill lane check:

```bash
.venv/bin/python scripts/eval/backfill_evidence_grounding_scorecard_inputs.py --items-json /tmp/pp_eval_backfill_items.XXXXXX.json --out-run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_eval_backfill_report.XXXXXX.json
# item_count=3; pass_count=3; fail_count=0; scorecard_readiness=pass=0 warn=2 fail=1

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_eval_backfill_report.XXXXXX.json --out /tmp/pp_eval_backfill_report_compat.json
# fail_count=0

.venv/bin/python scripts/eval/run_evidence_grounding_fixed_goldset_comparison.py --goldset-manifest goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/manifests/eval.json --baseline-run-root /tmp/pp_eval_backfill_runs.PQ7KrW --candidate-run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out-dir /tmp/pp_fixed_gold_eval_backfill_cli_comparison --gate-preset p0-gold --baseline-parser-version local-deepread-current --baseline-llm-provider local --baseline-llm-model paperpipe-current --baseline-llm-model-version 2026-05-24 --baseline-prompt-version current --baseline-reader-profile-version default --candidate-parser-version local-deepread-current --candidate-llm-provider local --candidate-llm-model paperpipe-current --candidate-llm-model-version 2026-05-24 --candidate-prompt-version current --candidate-reader-profile-version default --require-complete-candidate-config
# exits nonzero as expected; run-readiness succeeds, then comparison fails on embedded scorecard readiness failures

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --out /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit.json --print-next-actions --next-action-limit 5
# exits nonzero as expected; pass_count=7; fail_count=7; roadmap_complete=False

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit.json --out /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 73 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 307 passed, 5 warnings
```

Additional overstatement-rate next-action clarity check:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --out /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_overstatement_action.json --print-next-actions --next-action-limit 7
# exits nonzero as expected; pass_count=7; fail_count=7; roadmap_complete=False
# p0_metrics_reported next action now explicitly requires OVERSTATED_RESULT review labels or structured human review evidence before overstatement_rate can become available

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_overstatement_action.json --out /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_overstatement_action_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py::test_build_evidence_grounding_roadmap_completion_audit_names_overstatement_label_gap -q
# 1 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 308 passed, 5 warnings
```

Additional embedded scorecard-readiness next-action clarity check:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --out /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_scorecard_reason_actions.json --print-next-actions --next-action-limit 5
# exits nonzero as expected; pass_count=7; fail_count=7; roadmap_complete=False
# per_run_and_aggregate_scorecards next action now summarizes blocking embedded scorecard reason codes and first not-ready baseline/candidate IDs

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_scorecard_reason_actions.json --out /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_scorecard_reason_actions_compat.json
# fail_count=0
```

Additional workspace-inventory release-boundary check:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --out /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_release_inventory_boundary.json --print-next-actions --next-action-limit 8
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# workspace_evidence_inventory_ready now passes from the ready/consistent release package and matched run evidence, while legacy/non-gold review JSON remains visible as non-blocking inventory evidence

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_release_inventory_boundary.json --out /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_release_inventory_boundary_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 309 passed, 5 warnings
```

Additional reviewed-fixture consistency-label supplement check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py::test_build_evidence_grounding_scorecard_uses_reviewed_eval_consistency_labels_with_gold tests/test_evidence_grounding_scorecard.py::test_scorecard_from_run_dir_uses_reviewed_eval_fixture_sidecar_with_gold -q
# 2 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 75 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --out /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_reviewed_fixture_p0_path.json --print-next-actions --next-action-limit 8
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# p0_metrics_reported next action now names paper_understanding_gold.v1 OVERSTATED_RESULT labels or claim_evidence_reviewed_eval_fixtures.json as the supported enrichment paths for overstatement_rate

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_reviewed_fixture_p0_path.json --out /tmp/pp_after_cli_backfill_eval_comparison_roadmap_audit_reviewed_fixture_p0_path_compat.json
# fail_count=0
```

Additional reviewed-fixture structured-correction evidence check:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "reviewed_fixture_bundle or eval_candidate_export_as_correction_evidence"
# 2 passed, 309 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py -q
# 25 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 311 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_after_reviewed_fixture_bundle_correction_evidence_roadmap_audit.json --print-next-actions
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# claim_evidence_reviewed_eval_fixtures_bundle.v1 is now accepted as structured correction evidence when supplied, but the live run root still lacks an attached reviewed fixture sidecar

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q -k "scorecard_input_backfill"
# 6 passed, 72 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 78 passed, 5 warnings

.venv/bin/python scripts/eval/backfill_evidence_grounding_scorecard_inputs.py --item '{"paper_id":"zotero:duboisAlzheimerDiseaseClinicalBiological2024","source_run_dir":"/tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024","run_id":"zotero:duboisAlzheimerDiseaseClinicalBiological2024"}' --out-run-root /tmp/<temp_probe> --reviewed-fixtures-dir /tmp/<empty_reviewed_fixtures> --out /tmp/<temp_probe>/backfill_report.json
# exits zero; pass_count=1; fail_count=0; reviewed_eval_fixture_count=0; no reviewed-fixture sidecar generated when no approved fixtures match

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "existing_workspace_correction_log or storage_correction_log_from_goldset_root"
# 2 passed, 310 deselected, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_after_goldset_storage_correction_autodiscovery_roadmap_audit.json --print-next-actions
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# structured_correction_log now auto-selects storage/claim_evidence_corrections.jsonl via goldset_root workspace discovery and reports the invalid accepted rows plus missing replay lineage fields

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 312 passed, 5 warnings
```

Additional correction repair-plan handoff check:

```bash
.venv/bin/python scripts/eval/export_claim_evidence_correction_repair_plan.py --log-path /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --out /tmp/pp_claim_evidence_correction_repair_plan.json
# exits zero; source_record_count=3; source_invalid_record_count=2; repair_target_count=2
# targets preserve line numbers, correction IDs, paper/run/claim IDs, and missing replay-lineage fields without editing the raw correction log

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_claim_evidence_correction_repair_plan.json --out /tmp/pp_claim_evidence_correction_repair_plan_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py -q
# 27 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 314 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "existing_workspace_correction_log or storage_correction_log_from_goldset_root or nonreplayable_correction_log or invalid_source_correction_export or routes_structured_correction_export_as_prep or repair_plan"
# 6 passed, 308 deselected, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --correction-log /tmp/pp_claim_evidence_correction_repair_plan_current.json --out /tmp/pp_roadmap_audit_with_repair_plan_handoff.json --print-next-actions --next-action-limit 6
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# structured_correction_log recognizes claim_evidence_correction_repair_plan.v1 as a non-canonical repair handoff, not replayable correction evidence

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_with_repair_plan_handoff.json --out /tmp/pp_roadmap_audit_with_repair_plan_handoff_compat.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 315 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_p0_reviewed_fixture_hint.json --print-next-actions --next-action-limit 4
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# p0_metrics_reported now points to backfill_evidence_grounding_scorecard_inputs.py --reviewed-fixtures-dir before rerunning fixed-goldset comparison

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_p0_reviewed_fixture_hint.json --out /tmp/pp_roadmap_audit_p0_reviewed_fixture_hint_compat.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_contract_repair_plan_hint.json --print-next-actions --next-action-limit 11
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external-contract readiness hints include claim_evidence_correction_repair_plan.json as a non-canonical correction-loop handoff artifact for compatibility/readiness review

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_contract_repair_plan_hint.json --out /tmp/pp_roadmap_audit_contract_repair_plan_hint_compat.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_contract_backfill_hint.json --print-next-actions --next-action-limit 11
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external-contract readiness hints include scorecard_input_backfill.json as a non-canonical review artifact for compatibility/readiness review

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_contract_backfill_hint.json --out /tmp/pp_roadmap_audit_contract_backfill_hint_compat.json
# fail_count=0

.venv/bin/python scripts/eval/calibrate_evidence_grounding_thresholds_from_comparison_suite.py --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --out /tmp/pp_threshold_calibration_probe.json --metric-preset p0-gold
# exits zero; report_count=1; available P0 metrics cover claim_precision, evidence_support_precision, limitation_recall, locator_precision, method_result_confusion_rate, and unsupported_claim_rate; overstatement_rate is not available

.venv/bin/python scripts/eval/review_evidence_grounding_threshold_adoption_from_comparison_suite.py --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --calibration-out /tmp/pp_threshold_review_probe_calibration.json --threshold-checked-comparison-out /tmp/pp_threshold_checked_comparison_probe.json --out /tmp/pp_threshold_adoption_probe.json --calibration-metric-preset p0-gold --gate-preset p0-gold --reviewer-approval-reference probe-only-threshold-review --allow-production-threshold-ready
# exits nonzero as expected; fail_count=2; production_threshold_ready=False
# blockers are missing overstatement_rate for P0 threshold recommendations and embedded scorecard readiness failures in the comparison context

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_threshold_probe_after_patch.json --print-next-actions --next-action-limit 12
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# production_threshold_adoption_reviewed next actions now route through resolving missing overstatement_rate with reviewed fixture backfill before recalibration and adoption review

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_threshold_calibration_probe.json --artifact /tmp/pp_threshold_adoption_probe.json --artifact /tmp/pp_roadmap_audit_threshold_probe_after_patch.json --out /tmp/pp_contract_threshold_probe_after_patch.json
# fail_count=0

.venv/bin/python scripts/eval/build_evidence_grounding_benchmark_manifests_from_release_package.py --release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out-dir /tmp/pp_manifest_package_probe_allow_missing --out /tmp/pp_manifest_package_probe_allow_missing/package.json --candidate-prefix candidate --parser-version parser-probe --llm-provider local --llm-model probe --llm-model-version probe --prompt-version probe --reader-profile-version probe --require-complete-candidate-config --allow-missing-runs
# exits zero as a diagnostic package; without --allow-missing-runs this fails because the current run root only contains eval split run directories

.venv/bin/python scripts/eval/run_evidence_grounding_benchmark_package.py --manifest-package /tmp/pp_manifest_package_probe_allow_missing/package.json --out-dir /tmp/pp_benchmark_run_package_probe_allow_missing --out /tmp/pp_benchmark_run_package_probe_allow_missing/package.json
# exits zero; report_count=3; scorecard_count=3; scorecard_readiness=pass=0 warn=2 fail=1

.venv/bin/python scripts/eval/run_evidence_grounding_fixed_goldset_comparison_from_benchmark_run_packages.py --baseline-run-package /tmp/pp_benchmark_run_package_probe_allow_missing/package.json --candidate-run-package /tmp/pp_benchmark_run_package_probe_allow_missing/package.json --out-dir /tmp/pp_comparison_suite_package_probe_allow_missing --out /tmp/pp_comparison_suite_package_probe_allow_missing/package.json --gate-preset p0-gold --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json
# exits zero; suite_count=3; comparison_pass_count=0; comparison_fail_count=3; seed/eval/holdout package exists only as blocked diagnostic evidence

.venv/bin/python scripts/eval/review_evidence_grounding_threshold_adoption_from_comparison_suite_package.py --comparison-suite-package /tmp/pp_comparison_suite_package_probe_allow_missing/package.json --out-dir /tmp/pp_threshold_adoption_package_probe_allow_missing --reviewer-approval-reference probe-only-threshold-package-review --allow-production-threshold-ready --out /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json
# exits zero; comparison_suite_count=3; production_threshold_ready_count=0; production_threshold_blocked_count=3; scorecard_readiness=pass=0 warn=2 fail=1

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_threshold_package_probe_after_patch.json --print-next-actions --next-action-limit 20
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# fixed_goldset_threshold_adoption_package_ready actions now resolve blocked package splits and scorecard readiness instead of rebuilding an already supplied package

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_manifest_package_probe_allow_missing/package.json --artifact /tmp/pp_benchmark_run_package_probe_allow_missing/package.json --artifact /tmp/pp_comparison_suite_package_probe_allow_missing/package.json --artifact /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --artifact /tmp/pp_roadmap_audit_threshold_package_probe_after_patch.json --out /tmp/pp_contract_threshold_package_probe_after_patch.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_scorecard_proxy_metrics_after_patch.json --print-next-actions --next-action-limit 4
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# per_run_and_aggregate_scorecards now reports first not-ready scorecard proxy metrics such as grounded_evidence_ratio, page_coverage_ratio, missing_topic_signal_count, duplicate_cluster_count, low_overlap_claim_rate, and grounded_extraction_ref_rate

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_scorecard_proxy_metrics_after_patch.json --out /tmp/pp_contract_scorecard_proxy_metrics_after_patch.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_contract_package_hints_after_patch.json --print-next-actions --next-action-limit 12
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external-contract compatibility hints now include benchmark manifest/run packages, fixed-goldset comparison-suite package, and threshold-adoption package artifacts

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_contract_package_hints_after_patch.json --out /tmp/pp_contract_package_hints_after_patch.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_threshold_package_missing_runs_after_patch.json --print-next-actions --next-action-limit 12
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# fixed_goldset_threshold_adoption_package_ready now distinguishes run evidence gaps from scorecard readiness by reporting package_run_readiness_fail_count plus baseline/candidate missing gold/run paper IDs
# when those run evidence gaps are present, the next command hint starts at build_evidence_grounding_benchmark_manifests_from_release_package.py with a complete run root

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_missing_runs_after_patch.json --out /tmp/pp_contract_threshold_package_missing_runs_after_patch.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_threshold_package_split_missing_runs_after_patch.json --print-next-actions --next-action-limit 10
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# fixed_goldset_threshold_adoption_package_ready now reports missing run evidence by split, e.g. holdout:<paper_ids>|seed:<paper_ids>, for both baseline and candidate packages

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_split_missing_runs_after_patch.json --out /tmp/pp_contract_threshold_package_split_missing_runs_after_patch.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_contract_missing_schema_actions_after_patch.json --print-next-actions --next-action-limit 12
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external_contract_readiness_reviewed next actions now name the missing contract schema versions and the compatibility command hint includes evidence_grounding_fixed_goldset_comparison_suite.json

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_contract_missing_schema_actions_after_patch.json --out /tmp/pp_contract_missing_schema_actions_after_patch.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_contract_release_package_hint_after_patch.json --print-next-actions --next-action-limit 12
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external_contract_readiness_reviewed compatibility command hint now includes paper_understanding_gold_release_package.json as well as paper_understanding_gold_release_readiness.json

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_contract_release_package_hint_after_patch.json --out /tmp/pp_contract_release_package_hint_after_patch.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_contract_readiness_gold_artifacts_hint_after_patch.json --print-next-actions --next-action-limit 12
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external_contract_readiness_reviewed readiness command hint now passes paper_understanding_gold_release_package.json and paper_understanding_gold_release_readiness.json as additional artifacts

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_contract_readiness_gold_artifacts_hint_after_patch.json --out /tmp/pp_contract_readiness_gold_artifacts_hint_after_patch.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "contract_readiness_requests_describe_additional_correction_artifacts or contract_readiness_cli_help_describes_additional_correction_artifacts"
# 2 passed, 313 deselected, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_contract_readiness_from_threshold_adoption_package.py --help | rg "paper_understanding_gold_release|claim_evidence_reviewed|additional-artifact"
# help lists paper_understanding_gold_release_package.json and paper_understanding_gold_release_readiness.json as additional-artifact examples

.venv/bin/python scripts/eval/audit_evidence_grounding_contract_readiness_from_comparison_suite.py --help | rg "paper_understanding_gold_release|claim_evidence_reviewed|additional-artifact"
# help lists paper_understanding_gold_release_package.json and paper_understanding_gold_release_readiness.json as additional-artifact examples

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_scorecard_not_ready_ids_after_patch.json --print-next-actions --next-action-limit 4
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# per_run_and_aggregate_scorecards next action now lists all not-ready baseline/candidate IDs present in the audit evidence

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_scorecard_not_ready_ids_after_patch.json --out /tmp/pp_contract_scorecard_not_ready_ids_after_patch.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_structured_correction_all_targets_after_patch.json --print-next-actions --next-action-limit 6
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# structured_correction_log next action now lists all invalid accepted correction targets and all missing replay-lineage field groups from audit evidence

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_structured_correction_all_targets_after_patch.json --out /tmp/pp_contract_structured_correction_all_targets_after_patch.json
# fail_count=0

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_structured_correction_total_invalid_after_patch.json --print-next-actions --next-action-limit 6
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# structured_correction_log next action now distinguishes the two invalid accepted eval correction targets from the total non-replayable raw-log footprint of three records

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_structured_correction_total_invalid_after_patch.json --out /tmp/pp_contract_structured_correction_total_invalid_after_patch.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 315 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_contract_readiness_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --compatibility-out /tmp/pp_contract_from_threshold_package_with_gold_and_repair.json --out /tmp/pp_contract_readiness_from_threshold_package_with_gold_and_repair.json --additional-artifact goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --additional-artifact goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan.json
# exits nonzero as expected; compatibility artifact_count=29 with fail_count=2 due stale seed/holdout benchmark input-artifact coverage fields; readiness fail_count=6 and external_contract_ready=False

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-readiness-report /tmp/pp_contract_readiness_from_threshold_package_with_gold_and_repair.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_contract_readiness_blockers_after_patch.json --print-next-actions --next-action-limit 12
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external_contract_readiness_reviewed next actions now name readiness blockers plus compatibility/readiness fail counts

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_contract_readiness_blockers_after_patch.json --out /tmp/pp_contract_roadmap_contract_readiness_blockers_after_patch.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 316 passed, 5 warnings

.venv/bin/python scripts/eval/run_evidence_grounding_benchmark_package.py --manifest-package /tmp/pp_manifest_package_probe_allow_missing/package.json --out-dir /tmp/pp_benchmark_run_package_probe_allow_missing --out /tmp/pp_benchmark_run_package_probe_allow_missing/package.json
# exits zero; regenerated empty seed/holdout split benchmark reports now carry explicit not_available aggregate input-health metrics instead of omitting those metric keys

.venv/bin/python scripts/eval/run_evidence_grounding_fixed_goldset_comparison_from_benchmark_run_packages.py --baseline-run-package /tmp/pp_benchmark_run_package_probe_allow_missing/package.json --candidate-run-package /tmp/pp_benchmark_run_package_probe_allow_missing/package.json --out-dir /tmp/pp_comparison_suite_package_probe_allow_missing --out /tmp/pp_comparison_suite_package_probe_allow_missing/package.json --gate-preset p0-gold --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json
# exits zero; suite_count=3; comparison_pass_count=0; comparison_fail_count=3; scorecard readiness remains pass=0 warn=2 fail=1

.venv/bin/python scripts/eval/review_evidence_grounding_threshold_adoption_from_comparison_suite_package.py --comparison-suite-package /tmp/pp_comparison_suite_package_probe_allow_missing/package.json --out-dir /tmp/pp_threshold_adoption_package_probe_allow_missing --reviewer-approval-reference probe-only-threshold-package-review --allow-production-threshold-ready --out /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json
# exits zero; production_threshold_ready_count=0; production_threshold_blocked_count=3

.venv/bin/python scripts/eval/audit_evidence_grounding_contract_readiness_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --compatibility-out /tmp/pp_contract_from_threshold_package_empty_metrics_after_patch.json --out /tmp/pp_contract_readiness_empty_metrics_after_patch.json --additional-artifact goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --additional-artifact goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan.json
# exits nonzero as expected; compatibility artifact_count=29 with fail_count=0; readiness fail_count=5 and external_contract_ready=False

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-readiness-report /tmp/pp_contract_readiness_empty_metrics_after_patch.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_empty_benchmark_metrics_after_patch.json --print-next-actions --next-action-limit 12
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external_contract_readiness_reviewed now reports readiness fail_count=5 without a compatibility fail-count blocker

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_empty_benchmark_metrics_after_patch.json --out /tmp/pp_contract_empty_benchmark_metrics_after_patch.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 317 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_contract_readiness_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --compatibility-out /tmp/pp_contract_with_current_audited_paths_after_patch_probe.json --out /tmp/pp_contract_readiness_with_current_audited_paths_probe.json --additional-artifact /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --additional-artifact /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --additional-artifact /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --additional-artifact /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --additional-artifact /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --additional-artifact /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --additional-artifact /tmp/pp_threshold_calibration_probe.json --additional-artifact /tmp/pp_threshold_adoption_probe.json --additional-artifact goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --additional-artifact goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan.json
# exits nonzero as expected; artifact_count=37; readiness fail_count=5 and external_contract_ready=False

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-readiness-report /tmp/pp_contract_readiness_with_current_audited_paths_probe.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_contract_readiness_additional_artifacts_after_patch.json --print-next-actions --next-action-limit 12
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# contract-readiness command hint now carries standalone audited scorecard/benchmark/comparison/readiness/threshold artifacts as additional-artifact inputs

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_contract_readiness_additional_artifacts_after_patch.json --out /tmp/pp_contract_readiness_additional_artifacts_after_patch.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 317 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-readiness-report /tmp/pp_contract_readiness_with_current_audited_paths_probe.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_all_not_ready_proxy_metrics_after_patch.json --print-next-actions --next-action-limit 4
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# per_run_and_aggregate_scorecards next action now lists all embedded not-ready scorecard proxy metrics instead of only the first sample

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_all_not_ready_proxy_metrics_after_patch.json --out /tmp/pp_contract_all_not_ready_proxy_metrics_after_patch.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 317 passed, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion.py --scorecard /tmp/pp_eval_backfill_runs.PQ7KrW/zotero:duboisAlzheimerDiseaseClinicalBiological2024/evidence_grounding_scorecard.json --comparison-suite /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_suite.json --baseline-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/baseline_benchmark_report.json --candidate-benchmark-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/candidate_benchmark_report.json --comparison-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/comparison_report.json --run-readiness-report /tmp/pp_fixed_gold_eval_backfill_cli_comparison/run_readiness_report.json --threshold-calibration-report /tmp/pp_threshold_calibration_probe.json --threshold-adoption-review /tmp/pp_threshold_adoption_probe.json --threshold-adoption-package /tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-readiness-report /tmp/pp_contract_readiness_with_current_audited_paths_probe.json --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --out /tmp/pp_roadmap_audit_threshold_package_scorecard_ids_after_patch.json --print-next-actions --next-action-limit 10
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# fixed_goldset_threshold_adoption_package_ready now names embedded baseline/candidate not-ready scorecard IDs alongside split/run-readiness blockers

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_scorecard_ids_after_patch.json --out /tmp/pp_contract_threshold_package_scorecard_ids_after_patch.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 317 passed, 5 warnings
```

## 2026-05-25 Threshold Package Proxy Metrics Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /private/tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-compatibility-out /tmp/pp_contract_threshold_package_proxy_metrics_after_patch.json --contract-readiness-out /tmp/pp_contract_readiness_threshold_package_proxy_metrics_after_patch.json --out /tmp/pp_roadmap_audit_threshold_package_proxy_metrics_after_patch.json --representative-split eval --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log storage/claim_evidence_corrections.jsonl --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# fixed_goldset_threshold_adoption_package_ready now carries baseline/candidate scorecard_not_ready_proxy_metrics from the linked benchmark run packages

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "threshold_adoption_package_ready or failed_scorecard_context or package_scorecard"
# 3 passed, 314 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_proxy_metrics_after_patch.json --out /tmp/pp_contract_threshold_package_proxy_metrics_after_patch_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 317 passed, 5 warnings
```

## 2026-05-25 Threshold Package Regeneration Handoff Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /private/tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-compatibility-out /tmp/pp_contract_threshold_package_regenerate_suite_action_after_patch.json --contract-readiness-out /tmp/pp_contract_readiness_threshold_package_regenerate_suite_action_after_patch.json --out /tmp/pp_roadmap_audit_threshold_package_regenerate_suite_action_after_patch.json --representative-split eval --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log storage/claim_evidence_corrections.jsonl --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# fixed_goldset_threshold_adoption_package_ready now includes a non-human-review comparison-suite package regeneration action before the threshold-adoption review rerun

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "threshold_adoption_package or failed_scorecard_context or package_scorecard"
# 12 passed, 305 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_regenerate_suite_action_after_patch.json --out /tmp/pp_contract_threshold_package_regenerate_suite_action_after_patch_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 317 passed, 5 warnings
```

## 2026-05-25 Raw Correction Repair Contract Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /private/tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-compatibility-out /tmp/pp_contract_threshold_package_raw_repair_schema_after_patch.json --contract-readiness-out /tmp/pp_contract_readiness_threshold_package_raw_repair_schema_after_patch.json --out /tmp/pp_roadmap_audit_threshold_package_raw_repair_schema_after_patch.json --representative-split eval --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log storage/claim_evidence_corrections.jsonl --goldset-root goldset --run-root /tmp/pp_eval_backfill_runs.PQ7KrW --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external_contract_readiness_reviewed now reports missing_contract_schema_versions=claim_evidence_correction_repair_plan.v1 for the raw invalid correction log

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "nonreplayable_correction_log or correction_export_contract_schema_coverage or contract_schema_coverage"
# 4 passed, 313 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_raw_repair_schema_after_patch.json --out /tmp/pp_contract_threshold_package_raw_repair_schema_after_patch_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 317 passed, 5 warnings
```

## 2026-05-25 Threshold Package Additional Contract Artifact Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /private/tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-compatibility-out /tmp/pp_contract_threshold_package_with_repair_plan_after_cli_patch.json --contract-readiness-out /tmp/pp_contract_readiness_threshold_package_with_repair_plan_after_cli_patch.json --out /tmp/pp_roadmap_audit_threshold_package_with_repair_plan_after_cli_patch.json --representative-split eval --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /private/tmp/pp_eval_backfill_runs.PQ7KrW --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external_contract_readiness_reviewed now reports missing_contract_schema_versions=- when the correction repair plan is explicitly supplied as an additional contract artifact
# structured_correction_log remains blocked on raw correction-log repair; the audit does not mutate or accept the raw JSONL by proxy

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_with_repair_plan_after_cli_patch.json --out /tmp/pp_contract_threshold_package_with_repair_plan_after_cli_patch_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "threshold_package_accepts_additional_contract_artifacts or roadmap_completion_from_threshold_adoption_package_cli or roadmap_completion_from_threshold_adoption_package_api or threshold_package_request_describes_additional_artifacts or roadmap_completion_cli_help_describes_correction_export_input"
# 5 passed, 314 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 319 passed, 5 warnings
```

## 2026-05-25 External Contract Review Docs Follow-Up

Added draft, non-canonical review/export artifacts:

- `docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md`
- `docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md`
- `docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md`

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /private/tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-compatibility-out /tmp/pp_contract_threshold_package_with_review_docs_after_patch.json --contract-readiness-out /tmp/pp_contract_readiness_threshold_package_with_review_docs_after_patch.json --out /tmp/pp_roadmap_audit_threshold_package_with_review_docs_after_patch.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /private/tmp/pp_eval_backfill_runs.PQ7KrW --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external_contract_readiness_reviewed now reports blockers=reviewer_approval_reference_present,explicit_external_contract_opt_in and contract_readiness_fail_count=2
# migration_plan_present, backfill_plan_present, and public_contract_doc_present are pass in the generated readiness report

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_with_review_docs_after_patch.json --out /tmp/pp_contract_threshold_package_with_review_docs_after_patch_verify.json
# fail_count=0
```

## 2026-05-25 External Contract Readiness Action Text Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /private/tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-compatibility-out /tmp/pp_contract_threshold_package_with_review_docs_action_text_after_patch.json --contract-readiness-out /tmp/pp_contract_readiness_threshold_package_with_review_docs_action_text_after_patch.json --out /tmp/pp_roadmap_audit_threshold_package_with_review_docs_action_text_after_patch.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /private/tmp/pp_eval_backfill_runs.PQ7KrW --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# contract-readiness human action now starts: Complete human approval reference and explicit opt-in before external contract readiness is marked ready

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "contract_readiness_blockers or remaining_contract_readiness_blockers or requires_contract_schema_coverage"
# 3 passed, 317 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_with_review_docs_action_text_after_patch.json --out /tmp/pp_contract_threshold_package_with_review_docs_action_text_after_patch_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 Structured Correction Source Counts Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /private/tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-compatibility-out /tmp/pp_contract_threshold_package_correction_counts_after_patch.json --contract-readiness-out /tmp/pp_contract_readiness_threshold_package_correction_counts_after_patch.json --out /tmp/pp_roadmap_audit_threshold_package_correction_counts_after_patch.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /private/tmp/pp_eval_backfill_runs.PQ7KrW --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# structured-correction action now reports source records: 3; source valid records: 1; 2 invalid accepted records; total non-replayable records: 3

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "structured_correction or nonreplayable_correction_log or repair_plan_as_noncanonical_handoff or existing_workspace_correction_log"
# 4 passed, 316 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_correction_counts_after_patch.json --out /tmp/pp_contract_threshold_package_correction_counts_after_patch_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 Structured Correction CLI Count Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /private/tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-compatibility-out /tmp/pp_contract_threshold_package_correction_stdout_counts_after_patch.json --contract-readiness-out /tmp/pp_contract_readiness_threshold_package_correction_stdout_counts_after_patch.json --out /tmp/pp_roadmap_audit_threshold_package_correction_stdout_counts_after_patch.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /private/tmp/pp_eval_backfill_runs.PQ7KrW --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# stdout includes structured_correction_source_record_count=3, structured_correction_source_valid_record_count=1, structured_correction_source_invalid_record_count=2, and structured_correction_repair_target_count=0
# exits nonzero without tee; roadmap remains intentionally incomplete with pass_count=8, fail_count=6, roadmap_complete=False

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "roadmap_completion_cli_prints_correction_repair_targets or roadmap_completion_from_threshold_adoption_package_cli"
# 2 passed, 318 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_correction_stdout_counts_after_patch.json --out /tmp/pp_contract_threshold_package_correction_stdout_counts_after_patch_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 Structured Correction Repair Target Count Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /private/tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-compatibility-out /tmp/pp_contract_threshold_package_repair_target_count_after_patch.json --contract-readiness-out /tmp/pp_contract_readiness_threshold_package_repair_target_count_after_patch.json --out /tmp/pp_roadmap_audit_threshold_package_repair_target_count_after_patch.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /private/tmp/pp_eval_backfill_runs.PQ7KrW --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# stdout now includes structured_correction_repair_target_count=2 for the raw correction JSONL diagnostics
# exits nonzero without tee; roadmap remains intentionally incomplete with pass_count=8, fail_count=6, roadmap_complete=False

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "structured_correction or nonreplayable_correction_log or repair_plan_as_noncanonical_handoff or existing_workspace_correction_log or roadmap_completion_cli_prints_correction_repair_targets or roadmap_completion_from_threshold_adoption_package_cli"
# 6 passed, 314 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_repair_target_count_after_patch.json --out /tmp/pp_contract_threshold_package_repair_target_count_after_patch_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 Threshold Package CLI Blocker Diagnostics Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /private/tmp/pp_threshold_adoption_package_probe_allow_missing/package.json --contract-compatibility-out /tmp/pp_contract_threshold_package_stdout_package_gaps_after_patch.json --contract-readiness-out /tmp/pp_contract_readiness_threshold_package_stdout_package_gaps_after_patch.json --out /tmp/pp_roadmap_audit_threshold_package_stdout_package_gaps_after_patch.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /private/tmp/pp_eval_backfill_runs.PQ7KrW --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# stdout now includes threshold_package_not_ready_splits=eval,holdout,seed; threshold_package_run_readiness_fail_count=10; baseline/candidate missing papers by split; and baseline/candidate not-ready scorecard IDs
# exits nonzero without tee; roadmap remains intentionally incomplete with pass_count=8, fail_count=6, roadmap_complete=False

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "roadmap_completion_from_threshold_adoption_package_cli or threshold_adoption_package_ready or failed_scorecard_context"
# 2 passed, 318 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_threshold_package_stdout_package_gaps_after_patch.json --out /tmp/pp_contract_threshold_package_stdout_package_gaps_after_patch_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 Complete Release Backfill Probe

```bash
.venv/bin/python scripts/eval/backfill_evidence_grounding_scorecard_inputs.py --items-json /tmp/pp_scorecard_backfill_items_complete_release_alt_20260525.json --out-run-root /tmp/pp_complete_release_backfill_runs_alt_20260525 --out /tmp/pp_complete_release_backfill_report_alt_20260525.json --overwrite
# item_count=8; pass_count=8; fail_count=0; scorecard_readiness=pass=0 warn=6 fail=2

.venv/bin/python scripts/eval/build_evidence_grounding_benchmark_manifests_from_release_package.py --release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --run-root /tmp/pp_complete_release_backfill_runs_alt_20260525 --out-dir /tmp/pp_complete_release_baseline_manifests_20260525 --out /tmp/pp_complete_release_baseline_manifest_package_20260525.json --candidate-prefix baseline --parser-version existing-artifact-backfill --llm-provider local --llm-model existing-artifact --llm-model-version 2026-05-25 --prompt-version existing-artifact-backfill --reader-profile-version existing-artifact-backfill --require-complete-candidate-config
# manifest_count=3; item_count=8

.venv/bin/python scripts/eval/build_evidence_grounding_benchmark_manifests_from_release_package.py --release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --run-root /tmp/pp_complete_release_backfill_runs_alt_20260525 --out-dir /tmp/pp_complete_release_candidate_manifests_20260525 --out /tmp/pp_complete_release_candidate_manifest_package_20260525.json --candidate-prefix candidate --parser-version existing-artifact-backfill --llm-provider local --llm-model existing-artifact --llm-model-version 2026-05-25 --prompt-version existing-artifact-backfill --reader-profile-version existing-artifact-backfill --require-complete-candidate-config
# manifest_count=3; item_count=8

.venv/bin/python scripts/eval/run_evidence_grounding_benchmark_package.py --manifest-package /tmp/pp_complete_release_baseline_manifest_package_20260525.json --out-dir /tmp/pp_complete_release_baseline_benchmark_reports_20260525 --out /tmp/pp_complete_release_baseline_benchmark_run_package_20260525.json
# report_count=3; scorecard_count=8; scorecard_readiness=pass=0 warn=6 fail=2

.venv/bin/python scripts/eval/run_evidence_grounding_benchmark_package.py --manifest-package /tmp/pp_complete_release_candidate_manifest_package_20260525.json --out-dir /tmp/pp_complete_release_candidate_benchmark_reports_20260525 --out /tmp/pp_complete_release_candidate_benchmark_run_package_20260525.json
# report_count=3; scorecard_count=8; scorecard_readiness=pass=0 warn=6 fail=2

.venv/bin/python scripts/eval/run_evidence_grounding_fixed_goldset_comparison_from_benchmark_run_packages.py --baseline-run-package /tmp/pp_complete_release_baseline_benchmark_run_package_20260525.json --candidate-run-package /tmp/pp_complete_release_candidate_benchmark_run_package_20260525.json --out-dir /tmp/pp_complete_release_comparison_suite_20260525 --gate-preset p0-gold --out /tmp/pp_complete_release_comparison_suite_package_20260525.json
# suite_count=3; comparison_pass_count=1; comparison_fail_count=2; run_readiness_fail_count=0

.venv/bin/python scripts/eval/review_evidence_grounding_threshold_adoption_from_comparison_suite_package.py --comparison-suite-package /tmp/pp_complete_release_comparison_suite_package_20260525.json --out-dir /tmp/pp_complete_release_threshold_adoption_20260525 --out /tmp/pp_complete_release_threshold_adoption_package_20260525.json
# comparison_suite_count=3; production_threshold_ready_count=0; production_threshold_blocked_count=3

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_threshold_package_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_threshold_package_20260525.json --out /tmp/pp_roadmap_audit_complete_release_threshold_package_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /tmp/pp_complete_release_backfill_runs_alt_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# threshold-package run coverage is now clean in this regenerated package: package_run_readiness_fail_count=0; baseline/candidate missing paper ids=-

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_threshold_package_20260525.json --out /tmp/pp_contract_complete_release_threshold_package_20260525_verify.json
# fail_count=0
```

## 2026-05-25 Best Existing Source Backfill Probe

```bash
.venv/bin/python scripts/eval/backfill_evidence_grounding_scorecard_inputs.py --items-json /tmp/pp_scorecard_source_screen_items_zhou_pichet_20260525.json --out-run-root /tmp/pp_scorecard_source_screen_runs_zhou_pichet_20260525 --out /tmp/pp_scorecard_source_screen_report_zhou_pichet_20260525.json --overwrite
# item_count=4; pass_count=4; fail_count=0; scorecard_readiness=pass=0 warn=1 fail=3
# Pichetbinette's non-Zotero-keyed source run improves to warn; both available Zhou source runs remain fail on low grounded-evidence coverage.

.venv/bin/python scripts/eval/backfill_evidence_grounding_scorecard_inputs.py --items-json /tmp/pp_scorecard_backfill_items_complete_release_best_20260525.json --out-run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --out /tmp/pp_complete_release_backfill_report_best_20260525.json --overwrite
# item_count=8; pass_count=8; fail_count=0; scorecard_readiness=pass=0 warn=7 fail=1

.venv/bin/python scripts/eval/run_evidence_grounding_fixed_goldset_comparison_from_benchmark_run_packages.py --baseline-run-package /tmp/pp_complete_release_best_baseline_benchmark_run_package_20260525.json --candidate-run-package /tmp/pp_complete_release_best_candidate_benchmark_run_package_20260525.json --out-dir /tmp/pp_complete_release_best_comparison_suite_20260525 --gate-preset p0-gold --out /tmp/pp_complete_release_best_comparison_suite_package_20260525.json
# suite_count=3; comparison_pass_count=2; comparison_fail_count=1; baseline/candidate scorecard_readiness=pass=0 warn=7 fail=1

.venv/bin/python scripts/eval/review_evidence_grounding_threshold_adoption_from_comparison_suite_package.py --comparison-suite-package /tmp/pp_complete_release_best_comparison_suite_package_20260525.json --out-dir /tmp/pp_complete_release_best_threshold_adoption_20260525 --out /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json
# comparison_suite_count=3; production_threshold_ready_count=0; production_threshold_blocked_count=3

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_action_text_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_action_text_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_action_text_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# threshold_package_run_readiness_fail_count=0 and threshold-package scorecard readiness now reports failures=1 with non_pass_ids for the warn+fail context.

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "threshold_adoption_package_ready or failed_scorecard_context"
# 1 passed, 319 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_action_text_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_action_text_20260525_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 Scorecard Fail ID Diagnostics Follow-Up

```bash
# Broader Zhou source inventory found only two scorecard-backfillable deepread core artifact dirs:
# - storage/artifacts/zhouGliatoNeuronConversionCRISPRCasRx2020/159c0cdd-618a-44de-94c0-ed26cd612b1c
# - storage/artifacts/zotero:zhouGliatoNeuronConversionCRISPRCasRx2020/run_20260223_145400
# Both remain scorecard-fail on low grounded-evidence coverage.

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_fail_ids_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_fail_ids_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_fail_ids_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# per-run and threshold-package actions now distinguish fail_ids from non_pass_ids, identifying Zhou as the only current scorecard fail target.

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "failed_scorecard_readiness or threshold_adoption_package_ready or roadmap_completion_from_threshold_adoption_package_cli"
# 3 passed, 317 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_fail_ids_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_fail_ids_20260525_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 Scorecard Fail Reason/Proxy Diagnostics Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_fail_proxy_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_fail_proxy_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_fail_proxy_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report /Users/jangseongjin/paperpipe-projects/main/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log /Users/jangseongjin/paperpipe-projects/main/storage/claim_evidence_corrections.jsonl --goldset-root /Users/jangseongjin/paperpipe-projects/main/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# fail-only reason/proxy diagnostics now isolate Zhou: coverage_low_grounded_evidence_ratio, coverage_low_page_coverage, coverage_missing_major_topic_signals; grounded_evidence_ratio=0.3333; page_coverage_ratio=0.0645; grounded_extraction_ref_rate=0.3333.
# broader non-pass reason/proxy context remains present separately.

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "failed_scorecard_readiness or threshold_adoption_package_ready or roadmap_completion_from_threshold_adoption_package_cli"
# 3 passed, 317 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_fail_proxy_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_fail_proxy_20260525_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 Scorecard Fail CLI Diagnostics Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_fail_proxy_stdout_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_fail_proxy_stdout_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_fail_proxy_stdout_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --goldset-root <paperpipe-projects-main>/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# stdout now prints fail-only threshold-package scorecard diagnostics:
# - threshold_package_baseline_scorecard_fail_ids=evidence-grounding-eval:baselinezotero:zhouGliatoNeuronConversionCRISPRCasRx2020
# - threshold_package_candidate_scorecard_fail_ids=evidence-grounding-eval:candidatezotero:zhouGliatoNeuronConversionCRISPRCasRx2020
# - threshold_package_*_scorecard_fail_reason_codes=coverage_low_grounded_evidence_ratio:1,coverage_low_page_coverage:1,coverage_missing_major_topic_signals:1
# - threshold_package_*_scorecard_fail_proxy_metrics isolate Zhou's grounded_evidence_ratio=0.3333, page_coverage_ratio=0.0645, and grounded_extraction_ref_rate=0.3333 context

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "roadmap_completion_from_threshold_adoption_package_cli or threshold_adoption_package_ready or failed_scorecard_readiness"
# 3 passed, 317 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_fail_proxy_stdout_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_fail_proxy_stdout_20260525_verify.json
# fail_count=0

.venv/bin/python -m py_compile scripts/eval/audit_evidence_grounding_roadmap_completion.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 P0 Metric CLI Diagnostics Follow-Up

```bash
# Current workspace check found no reviewed fixture sidecar/dir under goldset/reviews:
# claim_evidence_reviewed_eval_fixtures.json is not available, so overstatement_rate
# must remain missing until explicit OVERSTATED_RESULT review labels are curated.

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_p0_stdout_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_p0_stdout_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_p0_stdout_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --goldset-root <paperpipe-projects-main>/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# stdout now prints:
# - p0_available_metrics=claim_precision,evidence_support_precision,limitation_recall,locator_precision,method_result_confusion_rate,unsupported_claim_rate
# - p0_missing_metrics=overstatement_rate
# - threshold_p0_missing_calibration_metrics=overstatement_rate
# - threshold_p0_missing_adoption_metrics=overstatement_rate
# - threshold_production_ready=False

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "roadmap_completion_from_threshold_adoption_package_cli or names_overstatement_label_gap or threshold_adoption_missing_p0"
# 2 passed, 318 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_p0_stdout_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_p0_stdout_20260525_verify.json
# fail_count=0

.venv/bin/python -m py_compile scripts/eval/audit_evidence_grounding_roadmap_completion.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 Structured Correction Reason-Code Diagnostics Follow-Up

```bash
# Current raw correction log summary:
# - 3 source rows
# - 3 UNSUPPORTED_CLAIM reason-code rows
# - 0 OVERSTATED_RESULT rows
# - accepted rows still miss replay lineage, so this raw lane cannot fill overstatement_rate

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_correction_reason_stdout_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_correction_reason_stdout_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_correction_reason_stdout_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --goldset-root <paperpipe-projects-main>/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 0
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# stdout now includes structured_correction_source_reason_code_counts=UNSUPPORTED_CLAIM:3

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "roadmap_completion_from_threshold_adoption_package_cli or guides_existing_workspace_correction_log or cli_prints_correction_repair_targets"
# 3 passed, 317 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_correction_reason_stdout_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_correction_reason_stdout_20260525_verify.json
# fail_count=0

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py scripts/eval/audit_evidence_grounding_roadmap_completion.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## 2026-05-25 Structured Correction Reason-Code Action Detail Follow-Up

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_correction_reason_action_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_correction_reason_action_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_correction_reason_action_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --goldset-root <paperpipe-projects-main>/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_after_raw_schema_patch.json --print-next-actions --next-action-limit 6
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# structured_correction_log next_action now includes reason codes: UNSUPPORTED_CLAIM:3

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "guides_existing_workspace_correction_log or all_repair_targets or roadmap_completion_from_threshold_adoption_package_cli"
# 2 passed, 318 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_correction_reason_action_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_correction_reason_action_20260525_verify.json
# fail_count=0

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings
```

## Audit Decision

PR1 acceptance criteria are satisfied in the current worktree.

The broader active goal should remain open because the full roadmap still requires fixed-goldset execution, real candidate comparisons, threshold calibration from those runs, and stronger visual/consistency evaluation before the complete performance program can be called finished.

## 2026-05-25 Correction Repair Target Reason-Code Carry-Through

This follow-up keeps the correction repair handoff additive and non-canonical. Invalid raw correction rows now carry their `reason_codes` into source diagnostics and `claim_evidence_correction_repair_plan.v1` targets, so operators can see the failure-label context while repairing replay lineage. The raw correction log is unchanged, and the repair plan remains a review/gate artifact rather than canonical runtime truth or human approval evidence.

```bash
.venv/bin/python scripts/eval/export_claim_evidence_correction_repair_plan.py --log-path <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --out /tmp/pp_claim_evidence_correction_repair_plan_current_reason_codes_20260525.json
# source_record_count=3
# source_invalid_record_count=2
# repair_target_count=2
# reason_codes=line_1:UNSUPPORTED_CLAIM;line_2:UNSUPPORTED_CLAIM

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_repair_target_reason_fixed_path_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_repair_target_reason_fixed_path_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_repair_target_reason_fixed_path_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --goldset-root <paperpipe-projects-main>/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_current_reason_codes_20260525.json --print-next-actions --next-action-limit 6
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# raw correction lane still reports structured_correction_source_reason_code_counts=UNSUPPORTED_CLAIM:3

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_benchmark.py -q -k "repair_plan_route_exports_invalid_accepted_rows or repair_plan_script_exports_successfully_with_targets or recognizes_repair_plan_as_noncanonical_handoff"
# 3 passed, 344 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_repair_target_reason_fixed_path_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_repair_target_reason_fixed_path_20260525_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py -q
# 27 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings

.venv/bin/python -m py_compile src/schemas/claim_evidence_correction.py src/services/claim_evidence_corrections.py scripts/eval/export_claim_evidence_correction_repair_plan.py src/services/evidence_grounding_benchmark.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_benchmark.py
# passed
```

## 2026-05-25 Correction Repair Available Run Context Follow-Up

The correction repair plan now carries observed local run metadata as `available_replay_context` for invalid accepted rows. This is repair context only: it does not infer the missing parser/model/prompt/profile lineage, does not edit `claim_evidence_corrections.jsonl`, and does not convert the repair handoff into canonical truth. In the current workspace it shows that the linked run metadata can identify the clinical extraction provider/model and selected backends, while the accepted correction rows still need explicit replay lineage repair before eval export.

```bash
.venv/bin/python scripts/eval/export_claim_evidence_correction_repair_plan.py --log-path <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --out /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json
# source_record_count=3
# source_invalid_record_count=2
# repair_target_count=2
# available_replay_context includes provider_name=openai, provider_model=gpt-5.4-mini, clinical_extraction.selected_backend=commercial, reader.selected_backend=local, and run_meta.selected_backend=mixed for both invalid accepted rows

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_repair_context_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_repair_context_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_repair_context_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --goldset-root <paperpipe-projects-main>/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --print-next-actions --next-action-limit 6
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# stdout now includes structured_correction_available_replay_context=...
# structured-correction action includes available run context while preserving the missing replay-lineage fields

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_benchmark.py -q -k "repair_plan_route_exports_invalid_accepted_rows or repair_plan_script_exports_successfully_with_targets or recognizes_repair_plan_as_noncanonical_handoff"
# 3 passed, 344 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_repair_context_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_repair_context_20260525_verify.json
# fail_count=0

.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py -q
# 27 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 320 passed, 5 warnings

.venv/bin/python -m py_compile src/schemas/claim_evidence_correction.py src/services/claim_evidence_corrections.py scripts/eval/export_claim_evidence_correction_repair_plan.py src/services/evidence_grounding_benchmark.py scripts/eval/audit_evidence_grounding_roadmap_completion.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py scripts/eval/audit_evidence_grounding_roadmap_completion_from_comparison_suite_package.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_benchmark.py
# passed
```

## 2026-05-25 Threshold Package Scorecard Handoff Follow-Up

When threshold-package run coverage is already clean but embedded scorecards still fail readiness, the roadmap next action now points to scorecard input backfill instead of a generic benchmark-package rerun. This keeps the package blocker actionable without pretending the Zhou scorecard failure is resolved.

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_scorecard_handoff_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_scorecard_handoff_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_scorecard_handoff_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --goldset-root <paperpipe-projects-main>/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --print-next-actions --next-action-limit 10
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# threshold-package scorecard blocker command_hint now points to backfill_evidence_grounding_scorecard_inputs.py

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "scorecard_only_blocker_points_to_backfill_handoff or threshold_adoption_package_ready"
# 1 passed, 320 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_scorecard_handoff_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_scorecard_handoff_20260525_verify.json
# fail_count=0

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 321 passed, 5 warnings
```

## 2026-05-25 PR1 Current-State Completion Evidence Refresh

Current-state audit result for the original PR1 slice: the additive scorecard schema/service/API/CLI/test lane is complete, while the broader Evidence Grounding Performance roadmap remains intentionally incomplete and must stay gated by fixed-gold, threshold, correction, and contract-readiness evidence.

Requirement-by-requirement evidence:

| Requirement | Current evidence | Result |
| --- | --- | --- |
| Schema and service for `evidence_grounding_scorecard.json` exist | `src/schemas/evidence_grounding_scorecard.py` defines strict `EvidenceGroundingScorecard` and `EvidenceGroundingScorecardBuildRequest`; `src/services/evidence_grounding_scorecard.py` defines `build_evidence_grounding_scorecard`, `build_evidence_grounding_scorecard_from_run_dir`, `write_evidence_grounding_scorecard`, and protected explicit-output writes. | PR1 satisfied |
| Scorecard is additive and non-canonical | Schema fixes `layer="review_gate_artifact"` and `canonical_status="non_canonical"`; writer only emits `evidence_grounding_scorecard.json` or explicit non-source output paths. | PR1 satisfied |
| Builds from existing deepread artifacts without rerunning deepread | Builder reads saved `reader_eval.json`, `claimset_coverage.json`, `evidence_extraction_bundle.json`, `visual_evidence_ledger.json`, `acceptance_contract.json`, `quality_gate.json`, `claimset.resolved.json`, optional run-local gold/review/candidate-config sidecars, and fails closed when `run_dir` is missing or contains no loadable core sidecar. | PR1 satisfied |
| Separates runtime proxy metrics from gold-scored metrics | Schema and tests keep `runtime_proxy_metrics` and `gold_scored_metrics` separate; scorecard tests assert proxy/gold separation. | PR1 satisfied |
| Does not fake precision/recall without gold labels | Gold-scored metrics are `not_available` when gold labels are absent or mismatched; metric validation rejects `status="not_available"` with a numeric value. | PR1 satisfied |
| Missing or malformed inputs are explicit diagnostics, not silent zeros | Scorecards expose `input_artifact_diagnostics`, input coverage/missing/malformed metrics, warnings, and reason codes; malformed sidecar/API/CLI tests verify no source sidecar mutation. | PR1 satisfied |
| API-first scorecard build path exists and is protected | `POST /evidence-grounding/scorecards/build` is included through `backend/main.py`; `/evidence-grounding/` POST routes require API key auth when private auth is configured. | PR1 satisfied |
| Thin CLI path exists without creating a new runtime generation path | `scripts/eval/build_evidence_grounding_scorecard.py` delegates to the scorecard service, supports optional external eval-only gold and candidate config, reports operator input errors as concise masked messages, and writes the same non-canonical scorecard artifact. | PR1 satisfied |
| Response surfaces do not leak local operator paths while persisted review artifacts preserve lineage | Evidence Grounding FastAPI scorecard, benchmark, comparison, threshold, contract, run-readiness, roadmap, and manifest responses now return masked path copies; persisted non-canonical artifacts keep local lineage for review. Router scan finds no remaining direct service/report return sites matching `return (build|run|audit|check|load|package|report|compare)`. | PR1/API posture satisfied |
| Canonical runtime truth is not replaced | Scorecard code reads `ClaimSet`/sidecars as inputs and writes only non-canonical review artifacts; no `src/db_utils.py`, runtime DB state, or canonical paper/run model is promoted by this PR1 lane. | PR1 satisfied |

Latest verification:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 90 passed, 5 warnings

PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_key_auth.py -q
# 13 passed, 5 warnings

PYTHONPATH=. .venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 336 passed, 5 warnings

rg -n "return (build|run|audit|check|load|package|report|compare)" backend/routers/evidence_grounding.py
# no matches
```

Broader roadmap status: not complete. Current roadmap completion evidence remains blocked by downstream fixed-gold/threshold/correction/contract readiness gates and human review requirements. This refresh only proves the PR1 additive scorecard lane, not the full Evidence Grounding Performance roadmap.

## 2026-05-25 Structured Correction Command Path Masking Follow-Up

Roadmap completion command hints for structured claim/evidence correction repair now mask local operator paths before quoting command arguments. Diagnostic evidence and persisted audit input paths still preserve lineage for local replay, but user-facing next-action commands avoid personal absolute filesystem paths.

The live threshold-package audit remains correctly incomplete. The structured correction next action now points to:

```bash
.venv/bin/python scripts/eval/export_claim_evidence_correction_repair_plan.py --log-path ./storage/claim_evidence_corrections.jsonl --out <claim_evidence_correction_repair_plan.json>
```

Verification:

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "existing_workspace_correction_log or finds_storage_correction_log_from_goldset_root or rejects_nonreplayable_correction_log or recognizes_repair_plan_as_noncanonical_handoff or rejects_eval_candidate_export_with_invalid_source_records or invalid_source_records"
# 5 passed, 320 deselected, 5 warnings

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 325 passed, 5 warnings

# Live audit: /tmp/pp_roadmap_audit_complete_release_best_threshold_package_pathmask_20260525.json
# pass_count=8; fail_count=6; roadmap_complete=False
# next-action command hints contain no user-local absolute path

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_pathmask_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_pathmask_20260525_verify.json
# fail_count=0
```

## 2026-05-25 Scorecard Backfill CLI Fail-Closed Follow-Up

The scorecard input backfill CLI now fails closed when generated scorecards fail readiness. Previously, a backfill report could show `pass_count=8` and `fail_count=0` while also carrying `scorecard_fail_count=1`; the CLI exited successfully even though contract compatibility rejected the artifact. The report now records `scorecard_input_backfill_scorecard_failures_present`, and the CLI returns nonzero whenever `scorecard_fail_count > 0`.

This keeps roadmap handoffs aligned with the contract gate without changing canonical state, raw correction logs, gold labels, or threshold adoption evidence.

```bash
.venv/bin/python scripts/eval/backfill_evidence_grounding_scorecard_inputs.py --benchmark-manifest-package /tmp/pp_complete_release_best_baseline_manifest_package_20260525.json --out-run-root /tmp/pp_scorecard_backfill_failclosed_probe_20260525 --out /tmp/pp_scorecard_backfill_failclosed_probe_20260525.json
# exits 1 as expected; pass_count=8; fail_count=0; scorecard_readiness=pass=0 warn=7 fail=1

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_scorecard_backfill_failclosed_probe_20260525.json --out /tmp/pp_scorecard_backfill_failclosed_probe_compat_20260525.json
# fail_count=1; finding=scorecard_input_backfill_scorecard_failures_present

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -k "backfill_cli_writes_copied_run_root or backfill_cli_fails_when_generated_scorecard_fails_readiness or backfill_cli_derives_items_from_benchmark_manifest"
# 3 passed, 81 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py
# 84 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 325 passed, 5 warnings
```

## 2026-05-25 Scorecard Backfill Failure Summary Follow-Up

The scorecard input backfill CLI now prints a path-free failure summary when generated scorecards fail readiness. The summary names the failed `paper_id` and the scorecard reason codes, so a nonzero backfill run points directly to the next repair target without requiring the operator to inspect the report JSON first.

```bash
.venv/bin/python scripts/eval/backfill_evidence_grounding_scorecard_inputs.py --benchmark-manifest-package /tmp/pp_complete_release_best_baseline_manifest_package_20260525.json --out-run-root /tmp/pp_scorecard_backfill_failure_summary_probe_20260525 --out /tmp/pp_scorecard_backfill_failure_summary_probe_20260525.json
# exits 1 as expected
# scorecard_failures=paper_id=zotero:zhouGliatoNeuronConversionCRISPRCasRx2020,reason_codes=coverage_low_grounded_evidence_ratio,coverage_low_page_coverage,coverage_missing_major_topic_signals,gold_labels_missing

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_scorecard_backfill_failure_summary_probe_20260525.json --out /tmp/pp_scorecard_backfill_failure_summary_probe_compat_20260525.json
# exits 1 as expected; finding=scorecard_input_backfill_scorecard_failures_present

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -k "backfill_cli_fails_when_generated_scorecard_fails_readiness or backfill_cli_writes_copied_run_root"
# 2 passed, 82 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py
# 84 passed, 5 warnings
```

## 2026-05-25 Scorecard Backfill Compatibility Detail Follow-Up

Contract compatibility now carries the same actionable failed-scorecard detail as the backfill CLI. When a `scorecard_input_backfill` report contains generated scorecards with `readiness_status=fail`, the compatibility item includes a path-free detail sample with `paper_id` and scorecard reason codes. It also checks that the report warning marker `scorecard_input_backfill_scorecard_failures_present` matches the actual failed generated-scorecard count.

```bash
.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_scorecard_backfill_failure_summary_probe_20260525.json --out /tmp/pp_scorecard_backfill_failure_detail_compat_20260525.json
# exits 1 as expected
# finding=scorecard_input_backfill_scorecard_failure_details: paper_id=zotero:zhouGliatoNeuronConversionCRISPRCasRx2020,reason_codes=coverage_low_grounded_evidence_ratio,coverage_low_page_coverage,coverage_missing_major_topic_signals,gold_labels_missing

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "rejects_failed_scorecard_input_backfill or failed_contract_schema_coverage or separates_failed_compatibility_from_human_contract_readiness"
# 3 passed, 322 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 325 passed, 5 warnings
```

## 2026-05-25 Scorecard Backfill Contract Failure Guard Follow-Up

`evidence_grounding_scorecard_input_backfill.v1` contract compatibility now fails closed when a backfill artifact is schema-valid but operationally failed. This prevents a failed scorecard-input repair report from satisfying the external contract gate merely because its Pydantic shape is valid.

The guard checks raw item/pass/fail counts, scorecard readiness counts, failed backfill items, failed generated scorecards, and the failure warning marker. It remains a non-canonical review-gate check only; it does not mutate gold labels, raw correction logs, scorecard thresholds, or runtime truth.

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "failed_scorecard_input_backfill"
# 1 passed, 321 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "contract_compatibility and (scorecard_input_backfill or scorecard or benchmark or threshold_package or external_contract_readiness)"
# 123 passed, 199 deselected, 5 warnings

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 322 passed, 5 warnings
```

The live threshold-package roadmap audit after this guard remains intentionally incomplete:

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_backfill_guard_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_backfill_guard_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_backfill_guard_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log storage/claim_evidence_corrections.jsonl --goldset-root goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --print-next-actions --next-action-limit 20
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# remaining actions are still evidence/human-review blockers plus the missing scorecard_input_backfill.json artifact for this audit invocation
```

## 2026-05-25 Scorecard Backfill No-Scorecards Contract Guard Follow-Up

`evidence_grounding_scorecard_input_backfill.v1` contract compatibility now also fails closed when a backfill report copied runs and regenerated sidecars but did not build scorecards. This keeps `--no-scorecards` useful for local probes while preventing that incomplete artifact from satisfying external-contract evidence requirements.

The guard requires pass items to have scorecard readiness coverage and `evidence_grounding_scorecard.json` in `generated_artifacts`. It remains a non-canonical review-gate check only; report generation, runtime truth, gold labels, correction logs, and thresholds are unchanged.

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "scorecard_input_backfill_without_scorecards or failed_scorecard_input_backfill"
# 2 passed, 321 deselected, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "contract_compatibility and (scorecard_input_backfill or scorecard or benchmark or threshold_package or external_contract_readiness)"
# 124 passed, 199 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_manifest_package_backfill_probe_20260525.json --out /tmp/pp_contract_scorecard_input_backfill_probe_no_scorecards_guard_20260525.json
# exits nonzero as expected; fail_count=1
# findings: scorecard_input_backfill_scorecard_coverage_mismatch, scorecard_input_backfill_scorecard_artifacts_missing

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 323 passed, 5 warnings
```

Including the old incomplete `/tmp/pp_manifest_package_backfill_probe_20260525.json` in the live threshold-package roadmap audit now keeps the roadmap blocked via compatibility failure instead of allowing a sidecar-only backfill artifact to cover the contract evidence lane.

## 2026-05-25 Failed Contract Schema Detail Follow-Up

External-contract schema coverage now distinguishes missing required artifact schemas from provided-but-failing required artifact schemas. This keeps the operator action accurate when a `scorecard_input_backfill.json` exists but is incomplete or incompatible: the action names it as a failing schema, not as a missing schema.

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "failed_contract_schema_coverage or requires_contract_schema_coverage or names_only_remaining_contract_readiness_blockers"
# 3 passed, 321 deselected, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_failed_schema_detail_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_failed_schema_detail_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_failed_schema_detail_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log storage/claim_evidence_corrections.jsonl --goldset-root goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --additional-artifact /tmp/pp_manifest_package_backfill_probe_20260525.json --print-next-actions --next-action-limit 13
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external-contract action reports: failing schema versions: evidence_grounding_scorecard_input_backfill.v1; compatibility fail_count: 1

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 324 passed, 5 warnings
```

## 2026-05-25 External Contract Compatibility/Human Split Follow-Up

External-contract roadmap next actions now keep compatibility repair separate from human approval. If the compatibility report fails, `compatibility_report_passes` stays on the non-human contract compatibility action instead of being folded into the human approval action.

In the live threshold-package audit with the intentionally incomplete no-scorecards backfill artifact, the external-contract actions now split as:
- Non-human: repair failing `evidence_grounding_scorecard_input_backfill.v1` compatibility evidence.
- Human: provide approval reference and explicit opt-in after compatibility passes.

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "failed_contract_schema_coverage or separates_failed_compatibility or names_contract_readiness_blockers or names_only_remaining_contract_readiness_blockers"
# 4 passed, 321 deselected, 5 warnings

.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_split_compat_human_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_split_compat_human_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_split_compat_human_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log storage/claim_evidence_corrections.jsonl --goldset-root goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --additional-artifact /tmp/pp_manifest_package_backfill_probe_20260525.json --print-next-actions --next-action-limit 13
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# compatibility action: failing schema versions: evidence_grounding_scorecard_input_backfill.v1; compatibility fail_count: 1
# human action: reviewer_approval_reference_present,explicit_external_contract_opt_in; readiness fail_count: 2

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 325 passed, 5 warnings
```

## 2026-05-25 Manifest-Based Backfill API-First Follow-Up

The manifest-based scorecard input backfill path is now exposed through the existing FastAPI scorecard backfill endpoint, not only through the CLI. `EvidenceGroundingScorecardInputBackfillRequest` accepts `benchmark_manifest_paths` and `benchmark_manifest_package_paths`, and the route resolves those into the same non-canonical copied-run backfill items used by the CLI.

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q -k "input_backfill_api"
# 3 passed, 78 deselected, 5 warnings

.venv/bin/python -m py_compile src/schemas/evidence_grounding_scorecard.py backend/routers/evidence_grounding.py tests/test_evidence_grounding_scorecard.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 81 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 321 passed, 5 warnings

./scripts/run_backend_api_smoke.sh
# passed
```

## 2026-05-25 Scorecard Backfill API Response Masking Follow-Up

The scorecard input backfill API now masks local filesystem paths in the HTTP response while leaving the persisted `out` report unmasked for local replay and audit traceability. This keeps the API/frontend-visible surface aligned with PaperPipe's local path masking posture without changing the non-canonical report artifact.

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q -k "input_backfill_api"
# 3 passed, 78 deselected, 5 warnings

.venv/bin/python -m py_compile backend/routers/evidence_grounding.py tests/test_evidence_grounding_scorecard.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 81 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 321 passed, 5 warnings

./scripts/run_backend_api_smoke.sh
# passed
```

## 2026-05-25 Manifest Package Backfill API Contract Regression

The scorecard input backfill API now has explicit regression coverage for manifest package inputs. This closes the remaining API-first parity gap after the CLI learned to derive backfill items from benchmark manifest packages: the FastAPI route accepts `benchmark_manifest_package_paths`, resolves embedded manifest item `run_dir` values, writes copied-run scorecard inputs under `out_run_root`, masks local paths in the HTTP response, and preserves full paths only in the local `out` report.

This is contract coverage only. It does not mark scorecard readiness complete, fabricate reviewed fixtures, fill `overstatement_rate`, repair the raw correction log, or approve external contract readiness.

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -k "input_backfill_api_derives_items_from_benchmark_manifest_package or input_backfill_api_derives_items_from_benchmark_manifest or input_backfill_api_writes_noncanonical_report"
# 3 passed, 79 deselected, 5 warnings

.venv/bin/python -m py_compile tests/test_evidence_grounding_scorecard.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py
# 82 passed, 5 warnings
```

## 2026-05-25 Embedded Manifest Package Out-Dir Resolution Follow-Up

The scorecard input backfill manifest-package helper now handles embedded-only packages more safely. If an `evidence_grounding_benchmark_manifest_package.v1` includes embedded `benchmark_manifests` but no linked `benchmark_manifest_paths`, relative embedded item `run_dir` values are resolved from package `out_dir`, which is the manifest output directory, instead of from the directory containing the package JSON file.

This closes a concrete replay failure: a package archived outside its manifest output tree could previously derive the wrong source run path and produce a failed backfill report even though the embedded manifest was valid relative to its declared `out_dir`. The change only affects non-canonical scorecard input backfill item loading; it does not change gold evidence, threshold readiness, raw correction logs, or canonical runtime state.

```bash
.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -k "resolves_embedded_package_runs_from_out_dir"
# failed before the service fix with pass_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -k "resolves_embedded_package_runs_from_out_dir or derives_items_from_benchmark_manifest_package or derives_items_from_benchmark_manifest"
# 4 passed, 79 deselected, 5 warnings

.venv/bin/python -m py_compile src/services/evidence_grounding_scorecard_input_backfill.py tests/test_evidence_grounding_scorecard.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py
# 83 passed, 5 warnings

./scripts/run_backend_api_smoke.sh
# passed
```

## 2026-05-25 Scorecard Backfill Contract Schema Requirement Follow-Up

The roadmap external-contract gate now requires `evidence_grounding_scorecard_input_backfill.v1` coverage. This aligns the contract check with the existing roadmap handoffs and API request descriptions that already name `scorecard_input_backfill.json` as a required review/contract artifact.

Before this change, a contract compatibility report could omit the backfill report schema while the roadmap action still instructed operators to provide `scorecard_input_backfill.json`. The live threshold-package audit now remains blocked, but the blocker is more accurate: `external_contract_readiness_reviewed` reports `missing_contract_schema_versions=evidence_grounding_scorecard_input_backfill.v1` when the backfill artifact is absent.

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_require_backfill_schema_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_require_backfill_schema_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_require_backfill_schema_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log storage/claim_evidence_corrections.jsonl --goldset-root goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --print-next-actions --next-action-limit 4
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# external_contract_readiness_reviewed now includes missing_contract_schema_versions=evidence_grounding_scorecard_input_backfill.v1

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "from_threshold_adoption_package or false_incomplete_roadmap_completion or incomplete_fail_count or unexpected_roadmap_completion_warnings or missing_warn_status_marker or can_pass_with_all_review_evidence or requires_correction_export_contract_schema_coverage"
# 16 passed, 305 deselected, 5 warnings

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 321 passed, 5 warnings
```

## 2026-05-25 External Contract Action Split Follow-Up

External-contract next actions now separate non-human compatibility gaps from human approval work. Missing schema versions and missing audited artifact paths stay on the `Run contract compatibility...` action. The human `Complete ... before external contract readiness is marked ready` action is emitted only when readiness blockers, readiness consistency findings, or readiness failures exist, and its detail is limited to those readiness fields.

This avoids telling a human reviewer to complete approval while the action detail is actually describing an artifact/schema omission. In the current live threshold-package audit, the compatibility action carries `missing schema versions: evidence_grounding_scorecard_input_backfill.v1`, while the human action only carries `reviewer_approval_reference_present`, `explicit_external_contract_opt_in`, and readiness fail count.

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_split_contract_actions_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_split_contract_actions_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_split_contract_actions_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log storage/claim_evidence_corrections.jsonl --goldset-root goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --print-next-actions --next-action-limit 20
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# compatibility action carries missing schema; human approval action carries only readiness blockers/fail count

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "contract_schema_coverage or readiness_details or names_only_remaining_contract_readiness_blockers or external_contract_readiness"
# 4 passed, 317 deselected, 5 warnings

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 321 passed, 5 warnings
```

## 2026-05-25 External Contract Detail Isolation Follow-Up

External-contract action details are now fully separated by responsibility. The non-human compatibility action includes only compatibility-side gaps: missing schema versions, missing audited artifact paths, compatibility fail count, or compatibility consistency findings. Readiness blockers, readiness fail count, and readiness consistency findings are reserved for the human readiness action.

This keeps the current live audit clearer: the compatibility action says only that `evidence_grounding_scorecard_input_backfill.v1` is missing; the human action says only that reviewer approval and explicit external-contract opt-in remain absent.

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_isolate_contract_details_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_isolate_contract_details_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_isolate_contract_details_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log storage/claim_evidence_corrections.jsonl --goldset-root goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --print-next-actions --next-action-limit 20
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# compatibility action carries only missing schema; human action carries readiness blockers/fail count

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -k "readiness_details or names_only_remaining_contract_readiness_blockers or contract_schema_coverage or external_contract_readiness"
# 4 passed, 317 deselected, 5 warnings

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py
# 321 passed, 5 warnings
```

## 2026-05-25 Per-Run Scorecard Handoff Follow-Up

The per-run scorecard readiness blocker now mirrors the threshold-package scorecard handoff: when embedded scorecards fail readiness, the command hint points first to scorecard input backfill rather than a generic fixed-goldset comparison rerun. This keeps Zhou-style readiness failures actionable while preserving the failed completion state.

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_per_run_scorecard_handoff_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_per_run_scorecard_handoff_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_per_run_scorecard_handoff_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --goldset-root <paperpipe-projects-main>/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --print-next-actions --next-action-limit 4
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# per_run_and_aggregate_scorecards scorecard blocker command_hint now points to backfill_evidence_grounding_scorecard_inputs.py

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "rejects_failed_scorecard_readiness or scorecard_only_blocker_points_to_backfill_handoff"
# 2 passed, 319 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_per_run_scorecard_handoff_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_per_run_scorecard_handoff_20260525_verify.json
# fail_count=0

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 321 passed, 5 warnings
```

## 2026-05-25 Per-Run Scorecard Action Ordering Follow-Up

The per-run scorecard blocker now puts the scorecard-input backfill action before the generic fixed-goldset comparison rerun whenever embedded scorecards fail readiness. This is only an operator-handoff ordering fix: it does not mark Zhou ready, does not alter the benchmark evidence, and does not change canonical runtime truth.

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_scorecard_order_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_scorecard_order_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_scorecard_order_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --goldset-root <paperpipe-projects-main>/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --print-next-actions --next-action-limit 4
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# next_action.1 is the scorecard backfill handoff; next_action.2 is the follow-up comparison rerun

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "rejects_failed_scorecard_readiness"
# 1 passed, 320 deselected, 5 warnings

.venv/bin/python -m py_compile src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 321 passed, 5 warnings
```

## 2026-05-25 Manifest-Based Scorecard Backfill Handoff Follow-Up

The scorecard input backfill CLI can now derive its item list from existing benchmark manifests and manifest packages. This removes an opaque hand-authored `<fixed_goldset_scorecard_backfill_items.json>` step from roadmap handoffs while preserving the same non-canonical, copy-into-output-root behavior.

```bash
.venv/bin/python scripts/eval/audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package.py --threshold-adoption-package /tmp/pp_complete_release_best_threshold_adoption_package_20260525.json --contract-compatibility-out /tmp/pp_contract_complete_release_best_threshold_package_manifest_backfill_handoff_20260525.json --contract-readiness-out /tmp/pp_contract_readiness_complete_release_best_threshold_package_manifest_backfill_handoff_20260525.json --out /tmp/pp_roadmap_audit_complete_release_best_threshold_package_manifest_backfill_handoff_20260525.json --representative-split eval --migration-plan docs/Evidence_Grounding_External_Contract_Migration_Plan_2026-05-25.md --backfill-plan docs/Evidence_Grounding_External_Contract_Backfill_Plan_2026-05-25.md --public-contract-doc docs/Evidence_Grounding_Public_Contract_Draft_2026-05-25.md --gold-release-package <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json --gold-release-readiness-report <paperpipe-projects-main>/goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_readiness.json --correction-log <paperpipe-projects-main>/storage/claim_evidence_corrections.jsonl --goldset-root <paperpipe-projects-main>/goldset --run-root /tmp/pp_complete_release_backfill_runs_best_20260525 --additional-artifact /tmp/pp_claim_evidence_correction_repair_plan_context_20260525.json --print-next-actions --next-action-limit 4
# exits nonzero as expected; pass_count=8; fail_count=6; roadmap_complete=False
# scorecard backfill hints now use --benchmark-manifest or --benchmark-manifest-package

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q -k "backfill_cli_derives_items_from_benchmark_manifest or backfill_cli_writes_copied_run_root"
# 2 passed, 78 deselected, 5 warnings

.venv/bin/python scripts/eval/backfill_evidence_grounding_scorecard_inputs.py --benchmark-manifest-package /tmp/pp_complete_release_best_baseline_manifest_package_20260525.json --out-run-root /tmp/pp_manifest_package_backfill_probe_20260525 --out /tmp/pp_manifest_package_backfill_probe_20260525.json --no-scorecards
# item_count=8; pass_count=8; fail_count=0

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q -k "rejects_failed_scorecard_readiness or scorecard_only_blocker_points_to_backfill_handoff"
# 2 passed, 319 deselected, 5 warnings

.venv/bin/python scripts/eval/check_evidence_grounding_contract_compatibility.py --artifact /tmp/pp_roadmap_audit_complete_release_best_threshold_package_manifest_backfill_handoff_20260525.json --out /tmp/pp_contract_complete_release_best_threshold_package_manifest_backfill_handoff_20260525_verify.json
# fail_count=0

.venv/bin/python -m py_compile src/services/evidence_grounding_scorecard_input_backfill.py scripts/eval/backfill_evidence_grounding_scorecard_inputs.py src/services/evidence_grounding_benchmark.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 80 passed, 5 warnings

.venv/bin/python -m pytest tests/test_evidence_grounding_benchmark.py -q
# 321 passed, 5 warnings
```

## 2026-05-27 PR1 Scorecard Route Ownership Reaudit

The PR1 scorecard build route is now owned by a scorecard-only FastAPI router instead of the mixed later-roadmap evidence-grounding router. `backend/routers/evidence_grounding_scorecards.py` exposes only `POST /evidence-grounding/scorecards/build`, delegates to the scorecard service and writer helpers, maps operator input failures to `400`, and masks local paths in API responses/log messages. `backend/main.py` includes that scorecard-only router directly and keeps `/evidence-grounding/` under the API-key policy.

This is a lane-boundary and verification update. It does not change canonical paper truth, DB/state, accepted gold, benchmark thresholds, reviewer-filled values, or external contract approval state.

```bash
.venv/bin/python -m py_compile src/schemas/evidence_grounding_scorecard.py src/services/evidence_grounding_scorecard.py backend/routers/evidence_grounding_scorecards.py scripts/eval/build_evidence_grounding_scorecard.py tests/test_evidence_grounding_scorecard.py tests/test_api_key_auth.py backend/main.py
# passed

.venv/bin/python -m pytest tests/test_evidence_grounding_scorecard.py -q
# 165 passed, 5 warnings

.venv/bin/python -m pytest tests/test_api_key_auth.py -k "write_endpoints_require_api_key_when_configured or write_endpoints_accept_valid_api_key" -q
# 2 passed, 11 deselected, 5 warnings

./scripts/run_backend_api_smoke.sh
# exits 0

.venv/bin/python - <<'PY'
from backend import main as api_main
routes = [route for route in api_main.app.routes if getattr(route, "path", None) == "/evidence-grounding/scorecards/build"]
print(len(routes))
print([(sorted(getattr(route, "methods", []) or []), getattr(getattr(route, "endpoint", None), "__module__", None)) for route in routes])
PY
# 1
# [(['POST'], 'backend.routers.evidence_grounding_scorecards')]
```
