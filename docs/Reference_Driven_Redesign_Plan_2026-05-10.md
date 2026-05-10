# Reference-Driven Redesign Plan

Status: Proposed redesign plan
Date: 2026-05-10
Owner: Frontend/product maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Related operating note: `docs/ui_references.md`
Related design identity: `docs/PaperPipe_Design_Identity.md`
Related page architecture: `docs/PaperPipe_Page_Architecture.md`
Related extracted data workflow: `docs/PaperPipe_Extracted_Data_Workflow_Map.md`
Related UI grammar: `docs/PaperPipe_UI_GRAMMAR.md`
Related UI audit: `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`
Related first route report: `docs/UX_REVIEW_REPORT_paper-detail-right-rail.md`
Document map: `docs/PaperPipe_UI_Redesign_Document_Map.md`
Related synthesis: `docs/reports/UI_Reference_Research_Lazyweb_Synthesis_2026-05-10.md`

## 1. Executive Summary

Recommendation: proceed with a reference-informed redesign program, but do not run a visual-only or full rewrite redesign.

PaperPipe has grown from a paper-reading viewer into a local-first biomedical research workspace with Paper Notes, Workbench, claim/evidence review, operator markers, Research DNA, Meeting Packs, Protocol Cards, Chart Packs, Image Evidence, Obsidian sync, and downstream artifact viewers.

That growth makes a redesign legitimate. The current risk is not that the UI is too simple. The risk is that strong, evidence-aware features now live in many screens with slightly different scan hierarchies, state language, and action priority.

The redesign should therefore be a workflow and information-architecture pass:
- define the PaperPipe design identity
- define the page architecture
- define a PaperPipe UI grammar
- audit the core research loops against that grammar
- run one bounded redesign spike on `/papers/:slug`, unless the audit identifies a safer first route
- propagate the proven grammar to Workbench, artifact detail, and Home only after the spike holds up

## 2. Scope And Non-Goals

In scope:
- layout grammar for reading, review, recovery, and artifact handoff screens
- state language for canonical, generated, draft, reviewed, stale, unresolved, and personal marker states
- action hierarchy for primary, secondary, guarded, and maintenance actions
- panel order and rail semantics
- mobile sheet ordering where it mirrors desktop information priority
- iconography, progress indicators, gauges, color-state changes, emphasis, and restrained motion when they clarify evidence workflow
- reference pattern mapping from Lazyweb and other generic UI references

Out of scope for this plan:
- replacing FastAPI, Vite, React Router, or TailwindCSS
- adding Lazyweb as a runtime dependency
- adding a new design system beside the existing `--pp-*` tokens
- changing Pydantic schemas solely for visual redesign
- adding approval, promotion, graph, or annotation states without explicit schema/API ownership
- sending PaperPipe PDFs, paper titles, private notes, screenshots, lab context, local paths, or identifiers to external reference tools

## 3. Quick Review

- Choice count: each screen should expose one primary research action, a small set of secondary actions, and clearly separated guarded maintenance actions.
- Benefit: the first scan should answer "what can I read, verify, recover, or safely reuse now?"
- Next action: prioritize evidence review, source reopening, marker recovery, or guarded artifact reuse over generic dashboard navigation.
- Feedback: saved review state, marker saves, rerenders, exports, and sync actions need visible state feedback.
- Ethics: polished generated artifacts must not look more trustworthy than their upstream evidence state.

## 4. Full Review

P0:
- Preserve local-first data ownership, canonical structured state, and evidence provenance.
- Do not let external references become product requirements without PaperPipe review.
- Do not introduce `Approved`, `Promoted`, passage annotation, figure-region annotation, or graph truth states without a first-class contract.
- Do not weaken artifact/state/provenance boundaries for visual polish.

P1:
- Create `docs/PaperPipe_Design_Identity.md` before the UI grammar.
- Use `docs/PaperPipe_UI_GRAMMAR.md` as the shared UI rulebook before broad UI implementation.
- Use `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md` before choosing the first code patch.
- Treat `/papers/:slug` as the first redesign spike, but keep the implementation bounded to the right rail, mobile sheet ordering, action hierarchy, and visual-state labels. The current UI audit names Paper Notes List row state/action grammar as the fallback if Paper Detail route risk is too high.
- Keep every implementation PR bounded to one route family or one shared primitive.

