# PaperPipe Page Architecture

Status: Proposed page architecture
Date: 2026-05-10
Owner: Frontend/product maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Related design identity: `docs/PaperPipe_Design_Identity.md`
Related redesign plan: `docs/Reference_Driven_Redesign_Plan_2026-05-10.md`
Related extracted data workflow: `docs/PaperPipe_Extracted_Data_Workflow_Map.md`
Document map: `docs/PaperPipe_UI_Redesign_Document_Map.md`

## 1. Executive Summary

PaperPipe should be organized around a small number of stable page families, not a growing pile of feature screens.

The page model should make the research loop legible:

> recover current work -> choose a paper -> read with evidence context -> verify claims -> review downstream artifacts -> recover local runtime issues.

The page model should also make extracted data reuse legible:

> source -> extracted structure -> claim/evidence -> review artifact -> downstream artifact -> used-by / stale-impact summary.

Recommended page families:

1. Home / Recovery
2. Paper Library
3. Paper Detail
4. Evidence Workbench
5. Figure / Table Evidence
6. Artifact Detail
7. Research Memory / DNA
8. Runtime / Diagnostics
9. Settings / Local Secrets
10. Evidence-Aware Assistant

These page families are product information-architecture categories. They do not imply that every family should become a new route immediately, or that all families should be implemented in the first redesign pass.

The first implementation priority should be:

1. Paper Detail
2. Evidence Workbench
3. Artifact Detail
4. Home / Recovery
5. Paper Library

Do not redesign every route at once. The safest route is to define the shared page grammar, run the current UI audit, then run one bounded spike, likely `Paper Detail`, and propagate only the parts that prove useful.

## 2. Quick Review

- Choice count: each page should expose one primary research loop and no more than a few visible next actions.
- Benefit: every page should answer what the researcher can safely read, verify, repair, recover, or reuse now.
- Next action: state should appear before action; guarded actions should follow source and review context.
- Feedback: save, sync, import, review, repair, regenerate, rerender, and export actions need visible feedback.
- Ethics: no page should make generated, polished, or assistant-produced content appear stronger than upstream evidence.

## 3. Full Review

### P0

- Keep source, evidence, canonical structured state, personal memory, generated artifact, review cue, and export visually distinct.
- Keep extracted data reuse visible enough to trace, but subordinate to canonical paper/job/artifact ownership.
- Avoid broad `approved`, `verified`, `accepted`, or `final` language unless a lane-owned contract explicitly supports it.
- Keep local-first and payload boundaries visible where data leaves, syncs, exports, or passes through assistant-like surfaces.
- Do not let dashboard counters become fake project state or fake approval queues.
- Do not let assistant UI become the primary product shell.

### P1

- Use a repeated three-zone grammar where useful: navigation/search, primary reading/review body, state/provenance/action rail.
- Use icons, badges, progress, gauges, and color only when they clarify source, state, warning, progress, or safe next action.
- Make `Paper Detail` the calm reading center and `Evidence Workbench` the high-density verification center.
- Put artifact reuse behind visible upstream source and warning context.
- Use progressive disclosure for legends, debug traces, raw provenance, and advanced filters.

### P2

- Add richer motion only for state changes, save confirmation, panel reveal, progress, and guarded action transitions.
- Add keyboard or command shortcuts after page hierarchy is stable.
- Add visual polish after state language and action hierarchy are consistent.

## 4. Full Review Coverage

6P storyboard context:
- Problem: PaperPipe now spans reading, claim review, figures, notes, downstream artifacts, sync, and future assistant support, but these surfaces need a shared page model.
- Emotion: a researcher wants confidence, not spectacle. They need to know what is sourced, unresolved, and safe to use.
- Action: the user opens a workspace, resumes a paper, checks evidence, repairs a gap, or reviews an artifact.
- Struggle: too many panels, counters, and generated outputs can blur what is true, reviewed, personal, or draft-like.
- Attempt: define stable page families and page-level content rules before broad redesign.
- Happy Ending: every screen makes source -> evidence -> review -> artifact visible without forcing the user to relearn the product.

BMAP:
- Motivation: high, because the product's value is strongest when evidence state is legible.
- Ability: improves when pages share stable zones, vocabulary, icon semantics, and action hierarchy.
- Prompt: each page should present one state-driven primary action at the moment the user needs it.

