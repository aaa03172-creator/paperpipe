# Release Rehearsal Checklist

Status: Active execution note  
Date: 2026-03-25  
Owner: Runtime/product maintainers  
Canonical parents:
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`

## Purpose

Run one bounded operator rehearsal before any real external demo or first-product presentation.

This checklist exists to confirm:
- the current product story can be shown without hand-waving
- the remaining `Must-Not-Ship` rows stay false in practice
- the current paper-centered runtime can be explained using visible system truth rather than operator narration

This is not:
- a new runtime spec
- a broad QA plan
- a reason to reopen `Project`, memory/chat, or generalized workspace lanes

## Preconditions

Use this checklist only after these conditions are already true:

- the release verification set is green enough
- the representative fresh deep-read rerun is green
- the legacy/partial bundle boundary is explicit

Current anchors:
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md`
- `docs/reports/Deep_Read_Legacy_Bundle_Release_Boundary_2026-03-25.md`

## Scope

### In scope

- `/papers`
- `/papers/:slug`
- `/workbench/:paperId`
- `Research DNA` as the current API/CLI lane
- `/meeting-packs`

### Out of scope

- first-class `Project`
- `Project Memory`
- `/api/chat`
- broad legacy-bundle rescue
- generalized experiment/decision/task platform claims
- multi-user or lab-governance stories

## Representative Assets

Use the current repo-grounded representatives below unless there is a better fresh equivalent.

### Representative paper

- `zotero:coricTargetingProdromalAlzheimer2015`

Reason:
- this is the paper used in the fresh successful rerun that produced canonical note-side `.pp/<slug>/state.json`

Anchor:
- `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md`

### Optional honesty-check paper

- any `/papers` row that currently shows `No saved state`

Reason:
- this proves the UI does not hide missing canonical state
- use it only as a transparency check, not as the center of the product story

### Representative Research DNA

- `dna_mci_medium_chain_triglycerides_probe_20260312`

Current reality:
- this is a real `Research DNA` asset with query versions, pilot governance, logs, and benchmark-backed pilot metadata
- `Research DNA` is currently an API/CLI lane, not a frontend viewer route

Anchors:
- `research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/profile.yaml`
- `docs/RESEARCH_DNA.md`

### Representative Meeting Pack

- any real pack visible in `/meeting-packs` that was generated from saved state

Rule:
- do not use mock/demo seed content
- if no real pack is available, the rehearsal should stop and record that as a blocker

## Rehearsal Flow

### 1. Enter from `/papers`

Action:
- open `/papers`
- locate the representative paper row
- record both:
  - the row's `paper_id` for `/workbench/:paperId`
  - the row/detail slug for `/papers/:slug`

Pass:
- the row is present and backend-real
- `Saved state` is visible for the representative paper
- operator can explain the row using visible labels only

Optional honesty check:
- find one row with `No saved state`
- verify that the missing state is labeled directly rather than hidden behind generic healthy-looking UI

Fail:
- the representative paper cannot be found through the current route
- the row looks healthy but saved-state truth still has to be explained manually
- `No saved state` is hidden or ambiguous

### 2. Open paper detail

Action:
- open `/papers/:slug` for the representative paper using the slug resolved from the selected row or the current note-detail route

Pass:
- the `Saved state` panel is visible
- status reads `Loaded`
- the expected `.pp/<slug>/state.json` path is shown
- run history and structured claims do not collapse into misleading generic empty states
- provenance/uncertainty language remains visible where support is partial

Fail:
- the detail page requires operator narration to explain where the real truth lives
- the page shows generic empty cards without distinguishing `missing sidecar` vs `loaded but empty`
- the detail page implies certainty without visible evidence/uncertainty cues

### 3. Open workbench

Action:
- open `/workbench/:paperId` for the same representative paper using the `paper_id` from the selected `/papers` row

Pass:
- the workbench opens against real backend state
- claims/evidence/uncertainty are inspectable
- the surface still reads as reviewable structured state, not as a one-shot answer screen

Fail:
- the workbench looks plausible but cannot be tied back to the paper/run/artifact truth path
- the operator has to explain hidden storage or reconstruct missing system state verbally

### 4. Show `Research DNA` honestly

Action:
- show the representative DNA through the current API or CLI lane
- acceptable examples:
  - `GET /research-dna/dna_mci_medium_chain_triglycerides_probe_20260312`
  - `paperpipe research-dna show dna_mci_medium_chain_triglycerides_probe_20260312`

Pass:
- the current `Research DNA` object is visible as a bounded reproducible search-design asset
- at minimum, the rehearsal can show:
  - `id`
  - `revision`
  - `status`
  - query versions
  - pilot/governance metadata
- the operator does not pretend there is already a dedicated frontend viewer if there is not

Fail:
- the rehearsal claims a product-real UI surface that does not exist
- `Research DNA` can only be described abstractly with no current runtime evidence

### 5. Show Meeting Pack as the downstream anchor

Action:
- open `/meeting-packs`
- open one real pack generated from saved state at `/meeting-packs/:packId`

Pass:
- the pack is clearly a draft/downstream artifact
- evidence lineage or trace remains visible
- readiness/regenerate semantics remain visible enough to explain where the pack came from

Fail:
- the pack is mock-only
- the pack cannot be tied back to saved state or visible trace
- the operator has to claim invisible support that the UI/API does not expose

### 6. Close with the correct product sentence

Action:
- summarize the product in one sentence

Pass:
- the summary stays within the approved product shape:
  - local-first
  - paper-centered
  - paper-first
  - single-operator-first
  - biomedical research workspace
- the summary uses current paper/job/artifact/Research DNA/Meeting Pack vocabulary

Fail:
- the closing story depends on `Project`, memory/chat, generalized workspace, or collaboration lanes
- the explanation shifts into future product promises to make the current demo feel complete

## Must-Not-Ship Confirmation Table

Record each row during the rehearsal.

| Condition | Expected result | Rehearsal result | Notes |
| --- | --- | --- | --- |
| Demo requires explaining away missing provenance | `false` | `todo` |  |
| Demo works only because the operator narrates hidden system truth or hidden storage | `false` | `todo` |  |
| Meeting Pack depends on mock data or invented support | `false` | `todo` |  |
| Research DNA appears only as a conceptual future lane | `false` | `todo` |  |
| Core viewer routes are only visually plausible and not backend-real | `false` | `todo` |  |
| Product story depends on gated `Project`, memory, or chat surfaces | `false` | `todo` |  |
| Run failures or partial artifact writes are hidden instead of visible | `false` | `todo` |  |

## Capture Template

Use one line per step.

| Step | Result (`pass` / `partial` / `fail`) | Evidence captured | Follow-up needed |
| --- | --- | --- | --- |
| `/papers` entry |  |  |  |
| paper detail |  |  |  |
| workbench |  |  |  |
| `Research DNA` |  |  |  |
| `Meeting Pack` |  |  |  |
| final product sentence |  |  |  |

## Exit Rule

Treat the rehearsal as `green enough` when:
- every step is at least `pass` or clearly bounded `partial`
- all `Must-Not-Ship` rows stay `false`
- any remaining issue is small enough for one bounded follow-up patch

Treat the rehearsal as `no-go` when:
- any `Must-Not-Ship` row becomes `true`
- the flow depends on hidden storage narration or future-lane hand-waving
- the downstream artifact step requires mock data or invented provenance

## Bottom Line

The rehearsal should prove one narrow claim:

> the current PaperPipe repo can be shown honestly as a local-first, paper-centered biomedical research workspace without relying on hidden truth, mock provenance, or future product lanes.
