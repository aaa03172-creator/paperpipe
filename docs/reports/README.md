# Reports Index

Status: Active  
Date: 2026-03-09  
Owner: Repository maintainers  
Canonical: `docs/reports/README.md`

This directory stores dated evidence outputs and operational records rather than normative specs.

## Contents
- `Local_Batch_Validation_*.md` / `.json`
- `Local_Reader_Audit_*.md` / `.json`
- `release_notes_*.md`
- temporary local validation artifacts such as `tmp_*.md` / `.json`
- current-state and posture notes such as:
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
  - `Docling_Tool_Intake_Decision_2026-03-23.md`
  - `Ingest_Backend_Docling_Pilot_2026-03-23.md`
  - `Hard_PDF_Evaluation_Slice_2026-04-01.md`
  - `PaddleOCR_Fallback_Pilot_2026-04-01.md`
  - `Reader_Attempt_Order_Reopen_Check_2026-04-01.md`
  - `DeepRead_Context_Manifest_Artifact_2026-04-01.md`
  - `Teacher_Review_Eval_Sidecar_Round1_2026-03-24.md`

## Rules
- Keep filenames dated or explicitly temporary.
- Do not cite files here as product/runtime SSOT.
- Treat current-state and packaging reports here as operational posture notes, not as replacement runtime specs.
- If a report becomes an enduring runbook or contract, promote its conclusions into a canonical doc under `docs/`.