B.I.A.S:
- Block: reduce first-scan overload by giving each page one dominant question.
- Interpret: use consistent state language and consistent placement for provenance and safe actions.
- Act: keep guarded actions behind the state that justifies them.
- Store: repeat the same trust rhythm until the user remembers how PaperPipe thinks.

Peak-End:
- Peak: the user clicks a claim or figure anchor and sees source, evidence, state, and next action without losing reading context.
- Pit: polished generated artifacts or assistant answers look more certain than they are.
- Transition: Home -> Paper Library -> Paper Detail -> Workbench -> Artifact Detail should preserve paper identity and evidence state.
- End: export or handoff should end with a provenance summary and unresolved warning context.

Ethics:
- Regret: reduced when the UI prevents over-trust and saves review time.
- Black Mirror: risk appears when AI/chat/generated artifacts outrank source-backed evidence.
- In Real-Life: PaperPipe should behave like a careful research collaborator, not a dashboard trying to create activity.

## 5. Page Families

### 5.1 Home / Recovery

Current route:
- `/`

Primary identity:
- resume the current evidence thread

Primary user question:
- What should I safely continue now?

Must contain:
- current or last active paper
- blocked source or review gaps
- small queue lens for repair, review, and reusable artifacts
- local-first and sync/readiness status
- recently touched papers or artifacts
- one primary continuation action

Important UI elements:
- compact current-work panel
- state badges for source availability, unresolved claims, stale artifacts, and blocked imports
- small progress or coverage indicators labeled as progress or coverage, not truth
- icon-led queue states
- restrained save/sync feedback

Primary action:
- `Open review` or `Continue reading`

Secondary actions:
- `Resolve sources`
- `Open paper`
- `Open artifact`
- `View all papers`

Guarded or lower-priority actions:
- artifact generation
- export
- bulk maintenance
- runtime diagnostics

State and provenance rules:
- counters must reflect real state, not aspirational project status
- `Ready` must mean ready for a bounded action, not scientifically validated
- local-first status should be visible but not dominate the reading loop

Avoid:
- generic SaaS KPI dashboard
- project management board
- activity feed as the main product
- large decorative hero
- fake approval queues

First PR-sized target:
- make the first panel a continuation surface for one paper, one blocker, and one next safe action.

### 5.2 Paper Library

Current route:
- `/papers`

Primary identity:
- research handoff index

Primary user question:
- Which paper should I open, repair, or review?

Must contain:
- searchable paper list
- paper title, authors, year, venue
- source access state
- structured state availability
- review state or unresolved count
- personal markers such as star, priority, note, or label
- next safe action per row
- saved filters for source access, review state, markers, and artifact readiness

Important UI elements:
- dense but readable table/list rows
- source icons with text labels or tooltips
- coverage meter only when it is clearly labeled as claim/source coverage
- marker icons for personal memory
- progressive filter drawer or collapsible filter bar
- compact legend, hidden by default after first use

Primary action:
- `Open paper`

Secondary actions:
- `Open review`
- `Check access`
- `Open Workbench`
- `Open note`

Guarded or lower-priority actions:
- import/reprocess
- bulk tag operations
- artifact creation

State and provenance rules:
- personal markers must not look like evidence validation
- source access must distinguish local PDF, open access, limited access, missing, and unknown
- structured state should indicate whether canonical state exists, is stale, or needs repair

Avoid:
- generic database table clone
- file-browser-only UI
- exposing every filter all the time
- assistant filters before assistant runtime exists
- score-like ranking that implies paper quality

First PR-sized target:
- align row state vocabulary and next-action hierarchy with Paper Detail and Workbench.

### 5.3 Paper Detail

Current route:
- `/papers/:slug`

Primary identity:
- calm reading surface with evidence-aware review bridge

Primary user question:
- What am I reading, what state exists, and what evidence should I inspect next?

Must contain:
- title, authors, venue, year, DOI or source identifier
- local/source access indicator
- reading tabs or sections: abstract, content, figures, tables, references, supplementary, notes
- readable paper content or extracted sections
- evidence anchors for claims, figures, tables, or passages when available
- right rail for saved state, claim/source coverage, provenance, personal markers, and next safe actions
- link back to source PDF
- link into Evidence Workbench

Important UI elements:
- readable center column
- evidence anchor chips or margin markers
- right-rail state cards
- source provenance mini-timeline
- personal marker controls with clear separation from review state
- coverage bar labeled `coverage, not truth`
- subtle save feedback

Primary action:
- `Open review`

