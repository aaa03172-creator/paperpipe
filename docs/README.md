# Documentation Map

Status: Active
Date: 2026-05-10
Owner: Lattice runtime maintainers
Purpose: keep a single reference map for specs, runbooks, templates, and historical records.

## How to classify a doc before using it

Before editing, citing, or using a document as implementation authority, classify it by status and role:

- `canonical/current`: current source of truth for product/runtime behavior, architecture, API contracts, or repo workflow.
- `active bounded spec`: current contract for one feature family or artifact lane; subordinate to canonical product/runtime docs.
- `runbook`: operational instructions for installing, running, verifying, recovering, or packaging the current system.
- `template`: reusable format for a repeated review, UX, artifact, or handoff workflow.
- `queue/staging note`: working-order or PR-packaging aid; useful for lane selection but not a runtime SSOT.
- `dated report`: evidence, audit, validation, posture, or decision record tied to a date; current only when named by an entrypoint or canonical doc.
- `proposal / fit review / future seam`: bounded input for discussion or RFCs; not authorization to change runtime behavior by itself.
- `historical/archive`: retained context or compatibility material; do not cite as current authority unless the document explicitly says what still applies.

When documents disagree, prefer in order:

1. `AGENTS.md` for agent workflow rules.
2. `docs/Lattice_v3_Master_Spec.md` plus bounded active specs for runtime/product contracts.
3. `docs/PERSONA_MODE_BOUNDARY.md`, `docs/PaperPipe_Minimum_Operating_Principles.md`, and related active operating notes for governance boundaries.
4. This documentation map and the current posture notes listed below for reading order.
5. Dated reports, queues, proposals, fit reviews, and archive records only as subordinate context.

Do not promote a queue, report, archive note, or fit review into runtime behavior unless a canonical doc or explicit user request adopts it.

## Current posture entrypoint

Use this section first when the question is "what is the current repo posture and which dated notes still matter?"

Read in this order:

1. `docs/reports/Current_Docs_Posture_2026-04-17.md`
   - Current reading-order note for the mixed repo state.
   - Start here if the question is "which docs should I trust first before I touch anything?"
2. `docs/reports/Lattice_Current_Safe_Product_Summary_2026-04-13.md`
   - Current-safe product wording anchor.
   - Start here if the question is "how should I describe the current product without overclaiming?"
3. `docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md`
   - Current lane split for the mixed dirty tree.
   - Start here if the question is "which implementation lane is actually open right now?"
4. `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`
   - Packaging split note for runtime-readiness and installability work.
   - Start here if the question is "what belongs in the personal-runtime/readiness lane?"
5. `docs/reports/Internal_Data_Readiness_For_Biomedical_Workspace_2026-04-13.md`
   - Support-only internal-data posture.
   - Start here only if the task touches project-context, artifact-history, or bounded raw-log surfaces.
6. `docs/reports/Python313_Import_Health_2026-04-14.md`
   - Local verification environment diagnostic.
   - Start here if local `pytest`, `src.cli`, or `backend.main` imports behave inconsistently.

## First-product baseline entrypoint

Use this section first when you need the current first shipped/demo-ready product baseline without re-reading the full doc tree.

Read in this order:

1. `docs/Product_Positioning_Principles.md`
   - Product identity, core assertions, and explicit non-positioning traps.
   - Start here if the question is "what kind of product is this, really?"
2. `docs/reports/Lattice_Current_Safe_Product_Summary_2026-04-13.md`
   - Current-safe wording anchor for product summaries, demos, and internal restatements.
   - Start here if the question is "how should we describe the current product without overclaiming?"
3. `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
   - The first-product promise, launch-defining loop, minimum deep-read bar, and out-of-scope lanes.
   - Start here if the question is "what counts as the first product?"
4. `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
   - The go/no-go checklist for the current first-product slice.
   - Start here if the question is "is the current slice launch-credible?"
