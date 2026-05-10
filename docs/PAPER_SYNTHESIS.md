# Paper Synthesis

Status: Active bounded spec
Date: 2026-04-08
Owner: Paper notes/runtime maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related docs:
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/INDEPENDENT_REVIEW_TEMPLATE.md`
- `docs/reports/Agent_Layer_Current_State_And_Implementation_Plan_2026-04-08.md`

## Purpose

`Paper Synthesis` is the first bounded compiled-knowledge pilot for the current PaperPipe runtime.

It exists to let operators materialize a reviewable paper-scoped synthesis bundle without introducing:
- a generalized wiki or memory platform
- a new canonical truth store beside current paper/run/artifact state
- a project/workspace runtime owner
- freeform memory-first biomedical answer generation

The lane is intentionally:
- paper-scoped
- file-backed
- derived
- evidence-linked
- review-first

## Current Implementation Status

Implemented in the current runtime slice:
- `src/schemas/paper_synthesis.py`
- `src/paper_syntheses/store.py`
- `src/paper_syntheses/service.py`
- `src/paper_syntheses/renderer.py`
- `src/services/runtime_paths.py::paper_syntheses_root()`
- `backend/routers/paper_syntheses.py`
- `src/cli.py` (`paper-synthesis-generate`, `paper-synthesis-show`, `paper-synthesis-list`)
- `frontend/src/app/pages/AnalysisWorkbench.tsx` + `frontend/src/app/components/ArtifactPanel.tsx` read-only card for the latest saved paper synthesis, including a visible trust-reopen path for minimum upstream lineage and an on-demand source-ref inspector
- targeted pytest coverage for store, runtime path, service, and API
- targeted CLI coverage

Currently deferred:
- dedicated viewer UI
- canonical-state promotion from paper synthesis
- generalized multi-paper synthesis
- project-level synthesis ownership
- freeform note mining
- autonomous synthesis refresh or promotion

## Current Judgment

At the current repo stage, `Paper Synthesis` is safe only as a compiled-knowledge artifact lane.

Current rule:
- it may summarize or connect current paper-scoped state
- it must not become canonical scientific truth
- promoted biomedical answers must still jump back to upstream claim/evidence/source lineage

## Current Boundary

### 1. Identity stays paper-first

Current rule:
- requests are `paper_slug`-first
- canonical owner remains note-side structured state at `.pp/<slug>/state.json`
- artifact discovery may resolve run directories through note frontmatter `id` / `doi`, but that does not change ownership

### 2. Source set stays bounded and explicit

Required inputs:
1. canonical structured state
2. selected `claimset.resolved.json`
3. selected `run_meta.json`

Optional additive review metadata from the same selected run:
- `quality_gate.json`
- `acceptance_contract.json`

Current rule:
- optional review artifacts may influence warnings or review posture
- optional review artifacts do not replace evidence truth or canonical state
- no freeform note-body mining or broad memory retrieval is allowed in this lane

### 3. Output stays derived and reviewable

Current bundle shape:

```text
storage/paper_syntheses/<synthesis_id>/
  paper_synthesis.json
  paper_synthesis.md
