# Protocol Knowledge

Status: Active spec
Date: 2026-03-23
Owner: Paper notes/runtime maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related docs:
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/document_artifact_v2.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/UX_REVIEW_REPORT_protocol-knowledge-inspector.md`
- `docs/archive/Protocol_Knowledge_Layer_RFC_2026-03-18.md`

## Purpose

`Protocol Knowledge` is a bounded, evidence-linked protocol reference artifact family.

It exists to let operators preserve:
- protocol identity
- versioned content snapshots
- change reasons
- linked paper/note context
- source-linked evidence refs

without introducing:
- a lab automation runtime
- a new `projects/documents/protocols` platform
- a second canonical truth store beside current paper/run/artifact state
- an execution console for wet-lab procedure control

The current lane is intentionally:
- file-backed
- version-first
- evidence-linked
- read-first
- bounded around saved protocol-card bundles

## Current Implementation Status

Implemented in current runtime slice:
- `src/schemas/protocol_card.py`
- `src/protocol_cards/store.py`
- `src/protocol_cards/service.py`
- `src/protocol_cards/renderer.py`
- `src/services/runtime_paths.py::protocol_cards_root()`
- `backend/routers/protocol_cards.py`
- read-only frontend inspector:
  - `/protocol-cards`
  - `/protocol-cards/:protocolId`
- targeted pytest coverage for schema/store/service/API/auth
- frontend mock Playwright coverage
- frontend real-backend Playwright coverage
- backend visual regression coverage for index/detail

Currently deferred:
- append-only version-write endpoints
- version activation/editor controls
- source-loader expansion beyond explicit request payloads
- execution/runtime semantics
- protocol authoring workflow UI

## Current Judgment

At the current repo stage, `Protocol Knowledge` is mature enough to freeze as an active bounded spec.

That judgment is based on:
- implemented schema/store/API/viewer slices
- explicit protocol identity vs version separation
- reuse of current `ChatEvidenceRef` lineage instead of inventing a new provenance family
- read-first frontend and backend verification that preserve the bounded review role

## Current Boundary

### 1. Identity stays protocol-card-first and version-separated

Current runtime split:
- `ProtocolCard` = reusable protocol identity and current-state metadata
- `ProtocolVersion` = content snapshot at a specific version number

Current rule:
- do not collapse identity and version content into one undifferentiated blob
- `current_version_id` must always point at a saved version summary
- linked papers and linked notes remain context, not primary identity

### 2. Version content stays evidence-linked

Current rule:
- protocol versions may carry `source_refs[]`
- `source_refs[]` reuse the current `ChatEvidenceRef` / locator family
- do not introduce a second protocol-specific locator system
- missing evidence should remain visible through draft/review state rather than being silently upgraded

### 3. Validation state and version status stay literal

Current card validation states:
- `unreviewed`
- `draft`
- `reviewed`
- `verified_by_user`
- `deprecated`

Current version states:
- `draft`
- `active`
- `deprecated`

Current rule:
- the viewer and API must present these states literally
- `active` does not mean experimentally validated success
- `verified_by_user` does not turn the lane into an execution runtime

### 4. Storage stays file-backed

Current storage root:

```text
storage/protocol_cards/<protocol_id>/
  protocol_card.json
  protocol_card.md
  versions/
    <version_id>.json
```

Current rule:
- `protocol_card.json` remains the primary bundle-local identity and metadata file
- `versions/*.json` remain bundle-local version members rather than a separate truth surface
- the bundle is a derived protocol-reference artifact, not a new generalized knowledge platform
- whole-card upserts may rewrite the bundle deterministically
- version snapshots remain inspectable on disk

### 5. API stays thin and bounded

Current API surface:
- `POST /protocol-cards`
- `GET /protocol-cards`
- `GET /protocol-cards/{protocol_id}`
- `GET /protocol-cards/{protocol_id}/versions`
- `GET /protocol-cards/{protocol_id}/versions/{version_id}`

Current rule:
- the API remains a thin wrapper over schema/service/store code
- broad workflow controls such as activation consoles, edit sessions, or execution-state APIs are out of scope

### 6. Inspector stays read-only

Current viewer surface:
- `/protocol-cards`
- `/protocol-cards/:protocolId`

Current rule:
- the inspector is for version-first review, not authoring
- current version, historical versions, change reason, and source-ref density should stay visible together
- `Open note` is a provenance handoff, not an editing shortcut

### 7. Protocol knowledge must not become a hidden runtime executor

Current rule:
- protocol cards are saved protocol-reference artifacts
- they do not imply SOP approval, instrument control, or lab workflow automation
- the inspector must keep trust-boundary language explicit

## Current Non-Goals

The current spec does not include:
- wet-lab execution guarantees
- protocol authoring/editor UI
- lab automation hooks
- protocol scheduling or orchestration
- generalized `projects/documents/protocols` modeling
- replacing paper notes as the primary knowledge surface

## Relationship To Other Bounded Lanes

- `Method Comparison` remains a separate evidence-linked comparison artifact and should not be folded into protocol-card version storage.
- `Chart Pack` remains a downstream visualization artifact and should not become the truth surface for protocol state.
- `Image Evidence` remains a metadata-first sidecar and should not be treated as a protocol execution substrate.

## Verification Expectations

Current verification lanes should remain:
- targeted pytest coverage for schema/store/service/API/auth
- mock Playwright coverage for index/detail inspector behavior
- real-backend Playwright coverage for saved bundle review and note handoff
- backend visual coverage for `/protocol-cards` index/detail

When this spec changes:
- keep version ordering and current-version semantics explicit
- keep trust-boundary language intact
- avoid widening into editor/activation semantics without updating both tests and this bounded spec

## Conclusion

`Protocol Knowledge` is now an active bounded spec because the lane is implemented, versioned, evidence-linked, and bounded as a read-first protocol reference family.

The next changes in this area should harden or extend this bounded artifact family.

They should not reopen the broader question of whether Lattice should become a generalized protocol platform or lab execution runtime.
