# PaperPipe Design Identity

Status: Proposed design identity
Date: 2026-05-10
Owner: Frontend/product maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Related operating note: `docs/PaperPipe_Minimum_Operating_Principles.md`
Related redesign plan: `docs/Reference_Driven_Redesign_Plan_2026-05-10.md`
Related page architecture: `docs/PaperPipe_Page_Architecture.md`
Related extracted data workflow: `docs/PaperPipe_Extracted_Data_Workflow_Map.md`
Document map: `docs/PaperPipe_UI_Redesign_Document_Map.md`

## 1. Executive Summary

PaperPipe's design identity should be defined before the reference-driven redesign proceeds.

The product should not look or behave like a generic SaaS dashboard, citation manager clone, Notion database, AI chat wrapper, LIMS/ELN replacement, or broad approval workflow platform.

PaperPipe should feel like:

> a local-first biomedical evidence workspace where a researcher can read a paper, inspect claim support, understand uncertainty, preserve personal memory, and reuse downstream artifacts without losing provenance.

The core design promise:

> You can always see where a claim came from, what state it is in, and what safe action comes next.

For extracted data, the matching promise is:

> You can see where a value, figure, table, claim, or artifact came from, where it is reused, and what becomes stale if it changes.

## 2. Quick Review

- Choice count: screens should expose one dominant research loop before secondary tools.
- Benefit: the product should make evidence state and provenance easier to see, not merely make screens prettier.
- Next action: every core surface should answer what the researcher can safely read, verify, repair, recover, or reuse now.
- Feedback: save, review, generation, sync, export, and marker actions should produce visible state feedback.
- Ethics: generated artifacts, polished charts, translations, and summaries must never look more certain than their upstream evidence.

## 3. Full Review

P0:
- Preserve local-first ownership and schema-backed canonical state.
- Keep generated outputs visually and semantically draft-like until a lane-owned review contract says otherwise.
- Keep personal memory separate from evidence truth.
- Keep downstream artifacts visibly downstream.
- Do not let external references define PaperPipe's identity.

P1:
- Use references for patterns, not personality.
- Make PaperPipe's shared grammar: source -> evidence -> review -> artifact.
- Prefer calm precision over spectacle.
- Prefer labels, layout, and grouping first; use icons as secondary scan aids; use color and motion only as restrained third cues when they shorten the path to understanding state.

P2:
- Tune typography, density, spacing, elevation, and motion after the identity and UI grammar are stable.
- Allow richer visual polish only when it reinforces source, state, confidence, recovery, or safe next action.

## 4. Product Archetype

Primary archetype:
- local-first biomedical evidence workspace

Adjacent but not primary:
- paper reader
- evidence workbench
- artifact review surface
- personal research memory
- local assistant workspace
- evidence-aware assistant panel

Explicitly not:
- generic SaaS dashboard
- citation manager clone
- Notion database clone
- AI chat wrapper
- lab LIMS/ELN replacement
- approval workflow platform
- marketing website
- file browser
- BI dashboard

## 5. Visual Personality

PaperPipe should feel:
- calm
- precise
- evidence-forward
- dense but ordered
- dark-first but not gloomy
- technical but humane
- cautious about certainty
- local and private without feeling isolated
- capable without feeling like enterprise surveillance

PaperPipe should not feel:
- flashy
- decorative
- gamified
- generic enterprise SaaS
- clinical EMR
- marketing-led
- chat-first
- dashboard-first
- approval-theater-heavy

## 6. Interaction Personality

PaperPipe should:
- show source before polish
- show extracted-data lineage before reuse
- show review state before action
- use motion as confirmation, not spectacle
- use color as state, not decoration
- use icons as scan aids, not hidden meaning
- treat personal notes and markers as memory, not truth
- treat assistant answers as source-routed support, not product truth
- keep generated outputs useful but visibly bounded
- make recovery paths easy to find
- prefer reversible and explicit operator actions

