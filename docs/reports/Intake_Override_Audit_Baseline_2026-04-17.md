# Intake Override Audit Baseline

Status: bounded baseline established
Date: 2026-04-17
Lane: `smallest-safe-patch`

## Purpose

Turn intake classification quality from an anecdotal judgment into a measurable, replayable lane.

This work does not retune the classifier.
It adds the missing audit surface for the existing `feedback_json.intake_override_log` contract and records the first baseline snapshots.

## Baseline Definition

Treat the intake-classification implementation baseline as reached only if all of the following are true:

1. The repo can replay persisted paper-like rows and compute:
   - `triage_override_rate`
   - `slot_disagreement_rate`
   - `tag_disagreement_rate`
   - `analysis_unavailable_rate`
   - `issues_state_unavailable_rate`
2. The audit can run against both:
   - a curated replay file
   - the current runtime DB
3. The output is persisted as stable JSON artifacts with explicit per-document details.

This is an implementation baseline, not a claim that current runtime classification quality is already good enough.

## New Paths

- Schema:
  [src/schemas/intake_override_audit.py](/Users/jangseongjin/paperpipe/src/schemas/intake_override_audit.py)
- Service:
  [src/services/intake_override_audit.py](/Users/jangseongjin/paperpipe/src/services/intake_override_audit.py)
- Eval script:
  [scripts/eval/audit_intake_override_logs.py](/Users/jangseongjin/paperpipe/scripts/eval/audit_intake_override_logs.py)
- Coverage gate:
  [scripts/eval/check_intake_override_coverage_gate.py](/Users/jangseongjin/paperpipe/scripts/eval/check_intake_override_coverage_gate.py)
- Broader readiness summary:
  [scripts/eval/check_internal_data_readiness.py](/Users/jangseongjin/paperpipe/scripts/eval/check_internal_data_readiness.py)
- Fixture cleanup maintenance script:
  [scripts/archive_fixture_no_feedback_papers.py](/Users/jangseongjin/paperpipe/scripts/archive_fixture_no_feedback_papers.py)
- Fixture cleanup CLI command:
  [src/cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- Runtime readiness hygiene surface:
  [src/services/runtime_readiness.py](/Users/jangseongjin/paperpipe/src/services/runtime_readiness.py)
- Backend smoke lane:
  [scripts/run_backend_api_smoke.sh](/Users/jangseongjin/paperpipe/scripts/run_backend_api_smoke.sh)
- Curated replay fixture:
  [tests/fixtures/intake_override_curated_replay_20260417.jsonl](/Users/jangseongjin/paperpipe/tests/fixtures/intake_override_curated_replay_20260417.jsonl)

## Current Operator Flow

Current operator path:

1. Generate an audit run with:
   `.venv/bin/python scripts/eval/audit_intake_override_logs.py --run-id <run_id>`
2. Read the compact markdown summary first:
   `<run_dir>/audit.md`
3. If you want a terminal view with buckets and metrics, run:
   `.venv/bin/paperpipe show-intake-override-audit <run_dir>`
4. If you want to collect threshold-review evidence in the same pass, rerun with:
   `.venv/bin/python scripts/eval/audit_intake_override_logs.py --run-id <run_id> --emit-threshold-review`
5. Inspect the emitted threshold-review artifact with:
   `.venv/bin/paperpipe show-intake-override-threshold-review <threshold_review_run_dir>`
6. By default, threshold-review sidecars emitted from the audit script are stored as operator provenance but `latest_eligible=false`, so they do not replace the operator-facing latest threshold review.
7. Only mark a threshold review latest-eligible when it is the run you want `paperpipe doctor`, `self-test --json`, and readiness/API to advertise:
   `.venv/bin/python scripts/eval/audit_intake_override_logs.py --run-id <run_id> --emit-threshold-review --threshold-review-latest-eligible`
8. Use `<run_dir>/summary.json` and `<run_dir>/details.json` when another script or follow-up check needs machine-readable artifacts

Current artifact contract per run:

- `summary.json`
- `details.json`
- `audit.md`
- optional threshold review summary under `snapshots/intake_override_threshold_review/<run_id>__threshold_review/summary.json`

Threshold review provenance contract:

- `provenance.kind=operator`: intended as a real review candidate
- `provenance.kind=synthetic`: test, smoke, or exploratory artifact
- `provenance.latest_eligible=true`: may appear as the operator-facing latest threshold review
- `provenance.latest_eligible=false`: hidden from operator-facing latest selection, but still fully inspectable by path or viewer command

## Curated Replay Baseline

Replay artifact:

- Summary:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_audits/intake_override_curated_replay_20260417_r1/summary.json)
- Details:
  [details.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_audits/intake_override_curated_replay_20260417_r1/details.json)

Curated result:

