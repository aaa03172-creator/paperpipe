# Research Workspace Implementation Sequencing (2026-04-01)

Status: working implementation memo
Scope: incremental UI/UX sequencing only
Basis:
- `docs/UX_REVIEW_REPORT_research-workspace-audit.md`
- `docs/reports/Research_Workspace_Core_Structure_Decisions_2026-04-01.md`
- `docs/reports/Research_Workspace_Home_IA_Draft_2026-04-01.md`
- `docs/reports/Research_Workspace_Project_Minimum_Chrome_2026-04-01.md`
- `docs/reports/Research_Workspace_Paper_Workspace_Shell_2026-04-01.md`
- `docs/reports/Research_Workspace_Paper_Workspace_Header_2026-04-01.md`
- `docs/reports/Research_Workspace_Mode_Semantics_And_CTA_Hierarchy_2026-04-01.md`
- current repo routes and page/component structure under `frontend/src/app/`

This memo converts the saved structure decisions into the smallest repo-fit implementation order.
It is intentionally incremental.
It does not assume a full route rewrite, a heavy project system, or a new runtime object graph.

## 1. Sequencing rule

The correct order is:

1. fix visible product language and action hierarchy
2. make paper work feel like one workspace
3. strengthen cross-screen continuity
4. add lightweight project framing only where the runtime can actually support it

This means:
- do not start with a heavy project shell
- do not start with a route merge
- do not start with artifact-first surfaces
- do not add new top-level navigation before the current paper/evidence loop is clearer

## 2. What can be implemented now vs later

### Implement now
- home emphasis reorder around `Continue current work`
- queue reframing as an operational block
- shared `Read / Review` language across note detail and workbench
- shared paper-workspace header model
- CTA hierarchy cleanup
- artifact boundary/thread language on artifact pages

### Delay until later
- true project routes as a major navigation root
- multi-project paper membership
- project-level object ownership semantics
- global resume ranking engine
- wizard/stage UI for reading/review/synthesis

## 3. One rule to lock before implementation

Before any UI patch starts, the secondary CTA rule should be treated as:

> one contextual secondary CTA only

Usually that CTA will be artifact-related.
In narrower cases, it may be a mode-return action such as `Open reading`.

This is better than treating the secondary slot as artifact-only, because:
- it fits the saved `Read / Review` mode model better
- it avoids forcing artifact language into contexts where returning to reading is the more natural secondary action
- it still preserves the larger rule that artifact work remains secondary

## 4. Recommended implementation tracks

There should be two tracks, but only one should start immediately.

### Track A: paper-workspace clarity
Start this immediately.

Goal:
- make the current product feel like a coherent evidence-backed paper workspace using the runtime and routes that already exist

### Track B: lightweight project framing
Start only after Track A has stabilized.

Goal:
- make project context visible without implying a heavy project system

Why this order is correct:
- the current repo already has strong paper/note/workbench/artifact surfaces
- it does not yet have a mature project runtime model
- if project chrome is introduced too early, the UI will over-promise

## 5. Phase sequence

## Phase 0: vocabulary and rule cleanup

This phase is small but important.
It should happen before larger layout changes.

### Goal
- align the public task model before changing more screen structure

### Main changes
- replace route-forward language such as:
  - `Paper note detail`
  - `Analysis Workbench`
  - `Open in Workbench`
- adopt task language:
  - paper title as the main title
  - `Read`
  - `Review`
  - `Open review`
  - `Resume review`
  - `Resume reading`
- demote `Learner / Inspect` from top-level task framing to subordinate view presets
- lock `secondary CTA = one contextual secondary action`

### Likely files
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `frontend/src/app/pages/AnalysisWorkbench.tsx`
- small shared copy/helpers if extracted

### Why first
- it creates one mental model before layout work starts
- it reduces the risk of building new UI around legacy route vocabulary

### Risk
- if overdone, the rename may feel cosmetic
- to avoid that, pair it with the new CTA hierarchy and shared header logic

## Phase 1: home IA reframe

### Goal
- make the home screen answer `What should I continue right now?`

### Main changes
- introduce one dominant `Continue current work` card
- reframe current triage/action-needed surfaces as `Queue`
- keep queue as a compact operational block:
  - `Needs review`
  - `Blocked`
  - `New`
- keep `Recent artifacts` visibly secondary
- stop giving route inventory and tool families equal emphasis near the top

### Likely files
- `frontend/src/app/pages/TriageDashboard.tsx`
- `frontend/src/app/lib/contentReview.ts`
- `frontend/src/app/lib/types.ts` only if lightweight view-model support is needed

### Why second
- home is the first place where the new product narrative becomes visible
- this can be done without introducing a project system yet

### Risk
- if the home card becomes a mini recommendation engine, the scope expands too fast
- keep it object-composed and thread-like, not globally optimized

## Phase 2: shared paper-workspace header and mode model

### Goal
- make note detail and workbench feel like the same workspace with different emphasis

### Main changes
- use the paper title as the main header title on both screens
- add the shared `Read / Review` mode model
- adopt one common header hierarchy:
  - context
  - paper identity
  - state strip
  - mode and CTA
- keep one primary CTA only
- keep at most one contextual secondary CTA

### Likely files
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `frontend/src/app/pages/AnalysisWorkbench.tsx`
- `frontend/src/app/layouts/WorkbenchLayout.tsx`
- `frontend/src/app/components/ArtifactHeaderContext.tsx`
- `frontend/src/app/components/StatusBadge.tsx` only if token treatment needs small support