5. `docs/reports/Canonical_Objects_Scope_Cut_And_Supported_Journey_2026-03-24.md`
   - The actual current canonical objects, now/later/not-this-product cut, and the researcher journey the repo honestly supports.
   - Start here if the question is "what does the runtime really support today?"
6. `docs/reports/Release_Rehearsal_Run_2026-03-25.md`
   - Recorded rehearsal result for the bounded current-runtime slice.
   - Start here if the question is "did we actually run the story end to end?"
7. `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
   - The late-March stop/continue decision and smallest follow-ups for that bounded first-product slice.
   - Start here only if the question is "what was the late-March baseline next-action call?"
8. `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
   - Direct answers to the recurring baseline questions: product identity, source of truth, v1 user, core workflow, first-class entities, current non-promises, and remaining doc/runtime gaps.
   - Start here if the question is "what is the concise repo-grounded answer?"
9. `docs/reports/First_Product_Demo_Runbook_2026-03-27.md`
   - The actual demo/handoff script for the bounded first-product slice.
   - Start here if the question is "how should we show or hand off the current product honestly?"
10. `docs/reports/First_Product_Demo_FAQ_2026-03-27.md`
   - Presenter-facing short answers for the most likely demo questions.
   - Start here if the question is "what should I say when asked directly?"
11. `docs/reports/First_Product_Demo_Script_3min_2026-03-27.md`
   - A short spoken script for the current first-product demo.
   - Start here if the question is "what exactly should I say in the demo?"

If you need the shortest path to the current answer, use:

- product shape -> `docs/Product_Positioning_Principles.md`
- current-safe wording -> `docs/reports/Lattice_Current_Safe_Product_Summary_2026-04-13.md`
- first-product bar -> `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- launch judgment -> `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- actual supported journey -> `docs/reports/Canonical_Objects_Scope_Cut_And_Supported_Journey_2026-03-24.md`
- proof and current stop/continue call -> `docs/reports/Release_Rehearsal_Run_2026-03-25.md` and `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- direct baseline Q&A -> `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
- demo / handoff script -> `docs/reports/First_Product_Demo_Runbook_2026-03-27.md`
- presenter FAQ -> `docs/reports/First_Product_Demo_FAQ_2026-03-27.md`
- 3-minute spoken script -> `docs/reports/First_Product_Demo_Script_3min_2026-03-27.md`

## Task-first entrypoint

If the question is not "which spec is canonical?" but "what can the current product actually help an operator do?", start here:

1. Run a deep read
   - `README.md`
   - `backend/main.py` (`POST /jobs/deepread`)
   - `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
   - `docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md` when the question is "how do we audit or compare saved deep-read handoff quality?"
2. Inspect saved paper state
   - `docs/WEB_VIEWER.md`
   - `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
   - `frontend/src/App.tsx` (`/papers`, `/papers/:slug`, `/workbench/:paperId`)
3. Refine reproducible search design
   - `docs/RESEARCH_DNA.md`
   - `src/cli.py` (`paperpipe research-dna ...`)
4. Generate a meeting-ready artifact
   - `docs/MEETING_PACK.md`
   - `backend/main.py` / `backend/routers/meeting_packs.py`
5. Inspect bounded artifact viewers
   - `docs/METHOD_COMPARISON.md`
   - `docs/CHART_PACK.md`
   - `docs/IMAGE_EVIDENCE.md`
   - `docs/PROTOCOL_KNOWLEDGE.md`

Use this path when you need the current supported workflow story without implying a broader project-centric or generic research-agent runtime.

For the implemented CLI surface, command group boundaries, and honest command-vs-route-vs-doc-label distinctions, use:

- `docs/CLI_WORKFLOW_REFERENCE.md`

## Canonical hierarchy

### 1. Governance and working rules
- `AGENTS.md`
- `docs/README.md` (this file)
- `docs/working-files.md`
  - Lightweight task-local planning workflow for long multi-step work.
  - Keeps ephemeral `plan.md` / `findings.md` / `progress.md` under `.codex/work/` and promotes durable outcomes into canonical docs.