Secondary actions:
- `Reopen source PDF`
- `Open Workbench`
- `Save marker`
- `Open figure/table`
- `Open references`

Guarded or lower-priority actions:
- create protocol draft
- build meeting pack
- export notes
- assistant-generated synthesis

State and provenance rules:
- reading text and extracted text must not be presented as canonical source unless the source layer is clear
- generated summaries should stay visually downstream from source/evidence
- claim coverage does not equal claim truth
- personal markers are memory, not review state

Avoid:
- turning paper detail into an all-purpose control panel
- putting artifact generation above source review
- chat as the first viewport
- decorative motion near reading text
- one-click trust language

First PR-sized target:
- reorganize the right rail into saved state, coverage, provenance, personal markers, and next safe action.

### 5.4 Evidence Workbench

Current route:
- `/workbench/:paperId`

Primary identity:
- high-density evidence verification surface

Primary user question:
- Which claims are sourced, unresolved, stale, or blocked, and what evidence should I inspect?

Must contain:
- selected paper identity
- source PDF or extracted excerpt panel
- claim list or claim review panel
- evidence refs, figure/table refs, source snippets, and provenance
- unresolved, missing source, conflict, stale, or warning states
- repair or rebuild steps
- artifact links when downstream artifacts exist
- local save/review state feedback

Important UI elements:
- side-by-side source and claim review
- claim status icons
- source coverage strip
- warning density indicator
- repair/rebuild stepper
- evidence excerpt highlight
- provenance footer or side rail

Primary action:
- `Verify claim` or `Open excerpt`

Secondary actions:
- `Needs source`
- `Repair source`
- `Rebuild claimset`
- `Open artifact`
- `Open paper detail`

Guarded or lower-priority actions:
- regenerate claimset
- build chart pack
- build meeting draft
- export

State and provenance rules:
- use `Sourced`, `Needs review`, `Partial source`, `Conflict`, `No source`, `Stale`, and `Blocked` before stronger truth language
- avoid `Supported` or `Approved` unless backed by an adopted review contract
- warning density and review progress are not scientific certainty scores

Avoid:
- parser/debug controls as the main first scan
- dense artifact actions before claim state
- animated effects over evidence text
- generated claim text outranking source excerpts

First PR-sized target:
- rename and visually separate claim state, source coverage, and repair actions.

### 5.5 Figure / Table Evidence

Current routes:
- `/image-evidence`
- `/image-evidence/:imageEvidenceId`
- figure/table tabs within `/papers/:slug`
- figure/table evidence surfaces linked from Workbench

Primary identity:
- inspect visual evidence before reuse

Primary user question:
- What figure or table am I inspecting, where did it come from, and can it support this claim or artifact?

Must contain:
- paper identity
- figure/table identifier
- source page, caption, and extracted image/table
- linked claims or artifacts
- provenance from source PDF to extracted visual state
- warnings for OCR, crop, caption mismatch, resolution, or missing source
- reuse boundary

Important UI elements:
- visual preview with stable aspect ratio
- caption/source metadata panel
- linked claim chips
- provenance timeline
- warning severity badges
- version or viewport indicator

Primary action:
- `Inspect source`

Secondary actions:
- `Open linked claim`
- `Open Workbench`
- `Use in artifact`
- `Mark issue`

Guarded or lower-priority actions:
- export image
- regenerate visual extraction
- assistant interpretation

State and provenance rules:
- visual extraction is derived state, not source truth
- image interpretation must not become canonical through styling
- every reuse action should preserve source paper, figure/table id, extraction version, and warning state

Avoid:
- image gallery without provenance
- decorative thumbnails detached from source
- AI interpretation presented as caption truth
- color-only warning states

First PR-sized target:
- create a figure/table evidence review pattern that can be reused by Paper Detail and Workbench.

### 5.6 Artifact Detail

Current routes:
- `/meeting-packs`
- `/meeting-packs/:packId`
- `/method-comparisons`
- `/method-comparisons/:comparisonId`
- `/chart-packs`
- `/chart-packs/:chartPackId`
- `/protocol-cards`
- `/protocol-cards/:protocolId`

Primary identity:
- downstream review and reuse surface

Primary user question:
- Where did this artifact come from, what warnings remain, and what can I safely reuse or export?

Must contain:
- artifact title, type, id, version, owner, created/updated timestamps
- artifact purpose and intended use
- upstream paper, claimset, source selectors, or notes
- preview body
- metadata, provenance, files, history, and diff tabs where applicable
- source coverage and warning density indicators
- trace/provenance timeline
- guarded maintenance steps
- export or handoff boundary

