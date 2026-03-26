# Viewer Truth-Visibility Drift Review

Status: Active review note  
Date: 2026-03-24  
Owner: Runtime/design maintainers  
Scope: paper-note detail, workbench, and active bounded artifact viewers vs the "visible system truth" product rule

## Purpose

Check whether the current viewer surfaces expose real saved state, provenance, and runtime boundaries directly enough that:

- an operator can inspect system truth without narration
- empty states do not silently hide missing canonical state
- optional debug traces stay optional without erasing the source of truth

This note is not a new spec.

## Executive Call

Current repo is mostly aligned on viewer truth visibility.

Strong current center:
- workbench and bounded artifact viewers already expose operational state, warnings, retrieval/source traces, and raw or near-raw saved payloads clearly
- backend paper-note detail responses already carry both canonical `structured_state` and deterministic `context_trace`
- current viewer docs already reject detail flows that require operator narration to explain missing canonical state

Main drift:
- paper-note detail UI is only a partial adopter of that visibility rule today
- the API exposes `context_trace`, including explicit `structured_state_loaded -> missing` cases, but the current detail UI does not render `context_trace`
- when `structured_state` is absent, current detail cards collapse into generic empty states instead of explicitly saying that no canonical sidecar state was loaded

This is a viewer hardening gap, not a runtime architecture contradiction.

## 1. What Is Aligned

### A. Current viewer docs already prefer visible system truth over narrated demos

Repo anchors:
- `docs/WEB_VIEWER.md`

Why this is aligned:
- the current viewer doc explicitly says detail surfaces should not require operator narration to explain missing canonical structured state or which saved sidecar path was used
- it also keeps `context_trace` as an optional/debug disclosure rather than treating hidden trace data as a substitute for visible system truth

### B. Workbench already exposes inspectable operational truth

Repo anchors:
- `frontend/src/app/components/ArtifactPanel.tsx`
- `docs/WEB_VIEWER.md`

Why this is aligned:
- the workbench artifact panel separates `Content Review` from `Operational State`
- it exposes Obsidian mirror preview, evidence-link review, and `Raw Artifact JSON`, so the operator can inspect saved output directly instead of relying on narration

### C. Bounded artifact viewers already surface source-linked review state directly

Repo anchors:
- `frontend/src/app/pages/MeetingPackPage.tsx`
- `frontend/src/app/pages/ChartPackPage.tsx`
- `frontend/src/app/pages/MethodComparisonPage.tsx`

Why this is aligned:
- `Meeting Pack` renders readiness, validation warnings, regenerateability, and retrieval trace directly
- `Chart Pack` and `Method Comparison` visibly expose warnings, source refs, transforms, or cell-level evidence status instead of hiding them behind a secondary debug mode

### D. Paper-note detail API already provides the needed truth payloads

Repo anchors:
- `backend/routers/paper_notes.py`
- `src/schemas/paper_notes.py`

Why this is aligned:
- the detail route returns both canonical `structured_state` and deterministic `context_trace`
- the backend explicitly records whether `structured_state_loaded` ended in `loaded` or `missing`, including the expected `.pp/<slug>/state.json` source path

## 2. Drift Found

### A. `WEB_VIEWER` allowed `context_trace` omission too loosely

Repo evidence:
- `docs/WEB_VIEWER.md`

Issue:
- the old wording said current UI may ignore `context_trace` safely
- that is too broad now that the viewer doc explicitly rejects narration as the only way to explain missing canonical state

Impact:
- readers can incorrectly infer that any visibility gap around canonical state/source-path reasoning is acceptable as long as the trace exists in the API

Action taken:
- tightened the viewer doc so `context_trace` can stay behind an optional/debug disclosure, but missing canonical structured state and sidecar-source decisions should not require operator narration

### B. Paper-note detail UI does not currently render `context_trace`

Repo evidence:
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `frontend/src/app/lib/types.ts`

Issue:
- the API and schema support `context_trace`, but the detail page does not consume or render it anywhere
- this is not fatal by itself, but it means the current detail surface is not the strongest implementation of the "visible system truth" rule

Current judgment:
- acceptable as a partial implementation
- still a legitimate future hardening target if detail-page debugging or release-proof visibility becomes more important

### C. Missing `structured_state` is only indirectly visible in paper-note detail

Repo evidence:
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `backend/routers/paper_notes.py`

Issue:
- when `structured_state` is absent, the backend knows and records `structured_state_loaded -> missing`
- the current detail UI instead falls through to generic empty states like `No structured runs recorded yet.` and `No structured claims are available for this note.`

Impact:
- an operator can still infer that structured output is missing, but the UI does not yet distinguish:
  - no canonical sidecar loaded
  - canonical sidecar loaded but empty
  - canonical sidecar present with partial data

Current judgment:
- this is the clearest truth-visibility drift in the current viewer stack
- it is a narrow UI/doc hardening candidate, not a schema or storage problem

## 3. Current Surface Map

### Strong truth-visible surfaces

- workbench artifact review
- meeting pack detail
- chart pack detail
- method comparison detail

These surfaces expose warnings, provenance, raw or near-raw payload views, or operational state directly in the product UI.

### Partial truth-visible surface

- paper-note detail

It exposes:
- note/frontmatter mirror state
- operational summary
- canonical run history when `structured_state` is present
- canonical claim cards when `structured_state` is present

It does not yet expose:
- `context_trace`
- an explicit distinction between missing canonical sidecar state and simply empty structured review sections

## 4. Recommended Guardrail Going Forward

When a viewer surface chooses not to render a debug/trace object directly:

1. it may keep the trace behind an optional disclosure or omit the full trace from the default UI
2. it should still make missing canonical state visible in plain operator language
3. it should not require narration to explain which saved source or sidecar the view is based on
4. generic empty cards should not be the only signal for missing canonical truth when the runtime already knows the difference

## 5. Current Best Next Step

Smallest safe follow-up:

- doc-only today:
  - keep `WEB_VIEWER.md` explicit about the difference between optional trace disclosure and required truth visibility
- future small UI PR if needed:
  - add an explicit missing-sidecar notice to paper-note detail when `structured_state` is null
  - optionally add a compact `context_trace` disclosure in inspect/debug mode instead of a full always-visible trace panel
