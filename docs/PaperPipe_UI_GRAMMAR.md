# PaperPipe UI Grammar

Status: Proposed UI grammar
Date: 2026-05-10
Owner: Frontend/product maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Operating note: `docs/PaperPipe_Minimum_Operating_Principles.md`
Related design identity: `docs/PaperPipe_Design_Identity.md`
Related page architecture: `docs/PaperPipe_Page_Architecture.md`
Related extracted data workflow: `docs/PaperPipe_Extracted_Data_Workflow_Map.md`
Related redesign plan: `docs/Reference_Driven_Redesign_Plan_2026-05-10.md`
Document map: `docs/PaperPipe_UI_Redesign_Document_Map.md`

## 1. Executive Summary

PaperPipe's UI grammar translates the product identity into implementation rules for route layout, state placement, action hierarchy, icon use, color, progress indicators, and motion.

The grammar is not a new design system and does not replace the existing `--pp-*` token system, dark-first Lattice tone, or route contracts. It is a shared rulebook for making the same research logic visible across Paper Detail, Evidence Workbench, artifact viewers, Paper Library, Home / Recovery, Settings, and future assistant surfaces.

First scan on any core screen should answer:

1. What source or evidence state exists?
2. What is generated, personal, downstream, stale, unresolved, or blocked?
3. What can the researcher safely do next?
4. Where is this data reused, and what becomes stale if upstream state changes?

Default product rhythm:

> source -> evidence -> review state -> personal memory -> downstream artifact -> guarded action

## 2. Quick Review

- Choice count: expose one dominant research action before secondary or maintenance tools.
- Benefit: use layout, labels, icons, and restrained emphasis to reveal source, state, provenance, reuse, and safe next action.
- Next action: state should appear before action; guarded actions should appear after relevant source/review context.
- Feedback: save, marker, extraction, review, regenerate, rerender, export, sync, and provider-readiness events need visible but quiet feedback.
- Ethics: generated, assistant-produced, polished, repeated, or exported content must not look stronger than upstream evidence-linked state.

## 3. Full Review

### P0

- Do not create a new runtime truth store, graph database, approval lifecycle, provider-secret surface, or assistant shell through visual design.
- Do not use `approved`, `verified`, `accepted`, `final`, `canonical approval`, or graph-truth language unless a lane-owned schema/API contract already supports it.
- Do not store provider API keys or MCP tokens in browser-owned state.
- Do not make color, motion, or visualization imply scientific truth.
- Do not send private PDFs, paper titles, lab notes, local paths, screenshots, or identifiers to external reference tools.

### P1

- Repeat stable zones: navigation/search, primary reading or review body, and a state/provenance/action rail where screen size allows.
- Keep color secondary to label, position, icon, density, and grouping.
- Prefer relationship summaries such as `source chain`, `used by`, `derived from`, `blocked by`, and `stale impact` before graph visualization.
- Use progress, gauges, and motion only for process state, coverage, readiness, or transition feedback.
- Make mobile sheets preserve the same trust order as desktop rails.

### P2

- Defer decorative polish, richer animation, advanced graph views, and assistant-first workflows until route-level state grammar is stable.
- Tune typography, density, elevation, card radius, and panel spacing after the current UI audit identifies the safest first route.

## 4. Full Review Coverage

6P storyboard context:
- Problem: PaperPipe now spans reading, evidence review, figure/table inspection, notes, markers, downstream artifacts, local runtime readiness, and future assistant support.
- Emotion: researchers need confidence and recoverability more than spectacle.
- Action: the user resumes a paper, inspects a claim, checks a figure/table, reviews an artifact, repairs stale state, or configures a local provider boundary.
- Struggle: polished artifacts, repeated extracted data, personal markers, generated summaries, and future assistant answers can blur what is source-backed.
- Attempt: use a shared grammar for source, evidence, state, reuse, action hierarchy, and visual feedback.
- Happy Ending: the user can always see where a claim/value/artifact came from, where it is reused, and what action is safe now.

BMAP:
- Motivation: high when the user is reading for evidence, preparing reuse, or avoiding stale downstream work.
- Ability: improves when every route uses familiar zones, vocabulary, icons, and state placement.
- Prompt: each screen should present one timely, state-driven prompt such as `Open review`, `Resolve source`, `Inspect evidence`, `Review stale artifact`, or `Continue reading`.

B.I.A.S:
- Block: reduce first-scan overload by hiding debug, raw traces, and maintenance controls until needed.
- Interpret: use consistent state names and consistent visual hierarchy so users do not reinterpret each page.
- Act: make the safest next action obvious; put guarded actions behind the context that justifies them.
- Store: repeat source -> evidence -> review -> artifact until users remember how PaperPipe thinks.