P2:
- Use reference research to tune density, state placement, panel order, and empty/error states.
- Defer pure visual refresh until workflow grammar is stable.
- Prefer current primitives and `--pp-*` tokens before adding new UI dependencies.

## 5. Full Review Coverage

6P storyboard context:
- Problem: PaperPipe's features have grown faster than its shared UI grammar.
- Emotion: researchers can trust the product more when evidence, state, and next action are obvious.
- Action: user opens Home, Paper Notes, Paper Detail, Workbench, or a saved artifact.
- Struggle: the user must decide which state is canonical, which artifact is draft-like, and which action is safe.
- Attempt: define a shared UI grammar, audit core loops, and redesign the central paper detail screen first.
- Happy Ending: PaperPipe feels like one coherent research workspace where source -> evidence -> review -> artifact is always legible.

BMAP:
- Motivation is high because the project has outgrown its early UI assumptions.
- Ability improves when the redesign is split into docs, audit, one spike, and propagation.
- Prompt is the UI grammar document plus a route-specific UX report before each PR.

B.I.A.S:
- Block: reduce first-scan overload by separating reading, evidence, state, and maintenance zones.
- Interpret: make state language consistent across Home, Paper Notes, Workbench, and artifact detail.
- Act: make the next safe research action obvious before lower-priority controls.
- Store: repeat source/evidence/review/artifact rhythm until users remember the product model.

Peak-End:
- Peak: a user can see a claim, its evidence/provenance, and its current review state without losing the paper context.
- Pit: a polished dashboard or artifact makes generated content feel reviewed when it is not.
- Transition: Home -> paper detail -> Workbench -> artifact detail should preserve state and source context.
- End: export, meeting, protocol, chart, or note handoff keeps the evidence boundary visible.

Ethics:
- Regret: reduced if redesign saves time and reduces over-trust.
- Black Mirror: risk appears if visual polish implies scientific certainty.
- In Real-Life: PaperPipe should act like a careful research assistant, not a sales dashboard.

## 6. Redesign Principles

1. Evidence first, polish second.
   - Every visual hierarchy decision should make source, evidence, state, or safe next action clearer.

2. Local-first remains product truth.
   - References may shape UI patterns, but they do not move data, tokens, PDFs, or private notes outside the local workspace.

3. Canonical state stays explicit.
   - Canonical structured state, generated artifacts, personal markers, lane-owned review cues, and user-facing exports must remain visually and conceptually distinct.

4. State before action.
   - Generated artifacts should show review/readiness/source boundary before rerender, regenerate, export, or share actions.

5. One primary loop per screen.
   - A screen may support many tasks, but first scan should reveal the dominant loop: recover, read, verify, repair, or reuse.

6. Shared grammar before shared aesthetics.
   - Do not start by changing colors, cards, icons, or spacing. Start by defining layout zones, state language, and action hierarchy.

7. Visual expression is allowed when it carries state.
   - Icons, progress bars, gauges, color changes, badges, and subtle motion are welcome when they make provenance, review progress, warnings, or safe next action easier to understand.
   - They should not exist only to make a screen feel more animated, gamified, or SaaS-like.

8. Motion should confirm transitions, not distract from reading.
   - Use motion for state changes, save confirmation, queue progress, panel reveal, artifact generation progress, and warning escalation.
   - Avoid looping decorative animation near reading text, evidence excerpts, or claim review controls.

9. Color and emphasis must preserve truth boundaries.
   - Use a small color vocabulary to distinguish only the states that truly need faster visual scanning: active context, warning, danger, and saved or healthy completion.
   - Prefer label, icon, position, density, and grouping before adding another color.
   - Do not use success colors to imply scientific validation unless upstream canonical review state supports it.

## 7. Proposed Deliverables

### Deliverable A: Current UI Reality Audit v2

