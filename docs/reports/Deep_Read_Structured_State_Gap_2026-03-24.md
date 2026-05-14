Status: Active blocker-identification note  
Date: 2026-03-24  
Owner: Runtime/product maintainers  
Canonical parents:
- `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/WEB_VIEWER.md`

# Deep Read Structured State Gap

## Purpose

Explain the current gap between:
- the release bar expectation of evidence-linked structured paper state
- the note/detail/workbench runtime path that reads canonical note-side structured state
- the current deep-read artifact lane

This is not a redesign proposal.
This is a blocker-identification note.

## Executive Call

Current repo behavior is split across two adjacent but not yet unified surfaces:

1. deep-read/job runtime writes paper/run artifacts under `storage/artifacts/<paper_id>/<run_id>/...`
2. note detail and other note-backed surfaces read canonical structured state from `vault/.pp/<slug>/state.json`

Current implementation evidence says:
- deep-read does **not** currently materialize note-side `.pp/<slug>/state.json` for the sampled real papers
- note detail does **not** currently bridge directly from deep-read artifacts when `.pp/<slug>/state.json` is missing
- therefore real-paper note detail can open successfully while still returning `structured_state = null`

This is the main structured-state blocker left by the release-scoped deep-read acceptance spot check.

## Confirmed Runtime Facts

### A. Note detail reads note-side canonical state only

Repo evidence:
- `backend/routers/paper_notes.py`
- `src/skills/storage.py`

Confirmed behavior:
- `GET /paper-notes/{slug}` calls `load_structured_state(vault_path, slug, frontmatter)`
- `load_structured_state()` reads only:
  - `.pp/<slug>/state.json`
  - or a frontmatter override in `pp.structured_path`
- it does not inspect `storage/artifacts/<paper_id>/<run_id>/...` directly

### B. Skill runs materialize the note-side canonical state

Repo evidence:
- `src/skills/runner.py`
- `docs/WEB_VIEWER.md`
- `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`

Confirmed behavior:
- `/skills/run` writes:
  - `vault/.pp/<slug>/runs/<ts>_<action>.json`
  - `vault/.pp/<slug>/state.json`
  - note frontmatter `pp.*`
- viewer docs explicitly describe this as the structured sidecar source of truth for skill runs

### C. Deep-read/job runtime writes artifacts, not note-side canonical state

Repo evidence:
- `backend/services/job_runner.py`
- `backend/routers/obsidian.py`

Confirmed behavior:
- deep-read/job runner writes files such as:
  - `document_artifact.json`
  - `index_artifact.json`
  - `claimset.json`
  - `claimset.resolved.json`
  - `run_meta.json`
  - `stats_report.json`
- these live under `storage/artifacts/<paper_id>/<run_id>/...`
- current `obsidian` router reads artifact bundles and syncs markdown blocks, but this code path does not write `.pp/<slug>/state.json`

### D. Real workspace evidence matches the split

Sample evidence from the live local vault/workspace:
- sampled real deep-read papers such as `zoteroparkDiscoveryDualactionSmall2022` have artifact bundles in `storage/artifacts/...`
- the same sampled notes do not currently have matching `.pp/<slug>/state.json`
- `GET /paper-notes/{slug}` therefore returns `structured_state = null`
- notes with existing `.pp/<slug>/state.json` such as `wenzelShortchainFattyAcids2020` do return populated `structured_state`

## Why This Matters For Release

The current first-product bar says:
- a deep-read run should leave inspectable, reusable structured paper state

But the current operator-facing note/runtime contract says:
- canonical note-backed structured state lives at `.pp/<slug>/state.json`

Those two statements only line up cleanly if one of these becomes true:

1. deep-read runs materialize `.pp/<slug>/state.json`
2. note detail/workbench explicitly bridges from deep-read artifacts when canonical note-side state is absent

Today, neither is happening for the sampled real papers.

That is why the release spot check remained `yellow` even after run-id surfacing was fixed.

## Safest Decision Options

### Option A. Deep-read owns note-side state materialization

Meaning:
- after a successful deep-read/job run, the runtime also writes or refreshes `.pp/<slug>/state.json`

Pros:
- matches the current note/detail/workbench canonical read path
- keeps one canonical reader contract for note-backed surfaces
- keeps meeting-pack/note-backed downstream readers aligned with existing `state.json`-first logic

Risk:
- requires a deterministic mapping from `paper_id -> slug -> vault note`
- must avoid silently overwriting richer skill-produced state in unsafe ways

### Option B. Note detail bridges from artifacts when canonical note-side state is absent

Meaning:
- `GET /paper-notes/{slug}` would synthesize a structured response from `storage/artifacts/...` as a fallback

Pros:
- smaller immediate release unblock for legacy deep-read bundles
- may reduce backfill needs for older notes

Risk:
- creates two structured-state assembly paths
- increases the chance of divergence between:
  - note-side canonical state
  - artifact-derived fallback state
- weakens the current `state.json`-first boundary if treated as a permanent default

## Current Best Judgment

Safest current interpretation:
- `.pp/<slug>/state.json` remains the canonical note-backed structured-state contract
- the current blocker is not that this contract is wrong
- the blocker is that deep-read/job outputs are not yet consistently promoted into that contract for real-paper notes

In other words:
- do not widen the reader to a broad artifact-first fallback by default without an explicit contract decision
- first decide whether deep-read should promote a bounded canonical projection into `.pp/<slug>/state.json`

## Safest Next Actions

1. Confirm the intended canonical rule:
   - `state.json` stays the canonical note-backed structured-state contract
2. Use the bounded design note for:
   - how deep-read should promote claim/evidence/run summaries into `.pp/<slug>/state.json`
   - how to avoid clobbering richer skill-run state
   - See: `docs/reports/Deep_Read_Note_State_Promotion_Design_2026-03-24.md`
3. Only if promotion is rejected, evaluate an explicit artifact fallback as a temporary release-only compatibility lane

## Conclusion

The remaining deep-read release blocker is now precise:

- not run-id surfacing
- not missing real papers
- not missing artifact bundles

The blocker is:
- canonical note-side structured state and deep-read artifact outputs are still separate lanes for real-paper notes, and the current release bar expects them to connect.
