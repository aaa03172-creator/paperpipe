# Current Worktree Lane Triage

Status: repository triage note
Date: 2026-04-07
Lane: `smallest-safe-patch`

## Purpose

Turn the current dirty worktree into a small set of execution lanes again before more implementation gets mixed together.

This note is intentionally narrow. It does not claim:

- that the whole repository should be cleaned in one pass
- that every changed file belongs in one future branch
- that the current user-visible frontend lane is the same thing as the broad backend/runtime pile

It answers a smaller question:

- given the current tree on 2026-04-07, what is stable, what is still open, and what should we treat as separate lanes?

## Current Snapshot

`git status --short` at capture time:

- total dirty paths: `374`
- `git diff --stat`: `210 files changed, 16076 insertions(+), 1528 deletions(-)`

Top-level concentration:

- `docs`: `99`
- `frontend`: `84`
- `tests`: `83`
- `src`: `41`
- `scripts`: `24`
- `goldset`: `16`
- `snapshots`: `8`
- `backend`: `4`

Highest-concentration second-level paths:

- `docs/reports`: `64`
- `frontend/e2e`: `44`
- `frontend/src`: `30`
- `goldset/manifests`: `15`
- `src/services`: `12`
- `scripts/eval`: `9`
- `src/schemas`: `9`
- `src/agents`: `7`

Current runtime truth at capture time:

- `./.venv/bin/python -m src.cli self-test --json` returned `degraded`, but only because `watch_folder` is missing or not configured
- `./.venv/bin/python -m src.cli start --no-open` booted successfully on `http://127.0.0.1:8000`
- `/ui`, `/ui/papers`, note detail, and workbench deep links all returned `200 text/html`
- targeted browser regression subset remained green:
  - note detail -> protocol handoff
  - image-evidence note handoff
  - core keyboard baseline
  - `/papers` default and active-filter keyboard recovery

Interpretation:

- the repo is broader and dirtier than the last 2026-03-29 lane map
- the current product baseline is still real and re-verifiable
- the primary risk now is scope mixing, not immediate frontend breakage

## Lane Map

### L1. Viewer / Runtime-Readiness / UX Lane

Estimated size: `127` paths

Main signals:

- `frontend/src/*`
- `frontend/e2e/*`
- `frontend/playwright*.ts`
- `frontend/README.md`
- `backend/main.py`
- `backend/routers/paper_notes.py`
- `backend/routers/obsidian.py`
- `docs/UX_REVIEW_REPORT_*`
- `docs/WEB_VIEWER.md`
- `docs/reports/Biomedical_*`
- `docs/reports/Frontend_*`
- `docs/reports/Research_Workspace_*`

Current judgment:

- this is still the strongest coherent user-facing lane in the tree
- it now includes the 2026-03-30 to 2026-04-01 keyboard/focus hardening work
- it is still the best active lane if the goal is “keep the product usable and demoable”

Observed stability:

- the core `/ui` runtime is startable
- the recent browser-backed UX subset is still green
- current live inventory is non-empty across the main artifact lanes:
  - paper notes `121`
  - meeting packs `95`
  - chart packs `1`
  - method comparisons `1`
  - image evidence `1`
  - protocol cards `2`

Recommended handling:

1. Treat this as the best next execution lane for user-visible work.
2. Keep it separated from extraction and packaging decisions.
3. Prefer the existing backend Playwright path for verification instead of broad ad hoc probing.

### L2. Core Runtime / Backend / Contracts Lane

Estimated size: `110` paths

Main signals:

- `src/*` outside the clearly isolated extraction/runtime-packaging files
- `backend/services/job_runner.py`
- `src/agents/*`
- `src/config.py`
- `src/cli.py`
- `src/exporter.py`
- `src/obsidian.py`
- `src/processor.py`
- `src/llm_provider.py`
- many backend/runtime tests

Current judgment:

- this is not one safe patch
- it is a large mixed lane covering runtime behavior, job orchestration, citation/provider behavior, and multiple backend contracts
- this lane should be split again before anyone stages it as one unit

Recommended handling:

1. Do not treat this as “the next thing” by default.
2. Reopen only through a narrower owner slice:
   - jobs/runtime orchestration
   - obsidian/export path behavior
   - citation/provider contract work