Important UI elements:
- artifact header context
- downstream-from-source banner
- preview canvas or structured artifact body
- readiness or warning indicators labeled as reuse readiness, not truth
- provenance timeline
- diff/history controls
- guarded export/regenerate/rerender actions

Primary action:
- `Review source`

Secondary actions:
- `Open Workbench`
- `Open Paper Detail`
- `View provenance`
- `View diff`
- `Export with provenance`

Guarded or lower-priority actions:
- regenerate
- rerender
- share
- overwrite existing output

State and provenance rules:
- artifact readiness is not claim truth
- generated artifacts remain draft-like unless a contract says otherwise
- export must carry provenance summary and warning context
- history/diff should distinguish generated changes from manual edits

Avoid:
- polished artifact preview detached from source
- fake approval workflow
- export button above warning/source context
- success color implying scientific validation

First PR-sized target:
- standardize artifact header, upstream source strip, warning summary, and guarded action area across artifact routes.

### 5.7 Research Memory / DNA

Current status:
- represented in navigation and product language, but not yet a clearly isolated route family in the current `App.tsx` route list.

Primary identity:
- personal and derived research memory map

Primary user question:
- What patterns, topics, markers, or recurring evidence threads have emerged across my local workspace?

Must contain:
- topic clusters or research threads when backed by state
- starred papers and personal markers
- recurring methods, claims, figures, or artifact families
- links back to paper detail and Workbench
- clear distinction between personal memory, compiled knowledge, and canonical structured state

Important UI elements:
- graph or cluster visualization only when backed by explicit data
- marker legend
- source-backed counts
- links to evidence-bearing surfaces
- uncertainty and source-gap indicators

Primary action:
- `Open evidence thread`

Secondary actions:
- `Open paper`
- `Open claim`
- `Open artifact`
- `Refine marker`

Guarded or lower-priority actions:
- generate synthesis
- export research map
- assistant summary

State and provenance rules:
- Research DNA is not canonical truth unless adopted by schema/API contract
- clusters should explain their source basis
- personal and generated memory must remain separate from evidence validation

Avoid:
- decorative graph with no source backing
- knowledge graph theater
- ranking papers by importance without user or source basis
- assistant-generated themes as product truth

First PR-sized target:
- defer route implementation until the data layer and state boundaries are explicit.

### 5.8 Runtime / Diagnostics

Current route:
- `/ready`

Primary identity:
- local machine trust and recovery support

Primary user question:
- Is this machine ready, and what should I fix to get back to reading or review?

Must contain:
- backend/API readiness
- import/index readiness
- PDF viewer readiness
- claim extraction and artifact writer readiness
- Obsidian sync state
- chat hook or assistant readiness when applicable
- payload boundary status
- recovery actions
- recent checks
- system snapshot

Important UI elements:
- readiness stepper
- local/external payload boundary badges
- clear warning rows
- recovery action cards
- recent checks table
- compact diagnostics details

Primary action:
- `Run diagnostics` or the most relevant recovery action

Secondary actions:
- `Restart backend`
- `Open Paper Notes`
- `View logs`
- `Check sync`

Guarded or lower-priority actions:
- external configuration
- reset/rebuild cache
- destructive maintenance

State and provenance rules:
- payload boundaries must use exact labels such as `local_only`, `lab_allowed`, and `external_allowed` when backed by policy
- external network state must never be implied as enabled unless it is actually enabled
- chat should remain `stub-only` while the API contract says so

Avoid:
- making diagnostics the main product experience
- noisy developer logs as first scan
- vague trust language
- hidden external calls

First PR-sized target:
- keep runtime readiness as a support page, with clear links back to Paper Detail and Workbench.

### 5.9 Settings / Local Secrets

Current status:
- represented in navigation, but not yet a dedicated route in the current `App.tsx` route list.

Recommended route:
- `/settings`

Primary identity:
- local configuration and secret boundary control

Primary user question:
- What personal settings, local runtime choices, and AI provider credentials are configured on this machine?

Must contain:
- user profile basics for local display, such as name, initials, workspace label, and preferred display density
- local workspace paths and Obsidian sync target summary
- AI provider selection, such as local, cloud, or hybrid mode
- model slots, such as reader, judge, embedder, and future assistant model
- API key presence status for provider secrets
- secret source indicator, such as environment variable, local config, OS keychain, or not configured
- payload boundary policy summary for `local_only`, `lab_allowed`, and `external_allowed`
- test connection action that runs server-side and returns redacted status only
- clear explanation of what data may be sent when external inference is enabled
- reset, remove, or rotate credential actions