- `document_count=4`
- `audited_document_count=3`
- `missing_intake_override_log_count=1`
- `triage_override_rate=0.3333`
- `slot_disagreement_rate=0.5`
- `tag_disagreement_rate=0.0`
- `analysis_unavailable_rate=0.3333`
- `issues_state_unavailable_rate=0.3333`

Interpretation:

- the audit lane is now real and replayable
- processor vs watcher can be separated in producer-level metrics
- missing-log rows are now explicit instead of silently disappearing from review

## Current Runtime DB Snapshot

Runtime artifact:

- Summary:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_audits/intake_override_db_baseline_20260417_r1/summary.json)
- Details:
  [details.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_audits/intake_override_db_baseline_20260417_r1/details.json)

Current DB result:

- `document_count=65`
- `has_feedback_json_count=54`
- `audited_document_count=0`
- `missing_intake_override_log_count=54`
- `no_feedback_json_count=11`

Interpretation:

- the new audit lane works, but current runtime storage has no persisted intake-override payloads to audit
- this means the current repo now has a measurable classification baseline, while the runtime data coverage gap is surfaced as an explicit blocker instead of hidden uncertainty

## Runtime Coverage Follow-up

Follow-up artifacts after patching the legacy gate/backfill paths and running a bounded backfill:

- Summary:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_audits/intake_override_db_baseline_20260417_r2/intake_override_db_baseline_20260417_r2/summary.json)
- Details:
  [details.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_audits/intake_override_db_baseline_20260417_r2/intake_override_db_baseline_20260417_r2/details.json)

Follow-up result:

- `document_count=65`
- `audited_document_count=54`
- `missing_intake_override_log_count=0`
- `no_feedback_json_count=11`
- `triage_override_rate=0.0`
- `slot_disagreement_rate=0.0`
- `tag_disagreement_rate=0.0`
- `analysis_unavailable_rate=0.0`
- `issues_state_unavailable_rate=0.0`
- `producer_counts={"backfill_analysis": 54}`

Interpretation:

- the runtime coverage blocker is now materially reduced: previously auditable runtime rows were `0`, now `54`
- the remaining `11` rows are not analyzed legacy rows with hidden overrides; they are rows with no `feedback_json`
- this confirms the audit lane is no longer just theoretically wired, and the repo can now produce a non-empty runtime audit on real local state

## Fixture-Aware Residual Bucket Follow-up

Fixture-aware runtime artifact:

- Summary:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_audits/intake_override_db_baseline_20260417_r3/intake_override_db_baseline_20260417_r3/summary.json)
- Details:
  [details.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_audits/intake_override_db_baseline_20260417_r3/intake_override_db_baseline_20260417_r3/details.json)

Fixture-aware result:

- `document_count=65`
- `test_fixture_document_count=14`
- `non_fixture_document_count=51`
- `no_feedback_json_count=11`
- `test_fixture_no_feedback_json_count=11`
- `non_fixture_no_feedback_json_count=0`
- `documents_with_missing_log_non_fixture=[]`

Interpretation:

- the residual `no_feedback_json` bucket is now explicitly classified instead of left ambiguous
- on the current local runtime state, every remaining `no_feedback_json` row is a fixture/test row
- there are no non-fixture rows left in the runtime DB that both lack `feedback_json` and still appear as hidden classification-audit debt

## Coverage Gate Follow-up

Advisory gate artifact:

- Summary:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_coverage_gate/intake_override_db_coverage_gate_20260417_r1/summary.json)

Gate result:

- `gate_applies=true`
- `passed=true`
- `feedback_coverage_rate=1.0`
- `blockers=[]`

Interpretation:

- once feedback-bearing rows exist, the repo now has a tiny machine-readable guard that can fail when intake override coverage silently drops
- the gate is intentionally advisory and summary-driven: it reads the audit artifact rather than adding a second runtime truth path

## Readiness Summary Integration

Broader readiness artifact:

- Summary:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/internal_data_readiness/internal_data_with_intake_override_gate_20260417_r2/summary.json)

Integrated result:

- `surfaces.intake_override_coverage_gate.status=present`
- `surfaces.intake_override_coverage_gate.decision.gate_applies=true`
- `surfaces.intake_override_coverage_gate.decision.passed=true`
- `surfaces.intake_override_coverage_gate.decision.feedback_coverage_rate=1.0`
- `category_status.classification_audit=bootstrap_ready`

Interpretation:

- the intake override guard is no longer a standalone artifact that has to be remembered manually
- the broader internal-data readiness summary now exposes classification-audit health alongside the other bounded advisory surfaces
- this keeps the new baseline visible without widening runtime ownership or changing the classifier contract

## Backend Smoke Integration

CI-facing integration:

- Script:
  [run_backend_api_smoke.sh](/Users/jangseongjin/paperpipe/scripts/run_backend_api_smoke.sh)