File:
- `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`

Purpose:
- score current screens against the design identity and the new reference-driven redesign criteria.

Required coverage:
- `/`
- `/papers`
- `/papers/:slug`
- `/workbench/:paperId`
- artifact detail family
- mobile sheet/order implications for paper detail and artifact detail
- existing visual primitives and gaps: `StatusBadge`, `Stepper`, `lucide-react`, `--pp-*` tokens, progress/loading patterns, and visual test coverage

Output:
- design debt table
- state/provenance clarity score
- action hierarchy score
- density/fatigue risk score
- visual-state opportunity score
- motion/accessibility risk score
- first-scan question for each route
- PR-sized redesign candidates

### Deliverable B: PaperPipe UI Grammar

File:
- `docs/PaperPipe_UI_GRAMMAR.md`

Purpose:
- define the shared interaction grammar before implementation.

Current status:
- initial proposed grammar exists.
- `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md` selects a bounded Paper Detail right-rail and mobile-sheet micro-spike as the first implementation target.
- `docs/UX_REVIEW_REPORT_paper-detail-right-rail.md` scopes that spike to route-local ordering/copy changes.

Required sections:
- design identity summary from `docs/PaperPipe_Design_Identity.md`
- screen families: recovery, reading, evidence review, artifact review, diagnostics
- layout zones: left navigation/search, center reading/review body, right state/provenance/action rail
- state language: canonical, generated, draft, reviewed, stale, unresolved, personal marker, export
- trust boundary placement rules
- action hierarchy rules
- visual state system: icons, badges, color, emphasis, progress, gauges, and motion
- additional redesign axes: progressive disclosure, recovery states, keyboard flow, diff UX, personal memory, accessibility, search/filter grammar, export guardrails, and local-only instrumentation
- design tooling map: reference tools, local primitives, component sourcing, verification tools, and dependency gates
- mobile sheet ordering rules
- banned patterns
- allowed dependency and primitive policy
- reference pattern map

Visual state system must define:
- icon semantics for source, claim, evidence, warning, stale, local file, external route, personal marker, generated artifact, and export
- progress/gauge semantics for import, parsing, artifact generation, review completeness, source coverage, warning density, and sync/readiness
- color-state rules that keep color secondary to labels and icons, with a restrained set of neutral, accent, warning, danger, and limited success roles
- motion rules for loading, save feedback, panel transitions, guarded action reveal, and completion feedback
- accessibility requirements for non-color state cues, reduced motion, contrast, and tooltip/label support

Existing local primitives to prefer:
- `StatusBadge` for small state labels
- `Stepper` for multi-step ingest, generation, or review flows
- `lucide-react` icons inside buttons, state chips, and section headers
- existing `--pp-*` and `--pp-status-*` tokens for color and tone
- existing Tailwind transition utilities for restrained hover, reveal, and save-feedback motion

Avoid introducing a new animation or visualization dependency unless the grammar document proves that existing primitives cannot express the state clearly.

### Deliverable B.1: Visual State Candidate Matrix

Location:
- inside `docs/PaperPipe_UI_GRAMMAR.md`

Purpose:
- convert the request for richer visualization into concrete, route-level candidates before implementation.

Candidate matrix:

| Surface | Candidate visual support | Useful when | Guardrail |
| --- | --- | --- | --- |
| Home / triage | icon-led queue states, compact readiness counters, subtle count-change emphasis | user needs to resume or choose a queue lens quickly | do not imply a real project model or approval queue that does not exist |
| Paper Notes list | row icons for local PDF, open access, operator marker, structured state, review-needed; optional small coverage meter | list should feel like a research handoff index, not just search results | every icon needs text/tooltip and filter alignment |
| Paper detail | right-rail state badges, source/evidence icons, claim coverage meter, save-feedback motion, guarded action reveal | user needs to see saved state, evidence, references, and next safe action while reading | no color/gauge should imply scientific truth without canonical review support |
| Workbench | review progress gauge, warning density marker, claim status icons, source-coverage strip, repair/rebuild stepper | user is verifying claims and repairing artifacts | keep motion away from evidence excerpts and highlighted source text |
| Image / figure evidence | provenance timeline, viewport/version icon, warning severity color, reuse boundary badge | user must inspect a derived visual before reuse | no image interpretation result becomes canonical through styling |
| Meeting / protocol / chart artifacts | readiness badge, source coverage gauge, draft/review state strip, guarded export/rerender stepper | user is close to sharing, export, or downstream reuse | state first, action second; no fake approved/promoted states |
| Runtime readiness / sync | stepper for machine readiness, local storage/source checks, sync status badges | user needs trust in local-first setup | do not expose noisy diagnostics as primary product UI |