```

Current rule:
- `paper_synthesis.json` is the bundle-local manifest
- `paper_synthesis.md` is a deterministic review-facing sibling export
- `paper_synthesis.md` carries visible layer/provenance frontmatter plus a human-readable layer contract section
- the bundle is a compiled view, not a new source of truth

### 4. Provenance and uncertainty stay explicit

Current rule:
- source refs must stay visible
- evidence refs reuse the existing `ChatEvidenceRef` / locator family
- warnings and uncertainty notes must remain explicit
- freshness must remain visible as `current`, `stale`, or `unknown`
- list/detail payloads may include a thin derived `lineage_summary`, but that summary must remain downstream of `source_refs`, not a replacement for them

### 5. Access surfaces stay thin

Current FastAPI surface:
- `POST /paper-syntheses/generate`
- `GET /paper-syntheses`
- `GET /paper-syntheses/{synthesis_id}` (compatibility bundle fetch)
- `GET /paper-syntheses/{synthesis_id}/manifest`
- `GET /paper-syntheses/{synthesis_id}/markdown`

Current CLI surface:
- `paperpipe paper-synthesis-generate <paper_slug>`
- `paperpipe paper-synthesis-show <synthesis_id>`
- `paperpipe paper-synthesis-list`

Current rule:
- FastAPI and CLI are both thin wrappers over schema/service/store code
- CLI keeps the bundle JSON as the default compatibility payload, but `paper-synthesis-generate --manifest` and `paper-synthesis-show --manifest` now expose structured manifest-only inspection without the markdown payload
- current UI exposure is a read-only workbench card that links to raw markdown, shows the minimum trust-reopen path (`structured_state`, selected resolved claimset, selected run metadata), and can lazily reopen saved `source_refs`; it is not a separate viewer lane
- structured provenance inspection should prefer the manifest route, while user-facing derived prose/export should prefer the markdown route
- the bundle route remains only as a compatibility alias for callers that still expect manifest + markdown together, and it returns explicit preferred-route headers for `manifest` and `markdown`
- successful compatibility bundle reads now emit a structured request-audit row (`source=compatibility_route`, `outcome=deprecated_bundle_read`) so future removal decisions can be grounded in actual route hits
- `python3 scripts/summarize_paper_synthesis_bundle_route_hits.py` provides a small operator-facing summary of those additive request-audit rows without turning them into a new truth store, and it keeps known local/test hosts (`testserver`, loopback, `localhost`) separate from stronger non-local host signals
- the same summary now marks known placeholder hits such as `papersynth_missing` on local/test hosts as likely test noise so historical false positives are less likely to be over-read as real compatibility traffic
- `python3 scripts/check_paper_synthesis_bundle_route_removal_readiness.py --db <path-to-state.db>` now includes that runtime hit summary inline, so first-party readiness and current DB observations can be inspected together without changing the deletion gate itself
- these surfaces are for deterministic bundle creation and retrieval, not conversational generation

## Current Non-Goals

The current spec does not include:
- a paper-synthesis viewer beyond the existing read-only workbench card
- operator editing UI
- multi-paper knowledge graph behavior
- memory-first retrieval over arbitrary notes
- automatic promotion into canonical note state
- project/workspace-scoped synthesis ownership

## Verification Expectations

Current verification lanes should remain:
- targeted pytest coverage for store, path, service, and API
- docs consistency with `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
- `python3 scripts/check_paper_synthesis_bundle_route_removal_readiness.py` may certify first-party retirement readiness for the compatibility bundle route, but it does not certify API route deletion because external callers remain not confirmed
- `python3 scripts/summarize_paper_synthesis_bundle_route_hits.py` can be used after deployment/runtime use to inspect whether compatibility-route traffic is still actually occurring in the current DB, while keeping local/test host hits from being over-interpreted as external-caller proof
- when a concrete runtime DB is available, prefer `python3 scripts/check_paper_synthesis_bundle_route_removal_readiness.py --db <path-to-state.db>` so the readiness output also carries the additive runtime hit interpretation (`unavailable`, `no_hits_observed`, `likely_historical_test_noise_only`, `local_or_internal_only`, or `possibly_external_seen`)

When this spec changes:
- keep the allowed source set explicit
- keep derived-vs-canonical language explicit
- do not widen the lane into generalized memory or workspace behavior without updating both tests and the bounded spec

## Conclusion

`Paper Synthesis` is now an active bounded spec because the lane is implemented as a paper-scoped, evidence-linked, compiled artifact bundle.

The next changes in this area should harden this compiled-knowledge lane.

They should not reopen the broader question of whether Lattice should become a generalized wiki, memory platform, or project-scoped knowledge runtime.