Important UI elements:
- Settings groups for `Profile`, `Workspace`, `Models`, `Secrets`, `Payload Boundaries`, and `Advanced`
- redacted secret fields, for example last 4 characters only when safe
- provider status badges, such as `Not configured`, `Configured locally`, `Env var`, `Keychain`, `Disabled by policy`
- local-first warning strip when a cloud provider is enabled
- guarded reveal for advanced model and payload settings
- confirmation dialog for removing or replacing credentials

Primary action:
- `Save local settings`

Secondary actions:
- `Test provider`
- `Use local model`
- `Set provider key` through a server-handled credential dialog
- `Remove key`
- `Open Runtime`

Guarded or lower-priority actions:
- enable external inference
- switch from local to cloud mode
- widen payload class
- clear local workspace paths
- reset all settings

State and provenance rules:
- the browser must not own backend or provider secrets
- credentials should be stored in backend-controlled local config, OS keychain, or environment variables, not in `localStorage`, frontend env, committed config, or exported docs
- any backend-controlled local secret file must be gitignored, covered by secret scanning, and excluded from reference/debug artifacts
- the frontend may show only redacted credential status
- provider test requests must be same-origin and server-side
- changing provider mode does not automatically enable chat, RAG, or assistant runtime
- external inference requires explicit payload classification before any non-local transfer path exists
- user profile information is personal memory or local preference, not canonical research state

Avoid:
- storing API keys in browser state, query strings, logs, screenshots, telemetry, or Vite `VITE_*` variables
- sending a full PDF, full notes, lab context, or raw memory to test a provider
- implying cloud mode is required
- burying external-call warnings behind advanced settings
- making settings the place where scientific trust decisions are made

First PR-sized target:
- add a settings architecture spec and backend secret-storage decision before implementing the route.

### 5.10 Evidence-Aware Assistant

Current status:
- future embedded surface; `/api/chat` is currently stub-only under `docs/API_CHAT_CONTRACT.md`

Primary identity:
- source-routed support panel, not a product shell

Primary user question:
- What does the current source-backed state say, what is uncertain, and what should I inspect next?

Must contain:
- answer scope
- source basis
- linked claims, figures, tables, notes, or artifacts
- uncertainty or source-gap statement
- next safe action
- payload boundary
- clear indication of whether the answer uses canonical state, generated artifacts, personal memory, or background context

Important UI elements:
- side panel embedded in Paper Detail, Workbench, or Artifact Detail
- source chips
- uncertainty block
- next-action suggestions
- copy/save feedback only for user-owned notes
- disabled or stub-only state when backend is not enabled

Primary action:
- `Open source`

Secondary actions:
- `Show unresolved evidence`
- `Reopen PDF`
- `Compare before/after repair`
- `Draft note with provenance`

Guarded or lower-priority actions:
- send external request
- generate synthesis
- save answer as artifact
- export chat

State and provenance rules:
- assistant answers are support, not canonical truth
- chat history is raw memory/support unless a separate contract promotes a derived artifact
- external payload class must be visible before any non-local transfer path exists

Avoid:
- chat-first application shell
- ungrounded biomedical answer engine
- assistant answer cards that look more authoritative than source evidence
- hidden external transfer
- using chat to replace Paper Detail, Workbench, or Artifact Detail

First PR-sized target:
- design the assistant boundary states before implementing the assistant runtime UI.

## 6. Cross-Page Information Architecture

### 6.1 Navigation Groups

Recommended groups:

Research:
- Home
- Papers
- Workbench
- Figure Evidence

Artifacts:
- Meeting Packs
- Protocol Cards
- Chart Packs
- Method Comparisons

Memory:
- Notes
- Starred
- Research DNA

System:
- Runtime
- Sync
- Settings

Rules:
- route labels should match what the user is trying to do, not internal backend names
- group labels should stay quiet and not compete with the active page
- assistant should not be a primary navigation item until it has a first-class runtime contract
- Settings may expose credential status and provider selection, but must not expose raw secrets to browser-owned state

### 6.2 Shared Layout Zones

Left zone:
- navigation
- search or paper list when the page is paper-centric
- recent items or collection context

