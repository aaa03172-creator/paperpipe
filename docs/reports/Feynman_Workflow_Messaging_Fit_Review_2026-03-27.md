# Feynman Workflow/Messaging Fit Review

Status: Applied fit review  
Date: 2026-03-27  
Owner: Runtime/product maintainers  
Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/README.md`

## 1. Current repo reading summary

### Repo-confirmed current structure

- The current product identity is explicitly `local-first`, `paper-centered`, `paper-first`, and `single-operator-first`, not project-first or chatbot-first.
  - Anchors:
    - `docs/Product_Positioning_Principles.md`
    - `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
    - `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
- The actual first-product runtime surface is centered on:
  - `papers`
  - deep-read jobs and run artifacts
  - paper-note detail and workbench review
  - `Research DNA`
  - `Meeting Pack`
  - bounded artifact viewers for method comparison, chart pack, image evidence, and protocol cards
  - Anchors:
    - `frontend/src/App.tsx`
    - `backend/main.py`
    - `docs/WEB_VIEWER.md`
    - `docs/RESEARCH_DNA.md`
    - `docs/MEETING_PACK.md`
- The current public README is mostly a runtime/ops guide.
  - It explains `lattice start`, env vars, CI gates, and monitoring.
  - It does not currently present the product through a task-first or artifact-first lens.
  - Anchor:
    - `README.md`
- The repo already has a real CLI surface beyond `start`.
  - Implemented commands in `src/cli.py` include:
    - runtime/ops: `start`, `doctor`, `audit`, `watch`, `watch_downloads`, `clear_logs`, `reconcile`, `reset`
    - paper workflow: `read`, `deepread`, `repair-stats`, `export`
    - fetch/process utilities: `fetch`, `run`, `organize`, `stats`, `done`
    - `research-dna` subcommands: `create`, `show`, `approve-pilot`, `update`, `interview`, `refine`, `pilot`, `screening`, `lock`, `unlock`, `project-profile`
  - Anchor:
    - `src/cli.py`
- Role separation already exists conceptually, but not as Feynman-style bundled runtime agents.
  - PaperPipe separates:
    - reasoning personas
    - profile context
    - output/view modes
  - Anchor:
    - `docs/PERSONA_MODE_BOUNDARY.md`

### What the current product can definitely do

- Start a local FastAPI + UI runtime with `lattice start` / `paperpipe start`.
- Enqueue and inspect deep-read jobs.
- Review saved paper state in `/papers`, `/papers/:slug`, and `/workbench/:paperId`.
- Create, refine, and lock `Research DNA`.
- Generate and inspect `Meeting Pack` artifacts.
- Inspect bounded artifact families:
  - method comparisons
  - chart packs
  - image evidence
  - protocol cards

### What is still weak, unclear, or easy to overstate

- The top-level README under-explains the product story and over-emphasizes ops/security details relative to user workflows.
- The repo has a real CLI surface, but the current docs do not clearly distinguish:
  - implemented CLI commands
  - API routes
  - documentation workflow labels
- Artifact-centered value is real, but scattered across feature docs rather than clearly surfaced at the top.
- `/api/chat` exists only as a stub and should not support chatbot-first positioning.
- `Project Memory` exists only as a gated backend slice and should not support project-centric product messaging.

### Inference

- The repo is stronger than the current README suggests.
- The main issue is not missing generic-agent capability, but weak top-level workflow framing and fragmented artifact messaging.

## 2. What to adopt from Feynman

### 2.1 Task-first workflow framing

What fits:
- Describe the product through operator tasks rather than through subsystems first.

Why it fits:
- PaperPipe already supports a coherent task loop:
  - ingest a paper
  - run deep read
  - inspect evidence-linked state
  - refine reproducible search design
  - generate a meeting-ready artifact

Where to apply:
- `README.md`
- `docs/README.md`
- top-level product copy blocks

How to adapt:
- Do not invent Feynman-style task verbs as if they are the primary CLI.
- Use task-first sections such as:
  - `Run a deep read`
  - `Inspect saved paper state`
  - `Refine search design`
  - `Generate a meeting-ready artifact`
  - `Inspect bounded artifact viewers`

### 2.2 Artifact-centered expression

What fits:
- Emphasize outputs the operator can reopen, inspect, validate, and regenerate.

Why it fits:
- PaperPipe already has strong bounded artifact families:
  - `Meeting Pack`
  - `Method Comparison`
  - `Chart Pack`
  - `Image Evidence`
  - `Protocol Card`

Where to apply:
- `README.md`
- docs index and product overview sections

How to adapt:
- Describe these as bounded artifact viewers or downstream draft artifacts.
- Do not present them as proof of a generalized platform.

### 2.3 Cleaner explanation of role separation

What fits:
- Feynman makes “who does what” legible.

Why it fits:
- PaperPipe already has a strong conceptual split, but it is buried in deeper docs.

Where to apply:
- README product explanation
- docs map or baseline Q&A

How to adapt:
- Explain the existing PaperPipe distinction explicitly:
  - reasoning personas
  - profile context
  - output/view modes
- Do not translate these into autonomous runtime agents unless the runtime actually changes.

### 2.4 More product-like packaging of current capabilities

What fits:
- Present the repo like a coherent product, not just a service harness.

Why it fits:
- The current runtime and UI are already product-shaped enough for a stronger top-level explanation.

Where to apply:
- README intro
- quick-start framing
- docs index entrypoint

How to adapt:
- Keep the current honesty level.
- Do not copy Feynman’s broad “AI research agent” framing.

## 3. What not to adopt

### 3.1 Generic research-agent positioning

Why it is risky:
- It would directly conflict with the current paper-first, biomedical-first product shape.

Repo-specific downside:
- It would blur the current first-product boundary and overstate unsupported areas such as generalized project memory, broad chat, or autonomous research completion.

### 3.2 Feynman-style bundled agent roles as runtime reality

Why it is risky:
- PaperPipe already has a cleaner separation between reasoning, context, and presentation.

Repo-specific downside:
- It would encourage unnecessary multi-agent framing and conflict with `docs/PERSONA_MODE_BOUNDARY.md`.

### 3.3 Overclaimed task completion language

Examples to avoid:
- “does literature review, replication, audit, and peer review in minutes”
- “autonomous research agent”
- “handles end-to-end research automatically”

Why it is risky:
- PaperPipe’s honest strength is inspectable evidence workflow, not broad autonomous completion.

### 3.4 Local/offline/reproducibility overstatement

Why it is risky:
- PaperPipe should keep saying only what is actually supported:
  - local-first
  - inspectable
  - reproducible within the bounded current runtime

Repo-specific downside:
- Broad offline or fully reproducible claims could overpromise beyond current proof.

### 3.5 Command-style taxonomy that sounds implemented when it is not

Why it is risky:
- Feynman’s README uses task commands as the product face.

Repo-specific downside:
- If PaperPipe copies that style too literally, it may imply unimplemented command verbs or workflows.

## 4. Recommended changes (prioritized)

### 4.1 Immediate

- Rewrite the top of `README.md` so it starts with product identity before env vars and security controls.
- Add a `What you can do today` section that maps to real supported workflows.
- Add a short `What this is not` block to preserve message honesty.
- Surface bounded artifact families as current outputs, not as platform claims.
- Add a short `How roles work` explanation that points to reasoning persona / profile / output mode separation.

### 4.2 Small implementation

- Add clearer CLI help or docs grouping around current implemented commands.
- Consider a thin documentation taxonomy for workflow groups:
  - runtime
  - paper workflow
  - search design
  - downstream artifacts
  - ops
- Consider a small `/ui` or docs-linked product overview page only if it stays honest and bounded.

### 4.3 Later

- Revisit whether README should split into:
  - product overview
  - runtime/ops guide
- Revisit whether bounded artifact viewers need a shared artifact-overview index page in the product surface.
- Revisit whether task labels should surface in UI cards more consistently across triage and bounded viewers.

## 5. Concrete proposed edits

### README intro rewrite

Proposed replacement for the top of `README.md`:

> Lattice is a local-first, paper-centered biomedical research workspace for a single primary operator. It helps you move from paper ingestion and deep read to evidence-linked structured state, reproducible search-design refinement, and meeting-ready downstream artifacts without hiding provenance or uncertainty.

Follow immediately with:

- current runtime shape:
  - paper-first
  - job/run/artifact-first
  - human-reviewable
  - additive rather than fully autonomous

### Feature/workflow section rewrite

Proposed section title:

`## What you can do today`

