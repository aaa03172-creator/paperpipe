# Research Workspace Project Minimum Chrome (2026-04-01)

Status: working UX structure memo
Scope: lightweight project chrome only
Basis:
- `docs/reports/Research_Workspace_Core_Structure_Decisions_2026-04-01.md`
- `docs/reports/Research_Workspace_Home_IA_Draft_2026-04-01.md`
- current shared UI primitives in:
  - `frontend/src/app/components/Rail.tsx`
  - `frontend/src/app/components/ArtifactHeaderContext.tsx`
  - `frontend/src/app/components/OperationalStateSummary.tsx`
  - `frontend/src/app/components/ContentReviewSummary.tsx`

This memo defines how `Project` should appear in the current product without implying a heavy project-management system or object-ownership model that the repo does not yet support.

## 1. Product stance

At the current repo stage:
- `Project` should feel important
- `Project` should not feel heavy
- `Project` should frame work
- `Paper workspace` should still execute work

So the right design rule is:

> Project chrome should provide context, momentum, and entry points, but not claim canonical ownership over every downstream object.

## 2. What project chrome is for

Project chrome should help users answer:
- What research question am I working on?
- Which papers belong to this context?
- Is there review work blocked or pending?
- What should I continue next?

Project chrome should **not** try to answer:
- Who owns every object?
- Which claims/decisions/experiments belong to this project as first-class entities?
- What is the full project-management lifecycle?

## 3. Recommended minimum chrome

### 3.1 Sidebar project row

Each row should show only:
- project title
- one-line research question
- `needs review` count
- `blocked` count
- last updated

### Example row

```text
Ketone Ester Neuroprotection
Can ketone ester signals support early neuroprotection hypotheses?
Needs review 3 · Blocked 1 · Updated 2h ago
```

### Why this is enough
- The title gives recognition
- The research question gives meaning
- The counts give urgency
- The timestamp gives recency

Anything beyond this risks turning the sidebar into a mini dashboard.

### 3.2 Project header

The header should show:
- project title
- research question
- linked paper count
- needs review count
- blocked count
- optional recent artifact draft hint

### Recommended actions
- `Add paper`
- `Continue current work`
- `Open queue`

### Example header structure

```text
Ketone Ester Neuroprotection
Can ketone ester signals support early neuroprotection hypotheses?

12 papers · Needs review 3 · Blocked 1 · Recent draft: meeting pack updated 2h ago

[Continue current work] [Add paper] [Open queue]
```

### Why this is enough
- It preserves the project as a visible working context
- It avoids implying project-level object management
- It gives exactly three actions that match the current repo reality

## 4. What project chrome should not show yet

To avoid capability over-promise, do **not** show these as first-class project chrome elements yet:
- claim count
- decision count
- experiment count
- artifact family counts broken down into many categories
- member avatars
- permissions/share states
- status workflows beyond `active / paused / archived`
- kanban lanes
- ownership trees
- tabs like `Claims`, `Decisions`, `Meetings`, `Experiments`, `Artifacts` as if project is already the canonical owner

These would make the UI look more “complete,” but they would misrepresent the actual runtime model.

## 5. Recommended count discipline

Project-level counts should stay derived from current paper-centered work, not from independent project-owned entities.

### Safe counts
- linked papers
- needs review
- blocked
- optional recent artifact presence

### Unsafe counts for now
- total claims
- total evidence refs
- total decisions
- total experiments
- total unresolved uncertainties across all artifact families

### Why
- safe counts summarize work context
- unsafe counts imply a mature project object graph that the repo does not yet implement

## 6. Recommended supporting primitives from the current repo

The current repo already has primitives that fit this minimum chrome well:

### `StatusBadge`
- good for compact state tokens
- use sparingly for project-level `blocked` or lightweight status hints

### `OperationalStateSummary`
- good for local action-needed language
- can inspire the project-level wording style
- should not be naively copied whole into the project sidebar, because it is too verbose for every project row

### `ContentReviewSummary`
- useful for language around “needs review”
- better as a detail-level block than as a repeated sidebar row payload

### `ArtifactHeaderContext`
- strong pattern for compact header context panels
- can be translated into project header context cards if needed

### `Rail`
- demonstrates the right density discipline
- title + state + compact metadata is the correct spirit for project rows

## 7. Text wireframe

### Home project block

```text
Active projects

[Project row]
Ketone Ester Neuroprotection
Can ketone ester signals support early neuroprotection hypotheses?
Needs review 3 · Blocked 1 · Updated 2h ago

[Project row]
Prodromal Alzheimer Biomarkers
Which papers still need evidence review before next meeting?
Needs review 1 · Blocked 0 · Updated yesterday
```

### Project header

```text
Ketone Ester Neuroprotection
Can ketone ester signals support early neuroprotection hypotheses?

12 linked papers · Needs review 3 · Blocked 1 · Recent draft available

[Continue current work] [Add paper] [Open queue]
```

## 8. What this chrome should imply semantically

When a user sees a project, they should infer:
- “this is the context for a research question”
- “these papers are being considered together”
- “I can continue the current research thread”

They should **not** infer:
- “all objects are now owned by this project”
- “this project has a full PM/task system”
- “the project is the canonical truth instead of the paper/note/state model”

## 9. Open questions

These are still intentionally open:

### 9.1 Placement
- Should project rows first appear as a home block only?
- Or should a persistent sidebar be introduced immediately?

### 9.2 Paper membership
- Should a paper belong to at most one active project for now?
- Or should multi-project linking be allowed later only?

### 9.3 Recent artifact hint
- Should it be a text hint only?
- Or a compact badge plus link?

### 9.4 Project route timing
- Do we need a real project route immediately?
- Or can project chrome first exist inside home and shared headers?

## 10. Recommendation summary

- `Project` should be visible as a lightweight first-class context
- `Project` should not yet behave like an owner of all research objects
- project chrome should stay to:
  - title
  - research question
  - paper-derived counts
  - three lightweight actions

This is the smallest chrome that makes the product feel more like a workspace without promising a project system the repo does not yet have.
