Status: Active bounded design note
Date: 2026-03-24
Owner: Runtime/product maintainers
Canonical parents:
- `docs/reports/Deep_Read_Structured_State_Gap_2026-03-24.md`
- `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

# Deep Read Note-State Promotion Design

## Purpose

Define the safest bounded way for the deep-read/job lane to promote canonical note-side structured state for real-paper notes.

This is not:
- a broad reader fallback proposal
- a storage/artifact schema replacement
- a paper-notes redesign

It is a narrow design note for connecting the existing deep-read artifact lane to the existing note-side canonical state contract.

## Executive Call

Safest current direction:

1. keep `vault/.pp/<slug>/state.json` as the canonical note-backed structured-state contract
2. do not add a broad artifact-first fallback to `GET /paper-notes/{slug}` by default
3. add a bounded promotion step after a successful deep-read/job run
4. only promote when the runtime can resolve a real note slug and the artifact bundle is modern enough to produce a trustworthy canonical projection

This keeps the current viewer and downstream readers aligned with one canonical note-side path instead of creating two permanent structured-state assembly paths.

## Confirmed Runtime Constraints

### A. Canonical note-backed structured state is still `.pp/<slug>/state.json`

Repo evidence:
- `src/skills/storage.py`
- `backend/routers/paper_notes.py`
- `src/meeting_packs/source_resolver.py`

Confirmed behavior:
- note detail reads `.pp/<slug>/state.json` or `pp.structured_path`
- meeting-pack source resolution also treats `.pp/<slug>/state.json` as the canonical paper-sidecar source
- no current note-backed reader uses `storage/artifacts/<paper_id>/<run_id>/...` as its default state source

### B. Deep-read already knows enough to find the note and artifact bundle

Repo evidence:
- `backend/services/job_runner.py`

Confirmed behavior:
- deep-read runtime already has:
  - `paper_id`
  - `run_id`
  - `artifact_dir`
  - `run_meta.json`
  - `bootstrap_meta.json`
- it already resolves the note path through `_resolve_note_path_for_paper()`
- it already performs a best-effort note markdown upsert near the end of the job

### C. Current state schema is skill-run-shaped

Repo evidence:
- `src/schemas/skills.py`
- `src/skills/storage.py`

Confirmed behavior:
- `StructuredPaperState.runs` currently stores `SkillRunRecord`
- `SkillRunRecord.action` is constrained by `SkillActionName`
- current allowed actions are:
  - `extract_markdown`
  - `validate_citations`
  - `critical_appraisal`

Implication:
- deep-read promotion cannot truthfully record `action="deep_read"` without a bounded schema extension
- using an existing skill action name as a placeholder would be misleading and should be avoided

### D. Existing merge helpers are reusable, but only with source-ownership guardrails

Repo evidence:
- `src/skills/storage.py`

Confirmed behavior:
- `merge_state()`, `update_frontmatter_pp()`, and `write_structured_state()` already implement the canonical write path
- but `merge_state()` will replace `claimset` when a new claimset is provided

Implication:
- naive deep-read promotion could clobber richer note-side state produced by the skills lane
- the promotion path needs an ownership rule before reusing the shared write helpers

## Safest Integration Shape

## 1. Promotion happens in the deep-read/job lane, not the note reader

Preferred insertion point:
- `backend/services/job_runner.py`
- after artifact files are written and after note-path resolution succeeds
- near the current best-effort deep-read markdown upsert

Why this is safer:
- the reader stays simple and canonical
- artifact interpretation happens once at write time, not repeatedly at read time
- downstream note-backed surfaces keep one state contract

## 2. Promotion is eligibility-gated

Promotion should run only when all of these are true:
- a real note path resolves for the current `paper_id`
- a stable note slug can be derived from that note path
- the artifact bundle for `run_id` exists
- the bundle is modern enough to support a trustworthy projection

Safest phase-1 eligibility bar:
- `run_meta.json` exists
- `claimset.resolved.json` exists

Optional phase-1 supporting inputs:
- `bootstrap_meta.json`
- `stats_report.json`

Why:
- this avoids fabricating canonical state from legacy/partial bundles that already failed the release spot check

## 3. Promotion writes a bounded canonical projection, not a raw artifact mirror

Canonical target remains:
- `vault/.pp/<slug>/state.json`

Projected fields should map as follows:

| Canonical field | Promotion source | Notes |
| --- | --- | --- |
| `paper_slug` | note slug | derived from resolved note path |
| `updated_at` | promotion write time | same rule as existing state writes |
| `runs` | promoted deep-read run record | requires bounded schema support for `deep_read` |
| `signals` | `run_meta.json` + `bootstrap_meta.json` + derived counts | keep provenance and readiness visible |
| `claimset` | `claimset.resolved.json` | prefer resolved claimset only in phase 1 |
| `entities` | bounded projection from resolved claimset and/or existing artifact metadata | do not invent if unavailable |
| `mesh` | bounded projection only if trustworthy source exists | otherwise empty |
| `outcomes` | bounded projection only if trustworthy source exists | otherwise empty |

Important:
- this should be a normalized canonical projection
- it should not copy the entire raw artifact payload into `.pp`

## 4. Promotion must be ownership-aware

Safest phase-1 ownership rule:
- if `.pp/<slug>/state.json` is missing, promotion may create it
- if `.pp/<slug>/state.json` exists and `signals.state_source == "deep_read_promotion"`, promotion may refresh it for the same note
- otherwise, do not overwrite existing canonical state automatically

Recommended signal additions:
- `state_source = "deep_read_promotion"`
- `state_source_run_id = <run_id>`
- `state_source_version = "v1"`

Why:
- avoids clobbering richer skill-produced state
- keeps future refresh/backfill logic explicit

## 5. Frontmatter update stays minimal

After a successful promotion:
- set or preserve `pp.structured_path`
- update `pp.last_run`
- merge bounded promotion signals into `pp.signals`

Do not:
- add a second frontmatter pointer for artifact-first state
- rewrite unrelated note metadata
- append a new markdown summary section by default

The current deep-read markdown upsert can remain a separate best-effort presentation layer.

## Required Bounded Schema Adjustment

Before implementation, the smallest truthful schema change is:
- extend `SkillActionName` to include `deep_read`

Why this is the smallest honest change:
- it preserves the existing `StructuredPaperState` model
- it preserves the existing `runs` list shape
- it avoids inventing a second run-record schema only for deep-read

What this should not trigger:
- no skill-system redesign
- no generic run-history schema migration
- no replacement of `StructuredPaperState`

## What To Reject

Reject these by default:

1. Broad artifact-first fallback in `GET /paper-notes/{slug}`
- creates two parallel state-assembly paths
- weakens the current canonical note-side contract

2. Promotion from legacy partial bundles by default
- risks writing canonical state from incomplete artifacts
- hides the very release gap the acceptance spot check exposed

3. Raw artifact mirroring into `.pp`
- bloats the note-side sidecar
- turns a canonical projection into an unbounded dump

4. Overwriting richer existing `.pp` state without source ownership checks
- risks corrupting skill-produced state
- makes rerun behavior less trustworthy

## Safest Phase-1 Implementation Slice

If this design is implemented, the safest first slice is:

1. extend `SkillActionName` with `deep_read`
2. add a small promotion helper used only by `backend/services/job_runner.py`
3. gate promotion on:
   - resolved note path
   - `run_meta.json`
   - `claimset.resolved.json`
4. create `.pp/<slug>/state.json` only when no canonical state exists yet
5. record `state_source = "deep_read_promotion"` in signals
6. leave legacy/partial bundles unchanged in phase 1

This is enough to test the release bar without widening the reader.

Implementation status as of 2026-03-24:
- a bounded phase-1 gate is now wired in `backend/services/job_runner.py`
- it promotes canonical note-side state only for eligible modern bundles
- it skips overwrite when an existing canonical `.pp` state is owned by another source
- it does not backfill legacy sampled bundles automatically

## Safest Next Experiments

1. Build one non-mutating projection helper that loads `run_meta.json`, `bootstrap_meta.json`, and `claimset.resolved.json` and returns an in-memory `StructuredPaperState` candidate for a single sampled paper.
2. If the projection looks credible, wire that helper into `job_runner.py` behind the phase-1 eligibility gate and create `.pp/<slug>/state.json` only when it does not already exist.
3. Rerun the deep-read release acceptance spot check on one representative real paper with a fresh run and verify that note detail now surfaces canonical `structured_state` without changing the reader path.

## Conclusion

The current blocker is precise, and the safest solution is also precise:

- keep `.pp/<slug>/state.json` as the canonical note-backed state contract
- promote deep-read outputs into that contract in the job lane
- do it only for modern, trustworthy bundles
- do not widen note detail into a permanent artifact-first fallback without a separate explicit contract decision
- after the current phase-1 implementation, the next proof step is one fresh real-paper rerun rather than another broad contract decision
