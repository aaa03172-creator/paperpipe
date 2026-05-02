# First Product Demo Runbook

Status: Active handoff note
Date: 2026-03-27
Owner: Lattice runtime maintainers
Purpose: provide one concise, repo-grounded demo and handoff script for the bounded first-product slice.
Canonical parents:
- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`
- `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

## Use This When

Use this note when you need to:

- demo the current first-product slice
- hand off the current product story to another maintainer or operator
- explain what is real now without reopening future lanes

Do not use this note to:

- redefine the product
- pitch `Project`, memory/chat, or generalized workspace lanes
- improvise a broader roadmap during the demo

## One-Sentence Product Line

> Lattice v1 is a local-first, paper-centered biomedical research workspace for a single primary operator, where schema-backed paper state, run/audit state, and bounded reproducible search design are the truth, and meeting-ready artifacts are evidence-linked downstream outputs.

## Demo Claim

The current demo should prove one bounded loop:

> paper -> structured understanding -> evidence review -> reproducible search design -> meeting-ready artifact

If the demo stays inside that loop, it is aligned.
If it needs `Project`, chat, collaboration, memory, or generalized experiment/task orchestration to feel complete, it has drifted.

## Representative Assets

Use these unless there is a clearly better fresh equivalent.

### Representative paper

- `paper_id`: `zotero:coricTargetingProdromalAlzheimer2015`
- `slug`: `zoterocoricTargetingProdromalAlzheimer2015`

Why:

- this paper already has a fresh successful deep-read rerun
- it has a visible paper-scoped `.pp/<slug>/state.json` sidecar
- it is now discoverable from the default `/papers` first payload

### Representative Research DNA

- `dna_mci_medium_chain_triglycerides_probe_20260312`

Why:

- it is a real bounded `Research DNA` asset with revision history and current `PILOT` state

### Representative Meeting Pack

- `meetingpack_20260328T003221552910Z_journal_club_0409564f`

Why:

- it is the current refreshed non-fixture pack
- it has `readiness = evidence_backed`
- it has saved trace coverage
- it validates and can regenerate
- it now carries the current uncertainty surfacing used by fresh runtime output

## 3-Minute Demo

### 1. Start at `/papers`

Say:

- this is the paper-centered entry surface
- the representative paper already shows `Saved state`

Show:

- the representative paper row
- one `No saved state` row only if you want to prove the UI does not hide missing truth

Do not say:

- this is a project dashboard
- this is a generalized research workspace index

### 2. Open `/papers/:slug`

Use:

- `/papers/zoterocoricTargetingProdromalAlzheimer2015`

Say:

- this page shows whether the runtime-managed paper-scoped structured state sidecar actually exists
- saved state and trace are visible

Show:

- `Saved state` panel
- loaded path `.pp/zoterocoricTargetingProdromalAlzheimer2015/state.json`
- structured claims and run history

Do not say:

- the summary itself is the truth
- the UI is reconstructing hidden state behind the scenes

### 3. Open `/workbench/:paperId`

Use:

- `/workbench/zotero:coricTargetingProdromalAlzheimer2015`

Say:

- this is the review surface for claims, evidence, and uncertainty

Show:

- that workbench is backend-real
- that it stays tied to the same paper/evidence path

Do not say:

- this is an autonomous copilot

### 4. Show `Research DNA`

Use current API or CLI.

Example:

```bash
curl http://localhost:8000/research-dna/dna_mci_medium_chain_triglycerides_probe_20260312
```

Say:

- this is the bounded reproducible search-design asset
- current status is `PILOT`

Show:

- `id`
- `revision`
- `status`
- query versions

Do not say:

- this already has a dedicated product-real viewer if you are not showing one

### 5. Open `/meeting-packs/:packId`

Use:

- `/meeting-packs/meetingpack_20260328T003221552910Z_journal_club_0409564f`

Say:

- this is the downstream draft artifact, not the truth store
- it is evidence-backed and traceable back to the representative paper and its saved state
- it also keeps current caution visible when citation-grounding metadata is unresolved

Show:

- readiness
- trace presence
- regenerate/validate state

Close with:

- Lattice currently helps one researcher move from paper to structured evidence state to reproducible search design to a meeting-ready draft without losing provenance

## 10-Minute Demo

Use the same flow, but add:

- one `No saved state` row to prove hidden truth is not being faked
- one quick mention that `Research DNA` is API/CLI today, not a frontend lane
- one trace view in `Meeting Pack`
- one explicit reminder that bounded extensions like protocol/chart/image exist but are not the product identity

## What Not To Promise

Do not describe the current product as:

- a project-first runtime
- a general project/document platform
- a chat-first or copilot-first product
- a broad memory workspace
- a full ELN/LIMS replacement
- a multi-user lab collaboration suite
- a system with repo-wide `Decision`, `Task`, or `Experiment` objects

## Q&A Short Answers

If asked what the product is:

- a local-first, paper-centered biomedical research workspace

If asked what the source of truth is:

- schema-backed structured paper state, run/audit state, and `Research DNA`

If asked what the user gets today:

- paper review, evidence-linked state, reproducible search-design state, and a meeting-ready downstream artifact

If asked what is not ready:

- project-first runtime, chat/memory surfaces, and generalized decision/experiment orchestration

## Fallback Rules

If one surface is unavailable during a live demo:

- do not invent a broader story
- fall back to the closest already-proven slice

Allowed fallback:

- `/papers` -> paper detail -> `Research DNA` -> `Meeting Pack`

Not allowed fallback:

- switching the story to `Project`, memory/chat, or generic workspace language

## Pre-Demo Checks

Before trusting `localhost:8000`, prefer a fresh backend start if the local server has been running for a long time.

Run only the narrow set:

```bash
./scripts/run_backend_api_smoke.sh
pytest -q tests/test_research_dna_service.py tests/test_evaluate_search.py tests/test_research_dna_cli.py
cd frontend && npm run verify:frontend:backend
./scripts/run_meeting_pack_verify.sh
python3 scripts/lint_docs.py
cd frontend && npm run e2e:backend:real-smoke
```

If the current shell makes `npm` or `npx` wrappers die without useful output, use the direct frontend CLI fallbacks:

```bash
cd frontend && node node_modules/eslint/bin/eslint.js .
cd frontend && node node_modules/typescript/bin/tsc -b --pretty false && node node_modules/vite/bin/vite.js build
cd frontend && env PAPERPIPE_REAL_SMOKE=1 PAPERPIPE_REAL_SMOKE_REQUIRE_CANDIDATES=1 node node_modules/@playwright/test/cli.js test -c playwright.backend.real.config.ts e2e/backend.spec.ts -g 'backend real-paper smoke' --reporter=line
```

## Handoff Links

- baseline Q&A: `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
- launch judgment: `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- rehearsal proof: `docs/reports/Release_Rehearsal_Run_2026-03-25.md`
- current stop/continue note: `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`

## Bottom Line

If you need to keep the story honest, stay inside this sentence:

> Lattice currently shows a real paper-centered evidence workflow, not a generalized platform.
