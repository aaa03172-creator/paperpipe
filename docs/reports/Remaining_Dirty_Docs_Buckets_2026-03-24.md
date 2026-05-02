# Remaining Dirty Docs Buckets (2026-03-24)

Status: Active packaging note  
Date: 2026-03-24  
Owner: Lattice runtime maintainers  
Related current posture:
- `docs/reports/Current_Docs_Posture_2026-04-17.md`
- `docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md`

## Purpose

Classify the remaining dirty docs into practical review buckets after the current canonical stale-wording cleanup.

This note does not open a new lane.

It answers a narrower question:
- when a dirty doc is still visible, what kind of doc is it, and should it travel with the default docs-only bundle or stay in a separate review bucket?

## 2026-04 usage note

This note remains useful as the late-March dirty-doc bucket map.

Use it for:
- historical bucket classification of the remaining late-March docs
- comparing older docs-only bundle assumptions with later posture cleanup
- review context when a dated doc still points back to the 2026-03 bucket model

Do not use it as the first current docs-posture entrypoint for later cleanup passes.

Read these first for current posture:
- `docs/reports/Current_Docs_Posture_2026-04-17.md`
- `docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md`
- `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`

## Current Judgment

The remaining dirty docs are not one class of work.

They currently split into:
1. active canonical/runtime docs
2. current posture and queue notes
3. release/readiness notes
4. lane-specific packaging or verification notes
5. other audits/reviews that should stay separate unless explicitly reviewed

The default docs-only pass may include buckets 1-4 when they are serving the current posture.
Bucket 5 should stay separate unless the user explicitly asks to review that audit material.

## A. Active Canonical / Runtime Docs

These are active canonical docs and should be treated as the highest-priority source docs when dirty:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/RESEARCH_DNA.md`
- `docs/WEB_VIEWER.md`
- `docs/MEETING_PACK.md`
- `docs/METHOD_COMPARISON.md`
- `docs/CHART_PACK.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/README.md`

Default handling:
- include in the docs-only bundle
- prefer narrow stale-wording or contract-alignment cleanup
- do not widen scope while touching them

## B. Current Posture / Queue Docs

These explain the current state, staging rule, and queue posture:
- `docs/Pending_PR_Queue.md`
- `docs/reports/README.md`
- `docs/reports/Current_State_Update_2026-03-24.md`
- `docs/reports/Current_State_Packaging_2026-03-24.md`
- `docs/reports/Current_State_Staging_Guide_2026-03-24.md`
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- `docs/reports/Canonical_Docs_Tail_Packaging_2026-03-24.md`
- `docs/reports/Deferred_Lanes_Recheck_2026-03-24.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
- `docs/reports/Local_Backup_Restore_Gate_2026-03-24.md`
- `docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md`
- `docs/reports/Docs_References_Implementation_Alignment_2026-03-24.md`

Default handling:
- include in the docs-only bundle when posture alignment is the task
- keep wording synchronized with the active canonical docs

## C. Release / Readiness Notes

These docs are still part of the current docs-only bundle, but they should be read as release-proof and acceptance notes rather than canonical contracts:
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md`
- `docs/reports/Deep_Read_Structured_State_Gap_2026-03-24.md`
- `docs/reports/Deep_Read_Note_State_Promotion_Design_2026-03-24.md`

Default handling:
- include when the task is about current product bar or launch readiness
- do not let them silently override canonical runtime docs

## D. Lane Packaging / Verification Notes

These are dirty docs that belong to a lane-specific packaging or verification frame:
- `docs/reports/Docling_Eval_Lane_Packaging_2026-03-24.md`
- `docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md`
- `docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md`
- `docs/reports/Frontend_Visual_Coverage_Lane_Packaging_2026-03-24.md`
- `docs/reports/Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`
- `docs/reports/Frontend_Backend_Visual_Coverage_Staging_Prep_2026-03-23.md`
- `docs/reports/Frontend_Backend_Visual_Coverage_Matrix_2026-03-24.md`
- `docs/reports/Frontend_Backend_Stale_Baseline_Audit_2026-03-24.md`
- `docs/reports/Frontend_Viewer_Shell_Staging_Prep_2026-03-20.md`
- `docs/UX_REVIEW_REPORT_chart-pack-viewer.md`
- `docs/UX_REVIEW_REPORT_meeting-pack-viewer.md`
- `docs/UX_REVIEW_REPORT_paper-notes-list.md`
- `docs/UX_REVIEW_REPORT_protocol-knowledge-inspector.md`
- `docs/UX_REVIEW_REPORT_workbench-persona-profile-split.md`
- `docs/reports/Teacher_Review_Spot_Check_Round_2026-03-23_Precheck.md`
- `docs/reports/Teacher_Review_Spot_Check_Major_Bundles_2026-03-23.md`

Default handling:
- keep separate unless the lane itself is being reviewed
- only the lane packaging and closeout posture notes belong in the default docs-state interpretation by default

## E. Other Audit / Review Material

These dirty docs are useful, but they should stay separate unless the user explicitly asks for those audits:
- `docs/reports/Acceptance_Proof_Drift_Review_2026-03-24.md`
- `docs/reports/Alignment_Midpoint_Checkpoint_2026-03-24.md`
- `docs/reports/Bounded_Lane_Terminology_Consistency_Review_2026-03-24.md`
- `docs/reports/Canonical_Owner_Drift_Review_2026-03-24.md`
- `docs/reports/Document_Overlap_Conflict_Map_2026-03-24.md`
- `docs/reports/Future_Lane_Leakage_Review_2026-03-24.md`
- `docs/reports/Readiness_Vocabulary_Drift_Review_2026-03-24.md`
- `docs/reports/State_vs_Artifact_Drift_Review_2026-03-24.md`
- `docs/reports/Viewer_Truth_Visibility_Drift_Review_2026-03-24.md`
- `docs/reports/Product_Document_Final_v2_Review_2026-03-24.md`
- `docs/archive/Prompt_Review_Parked_Useful_Items_2026-03-23.md`

Default handling:
- do not force these into the default docs-only pass
- treat them as explicit audit/review material

## Practical Rule

If a docs-only pass resumes now:
1. start with bucket A
2. keep bucket B aligned with A
3. use bucket C only when the task is current product bar/readiness
4. touch bucket D only when that lane is explicitly in review
5. leave bucket E parked unless requested

## Verification

Default verification for this note and any bucket-only docs cleanup:
- `python3 scripts/lint_docs.py`

## Relationship To Other Notes

- `docs/reports/Current_State_Packaging_2026-03-24.md` defines the higher-level split between docs, lanes, and generated artifacts
- `docs/reports/Current_State_Staging_Guide_2026-03-24.md` defines staging behavior
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md` defines the default action order
- this note classifies the remaining dirty docs inside that posture

## Conclusion

The remaining dirty docs should be read as buckets, not as one change.

The default move is still the docs-only bundle, but the docs-only bundle itself now has a practical internal order:
- active canonical docs first
- posture docs second
- release/readiness notes when relevant
- lane docs and other audits only by explicit choice
