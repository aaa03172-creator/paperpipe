# Launch Readiness Checklist

Status: Active release gate note  
Date: 2026-03-24  
Owner: Runtime/product maintainers  
Canonical parents:
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/Product_Positioning_Principles.md`
- `docs/reports/Current_Baseline_Recheck_2026-03-18.md`

## Purpose

Turn the first shippable product bar into a practical release gate.

Use this note to answer:
- are we ready to present the current repo as a coherent first product?
- which launch-defining areas are already green?
- which areas are still yellow or red?
- what exact verification set should be rerun before a real ship/demo decision?

This is not a new runtime spec.

## Status Vocabulary

- `green`: repo-grounded evidence says the item is implemented and currently credible for the first product bar
- `yellow`: usable and partially evidenced, but still missing a tighter release-proof, stronger enforcement, or a fresh acceptance pass
- `red`: not credible enough to count toward first-product readiness
- `n/a`: intentionally out of the first-product gate

## Current Snapshot Rule

This checklist records the current launch picture from existing repo evidence as of 2026-03-24.

Important:
- statuses below are based on the latest available reports, bounded specs, code paths, and recorded verification
- this note does **not** claim that every verification command was rerun during this specific documentation pass
- older baseline-green reports support credibility, but they do not override newer release-scoped blocker notes or acceptance spot checks
- before any real external release/demo decision, rerun the verification set in the `Release Verification Set` section

## Go / No-Go Rule

Default release rule:
- any `red` item in a launch-defining row = `no-go`
- `yellow` is allowed only with explicit operator sign-off and a clear explanation of why the yellow item does not break the first-product promise
- all `Must-Not-Ship` conditions must remain false

## Executive Summary

Current assessment:
- first-product shape and scope boundary: `green`
- core biomedical loop credibility: `green` on the bounded current-runtime proof slice
- release-proof verification and acceptance evidence: mixed `green/yellow`
- main remaining risk: not missing product shape, but keeping rehearsal-level trust checks and provenance consistency honest after the now-explicit legacy-bundle boundary decision

Working judgment:
- the repo is close enough to talk about a first-product bar credibly
- it is reasonable to treat the deep-read/job path as `green enough` for the bounded first-product proof slice
- the remaining `yellow` rows are now narrower rehearsal-level and trust-language items, not an unresolved current-runtime deep-read credibility question
- the representative-paper deep-read/job path itself is no longer the main blocker after the fresh successful rerun recorded in `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md`

## Launch-Defining Checklist

| Area | Status | What must be true | Current evidence | Notes / blocker judgment |
| --- | --- | --- | --- | --- |
| Product shape is paper-centered, paper-first, artifact-first, single-operator-first | `green` | First product story stays centered on `papers`, `jobs`, `artifacts`, `Research DNA`, and `Meeting Pack`; not `projects`/memory/chat | `docs/Product_Positioning_Principles.md`, `frontend/src/App.tsx`, `docs/reports/Project_Memory_API_Gate_2026-03-23.md`, `docs/API_CHAT_CONTRACT.md` | Boundary is currently explicit and defensible. |
| Deep-read/job path produces inspectable paper state | `green` | Real paper can run through deep-read/job flow and leave reusable saved state instead of only logs | `backend/services/job_runner.py`, `backend/main.py`, `docs/WEB_VIEWER.md`, `docs/API_CHAT_CONTRACT.md`, `docs/reports/Current_Baseline_Recheck_2026-03-18.md`, `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md`, `docs/reports/Deep_Read_Structured_State_Gap_2026-03-24.md`, `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md`, `docs/reports/Deep_Read_Legacy_Bundle_Release_Boundary_2026-03-25.md` | The fresh representative rerun on `zotero:coricTargetingProdromalAlzheimer2015` completed successfully and promoted note-side canonical state. Older legacy/partial bundles are now explicitly outside the bounded v1 proof slice unless later backfilled. |
| Paper-notes/workbench review surface is product-real | `green` | Operator can open and inspect real backend-backed note state and operational state | `frontend/src/App.tsx`, `backend/routers/paper_notes.py`, `frontend/e2e/backend.spec.ts`, `docs/WEB_VIEWER.md`, `docs/reports/Current_Baseline_Recheck_2026-03-18.md` | Current baseline recheck, active viewer spec, and backend workbench coverage support this as a real surface. |
| Research DNA loop is real | `green` | `DRAFT -> PILOT -> LOCKED` plus screening/refine loop works as a bounded reproducible search-design lane | `docs/RESEARCH_DNA.md`, `src/profiles/research_dna_schema.py`, `src/profiles/research_dna_service.py` | Implemented and supported by real pilot/probe reports. |
| Meeting Pack is a real downstream anchor artifact | `green` | Pack generation from real saved state works, and validate/rerender/regenerate boundaries are explicit | `docs/MEETING_PACK.md`, `src/meeting_packs/service.py`, `backend/routers/meeting_packs.py`, `docs/archive/Meeting_Pack_V1_Checklist_Review_2026-03-13.md` | Current checklist review cleared `7/7`; this is the strongest current downstream artifact lane. |
| Provenance and uncertainty remain visible | `yellow` | Saved state and downstream artifacts keep evidence linkage and visible caution instead of polishing weak support into certainty | `docs/Evidence_and_Uncertainty_Rules.md`, `docs/MEETING_PACK.md`, `docs/WEB_VIEWER.md`, `docs/Citation_Grounding_Audit_2026-03-13.md` | Core rule is explicit and implemented, but citation readiness is still presence-based in places rather than full verification-based. |
| Non-destructive rerun/regenerate behavior is credible | `yellow` | Reruns and artifact regeneration do not silently corrupt state or leave hidden partial bundles | `docs/MEETING_PACK.md`, `src/meeting_packs/store.py`, `src/services/paper_ops_summary.py`, `docs/archive/Meeting_Pack_V1_Checklist_Review_2026-03-13.md` | Meeting Pack rollback/regenerate path is strong; broader deep-read acceptance should still be spot-checked directly for release. |
| Release-defining verification set is identified | `green` | A narrow release gate exists and is not confused with the entire repo | `scripts/run_backend_api_smoke.sh`, `scripts/run_meeting_pack_verify.sh`, `frontend/package.json`, `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`, `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md` | The release set is now concrete; historical baseline reports are supporting context only and do not replace a fresh rerun. |
| Gated/internal-only lanes stay outside product readiness | `green` | `Project Memory`, `/api/chat`, and other gated surfaces do not leak into the launch story | `docs/reports/Project_Memory_API_Gate_2026-03-23.md`, `docs/API_CHAT_CONTRACT.md`, `docs/reports/Deferred_Lanes_Recheck_2026-03-24.md` | Current gating is explicit. |

## Shippable Extensions Checklist

These do not decide first-product readiness on their own.

| Area | Status | Current judgment | Evidence |
| --- | --- | --- | --- |
| Method Comparison | `green` | Real bounded extension; good to show after the core loop | `docs/METHOD_COMPARISON.md`, `docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md` |
| Chart Pack | `green` | Real bounded extension; should remain clearly downstream | `docs/CHART_PACK.md`, `docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md` |
| Protocol Knowledge | `green` | Real bounded extension; not a launch-defining project/protocol platform | `docs/PROTOCOL_KNOWLEDGE.md`, `docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md` |
| Image Evidence | `green` | Real bounded sidecar; not a core truth layer | `docs/IMAGE_EVIDENCE.md`, `docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md` |

## Gated / Non-Product Surfaces

These must not be counted as first-product readiness evidence.

| Surface | Status | Why not counted | Evidence |
| --- | --- | --- | --- |
| Project Memory | `n/a` | Backend-only hold; API/viewer opening would change product shape | `docs/reports/Project_Memory_API_Gate_2026-03-23.md` |
| `/api/chat` | `n/a` | Stub-only; no provider, memory, or retrieval runtime | `docs/API_CHAT_CONTRACT.md` |

## Must-Not-Ship Checklist

All of these must remain false.

For this table:
- `false` means current repo evidence and the recorded release rehearsal do not indicate that the condition is true
- `yellow` means the condition is not supported by the current product story, but it still lacks strong enough current-runtime or rehearsal evidence to call it closed

| Condition | Current check | Evidence | Notes |
| --- | --- | --- | --- |
| Demo requires explaining away missing provenance | `false` | `docs/Evidence_and_Uncertainty_Rules.md`, `docs/MEETING_PACK.md`, `docs/WEB_VIEWER.md`, `docs/reports/Release_Rehearsal_Run_2026-03-25.md` | The recorded rehearsal kept provenance/trust explanation inside visible system state rather than operator hand-waving. |
| Demo works only because an operator narrates hidden system truth, hidden storage, or manual reconstruction steps | `false` | `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`, `docs/WEB_VIEWER.md`, `docs/reports/Release_Rehearsal_Run_2026-03-25.md` | Rehearsal evidence now exists for the visible-truth rule rather than doc-only confidence. |
| Meeting Pack depends on mock data or invented support | `false` | `docs/archive/Meeting_Pack_V1_Checklist_Review_2026-03-13.md` | Real-input pack generation has been checked. |
| Research DNA is only conceptual and cannot be piloted/refined/locked | `false` | `docs/RESEARCH_DNA.md` | Real probe history exists. |
| Core viewer routes are only visually plausible and not backend-real | `false` | `docs/reports/Current_Baseline_Recheck_2026-03-18.md` | Backend build/playwright evidence exists. |
| Product story depends on gated `Project`, memory, or chat surfaces | `false` | `docs/reports/Project_Memory_API_Gate_2026-03-23.md`, `docs/API_CHAT_CONTRACT.md` | Current release bar explicitly excludes them. |
| Run failures or partial artifact writes can silently leave broken local state | `false` | `docs/MEETING_PACK.md`, `docs/archive/Meeting_Pack_V1_Checklist_Review_2026-03-13.md`, `docs/reports/Release_Rehearsal_Run_2026-03-25.md` | The current bounded rehearsal and Meeting Pack rollback/validate/regenerate checks do not indicate silent partial-state corruption on the release slice. |

## Release Verification Set

Before a real ship/demo decision, rerun this narrow set.

### Required commands

```bash
./scripts/run_backend_api_smoke.sh
pytest -q tests/test_research_dna_service.py tests/test_evaluate_search.py tests/test_research_dna_cli.py
cd frontend && npm run verify:frontend:backend
./scripts/run_meeting_pack_verify.sh
python3 scripts/lint_docs.py
```

Latest rerun note:
- the 2026-03-24 rerun passed `run_backend_api_smoke.sh`, the `Research DNA` test slice, `run_meeting_pack_verify.sh`, `lint_docs.py`, `frontend build`, and `frontend e2e:backend:real-smoke`
- `cd frontend && npm run verify:frontend:backend` also passed after aligning the paper-note detail E2E expectations with the current `Saved state` panel ordering
- the 2026-03-25 release-boundary decision now treats older legacy/partial bundles as out-of-slice historical evidence unless explicitly backfilled later

### Required release-scoped checks

- concrete frontend/backend route coverage command:

```bash
cd frontend && npm run e2e:backend:real-smoke
```

- route families that must remain covered by the release-scoped frontend/backend proof:
  - `/papers`
  - `/papers/:slug`
  - `/workbench/:paperId`
  - `/meeting-packs`
  - `/meeting-packs/:packId`
- a narrow `Research DNA` acceptance rerun on a real example
- a narrow deep-read acceptance spot check on real papers against the `Minimum Deep Read Success Bar`

## Deep Read Acceptance Spot Check Template

Use a small real-paper slice such as `5-10` papers.

For each paper, record:
- deep-read enqueue/run success
- inspectable saved state written
- minimum structured state fields present
- claims evidence-linked or uncertainty-marked
- `issues_state` / `ops_summary` / readiness signals visible when relevant
- note detail opens against real backend data
- rerun does not silently corrupt saved state

Suggested result vocabulary:
- `pass`
- `partial`
- `fail`

## Current Blockers To Close Before Confident Go

No blocker-shaped follow-ups remain on the bounded current-runtime slice.

Optional closeout only:

1. Provenance/trust language consistency across release-defining surfaces
- Why: the evidence-first rule is explicit, but citation/grounding readiness is still not equivalent to full verification everywhere.
- This is no longer a launch-slice viability blocker.

## Suggested Usage

Use this checklist in three steps:

1. mark each launch-defining row as `green`, `yellow`, or `red`
2. rerun the `Release Verification Set`
3. convert remaining `yellow` or `red` rows into blocker PRs only if they threaten the first-product promise

## Conclusion

Current best judgment:
- first-product positioning is ready enough to evaluate honestly
- the launch-defining product story is mostly real
- the remaining work is not broad redesign
- the remaining work is optional provenance/trust consistency closeout, not a current-runtime deep-read or rehearsal rescue effort