Peak-End:
- Peak: a user clicks a claim, figure, table, or artifact unit and reaches the upstream evidence without losing context.
- Pit: a generated or repeated downstream artifact looks more reliable because it is polished.
- Transition: Home -> Paper Library -> Paper Detail -> Evidence Workbench -> Artifact Detail should preserve paper identity, source refs, and warning state.
- End: export, sync, or handoff should end with provenance, unresolved warnings, and draft/reuse status.

Ethics:
- Regret: reduced when visual hierarchy prevents over-trust and saves review time.
- Black Mirror: risk appears if visual polish or assistant answers compound weak extraction into apparent truth.
- In Real-Life: PaperPipe should behave like a careful research collaborator that says what it knows, where it came from, and what remains unresolved.

## 5. Core Layout Grammar

### 5.1 Desktop Zones

Use three zones where the route has enough complexity:

| Zone | Purpose | Typical contents | Avoid |
| --- | --- | --- | --- |
| Left navigation/search | orientation and selection | paper list, filters, route nav, recent work, search | primary evidence truth, noisy counters |
| Center body | reading or verification work | paper text, claim list, evidence excerpts, figure/table viewport, artifact content | maintenance controls above evidence |
| Right state/provenance/action rail | trust and next action | source state, coverage, provenance, personal markers, used-by, stale impact, primary action | unrelated dashboard cards, decorative metrics |

When a route cannot support three zones, preserve the order:

1. identity and source state
2. primary content
3. evidence/provenance
4. warnings and stale impact
5. personal memory
6. next safe action
7. guarded actions
8. maintenance/debug

### 5.2 Mobile Ordering

On mobile, keep the primary reading/review body first and move rail material into a sheet or drawer.

Recommended sheet order:

1. saved/source state
2. warnings, missing source, stale, or blocked state
3. provenance/source chain
4. evidence coverage or review progress
5. used-by and stale-impact summary
6. personal markers
7. primary action
8. secondary actions
9. guarded actions
10. debug and raw traces

Do not hide P0 warnings below convenience actions.

## 6. Screen Family Grammar

### 6.1 Home / Recovery

Identity:
- resume current evidence work

First scan should answer:
- What should I continue now?
- What is blocked?
- What is ready for review or reuse?

UI grammar:
- show one current-work block before queue lenses
- use compact source, blocker, review, and reuse indicators
- use progress only for process or readiness, not research quality
- keep diagnostics and bulk maintenance secondary

### 6.2 Paper Library

Identity:
- research handoff index

First scan should answer:
- Which paper should I open, repair, or review?

UI grammar:
- each row should show source access, structured state, review state, personal markers, and next safe action
- use icons only with labels or tooltips
- filters should follow route intent: source access, review state, marker, artifact readiness
- avoid score-like ranking that implies paper quality

### 6.3 Paper Detail

Identity:
- calm reading surface with evidence-aware review bridge

First scan should answer:
- What am I reading, what state exists, and what evidence should I inspect next?

UI grammar:
- center column is for reading and evidence anchors
- right rail order: saved state, source/coverage, provenance, personal markers, used-by/stale impact, next safe action
- artifact generation stays downstream of source and review state
- assistant support stays secondary and source-routed if introduced later

### 6.4 Evidence Workbench

Identity:
- high-density evidence verification surface

First scan should answer:
- Which claim needs attention, what supports it, and what repair is safe?

UI grammar:
- use claim status icons, source-coverage strips, warning density, and review progress gauges when they reduce scanning effort
- show evidence excerpts and locators near the claim they support
- keep repair/rebuild actions behind affected-source and affected-artifact context
- avoid looping motion or animated emphasis near evidence excerpts

### 6.5 Figure / Table Evidence

Identity:
- inspect visual or tabular evidence before reuse

First scan should answer:
- Where did this figure/table come from, what claims use it, and where is it reused?

UI grammar:
- show source page, caption, locator, extraction/version state, linked claims, allowed/not-allowed claim notes, and downstream reuse
- make figure/table viewport stable and inspectable
- visual evidence review artifacts remain non-canonical unless a lane contract says otherwise

### 6.6 Artifact Detail

Identity:
- downstream artifact review and handoff surface

First scan should answer:
- What upstream evidence does this artifact use, what is stale or unresolved, and what can I safely export or rerender?

UI grammar:
- header should include artifact type, source paper(s), freshness, warning state, and draft/reuse status
- attach source refs to reusable units, not only to the whole artifact
- put export, regenerate, and rerender behind readiness, warnings, and provenance context
- avoid broad approval language

