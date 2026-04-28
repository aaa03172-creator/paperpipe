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
- `paperpipe doctor --fix`

Use these when the operator needs to boot the local runtime or confirm the environment is healthy.
Current default behavior starts both the FastAPI backend and the background job worker; use `--no-worker` only for an intentional backend-only shell.

### Runtime hygiene

- `paperpipe doctor`
- `paperpipe doctor --fix`
- `paperpipe self-test`
- `paperpipe quarantine-fixture-states`
- `paperpipe archive-meeting-pack-noise`

Use these when the operator needs a human-readable setup diagnosis, a safe first-run config/local-folder bootstrap, a bounded readiness check, needs to quarantine hidden fixture structured states from the current vault, or needs to archive low-value Meeting Pack storage noise into a reversible quarantine path instead of deleting artifacts in place.

### Paper workflow

- `paperpipe import-pdf <path>`
- `paperpipe demo-first-paper`
- `paperpipe deepread <paper-id-or-doi>`
- `paperpipe read <paper-id-doi-or-title>`
- `paperpipe done <paper-id-doi-or-title>`
- `paperpipe repair-stats`
- `paperpipe export`

Use these when the operator needs to move from paper ingestion and deep read to saved paper state, repair missing stats artifacts, or export bounded outputs.

Current local-PDF entry boundary:
- The recommended first local-PDF path is the Web UI at `http://127.0.0.1:8000/ui/papers#import-pdf` after `lattice start` (the frontend route itself is `/papers#import-pdf`).
- The implemented API route is `POST /paper-notes/import-pdf`; it creates a saved paper note and a generated `userpdf-*` paper id.
- The CLI bridge `paperpipe import-pdf <path>` uses the same import contract and prints the generated id plus next routes.
- `paperpipe demo-first-paper` imports the bundled sample PDF through the same contract for zero-choice onboarding checks; do not treat the sample as biomedical evidence.
- `paperpipe deepread <paper-id-or-doi>` expects an already saved paper id/DOI or a PDF discoverable from configured local storage.

### Research DNA

`Research DNA` is a real API/CLI lane today, not a dedicated frontend viewer route.

- `paperpipe research-dna create`
- `paperpipe research-dna show`
- `paperpipe research-dna approve-pilot`
- `paperpipe research-dna update`
- `paperpipe research-dna interview`
- `paperpipe research-dna refine`
- `paperpipe research-dna pilot`
- `paperpipe research-dna runs`
- `paperpipe research-dna resume`
- `paperpipe research-dna rerank`
- `paperpipe research-dna materialize-guidance`
- `paperpipe research-dna guidance-artifact`
- `paperpipe research-dna guidance`
- `paperpipe research-dna guidance-history`
- `paperpipe research-dna recommend`
- `paperpipe research-dna rerank-gate`
- `paperpipe research-dna queue`
- `paperpipe research-dna next`
- `paperpipe research-dna session`
- `paperpipe research-dna progress`
- `paperpipe research-dna screen-next`
- `paperpipe research-dna screen-current`
- `paperpipe research-dna screening`
- `paperpipe research-dna lock`
- `paperpipe research-dna unlock`
- `paperpipe research-dna project-profile`

Use these when the operator needs to create, review, refine, pilot, inspect the current run list before choosing a `run_id`, resume the latest run without manually copying a `run_id` into separate reads, rerank, materialize a run-local guidance audit snapshot, re-read the latest saved guidance snapshot without writing a new one, inspect a combined advisory guidance read without changing the owner queue, inspect recent guidance history without opening artifact files manually, inspect an advisory queue recommendation without changing the owner queue, inspect a bounded rerank gate report for `eligible | not_eligible | insufficient_signal`, inspect ordered queues, review an active screening session snapshot together with the current recommendation and gate, inspect a compact screening-progress report without opening `manifest.json` or `metrics.json` manually, pick the next screening item, advance a screening session, screen the current next item with fewer round-trips, and now optionally use `--latest` on `screen-next` / `screen-current` to target the newest run without manually copying the `run_id`, receive the refreshed advisory recommendation and gate alongside those screening actions, inspect whether recent screening writes followed or diverged from the pre-write guidance, inspect a small run-local adherence summary without counting logs manually, and read stable reason/summary fields without client-side code mapping, screen manually, lock, or materialize a reproducible search-design asset.

## 3. Secondary implemented utilities

These are implemented and useful, but they are not the cleanest top-level product face.

### Bounded compiled-knowledge pilot

- `paperpipe paper-synthesis-generate <paper_slug>`
- `paperpipe paper-synthesis-show <synthesis_id>`
- `paperpipe paper-synthesis-list`

Use these when the operator needs to materialize or inspect the current paper-scoped compiled-knowledge pilot from canonical structured state plus selected run artifacts.

Current boundary:
- this is a bounded compiled-knowledge lane, not a new canonical truth owner
- it is implemented and operator-usable today, but it is not yet a primary first-product front-door workflow
- `paper-synthesis-generate --manifest` and `paper-synthesis-show --manifest` expose structured manifest-only inspection, while the default payload remains the compatibility bundle

### Bounded artifact-history capture

- `paperpipe artifact-history meeting-pack-review`
- `paperpipe artifact-history meeting-pack-outcome`
- `paperpipe artifact-history protocol-card-review`
- `paperpipe artifact-history protocol-card-outcome`

Use these when the operator needs to record explicit review or downstream-use outcomes for the currently instrumented artifact families without calling the API routes directly.

Current boundary:
- this is a bounded raw-log capture lane for selected families, not an automatic promotion system
- it does not infer outcomes from reads or open generic artifact-history writes for every artifact family
- it exists to help `meeting_pack` and `protocol_card` history accumulate so the advisory promotion gate can be re-evaluated on real operator traces

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

- `./scripts/run_first_paper_smoke.sh`
- `paperpipe test-fetch`
- `paperpipe process-test`
- `paperpipe test-filter`
- `paperpipe test-unpaywall`
- `paperpipe show-processor-gate-threshold-review`

Use `paperpipe show-processor-gate-threshold-review <run_dir>` when a bounded processor-gate threshold review artifact already exists and the operator needs a compact terminal summary of:
- current `high/low` thresholds
- drift warning heuristic
- latest replay-drift run status
- top drift transitions and probable causes

Current operator loop for this bounded calibration lane:

1. Generate replay-drift evidence with:
   `./.venv/bin/python scripts/eval/audit_processor_gate_replay_drift.py --run-id <drift_run_id>`
2. Turn that drift summary into an advisory threshold review with:
   `./.venv/bin/python scripts/eval/recommend_processor_gate_threshold_review.py --drift-summary <summary_path> --run-id <review_run_id>`
3. Inspect the threshold review artifact with:
   `./.venv/bin/paperpipe show-processor-gate-threshold-review <review_run_dir>`

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
- `paperpipe import-pdf`
- `paperpipe read`
- `paperpipe repair-stats`
- `paperpipe export`
  - `paperpipe research-dna ...`
- Implemented operator hygiene commands:
  - `paperpipe self-test`
  - `paperpipe quarantine-fixture-states`
  - `paperpipe archive-meeting-pack-noise`
- Implemented bounded pilot workflows:
  - `paperpipe paper-synthesis-generate`
  - `paperpipe paper-synthesis-show`
  - `paperpipe paper-synthesis-list`
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