Integrated result:

- backend smoke now lint-checks:
  - `scripts/eval/check_intake_override_coverage_gate.py`
  - `scripts/eval/check_internal_data_readiness.py`
- backend smoke now executes:
  - `tests/test_intake_override_coverage_gate.py`
  - `tests/test_internal_data_readiness.py`

Interpretation:

- the new classification-audit guard is no longer local-only verification
- the existing `backend-api-smoke` workflow will now exercise the guard through its owner tests without requiring a new workflow
- this keeps CI wiring small and aligned with the current verification contract instead of introducing another parallel gate job

## Fixture Cleanup Maintenance Follow-up

Maintenance path:

- Script:
  [archive_fixture_no_feedback_papers.py](/Users/jangseongjin/paperpipe/scripts/archive_fixture_no_feedback_papers.py)

Dry-run result on the current local runtime DB:

- `fixture_no_feedback_candidates=11`
- `by_fixture_reason={"fixture_visibility_rule": 10, "paper_id_test_prefix": 1}`
- `by_status={"NEW": 10, "FETCHED": 1}`

Behavior:

- the script reuses the shared fixture-classification helper rather than inventing a second cleanup rule
- default behavior is dry-run only
- `--apply` first writes a SQLite backup, then archives original rows into `fixture_papers_archive`, then deletes only fixture rows whose `feedback_json` is still empty
- the same maintenance path is now also exposed through the CLI command `archive-fixture-no-feedback-papers`

Interpretation:

- the repo now has a bounded cleanup path for the residual fixture-only bucket without changing parser/classifier ownership
- this keeps the cleanup lane operational and reversible instead of forcing immediate mutation of the local runtime DB
- the new archive table is an ops/recovery artifact, not a new canonical state path

## Fixture Cleanup CLI Follow-up

CLI path:

- Command:
  `archive-fixture-no-feedback-papers`
- Implementation:
  [src/cli.py](/Users/jangseongjin/paperpipe/src/cli.py)

CLI behavior:

- supports `--db`, `--apply`, `--sample`, `--max-count`, `--backup-path`, and `--json`
- remains a thin wrapper over the same script-owned archive logic rather than introducing a second cleanup implementation
- on the current cleaned local runtime DB, the CLI dry-run reports no remaining candidates

Interpretation:

- the cleanup path is now available through the repo's existing operator entrypoint instead of requiring direct script invocation
- runtime hygiene can be checked or applied with the same dry-run/apply ergonomics used by other PaperPipe cleanup commands

## Doctor Hygiene Follow-up

Doctor/readiness path:

- Runtime readiness service:
  [src/services/runtime_readiness.py](/Users/jangseongjin/paperpipe/src/services/runtime_readiness.py)
- Doctor command:
  [src/cli.py](/Users/jangseongjin/paperpipe/src/cli.py)

Behavior:

- runtime readiness now emits `fixture_paper_hygiene` as an advisory check backed by the existing fixture archive candidate selector
- `doctor` now prints a dedicated `Fixture Paper Hygiene` line alongside structured-state and Meeting Pack hygiene
- when candidates exist, the warning text points directly at `paperpipe archive-fixture-no-feedback-papers`
- browser-safe readiness summary also treats this as part of internal runtime storage hygiene instead of dropping the signal entirely
- when fixture paper cleanup candidates reach `10` or more, the check now escalates from `warn` to `error`
- that `10`-candidate threshold is intentionally fixed for now rather than exposed as config

Live result after the earlier cleanup:

- `fixture_paper_hygiene.status=ok`
- `fixture_paper_hygiene.detail="no fixture paper cleanup candidates detected"`

Interpretation:

- fixture paper cleanup is now not only runnable, but also discoverable from the main runtime diagnosis path
- this closes the operator loop: `doctor` can now point to the exact cleanup command when the local runtime DB drifts again
- severe local drift now promotes the overall readiness result as well, instead of leaving a large candidate pile as a soft warning
- the threshold remains simple and deterministic until real operator evidence justifies making it configurable

## Producer Ownership Follow-up

Internal readiness artifact:

- Summary:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/internal_data_readiness/internal_data_with_intake_override_producer_ownership_20260420_r1/summary.json)

Behavior:

- internal-data readiness now exposes `intake_override_producer_ownership` as a separate advisory surface
- this surface distinguishes runtime producers (`processor_gate`, `processor_daily_slots`, `watcher_local_pdf`) from repair-only producers (`backfill_analysis`)
- it does not change runtime state; it makes current producer provenance explicit so repair-only coverage is not mistaken for active runtime ownership

Current local runtime result:

- `classification_audit=bootstrap_ready`
- `classification_runtime_producer=repair_only`
- `producer_counts={"backfill_analysis": 54}`
- `runtime_producer_present=false`
- `repair_only_mode=true`
- `primary_runtime_producer=null`

