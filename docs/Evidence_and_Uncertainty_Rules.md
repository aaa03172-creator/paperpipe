# Evidence and Uncertainty Rules

Status: Active bounded rule
Date: 2026-04-08
Owner: Runtime/design maintainers
Canonical: `docs/Evidence_and_Uncertainty_Rules.md`
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Applies to: `ClaimSet`, `StatsReport`, `claimset.resolved.json`, Obsidian export, paper-note state, `Meeting Pack`, stub-only `/api/chat` compatibility surface

Related docs:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/Stats_Verification_Agent_Spec.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/document_artifact_v2.md`
- `docs/bootstrap_meta_schema.md`
- `docs/ClaimSet_Rendering_Guide.md`
- `docs/MEETING_PACK.md`
- `docs/WEB_VIEWER.md`
- `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
- `docs/operations_checklist_watcher_review_queue.md`
- `docs/Citation_Grounding_Audit_2026-03-13.md`
- `docs/PR_C1_Citation_Grounding_Resolver_Spec_2026-03-13.md`

## 1. Purpose

This document makes one bounded rule explicit:

- scientific truth in PaperPipe must stay evidence-linked
- uncertainty must stay visible
- presentation modes must not silently loosen evidence policy

The current repository already implements these rules across schemas, policy code, grounding, exporter behavior, and downstream artifact surfaces. This doc makes that contract explicit in one place.

## 2. Current Judgment

- A promoted scientific claim should not appear as well-supported without evidence.
- Missing support, missing location, ambiguity, and conflict should be surfaced rather than hidden.
- `claimset.resolved.json` is an additive grounding improvement, not a license to overstate certainty.
- `output_mode_family` and similar presentation controls do not change truth policy.

## 3. Canonical Rules

### 3.1 Evidence is required for promoted claims

- `ClaimSet` claims are evidence-first by default.
- If a claim has no evidence spans, it must be downgraded to `unknown=true`.
- Current runtime policy caps confidence when evidence is missing instead of pretending the claim is well-supported.
- Derived outputs should not promote unsupported claims into evidence-backed summaries, cards, or packs.

### 3.2 Location metadata matters

- Evidence text alone is not enough for a normal supported-state claim.
- If evidence exists but no usable location metadata survives, the claim must be marked `unknown=true` with a missing-location reason.
- Current accepted location signals are additive and pragmatic:
  - `page`
  - `source_span`
  - `char_start` + `char_end`
  - `bbox_pdf`
  - `bbox_pct`
  - `table_id` + `cell_id`
- No surface should fabricate a locator that the runtime does not actually have.

### 3.3 Grounding is additive and explicit

- The read pipeline may write both `claimset.json` and `claimset.resolved.json`.
- When resolver output exists, downstream surfaces should preserve `grounded` and `resolution` instead of dropping them.
- Failed or ambiguous grounding must remain visible as failed or ambiguous.
- `claimset_readiness` and related operational badges are useful, but they are not the same thing as full citation verification.

### 3.3A Compiled knowledge assets stay derivative

- A compiled knowledge page or asset may summarize or connect current scientific state, but it does not become canonical truth by itself.
- If a compiled asset presents biomedical content as evidence-backed, it must still point back to upstream claim/evidence/source lineage rather than relying on compiled prose alone.
- If a compiled asset cannot preserve upstream support clearly enough, it should remain explicitly background-only, draft-like, stale, or uncertain instead of sounding fully grounded.
- Compiled knowledge convenience must not erase freshness, conflict, or unresolved-grounding signals that exist upstream.

### 3.3B Answer generation stays evidence-routed

- A future answer surface, chat response, brief, or generated explanation should prefer current canonical structured state plus reusable evidence refs before consulting derived summaries.
- Compiled knowledge assets, method comparisons, meeting packs, review gates, and raw-memory helpers may assist retrieval or phrasing, but they do not replace upstream evidence-linked support.
- If an answer surface cannot jump back to canonical state and evidence lineage clearly enough, it should answer in explicitly uncertain or background-only terms rather than presenting itself as fully evidence-backed.

### 3.4 Approximate support must stay labeled

- Evidence quality currently uses `highlight_source` to distinguish `bbox`, `text_match`, and `approx`.
- `bbox` and resolved text matches should not be rendered as equivalent to approximate fallback evidence.
- If a downstream lane introduces operator-added or manually repaired evidence, that material must remain distinguishable from raw model-extracted evidence.

### 3.5 Uncertainty and conflict must be surfaced

- Claim-level uncertainty should remain explicit through `unknown` and `unknown_reason`.
- Span-level uncertainty should remain explicit through `grounded`, `resolution`, and locator quality.
- Downstream artifact layers should carry visible caution states instead of inventing consensus:
  - review queue escalation such as `NEEDS_EVIDENCE_LINK`
  - `Meeting Pack` readiness such as `evidence_backed` vs `background_only`
  - explicit `conflicts[]`, `consensus_points[]`, and uncertainty notes where the bounded feature supports them
