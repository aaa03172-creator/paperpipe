# Reports Index

Status: Active  
Date: 2026-03-09  
Owner: Repository maintainers  
Canonical: `docs/reports/README.md`

This directory stores dated evidence outputs and operational records rather than normative specs.

## Recommended Current Reading Order

If you are trying to understand the current repo posture from inside `docs/reports/`, start here:

1. `Current_Docs_Posture_2026-04-17.md`
   - Current reading-order note for the mixed repo state.
2. `Current_Worktree_Lane_Triage_2026-04-07.md`
   - Current lane split for the mixed dirty tree.
3. `Runtime_Readiness_Lane_Packaging_2026-04-07.md`
   - Current runtime-readiness/installability packaging split.

Then use the older 2026-03 notes only as baseline, release-gate, or packaging context.

## Contents
- `Local_Batch_Validation_*.md` / `.json`
- `Local_Reader_Audit_*.md` / `.json`
- `release_notes_*.md`
- temporary local validation artifacts such as `tmp_*.md` / `.json`
- current-state and posture notes such as:
  - `Current_Docs_Posture_2026-04-17.md`
  - `Current_Worktree_Lane_Triage_2026-04-07.md`
  - `Runtime_Readiness_Lane_Packaging_2026-04-07.md`
  - `Current_State_Update_2026-03-24.md`
  - `Current_State_Packaging_2026-03-24.md`
  - `Current_State_Staging_Guide_2026-03-24.md`
  - `Current_Concrete_Next_Actions_2026-03-24.md`
  - `External_Reference_Action_Order_2026-04-01.md`
  - `External_Reference_Followups_Closeout_2026-04-01.md`
  - `Canonical_Docs_Tail_Packaging_2026-03-24.md`
  - `Remaining_Dirty_Docs_Buckets_2026-03-24.md`
  - `Docs_Only_Cleanup_Closeout_2026-03-25.md`
- lane-specific packaging notes such as:
  - `Docling_Eval_Lane_Packaging_2026-03-24.md`
  - `External_Reference_Lane_Packaging_2026-04-01.md`
  - `External_Reference_Lane_Stage_Set_2026-04-02.md`
  - `Frontend_Visual_Coverage_Lane_Packaging_2026-03-24.md`
  - `Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`
- verification matrix and audit notes such as:
  - `Frontend_Backend_Visual_Coverage_Matrix_2026-03-24.md`
  - `Frontend_Backend_Stale_Baseline_Audit_2026-03-24.md`
- bounded evaluation reports such as:
  - `Slot_Classification_Prompt_Candidate_Boundary_Clarification_2026-04-24.md`
  - `Slot_Classification_Runtime_Boundary_Clarification_Patch_2026-04-24.md`
  - `Slot_Classification_Post_Promotion_Stability_2026-04-25.md`
  - `Slot_Classification_Review_Resource_Boundary_Companion_2026-04-26.md`
  - `Slot_Classification_Prompt_Candidate_Review_Checklist_2026-04-24.md`
  - `Slot_Classification_Hard_Case_Adjudication_Rule_2026-04-24.md`
  - `Slot_Classification_Rerun_Stability_Followup_2026-04-24.md`
  - `Slot_Classification_Tuning_Advisory_Hold_Runbook_2026-04-24.md`
  - `Processor_Gate_Excluded_Bucket_Policy_Runbook_2026-04-23.md`
  - `Processor_Gate_Mid_Confidence_Policy_Debt_Runbook_2026-04-23.md`
  - `Docling_Tool_Intake_Decision_2026-03-23.md`
  - `Ingest_Backend_Docling_Pilot_2026-03-23.md`
  - `Hard_PDF_Evaluation_Slice_2026-04-01.md`
  - `PaddleOCR_Fallback_Pilot_2026-04-01.md`
  - `Reader_Attempt_Order_Reopen_Check_2026-04-01.md`
  - `DeepRead_Context_Manifest_Artifact_2026-04-01.md`
  - `DeepRead_Handoff_Baseline_Compare_2026-04-08.md`
  - `DeepRead_Handoff_Backfill_Refresh_2026-04-08.md`
  - `DeepRead_Handoff_Multicase_Baseline_2026-04-08.md`
  - `Teacher_Review_Eval_Sidecar_Round1_2026-03-24.md`

## Rules
- Keep filenames dated or explicitly temporary.
- Do not cite files here as product/runtime SSOT.
- Treat current-state and packaging reports here as operational posture notes, not as replacement runtime specs.
- If a report becomes an enduring runbook or contract, promote its conclusions into a canonical doc under `docs/`.
- Recent example:
  - `docs/reports/PaperPipe_Minimum_Operating_Principles_2026-03-25.md` was promoted into `docs/PaperPipe_Minimum_Operating_Principles.md` and the dated path was retained only as a retired compatibility stub.