Each candidate must be accepted, revised, deferred, or rejected during the v2 audit before code changes.

### Deliverable B.2: Additional Redesign Axes

Location:
- inside `docs/PaperPipe_UI_GRAMMAR.md`
- summarized in `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`

Purpose:
- prevent the redesign from focusing only on layout and visual state while missing usability systems that make a research workspace feel mature.

Priority order:

| Priority | Axis | Why it matters | First acceptable output | Guardrail |
| --- | --- | --- | --- | --- |
| 1 | Progressive disclosure | PaperPipe has dense reading, review, trace, and artifact data. Users need summaries before raw detail. | rules for summary, details, advanced/debug, and mobile sheet reveal | evidence-critical warnings and trust boundaries cannot be hidden behind optional disclosure |
| 2 | Empty / loading / error / recovery states | Product quality is most visible when imports, state sidecars, artifacts, or backend calls are missing or stale. | route-level recovery-state checklist with icons, progress, next action, and copy guidance | recovery UI must not pretend missing canonical state exists |
| 3 | Keyboard / command flow | Repeated review actions need speed once the user understands the screen. | local hot-action shortlist per route before global command palette | shortcuts must not trigger destructive or externally visible actions without confirmation |
| 4 | Comparison / diff UX | Regeneration, repair, versioning, and protocol/artifact updates need before/after trust. | candidate diff surfaces for claimsets, meeting drafts, protocol versions, and chart/image bundles | diff UI must identify source layer and avoid treating generated deltas as reviewed truth |
| 5 | Personal workspace memory | Users need to resume where they left off without turning personal memory into canonical evidence. | rules for last-opened, pinned, starred, unresolved, and recently reviewed recovery cues | personal memory must stay separate from claim/evidence validation state |
| 6 | Accessibility / cognitive load | Richer visual state increases accessibility responsibility. | contrast, reduced motion, focus order, tooltip, truncation, and tap-target checklist | visual-only meaning is not allowed |
| 7 | Search / filter grammar | Retrieval is a core workflow, not a generic table feature. | common vocabulary for source availability, markers, review state, artifact readiness, and blocked states | filter labels must match backend/API semantics |
| 8 | Export / share guardrails | Artifacts are closest to downstream reuse and over-trust. | pre-export state checklist for source coverage, warnings, generated/draft state, and provenance summary | do not add approval/share language without adopted contract |
| 9 | Evidence-aware assistant readiness | A future chatbot should help users inspect source/evidence, not replace the workspace shell. | assistant panel placement, answer-source labels, uncertainty states, and payload boundary checklist | chat is not canonical truth, product shell, or hidden external transfer surface |
| 10 | Local-only instrumentation | The team needs evidence that redesign reduces friction without external tracking. | dev-only/local metrics proposal for click depth, dead ends, and route recovery | no external analytics/tracking SDK without explicit approval |

Adoption rule:
- each axis should produce a small checklist or grammar subsection before implementation.
- if an axis needs runtime state, classify the layer first: personal memory, review/gate artifact, user-facing export, compiled knowledge, or canonical structured state.
- if an axis is only visual or convenience-level, it must still show how it improves first-scan clarity, recovery, verification, or safe handoff.

### Deliverable B.3: Design Tooling Map

Location:
- inside `docs/PaperPipe_UI_GRAMMAR.md`
- summarized in each route-specific UX report when a tool materially shapes the implementation