PaperPipe should avoid:
- primary CTAs that skip evidence context
- chat UI that becomes the primary shell
- assistant answers that outrank canonical state or upstream evidence
- one-click trust language
- browser-stored provider secrets
- success color that means "scientifically true"
- animated loops near reading text or evidence excerpts
- dashboard counters that imply project/workspace state not backed by runtime contracts
- broad approval language without lane-owned lifecycle

## 7. Trust Rules

1. Generated is not reviewed.
2. Reviewed is not canonical unless the schema/API contract says so.
3. Exported is not automatically approved.
4. Personal markers are not evidence validation.
5. Translated or assisted display is not canonical source text.
6. Artifact readiness is not claim truth.
7. Local state remains owner.
8. External reference never becomes product truth.
9. Assistant answers are not stronger than canonical state or evidence lineage.
10. Chat history is raw memory/support unless a separate contract promotes a derived artifact.
11. Duplicate downstream use does not increase evidence confidence.
12. Relationship graphs are navigation aids, not truth owners.

## 8. State Language

Preferred presentation vocabulary:
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

Use with care:
- reviewed
- validated
- approved
- promoted
- verified
- complete

Avoid unless backed by a lane-owned contract:
- canonical approval
- final truth
- accepted evidence
- confirmed claim
- approved artifact
- production-ready science

## 9. Visual System Direction

Use:
- existing `--pp-*` tokens
- dark-first Lattice tone
- restrained contrast
- visible but quiet status colors used sparingly
- a mostly neutral interface where layout, labels, icons, and density carry most meaning
- compact icon + label pairs
- local primitives before new components
- badges, strips, rails, steppers, and timelines when they carry state
- progressive disclosure for raw traces, debug details, and lower-priority provenance

Avoid:
- ornamental gradient blobs
- marketing hero patterns
- dashboard card sprawl
- large decorative illustrations in core research screens
- brand mimicry from reference products
- color-only state communication
- separate colors for every status, artifact family, relationship type, or marker type
- multi-color dashboards where the palette competes with evidence
- motion that competes with reading

## 10. Screen Family Identity

### Home / Recovery

Identity:
- resume the current paper thread

Should answer:
- what should I continue now?
- what is blocked?
- what is ready for review or reuse?

Should not become:
- project management dashboard
- KPI overview
- generic workspace homepage

### Paper Notes List

Identity:
- research handoff index

Should answer:
- which paper should I open?
- which papers need review, repair, or recovery?
- which papers have local/source access and operator markers?

Should not become:
- passive note warehouse
- file browser
- generic database table

### Paper Detail

Identity:
- reading surface with evidence-aware review bridge

Should answer:
- what am I reading?
- what saved state exists?
- what claims/evidence are available?
- what personal markers are mine?
- what safe action comes next?

Should not become:
- all-purpose control panel
- annotation playground
- generated-summary authority

### Workbench

Identity:
- evidence verification surface

Should answer:
- which claims need review?
- what evidence supports them?
- what is unresolved, stale, or blocked?
- what repair or artifact action is safe?

Should not become:
- settings console first
- parser debug page first
- broad chart/artifact dashboard

### Artifact Detail

Identity:
- downstream review and reuse surface

Should answer:
- where did this artifact come from?
- is it draft-like, stale, ready, or warning-heavy?
- what upstream source should I reopen?
- what can be safely rerendered, regenerated, exported, or reused?

Should not become:
- proof of claim truth
- approval workflow platform
- polished output detached from source

### Runtime / Diagnostics

Identity:
- local machine trust and recovery support

Should answer:
- is this machine ready?
- what dependency or runtime boundary is blocking work?
- how do I get back to the paper-first loop?

Should not become:
- primary product dashboard
- noisy developer console for normal users

### Settings / Local Secrets

Identity:
- local preferences, provider configuration, and secret boundary control

