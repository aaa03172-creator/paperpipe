# PaperPipe Agentic Guidelines

## 1. Architectural Rules
- **API-First:** Core logic must be exposed via FastAPI. No hardcoded CLI-only paths.
- **Pydantic Contracts:** All agent inputs/outputs must strictly follow the Pydantic schemas in `src/schemas/`.
- **Idempotency:** Obsidian markdown generation must replace sections safely, not blindly append.
- **Persona/Mode Boundary:** Follow `docs/PERSONA_MODE_BOUNDARY.md`. Do not implement every user-facing perspective as a separate agent; separate core reasoning personas from profile context and output/view modes.
- **Canonical Docs Boundary:** Treat `docs/Lattice_v3_Master_Spec.md` as the top-level runtime SSOT and `docs/PERSONA_MODE_BOUNDARY.md` as the persona/output boundary. Proposal or fit-review docs may inform bounded RFCs, but they must not directly replace the current FastAPI API surface, the `src/db_utils.py` runtime DB/state layer, or the paper/run/artifact model unless explicitly adopted.
- **Operating Note Entry Point:** Use `docs/PaperPipe_Minimum_Operating_Principles.md` as the durable operating-note entrypoint for workflow/governance fit checks. Do not treat dated report copies or fit reviews as the primary operating reference once a canonical doc exists.
- **Layer Taxonomy Rule:** Before adding or changing a store, file, artifact, or response shape, classify it as one of: raw source, raw memory, compiled knowledge, canonical structured state, review/gate artifact, or user-facing artifact/export. If the layer is ambiguous, default to non-canonical until a canonical doc explicitly adopts it.
- **Raw / Memory / Compiled / Canonical Boundary:** Preserve raw sources as originals. Treat raw memory such as logs, traces, working files, backend-only project memory, or future conversation-like material as retrieval/support only. Treat compiled knowledge as derived and reviewable. Keep schema-backed structured state as the current system truth.
- **Review / Export Boundary:** Acceptance contracts, quality gates, eval sidecars, and review notes are additive checks, not replacement truth stores. User-facing answers, reports, packs, notes, or exports that present biomedical content as evidence-backed must be able to trace back to upstream canonical state and source/evidence lineage.
- **Inference Strategy Boundary:** Treat `local-first` primarily as data/runtime ownership, not as a blanket requirement that every operator machine run strong local-only inference. Keep canonical state local; allow bounded external inference only as a subordinate backend choice.
- **Inference Payload Rule:** Before adding or widening any inference request path, classify the payload as `local_only`, `lab_allowed`, or `external_allowed`. If ambiguous, default to the stricter class and keep excerpts minimal rather than sending full notes, full state, or raw memory.

## 1.5 Review guidelines
- Do not guess. Base judgments only on actual code evidence.
- Prioritize structural defects, data integrity, security, and failure modes over style.
- Do not imagine and overwrite a new architecture. Review for conflicts with the current implementation first.
- Distinguish source data, canonical state, derived artifacts, and cache.
- Always check whether any frontend flow handles secret keys directly.
- On failure paths, inspect partial writes, orphan records, and stale cache risks first.
- If documentation and implementation differ, explicitly call it out.
- Actively look for dead code, duplicate abstractions, and hidden side effects.
- Review output should list findings first, ordered by severity, with file/line evidence when available.
- Each finding should explain the impact, the concrete failure mode, and the smallest plausible fix direction.
- Separate confirmed defects from open questions, test gaps, residual risks, and optional cleanup suggestions.
- Do not present unverified assumptions as findings; mark uncertain items as questions or residual risk.
- Mention relevant tests or checks that were run, and explicitly state when verification was not run.
- Avoid broad rewrite recommendations unless the current implementation creates a concrete correctness, security, data-integrity, or maintainability risk.

## 1.6 Test-first and Codex-assisted review discipline
- Prefer test-first work for bug fixes: add or update the smallest failing test that reproduces the defect before changing implementation when practical.
- Apply TDD most strongly to contract-sensitive paths: FastAPI API behavior, Pydantic schemas, DB/state transitions, artifact generation, parsers, idempotent markdown replacement, inference payload boundaries, and security-sensitive flows.
- For narrow documentation, copy, or non-behavioral UI changes, a documented verification step may be sufficient instead of a new test.
- Keep verification proportional to risk. Prefer targeted tests, smoke checks, or builds for the touched surface before broader suites.
- If relevant tests cannot be run, state why and describe the residual risk.
- Use Codex-assisted review for non-trivial changes, especially changes touching schemas, persistence, state, security, artifacts, viewer flows, external inference paths, or workflow/governance rules.
- Treat Codex-assisted review as advisory. It should surface confirmed defects, open questions, test gaps, and optional cleanup, but it does not replace human judgment, repository policy, or canonical architecture docs.
- Do not accept Codex review suggestions that require broad rewrites unless they are tied to a concrete correctness, security, data-integrity, or maintainability risk with file/line evidence.

