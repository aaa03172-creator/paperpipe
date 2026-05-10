# Research Workspace Mode Semantics And CTA Hierarchy (2026-04-01)

Status: working UX structure memo
Scope: `Read / Review` mode semantics and CTA hierarchy only
Basis:
- `docs/reports/Research_Workspace_Paper_Workspace_Shell_2026-04-01.md`
- `docs/reports/Research_Workspace_Paper_Workspace_Header_2026-04-01.md`
- current implementations:
  - `frontend/src/app/pages/PaperNoteDetailPage.tsx`
  - `frontend/src/app/pages/AnalysisWorkbench.tsx`

This memo defines what the two paper-workspace modes actually mean and how actions should be prioritized so the UI stops mixing orientation, review, repair, and artifact actions at the same visual level.

## 1. Core decision

The shared paper workspace should expose exactly two primary user-facing modes:
- `Read`
- `Review`

These are not merely visual layouts.
They represent two different user intents:
- understand the paper in context
- validate or resolve evidence-backed review work

## 2. What each mode means

### 2.1 Read

`Read` means:
- understand the paper
- read the note in context
- see enough structure to decide whether deeper validation is needed
- preserve continuity with related papers, references, and downstream artifacts

`Read` does **not** mean:
- plain PDF/markdown reading with no structured support
- ignoring evidence state
- hiding review concerns until later

The right mental model is:

> Read = evidence-assisted reading

### 2.2 Review

`Review` means:
- inspect claims and evidence links
- understand provenance and uncertainty
- resolve review flags or blockers
- validate whether current structured outputs are safe to reuse

`Review` does **not** mean:
- generic debug console
- low-level system control surface
- artifact generation mode

The right mental model is:

> Review = evidence and trust validation

## 3. What the modes are not

The modes should not be interpreted as:
- separate products
- wizard stages
- beginner vs expert modes
- note mode vs engineer mode

This matters because the current note page has `Learner / Inspect` vocabulary, while the workbench has heavy review/operation controls. If those are carried forward unchanged, the user ends up with overlapping mode systems.

## 4. Recommended mode semantics

### Read mode primary center
- note body
- compact review snapshot
- related papers and references nearby

### Read mode default question
- “Do I understand this paper and know whether deeper review is needed?”

### Review mode primary center
- document/PDF evidence
- claim/evidence inspection
- blocker and uncertainty handling

### Review mode default question
- “Can I trust, validate, or repair the current structured state before reuse?”

## 5. Relationship to current repo UI

### Current note-detail view
Already closest to `Read`, but currently:
- route identity is too foregrounded
- view modes (`Learner`, `Inspect`) overlap with a larger `Read / Review` concept
- artifact and review actions compete with reading in the same header cluster

### Current workbench
Already closest to `Review`, but currently:
- title leads with route name (`Analysis Workbench`)
- control density mixes user intent with system settings
- some actions read like operator tooling rather than review actions

## 6. CTA hierarchy rule

The paper workspace needs a strict action hierarchy.

### Tier 1: Primary human action
Exactly one primary CTA should be visible in the header.

Allowed examples:
- `Resume review`
- `Resume reading`
- `Fix blocker`
- `Open review`
- `Open reading`

### Tier 2: Secondary artifact action
At most one secondary artifact CTA may sit beside the primary CTA.

Allowed examples:
- `Save protocol card`
- `Open meeting draft`
- `Continue draft`

### Tier 3: Contextual maintenance actions
Maintenance or system actions should not compete with Tier 1 or Tier 2 in the main header.

Examples:
- `Refresh`
- `Refresh checks`
- `Cancel run`
- `Sync to Obsidian`
- runtime checks

### Tier 4: Advanced session controls
These should stay collapsed or moved into a secondary controls panel.

Examples:
- theme
- highlight mode
- panel density
- reading style
- context profile
- parser/debug-adjacent controls

## 7. Primary CTA selection logic

The primary CTA should be chosen by user work state, not by route.

### Recommended order
1. blocker resolution
2. review-required action
3. resume reading
4. artifact continuation

### Why
- blocker and review actions are closer to evidence trust
- artifact continuation is important but should not outrank unresolved evidence work

## 8. Mode-driven CTA mapping

### When in Read mode
Preferred primary CTA:
- `Open review` or `Resume review` if unresolved work exists
- otherwise `Resume reading`

Preferred secondary CTA:
- one artifact action only if structurally relevant

### When in Review mode
Preferred primary CTA:
- `Fix blocker`
- `Resume review`
- `Refresh checks` only when the blocker is explicitly saved-check related

Preferred secondary CTA:
- `Open reading` only when returning to context is likely useful
- or one artifact CTA if review is already clear

## 9. What should not be a primary CTA

These should not become the main action in the shared paper workspace header except in narrow edge cases:
- `Save protocol card`
- `Open meeting draft`
- `Sync to Obsidian`
- `Refresh`
- `Runtime checks`
- `Terminal logs`
- `Run deep read`

### Important nuance
`Run deep read` is important, but it is still a system-generating action.
It should not visually outrank “review what is already here” when meaningful structured state and review signals already exist.

## 10. Repo-fit translation for current screens

### Current note-detail actions
Current top actions include:
- back to list
- runtime checks
- save protocol card
- review details
- open in workbench

Recommended translation:
- `Read / Review` mode switch becomes the main conceptual split
- `Open in Workbench` evolves into `Open review` or `Resume review`
- `Save protocol card` stays secondary
- `Review details` becomes contextual, not header-primary

### Current workbench actions
Current visible actions include:
- run deep read
- cancel run
- refresh
- refresh checks
- rebuild checks
- sync to obsidian

Recommended translation:
- the header should still expose only the one best next human action
- system and maintenance actions move into a secondary review-controls area
- workbench remains powerful without making every control feel equally primary

## 11. Recommended copy changes

### Replace
- `Paper note detail`
- `Analysis Workbench`
- `Open in Workbench`

### With
- paper title as the main title
- `Read`
- `Review`
- `Open review`
- `Resume review`
- `Resume reading`

### Why
- route labels are implementation language
- mode labels should describe user intent

## 12. What to keep vs change from current mode language

### Keep conceptually
- the existence of a lighter contextual reading emphasis
- the existence of a more inspection-heavy emphasis

### Change
- do not let `Learner / Inspect` become the public top-level mode model
- if those remain at all, they should be subordinate view presets inside a broader `Read` or `Review` context

### Why
- `Learner / Inspect` is a presentation emphasis
- `Read / Review` is a product-level task model

## 13. Text wireframe

### Read mode

```text
Project: Ketone Ester Neuroprotection
Lee et al. 2024
Open access · Needs review 3

[Read] [Review]
[Open review] [Save protocol card]

Review snapshot
- grounded 8
- unresolved 3
- saved state updated 2h ago
```

### Review mode

```text
Project: Ketone Ester Neuroprotection
Lee et al. 2024
Open access · Blocked: saved checks missing

[Read] [Review]
[Fix blocker] [Open reading]

Note panels
- saved checks missing
- claim review flags available
- text-match fallback active on 2 claims
```

## 14. Recommendation summary

- lock `Read / Review` as the only primary paper-workspace modes
- treat them as user-intent modes, not styling modes
- use one primary CTA only
- keep artifact actions secondary
- move maintenance/system controls below the header hierarchy

This gives the product a clearer task model without changing the runtime contract or forcing a full UI rewrite.
