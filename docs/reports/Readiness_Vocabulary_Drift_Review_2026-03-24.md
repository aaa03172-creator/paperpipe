# Readiness Vocabulary Drift Review

Status: Active review note  
Date: 2026-03-24  
Owner: Runtime/design maintainers  
Scope: active bounded-lane trust/readiness vocabulary across docs, schemas, and nearby viewer surfaces

## Purpose

Check whether current active docs and runtime anchors agree on how bounded lanes talk about:

- `readiness`
- `warnings`
- freshness
- trace availability
- regenerateability
- adjacent operational trust signals

This note is not a new spec.

## Executive Call

Current repo is mostly aligned, but not because every lane shares one uniform summary shape.

Actual current pattern:
- `Meeting Pack` is the only active bounded lane with a full readiness/recoverability vocabulary
- paper-note/workbench surfaces use adjacent operational vocabulary (`ops_summary`, `context_trace`)
- `Chart Pack`, `Method Comparison`, and `Image Evidence` are warning-centric partial adopters
- `Protocol Knowledge` is validation-status-centric rather than readiness-centric

Main drift risk:
- `docs/Evidence_and_Uncertainty_Rules.md` can be read too strongly, as if every bounded lane should already expose all of `readiness`, `warnings[]`, `freshness_state`, `trace_available`, and `can_regenerate`

Current implementation does not support that reading, and it does not need to.

## 1. What Is Implemented Today

### A. `Meeting Pack` implements the richest current trust/recoverability contract

Repo anchors:
- `docs/MEETING_PACK.md`
- `src/schemas/meeting_pack.py`
- `src/meeting_packs/service.py`

Implemented:
- `readiness`
- `markdown_sync`
- `can_regenerate`
- `regenerate_strategy`
- `warnings`
- `retrieval_trace`
- trace summary/counts in list/detail responses

Why this is implemented:
- `Meeting PackValidation` and related response/list schemas explicitly expose readiness and regenerateability fields
- service code computes markdown drift, validates regenerate availability, and returns warnings during validation

### B. Paper-note/workbench surfaces expose adjacent operational trust signals

Repo anchors:
- `docs/WEB_VIEWER.md`
- `src/schemas/paper_notes.py`
- `backend/routers/paper_notes.py`

Implemented:
- `ops_summary.state`
- `ops_summary.reason`
- `ops_summary.recommended_action`
- optional `context_trace`

Why this is implemented:
- note list/detail responses expose operational state and deterministic context assembly traces
- this is viewer/workbench operational trust vocabulary, not a bounded-artifact readiness schema

### C. `Chart Pack` is warning-centric, not readiness-centric

Repo anchors:
- `docs/CHART_PACK.md`
- `src/schemas/chart_pack.py`
- `src/chart_packs/service.py`

Implemented:
- typed `warnings[]`
- `warning_count`
- `caution_notes`

Missing on purpose in the current active contract:
- `readiness`
- `freshness_state`
- `trace_available`
- `can_regenerate`

Why this is implemented/omitted:
- the chart lane currently emphasizes visible warning state and deterministic source-bound rendering
- list/response schemas summarize warning density, but no separate regenerate or freshness contract exists yet

### D. `Method Comparison` is minimal warning-only plus cell-status semantics

Repo anchors:
- `docs/METHOD_COMPARISON.md`
- `src/schemas/method_comparison.py`
- `src/method_comparisons/service.py`

Implemented:
- `warnings[]`
- `warning_count`
- cell status family: `explicit | inferred | missing | conflict`

Missing on purpose in the current active contract:
- `readiness`
- freshness vocabulary
- trace vocabulary
- regenerateability vocabulary

Why this is implemented/omitted:
- current trust signaling is carried by cell-level evidence status and bundle-level warning text
- the lane is intentionally simpler than `Meeting Pack`

### E. `Image Evidence` is warning-centric with bundle-presence summary fields

Repo anchors:
- `docs/IMAGE_EVIDENCE.md`
- `src/schemas/image_evidence.py`
- `src/image_evidence/service.py`

Implemented:
- typed `warnings[]`
- `warning_count`
- `has_view_state`
- `has_handoff`

Missing on purpose in the current active contract:
- `readiness`
- freshness vocabulary
- regenerateability vocabulary
- explicit trace vocabulary

Why this is implemented/omitted:
- image-evidence trust signals currently center on source registration health, checksum/path issues, and presence of bundle-local review aids
- the lane is metadata-review-first, not regenerate/revalidate-first

### F. `Protocol Knowledge` uses validation/version states instead of generic readiness

Repo anchors:
- `docs/PROTOCOL_KNOWLEDGE.md`
- `src/schemas/protocol_card.py`

Implemented:
- `validation_status`
- version `status`
- `cautions[]`
- `source_ref_count`

Missing on purpose in the current active contract:
- generic `readiness`
- `warnings[]`
- freshness vocabulary
- trace vocabulary
- regenerateability vocabulary

Why this is implemented/omitted:
- protocol cards are versioned reference artifacts, so the trust surface is “review/validation/version status”
- the lane does not currently expose a separate validation summary object

## 2. Drift Found

### A. Shared vocabulary guidance could be read as mandatory uniformity

Repo evidence:
- `docs/Evidence_and_Uncertainty_Rules.md:130`

Issue:
- the current wording says “Recommended shared vocabulary,” but without an explicit adoption note it can sound like every active lane should already expose every field.

Impact:
- this could trigger unnecessary schema churn or misleading docs patches that force dummy fields into bounded lanes with simpler trust surfaces.

Recommended fix:
- state explicitly that current adoption is partial and lane-specific
- note that adjacent vocabularies like `ops_summary.state` or `validation_status` are not drift bugs by themselves

### B. Warning shape is intentionally heterogeneous today

Repo evidence:
- `src/schemas/meeting_pack.py`
- `src/schemas/method_comparison.py`
- `src/schemas/chart_pack.py`
- `src/schemas/image_evidence.py`

Issue:
- some lanes use `list[str]`
- some use typed warning objects with `code`, `severity`, `message`

Current judgment:
- acceptable for now
- not worth forcing a repo-wide warning object migration unless cross-lane UI or API consumers clearly need it

## 3. Current Vocabulary Map

### Full trust/recoverability contract

- `Meeting Pack`
  - `readiness`
  - `markdown_sync`
  - `can_regenerate`
  - `regenerate_strategy`
  - `warnings`
  - `retrieval_trace`

### Operational adjacent vocabulary

- paper notes / workbench
  - `ops_summary.state`
  - `ops_summary.reason`
  - `recommended_action`
  - `context_trace`

### Warning-centric partial adoption

- `Chart Pack`
  - `warnings[]`
  - `warning_count`
  - `caution_notes`
- `Method Comparison`
  - `warnings[]`
  - `warning_count`
  - cell-level status
- `Image Evidence`
  - `warnings[]`
  - `warning_count`
  - `has_view_state`
  - `has_handoff`

### Validation-status-centric partial adoption

- `Protocol Knowledge`
  - `validation_status`
  - version `status`
  - `cautions[]`
  - `source_ref_count`

## 4. Recommended Guardrail Going Forward

When adding or reviewing a bounded lane:

1. do not force all lanes into one summary schema unless a real shared consumer requires it
2. prefer partial adoption of the shared vocabulary where it naturally fits
3. keep lane-specific trust signals explicit instead of hiding them behind generic names
4. if a lane adds freshness or regenerateability later, reuse `freshness_state` and `can_regenerate` rather than inventing new synonyms