### 6.7 Research Memory / DNA

Identity:
- personal and cross-session research memory

First scan should answer:
- What should this help me remember, and what is evidence-backed versus personal?

UI grammar:
- separate personal memory from evidence validation
- show source-backed clusters only when refs are available
- avoid turning memory into a fake canonical knowledge graph

### 6.8 Runtime / Diagnostics

Identity:
- local readiness and recovery support

First scan should answer:
- Is the local workspace ready, blocked, stale, or degraded?

UI grammar:
- use steppers for setup/readiness, status badges for services, and restrained warning states for blockers
- keep noisy logs folded by default
- diagnostics should support recovery, not become the primary workspace

### 6.9 Settings / Local Secrets

Identity:
- local preference, provider boundary, and secret readiness surface

First scan should answer:
- What is configured locally, what is redacted, and what data is allowed to leave?

UI grammar:
- frontend shows redacted presence, provider mode, payload class, and same-origin server-side test status
- provider credentials belong in server-side local config, environment, or OS-keychain-style storage
- provider setup does not automatically enable live chat, RAG, or external inference
- show `local_only`, `lab_allowed`, or `external_allowed` payload boundaries before any provider action

### 6.10 Evidence-Aware Assistant

Identity:
- future source-routed support surface, not the primary shell

First scan should answer:
- What source context is in scope, what uncertainty exists, and where can I inspect the evidence?

UI grammar:
- current `/api/chat` is stub-only and must remain visually bounded
- assistant answers must carry source refs and uncertainty when live support is adopted
- assistant history is raw memory/support unless a separate contract promotes a derived artifact
- never let assistant wording outrank canonical state or evidence lineage

## 7. State Language

### 7.1 Preferred Vocabulary

Use:
- source
- evidence
- review state
- saved state
- generated
- draft-like
- unresolved
- stale
- blocked
- needs review
- ready for reuse
- personal marker
- downstream artifact

### 7.2 Use With Care

Use only with clear lane context:
- reviewed
- validated
- approved
- promoted
- verified
- complete

### 7.3 Avoid Unless Contracted

Avoid:
- canonical approval
- final truth
- accepted evidence
- confirmed claim
- approved artifact
- production-ready science

## 8. Action Hierarchy

### 8.1 Primary Actions

Primary actions should be route-specific and state-driven:
- `Continue reading`
- `Open review`
- `Inspect evidence`
- `Resolve source`
- `Review stale artifact`
- `Open source PDF`
- `Open affected artifact`

### 8.2 Secondary Actions

Secondary actions support the current loop:
- save marker
- open Workbench
- open figure/table
- open related artifact
- open references
- copy citation
- sync note

### 8.3 Guarded Actions

Guarded actions can change or export downstream state and must appear after source/review context:
- regenerate
- rerender
- export
- external inference
- provider switch
- reprocess source
- bulk maintenance

### 8.4 Maintenance And Debug

Maintenance and debug actions should be folded or placed below the primary workflow:
- raw traces
- logs
- schema payloads
- environment diagnostics
- batch cleanup

## 9. Visual State System

### 9.1 Priority Order

Use cues in this order:

1. label
2. placement
3. grouping
4. density or scale
5. icon
6. color
7. motion

Color and motion are third cues, not the main meaning.

### 9.2 Icon Semantics

Use `lucide-react` icons where the existing frontend already supports them. Icons should usually appear with text labels, tooltips, or accessible names.

Suggested semantic roles:

| Meaning | Icon role | Notes |
| --- | --- | --- |
| source document | document/file icon | never means canonical truth alone |
| reading | book/text icon | for paper body or note context |
| evidence link | link/anchor icon | should open source or evidence detail |
| warning | warning triangle icon | pair with text and severity |
| stale/rebuild | refresh/history icon | pair with affected downstream count |
| local/private | shield/lock icon | use for local-first boundary |
| personal marker | star/bookmark icon | memory, not validation |
| generated artifact | layers/package icon | downstream, draft-like unless contracted |
| export | outbound/share icon | guarded when provenance matters |
| assistant | message icon | support surface, not truth source |

### 9.3 Color Roles

Keep a small color vocabulary:

| Role | Meaning | Guardrail |
| --- | --- | --- |
| neutral | default reading, inactive state, ordinary metadata | should dominate the UI |
| accent | active context, selected evidence, navigable focus | avoid using as generic decoration |
| warning | unresolved, stale, missing, partial, needs review | pair with label/icon |
| danger | destructive, blocked, unsafe, external-send risk | use sparingly |
| limited success | saved, completed process, local readiness | never means scientific truth |

Do not assign separate colors per artifact family, marker type, relation type, graph edge, or paper category.