Interpretation:

- the current local runtime DB is fully auditable, but that auditability is still coming entirely from the repair/backfill lane
- this means the baseline is now measurable in a sharper way: coverage is good, but active runtime producer ownership is not yet demonstrated on the current local state
- the next meaningful runtime-side change should focus on real producer ownership rather than more repair-only coverage work

## Bounded Processor Gate Replay Follow-up

Applied artifacts:

- Runtime audit after bounded replay:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_audits/intake_override_db_baseline_20260420_r5/intake_override_db_baseline_20260420_r5/summary.json)
- Coverage gate after bounded replay:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_coverage_gate/intake_override_db_coverage_gate_20260420_r4/summary.json)
- Readiness summary after bounded replay:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/internal_data_readiness/internal_data_with_intake_override_runtime_replay_20260420_r2/summary.json)
- SQLite backup before bounded replay:
  [state_before_processor_gate_replay_20260420_184642.db](/Users/jangseongjin/paperpipe/storage/backups/state_before_processor_gate_replay_20260420_184642.db)

Behavior:

- `src/processor.py` now exposes the gate-persistence calculation as a reusable helper instead of keeping it trapped inside `_step_gate`
- `scripts/replay_processor_gate_intake_logs.py` reuses that helper in dry-run mode by default
- replay explicitly disables escalation and only applies rows whose current `gate_decision` and effective final status stay stable under the current gate helper
- rows that would drift are intentionally left as `backfill_analysis` rather than being force-promoted

Current local runtime result after apply:

- replay dry-run before apply: `backfill_candidates=54`, `promotable_candidates=28`, `skipped_candidates=26`
- skip reasons: `gate_decision_mismatch=24`, `status_mismatch=2`
- dominant drift transitions: `APPROVED -> PENDING_REVIEW` for `23` rows, `PENDING_REVIEW -> APPROVED` for `1` row, and `PENDING_REVIEW -> PENDING_REVIEW` with final-status mismatch for `2` rows
- replay apply result: `updated=28`
- post-apply repeat dry-run: `backfill_candidates=26`, `promotable_candidates=0`
- audit producer counts now show `processor_gate=28`, `backfill_analysis=26`
- audit processing-status counts now show `APPROVED=28`, `INDEXED=26`
- readiness now reports:
  - `classification_runtime_producer=runtime_ready`
  - `runtime_producer_present=true`
  - `primary_runtime_producer="processor_gate"`
  - `runtime_producer_document_count=28`
  - `repair_producer_document_count=26`
  - `runtime_producer_coverage_rate=0.5185185185185185`

Interpretation:

- the local runtime DB is no longer `repair_only`; current persisted state now includes a real bounded subset of `processor_gate` ownership
- this was not a full promotion and should not be described that way: just over half of the audited rows are stable under current gate logic, while the rest still reflect legacy drift
- the residual `26` rows are useful evidence, not cleanup noise, because they show where historical decisions and the current gate helper no longer agree
- the next safe step is to inspect that drift explicitly before widening replay scope or changing any gate semantics

## Replay Drift Audit Follow-up

Artifacts:

- Pre-apply drift audit on the replay backup DB:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/processor_gate_replay_drift/processor_gate_replay_drift_preapply_20260421_r9/summary.json)
- Residual drift audit on the current live DB:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/processor_gate_replay_drift/processor_gate_replay_drift_residual_20260421_r9/summary.json)

Behavior:

- the repo now has a dedicated `processor_gate` replay-drift lane that reuses the existing replay helper rather than inventing a second gate implementation
- the drift lane records candidate counts, promotable counts, skip reasons, decision transitions, confidence bands, and evidence-source presence for the backfill-owned rows under review
- the same lane now carries schema-backed provenance layers for canonical-id migration, legacy feedback import, feedback-log timestamp ordering, preserved explicit pre-canonical gate reasons, and fixture/test-row classification
- the same lane can now optionally attach legacy `feedback.jsonl` provenance by comparing current rows against claim-level average confidence from the historical feedback log
- this is additive observability only; it does not mutate runtime state and it does not alter gate thresholds

Observed pattern:

- pre-apply backup DB:
  - `candidate_count=54`
  - `promotable_count=28`
  - `drift_count=26`
  - `drift_rate=0.48148148148148145`
- residual current DB:
  - `candidate_count=26`
  - `promotable_count=0`
  - `drift_count=26`
  - `drift_rate=1.0`
- both audits show the same dominant transition pattern:
  - `APPROVED -> PENDING_REVIEW = 23`
  - `PENDING_REVIEW -> APPROVED = 1`
  - `PENDING_REVIEW -> PENDING_REVIEW = 2` with final-status mismatch
- both audits also show the same confidence/evidence pattern:
  - `confidence_band_counts={"mid": 25, "high": 1}`
  - `evidence_source_counts={"evidence_span": 26}`