## 1.7 Branch and worktree discipline
- Before staging, committing, branching, or creating a worktree, inspect the current git status and preserve unrelated dirty changes.
- Do not create branches, worktrees, commits, pushes, or PRs unless the user asks or the task clearly requires it.
- For mixed dirty trees or non-trivial lane splits, prefer creating a clean branch/worktree from the latest merged base instead of staging directly from the dirty main worktree.
- Keep branch strategy explicit: repository default branch is currently `main`, while some PR/CI checks may still target `master` until the integration strategy is unified.
- Stage only the files or hunks that belong to the active lane. Use patch staging for mixed files.
- Keep local backup branch cleanup opt-in: follow `docs/Local_Backup_Branch_Retention_2026-02-24.md`, review dry-run output first, and require explicit `--apply` for deletion.

## 1.8 Change boundary and staging hygiene
- Keep docs-only governance changes separate from runtime/API/schema changes unless the user explicitly asks for both in one lane.
- Do not treat proposal, queue, report, archive, or fit-review docs as authorization to change runtime behavior unless a canonical doc or explicit user request adopts that change.
- Schema, DB/state, or persisted artifact contract changes must include compatibility impact, migration/backfill expectations, and targeted tests or a clear reason tests were not run.
- Do not silently change persisted artifact shapes without updating the owning schemas, readers, writers, and canonical docs together.
- Do not stage generated outputs, caches, snapshots, storage artifacts, logs, local runtime files, or temporary evidence unless they are explicitly part of the requested fixture, report, or validation artifact.
- Do not commit secrets, API keys, private document contents, or personal filesystem paths in user-facing artifacts. Prefer masked paths in logs, docs, API responses, and frontend-visible data.

## 2. MCP & Cost Control Guardrails (CRITICAL)
If you are equipped with the Google Developer Knowledge MCP (or any external search tool):
- **Limit `search_documents`:** Maximum 2 calls per session.
- **Limit `get_document`:** Maximum 1 call per session (only fetch the single most relevant doc).
- **BANNED `batch_get_documents`:** Do NOT use this tool. It causes massive token bloat. If absolutely necessary, you must ask the user for explicit permission first.
- **Save Context:** Summarize findings internally; do not repeatedly fetch the same external docs.

## 2.5 Scientific Skills Pack Rules
- `rules/scientific-skills` is a pinned submodule. Do not treat it as an unrestricted execution surface.
- Any adoption or execution path for scientific skills must pass `config/skills_policy.yaml`.
- Only project-approved skills may be copied into `.codex/skills/`.
- Default stance is deny-by-default for license, network, and secrets. If a skill is not explicitly allowed by policy, it is blocked.
- Keep PaperPipe's existing implementations when an external skill only duplicates functionality without materially improving reliability or UX.

## 2.6 Long Multi-Step Work Files
- For long multi-step work, use the lightweight workflow in `docs/working-files.md`.
- Keep task-local `plan.md`, `findings.md`, and `progress.md` under `.codex/work/<date>_<slug>/`.
- Re-read `plan.md` before major decisions, broad edits, or after context interruptions.
- Promote durable conclusions into canonical docs, queue docs, `docs/reports/`, or `docs/archive/` instead of treating working files as SSOT.
- Do not adopt Claude Code plugin or hook systems as part of this pattern unless the repo explicitly standardizes on them.

## 2.7 Local Skills Packaging
- For future local skills, follow `docs/SKILLS_PACKAGING_GUIDE.md`.
- Use external repositories such as Anthropic `skills` as design reference only for folder layout, `SKILL.md` shape, and resource separation.
- Do not import Claude-specific runtime assumptions, hooks, or plugin behavior into PaperPipe skill design.
- Do not copy source-available or mixed-license skill content until file-level license boundaries are checked and project policy allows it.
- If a skill becomes runtime-visible, wire it through `config/skills_policy.yaml`, `src/skills/`, and the relevant Pydantic schemas instead of treating `.codex/skills/` alone as product runtime.

## 3. Product Psychology Rules (Always-on for UX)
Before proposing or implementing UI/UX, onboarding, pricing, CTA, conversion, flow, or key user journey changes, always read and apply:
- `rules/product-psychology/SKILL.md`
- `rules/product-psychology/references/review-checklist.md`
- `rules/product-psychology/references/bias-framework.md`
- `rules/product-psychology/references/ethics-checklist.md`
- `rules/product-psychology/references/prompt-templates.md`