Purpose:
- make the redesign toolchain explicit so reference research, component sourcing, implementation, and verification do not blur together.

Tooling matrix:

| Category | Tool / source | Current status | Use for | Boundary |
| --- | --- | --- | --- | --- |
| Reference research | Lazyweb MCP | developer-local only | generic UI references, approval/review patterns, dense workspace analogies | not runtime, not product requirement, no private PaperPipe data |
| Reference research | VoltAgent `awesome-design-md` | reference only | DESIGN.md structure, design-token checklist, do/don't format, preview artifact idea | do not copy brand identities or drop a third-party DESIGN.md into the repo as PaperPipe truth |
| Design composition | Figma | optional external design tool | wireframes, layout experiments, visual grammar before code | design file is reference, not implementation truth |
| UI component source | existing local primitives | preferred | `Rail`, `StatusBadge`, `StatusChip`, `Stepper`, `TimelinePanel`, `WorkspaceContextStrip`, `ArtifactHeaderContext` | adapt before adding new primitives |
| UI component source | `frontend/src/app/components/ui/` | preferred | button, badge, card, command, input, separator, sheet | keep `--pp-*` tokens and dark-first tone |
| UI component source | shadcn/ui style | allowed | new reusable primitives when local ones are insufficient | `frontend/components.json` is absent now, so vendor manually unless CLI config is added intentionally |
| UI block source | 21st.dev registry | allowed with review | complex UI blocks or interaction patterns | record source URL, modifications, verification, and remove demo/network code |
| Icons | `lucide-react` | installed | action icons, state chips, section headers, compact controls | unfamiliar icons need labels, aria labels, or tooltips |
| Styling | TailwindCSS + `--pp-*` tokens | current contract | layout, density, state tones, responsive behavior | no second theme system |
| Document/PDF viewing | `@react-pdf-viewer/*`, `pdfjs-dist` | installed | PDF reading, highlight/search/page navigation surfaces | do not add annotation semantics without anchor contract |
| Visual state | local `StatusBadge`, `Stepper`, CSS transitions | preferred | readiness, progress, warnings, save feedback, generation/review steps | no heavy animation dependency by default |
| Browser verification | Playwright configs | installed | route behavior, visual snapshots, mock/backend coverage | update snapshots only when layout change is intentional |
| Local browser inspection | Codex Browser / in-app browser | available during development | inspect localhost UI and screenshots | use for verification, not as product dependency |
| Image generation/search | generated or reference imagery | optional | rare illustrative backgrounds or visual exploration | generally avoid for core research UI unless it exposes actual product state |
| Motion libraries | `framer-motion`, `motion`, heavy animation libs | requires explicit approval | only if native CSS/Tailwind cannot express necessary state transition | must justify dependency, accessibility, and bundle cost |
| 3D / canvas | `three` or similar | requires explicit approval | only for explicitly 3D/visualization-heavy features | not for ordinary research workflow polish |
| Analytics/tracking | external analytics SDKs | requires explicit approval | generally avoid | prefer local-only/dev-only instrumentation |

Default order of operations:
1. use existing local primitives and `--pp-*` tokens.
2. use `lucide-react`, `StatusBadge`, `Stepper`, and CSS transitions for visual state.
3. use Figma or Lazyweb only to clarify reference patterns and layout grammar.
4. use `awesome-design-md` only as a checklist/template reference for the PaperPipe-owned grammar document.
5. vendor a shadcn/21st.dev-style primitive only if the local component set cannot express the needed interaction.
6. request explicit approval before keeping any heavy runtime dependency.

`awesome-design-md` fit:
- classification: reference only
- useful pattern: a markdown design-system file with sections for visual theme, color roles, typography, component styling, layout principles, depth/elevation, do/don't rules, responsive behavior, and prompt guidance
- safest use: borrow the document structure for `docs/PaperPipe_UI_GRAMMAR.md`
- unsafe use: copying a named brand's visual identity, typography, marketing chrome, gradients, or token values into PaperPipe
- license note: upstream is MIT, but individual DESIGN.md files describe public brand identities and should be treated as inspiration/checklist material rather than imported design assets