- the inferred cause taxonomy is also stable across both audits:
  - `legacy_mid_confidence_approval=21`
  - `manual_or_human_override_mid_confidence=2`
  - `legacy_indexed_pending_review=2`
  - `legacy_high_confidence_pending=1`
- direct row-level provenance signals are now also stable across both audits:
  - `gate_reason_category_counts={"none": 22, "manual_or_human": 2, "confidence_threshold": 2}`
  - `timestamp_relation_counts={"created_updated_differ": 26}`
  - `confidence_value_counts={"0.8": 25, "0.95": 1}`
- direct canonical-migration provenance is now also visible in the same artifacts:
  - `identity_migration_hint_counts={"precanonical_row_matches_current_decision": 25}`
  - the drift lane uses `storage/paper_id_migration_plan.json` plus `storage/state.db.bak.zotero_policy.20260223_125245` to compare current canonical ids against their pre-canonical legacy rows
- direct feedback-import provenance is now also visible in the same artifacts:
  - `feedback_log_import_hint_counts={"feedback_import_gate_preserved_confidence_overwritten": 21, "feedback_import_gate_and_confidence_match": 1, "no_feedback_log_match": 4}`
  - `feedback_log_timestamp_relation_counts={"feedback_before_or_equal_created": 22}`
  - `feedback_log_to_precanonical_update_relation_counts={"feedback_before_or_equal_created": 22}`
  - the drift lane uses `storage/feedback.jsonl` to compute a legacy average claim confidence, carry forward the original feedback timestamp, and derive the implied `APPROVED if avg > 0.8 else PENDING_REVIEW` gate hint for each matching legacy paper id
- direct later-rewrite candidates are now also visible in the same artifacts:
  - `historical_rewrite_hint_counts={"post_feedback_precanonical_confidence_overwrite_candidate": 20}`
  - this hint is intentionally narrow: non-fixture rows only, feedback-import gate preserved, feedback timestamp at or before the pre-canonical row's `updated_at`, and no surviving explicit pre-canonical `gate_reason`
- direct local-provenance cleanup of the formerly unresolved bucket is now also visible in the same artifacts:
  - `local_provenance_hint_counts={"precanonical_explicit_gate_reason_preserved": 4, "test_fixture_row": 1}`
  - the same drift lane now distinguishes preserved pre-canonical explicit gate reasons from fixture/test rows using shared repo helpers instead of ad hoc shell inference

Interpretation:

- the remaining disagreement is mostly not about missing evidence; every residual drift row still has evidence text via `evidence_span`
- the dominant bucket is historical `APPROVED` rows that now sit in the current helper's mid-confidence band, which explains why bounded replay had to stop at partial ownership
- the two rows with explicit manual/human review reasons show that at least part of the residual bucket really is operator override rather than pure threshold drift
- the two rows with explicit confidence-threshold reasons show that a small part of the bucket also carries direct threshold-style provenance instead of pure inference
- the two `legacy_indexed_pending_review` rows show a separate legacy shape: rows whose gate decision is still pending but whose persisted status is already `INDEXED`
- the `22` rows with no surviving `gate_reason` remain the least explained subset; they are also the rows where row-level provenance is thinnest
- the universal `created_updated_differ` signal confirms that every residual row was mutated after creation, which is consistent with later repair/rewrite touch, but does not by itself prove why the decision stayed approved
- the exact confidence distribution sharpens that story further: `25/26` residual rows sit at exact `0.8`, not above it
- this matters because `scripts/migrate_legacy.py` is a real historical import path that could write `APPROVED` without `gate_reason`, but it uses `confidence > 0.8`. That makes it a poor direct explanation for most of this residual bucket
- the new migration evidence narrows one ambiguity substantially: for `25/26` residual rows, the current canonical `zotero:` id is not where the approved decision originated
- instead, those rows already existed in the pre-canonical backup DB under legacy unprefixed ids with the same `status`, `gate_decision`, and `confidence`; the later zotero-key migration preserved those decisions rather than creating them
- the only residual row without that direct migration match is `phase0_test`, which also remains the lone `0.95` outlier
- the new feedback-log evidence narrows the remaining ambiguity further:
  - `21` residual rows now show `feedback_import_gate_preserved_confidence_overwritten`, meaning the current `gate_decision` still matches the legacy feedback-import rule, but the current stored confidence no longer matches the original feedback average
  - `1` row (`kowalski...`) shows `feedback_import_gate_and_confidence_match`, which is exactly what the old feedback-import rule would predict for a preserved mid-band pending-review case
  - all `22` feedback-matched rows now also show `feedback_before_or_equal_created`, which means the legacy feedback record predates or exactly matches row creation time instead of being a later synthetic add-on