- `docs/PaperPipe_Minimum_Operating_Principles.md`
  - Smallest durable operating guardrails for the current paper/job/artifact runtime shape.
  - Use this to evaluate workflow or governance proposals without reopening product shape or replacing runtime SSOT.
- `docs/inference_strategy.md`
  - Active operating note for local-first data ownership vs inference placement.
  - Use this when the question is "what backend strategy fits the current repo without turning it into a cloud-first or local-only product?"
- `docs/inference_data_boundary.md`
  - Active operating note for `local_only` / `lab_allowed` / `external_allowed` payload classification.
  - Use this before adding or widening any inference request path so canonical state and private research material are not over-shared.
- `docs/inference_routing_policy.md`
  - Active operating note for current task-to-backend routing posture across local, lab-server, and commercial inference slots.
  - Use this when deciding where a new reasoning or synthesis lane should run.
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
  - Bounded operating note for future compiled knowledge assets.
  - Use this when evaluating wiki-style or compiled-memory proposals so derived knowledge does not become a second source of truth.
- `docs/INDEPENDENT_REVIEW_TEMPLATE.md`
  - Optional PR-sized independent review template for bounded non-UX changes using `pass / warn / fail`.
  - Use this as an additive signoff aid, not as a mandatory universal protocol.
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
  - Repo-grounded workflow guide for architecture/ownership/linkage/priority refocus work.
  - Use this when a prompt or proposal risks widening scope beyond the current paper/job/artifact runtime.
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
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
  - Clarifies how future compiled knowledge assets fit the current runtime without replacing canonical structured state.
- `docs/inference_strategy.md`
  - Clarifies the current recommended product posture: local-first data ownership with selective external inference.
- `docs/inference_data_boundary.md`
  - Defines the current payload-minimization and backend-boundary rules for inference calls.
- `docs/inference_routing_policy.md`
  - Defines the current task-family routing recommendation for local, lab, and commercial inference backends.
- `docs/API_CHAT_CONTRACT.md`
  - Chat/API contract for the current runtime.
- `docs/RESEARCH_DNA.md`
  - Search-design asset spec for the bounded `DRAFT -> PILOT -> LOCKED` reproducibility lane.
- `docs/MEETING_PACK.md`
  - Evidence-linked lab meeting draft generation spec for downstream presentation packs.
  - Standard local verification: `./scripts/run_meeting_pack_verify.sh`
  - CI workflow: `.github/workflows/meeting-pack-verify.yml`
- `docs/METHOD_COMPARISON.md`
  - Evidence-linked paper-centric comparison artifact spec for saved cross-paper method snapshots.
- `docs/PAPER_SYNTHESIS.md`
  - Paper-scoped compiled-knowledge pilot spec for saved synthesis bundles derived from canonical state and selected run artifacts.
- `docs/CHART_PACK.md`
  - Deterministic chart artifact spec for file-backed visualization bundles built from saved structured artifacts.
- `docs/PROTOCOL_KNOWLEDGE.md`
  - Versioned, evidence-linked protocol reference spec for saved protocol-card bundles and the read-first inspector.
- `docs/IMAGE_EVIDENCE.md`
  - Metadata-first image-evidence sidecar spec for registered image bundles and the read-only inspector.
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
- `docs/UX_REVIEW_REPORT_chart-pack-viewer.md`
  - Review artifact for the read-only Chart Pack viewer and its warning-forward artifact review loop.
- `docs/UX_REVIEW_REPORT_image-evidence-viewer.md`
  - Review artifact for the read-only Image Evidence viewer and its source-first, metadata-only inspection loop.
- `docs/UX_REVIEW_REPORT_protocol-knowledge-inspector.md`
  - Review artifact for the read-only Protocol Knowledge inspector and its version-first review loop.
