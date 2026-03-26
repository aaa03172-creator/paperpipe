# Docling Eval Lane Packaging (2026-03-24)

Status: Active packaging note
Date: 2026-03-24
Owner: Lattice runtime maintainers
Canonical: `docs/reports/Docling_Eval_Lane_Packaging_2026-03-24.md`

## Purpose

Package the current Docling / ingest-eval / teacher-review dirty tail as one bounded evaluation lane.

This note is not a parser-adoption approval.
This note is not a new product/runtime roadmap.

Its job is to keep the current evaluation work separate from:
- the active bounded-spec docs tail
- frontend visual-coverage hardening
- generated snapshots and runtime artifacts

## Current Judgment

The current Docling / ingest-eval / teacher-review tail should be treated as:
- a bounded evaluation lane
- an optional pilot / sidecar lane
- not ready for default runtime adoption

Why:
- `docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md` already classifies Docling as a behind-flag optional parser pilot candidate
- `docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md` now carries the stronger `r11` expanded rerun plus `r12` and `r13` audits
- the teacher-review work is additive precision/eval-sidecar work, not a broad runtime rewrite

## Included Source Tail

### A. Docling parser-eval and intake docs

- `docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md`
- `docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md`
- `docs/reports/Docling_Hybrid_Core_Staging_Prep_2026-03-23.md`
- `docs/reports/Docling_Hybrid_Evidence_Bundle_Staging_Prep_2026-03-23.md`
- `docs/reports/Docling_Parser_Eval_Core_Staging_Prep_2026-03-23.md`
- `docs/reports/Docling_Pilot_Artifacts_Staging_Prep_2026-03-23.md`
- `docs/reports/Parser_Backends_Docling_Doi_Fallback_Staging_Prep_2026-03-23.md`

Interpretation:
- these files belong together as the parser-eval and tool-intake narrative
- they support a bounded optional pilot story, not a default-backend switch

### B. Teacher-review eval and anchor-quality docs

- `docs/reports/Teacher_Review_Spot_Check_Round_2026-03-23_Precheck.md`
- `docs/reports/Teacher_Review_Spot_Check_Major_Bundles_2026-03-23.md`
- `docs/reports/Teacher_Review_Eval_Sidecar_Round1_2026-03-24.md`
- `docs/reports/Teacher_Review_Precision_Followup_2026-03-24.md`
- `docs/reports/Teacher_Review_Anchor_Quality_Replay_2026-03-24.md`
- `docs/reports/Teacher_Review_Anchor_Quality_Full_Replay_2026-03-24.md`
- `docs/reports/Teacher_Review_Anchor_Quality_Extended_Replay_2026-03-24.md`

Interpretation:
- these files are bounded evaluation reports for teacher-review precision
- they should remain sidecar-style quality work, not be confused with a new product surface

### C. Supporting code and test tail

- `scripts/bootstrap.py`
- `src/services/cli_workflows.py`
- `scripts/eval/audit_table_merge_semantics.py`
- `scripts/eval/audit_section_quality.py`
- `src/schemas/teacher_review_eval.py`
- `src/services/teacher_review_eval_sidecar.py`
- `tests/test_table_merge_audit.py`
- `tests/test_section_quality_audit.py`
- `tests/test_teacher_review_eval_sidecar.py`

Interpretation:
- these changes support the bounded evaluation lane operationally
- they do not by themselves justify default parser adoption or a broader runtime redesign
- `scripts/bootstrap.py` and `src/services/cli_workflows.py` should be read as supporting operational/eval plumbing, not as a new product lane

## Explicit Exclusions

Do not treat these as part of the canonical source package for this lane:
- `snapshots/ingest_backend_eval/`
- `storage/`
- `goldset/reviews/spot_checks/teacher_review_spot_check_20260323_round1_codex_precheck.jsonl`
- frontend visual-snapshot files under `frontend/e2e/visual-backend.backend.spec.ts-snapshots/`
- active bounded-spec docs such as `docs/METHOD_COMPARISON.md`, `docs/CHART_PACK.md`, `docs/PROTOCOL_KNOWLEDGE.md`, and `docs/IMAGE_EVIDENCE.md`

Why:
- they are generated evidence, runtime state, or a different lane entirely
- they can still be referenced as validation artifacts, but they should not drive the packaging boundary

## Current Recommendation

Read this lane with the following contract:
1. Docling remains a behind-flag optional parser pilot candidate.
2. Teacher-review work remains additive precision and sidecar evaluation work.
3. The current parser stack remains the runtime owner.
4. Promotion requires new evidence, not just more packaging.

## Reopen Conditions

Only revisit the “default runtime adoption” question if one of these changes materially:
- fallback frequency rises or falls enough to alter the current risk judgment
- same-page merged tables stop preserving normalized content
- section-quality review buckets show broad page-loss or collapse patterns
- teacher-review sidecar results justify a stricter or broader acceptance contract

Without that evidence, keep this lane bounded.

## Relationship To Current State Notes

- `docs/reports/Current_State_Packaging_2026-03-24.md` remains the top-level mixed-worktree separation note
- this note is the lane-specific packaging summary for the Docling / ingest-eval / teacher-review tail
- `docs/reports/Current_State_Update_2026-03-24.md` should now treat this packaging step as completed

## Conclusion

The right reading of the current Docling / ingest-eval / teacher-review tail is:
- real work
- worth preserving
- still bounded
- still evaluation-first
- not a silent runtime-default migration
