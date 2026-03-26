# Docs Demo Microtail Staging Prep

Date: 2026-03-27
Status: Ready for isolated docs-only packaging
Owner: Runtime/product maintainers

## Goal

Close the remaining docs-only micro-tail that sharpens first-product demo messaging, release rehearsal evidence, and drift-review notes without pulling runtime or frontend code lanes back into scope.

## Include

Tracked updates:
- `README.md`
- `docs/README.md`
- `docs/archive/README.md`

Untracked docs:
- `docs/archive/Feynman_Workflow_Messaging_Review_Prompt_2026-03-27.md`
- `docs/archive/Prompt_Review_Parked_Useful_Items_2026-03-23.md`
- `docs/reports/Acceptance_Proof_Drift_Review_2026-03-24.md`
- `docs/reports/Alignment_Midpoint_Checkpoint_2026-03-24.md`
- `docs/reports/Bounded_Lane_Terminology_Consistency_Review_2026-03-24.md`
- `docs/reports/Canonical_Objects_Scope_Cut_And_Supported_Journey_2026-03-24.md`
- `docs/reports/Canonical_Owner_Drift_Review_2026-03-24.md`
- `docs/reports/Deep_Read_Legacy_Bundle_Release_Boundary_2026-03-25.md`
- `docs/reports/Deep_Read_Note_State_Promotion_Design_2026-03-24.md`
- `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md`
- `docs/reports/Deep_Read_Structured_State_Gap_2026-03-24.md`
- `docs/reports/Docs_Only_Cleanup_Closeout_2026-03-25.md`
- `docs/reports/Document_Overlap_Conflict_Map_2026-03-24.md`
- `docs/reports/Feynman_Workflow_Messaging_Fit_Review_2026-03-27.md`
- `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
- `docs/reports/First_Product_Demo_FAQ_2026-03-27.md`
- `docs/reports/First_Product_Demo_Runbook_2026-03-27.md`
- `docs/reports/First_Product_Demo_Script_3min_2026-03-27.md`
- `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md`
- `docs/reports/Future_Lane_Leakage_Review_2026-03-24.md`
- `docs/reports/PaperPipe_Minimum_Operating_Principles_2026-03-25.md`
- `docs/reports/Product_Document_Final_v2_Review_2026-03-24.md`
- `docs/reports/Readiness_Vocabulary_Drift_Review_2026-03-24.md`
- `docs/reports/Release_Rehearsal_Checklist_2026-03-25.md`
- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`
- `docs/reports/Remaining_Dirty_Docs_Buckets_2026-03-24.md`
- `docs/reports/State_vs_Artifact_Drift_Review_2026-03-24.md`
- `docs/reports/Teacher_Review_Spot_Check_Major_Bundles_2026-03-23.md`
- `docs/reports/Teacher_Review_Spot_Check_Round_2026-03-23_Precheck.md`
- `docs/reports/Viewer_Truth_Visibility_Drift_Review_2026-03-24.md`

This staging prep note:
- `docs/reports/Docs_Demo_Microtail_Staging_Prep_2026-03-27.md`

## Exclude

Code/runtime lanes:
- `backend/services/job_runner.py`
- `src/agents/deep_reader.py`
- `src/agents/profile_chat_agent.py`
- `src/agents/reader_agent.py`
- `src/cli.py`
- `tests/test_librarian_advanced.py`
- `tests/test_paper_notes_api.py`
- `tests/test_reader_agent_reliability.py`

Frontend/backend visual/runtime harness lanes:
- `frontend/README.md`
- `.omx/`
- `.serena/`
- `storage/meeting_packs/`
- `storage/method_comparisons/`
- `storage/obsidian/`
- `storage/search_eval/`

Other eval/provider follow-ups:
- `scripts/eval/compare_extraction_outputs.py`
- `tests/test_extraction_regression_eval.py`
- `tests/test_ollama_provider_timeout.py`

## Verification

Current worktree:
- `python3 scripts/lint_docs.py`

Clean temp closure:
- apply only the included docs bundle onto `HEAD`
- `python3 scripts/lint_docs.py`

## Commit Message

`docs(product): add first-product demo and drift review bundle`
