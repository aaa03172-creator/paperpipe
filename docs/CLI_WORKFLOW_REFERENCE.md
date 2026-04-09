## CLI Workflow Reference

Status: Active  
Date: 2026-03-27  
Owner: Runtime/product maintainers  
Purpose: distinguish the implemented CLI surface from API routes, task-taxonomy docs, and legacy utilities.

Canonical parents:
- `README.md`
- `docs/README.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`

## 1. Current shape

- Both `paperpipe` and `lattice` point to the same Typer entrypoint in `src/cli.py`.
- The CLI is real and implemented, but not every command is equal product surface.
- Use this doc to answer:
  - which commands are implemented today
  - which commands are current operator-facing workflows
  - which commands are narrower utilities, diagnostics, or retained legacy surfaces

Do not use this doc to imply:
- a broader generic-agent command system
- a project-centric runtime
- a front-page promise that every implemented command is part of the current first-product story

## 2. Current recommended operator-facing subset

These are the commands most aligned with the current first-product boundary.

### Runtime shell

- `lattice start`
- `paperpipe start`
- `paperpipe doctor`

Use these when the operator needs to boot the local runtime or confirm the environment is healthy.

### Paper workflow

- `paperpipe deepread <paper-id-or-doi>`
- `paperpipe read <paper-id-doi-or-title>`
- `paperpipe done <paper-id-doi-or-title>`
- `paperpipe repair-stats`
- `paperpipe export`

Use these when the operator needs to move from paper ingestion and deep read to saved paper state, repair missing stats artifacts, or export bounded outputs.

### Research DNA

`Research DNA` is a real API/CLI lane today, not a dedicated frontend viewer route.

- `paperpipe research-dna create`
- `paperpipe research-dna show`
- `paperpipe research-dna approve-pilot`
- `paperpipe research-dna update`
- `paperpipe research-dna interview`
- `paperpipe research-dna refine`
- `paperpipe research-dna pilot`
- `paperpipe research-dna rerank`
- `paperpipe research-dna materialize-guidance`
- `paperpipe research-dna guidance`
- `paperpipe research-dna recommend`
- `paperpipe research-dna rerank-gate`
- `paperpipe research-dna queue`
- `paperpipe research-dna next`
- `paperpipe research-dna session`
- `paperpipe research-dna screen-next`
- `paperpipe research-dna screen-current`
- `paperpipe research-dna screening`
- `paperpipe research-dna lock`
- `paperpipe research-dna unlock`
- `paperpipe research-dna project-profile`

Use these when the operator needs to create, review, refine, pilot, rerank, materialize a run-local guidance audit snapshot, inspect a combined advisory guidance read without changing the owner queue, inspect an advisory queue recommendation without changing the owner queue, inspect a bounded rerank gate report for `eligible | not_eligible | insufficient_signal`, inspect ordered queues, review an active screening session snapshot together with the current recommendation and gate, pick the next screening item, advance a screening session, screen the current next item with fewer round-trips, receive the refreshed advisory recommendation and gate alongside those screening actions, and read stable reason/summary fields without client-side code mapping, screen manually, lock, or materialize a reproducible search-design asset.

## 3. Secondary implemented utilities

These are implemented and useful, but they are not the cleanest top-level product face.

- `paperpipe fetch`
  - on-demand paper search, with optional save path
- `paperpipe organize`
  - organize local PDFs into the library structure
- `paperpipe stats`
  - show reading-status/library counts from indexes
- `paperpipe reconcile`
  - reconcile approved decisions into stored paper status
- `paperpipe watch`
  - watch-folder processing for local PDFs
- `paperpipe watch-downloads`
  - downloads-folder watcher for manual-required PDFs

## 4. Retained diagnostics, maintenance, and legacy surface

These commands are implemented, but they should not be used as the top-level product taxonomy.

### Diagnostics and smoke helpers

- `paperpipe test-fetch`
- `paperpipe process-test`
- `paperpipe test-filter`
- `paperpipe test-unpaywall`

### Maintenance or destructive utilities

- `paperpipe clear-logs`
- `paperpipe reset`
- `paperpipe run`

### Narrow or legacy lanes

- `paperpipe ask`
  - local RAG query helper; not a basis for chatbot-first product messaging
- `paperpipe profiles`
- `paperpipe audit`
  - legacy profile-management lanes; do not treat these as the main current search-design surface when `Research DNA` exists

## 5. How to talk about commands honestly

When documenting or demoing the product, keep these distinctions explicit:

- Implemented runtime commands:
  - `lattice start`, `paperpipe start`
- Implemented CLI workflows:
  - `paperpipe deepread`
  - `paperpipe read`
  - `paperpipe repair-stats`
  - `paperpipe export`
  - `paperpipe research-dna ...`
- API routes:
  - FastAPI endpoints under `backend/main.py` and related routers
- Documentation workflow labels:
  - task-first phrases such as `Run a deep read` or `Generate a meeting-ready artifact`

Do not collapse those four layers into one.

## 6. Quick help paths

- `paperpipe --help`
- `paperpipe research-dna --help`
- `lattice --help`

Representative examples:

```bash
paperpipe deepread --help
paperpipe research-dna show --help
```

If you need the current product boundary before choosing a command, read:
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
- `docs/Product_Positioning_Principles.md`
