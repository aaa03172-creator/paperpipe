# Research Workspace Paper Workspace Header (2026-04-01)

Status: working UX structure memo
Scope: shared paper workspace header only
Basis:
- `docs/reports/Research_Workspace_Paper_Workspace_Shell_2026-04-01.md`
- current implementations:
  - `frontend/src/app/pages/PaperNoteDetailPage.tsx`
  - `frontend/src/app/pages/AnalysisWorkbench.tsx`
  - `frontend/src/app/layouts/WorkbenchLayout.tsx`

This memo narrows the minimum shared header model for the paper workspace so that `Read` and `Review` feel like two modes of the same working surface rather than two unrelated screens.

## 1. Core decision

The paper workspace should use **one shared header model** across:
- note detail (`Read`)
- workbench (`Review`)

The header should express:
- context
- state
- next action
- mode

It should not try to express:
- every available tool
- every review detail
- every artifact pathway

## 2. What the header must do

When a user lands on either mode, the header should immediately answer:
- Which project context am I in?
- Which paper am I working on?
- Is this paper blocked, review-ready, or currently actionable?
- Am I in `Read` or `Review`?
- What is the best next action from here?

If the header does that well, the rest of the workspace can stay denser without becoming disorienting.

## 3. Recommended shared header structure

### Row 1: Context
- project name if assigned
- lightweight project question or context hint

### Row 2: Paper identity
- paper title
- optional authors/year only if already cheaply available

### Row 3: State strip
- access status
- review state
- blocker state when present
- optional saved-state freshness hint

### Row 4: Mode and action
- mode switch:
  - `Read`
  - `Review`
- one primary CTA
- one optional secondary artifact CTA

## 4. Recommended header content

### 4.1 Must-show fields
- project context label
- paper title
- access signal
- review signal
- blocker signal when present
- one primary next-action CTA
- mode switch

### 4.2 Good secondary fields
- last updated
- saved state freshness
- recent artifact draft hint

### 4.3 Do not show in the top header
- full claim counts
- full evidence counts
- run history
- parser/debug settings
- multiple artifact buttons
- detailed provenance explanation paragraphs
- large arrays of tags

Those belong in summary strips or side/context panels, not the main header.

## 5. Recommended CTA hierarchy

### Primary CTA
The primary CTA should represent the best next human action.

#### Allowed primary labels
- `Resume review`
- `Resume reading`
- `Fix blocker`
- `Open review`
- `Open reading`

#### Rule
- only one primary CTA in the header

### Secondary CTA
One secondary CTA may exist when relevant.

#### Allowed secondary examples
- `Save protocol card`
- `Open meeting draft`
- `Recent draft available`

#### Rule
- artifact CTA must remain secondary to evidence/review work unless no higher-priority review action exists

## 6. Recommended mode switch behavior

The mode switch should be visible and simple.

### Labels
- `Read`
- `Review`

### Why these labels
- shorter and clearer than `Paper note detail` vs `Analysis Workbench`
- closer to the user’s task than to the route implementation

### What the switch should not imply
- different truth sources
- different products
- stage completion

The user is not leaving one system and entering another. They are changing emphasis inside one paper workspace.

## 7. Repo-fit translation from current screens

### Current note detail strengths to preserve
- review snapshot is already near the top
- title and note identity are clear
- workbench handoff exists

### Current workbench strengths to preserve
- access/review/ops state are already strong in header meta
- workbench notice area already carries important blocker language

### Main changes needed
- note detail should stop introducing itself as a standalone route first
- workbench should stop leading with “Analysis Workbench” as if detached from the paper workspace
- both should use the same top-level naming and hierarchy

## 8. Recommended text model

### Header title model

Instead of:
- `Paper note detail`
- `Analysis Workbench`

Prefer:
- project context label above
- paper title as the main header title

### Example

```text
Project: Ketone Ester Neuroprotection
Lee et al. 2024

Open access · Needs review 3 · Blocked: saved checks missing

[Read] [Review]
[Fix blocker] [Save protocol card]
```

### Why this is better
- the paper becomes the main working unit
- the route name stops competing with the work object
- the mode becomes explicit without becoming heavy UI chrome

## 9. Recommended state strip rules

The state strip should use compact tokens only.

### Always eligible
- access badge
- review badge

### Conditional
- blocker badge when actionable
- saved-state freshness when useful
- recent artifact draft hint when it helps resume context

### Never all at once
- status badge
- confidence badge
- many tags
- review summary text
- run status
- artifact status
- runtime guidance

If too many signals compete in the first band, the header loses its orientation role.

## 10. What should sit below the header instead

These belong immediately below the header, not inside it:
- compact review snapshot
- blocker explanation text
- current mode summary
- lightweight artifact handoff summary

This preserves the header as orientation and the next band as interpretation.

## 11. Desktop and mobile behavior

### Desktop
- context and title at left
- state strip directly under title
- mode + CTA cluster on the right or below

### Mobile
- stack all four layers vertically:
  1. project context
  2. paper title
  3. state strip
  4. mode + primary CTA

### Mobile constraint
- do not let the mobile header become a badge wall
- if more than 3 compact tokens are needed, move the rest into the first summary block below

## 12. Recommendation summary

- the paper title should be the shared primary header title
- `Read / Review` should be the visible shared mode model
- the header should contain one primary CTA and at most one secondary artifact CTA
- orientation lives in the header
- interpretation lives in the first summary block below

This is the smallest shared header that makes the paper workspace feel coherent without forcing a route merge or an overbuilt tab system.
