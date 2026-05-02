# First Product Demo Script (3 Minutes)

Status: Active handoff note
Date: 2026-03-27
Owner: Lattice runtime maintainers
Purpose: provide a short, presenter-ready spoken script for the bounded first-product demo.
Canonical parents:
- `docs/reports/First_Product_Demo_Runbook_2026-03-27.md`
- `docs/reports/First_Product_Demo_FAQ_2026-03-27.md`

## Before You Start

Use these assets:

- paper: `zotero:coricTargetingProdromalAlzheimer2015`
- slug: `zoterocoricTargetingProdromalAlzheimer2015`
- `Research DNA`: `dna_mci_medium_chain_triglycerides_probe_20260312`
- `Meeting Pack`: `meetingpack_20260328T003221552910Z_journal_club_0409564f`

## Script

### 0:00 - 0:20

"Lattice is a local-first, paper-centered biomedical research workspace for one primary operator.  
The current product is not a general project platform or a chatbot-first system.  
What it does well today is move from a paper, to structured evidence state, to reproducible search design, to a meeting-ready downstream artifact."

### 0:20 - 0:50

"I’ll start at `/papers`.  
This is the paper-centered entry surface.  
The key thing to notice is that the representative paper already shows `Saved state`, so I’m not relying on hidden backend state or manual reconstruction."

Action:

- open `/papers`
- point at the `Saved state` row for `coric`

### 0:50 - 1:25

"Now I’ll open the paper detail page.  
This page makes the canonical note-side structured state visible.  
You can see the saved state panel, the `.pp/.../state.json` path, and the structured claims and run history.  
So the system truth is inspectable here; I don’t have to explain it away verbally."

Action:

- open `/papers/zoterocoricTargetingProdromalAlzheimer2015`
- point at `Saved state`
- point at the `.pp/.../state.json` path

### 1:25 - 1:50

"From there, I can open the workbench.  
This is the review surface for claims, evidence, and uncertainty.  
The important part is that it’s still tied to the same paper and evidence path, not a detached summary screen."

Action:

- open `/workbench/zotero:coricTargetingProdromalAlzheimer2015`

### 1:50 - 2:20

"The next part is `Research DNA`.  
This is the bounded reproducible search-design asset in the current runtime.  
Today this is an API or CLI lane rather than a dedicated frontend page, so I’m showing it honestly that way.  
What matters is that we have revisioned, status-backed search-design state rather than ad hoc prompts."

Action:

- show `Research DNA` via API or CLI
- point at `id`, `revision`, `status`

### 2:20 - 2:50

"Finally, I’ll open the representative `Meeting Pack`.  
This is the downstream draft artifact.  
It is not the source of truth; it is generated from saved state.  
What matters here is that it’s evidence-backed, traceable to the paper, and can be validated or regenerated."

Action:

- open `/meeting-packs/meetingpack_20260328T003221552910Z_journal_club_0409564f`
- point at readiness
- point at the uncertainty note
- point at trace/regenerate state

### 2:50 - 3:00

"So the current Lattice story is simple: one researcher can go from a paper, to structured evidence state, to reproducible search design, to a meeting-ready draft, without losing provenance.  
What I’m not claiming today is project-first runtime, chat-first workflow, or a generalized research platform."

## If You Need One Short Closing Line

> Lattice currently demonstrates a real paper-centered evidence workflow, not a generalized platform.