Proposed bullets:

- `Run a deep read`
  - enqueue a paper, inspect run state, and review saved paper state
- `Inspect saved paper state`
  - use paper notes and workbench to review evidence, uncertainty, and operational status
- `Refine reproducible search design`
  - create, pilot, screen, refine, and lock `Research DNA`
- `Generate a meeting-ready artifact`
  - produce and reopen `Meeting Pack` drafts from saved structured state
- `Inspect bounded artifact viewers`
  - review method comparisons, chart packs, image evidence, and protocol cards

### Naming / command taxonomy proposal

Do not present all of these as equal product commands.
Split them into three clearly labeled groups:

- Implemented runtime commands
  - `lattice start`
  - `paperpipe start`
- Implemented CLI workflows
  - `paperpipe deepread`
  - `paperpipe read`
  - `paperpipe repair-stats`
  - `paperpipe export`
  - `paperpipe research-dna ...`
- Documentation workflow labels
  - `Run a deep read`
  - `Review saved paper state`
  - `Refine search design`
  - `Generate a meeting-ready artifact`
  - `Inspect bounded artifact viewers`

### Messaging guardrails

Add or preserve wording like:

- `local-first evidence workflow`
- `paper-first workspace`
- `bounded artifact viewers`
- `human-reviewable`
- `schema-backed structured state remains the source of truth`

