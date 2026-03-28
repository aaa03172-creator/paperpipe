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
  - `Current_Baseline_Recheck_2026-03-18.md`
  - `Deferred_Lanes_Recheck_2026-03-24.md`
  - `Docs_Only_Cleanup_Closeout_2026-03-25.md`
  - `Release_Rehearsal_Run_2026-03-25.md`
  - `Installability_Audit_2026-03-27.md`
- lane-specific packaging and staging notes such as:
  - `Backend_API_PR_Packaging_2026-03-18.md`
  - `Committed_Backend_API_Stack_Summary_2026-03-18.md`
  - `Deepread_Handoff_Artifacts_Closeout_2026-03-28.md`
  - `Deepread_Runtime_Followups_Closeout_2026-03-28.md`
  - `Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`
  - `Profiles_Yaml_Research_DNA_Snapshot_Staging_Prep_2026-03-23.md`
  - `Docling_Eval_Artifacts_Staging_Prep_2026-03-27.md`
- verification and drift audit notes such as:
  - `Acceptance_Proof_Drift_Review_2026-03-24.md`
  - `Frontend_Backend_Stale_Baseline_Audit_2026-03-24.md`
  - `Viewer_Truth_Visibility_Drift_Review_2026-03-24.md`
- bounded evaluation reports such as:
  - `Docling_Tool_Intake_Decision_2026-03-23.md`
  - `Ingest_Backend_Docling_Pilot_2026-03-23.md`
  - `OpenDataLoader_Sidecar_First_Run_2026-03-27.md`
  - `OpenDataLoader_Sidecar_Inspection_2026-03-27.md`

## Rules
- Keep filenames dated or explicitly temporary.
- Do not cite files here as product/runtime SSOT.
- Treat current-state and packaging reports here as operational posture notes, not as replacement runtime specs.
- If a report becomes an enduring runbook or contract, promote its conclusions into a canonical doc under `docs/`.
