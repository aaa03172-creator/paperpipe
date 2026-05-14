# Current State Packaging (2026-03-24)

Status: Active
Date: 2026-03-24
Owner: Lattice runtime maintainers
Related current posture:
- `docs/reports/Current_Docs_Posture_2026-04-17.md`
- `docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md`

## Purpose

Summarize the current dirty workspace in a way that makes the next safe action obvious.

This note is not a new roadmap.

It is a packaging and separation note for the current mixed worktree state.

## 2026-04 usage note

This note remains useful as the original late-March packaging split for that mixed tree snapshot.

Use it for:
- the first docs-tail vs frontend-visual vs Docling/eval separation
- understanding what the late-March packaging pass considered "current"
- historical staging context when reviewing older docs-only bundles

Do not use it as the first current packaging or lane-selection note for the later repo state.

Read these first for current posture:
- `docs/reports/Current_Docs_Posture_2026-04-17.md`
- `docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md`
- `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`

## Current judgment

The repository does not need another new implementation lane right now.

The immediate need is to separate the current dirty tree into:
1. canonical/docs state that reflects the latest bounded-spec decisions
2. separate in-progress feature or evaluation lanes
3. generated/runtime artifacts that should not be treated as canonical source changes

## Recommended packaging split

### A. Keep as current canonical/docs tail

These changes reflect the latest repo state and should be treated as the current documentation tail:
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
- `docs/reports/Canonical_Docs_Tail_Packaging_2026-03-24.md`
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- `docs/reports/Current_State_Packaging_2026-03-24.md`
- `docs/reports/Current_State_Staging_Guide_2026-03-24.md`
- `docs/reports/Current_State_Update_2026-03-24.md`
- `docs/reports/Docling_Eval_Lane_Packaging_2026-03-24.md`
- `docs/reports/Frontend_Visual_Coverage_Lane_Packaging_2026-03-24.md`
- `docs/reports/Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
- `docs/reports/Local_Backup_Restore_Gate_2026-03-24.md`
- `docs/reports/Deferred_Lanes_Recheck_2026-03-24.md`

Why:
- these files capture the current bounded-spec promotions
- they also include the remaining dirty active canonical runtime docs that are not separate lanes
- they record the current hold/deferred decisions honestly
- they keep the queue and docs map aligned with the implementation maturity already reached

### B. Keep as a separate frontend visual-coverage lane

These changes should not be mixed into the docs-state packaging note above:
- `frontend/e2e/visual-backend.backend.spec.ts`
- visual snapshot files under `frontend/e2e/visual-backend.backend.spec.ts-snapshots/`
- related UX review docs such as:
  - `docs/UX_REVIEW_REPORT_chart-pack-viewer.md`
  - `docs/UX_REVIEW_REPORT_meeting-pack-viewer.md`
  - `docs/UX_REVIEW_REPORT_paper-notes-list.md`

Why:
- this is a distinct viewer-verification hardening lane
- it mixes route-shell review, copy checkpointing, and visual threshold work
- it should be reviewed as UI verification, not as bounded-spec packaging

Current lane note:
- `docs/reports/Frontend_Visual_Coverage_Lane_Packaging_2026-03-24.md`
- `docs/reports/Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`

### C. Keep as a separate Docling / ingest-eval lane

These changes are clearly part of a different evaluation/hardening track:
- `docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md`
- `docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md`
- `scripts/bootstrap.py`
- `src/services/cli_workflows.py`
- `scripts/eval/audit_section_quality.py`
- `scripts/eval/audit_table_merge_semantics.py`
- `src/schemas/teacher_review_eval.py`
- `src/services/teacher_review_eval_sidecar.py`
- `tests/test_section_quality_audit.py`
- `tests/test_table_merge_audit.py`
- `tests/test_teacher_review_eval_sidecar.py`
- related teacher-review and eval-sidecar reports under `docs/reports/`

Why:
- this lane is about parser/eval/tool-intake and teacher-review sidecars
- it should not be hidden inside bounded-spec or queue-state cleanup
- it likely needs its own narrative and verification summary

Current lane note:
- `docs/reports/Docling_Eval_Lane_Packaging_2026-03-24.md`

### D. Treat as generated/runtime artifacts, not canonical source changes

These paths should be treated cautiously and usually excluded from a docs-only packaging slice:
- `storage/meeting_packs/`
- `storage/method_comparisons/`
- `storage/obsidian/`
- `storage/search_eval/`
- `snapshots/ingest_backend_eval/`
- `goldset/reviews/spot_checks/teacher_review_spot_check_20260323_round1_codex_precheck.jsonl`
- local tool folders such as `.omx/` and `.serena/`

Why:
- these are generated outputs, runtime state, or local tool artifacts
- they may still be useful evidence, but they are not the same thing as source-of-truth code/docs changes

## Immediate recommendation

Do not open a new feature lane next.

Do this instead:
1. keep the canonical/docs tail conceptually separate
2. keep frontend visual coverage as its own verification lane
3. keep Docling/teacher-review work as its own evaluation lane
4. avoid treating generated `storage/` and `snapshots/` outputs as if they were ordinary source edits
5. treat the frontend lane as closed unless a route regresses or lacks shell coverage

## Explicit non-recommendations

Do not do these next:
- do not start another bounded feature lane from the current dirty tree
- do not mix Docling/eval changes into the bounded-spec documentation narrative
- do not treat snapshot or storage outputs as canonical docs/code changes
- do not reopen deferred lanes just because the worktree is already noisy

## Practical next step

If staging work continues, the next safe move is:
- use `docs/reports/Current_State_Staging_Guide_2026-03-24.md`
- use `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- keep lane-specific staging separate
- or explicitly leave remaining dirty paths as separate in-progress work

But do not merge all current dirty paths into one undifferentiated “current state” change.

For a practical split of the remaining dirty docs inside the docs-oriented side of the tree, use:
- `docs/reports/Remaining_Dirty_Docs_Buckets_2026-03-24.md`

## References

- `docs/README.md`
- `docs/Pending_PR_Queue.md`
- `docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md`
- `docs/reports/Deferred_Lanes_Recheck_2026-03-24.md`
- `docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md`
- `docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md`
- `docs/reports/Docling_Eval_Lane_Packaging_2026-03-24.md`
- `docs/reports/Frontend_Visual_Coverage_Lane_Packaging_2026-03-24.md`
- `docs/reports/Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`
- `docs/reports/Current_State_Staging_Guide_2026-03-24.md`
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- `docs/reports/Remaining_Dirty_Docs_Buckets_2026-03-24.md`

## Conclusion

The repo is past the point where another new lane is the right answer.

The right move is packaging discipline:
- keep the active bounded-spec docs tail clean
- keep visual verification work separate
- keep Docling/eval work separate
- keep generated artifacts out of the canonical narrative