- Rendering may simplify wording, but it must not erase the fact that support is weak, partial, unresolved, or conflicting.

### 3.6 Presentation modes do not override truth policy

- `output_mode_family` is presentation-only.
- Meeting Pack `mode` changes framing, sequence, and audience emphasis, not source acceptance criteria.
- Future chat/viewer output modes may change layout or explanation density, but they must not create a second evidence threshold.
- Persona/profile/output-mode separation from `docs/PERSONA_MODE_BOUNDARY.md` applies here directly.

## 4. Current Status Vocabulary

### 4.1 Claim-level

- `unknown: true|false`
- `unknown_reason`
  - `EVIDENCE_MISSING`
  - `EVIDENCE_LOCATION_MISSING`
  - `UNSPECIFIED`

### 4.2 Evidence-span level

- `highlight_source`
  - `bbox`
  - `text_match`
  - `approx`
- `grounded`
  - `true`
  - `false`
  - `null` when grounding has not been applied or preserved
- `resolution`
  - current resolver examples include `OK`, `NORMALIZED_MATCH`, `AMBIGUOUS_MATCH`, `FAILED_MATCH`

### 4.3 Downstream operational and draft states

- review queue escalation: `NEEDS_EVIDENCE_LINK`
- meeting-pack readiness:
  - `evidence_backed`
  - `background_only`
- bootstrap metadata may summarize:
  - `claimset_grounded_span_count`
  - `claimset_unresolved_span_count`
  - `claimset_readiness`

These operational summaries are useful, but they must not be mistaken for scientific truth by themselves.

### 4.4 Validation and freshness summary vocabulary

When a bounded lane needs a compact validation or trust summary, prefer a small additive shape rather than inventing a new truth policy.

Recommended shared vocabulary:
- `readiness`
  - example: `evidence_backed`, `background_only`
- `warnings[]`
  - explicit caution messages or machine-generated validation notes
- `canonical_status`
  - example: `non_canonical`
- `freshness_state`
  - `current`
  - `stale`
  - `unknown`
- `trace_available`
  - `true|false`
- `can_regenerate`
  - `true|false|unknown`

Rules:
- these fields summarize trust or recoverability; they do not replace claim/evidence truth
- `freshness_state=stale` or `unknown` must not be hidden by polished rendering
- `canonical_status=non_canonical` should stay visible when a derived or memory lane could otherwise be mistaken for promoted truth
- `trace_available=false` does not weaken evidence rules; it only says observability is limited
- bounded lanes may extend this shape, but they should reuse the vocabulary when possible
- current adoption is intentionally partial:
  - `Meeting Pack` currently uses the richest subset (`readiness`, `warnings[]`, regenerateability, trace-adjacent observability)
  - paper-note/workbench surfaces use adjacent operational vocabulary such as `ops_summary.state` and `context_trace`
  - some bounded lanes are warning-centric or validation-status-centric and do not need every field yet
- do not add dummy `freshness_state`, `trace_available`, or `can_regenerate` fields just to make a lane look uniform unless a real shared consumer requires them

## 5. Current Integration Points

- `src/schemas/agent_artifacts.py`
  - canonical claim/evidence payload shape
- `src/quality/claimset_policy.py`
  - evidence-required unknown-marking and confidence capping
- `src/services/citation_grounding.py`
  - additive quote-to-chunk grounding and `resolution` output
- `src/exporter.py`
  - review-queue escalation and evidence-linked export behavior
- `docs/Stats_Verification_Agent_Spec.md`
  - reference feature contract for stats-check evidence payloads
- `docs/bootstrap_meta_schema.md`
  - operational summary fields such as claimset readiness and grounded/unresolved counts
- `backend/routers/obsidian.py`
  - prefers `claimset.resolved.json` and exposes primary evidence grounding fields
- `src/schemas/chat.py`
  - reuses additive locator/evidence-ref shape for the current stub-only `/api/chat` compatibility surface
- `src/schemas/meeting_pack.py`
  - reuses locator/evidence refs and keeps caution/readiness states explicit
- `docs/WEB_VIEWER.md` and `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
  - viewer and detail surfaces must preserve the same evidence-truth boundary
- `docs/operations_checklist_watcher_review_queue.md`
  - operational review-queue workflow keeps open follow-up states explicit instead of silently discarding them

## 6. Non-Goals

- This doc does not introduce a new `/projects` or `/documents` contract.
- This doc does not require every evidence span to have bbox coordinates.
- This doc does not create a second locator family for chat, packs, or viewer surfaces.
- This doc does not claim that every current citation jump is human-verified.
- This doc does not allow output/view modes to loosen evidence requirements.

## 7. Practical Rule of Thumb

When a new feature wants to summarize, compare, chat over, or present scientific content:

1. Reuse current claim/evidence identity and locator shapes where possible.
2. Keep unsupported or weakly supported material visibly uncertain.
3. Treat presentation changes as presentation changes only.
4. If the feature needs a different truth policy, make that an explicit bounded spec decision instead of silently changing the rule.