- the strongest evidence for a later rewrite step is now more specific than before:
  - `20` non-fixture rows now show `post_feedback_precanonical_confidence_overwrite_candidate`
  - for those rows, the legacy feedback record predates the pre-canonical row's `updated_at`, the stored decision still matches the feedback-import gate, the stored confidence no longer matches the original feedback average, and the pre-canonical row still has no explicit `gate_reason`
  - those `20` pre-canonical `updated_at` timestamps cluster on `2026-02-17`, which is the same calendar day the tracked `scripts/backfill_analysis.py` path first appears in git history
- a direct execution marker search narrowed the remaining uncertainty but did not fully close it:
  - no explicit Feb 17 backfill log, run report, or backup filename mentioning `backfill_analysis` was found under `storage/`, `logs/`, or `docs/archive/`
  - the `14` `logs/jobs/*.jsonl` files created on `2026-02-17` are generic step-progress traces without paper ids or backfill markers, so they do not directly explain the rewrite candidate bucket
  - `storage/batch_run.log` only shows the original Feb 13 DeepRead/bootstrap runs for papers such as `bialystok...`, `hansson...`, and `nyberg...`, not the later metadata-refresh step
  - `storage/zotero_export.json` is a same-day repository snapshot artifact (`mtime=2026-02-17 16:25 KST`, `53` exported items) and therefore consistent with a post-refresh state, but it does not carry runtime gate or `feedback_json` metadata and cannot directly prove which rewrite path executed
- the previously open `4 + 1` residual sub-bucket is now materially narrower:
  - the `4` `no_feedback_log_match` rows are no longer provenance-blind; each now shows `precanonical_explicit_gate_reason_preserved`, meaning the same explicit gate reason was already present in the pre-canonical Feb 23 backup row and survived into the current row
  - the lone `phase0_test` outlier now shows `test_fixture_row` via the shared `fixture_visibility` rule and also has a legacy feedback timestamp that predates row creation, which makes it a local fixture/test path rather than a product-runtime provenance gap
- taken together, the strongest repo-grounded explanation is now:
  - an early legacy feedback import created the original `gate_decision`
  - a later Feb 17-era metadata refresh rewrote `feedback_json` and `confidence` into tag-payload shape while leaving `gate_decision` intact for at least the `20` non-fixture rows now marked as rewrite candidates
  - a later Feb 23 canonical-id migration renamed those rows to `zotero:` ids without changing the already-stored decision
- a tracked `scripts/backfill_analysis.py` path from the same Feb 17 repo window now fits that rewrite candidate bucket more tightly than before: it updates `feedback_json`, `confidence`, and `summary` for `APPROVED/INDEXED` rows while preserving the stored decision columns, and its introduction date matches the dominant pre-canonical update cluster
- the remaining inference burden is now narrower than before:
  - whether the `20` non-fixture rewrite-candidate rows came from one exact execution of the tracked backfill script or from a neighboring local path with the same persistence shape
  - whether the lack of an explicit execution log means the rewrite happened from an unlogged local working copy shortly before the `14:09 KST` commit that introduced `scripts/backfill_analysis.py`
  - whether the remaining single non-fixture feedback-matched row with unchanged confidence (`kowalski...`) reflects a partial no-op pass or a separate adjacent path
- the old threshold explanation remains an inference, not a proven historical fact. Repo search found indirect hints of older threshold variants in other lanes, but the current strongest direct evidence now points more to feedback-import plus later metadata rewrite than to a pure threshold-rule change

Current operator flow for the processor-gate drift lane:

1. Generate a drift audit run:
   `.venv/bin/python scripts/eval/audit_processor_gate_replay_drift.py --run-id <drift_run_id>`
2. Read the emitted `summary.json` or `audit.md` first to confirm candidate count, drift rate, and dominant transition pattern.
3. Turn that drift summary into a bounded threshold review:
   `.venv/bin/python scripts/eval/recommend_processor_gate_threshold_review.py --drift-summary <summary_path> --run-id <review_run_id>`
4. Inspect the resulting advisory artifact with:
   `.venv/bin/paperpipe show-processor-gate-threshold-review <review_run_dir>`
5. Treat that threshold review as advisory evidence only. It is there to focus manual review, not to auto-change gate thresholds.

For operator/debug readability, the threshold-review script now also emits a compact stderr line while preserving its JSON stdout payload, for example:

- `review_ready=True action=manual_gate_threshold_review latest_run_status=warn threshold_change=blocked_policy_only candidate_count=54 drift_rate=0.4815 latest_run=processor_gate_replay_drift_new`

The older intake-override threshold review script now follows the same idea while preserving its simpler path-only stdout contract. It emits a compact stderr line such as:

- `review_ready=False action=hold_current_threshold latest_run_status=warn eligible_runs=1/3 provenance=synthetic latest_eligible=False latest_run=audit_latest`

