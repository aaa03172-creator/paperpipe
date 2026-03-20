# Documentation Map

Status: Active
Date: 2026-03-13
Owner: Lattice runtime maintainers
Purpose: keep a single reference map for specs, runbooks, templates, and historical records.

## Canonical hierarchy

### 1. Governance and working rules
- `AGENTS.md`
- `docs/README.md` (this file)
- `docs/working-files.md`
  - Lightweight task-local planning workflow for long multi-step work.
  - Keeps ephemeral `plan.md` / `findings.md` / `progress.md` under `.codex/work/` and promotes durable outcomes into canonical docs.
- `docs/SKILLS_PACKAGING_GUIDE.md`
  - PaperPipe-local authoring and packaging guidance for future skills under `.codex/skills/`.
  - Uses external skill repositories as design reference only, not as runtime dependency.

### 2. Product positioning
- `docs/Product_Positioning_Principles.md`
  - Product-level positioning note for why Lattice exists, who it helps, and which principles should survive runtime evolution.
  - Keep this separate from API/DB/schema contracts.

### 3. Product/runtime SSOT
- `docs/Lattice_v3_Master_Spec.md`
  - Top-level product/runtime source of truth.
  - Use this as the default reference for architecture, contracts, and milestone intent.

### 4. Bounded specs and contracts
- `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
  - Viewer-specific feature spec for `/papers`, `/papers/:slug`, and the viewer UX loop.
- `docs/Korean_Reading_Assist_Policy.md`
  - Translation boundary spec for Korean reading-assist as a display-only layer.
- `docs/Stats_Verification_Agent_Spec.md`
  - Stats verification feature contract.
- `docs/PERSONA_MODE_BOUNDARY.md`
  - Separates core reasoning personas, profile context, and output/view modes.
  - Prevents audience or deliverable variants from turning into separate agents by default.
- `docs/Evidence_and_Uncertainty_Rules.md`
  - Consolidates current evidence-first, uncertainty-visible, and grounding-preservation rules across claim, export, chat, and downstream artifact surfaces.
- `docs/API_CHAT_CONTRACT.md`
  - Chat/API contract for the current runtime.
- `docs/RESEARCH_DNA.md`
  - Search-design asset spec for the future `DRAFT -> PILOT -> LOCKED` reproducibility lane.
- `docs/MEETING_PACK.md`
  - Evidence-linked lab meeting draft generation spec for downstream presentation packs.
  - Standard local verification: `./scripts/run_meeting_pack_verify.sh`
  - CI workflow: `.github/workflows/meeting-pack-verify.yml`
- `docs/Indexer_Model_Policy_Blueprint_2026-02-18.md`
  - Indexer policy source of truth.
- `docs/document_artifact_v2.md`
  - Document artifact contract.
- `docs/bootstrap_meta_schema.md`
  - Bootstrap metadata schema reference.

### 5. UX process, templates, and UI guidance
- `docs/ux-review.md`
  - Command/process definition for UX reviews.
- `docs/UX_REVIEW_TEMPLATE.md`
  - Template for new UX reviews.
- `docs/UX_REVIEW_REPORT_<flow>.md`
  - Per-flow review artifact format.
- `docs/UX_REVIEW_REPORT_korean-reading-assist.md`
  - Review artifact for translation boundary and Korean reading-assist prioritization.
- `docs/UX_REVIEW_REPORT_method-comparison-viewer.md`
  - Review artifact for the read-only Method Comparison viewer and its evidence-forward inspection loop.
- `docs/UIUX_Adoption_Filter_2026-02-25.md`
  - UI adoption/include-exclude guardrail.
- `docs/WEB_VIEWER.md`
  - Viewer operations guide and implementation notes.
- `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`
  - Scoped follow-up queue for `/papers`, triage, rail, and workbench note-context work.
- `docs/archive/Paper_Notes_Workbench_Midpoint_Checkpoint_2026-03-13.md`
  - Recorded midpoint decision log for what is implemented now vs intentionally deferred.

### 6. Runtime and ops runbooks
- `docs/runtime_security_env.md`
- `docs/downloader_monitoring.md`
- `docs/institutional_access.md`
- `docs/operations_checklist_watcher_review_queue.md`
- `docs/teacher_quality_loop.md`
- `docs/Local_Backup_Branch_Retention_2026-02-24.md`
  - Local branch-backup retention policy; adjacent to, but not a replacement for, future runtime backup/restore semantics.

### 7. Historical records and working papers
- Reports index: `docs/reports/README.md`
- Archive index: `docs/archive/README.md`
- Dated validation and audit outputs live under `docs/reports/`
- Zero-reference or superseded proposals, fit reviews, plans, release notes, and snapshots live under `docs/archive/`
- `docs/archive/External_Reference_Fit_Review_2026-03-18.md`
  - Consolidated current-system-safe interpretation of recent external references across OCR/parser, retrieval/reranking, enrichment, note/memory, and agentic RAG references.
  - Keep this as a historical fit-review input, not as a replacement runtime spec.
- `docs/Pending_PR_Queue.md` as a working queue, not a spec
- For `/papers`, triage, rail, and workbench note-context follow-up, prefer `docs/PAPER_NOTES_WORKBENCH_QUEUE.md` before the repo-wide queue.

## Duplicate and alias findings

As of 2026-03-09, the following files were byte-identical before retirement and should not all be treated as separate SSOTs:

- `docs/Lattice_v3_Master_Spec.md`
- `docs/Lattice_v3_UIUX_MASTER.md`
- `docs/PaperPipe_v3_Master_Spec.md`
- `docs/PaperPipe_v3_Master_Spec_Final_Blueprint_v1_2.md`

Canonical choice:

- Use `docs/Lattice_v3_Master_Spec.md` for all new references.

Treat the others as retired compatibility stubs. They keep the old paths alive but are no longer normative docs.

Additional note:

- `docs/ux-review-report.md` is a historical example report.
- New review artifacts should use `docs/UX_REVIEW_REPORT_<flow>.md`.

## Naming rules from now on

- Keep exactly one canonical top-level master spec.
- Keep exactly one canonical spec per bounded feature area.
- Keep exactly one template per workflow.
- Active normative docs should declare at least `Status`, `Date`, `Owner`, and either `Canonical` or `Canonical parent`, or the equivalent fields in YAML frontmatter when the document already uses frontmatter.
- Use dated filenames for reports, audits, validation outputs, proposals, and snapshots.
- Do not create a new "master spec" or "final blueprint" file if the change belongs in an existing canonical doc.

## Safe consolidation rules

- When a document is normative, update the canonical doc instead of cloning it.
- When a document is historical, keep it dated and do not cite it as SSOT.
- When a document exists only as an alias, prefer updating references before deleting the alias.
- If a subsystem needs both a spec and a runbook, keep the split explicit:
  - spec = what the subsystem must do
  - runbook = how to operate, verify, or troubleshoot it
- Run `python3 scripts/lint_docs.py` after doc moves or naming changes.

## Contributor boundary note

- Canonical product/runtime docs remain `docs/Lattice_v3_Master_Spec.md` plus the bounded specs listed in this map, especially `docs/PERSONA_MODE_BOUNDARY.md` and `docs/API_CHAT_CONTRACT.md` for current runtime semantics.
- Current runtime boundary means the FastAPI app in `backend/main.py`, the runtime DB/state helpers in `src/db_utils.py`, and the existing paper/run/artifact storage paths under `storage/`.
- Future proposal docs may introduce bounded RFCs or subsystem specs, but they must not silently replace the current master spec, current API/DB contracts, or the repo's paper/run/artifact vocabulary unless an explicit architecture decision says so.
- Proposal, fit-review, or future-idea docs should stay dated historical notes or bounded RFCs until adopted; do not cite them as replacement SSOT for the current paper/run/artifact model.

## Immediate cleanup backlog

1. Update future references to point to `docs/Lattice_v3_Master_Spec.md` instead of the retired stub paths.
2. Delete the retired stub files only after you are comfortable breaking old links/bookmarks.
3. Keep UX review artifacts on the uppercase `UX_REVIEW_*` path family and treat `docs/ux-review-report.md` as historical only.
4. Move additional zero-reference historical working docs into `docs/archive/` when they stop serving as active handoff material.
5. Consider wiring `python3 scripts/lint_docs.py` into any local pre-commit flow if docs churn increases further.