Every design-tool-assisted PR must record:
- which tool/source was used
- why existing local primitives were insufficient, if a new primitive was added
- which code was vendored or adapted
- which demo/network/telemetry code was removed
- how `--pp-*` tokens and dark-first tone were preserved
- which Playwright/build/docs checks ran

### Deliverable C: Reference Pattern Map

Location:
- either inside `docs/PaperPipe_UI_GRAMMAR.md` or as `docs/reports/UI_Reference_Pattern_Map_2026-05-10.md`

Examples:
- GitHub checks -> review-state-before-action
- Metaplane data quality gates -> guarded artifact reuse
- Dropbox Replay -> viewport/version-scoped annotation, only after anchor contract
- Benchling -> scientific workspace density, not lab-platform marketing
- Grammarly citation side panel -> nearby citation support, not one-click truth

### Deliverable D: Paper Detail Redesign Spike

Target:
- `/papers/:slug`
- [PaperNoteDetailPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx)

Why this route first:
- it is the central handoff between reading, saved state, claim/evidence review, operator markers, references, Workbench, Protocol Cards, and downstream artifacts.
- if the grammar works here, it can propagate to Workbench and artifact details.

Initial goals:
- make saved state and claim/evidence review the first trust-bearing rail sequence
- keep personal markers clearly scoped as revisit memory
- make references/support material nearby but not canonical truth owners
- keep Workbench/protocol/artifact actions behind state and provenance context
- introduce or refine icons, badges, progress/state indicators, and restrained transitions where they reduce first-scan effort
- mirror the same order in mobile sheets

Non-goals:
- no schema changes
- no new annotation model
- no passage anchoring
- no new runtime dependencies
- no wholesale visual restyle

## 8. Phase Plan

### Phase 0: Governance And Safety

Status:
- mostly complete through `docs/ui_references.md` and Lazyweb synthesis.

Remaining:
- add this redesign plan.
- keep Lazyweb and other reference tools developer-local only.
- keep MCP config and tokens out of git.

Exit criteria:
- reference research policy exists.
- synthesis report exists.
- redesign plan exists.
- secret/config checks pass.

### Phase 1: Audit

Create:
- `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`

Work:
- review current route hierarchy and screenshots/code paths.
- score routes against UI grammar candidates.
- inventory existing icons, badges, status colors, progress/stepper patterns, hover transitions, loading states, and visual test coverage.
- identify which candidate visual states should be adopted, revised, deferred, or rejected.
- identify the minimum viable redesign spike.

Exit criteria:
- route-level scorecard exists.
- visual-state candidate matrix has dispositions.
- `/papers/:slug` spike scope is confirmed or replaced with a better first target based on evidence.

### Phase 2: Grammar

Create:
- `docs/PaperPipe_UI_GRAMMAR.md`

Work:
- define layout zones, state language, action hierarchy, trust boundary placement, mobile ordering, and banned patterns.
- include reference pattern map.
- include icon, gauge, progress, color, emphasis, and motion semantics.
- include accepted additional redesign axes with checklists and layer classification requirements.
- include design tooling rules for Lazyweb, Figma, local primitives, shadcn/21st.dev, lucide, Tailwind, Playwright, Browser, and dependency approvals.

Exit criteria:
- each core screen family has a written grammar.
- each accepted visual-state pattern has a state meaning, text fallback, reduced-motion behavior, and verification note.
- each accepted additional axis has a first acceptable output and a guardrail.
- each allowed design tool has a clear use case, boundary, and verification requirement.
- first implementation PR can cite the grammar.

### Phase 3: Paper Detail Spike

Implement:
- route-scoped changes in `/papers/:slug`.

Verify:
- `cd frontend && npm run build`
- relevant mock and backend Playwright tests for paper detail
- mobile paper detail tests where touched
- docs lint for the matching UX report
- secret/config scan if reference docs are updated

Exit criteria:
- first scan answers: what is saved, what is evidence-backed, what needs review, what can I safely do next?
- icons, badges, gauges, and motion reduce first-scan effort without replacing text labels.
- desktop and mobile keep the same trust/action order.