- `docs/UIUX_Adoption_Filter_2026-02-25.md`
  - UI adoption/include-exclude guardrail.
- `docs/WEB_VIEWER.md`
  - Viewer operations guide and implementation notes.
- `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`
  - Scoped follow-up queue for `/papers`, triage, rail, and workbench note-context work.
- `docs/archive/Paper_Notes_Workbench_Midpoint_Checkpoint_2026-03-13.md`
  - Recorded midpoint decision log for what is implemented now vs intentionally deferred.

### 6. Runtime and ops runbooks
- `docs/OPERATIONS_RUNBOOK.md`
  - First operator entrypoint for health/readiness, stuck jobs, logs, lightweight monitoring, secrets, backup posture, and deployment/rollback.
  - Use this when the question is "where should an operator start during an incident or routine runtime check?"
- `docs/RESTORE_READINESS_MATRIX.md`
  - Current restore expectation matrix for runtime DB, logs, caches, raw sources, bounded artifact bundles, and generated reports.
  - Use this when the question is "can this asset be directly restored, rerendered, recovered from a pre-apply backup, or only handled manually?"
- `docs/MUTATION_SCRIPT_SAFETY_INVENTORY.md`
  - Current safety inventory for local mutation scripts: dry-run, `--apply`, backup-before-apply, transaction/rollback, and summary output.
  - Use this before running archive, migration, replay, cleanup, or backfill scripts against local runtime state.
- `docs/DEPLOYMENT_ROLLBACK_CHECKLIST.md`
  - Current deployment/update/rollback checklist for repo alpha, macOS alpha handoff, macOS Gatekeeper-ready release, and Windows source alpha.
  - Use this before sharing, updating, or rolling back a personal runtime.
- `docs/CLI_WORKFLOW_REFERENCE.md`
  - Current implemented CLI surface grouped into operator-facing workflows, secondary utilities, and retained legacy/diagnostic commands.
- `docs/PERSONAL_RUNTIME_INSTALL.md`
  - Current close-person alpha install/start runbook for the personal-runtime path.
  - Use this when the question is "how should one operator install and run Lattice without turning it into a shared server?"
- `docs/PERSONAL_RUNTIME_USER_KITS.md`
  - Generator runbook for the current user-facing macOS and Windows handoff folders.
  - Use this when the question is "what folder do we send a tester right now, and how is it produced?"
- `docs/WINDOWS_PERSONAL_RUNTIME_ALPHA.md`
  - Honest Windows status note and cautious from-source alpha path for the personal-runtime shape.
  - Use this when the question is "what can we really say about Windows today, and what is the least risky operator path?"
- `docs/MACOS_PERSONAL_RUNTIME_RELEASE.md`
  - macOS release runbook for signing, notarization, stapling, and Gatekeeper-ready packaging around the current personal-runtime bundle.
  - Use this when the question is "how do we turn the current macOS alpha bundle into a distribution artifact?"
- `docs/MACOS_PERSONAL_RUNTIME_ALPHA_HANDOFF.md`
  - close-person macOS alpha handoff runbook for sharing the current bundle before Gatekeeper-ready trust distribution.
  - Use this when the question is "what do we actually send a trusted tester right now?"
- `docs/runtime_security_env.md`
- `docs/STALE_RUNNING_RECOVERY.md`
  - Current operator runbook for diagnosing stale `running` jobs, confirming queue-health warnings, and performing bounded manual recovery without direct DB edits.
  - Use this when the question is "a deep-read job looks stuck; how do we safely inspect, cancel, and re-run it with the current runtime semantics?"
- `docs/downloader_monitoring.md`
- `docs/institutional_access.md`
- `docs/operations_checklist_watcher_review_queue.md`
- `docs/teacher_quality_loop.md`
- `docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md`
  - Current runbook for bounded saved-run deep-read handoff audits, derived-artifact backfill, baseline compare, and promotion across fixed coric and multicase manifests.
  - Use this when the question is "how do we measure long-run deep-read reliability without reopening runtime architecture?"
