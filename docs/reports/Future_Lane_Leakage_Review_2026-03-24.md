# Future-Lane Leakage Review

Status: Active review note  
Date: 2026-03-24  
Owner: Runtime/design maintainers  
Scope: active docs and nearby user-facing copy vs the current rule that `Project`, broad memory/chat, and generalized workspace/platform lanes remain future-only unless explicitly adopted

## Purpose

Check whether active docs or current UI copy silently reopen future lanes such as:

- first-class `Project`
- broad memory/chat runtime
- generalized workspace/platform framing
- multi-user or collaboration product shape

This note is not a new spec.

## Executive Call

Current repo is strongly aligned against future-lane leakage.

Strong current center:
- active positioning, master spec, persona boundary, and chat contract all explicitly keep `Project`, memory/chat, and generalized platform framing out of the active runtime
- bounded artifact specs consistently describe themselves as narrow derived lanes rather than new product roots
- the only active user-facing `project` language in the frontend is `project_update`, which is explicitly an output-mode family, not a project-first runtime owner

Main drift:
- mostly legacy wording, not implementation pressure
- the largest examples were:
  - `Project Overview` as a master-spec section label
  - repeated `Implemented in workspace:` wording in bounded specs

These phrases were broader than the current `paper-centered`, `paper/job/artifact-first` boundary and were worth narrowing.

## 1. What Is Aligned

### A. Product positioning explicitly rejects platform-shaped overreach

Repo anchors:
- `docs/Product_Positioning_Principles.md`

Why this is aligned:
- the active positioning note explicitly says the product should not currently be described as a generic `projects/documents` platform, a broad workspace memory platform, or a multi-user collaboration suite

### B. Master spec already keeps `Project` and memory/chat outside the active runtime

Repo anchors:
- `docs/Lattice_v3_Master_Spec.md`

Why this is aligned:
- the current scope note says first-class `Project`, broad memory/chat, and generalized workspace/platform lanes are out of active runtime scope until separately adopted
- the ownership section still centers `papers`, `jobs`, and `artifacts`

### C. Chat remains a future hook, not an active product lane

Repo anchors:
- `docs/API_CHAT_CONTRACT.md`
- `docs/PERSONA_MODE_BOUNDARY.md`

Why this is aligned:
- `/api/chat` is still documented as stub-only
- output-mode support is explicitly presentation-only and must not become a separate chat runtime or truth policy

### D. Pending future lanes are held behind explicit gates

Repo anchors:
- `docs/Pending_PR_Queue.md`

Why this is aligned:
- `Project Memory` is recorded as a backend-only hold with a separate gate note
- the queue explicitly says it should not be treated as a viewer/API pilot

### E. Frontend `project_update` copy is presentation-only, not product-shape leakage

Repo anchors:
- `frontend/src/app/pages/MeetingPackPage.tsx`
- `docs/PERSONA_MODE_BOUNDARY.md`

Why this is aligned:
- `Project Update` appears only as an output-mode-family label
- the persona/mode boundary doc already says output-mode families must remain presentation-oriented

## 2. Drift Found

### A. Master spec still used a `Project Overview` heading

Repo evidence:
- `docs/Lattice_v3_Master_Spec.md`

Issue:
- the section content was already runtime-safe, but the label could still reinforce project-first reading habits

Action taken:
- renamed the section heading to `System Overview`

### B. Several active bounded specs said `Implemented in workspace`

Repo evidence:
- `docs/CHART_PACK.md`
- `docs/METHOD_COMPARISON.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/MEETING_PACK.md`

Issue:
- that phrase is not wrong in plain English, but in this repo it can read too close to a broad workspace/product-root claim
- the current product shape is narrower: bounded lanes implemented inside the current paper/job/artifact runtime slice

Action taken:
- changed those headings to `Implemented in current runtime slice`

## 3. Remaining Low-Risk Tension

### A. Some active dated audits still use memory-ready comparison language

Repo anchors:
- `docs/Event_Logging_Audit_2026-03-13.md`
- `docs/Current_Code_Baseline_Audit_2026-03-13.md`

Current judgment:
- acceptable for now because they are dated audits, not product SSOT
- they compare current reality against older plans and future hooks, but they do not currently override the active runtime boundary

### B. Active docs still mention future hooks where needed

Repo anchors:
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/PERSONA_MODE_BOUNDARY.md`

Current judgment:
- acceptable and intentional
- the key is that future hooks stay explicitly bounded and do not silently claim active runtime behavior

## 4. Recommended Guardrail Going Forward

When active docs mention future lanes:

1. say they are hooks, holds, or future RFCs
2. avoid headings that imply first-class runtime ownership unless code and routes prove it
3. prefer `current runtime slice` or `bounded lane` over generic `workspace` phrasing when describing implemented features
4. keep `project_update` and similar labels tied to presentation/output-mode semantics, not product-shape semantics
