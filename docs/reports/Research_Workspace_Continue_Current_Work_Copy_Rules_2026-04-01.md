# Research Workspace Continue Current Work Copy Rules (2026-04-01)

Status: working copy/state memo
Scope: home `Continue current work` card only
Basis:
- `docs/reports/Research_Workspace_Core_Structure_Decisions_2026-04-01.md`
- `docs/reports/Research_Workspace_Home_IA_Draft_2026-04-01.md`
- `docs/reports/Research_Workspace_Implementation_Sequencing_2026-04-01.md`
- current home logic in `frontend/src/app/pages/TriageDashboard.tsx`
- current review-state helper in `frontend/src/app/lib/contentReview.ts`
- current runtime types in `frontend/src/app/lib/types.ts`

This memo defines the smallest reliable copy rules for the home `Continue current work` card.
It is meant to support implementation without turning home into a heavy recommendation engine.

## 1. Core rule

The home screen should show:

> one thread-like resume card, not a list of competing recommended objects

Internally, the card may be composed from several objects:
- project context if present
- paper summary
- review state
- blocker state
- recent artifact draft hint when available

But the user should feel:
- “this is the work thread I should continue”

not:
- “the system ranked several unrelated objects for me”

## 2. Card structure

The card should keep a stable shape across all states.

### Slot 1: Block label
- fixed label:
  - `Continue current work`

### Slot 2: Context line
- if project exists:
  - project title
- if no project exists:
  - `No project assigned`

### Slot 3: Main title
- paper title

### Slot 4: Primary next-action sentence
- one sentence only
- should begin with:
  - `Next:`

### Slot 5: Secondary state hint
- optional
- one short line only
- used for:
  - blocker explanation
  - unassigned warning
  - recent artifact hint
  - last updated

### Slot 6: Primary CTA
- exactly one primary CTA

### Slot 7: Optional compact metadata tokens
- at most 2 compact tokens
- eligible examples:
  - `Needs review`
  - `Blocked`
  - `Draft available`
  - `Open access`

Do not show large token stacks, confidence percentages, or multiple route buttons.

## 3. State priority order

The card should choose copy by priority, not by route or by object type.

### Priority 1: blocked thread
Use when:
- `paper.ops_summary?.recommended_action === "repair_stats"`
- or equivalent blocker state exists in the assembled thread

### Priority 2: review-needed thread
Use when:
- `paper.ops_summary?.recommended_action === "open_workbench"`
- or content review is `flagged`

### Priority 3: reading resume
Use when:
- no blocker is active
- no flagged review action is higher priority
- a paper workspace already exists and should be resumed

### Priority 4: artifact continuation
Use when:
- a recent artifact draft exists
- and no blocker or review-needed state outranks it

This preserves the broader product rule:
- evidence and trust work outrank artifact continuation

## 4. Recommended copy rules by state

## 4.1 Blocked thread

### When this state applies
- saved checks are missing
- a repair action is required before reliable review reuse
- another equivalent home-blocking runtime state exists

### Recommended card copy
- context:
  - project title if available
  - otherwise `No project assigned`
- main title:
  - paper title
- primary next-action sentence:
  - `Next: Fix the blocker before continuing review.`
- secondary hint:
  - use the blocker reason
  - example:
    - `Saved checks are missing for the current claims.`
- primary CTA:
  - `Fix blocker`
- compact tokens:
  - `Blocked`
  - optional access token if useful

### Why this is right
- blocker language is user-meaningful
- it avoids leaking implementation-specific actions like `repair_stats`
- it still preserves urgency

## 4.2 Review-needed thread

### When this state applies
- recommended action is currently `open_workbench`
- or content review state is `flagged`

### Recommended card copy
- primary next-action sentence:
  - `Next: Review flagged claims and evidence.`
- secondary hint:
  - if flagged:
    - `3 claim review flags recorded in the current paper summary.`
  - otherwise:
    - `Evidence review is the best next step for this paper.`
- primary CTA:
  - `Resume review`
- compact tokens:
  - `Needs review`
  - optional access token

### Why this is right
- it matches the saved `Read / Review` model
- it avoids route language like `Open workbench`

## 4.3 Reading resume

### When this state applies
- no blocker
- no flagged review issue with higher priority
- the best next move is to reopen the paper workspace in reading context

### Recommended card copy
- primary next-action sentence:
  - `Next: Resume reading and note review.`
- secondary hint:
  - `Pick up the paper context before deeper evidence validation.`