- `docs/Local_Backup_Branch_Retention_2026-02-24.md`
  - Local branch-backup retention policy; adjacent to, but not a replacement for, future runtime backup/restore semantics.

### 7. Historical records and working papers
- Reports index: `docs/reports/README.md`
- Archive index: `docs/archive/README.md`
- Dated validation and audit outputs live under `docs/reports/`
- The 2026-03-13 audit/roadmap cluster in top-level `docs/` is historical evidence for the baseline split, not the current implementation queue or runtime SSOT:
  - `docs/Current_Code_Baseline_Audit_2026-03-13.md`
  - `docs/Audit_Driven_Roadmap_2026-03-13.md`
  - `docs/Citation_Grounding_Audit_2026-03-13.md`
  - `docs/Event_Logging_Audit_2026-03-13.md`
  - `docs/Identity_Pathing_Audit_2026-03-13.md`
  - `docs/Output_Contract_Audit_2026-03-13.md`
- `docs/Indexer_Model_Policy_Blueprint_2026-02-18.md` is historical policy context for indexer model defaults; verify current behavior in code and tests before using it as implementation guidance.
- `docs/SKILLS_RECOMMENDATIONS.md` is historical recommendation context for scientific-skills adoption; current adoption still requires `config/skills_policy.yaml`, `docs/SKILLS_PACKAGING_GUIDE.md`, and the relevant runtime schemas.
- `docs/UIUX_Adoption_Filter_2026-02-25.md` is an active adoption/exclusion record for imported UI reference material, not a standalone UI system or replacement for current `AGENTS.md` UX rules.
- `docs/Pending_PR_Queue.md` remains a secondary working queue for staging, packaging, and bounded reopen history.
- Do not use the queue as the first current-posture entrypoint when `docs/reports/Current_Docs_Posture_2026-04-17.md` answers the question directly.
- `docs/Personal_Assistant_Integration_Review_Packet_2026-05-10.md`
  - Maintainer-facing review packet for the current assistant-integration proposal set.
  - Use this when the question is "how should PaperPipe review the new personal-assistant seam docs before deciding whether to adopt, defer, or reject them?"
- `docs/Personal_Assistant_Integration_Seam_2026-05-10.md`
  - Bounded future-seam note for exposing PaperPipe safely to a separate personal assistant OS.
  - Use this when the question is "what should PaperPipe expose so an external assistant can orchestrate it without becoming the new truth owner?"
- `docs/Assistant_Facing_Summary_Contracts_2026-05-10.md`
  - Bounded future-seam note for thin assistant-facing summary/read models over current PaperPipe route and schema vocabulary.
  - Use this when the question is "what summary shape should an external assistant consume instead of rebuilding meaning from raw payloads?"
- Current dated reading-order and lane posture is summarized by:
  - `docs/reports/Current_Docs_Posture_2026-04-17.md`
  - `docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md`
  - `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`