### Why here
- this is the smallest change that makes the product feel less like disconnected routes
- it does not require route convergence

### Risk
- if the header becomes a badge wall, the mode model will not land
- keep interpretation in the first summary block below, not in the header itself

## Phase 3: note detail rebalance

### Goal
- move structured review and next action closer to the reading surface

### Main changes
- add a compact structured review block near the top of the center column
- reduce dependence on the right rail for the most important evidence/review cues
- keep references and related papers available without making them compete with the note body
- preserve reading-first entry while making review need visible earlier

### Likely files
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `frontend/src/app/components/ContentReviewSummary.tsx`
- `frontend/src/app/components/OperationalStateSummary.tsx`

### Why after the shared header
- once the mode model is clear, the center-column rebalance becomes easier to read

### Risk
- duplicating summary content across header, center, and rail
- use a compact center summary and simplify the rail rather than copying full blocks everywhere

## Phase 4: workbench task-first cleanup

### Goal
- keep workbench powerful while making review intent clearer than system controls

### Main changes
- preserve only the most relevant review action in the main CTA position
- move refresh/repair/rebuild/theme/highlight/style/density controls into a secondary controls area
- keep blockers and claim-review notices visible near the top
- shift language away from route or notebook implementation vocabulary where needed

### Likely files
- `frontend/src/app/pages/AnalysisWorkbench.tsx`
- `frontend/src/app/layouts/WorkbenchLayout.tsx`
- `frontend/src/app/components/ArtifactPanel.tsx`

### Why after note detail rebalance
- together these phases complete the paper-workspace convergence without forcing a single route

### Risk
- advanced users may fear loss of power
- avoid this by collapsing controls, not removing them

## Phase 5: artifact continuity pass

### Goal
- make artifact viewers feel like derived surfaces in the same research thread

### Main changes
- add shared derived-artifact context language:
  - derived artifact
  - canonical evidence lives upstream
  - continue in note/review
- align artifact-page header context
- keep artifact actions secondary to unresolved evidence work

### Likely files
- `frontend/src/app/pages/MeetingPackPage.tsx`
- `frontend/src/app/pages/ProtocolCardPage.tsx`
- sibling saved-artifact pages if they share the same issue
- `frontend/src/app/components/ArtifactHeaderContext.tsx`

### Why after paper-workspace cleanup
- artifact continuity is easier to express once upstream paper surfaces already share one language model

### Risk
- if artifact pages get too many context banners, they become noisy
- prefer one compact thread/context block over many reminders

## Phase 6: lightweight project framing

This phase should only begin after the earlier phases make the paper workspace and home coherent.

### Goal
- introduce visible project context without implying project-level ownership of all research objects

### Main changes
- add an `Active projects` home block if minimal project data exists
- optionally add lightweight project rows/sidebar chrome
- keep project counts paper-derived only
- use project context as framing and resume support, not as a new canonical object owner

### Likely files
- `frontend/src/app/pages/TriageDashboard.tsx`
- any new lightweight project view-model utilities
- shared context/header components only if needed

### Why last
- project framing is strategically important but currently less runtime-grounded than paper/evidence work
- adding it too early creates capability over-promise

### Risk
- the UI may imply a project management system the runtime does not support
- limit chrome to title, research question, paper-derived counts, and three actions

## 6. Recommended PR breakdown

### PR1: public language and CTA hierarchy
- scope:
  - Phase 0
  - small pieces of Phase 2 if needed
- user-visible win:
  - the product starts speaking in one task model

### PR2: home resume-first IA
- scope:
  - Phase 1
- user-visible win:
  - app open becomes action-oriented rather than route-oriented

### PR3: shared paper-workspace header
- scope:
  - Phase 2
- user-visible win:
  - note detail and workbench start to feel connected

### PR4: note detail center rebalance
- scope:
  - Phase 3
- user-visible win:
  - reading and structuring stop feeling split apart

### PR5: workbench control cleanup
- scope:
  - Phase 4
- user-visible win:
  - review becomes clearer than system operation

### PR6: artifact continuity pass
- scope:
  - Phase 5
- user-visible win:
  - artifacts feel downstream but connected

### PR7: lightweight project framing
- scope:
  - Phase 6
- user-visible win:
  - project context becomes visible without a heavy project rewrite

## 7. What should not be started yet

Do not start with:
- a project-first route rewrite
- a persistent mega-shell with every panel visible
- a `Projects` vs `Queue` top-level split as equal roots
- a synthesis-first workspace
- a command-center home that replaces the paper workflow

These may look more “complete,” but they are less repo-fit than the sequence above.

## 8. Recommended next design lock

Before implementation begins, one more tiny lock is worth writing down explicitly:

- `Continue current work` state-copy rules

The resume card should get final copy rules for:
- blocked thread
- unassigned paper
- artifact draft exists but unresolved review remains

This is a small follow-up compared with the sequencing work above, and it will make the home implementation much less ambiguous.

## 9. Short version

- Start with paper-workspace language, not heavy project chrome
- Reframe home around resume and queue before adding more navigation
- Make note detail and workbench feel like one workspace before touching routes
- Treat artifact continuity as a downstream pass
- Delay visible project framing until it can stay lightweight and honest