- primary CTA:
  - `Resume reading`
- compact tokens:
  - optional access token
  - optional freshness token only if very recent

### Why this is right
- it keeps reading-first entry without pretending the product is a plain reader
- it reinforces that reading is already evidence-assisted

## 4.4 Unassigned paper

### When this state applies
- the chosen current thread has no project context

### Recommended card copy
- context line:
  - `No project assigned`
- primary next-action sentence:
  - if review-needed:
    - `Next: Review this paper before assigning it to a project.`
  - otherwise:
    - `Next: Resume this paper and decide where it belongs.`
- secondary hint:
  - `You can keep working without a project, but this paper is not linked to a research context yet.`
- primary CTA:
  - `Resume review`
  - or `Resume reading`, depending on the higher-priority state

### Important rule
- do not make `Assign to project` the primary CTA on the home card

### Why
- paper work should stay executable even without a project
- otherwise project assignment starts to outrank evidence work

## 4.5 Artifact draft exists but unresolved review remains

### When this state applies
- recent artifact draft hint exists
- but blocker or review-needed state is still active

### Recommended card copy
- primary next-action sentence:
  - `Next: Finish evidence review before continuing the draft.`
- secondary hint:
  - `Meeting draft updated 2h ago.`
- primary CTA:
  - `Resume review`
- compact tokens:
  - `Needs review`
  - `Draft available`

### Why
- it preserves the product rule that artifact continuation stays secondary to unresolved evidence work

## 4.6 Artifact draft exists and no higher-priority evidence work remains

### When this state applies
- recent artifact draft hint exists
- no blocker
- no review-needed state

### Recommended card copy
- primary next-action sentence:
  - `Next: Continue the latest draft from this paper thread.`
- secondary hint:
  - `Meeting draft updated 2h ago.`
- primary CTA:
  - `Continue draft`
- compact tokens:
  - `Draft available`
  - optional project context token only if visually light

### Why
- artifact continuation is valid here because nothing more urgent outranks it

## 5. Recommended copy constraints

### Keep
- action-first language
- one sentence for the next action
- one supporting line at most
- one CTA only

### Avoid
- raw route names:
  - `Open workbench`
  - `Open paper note`
- raw implementation words:
  - `repair stats`
  - `saved checks artifact`
- too much judgment language:
  - `urgent`
  - `critical`
  - `must fix now`
- too much object inventory:
  - multiple counts
  - long tag lists
  - repeated state badges

## 6. Minimal runtime mapping to current repo

The current repo can already support most of this without a new ranking engine.

### Current signals already available
- `paper.title`
- `paper.updated_at`
- `paper.ops_summary`
- `paper.access_summary`
- `paper.issues`
- `paper.issues_label`
- `paper.issues_state`

### Helpful current helpers
- `getPrimaryNextAction` in `TriageDashboard.tsx` as an existing starting point
- `deriveContentReviewSummary` in `contentReview.ts`

### What is still optional/overlay-level
- project title
- recent artifact draft hint

Those can be added when the home view model grows, but they do not need to block implementation of the card’s base state logic.

## 7. Text wireframe examples

### Blocked

```text
Continue current work
Ketone Ester Neuroprotection
Lee et al. 2024
Next: Fix the blocker before continuing review.
Saved checks are missing for the current claims.
[Fix blocker]
```

### Review needed

```text
Continue current work
Ketone Ester Neuroprotection
Lee et al. 2024
Next: Review flagged claims and evidence.
3 claim review flags recorded in the current paper summary.
[Resume review]
```

### Reading resume

```text
Continue current work
Ketone Ester Neuroprotection
Lee et al. 2024
Next: Resume reading and note review.
Pick up the paper context before deeper evidence validation.
[Resume reading]
```

### Unassigned

```text
Continue current work
No project assigned
Lee et al. 2024
Next: Resume this paper and decide where it belongs.
You can keep working without a project, but this paper is not linked to a research context yet.
[Resume reading]
```

### Draft exists but review still needed

```text
Continue current work
Ketone Ester Neuroprotection
Lee et al. 2024
Next: Finish evidence review before continuing the draft.
Meeting draft updated 2h ago.
[Resume review]
```

## 8. Recommendation summary

- `Continue current work` should stay one card
- the card should feel like a thread resume, not an object picker
- blockers outrank review
- review outranks reading
- reading outranks artifact continuation
- project assignment should inform context, not replace evidence work as the primary action
