# Canonical Docs Tail Packaging (2026-03-24)

Status: Active packaging note
Date: 2026-03-24
Owner: Lattice runtime maintainers
Related current posture:
- `docs/reports/Current_Docs_Posture_2026-04-17.md`
- `docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md`

## Purpose

Define the default source-only bundle for the current mixed dirty tree.

This note is intentionally narrower than the full staging guide.
It exists so the default first move is explicit:
- if work resumes and no other lane is explicitly chosen, use this docs tail

## 2026-04 usage note

This note remains useful as the default docs-tail packaging rule for the late-March snapshot.

Use it for:
- understanding what the original default docs-only bundle included
- historical review of the first docs-tail packaging pass
- comparing later docs-entrypoint cleanup against the earlier bundle shape

Do not use it as the first current packaging note for the later repo state.

Read these first for current posture:
- `docs/reports/Current_Docs_Posture_2026-04-17.md`
- `docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md`
- `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`

## Current Judgment

The canonical/docs tail is the only default source bundle right now.

Why:
- it captures the current repo posture
- it does not require runtime code review
- it keeps the lane-packaging notes and queue posture aligned

## Default Bundle Shape

Stage or review these files together by default:
- `docs/API_CHAT_CONTRACT.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/CHART_PACK.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/MEETING_PACK.md`
- `docs/METHOD_COMPARISON.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/Product_Positioning_Principles.md`
- `docs/RESEARCH_DNA.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/WEB_VIEWER.md`
- `docs/README.md`
- `docs/reports/README.md`
- `docs/Pending_PR_Queue.md`
- `docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md`
- `docs/reports/Docs_References_Implementation_Alignment_2026-03-24.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/reports/Current_State_Packaging_2026-03-24.md`
- `docs/reports/Current_State_Update_2026-03-24.md`
- `docs/reports/Current_State_Staging_Guide_2026-03-24.md`
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- `docs/reports/Canonical_Docs_Tail_Packaging_2026-03-24.md`
- `docs/reports/Deferred_Lanes_Recheck_2026-03-24.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
- `docs/reports/Docling_Eval_Lane_Packaging_2026-03-24.md`
- `docs/reports/Frontend_Visual_Coverage_Lane_Packaging_2026-03-24.md`
- `docs/reports/Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`
- `docs/reports/Local_Backup_Restore_Gate_2026-03-24.md`

## Explicit Exclusions

Do not pull these into the default docs bundle:
- Docling / ingest-eval / teacher-review implementation/eval files beyond the lane packaging note
- frontend visual-coverage verification files beyond the lane packaging note and closeout note
- generated/runtime artifacts under `storage/` and `snapshots/`
- unrelated planning or review docs not named above

## Verification

Default verification for this bundle:
- `python3 scripts/lint_docs.py`

This bundle does not require frontend or backend runtime verification by default because it is source-of-truth documentation only.

## Relationship To Other Notes

- `docs/reports/Current_State_Packaging_2026-03-24.md` explains the whole mixed-worktree split
- `docs/reports/Current_State_Staging_Guide_2026-03-24.md` explains all staging buckets
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md` explains the default action order
- this note defines the default first bundle within that model

## Conclusion

If no one explicitly chooses a different lane, this is the only bundle that should move first.