### UI Tooling Rule (Viewer/UI surfaces)
- Do not introduce random bespoke UI for new viewer-facing features.
- Keep the existing `--pp-*` token system and dark-first Lattice tone as the visual contract.
- For new reusable UI primitives, prefer vendored `shadcn/ui`-style components under `frontend/src/app/components/ui/`.
- 21st.dev component registry is an approved source for new UI blocks when existing local primitives are insufficient.
- Use the repo's package manager for registry installs when the shadcn CLI is already configured.
- If `frontend/components.json` exists, in this repo prefer `npx shadcn@latest add "https://21st.dev/r/<user>/<component>"` from `frontend/`.
- If `frontend/components.json` is absent or the CLI path does not fit the repo, vendor the component manually instead of bootstrapping a parallel UI system.
- Imported registry code must stay minimal, editable, and vendored into the repo. Remove demo-only logic and adapt styling to the existing `--pp-*` tokens and dark-first Lattice tone.
- Allowed by default: `shadcn/ui`, Radix, `lucide-react`, `clsx`, `tailwind-merge`, `class-variance-authority`.
- Requires explicit approval before keeping the dependency: `framer-motion`, `motion`, `three`, heavy animation libraries, analytics SDKs, trackers, or any other non-allowlisted runtime dependency.
- Review installed code and dependency diffs before commit. Remove suspicious network calls, telemetry, remote demo assets/fonts, and unnecessary sample content.
- Do not introduce Next.js-only code paths, a second token/theme system, or flashy landing-page sections unless explicitly requested.
- Reusable primitives belong in `frontend/src/app/components/ui/`; feature compositions belong with the feature route/component.
- Do not rewrite stable existing screens solely to force a framework migration.
- Current runtime stack is the contract unless a separate approved spec says otherwise:
  - FastAPI backend
  - Vite + React Router frontend
  - TailwindCSS
- Paper Notes Viewer layout standard:
  - Desktop target: left navigation/search, center reading content, right metadata/related/references
  - Mobile target: metadata/related/references in Sheet/Drawer style

### Trigger Conditions
Apply the product psychology rules whenever work includes:
- Landing pages
- Onboarding
- Pricing or paywall
- Key CTA design/copy
- Conversion or retention UX
- Error or empty states
- Core user flows (signup, purchase, explore, approve/export)
- "Why should I use this?" clarity problems
- Information architecture changes (search/filter/sort/related recommendations)
- Paper Notes Viewer layout, properties, references, or cross-linking changes

### Required Output Format (when UX is involved)
Every UX-involved response must include:
1. Quick Review (5 min)
2. Full Review (P0/P1/P2 prioritized)
3. BMAP diagnosis
4. B.I.A.S diagnosis
5. Peak-End design notes
6. Concrete changes (component/route/copy/default-action level)
7. Ethics check results (Regret / Black Mirror / In Real-Life)
8. Next PR-sized actions (1-3 items)

### Full Review Coverage (mandatory)
Inside "Full Review", explicitly cover all five frameworks:
- 6P storyboard context (Problem/Emotion/Action/Struggle/Attempt/Happy Ending)
- BMAP (Motivation / Ability / Prompt gaps)
- B.I.A.S (Block / Interpret / Act / Store)
- Peak-End (peak, pit, transition, end)
- Ethics checks (Regret / Black Mirror / In Real-Life)

### Internal Command Convention
Treat `/ux-review` as the standard review mode for UX tasks.

Input:
- target screen/flow
- user goal
- current pain points
- constraints (tech/design/business)

Output:
- Quick Review
- Full Review (P0/P1/P2)
- BMAP diagnosis
- B.I.A.S diagnosis
- Peak-End design notes
- Concrete implementation changes
- Ethics check
- 1-3 PR-sized next actions

### UX Review Artifacts
- Before starting UI changes, create or update:
  - `docs/UX_REVIEW_TEMPLATE.md`
  - `docs/UX_REVIEW_REPORT_<flow>.md`
- Each report header must include:
  - `Screen/Flow`
  - `Goal action`
  - `Primary persona`
  - `Current friction`
  - `Success metric`
- Any UI change that uses 21st.dev components must record the chosen component URL, why it was chosen, what was modified from upstream, and verification results in the matching UX review report and PR description.
- Verify UI sourcing changes from `frontend/` with `npm run build` and the relevant Playwright coverage when the touched surface already has tests.
- UI/flow changes are not done until the matching UX review artifact exists and references the product psychology repo files above.
