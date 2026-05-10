# Research Workspace Core Structure Decisions (2026-04-01)

Status: working design decision memo
Scope: current PaperPipe UI/UX structure only
Basis:
- repo-grounded UI audit in `docs/UX_REVIEW_REPORT_research-workspace-audit.md`
- actual current frontend routes and page/component structure
- design discussion narrowed around `Queue`, `Project`, `Resume`, and workspace model

This memo does not define a full product rewrite. It captures the current best judgment about the minimum information architecture that fits the repo as it exists today.

## 1. Current product stance

The current PaperPipe repo is **not yet project-centered in implementation**. Its strongest existing runtime objects and screens are still:
- paper summaries
- paper notes
- structured paper state
- workbench evidence/review surfaces
- derived artifact viewers

Because of that, the most accurate product center **right now** is:

> PaperPipe is a local-first biomedical research workspace whose primary working surface is a source-grounded, evidence-assisted paper workspace.

That means:
- `Project` is important, but it is not yet the deepest runtime truth.
- `Paper workspace` is still the real execution center.
- `Artifacts` matter, but they remain derived and secondary to evidence review.

## 2. Decisions currently locked

### 2.1 Queue
- `Queue` is a **state view**, not a container.
- The same paper may appear inside a project context and inside the queue at the same time.
- Queue should answer: **what currently needs human attention?**
- Queue should not become a second paper library or a second home.

#### Recommended UI placement
- Primary placement: a **home block** under `Continue current work`
- Internal grouping:
  - `Needs review`
  - `Blocked`
  - `New`

#### Important constraint
- `Auto-collected` is **not** a top-level queue bucket.
- It is metadata or a filter on queue items, not the main queue meaning.

#### Why this is locked
- A queue is an operational lens over work state.
- If it becomes a top-level container, the app risks recreating the same mixed-home problem under a cleaner label.

### 2.2 Project
- `Project` is a **paper context**, not an object owner.
- It should be visible as a lightweight first-class UX entity, but not as a heavy system that implies ownership over every claim, artifact, or decision object.

#### Minimum project role
- provides research question / working context
- groups linked papers
- surfaces open work and recent momentum
- helps users resume and prioritize within one research theme

#### Minimum project chrome
- sidebar row:
  - project title
  - one-line research question
  - `needs review` count
  - `blocked` count
  - last updated
- project header:
  - title
  - research question
  - linked paper count
  - needs review count
  - blocked count
  - optional recent artifact draft hint
  - lightweight actions:
    - `Add paper`
    - `Continue current work`
    - `Open queue`

#### Minimum schema
- `project_id`
- `title`
- `research_question` or `goal`
- `status` (`active | paused | archived`)
- `linked_paper_refs`
- `last_active_ref`
- `updated_at`
- derived counts:
  - `needs_review`
  - `blocked`
  - `artifacts`

#### Important constraint
- Project must not visually imply:
  - permissions
  - nested ownership trees
  - project-level canonical claim ownership
  - project management features that the runtime does not support

### 2.3 Resume
- `Resume` should be implemented internally as an object composition, but shown to users as a **current thread**.
- The user should feel they are resuming ongoing work, not reopening a random object.

#### Recommended resume model
- internal composition:
  - active project
  - last active paper
  - next human action
  - blocker state
  - recent artifact draft hint
- UX expression:
  - one primary `Continue current work` card on home

#### Recommended card content
- project name
- paper title
- next human action
- blocker flag when present
- recent artifact draft hint when relevant
- last active time

#### Recommended CTA behavior
- primary CTA should reflect the next human action:
  - `Resume review`
  - `Resume reading`
  - `Fix blocker`
  - `Continue draft`
- `Continue draft` should only become primary when no higher-priority review/evidence action is pending.

#### Recommended priority order
1. active project + last active paper thread
2. blocker or review action inside that thread
3. linked recent artifact draft

### 2.4 Workspace model
- Do **not** describe the product as a strict two-stage wizard.
- The better model is a **reversible dual-surface workspace**.

#### Surface 1: Evidence workspace
- reading
- claims
- evidence
- provenance
- uncertainty
- review

#### Surface 2: Artifact workspace
- meeting packs
- protocol cards
- chart/image/method outputs

#### Relationship
- artifact work is derived from evidence work
- users must be able to move back upstream easily
- the model is reversible, not forward-only

## 3. Decisions intentionally not locked yet

These items are still open and should not be prematurely standardized.

### 3.1 Queue exact chrome
- whether queue eventually needs a dedicated full page
- whether the home queue block uses tabs, pills, or compact sections
- whether `ready` work should be shown in a separate lane or omitted from queue entirely

### 3.2 Project relationship rules
- whether one paper may belong to multiple active projects
- whether projects need their own route immediately or can begin as a lightweight shell/state overlay
- whether recent artifact count belongs in the header or just a single “recent draft” hint

### 3.3 Resume details
- exact copy style for blocked vs non-blocked resume states
- whether last active time is useful enough to keep visible
- how to phrase resume when the paper is not yet assigned to a project

### 3.4 Paper workspace convergence
- whether note detail and workbench converge into one route shell
- whether they stay separate routes but adopt one shared paper-workspace frame
- how explicit the mode split should be between reading and review

## 4. What is over-designed right now

The following ideas are currently too heavy for the repo and should be resisted for now:
- a heavy project management model
- a top-level `Projects` vs `Queue` split as equal app roots
- a global recommendation/priority engine for resume
- stage-completion/wizard framing for the whole research workflow
- project ownership of every downstream object

## 5. What should be defined next

The next round should lock only the minimum needed to shape the UI shell:
1. the exact home IA around `Continue current work`, `Projects`, and `Queue`
2. the minimum visible project chrome
3. the paper workspace shell for `Read` and `Review`

## 6. Immediate design implications

If these decisions hold, then the near-term UI should move in this direction:
- home becomes `continue current work` first
- queue becomes a compact operational block, not a second home
- projects become lightweight visible contexts, not heavy data owners
- paper note detail and workbench become two surfaces of one paper workspace
- artifacts stay nearby but secondary

## 7. Short version

- `Queue` = state view
- `Project` = paper context
- `Resume` = object-composed internally, thread-like in UX
- `Workspace` = reversible dual-surface model
- `Primary center` = source-grounded evidence-assisted paper workspace
