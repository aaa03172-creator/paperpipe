# Research Workspace Paper Workspace Shell (2026-04-01)

Status: working UX structure memo
Scope: shared paper workspace shell only
Basis:
- `docs/reports/Research_Workspace_Core_Structure_Decisions_2026-04-01.md`
- `docs/reports/Research_Workspace_Home_IA_Draft_2026-04-01.md`
- `docs/reports/Research_Workspace_Project_Minimum_Chrome_2026-04-01.md`
- current routes:
  - `frontend/src/app/pages/PaperNoteDetailPage.tsx`
  - `frontend/src/app/pages/AnalysisWorkbench.tsx`
  - `frontend/src/app/layouts/WorkbenchLayout.tsx`

This memo defines how `Paper note detail` and `Analysis workbench` should converge conceptually into one paper workspace without forcing an immediate route merge or mega-screen rewrite.

## 1. Core decision

The product should treat paper work as **one workspace with two primary modes**:
- `Read`
- `Review`

This should be described as a **shared paper workspace shell**, not as:
- two unrelated routes
- a single giant all-panels screen
- a rigid stage-based flow

## 2. Why this is the right unit

At the current repo stage, the strongest real execution surface is the paper-level workflow:
- open a paper note
- understand the note and its context
- inspect evidence and review state
- hand work forward into an artifact when needed

That means the true working unit is:

> one paper, one structured state, two primary working surfaces

This matches the repo better than:
- project-only navigation
- artifact-first navigation
- chat-first workflow

## 3. Current repo reality

### Existing `Read` surface
`PaperNoteDetailPage` already behaves like a read-oriented workspace:
- header with title and downstream CTA
- review snapshot
- reading markdown body
- saved state, related papers, references, actions in side rails

### Existing `Review` surface
`AnalysisWorkbench` already behaves like a review-oriented workspace:
- PDF/document viewer
- claim/evidence panel
- operational review state
- workbench controls and timeline

### The actual gap
The main problem is not missing functionality.
The main problem is that these two surfaces do not yet feel like the same workspace with different emphasis.

## 4. Recommended shell model

### 4.1 Shared top chrome

Both `Read` and `Review` should share the same top context frame.

#### Minimum shared header content
- project context if assigned
- paper title
- paper access signal
- review state signal
- blocker signal when present
- one primary next-action CTA
- mode switch:
  - `Read`
  - `Review`

#### Optional secondary hint
- recent artifact draft

### 4.2 Shared mode switch

The shell should clearly say:
- `Read` = evidence-assisted reading and note context
- `Review` = claim/evidence/provenance inspection

The mode switch should not imply:
- separate products
- separate ownership models
- different canonical truth sources

## 5. Recommended role of each mode

### 5.1 Read mode

#### Primary center
- note reading body
- compact structured review summary near the top

#### Supporting side content
- outline
- saved state summary
- related papers
- references
- lightweight downstream actions

#### Main job
- help the user understand the paper and its note context
- surface enough structure to know whether deeper review is needed

### 5.2 Review mode

#### Primary center
- PDF or document evidence viewer
- claim/evidence review surface

#### Supporting side content
- operational review state
- content review summary
- claim navigation
- timeline / run state
- artifact handoff hints

#### Main job
- help the user validate claims, evidence links, provenance, and unresolved review work

## 6. Recommended artifact relationship

Artifacts should remain:
- nearby
- visible
- easy to reach

Artifacts should not become:
- a third equal primary mode in the same shell
- a constant parallel lane that competes with reading/review

### Recommended treatment
- artifact entry should appear as a secondary action cluster in the shared header or context panel
- examples:
  - `Open meeting draft`
  - `Save protocol card`
  - `Recent draft available`

### Why
- artifact work is downstream and reversible
- it matters, but it should not replace evidence work as the core paper workspace identity

## 7. Desktop shell recommendation

### Shared desktop structure
- header:
  - project context
  - paper title
  - access/review/blocker signals
  - mode switch
  - primary CTA
- body:
  - left support rail
  - center dominant surface
  - right contextual/review rail

### Read mode emphasis
- center = reading
- right = review summary and references
- left = outline/context

### Review mode emphasis
- center = document/PDF
- right = claim/evidence/review
- left = paper list or local paper context rail

This means the shell stays familiar, but the center of gravity changes per mode.

## 8. Mobile shell recommendation

On mobile, the shell should remain mode-based, but not three-column.

### Shared mobile order
1. shared header
2. mode switch
3. primary center surface
4. collapsible context/review sheet
5. one sticky primary CTA when needed

This fits the current mobile approach in `PaperNoteDetailPage` and `WorkbenchLayout` without forcing a new navigation model.

## 9. What should not happen

To avoid over-design, do **not** do these yet:
- merge note detail and workbench into one giant page with all panels visible
- add `Synthesize` as a top-level peer to `Read` and `Review`
- introduce a wizard or stepper across read/review/artifact states
- duplicate structured state summaries in every region at equal emphasis
- force route unification before the shared shell language is clear

## 10. Current repo-fit implementation path

The correct next move is conceptual convergence first, not route convergence first.

### Phase 1: shared shell language
- same naming for the paper workspace across note detail and workbench
- shared top context block
- shared `Read / Review` mode expression
- shared artifact entry language

### Phase 2: shared chrome
- align headers
- align status blocks
- align CTA hierarchy

### Phase 3: optional route convergence
- only after the shell language proves useful

## 11. Text wireframe

### Shared paper workspace header

```text
Project: Ketone Ester Neuroprotection
Lee et al. 2024
Open access · Needs review 3 · Blocked 1

[Read] [Review]

Next: Review flagged claims in Workbench
[Resume review] [Save protocol card]
```

### Read mode

```text
Header

Compact review summary
- claims 12
- grounded 8
- unresolved 3
- saved state updated 2h ago

Reading body

Side context
- outline
- related papers
- references
```

### Review mode

```text
Header

Document viewer

Review side rail
- claim review summary
- saved checks
- active claim list
- artifact hint
```

## 12. Recommendation summary

- treat note detail and workbench as one paper workspace with two modes
- do not force immediate route merge
- do not make artifact a third equal mode
- do make the shared shell explicit through:
  - one header model
  - one mode model
  - one CTA hierarchy

The goal is not a bigger screen.
The goal is a clearer mental model.