### Phase 4: Propagation

Apply the proven grammar to:
- Workbench
- artifact detail family
- Home/triage recovery surface
- Paper Notes list if audit shows list-level action hierarchy remains weak

Exit criteria:
- repeated state/action vocabulary across route families.
- no route-specific redesign creates a conflicting state model.

## 9. Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Reference-driven redesign becomes visual mimicry | high | require PaperPipe route/component/layer translation before implementation |
| Generated artifact looks approved | high | state-before-action rule; no approved/promoted language without schema/API contract |
| Success color or completion gauge overstates scientific certainty | high | reserve success states for explicit reviewed/canonical contracts; pair gauges with source/review labels |
| Scope expands into rewrite | high | one route family per PR; grammar before aesthetics |
| New UI hides provenance | high | trust boundary placement rules and route tests |
| Motion distracts from reading or claim verification | medium | allow reduced motion and avoid looping animation near reading/evidence content |
| Icons become ambiguous decoration | medium | require labels/tooltips and non-color text cues for unfamiliar icons |
| Private research content leaks to reference tools | high | sanitized prompts only; no screenshots or private content |
| Existing tests fail due to broad layout churn | medium | start with paper detail spike and targeted Playwright coverage |
| Mobile order diverges from desktop trust order | medium | include mobile sheet ordering in grammar |
| Current dirty worktree causes accidental overlap | medium | keep redesign docs and PRs isolated; do not revert unrelated changes |

## 10. Verification Strategy

Docs:
- `python3 scripts/lint_docs.py docs/Reference_Driven_Redesign_Plan_2026-05-10.md`
- lint any UX report or grammar document touched by the same PR

Frontend:
- `cd frontend && npm run build`
- targeted Playwright tests for touched routes
- visual/backend coverage only when the touched surface already has visual tests or layout risk is high
- screenshot checks for visual-state changes that add new icons, gauges, progress indicators, or motion-sensitive panels
- reduced-motion and non-color-state checks when animation or color becomes part of state communication

Visual-state acceptance checklist:
- the state is understandable without color alone
- unfamiliar icons have text labels, aria labels, or tooltips
- progress/gauge math is explained by nearby copy
- loading or transition motion respects reduced-motion preferences
- success styling maps to an explicit saved/reviewed/completed contract
- warning/danger styling does not block reading unless action is genuinely unsafe
- mobile and desktop expose the same state priority

Security/config:
- scan docs and frontend diffs for tokens, MCP config, signed URLs, bearer strings, and private reference artifacts
- confirm `.lazyweb/`, MCP config files, and token filenames remain ignored

Product review:
- every implementation PR must state:
  - route/component touched
  - layer affected
  - canonical state unchanged or explicitly adopted
  - reference pattern used
  - anti-pattern avoided
  - visual state or motion semantics added
  - accessibility fallback for visual state
  - design tool or component source used, if any
  - UX report updated

## 11. PR-Sized Sequence

1. Completed: add this redesign plan.
2. Completed: add `docs/PaperPipe_Design_Identity.md`.
3. Completed: add `docs/PaperPipe_UI_GRAMMAR.md`.
4. Completed: add `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`.
5. Completed: add `docs/UX_REVIEW_REPORT_paper-detail-right-rail.md`.
6. Next: implement the `/papers/:slug` right-rail and mobile-sheet micro-spike.
7. Next: verify and compare against current route tests and screenshots.
8. Later: decide whether to propagate to Workbench, Artifact Detail, Home / Recovery, or Paper Library next.

## 12. Final Recommendation

Proceed with reference-driven redesign as a structured product-design program.

Do not proceed with a broad visual redesign or replacement UI system.

The first meaningful implementation target should be a bounded `/papers/:slug` right-rail and mobile-sheet micro-spike, not a full Paper Detail rewrite. The redesign should make PaperPipe feel less like accumulated SaaS screens and more like one local-first research workspace where evidence, provenance, review state, and safe next action are always visible.
