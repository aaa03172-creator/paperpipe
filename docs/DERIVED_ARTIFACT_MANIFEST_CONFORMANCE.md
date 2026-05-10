# Derived Artifact Manifest Conformance

Status: Draft bounded verification note
Date: 2026-04-20
Owner: Runtime/artifact maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/DERIVED_ARTIFACT_MANIFEST_SCHEMA.md`
- `docs/Evidence_and_Uncertainty_Rules.md`

Related docs:
- `docs/PAPER_SYNTHESIS.md`
- `docs/ARTIFACT_BUNDLE_SPEC.md`
- `docs/REVIEW_GATE_SCHEMA.md`

## Purpose

Define what it currently means for a derived artifact manifest to be conformant in the PaperPipe runtime.

This note exists to keep manifest hardening grounded in:
- actual saved owner files
- actual schema validation
- actual route and renderer behavior
- actual targeted tests and audit scripts

without:
- introducing a second approval system
- pretending every lane already has the same manifest maturity
- treating a schema doc as sufficient proof that runtime behavior follows it

## Current Judgment

At the current repo stage, manifest conformance is strongest for:
- `paper_synthesis`

Other lanes have partial conformance through lane-owned fields and tests, but they do not yet expose the same manifest contract depth.

Current rule:
- do not claim cross-lane manifest standardization just because one lane is strong
- use `paper_synthesis` as the current conformance anchor, not as proof that every derived lane should immediately migrate

## Current Scope

This note applies to conformance checks for:
- saved derived manifest owner files
- their paired export/render behavior when present
- manifest-specific read routes when present

This note does not apply to:
- raw-source bundles
- review-gate sidecars by themselves
- raw operator logs
- canonical structured state

## 1. Conformance Axes

### 1.1 Owner-file conformance

A derived lane is conformant only when the saved owner file is the primary structured truth for that lane.

Current expectations:
- the owner file is persisted deterministically
- the owner file reloads through the lane schema
- sibling exports remain subordinate to the owner file

Current strongest example:
- `paper_synthesis.json` + `paper_synthesis.md`

### 1.2 Schema conformance

A derived manifest is conformant only when the schema enforces the lane's claimed trust contract.

Current `paper_synthesis` examples:
- required upstream source kinds are enforced in `source_refs`
- `lineage_summary` is rebuilt from `source_refs`
- `readiness`, `evidence_refs`, `warnings`, and `uncertainty_notes` cannot drift into contradictory combinations

Current rule:
- a manifest field is not part of the real contract unless the schema or runtime actually enforces it

### 1.3 Render/export conformance

If a manifest has a human-readable sibling export, that export should keep the manifest's trust boundary visible.

Current `paper_synthesis` expectations:
- frontmatter exposes `artifact_family`, `template_kind`, `layer`, `canonical_status`, and `source_refs`
- the markdown body contains a visible layer contract and promotion guardrail

Current rule:
- user-facing prose must not erase layer, canonical-status, or provenance signals that the saved manifest carries

### 1.4 Route conformance

If a lane exposes a manifest-specific route, that route should be the preferred provenance surface.

Current `paper_synthesis` expectations:
- manifest route exists
- markdown route exists
- compatibility bundle route remains bounded and explicitly discouraged from spreading

Current rule:
- prefer manifest routes for structured provenance inspection
- treat compatibility bundle routes as bounded legacy surfaces, not the future contract

### 1.5 Summary-field conformance

Compact helper fields such as counts or summaries are conformant only when they stay additive.

Current examples:
- `source_ref_count`
- `lineage_summary`
- protocol version `source_ref_count`

Current rule:
- helper summaries must remain downstream of the direct provenance surface
- helper summaries must not become the only thing a client needs to inspect

## 2. Current Strong Conformance Anchor: `paper_synthesis`

### 2.1 Schema-level proof

Current source:
- `src/schemas/paper_synthesis.py`

Current conformance facts:
- `artifact_family`, `template_kind`, `layer`, and `canonical_status` are first-class schema fields
- `source_refs[]` must include `structured_state`, `claimset_resolved`, and `run_meta`
- `lineage_summary` is rebuilt from `source_refs[]`
- `readiness=evidence_backed` cannot coexist with warnings or uncertainty notes

### 2.2 Save/load proof

Current source:
- `src/paper_syntheses/store.py`

Current conformance facts:
- JSON and markdown are saved as sibling files
- save is atomic enough to restore previous content on second-write failure
- JSON reload goes back through `PaperSynthesis`

### 2.3 Build/runtime proof

Current source:
- `src/paper_syntheses/service.py`

Current conformance facts:
- only bounded upstream inputs are selected
- optional `quality_gate.json` and `acceptance_contract.json` stay additive
- warnings/readiness/freshness are computed from the selected inputs rather than invented in the renderer

### 2.4 Render proof

Current source:
- `src/paper_syntheses/renderer.py`

Current conformance facts:
- frontmatter repeats manifest-critical trust fields
- markdown includes a visible layer contract section
- markdown includes an explicit promotion guardrail

### 2.5 Route proof

Current sources:
- `tests/test_paper_syntheses_api.py`
- `tests/test_no_new_paper_synthesis_bundle_route_usage.py`
- `scripts/check_paper_synthesis_bundle_route_usage.py`
- `scripts/check_paper_synthesis_bundle_route_removal_readiness.py`
- `scripts/check_paper_synthesis_manifest_conformance.py`

Current conformance facts:
- `/paper-syntheses/{id}/manifest` is the preferred structured read surface
- `/paper-syntheses/{id}` remains only as a compatibility bundle route
- route spread is bounded by allowlist tests and audit scripts

## 3. Partial Conformance In Other Lanes

### 3.1 Meeting Pack

Current strength:
- owner-file semantics, layer/canonical-status fields, readiness, and lane-native provenance are real

Current gap versus `paper_synthesis`:
- provenance is intentionally lane-native (`source_items[]`, `retrieval_trace[]`, `evidence_refs[]`) rather than normalized into one manifest-source contract
- bounded audit source now exists at `scripts/check_meeting_pack_manifest_conformance.py`, but it verifies only the lane's current partial contract rather than upgrading `Meeting Pack` into the cross-lane anchor

### 3.2 Chart Pack

Current strength:
- owner file plus deterministic sibling bundle members are real
- review-gate sidecars are explicit

Current gap versus `paper_synthesis`:
- provenance is distributed across `source_items[]`, per-chart `source_ref`, snapshot refs, and spec refs rather than one manifest-level source-ref family

### 3.3 Method Comparison

Current strength:
- layer/canonical-status/readiness/freshness/warnings are real manifest fields

Current gap versus `paper_synthesis`:
- provenance is cell-level and source-summary-level, not a first-class manifest `source_refs[]` contract

### 3.4 Image Evidence

Current strength:
- raw-vs-derived separation and explicit `source_ref` are real

Current gap versus `paper_synthesis`:
- this lane is metadata-first, so compiled-manifest vocabulary is intentionally narrower

### 3.5 Protocol Knowledge

Current strength:
- version-first ownership and version `source_refs[]` are real

Current gap versus `paper_synthesis`:
- provenance lives mainly at version level, not at card-manifest level

## 4. Minimum Conformance Checklist For New Lanes

Before calling a new derived lane manifest-conformant, verify all applicable items below.

1. The lane has one saved owner file that round-trips through a Pydantic schema.
2. The owner file carries visible layer and canonical-status semantics when the lane is derived.
3. If the lane claims evidence-linked or source-linked support, the minimum trust-reopen path is explicit in saved fields.
4. Any helper counts or summaries stay additive to the direct provenance surface.
5. If a human-readable export exists, it preserves layer/provenance guardrails visibly.
6. If a manifest-specific route exists, it is the preferred structured inspection surface.
7. Any compatibility bundle route is bounded by tests or audit scripts rather than silently spreading.

If fewer than these conditions hold, call the lane partial rather than conformant.

## 5. Current Verification Sources

Current repo evidence for manifest conformance includes:
- schema tests
- service tests
- API tests
- route-spread allowlist tests
- bounded audit scripts for compatibility-route posture

Current concrete examples:
- `tests/test_paper_synthesis_service.py`
- `tests/test_paper_syntheses_api.py`
- `tests/test_no_new_paper_synthesis_bundle_route_usage.py`
- `tests/test_meeting_pack_manifest_conformance_script.py`
- `tests/test_protocol_card_schema.py`
- `tests/test_paper_synthesis_manifest_conformance_script.py`
- `scripts/check_meeting_pack_manifest_conformance.py`

Current rule:
- prefer targeted pytest and small audit scripts over broad, indirect suites when validating manifest behavior

## 6. What Does Not Count As Conformance

The following are not sufficient by themselves:
- a schema doc with no matching tests
- a viewer that renders fields the saved manifest does not own
- a count field such as `source_ref_count` without direct provenance available
- a review-gate sidecar that substitutes for the manifest owner
- a compatibility bundle route that becomes the de facto primary client surface

## 7. Future Direction

The safe next step is:
- add lane-specific targeted tests when a new manifest field becomes part of the trust contract
- add manifest-specific routes before broadening bundle-style compatibility reads
- keep conformance claims narrow and evidence-based

The unsafe next step is:
- declaring all downstream lanes manifest-conformant from docs alone
- flattening lane-native provenance into weaker generic fields just to satisfy a checklist
- treating compatibility routes or viewer summaries as proof of manifest maturity