- Current state / packaging / staging posture is currently summarized by:
  - `docs/reports/Current_State_Update_2026-03-24.md`
  - `docs/reports/Current_State_Packaging_2026-03-24.md`
  - `docs/reports/Current_State_Staging_Guide_2026-03-24.md`
  - `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
  - `docs/reports/Canonical_Docs_Tail_Packaging_2026-03-24.md`
  - `docs/reports/Personal_Runtime_Packaging_Decision_2026-03-28.md`
- Current lane-specific packaging notes are:
  - `docs/reports/Docling_Eval_Lane_Packaging_2026-03-24.md`
  - `docs/reports/Frontend_Visual_Coverage_Lane_Packaging_2026-03-24.md`
  - `docs/reports/Frontend_Core_UI_Refinement_Closeout_2026-03-24.md`
- Zero-reference or superseded proposals, fit reviews, plans, release notes, and snapshots live under `docs/archive/`
- `docs/archive/External_Reference_Fit_Review_2026-03-18.md`
  - Consolidated current-system-safe interpretation of recent external references across OCR/parser, retrieval/reranking, enrichment, note/memory, and agentic RAG references.
  - Keep this as a historical fit-review input, not as a replacement runtime spec.
- `docs/archive/OpenDataLoader_PDF_Fit_Review_2026-03-20.md`
  - Bounded parser/fallback fit review for OpenDataLoader PDF under the current ingest/runtime architecture.
  - Treat this as a historical parser-adjacent reference note, not as a parser migration spec.
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
- `docs/PaperPipe_Minimum_Operating_Principles.md` is the canonical operating note.
- `docs/reports/PaperPipe_Minimum_Operating_Principles_2026-03-25.md` is a retired compatibility stub kept only so older references do not break.

## Naming rules from now on

- Keep exactly one canonical top-level master spec.
- Keep exactly one canonical spec per bounded feature area.
- Keep exactly one template per workflow.
- Active normative docs should declare at least `Status`, `Date`, `Owner`, and either `Canonical` or `Canonical parent`, or the equivalent fields in YAML frontmatter when the document already uses frontmatter.
- Use dated filenames for reports, audits, validation outputs, proposals, and snapshots.
- Do not create a new "master spec" or "final blueprint" file if the change belongs in an existing canonical doc.
- Before creating a new report or spec, check this map for an existing canonical, bounded-spec, queue, or report home that should be updated instead.
- If a dated report is still the current entrypoint for a task, list it in the relevant entrypoint section instead of relying on filename recency alone.

## Safe consolidation rules

- When a document is normative, update the canonical doc instead of cloning it.
- When a document is historical, keep it dated and do not cite it as SSOT.
- When a document exists only as an alias, prefer updating references before deleting the alias.
- If a subsystem needs both a spec and a runbook, keep the split explicit:
  - spec = what the subsystem must do
  - runbook = how to operate, verify, or troubleshoot it
- Prefer adding `Status`, `Current entrypoint`, or `Do not use as runtime SSOT` notes before deleting or moving older documents.
- Keep docs-only posture cleanup separate from runtime/API/schema changes unless the lane explicitly includes both.
- Run `python3 scripts/lint_docs.py` after doc moves or naming changes.

## Contributor boundary note

- Canonical product/runtime docs remain `docs/Lattice_v3_Master_Spec.md` plus the bounded specs listed in this map, especially `docs/PERSONA_MODE_BOUNDARY.md` and `docs/API_CHAT_CONTRACT.md` for current runtime semantics.
- Current runtime boundary means the FastAPI app in `backend/main.py`, the runtime DB/state helpers in `src/db_utils.py`, and the existing paper/run/artifact storage paths under `storage/`.
- Future proposal docs may introduce bounded RFCs or subsystem specs, but they must not silently replace the current master spec, current API/DB contracts, or the repo's paper/run/artifact vocabulary unless an explicit architecture decision says so.
- Proposal, fit-review, or future-idea docs should stay dated historical notes or bounded RFCs until adopted; do not cite them as replacement SSOT for the current paper/run/artifact model.

## Immediate cleanup backlog

1. Update future references to point to `docs/Lattice_v3_Master_Spec.md` instead of the retired stub paths.
2. Update future operating-rule references to point to `docs/PaperPipe_Minimum_Operating_Principles.md` instead of the retired dated stub path.
3. Delete retired stub files only after you are comfortable breaking old links/bookmarks.
4. Keep new compatibility stubs paired with an explicit canonical target and docs lint coverage.
5. Keep UX review artifacts on the uppercase `UX_REVIEW_*` path family and treat `docs/ux-review-report.md` as historical only.
6. Move additional zero-reference historical working docs into `docs/archive/` when they stop serving as active handoff material.
7. Consider wiring `python3 scripts/lint_docs.py` into any local pre-commit flow if docs churn increases further.