Avoid wording like:

- `AI research agent`
- `autonomous research assistant`
- `project-centric workspace`
- `replicates and reviews papers automatically`
- `chat-first biomedical copilot`

## 6. Patch plan

### Files to change first

- `README.md`
  - Purpose:
    - add honest product identity at the top
    - add task-first workflow section
    - distinguish runtime commands from workflows
  - Scope:
    - top intro
    - quick-start framing
    - one new product/workflow section
  - Conflict risk:
    - low to medium
    - risk is mostly making the README too long or mixing product and ops content

- `docs/README.md`
  - Purpose:
    - add a task-first “where to start” path, not only spec-first navigation
  - Scope:
    - one small section near the top
  - Conflict risk:
    - low

- `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
  - Purpose:
    - optional supporting copy alignment if README wording changes
  - Scope:
    - small wording sync only
  - Conflict risk:
    - low

### Recommended order

1. rewrite `README.md` top section
2. add workflow-first path to `docs/README.md`
3. optionally align baseline QA wording

### Safer stop point

Stop after README + docs map if:
- the product message is already clearer
- no new claims were introduced
- the current first-product boundary remains intact

## 7. Current closeout judgment

Immediate doc-only items from this fit review are now applied:

- `README.md`
  - product identity moved to the top
  - `What You Can Do Today` added
  - `What this repo is not` added
  - runtime commands, CLI workflows, UI surfaces, and representative API examples separated more explicitly
- `docs/README.md`
  - task-first entrypoint added
- `docs/CLI_WORKFLOW_REFERENCE.md`
  - implemented command groups now documented with honest operator-facing vs utility/legacy separation

Current judgment:

- keep these changes
- do not widen this lane into broader product repositioning
- do not add Feynman-style bundled runtime roles
- do not add invented task commands or generic-agent messaging

Deferred on purpose:

- splitting `README.md` into a separate product overview and runtime runbook
- building a new shared artifact-overview surface
- pushing task labels deeper into viewer UI without a separate route-level need

Recommended stop point:

- treat this messaging/doc lane as closed unless a new runtime boundary problem or README honesty issue appears
- move the next work pass to a different product or release bottleneck instead of continuing copy churn

## Source notes

### Repo-confirmed facts

- Product identity and first-product boundary are defined in local canonical docs.
- Current supported UI routes and API surfaces are real and implemented.
- CLI commands beyond `start` exist in `src/cli.py`.

### Target-repo-confirmed facts

- The public Feynman README uses task-first command framing.
- It presents bundled `Researcher`, `Reviewer`, `Writer`, and `Verifier` roles.
- It emphasizes artifact outputs and product-style packaging.

### Inference

- The main value of the comparison is messaging and workflow framing, not runtime architecture adoption.