3. Keep it out of viewer-only signoff unless a specific backend owner path is selected first.

### L3. Extraction / Eval / Runtime-Specialty Lane

Estimated size: `61` paths

Main signals:

- `goldset/*`
- `snapshots/extraction_*`
- `scripts/eval/*`
- `src/services/citation_grounding.py`
- `src/services/evidence_extraction_sidecar.py`
- `src/services/bc5cdr_eval.py`
- `src/schemas/evidence_extraction.py`
- `src/schemas/bc5cdr_eval.py`
- extraction/runtime-specialty tests

Current judgment:

- keep this lane frozen by default
- it is evaluation-heavy and materially separate from the current viewer/runtime UX work
- the main risk is accidental mixing with user-visible runtime changes

Recommended handling:

1. Do not mix this lane into frontend/runtime signoff.
2. Reopen only if the explicit goal is extraction-sidecar or evaluation work.
3. Keep its artifacts and reports separate from shareable runtime polish.

### L4. Personal Runtime / Packaging Lane

Estimated size: `31` paths

Main signals:

- `packaging/*`
- `docs/MACOS_PERSONAL_RUNTIME_*`
- `docs/WINDOWS_PERSONAL_RUNTIME_ALPHA.md`
- `docs/PERSONAL_RUNTIME_*`
- `scripts/build_personal_runtime_*`
- `scripts/release_macos_personal_runtime.py`
- `scripts/check_windows_personal_runtime_smoke.py`
- `scripts/measure_deepread_runtime.py`
- `src/services/runtime_readiness.py`
- `src/services/runtime_paths.py`
- related tests

Current judgment:

- this is a distinct productization lane
- it is compatible with the viewer/runtime-readiness story, but it should still ship separately
- it is not the same question as “is the current workspace UI healthy?”

Recommended handling:

1. Use this lane only when the explicit goal is installability or packaged delivery.
2. Keep it separate from viewer UX commits and extraction work.
3. Treat current `watch_folder` degraded status as packaging/setup debt, not a reason to reopen viewer UX by default.

### L5. Docs / Meta / Generated-Residue Lane

Estimated size: `40+` paths

Main signals:

- `.playwright-cli/`
- `output/`
- `storage/chart_packs/`
- `storage/image_evidence/`
- `storage/protocol_cards/`
- `.codex/skills/*`
- policy/report/docs files that are not tightly owned by a single behavior lane

Current judgment:

- this lane should not be staged blindly
- some of it is valuable documentation, some is generated residue, and some is runtime inventory
- this lane needs deliberate curation rather than more execution

Recommended handling:

1. Keep generated/runtime residue out of any product-facing commit by default.
2. Decide intentionally which reports are durable and which are just local analysis.
3. Treat `.playwright-cli/`, `output/`, and runtime storage artifacts as operational residue unless a user explicitly wants them preserved.

## What Changed Since The 2026-03-29 Triage

- the viewer/runtime lane is now better verified than before
- the broad backend/core lane is materially larger and less safe to treat as one patch
- packaging/installability is now a clearer standalone lane
- the current runtime is healthier than the worktree size suggests
- the repo risk has shifted from “can the UI run?” to “can we keep lane boundaries disciplined?”

## Recommended Action Order

### 1. Keep L3 frozen

Default posture:

- no extraction/runtime-specialty widening by default
- keep eval artifacts out of viewer/runtime closure work

### 2. If we continue implementation now, choose exactly one lane

Recommended first choice:

- `L1. Viewer / Runtime-Readiness / UX`

Recommended alternatives:

- `L4. Personal Runtime / Packaging` if the goal is installability or release prep
- a carefully re-split subset of `L2` if a backend contract issue becomes the real blocker

### 3. Do not treat L2 or L5 as one branch-sized unit

This is the main anti-pattern to avoid now:

- do not bundle the broad runtime/backend pile or the mixed docs/generated residue into one “cleanup” pass

## Short Version

The current repository is a healthy-but-broad multi-lane worktree.

Safe default:

1. keep extraction/eval frozen
2. pick exactly one active lane
3. treat viewer/runtime UX as the best next user-visible lane
4. split core backend and generated/docs residue again before trying to stage them
