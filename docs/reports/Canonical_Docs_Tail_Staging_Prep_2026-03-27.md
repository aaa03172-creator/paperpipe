# Canonical Docs Tail Staging Prep (2026-03-27)

## Goal
- Close the current docs-only canonical tail without mixing runtime, frontend verification, or eval lanes.

## Include
- `/Users/jangseongjin/paperpipe/docs/API_CHAT_CONTRACT.md`
- `/Users/jangseongjin/paperpipe/docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `/Users/jangseongjin/paperpipe/docs/CHART_PACK.md`
- `/Users/jangseongjin/paperpipe/docs/Evidence_and_Uncertainty_Rules.md`
- `/Users/jangseongjin/paperpipe/docs/IMAGE_EVIDENCE.md`
- `/Users/jangseongjin/paperpipe/docs/Lattice_v3_Master_Spec.md`
- `/Users/jangseongjin/paperpipe/docs/MEETING_PACK.md`
- `/Users/jangseongjin/paperpipe/docs/METHOD_COMPARISON.md`
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`
- `/Users/jangseongjin/paperpipe/docs/PROTOCOL_KNOWLEDGE.md`
- `/Users/jangseongjin/paperpipe/docs/Product_Positioning_Principles.md`
- `/Users/jangseongjin/paperpipe/docs/README.md`
- `/Users/jangseongjin/paperpipe/docs/RESEARCH_DNA.md`
- `/Users/jangseongjin/paperpipe/docs/reports/README.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Canonical_Docs_Tail_Packaging_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Current_State_Packaging_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Current_State_Staging_Guide_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Current_State_Update_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Deferred_Lanes_Recheck_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Docs_References_Implementation_Alignment_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Docling_Eval_Lane_Packaging_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Frontend_Visual_Coverage_Lane_Packaging_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Local_Backup_Restore_Gate_2026-03-24.md`

## Exclude
- `/Users/jangseongjin/paperpipe/frontend/*`
- `/Users/jangseongjin/paperpipe/scripts/bootstrap.py`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- `/Users/jangseongjin/paperpipe/scripts/eval/*`
- `/Users/jangseongjin/paperpipe/storage/*`
- `/Users/jangseongjin/paperpipe/snapshots/*`
- dated review/parking notes not listed above

## Verification
- `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`
- clean temp worktree closure:
  - copy staged docs bundle only
  - rerun docs lint

## Notes
- This docs tail intentionally keeps `Docling` and `frontend visual coverage` as referenced packaged lanes, not reopened code lanes.
- `frontend/README.md` remains excluded because it is not part of the canonical docs tail described in the 2026-03-24 packaging notes.