Center zone:
- reading content
- source PDF or excerpt
- claim review body
- artifact preview
- runtime readiness table

Right zone:
- saved state
- source coverage
- provenance
- warnings
- personal markers
- next safe action
- guarded maintenance actions

Mobile rule:
- center content remains first
- right-zone state appears as a sheet or drawer
- guarded actions stay below state and warnings
- debug details and legends remain collapsed

### 6.3 State Language

Preferred:
- `Saved`
- `Local PDF`
- `Open access`
- `Source missing`
- `Structured state`
- `Generated`
- `Draft`
- `Needs review`
- `Unresolved`
- `Conflict`
- `Stale`
- `Blocked`
- `Personal marker`
- `Ready for reuse`

Use with care:
- `Reviewed`
- `Verified`
- `Supported`
- `Complete`
- `Ready`

Avoid unless explicitly contracted:
- `Approved`
- `Accepted`
- `Final`
- `Truth`
- `Validated`
- `Confirmed`
- `Promoted`

### 6.4 Visual State Rules

Icons:
- use icons as scan aids with text labels or tooltips
- use consistent meanings for source, claim, evidence, warning, stale, local, external, personal marker, generated artifact, and export

Progress:
- allowed for import, parse, generation, source coverage, review progress, warning density, sync, and runtime readiness
- must be labeled as progress, coverage, density, or readiness
- must not imply scientific truth

Color:
- use color as a third cue after label and icon, not as the primary state language
- keep the default page mostly neutral
- use the existing accent sparingly for active route, active tab, focused evidence link, or primary action
- use warning color for needs-review, uncertainty, partial source, stale, or caution states
- use danger color only for blocked, missing, failed, or destructive states
- use success color narrowly for saved, completed, locally healthy, or available states; never for scientific truth
- avoid separate colors for every artifact family, marker type, graph edge, or relationship type
- personal markers may use accent treatment, but should rely on icon, label, or shape before extra color

Motion:
- allowed for save feedback, loading, panel reveal, progress update, guarded action reveal, and completion confirmation
- avoid looping motion near reading text or evidence excerpts
- respect reduced-motion preferences

## 7. Implementation Order

1. Define shared UI grammar.
   - create `docs/PaperPipe_UI_GRAMMAR.md`
   - include state vocabulary, layout zones, visual state semantics, mobile ordering, and banned patterns

2. Run current UI reality audit v2.
   - create `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`
   - score each current route against this page architecture

3. Spike Paper Detail.
   - reorganize right rail and evidence anchors
   - add a compact downstream `used by` summary for claims, figures, tables, or extracted values when the data exists
   - keep artifact generation secondary
   - verify text density and mobile sheet ordering

4. Spike Evidence Workbench.
   - separate claim state, source coverage, warnings, and repair actions
   - show stale-impact or affected-artifact cues before repair/regenerate actions
   - avoid over-strong truth language

5. Standardize Artifact Detail.
   - create shared header/source/warning/action pattern across artifact routes
   - show source refs, reuse dependencies, and stale/drift status before export or rerender

6. Simplify Home and Paper Library.
   - make Home a recovery surface
   - make Paper Library a handoff index, not a dashboard or database clone

7. Add assistant boundary UI only after the API/runtime contract changes.
   - do not let future assistant plans drive current page architecture beyond reserved panel space and boundary rules

8. Add Settings / Local Secrets only after a backend-owned secret-storage contract exists.
   - do not store provider keys in browser state or frontend environment variables
   - expose redacted provider readiness and payload-boundary state to the UI

## 8. Acceptance Checklist

For every page redesign PR:

- the page's primary user question is visible in the first scan
- source, evidence, state, provenance, and action are visually separable
- generated/draft/personal memory states cannot be mistaken for canonical truth
- one primary action dominates
- guarded actions appear after warnings and provenance
- color is not the only state cue
- progress/gauge labels avoid truth-score interpretation
- mobile ordering preserves the same evidence hierarchy
- relevant UX review report exists or is updated
- no new runtime dependency is added without explicit approval
- no external reference result is treated as product truth without review
- settings and provider UI never expose raw secrets in frontend state, logs, or committed files

## 9. Next PR-Sized Actions

1. Create `docs/PaperPipe_UI_GRAMMAR.md` from this page architecture and the design identity.
2. Create `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md` and score the current routes.
3. Start the first implementation spike on `/papers/:slug`, focused on right-rail state/provenance/action hierarchy.