Closeout decision:

- treat this replay-drift provenance lane as closed for now at a `best-supported, no direct execution marker found` posture
- do not widen the schema or artifact surface further unless a new local artifact, backup, or log appears that can directly identify the Feb 17 rewrite execution
- use the current v5 drift artifact as the durable baseline for any future reopen:
  - `feedback_log_import_hint_counts={"feedback_import_gate_preserved_confidence_overwritten": 21, "feedback_import_gate_and_confidence_match": 1, "no_feedback_log_match": 4}`
  - `feedback_log_to_precanonical_update_relation_counts={"feedback_before_or_equal_created": 22}`
  - `local_provenance_hint_counts={"precanonical_explicit_gate_reason_preserved": 4, "test_fixture_row": 1}`
  - `historical_rewrite_hint_counts={"post_feedback_precanonical_confidence_overwrite_candidate": 20}`
- the next useful product-quality work should move away from this provenance lane and back toward either parser-baseline hardening or a slot-classification goldset audit

## Fixture Cleanup Apply Follow-up

Applied maintenance artifacts:

- Runtime audit after cleanup:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_audits/intake_override_db_baseline_20260417_r4/intake_override_db_baseline_20260417_r4/summary.json)
- Coverage gate after cleanup:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/intake_override_coverage_gate/intake_override_db_coverage_gate_20260417_r3/summary.json)
- Readiness summary after cleanup:
  [summary.json](/Users/jangseongjin/paperpipe/snapshots/internal_data_readiness/internal_data_with_intake_override_gate_20260417_r4/summary.json)
- SQLite backup before cleanup:
  [state_before_fixture_paper_archive_20260417_164240.db](/Users/jangseongjin/paperpipe/storage/backups/state_before_fixture_paper_archive_20260417_164240.db)

Applied result on the current local runtime DB:

- `archived=11`
- `fixture_papers_archive_count=11`
- `document_count=54`
- `audited_document_count=54`
- `has_feedback_json_count=54`
- `no_feedback_json_count=0`
- `test_fixture_no_feedback_json_count=0`
- `non_fixture_no_feedback_json_count=0`
- `missing_intake_override_log_count=0`

Post-cleanup verification:

- a repeat dry-run now reports `fixture_no_feedback_candidates=0`
- the coverage gate still passes with `feedback_coverage_rate=1.0`
- the broader readiness summary still reports `classification_audit=bootstrap_ready`

Interpretation:

- the local runtime DB is now clean with respect to the previously identified fixture-only residual bucket
- cleanup did not degrade the intake-audit lane because all remaining rows are still auditable
- the backup plus archive-table pair makes this reversible if any local fixture row needs to be restored for debugging

## Relationship To Parser Baseline

This report does not replace the existing parser baseline.

Current parser evidence still lives in:

- [docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md](/Users/jangseongjin/paperpipe/docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md)
- [docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md](/Users/jangseongjin/paperpipe/docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md)

That parser lane already has bounded success/fidelity evidence.
The missing piece was intake-classification measurement, which this work adds.

## Verification

- `pytest -q tests/test_intake_override_audit.py tests/test_processor_institutional_proxy.py tests/test_watcher_issue_state.py`
- `pytest -q tests/test_processor_gate_integration.py tests/test_backfill_analysis.py tests/test_processor_institutional_proxy.py tests/test_watcher_issue_state.py`
- `pytest -q tests/test_intake_override_coverage_gate.py`
- `pytest -q tests/test_fixture_visibility.py tests/test_intake_override_audit.py tests/test_archive_fixture_no_feedback_papers.py`
- curated replay:
  `.venv/bin/python scripts/eval/audit_intake_override_logs.py --rows-jsonl tests/fixtures/intake_override_curated_replay_20260417.jsonl --run-id intake_override_curated_replay_20260417_r1`
- runtime DB replay:
  `.venv/bin/python scripts/eval/audit_intake_override_logs.py --run-id intake_override_db_baseline_20260417_r1`
- runtime log backfill:
  `PYTHONPATH=. .venv/bin/python scripts/backfill_analysis.py`
- runtime DB replay after backfill:
  `PYTHONPATH=. .venv/bin/python scripts/eval/audit_intake_override_logs.py --db-path storage/state.db --out-dir snapshots/intake_override_audits/intake_override_db_baseline_20260417_r2 --run-id intake_override_db_baseline_20260417_r2`
- fixture-aware runtime DB replay:
  `PYTHONPATH=. .venv/bin/python scripts/eval/audit_intake_override_logs.py --db-path storage/state.db --out-dir snapshots/intake_override_audits/intake_override_db_baseline_20260417_r3 --run-id intake_override_db_baseline_20260417_r3`
