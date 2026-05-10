# Docs Archive And Report Migration Staging Prep

Status: staging-prep manifest  
Date: 2026-03-20  
Lane: `docs-archive-and-report-migration`

## Purpose

Define the exact dirty subset for the docs archive and report migration lane so it can be staged without mixing feature/runtime work.

## Guardrail

Only stage files listed below. Do not pull in unrelated docs/spec/feature files from `docs/`, `frontend/`, `src/`, or `tests/`.

## Dirty Files In Scope

Total in-scope paths at capture time: `114`

- tracked deletions: `0`
- tracked modifications: `0`
- untracked additions: `89`

### Untracked additions

- `/Users/jangseongjin/paperpipe/docs/README.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Agent_Proposal_Fit_Review_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Codex_Hybrid_Working_Context.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Codex_Implementer_Packet_2026-02-17.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Deep_Read_Real_Quality_Check_Park_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Deep_Research_Integrated_Final_Design_2026-03-05.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Deep_Research_Report3_Fit_Review_2026-03-05.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Deep_Research_Report4_Fit_Review_2026-03-05.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Deep_Research_Report5_Fit_Review_2026-03-11.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Deep_Research_Reports_2_3_4_Fit_Review_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/External_Reference_Fit_Review_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Hold_Mode_Checklist_2026-02-20.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Image_Evidence_Viewer_Layer_RFC_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Image_Evidence_Viewer_v0_Implementation_Plan_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Local_Backup_and_Restore_Semantics_RFC_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Meeting_Pack_Fit_Review_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Meeting_Pack_Profile_Projection_Real_Probe_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Meeting_Pack_Real_Probe_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Meeting_Pack_V1_Checklist_Review_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Meeting_Pack_v1_Implementation_Plan_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Method_Comparison_Layer_RFC_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Method_Comparison_v0_Implementation_Plan_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Next_Feature_First_Batches_2026-02-19.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Next_Feature_Kickoff_Checklist_2026-02-19.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Obsidian_Index_PaperId_Normalization_2026-02-23.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Operational_Backfill_Outputs_2026-02-23.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Operational_Checkpoint_2026-02-23_Final.md`
- `/Users/jangseongjin/paperpipe/docs/archive/P2_PR1-PR3_PR_Descriptions_2026-02-19.md`
- `/Users/jangseongjin/paperpipe/docs/archive/P2_PR1-PR3_Review_Packet_2026-02-19.md`
- `/Users/jangseongjin/paperpipe/docs/archive/P2_PreFeature_Hardening_Execution_Plan_2026-02-19.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PR_Split_Plan_2026-02-17.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PaperPipe_Agent_Personas_Audit_2026-02-19.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PaperPipe_DeveloperKnowledge_MCP_Cost_Control_Proposal.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PaperPipe_Master_Spec_v2_1_reviewed.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PaperPipe_Vercel_React_Best_Practices_Proposal.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PaperPipe_v3_Gemini_DeepResearch_Proposal.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Paper_Notes_Workbench_Midpoint_Checkpoint_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Phase2_Start_Snapshot_2026-02-21.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Phase3_FixPack_Workbench_EvidenceLinking_Adapted_2026-02-26.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PostMerge_Operations_Note_2026-02-19.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Project_Memory_Layer_RFC_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Prompt_Review_01_Autoresearch_Search_2026-03-11.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Prompt_Review_02_Auton_Agentic_P0_2026-03-11.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Prompt_Review_03_Fireauto_2026-03-11.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Prompt_Review_04_DeerFlow_2026-03-11.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Prompt_Review_05_Research_DNA_2026-03-11.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Prompt_Review_Integrated_Priority_2026-03-11.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Proposal_to_Lattice_Mapping_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Protocol_Knowledge_Layer_RFC_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/README.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_Bounded_External_Benchmark_Policy_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_External_Benchmark_Breadth_Followup_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_External_Benchmark_Candidate_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_External_Benchmark_Promotion_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_External_Benchmark_Subset_Eval_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_Goldset_Sanity_Followup_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_Real_Pilot_Probe_2026-03-12.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_Real_Profile_Projection_Validation_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_DNA_v0_Implementation_Plan_2026-03-11.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_Data_Visualization_Layer_RFC_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Research_Data_Visualization_v0_Implementation_Plan_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Soft_Gate_Reintroduction_Checklist_2026-03-06.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Teacher_Quality_Loop_Baseline_Compare_2026-03-10.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Teacher_Quality_Loop_Baseline_Regression_Batch_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Teacher_Quality_Loop_Natural_Quarantine_Probe_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Teacher_Quality_Loop_Quarantine_Review_Drill_2026-03-09.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Teacher_Quality_Loop_Real_Output_Probe_2026-03-09.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Teacher_Quality_Loop_Smoke_2026-02-24.md`
- `/Users/jangseongjin/paperpipe/docs/archive/engineering_health_2026-02-21.md`
- `/Users/jangseongjin/paperpipe/docs/archive/institutional_access_execution_plan_2026-02-21.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06.json`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06_30_fast.json`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06_30_fast.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06_30_full_timeout.json`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06_30_full_timeout.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-07_30_full_timeout.json`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-07_30_full_timeout.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-08_30_full_timeout_adaptive_tuned.json`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-08_30_full_timeout_adaptive_tuned.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-09_30_full_timeout_adaptive_precise_v5.json`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-09_30_full_timeout_adaptive_precise_v5.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-09_30_full_timeout_adaptive_precise_v6.json`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-09_30_full_timeout_adaptive_precise_v6.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Reader_Audit_2026-03-07_30.json`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Reader_Audit_2026-03-07_30.md`
- `/Users/jangseongjin/paperpipe/docs/reports/release_notes_2026-02-21_watcher_qa.md`
- `/Users/jangseongjin/paperpipe/docs/reports/release_notes_2026-02-25_ui_mock_test_stability.md`
- `/Users/jangseongjin/paperpipe/docs/working-files.md`

## Intent

This lane appears to do three things:

1. move legacy documents under `/docs/archive/`
2. move older validation/release-note outputs under `/docs/reports/`
3. add a lightweight `docs` index/readme layer

## Verification

This lane is docs-only. The expected verification is:

1. `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`
2. spot-check that deleted root docs have matching archive destinations where intended
3. confirm no runtime or frontend files enter the index

## Explicit Exclusions

- `/Users/jangseongjin/paperpipe/docs/reports/Memory_Ready_Hardening_Baseline_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Current_Baseline_Recheck_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_*` outside archive migration intent
- any `frontend/`, `src/`, `backend/`, `tests/`, `.github/`, `scripts/` paths

## Safe Next Git Step

If this lane is staged later, do it in this order:

1. tracked deletions
2. matching `docs/archive/` additions
3. `docs/reports/` migrated outputs
4. `docs/README.md` and `docs/working-files.md`

Stop after each pass and inspect `git diff --cached --name-only`.