### 9.4 Progress And Gauges

Allowed when the label says exactly what is being measured:
- import progress
- parsing progress
- artifact generation progress
- review progress
- source coverage
- evidence coverage
- warning density
- local readiness
- sync/readiness state

Avoid:
- `truth score`
- `quality score`
- generic confidence meter
- paper importance score
- graph centrality score
- success gauge that means scientific validation

### 9.5 Motion

Allowed motion:
- save confirmation
- marker toggled feedback
- loading or step progress
- panel/sheet reveal
- guarded action reveal
- stale impact expansion
- completion confirmation

Motion rules:
- keep motion short, quiet, and interruptible
- honor reduced-motion preferences
- do not loop decorative motion near reading text, evidence excerpts, or claim review controls
- do not use motion to create false urgency

### 9.6 Emphasis

Use emphasis for:
- current source context
- unresolved blocker
- stale downstream impact
- selected evidence anchor
- active review item
- guarded external-send boundary

Avoid emphasis for:
- decorative cards
- fake KPI dashboards
- assistant output without source refs
- repeated extracted data that does not add evidence strength

## 10. Relationship And Reused Data Grammar

Use route-level summaries before any broad graph UI.

Core patterns:

| Pattern | Answers | Placement |
| --- | --- | --- |
| Source Chain | Where did this item come from? | right rail, detail header, artifact unit |
| Used By | Where is this item reused? | right rail, artifact/source detail |
| Impact Of Change | What becomes stale if this changes? | warning section before repair/regenerate/export |
| Evidence Coverage | Which claims or units have source refs? | rail, Workbench strip, artifact header |

Rules:
- repeated downstream use does not increase evidence confidence
- relationship summaries are navigation aids, not truth owners
- derived relationship indexes, if added later, must be rebuildable and non-canonical
- do not ask users to maintain low-level relation edges manually during reading

## 11. Component And Dependency Rules

Prefer current local primitives and patterns:
- existing `--pp-*` and `--pp-status-*` tokens
- Tailwind utilities already used by the frontend
- `lucide-react` icons
- local badges, chips, rails, panels, steppers, tabs, sheets, and timelines
- vendored `shadcn/ui`-style primitives under `frontend/src/app/components/ui/` when local primitives are insufficient

21st.dev or other registry components may be used only when:
- the component solves a real local UI gap
- styling is adapted to `--pp-*` tokens and dark-first Lattice tone
- demo content, remote assets, telemetry, and unnecessary dependencies are removed
- source URL, modifications, and verification are recorded in the matching UX review report

Requires explicit approval before keeping:
- `framer-motion`
- `motion`
- `three`
- heavy visualization libraries
- analytics SDKs
- trackers
- non-allowlisted runtime dependencies

## 12. Accessibility And Usability Requirements

Every state cue needs a non-color fallback:
- label
- icon
- tooltip
- accessible name
- placement
- summary text

Additional requirements:
- preserve keyboard focus order through rails, sheets, and guarded actions
- keep touch targets stable on mobile
- avoid text overlap and clipped labels
- keep dynamic status text within fixed or constrained containers
- use truncation only when full text remains discoverable
- do not scale font size with viewport width
- avoid negative letter spacing
- honor reduced-motion preferences

## 13. Banned Patterns

Do not introduce:
- generic SaaS dashboard as the main product shape
- landing-page hero inside the research workspace
- decorative gradient/orb backgrounds
- dashboard card sprawl
- color per artifact family, marker type, relation type, or graph edge
- graph visualization that implies truth ownership
- broad approval/promote/final states
- chat-first shell
- browser-owned provider keys
- external reference outputs as product requirements
- motion that competes with reading
- fake project KPIs or fake approval queues

## 14. Implementation Gate

Before a UI implementation PR:

- cite the relevant section of this grammar
- cite the target route's UX review report
- identify the data layer: raw source, raw memory, compiled knowledge, canonical structured state, review/gate artifact, or user-facing artifact/export
- identify whether relationship UI is source chain, used by, impact of change, or coverage
- confirm no unapproved runtime dependency is added
- confirm color and motion have non-color and reduced-motion fallbacks
- confirm secrets remain out of browser-owned state
- run the smallest relevant verification for the touched surface

## 15. Next PR-Sized Actions

1. Create `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`.
   - Score existing routes against this grammar, page architecture, extracted-data workflow, and visual-state rules.

2. Choose the first route spike from the audit.
   - Default candidate remains `/papers/:slug`, but the audit may identify a safer first route.

3. Prepare the first bounded UI spike.
   - Scope to one route family or one shared primitive, and avoid broad redesign churn.
