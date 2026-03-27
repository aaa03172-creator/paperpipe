# Release Rehearsal Run

Status: Active release evidence note  
Date: 2026-03-25  
Owner: Runtime/product maintainers  
Current posture anchors:
- `docs/reports/Acceptance_Proof_Drift_Review_2026-03-24.md`
- `docs/reports/Current_Baseline_Recheck_2026-03-18.md`
- `docs/reports/Docs_Only_Cleanup_Closeout_2026-03-25.md`

## Purpose

Record one bounded release rehearsal run against the current first-product story.

This run answers:
- can the current repo be shown honestly without hidden-truth narration?
- do the `Must-Not-Ship` rows stay false on the current bounded product slice?
- what, if anything, remains small enough for one more bounded follow-up?

This is not:
- a new runtime spec
- a broad product QA matrix
- a reason to reopen `Project`, memory/chat, or generalized workspace lanes

## Representative Assets Used

### Representative paper

- `zotero:coricTargetingProdromalAlzheimer2015`
- resolved slug: `zoterocoricTargetingProdromalAlzheimer2015`

Why this paper:
- it is the paper from the fresh successful rerun that produced canonical note-side `.pp/<slug>/state.json`

### Optional honesty-check row

- `paper-e2e-list-missing-stats-001`

Why used:
- it is a current `/paper-notes` list row with `structured_state_present = false`
- it confirms the list can still show `No saved state` directly

### Representative Research DNA

- `dna_mci_medium_chain_triglycerides_probe_20260312`

Why used:
- it is a real bounded `Research DNA` asset with query versions, pilot metadata, and current `PILOT` state

### Representative Meeting Pack

- `meetingpack_20260325T062516207912Z_journal_club_0409564f`

Why used:
- it is a newer non-fixture journal-club pack generated from the representative real paper
- it carries the current trace contract, validate/regenerate metadata, and evidence-backed readiness without depending on backend-visual fixture outputs

## Verification Used

### API/runtime inspection

- FastAPI `TestClient` requests against:
  - `/paper-notes`
  - `/paper-notes/resolve-by-paper-id`
  - `/paper-notes/{slug}`
  - `/papers/{paper_id}`
  - `/research-dna/{dna_id}`
  - `/meeting-packs`
  - `/meeting-packs/{pack_id}`
  - `/meeting-packs/{pack_id}/trace`
  - `/meeting-packs/{pack_id}/validate`

### Current route-smoke anchor

```bash
cd frontend && npm run e2e:backend:real-smoke
```

Result:
- `1 passed`
- current real-paper workbench/backend route proof stayed green

## Rehearsal Results

| Step | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `/papers` entry | `pass` | default `/paper-notes?page_size=10` now surfaces `zotero:coricTargetingProdromalAlzheimer2015` first; a separate row with `structured_state_present = false` is still present for transparency checks | The representative paper is now discoverable from the default first payload instead of depending on the search flow. |
| paper detail | `pass` | `/paper-notes/zoterocoricTargetingProdromalAlzheimer2015` returned `structured_state` with `1` run and `4` claims; `context_trace` included `.pp/zoterocoricTargetingProdromalAlzheimer2015/state.json` and `structured_state_loaded -> loaded` | Current paper detail can be explained from visible note-side canonical state and trace metadata without hand reconstruction. |
| workbench | `pass` | `cd frontend && npm run e2e:backend:real-smoke` -> `1 passed` (`backend real-paper smoke keeps claim jump and highlight rendering stable`) | Current route-level proof supports the representative paper/workbench leg of the story. |
| `Research DNA` | `pass` | `/research-dna/dna_mci_medium_chain_triglycerides_probe_20260312` returned `revision = 3`, `status = PILOT`, query versions `v1/v2`, and pilot/governance metadata | The lane is current-runtime-real, but it remains an API/CLI lane rather than a dedicated frontend viewer. The rehearsal stayed honest about that. |
| `Meeting Pack` | `pass` | `/meeting-packs/meetingpack_20260325T062516207912Z_journal_club_0409564f` returned `status = draft` and `readiness = evidence_backed`; `/validate` returned `markdown_sync.status = in_sync` and `can_regenerate = true`; `/trace` returned `available = true` with `matched_paper_slugs = [zoterocoricTargetingProdromalAlzheimer2015]` | The current downstream-artifact story can now use a non-fixture representative pack that carries the saved trace contract. |
| final product sentence | `pass` | The flow can still be summarized as `local-first, paper-centered, paper-first, single-operator-first biomedical research workspace` without mentioning `Project`, memory/chat, or generalized platform lanes | The current story stays inside the approved product boundary. |

## Must-Not-Ship Confirmation

| Condition | Result | Notes |
| --- | --- | --- |
| Demo requires explaining away missing provenance | `false` | The representative paper detail and the non-fixture pack both preserve evidence/uncertainty language. |
| Demo works only because the operator narrates hidden system truth or hidden storage | `false` | The current paper detail exposes note-side canonical state and `context_trace` directly; `Research DNA` was shown honestly as API/CLI rather than pretending a UI exists. |
| Meeting Pack depends on mock data or invented support | `false` | The rehearsal now uses a newer non-fixture pack generated from the representative real paper, not the backend-visual fixture packs. |
| Research DNA appears only as a conceptual future lane | `false` | Current API/runtime asset exists and is inspectable now. |
| Core viewer routes are only visually plausible and not backend-real | `false` | Backend real-paper smoke stayed green and current backend APIs returned real data. |
| Product story depends on gated `Project`, memory, or chat surfaces | `false` | The rehearsal never used those lanes. |
| Run failures or partial artifact writes are hidden instead of visible | `false` | The representative paper row still shows `Action needed` because stats are missing, rather than silently reporting a clean state. |

## Overall Judgment

Current result:
- the rehearsal is `green enough` for the bounded first-product story
- no `Must-Not-Ship` row turned `true`
- the previous `Meeting Pack` representative partial is now closed on the bounded current-runtime slice

## Smallest Credible Follow-Ups

No further closeout PR is required for the bounded first-product story.

Optional only:

1. keep older non-fixture packs as historical reference artifacts rather than external demo representatives

Do not:
- reopen `Project`
- treat fixture packs as the first-product story
- widen this into a broad artifact/trace redesign

## Bottom Line

This rehearsal supports the current release judgment:

> PaperPipe can already be shown honestly as a local-first, paper-centered biomedical research workspace on the bounded current-runtime slice.

The remaining issues are no longer architecture blockers.
They are optional historical-artifact housekeeping decisions.
