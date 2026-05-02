# Current State Staging Guide (2026-03-24)

Status: Active staging guide
Date: 2026-03-24
Owner: Lattice runtime maintainers
Related current posture:
- `docs/reports/Current_Docs_Posture_2026-04-17.md`
- `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`

## Purpose

Translate the current packaging notes into a practical staging guide for the mixed dirty tree.

This note is not a roadmap.
This note is not a commit plan that must be executed as-is.

Its purpose is to show:
- what may be staged together safely
- what should stay in separate source lanes
- what should not be staged as source changes at all

## 2026-04 usage note

This guide remains useful as the late-March staging guide for that mixed-tree snapshot.

Use it for:
- the original docs-tail / eval-lane / visual-lane staging split
- reviewing how the late-March dirty tree was meant to be staged safely
- historical context when comparing newer lane-triage decisions against the earlier staging model

Do not use it as the first current staging or lane-selection entrypoint for the later repo state.

Read these first for current posture:
- `docs/reports/Current_Docs_Posture_2026-04-17.md`
- `docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md`
- `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`

## Current Staging Rule

Do not treat the current dirty tree as one bundle.

Before staging anything, classify each path into one of these buckets:
1. canonical/docs state tail
2. Docling / ingest-eval / teacher-review evaluation lane
3. frontend visual-coverage verification lane
4. generated/runtime artifacts
5. unrelated or not-yet-packaged planning tail

## A. Safe Staging Unit: canonical/docs state tail

These paths may be reviewed together as the current state/docs tail:
- `docs/API_CHAT_CONTRACT.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/CHART_PACK.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/MEETING_PACK.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/RESEARCH_DNA.md`
- `docs/WEB_VIEWER.md`
- `docs/README.md`
- `docs/reports/README.md`
- `docs/METHOD_COMPARISON.md`
- `docs/Product_Positioning_Principles.md`
- `docs/Pending_PR_Queue.md`
- `docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md`
- `docs/reports/Docs_References_Implementation_Alignment_2026-03-24.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/reports/Canonical_Docs_Tail_Packaging_2026-03-24.md`
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- `docs/reports/Current_State_Packaging_2026-03-24.md`
- `docs/reports/Current_State_Staging_Guide_2026-03-24.md`
- `docs/reports/Current_State_Update_2026-03-24.md`
- `docs/reports/Deferred_Lanes_Recheck_2026-03-24.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
- `docs/reports/Frontend_Visual_Coverage_Lane_Packaging_2026-03-24.md`
- `docs/reports/Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`
- `docs/reports/Docling_Eval_Lane_Packaging_2026-03-24.md`
- `docs/reports/Local_Backup_Restore_Gate_2026-03-24.md`

Why this unit is safe:
- these files update current-state interpretation and queue posture
- they do not require runtime code review
- they define the separation boundary for the rest of the dirty tree

Default bundle note:
- use `docs/reports/Canonical_Docs_Tail_Packaging_2026-03-24.md` if a default docs-only bundle is needed

## B. Safe Staging Unit: Docling / ingest-eval / teacher-review lane

These paths belong together as a bounded evaluation lane:
- `docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md`
- `docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md`
- `docs/reports/Teacher_Review_Spot_Check_Round_2026-03-23_Precheck.md`
- `docs/reports/Teacher_Review_Spot_Check_Major_Bundles_2026-03-23.md`
- `docs/reports/Teacher_Review_Eval_Sidecar_Round1_2026-03-24.md`
- `docs/reports/Teacher_Review_Precision_Followup_2026-03-24.md`
- `scripts/bootstrap.py`
- `src/services/cli_workflows.py`
- `scripts/eval/audit_section_quality.py`
- `scripts/eval/audit_table_merge_semantics.py`
- `tests/test_section_quality_audit.py`
- `tests/test_table_merge_audit.py`

Guide:
- stage these only if the goal is to review the evaluation lane itself
- do not mix them with active bounded-spec docs promotion work
- do not stage them together with frontend visual snapshots

## C. Safe Staging Unit: frontend visual-coverage lane

These paths belong together as a verification-only lane:
- `frontend/e2e/visual-backend.backend.spec.ts`
- snapshot files under `frontend/e2e/visual-backend.backend.spec.ts-snapshots/`
- `docs/UX_REVIEW_REPORT_chart-pack-viewer.md`
- `docs/UX_REVIEW_REPORT_meeting-pack-viewer.md`
- `docs/UX_REVIEW_REPORT_paper-notes-list.md`
- `docs/UX_REVIEW_REPORT_protocol-knowledge-inspector.md`
- `docs/UX_REVIEW_REPORT_workbench-persona-profile-split.md`
- `docs/reports/Frontend_Backend_Visual_Coverage_Staging_Prep_2026-03-23.md`
- `docs/reports/Frontend_Backend_Visual_Coverage_Matrix_2026-03-24.md`
- `docs/reports/Frontend_Backend_Stale_Baseline_Audit_2026-03-24.md`
- `docs/reports/Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`
- `docs/reports/Frontend_Viewer_Shell_Staging_Prep_2026-03-20.md`

Guide:
- stage these only as a verification lane
- treat snapshot files as part of the verification contract for this lane
- do not treat this lane as a runtime/product redesign bundle
- treat the lane as closed after packaging unless a route regresses or a new shell lacks coverage

## D. Do not stage as canonical source changes

These paths should normally stay out of source-oriented staging bundles:
- `storage/meeting_packs/`
- `storage/method_comparisons/`
- `storage/obsidian/`
- `storage/search_eval/`
- `snapshots/ingest_backend_eval/`
- `.omx/`
- `.serena/`

Why:
- they are generated artifacts, runtime state, or local-tool state
- they may be useful for local verification, but they should not be used to define the source lane boundary

## E. Keep separate until explicitly reopened

These paths are visible in the dirty tree but are not covered by the current packaged lanes:
- `docs/archive/Prompt_Review_Parked_Useful_Items_2026-03-23.md`
- `docs/reports/Product_Document_Final_v2_Review_2026-03-24.md`

Guide:
- do not force these into the current docs-state bundle
- treat them as separate planning/review material unless a later note explicitly packages them

## Practical Staging Order

If actual staging begins, the safest order is:
1. stage the canonical/docs state tail first
2. stage the Docling/eval lane only if that lane is being reviewed on its own
3. stage the frontend visual lane only if that lane is being reviewed on its own
4. leave generated/runtime artifacts unstaged unless a very specific evidence handoff requires them

## Explicit Non-Recommendations

Do not do these:
- do not stage docs-state, Docling/eval, and visual-snapshot files as one bundle
- do not treat `storage/` and `snapshots/` as ordinary source files
- do not reopen deferred lanes from staging momentum alone
- do not force unrelated planning docs into the current state bundle just because they are dirty

## Relationship To Current Notes

- `docs/reports/Current_State_Packaging_2026-03-24.md` explains the separation logic
- `docs/reports/Current_State_Update_2026-03-24.md` explains the current posture
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md` explains the default next-action order
- `docs/reports/Canonical_Docs_Tail_Packaging_2026-03-24.md` defines the default docs-only bundle
- this note turns those two notes into a staging-oriented guide

## Conclusion

The current repo does not need another feature lane.

It needs disciplined staging:
- keep source lanes separate
- keep generated artifacts out
- keep unrelated planning tails parked