- advisory coverage gate:
  `python3 scripts/eval/check_intake_override_coverage_gate.py --audit-summary snapshots/intake_override_audits/intake_override_db_baseline_20260417_r2/intake_override_db_baseline_20260417_r2 --out-dir snapshots/intake_override_coverage_gate --run-id intake_override_db_coverage_gate_20260417_r1`
- internal data readiness with integrated intake coverage surface:
  `python3 scripts/eval/check_internal_data_readiness.py --run-id internal_data_with_intake_override_gate_20260417_r2 --out-dir snapshots/internal_data_readiness`
- backend smoke subset after CI wiring:
  `pytest -q tests/test_intake_override_coverage_gate.py tests/test_internal_data_readiness.py`
- backend smoke script after CI wiring:
  `./scripts/run_backend_api_smoke.sh`
- fixture cleanup dry-run:
  `PYTHONPATH=. .venv/bin/python scripts/archive_fixture_no_feedback_papers.py --db storage/state.db --sample 20`
- fixture cleanup apply:
  `PYTHONPATH=. .venv/bin/python scripts/archive_fixture_no_feedback_papers.py --db storage/state.db --apply --sample 20`
- runtime DB replay after fixture cleanup:
  `PYTHONPATH=. .venv/bin/python scripts/eval/audit_intake_override_logs.py --db-path storage/state.db --out-dir snapshots/intake_override_audits/intake_override_db_baseline_20260417_r4 --run-id intake_override_db_baseline_20260417_r4`
- advisory coverage gate after fixture cleanup:
  `python3 scripts/eval/check_intake_override_coverage_gate.py --audit-summary snapshots/intake_override_audits/intake_override_db_baseline_20260417_r4/intake_override_db_baseline_20260417_r4 --out-dir snapshots/intake_override_coverage_gate --run-id intake_override_db_coverage_gate_20260417_r3`
- internal data readiness after fixture cleanup:
  `python3 scripts/eval/check_internal_data_readiness.py --run-id internal_data_with_intake_override_gate_20260417_r4 --out-dir snapshots/internal_data_readiness`
- fixture cleanup CLI dry-run after exposure:
  `PYTHONPATH=. .venv/bin/python -m src.cli archive-fixture-no-feedback-papers --db storage/state.db`
- doctor/readiness owner coverage:
  `pytest -q tests/test_runtime_readiness_external_roots.py tests/test_cli_watch_commands.py tests/test_runtime_readiness_api.py tests/test_cli_self_test_command.py`
- live self-test check for fixture paper hygiene:
  `PYTHONPATH=. .venv/bin/python -m src.cli self-test --json | jq '.checks[] | select(.name=="fixture_paper_hygiene")'`
- producer ownership readiness snapshot:
  `python3 scripts/eval/check_internal_data_readiness.py --run-id internal_data_with_intake_override_producer_ownership_20260420_r1 --out-dir snapshots/internal_data_readiness`

## Current Judgment

The implementation baseline is now established for intake-classification auditing.

What is now true:

- there is a first-class audit lane for persisted intake override logs
- the lane works on curated replay input
- the lane now also works on real runtime DB state with non-zero audited coverage
- the legacy gate/backfill path can populate auditable runtime rows without requiring a rewrite of parser/classifier ownership
- there is now a small advisory gate that can detect when feedback-bearing rows lose intake override auditability again
- the broader internal-data readiness summary now includes that intake-override coverage signal as an explicit advisory surface
- the existing backend smoke CI lane now covers the new guard and readiness integration
- the remaining `no_feedback_json` bucket is now shown to be fixture-only on the current local runtime DB
- there is now a dry-run-first maintenance path to archive fixture-only `no_feedback_json` rows when local runtime hygiene matters
- that maintenance path has now been applied once to the current local runtime DB, and the residual bucket is reduced from `11` to `0`
- the same maintenance path is now exposed through the main CLI, not only through a standalone script
- `doctor` and runtime readiness now explicitly surface fixture paper cleanup drift and point to the cleanup command
- large fixture-paper drift now escalates `fixture_paper_hygiene` to `error` at `10+` candidates
- internal-data readiness now distinguishes repair-only intake log coverage from true runtime producer ownership

What is not yet true:

- this does not prove strong live classification accuracy on current runtime history
- this does not mean current runtime flows are already persisting the new log shape in enough volume for operational trend analysis without periodic maintenance
- future local runs can still reintroduce fixture/test rows, so cleanup remains a periodic hygiene action rather than a permanently enforced runtime invariant

## Next Safe Follow-up

1. Decide whether `processor_gate` or another active runtime path should become the primary producer instead of relying on `backfill_analysis` for legacy rows.
2. The `10`-candidate escalation threshold remains intentionally fixed until new operator evidence suggests otherwise.
3. If needed later, promote the advisory gate from smoke-test coverage into a dedicated required CI summary/report artifact.