Should answer:
- what profile and workspace preferences are local to this machine?
- which AI provider and model slots are configured?
- where are credentials sourced from?
- what payload boundary applies before any external inference path runs?
- how can I test, rotate, or remove a provider credential safely?

Should always show:
- redacted credential status only
- whether a key comes from environment, local config, OS keychain, or is not configured
- local, cloud, or hybrid mode
- payload class warnings before external inference is enabled
- link to Runtime / Diagnostics for provider readiness checks

Should not become:
- a browser-owned secret store
- a hidden external transfer switch
- a place where chat, RAG, or cloud inference becomes live without runtime contract changes
- a scientific trust or approval surface
- a committed config editor

### Evidence-Aware Assistant

Identity:
- source-routed assistant embedded in the research workspace

Current runtime note:
- this is a future design direction; current `/api/chat` remains stub-only under `docs/API_CHAT_CONTRACT.md`.

Should answer:
- where does this claim come from?
- what evidence is unresolved?
- what should I inspect before using this artifact?
- what source gap blocks a safe answer?
- what paper, claim, figure, or artifact should I reopen?

Should always show:
- answer scope
- source basis
- uncertainty when evidence is missing
- linked claims, evidence refs, paper notes, or artifacts when available
- whether the answer is using canonical state, generated artifacts, personal memory, or background context

Should not become:
- primary product shell
- canonical truth owner
- ungrounded biomedical answer engine
- generic AI chat wrapper
- replacement for paper detail, Workbench, or artifact review
- hidden external data transfer surface

## 11. Reference Filter

When looking at an external reference, ask:

1. Does it help source, evidence, review state, recovery, or artifact handoff become clearer?
2. Does it preserve local-first and provenance boundaries?
3. Can it be expressed with current primitives and `--pp-*` tokens?
4. Does it avoid brand mimicry?
5. Does it avoid implying scientific certainty?
6. Does it reduce cognitive load for a researcher?

Use references for:
- state placement
- panel hierarchy
- density management
- review-before-action patterns
- annotation scope patterns
- progressive disclosure
- recovery and error handling
- visual state systems

Do not use references for:
- brand identity copying
- marketing style
- generic SaaS dashboard patterns
- chat-first product shells
- ungrounded approval flows
- decorative animation
- broad platform metaphors not backed by runtime contracts

## 12. BMAP Diagnosis

Motivation:
- researchers need fast confidence in what is sourced, reviewed, unresolved, and reusable.

Ability:
- improves when screen grammar, visual state, and action hierarchy repeat across routes.

Prompt:
- should appear as state-first next actions: open review, inspect evidence, reopen source, save marker, repair, guarded export.

## 13. B.I.A.S Diagnosis

Block:
- dense research UIs lose users when every panel has equal weight.

Interpret:
- state terms and visual cues must mean the same thing across screen families.

Act:
- primary action should follow evidence state, not compete with it.

Store:
- the user should remember PaperPipe as source -> evidence -> review -> artifact.

## 14. Peak-End Notes

Peak:
- a researcher sees the source, claim support, and next safe action without losing reading context.

Pit:
- generated or polished output appears more trustworthy than its evidence.

Transition:
- Home -> Paper Detail -> Workbench -> Artifact should preserve provenance and state language.

End:
- downstream reuse should leave the researcher with a memory of the source boundary, not only the artifact.

## 15. Ethics Check

Regret:
- design should save time and reduce over-trust.

Black Mirror:
- unsafe if generated summaries, charts, translations, or artifacts look reviewed because they are visually polished.

In Real-Life:
- PaperPipe should behave like a careful research assistant: clear, cautious, source-aware, and helpful without being theatrical.

## 16. Next PR-Sized Actions

1. Use this identity as the first section or guiding reference in `docs/PaperPipe_UI_GRAMMAR.md`.
2. Use it as the rubric for `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`.
3. Before the `/papers/:slug` redesign spike, list which identity statements the spike must strengthen.
4. Reject any reference pattern that conflicts with this identity unless a separate product decision explicitly adopts a new direction.
