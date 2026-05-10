# Research Workspace Home IA Draft (2026-04-01)

Status: working IA draft
Scope: home screen only
Basis:
- `docs/reports/Research_Workspace_Core_Structure_Decisions_2026-04-01.md`
- `docs/UX_REVIEW_REPORT_research-workspace-audit.md`
- current `frontend/src/app/pages/TriageDashboard.tsx`

This draft narrows only the home information architecture. It does not yet propose a full project route model or implementation detail beyond current repo-fit structure.

## 1. Home purpose

The home screen should answer one question first:

> What should I continue right now?

It should not behave like:
- a flat route launcher
- a second paper library
- a full project management dashboard

It should behave like:
- a resume-first workspace entry
- a lightweight research context selector
- an operational inbox summary for work that needs human attention

## 2. Recommended home block order

### 2.1 Block 1: Continue current work
This is the first and most important home block.

#### Content
- project name
- current paper title
- next human action
- blocker signal when present
- recent artifact draft hint when relevant
- last active time

#### Primary CTA
- one CTA only
- state-aware label:
  - `Resume review`
  - `Resume reading`
  - `Fix blocker`
  - `Continue draft`

#### Why this comes first
- It best matches the product’s real center: ongoing evidence-backed paper work.
- It reduces decision overhead at app open.
- It keeps the home screen aligned with the “current thread” model.

### 2.2 Block 2: Active projects
This is the second home block.

#### Content per project row
- title
- one-line research question
- `needs review` count
- `blocked` count
- last updated

#### Interaction
- selecting a project should narrow context, not imply full project ownership semantics
- project actions should stay light:
  - `Continue`
  - `Add paper`
  - `Open queue`

#### Why this comes second
- Project is an important context signal, but not the first action surface.
- Users usually want to resume work before browsing contexts.

### 2.3 Block 3: Queue
Queue should appear as a compact operational block, not as a parallel home.

#### Internal grouping
- `Needs review`
- `Blocked`
- `New`

#### Queue item shape
- paper title
- project context if assigned
- reason for being here
- one recommended next action

#### Why queue comes after projects
- Queue is a state lens over attention-demanding work.
- If it appears first, the product risks feeling like an operational inbox rather than a research workspace.

### 2.4 Block 4: Recent artifacts
This should remain optional and clearly secondary.

#### Content
- recent meeting pack or protocol draft
- linked paper/project context
- recency

#### Constraint
- this block must never outrank active evidence/review work

## 3. Recommended layout stance

### Desktop
- upper hero-width block:
  - `Continue current work`
- below or adjacent:
  - `Active projects`
  - `Queue`
- secondary lower block:
  - `Recent artifacts`

### Mobile
- strict top-down stack:
  1. Continue current work
  2. Active projects
  3. Queue
  4. Recent artifacts

## 4. What home should no longer try to do

The current home mixes:
- workspace explanation
- onboarding
- tool links
- triage summary
- paper acting table

The next home should stop trying to give all route families equal emphasis.

Specifically, home should no longer lead with:
- route inventory language
- “more tools” framing as a top-level peer to the core workflow
- generic paper table before context and next action are established

## 5. Repo-fit translation from the current home

The current `TriageDashboard` already contains reusable pieces that fit this draft:
- triage summary counts
- per-paper next action logic
- rail-based paper metadata
- clear runtime transparency

This means the next home IA can be achieved by:
- reordering emphasis
- relabeling sections
- reframing the current paper table into queue semantics
- adding a lightweight active-project layer

It does **not** require:
- a full new shell
- a new backend architecture before UX exploration

## 6. What is intentionally not in the draft

To avoid over-design, the home draft does not yet include:
- project kanban
- task timeline
- chat-first panel
- global command center as the dominant surface
- artifact creation as a top-priority entry point

## 7. Open decisions for the next round

1. Should `Active projects` be a left sidebar list or a home-center block first?
2. Should queue grouping use tabs, chips, or stacked sections?
3. Should `Recent artifacts` stay on home or move under project context only?
4. Should unassigned papers show under queue only, or also in a separate lightweight intake block?

## 8. Short version

- Home is `resume first`
- Projects provide context, not heavy ownership
- Queue is an operational block
- Artifacts are visible, but secondary
