# Paper Annotation MVP Checklist (2026-04-10)

Purpose: turn the paper annotation / marking audit into a smallest-safe implementation checklist that preserves PaperPipe's current paper-first, evidence-linked runtime boundaries.

## 1. Current product boundary

The MVP must stay inside the current product shape:
- paper-first
- artifact-first
- local-first
- single-operator-first
- evidence-linked
- reviewable by a human operator

The MVP must not silently expand the runtime into:
- a first-class project/workspace platform
- a generic note-taking product
- a decorative annotation layer
- a second canonical truth store

## 2. MVP target

The near-term MVP target is:
- one paper-scoped operator judgment state per paper note
- editable from paper note detail
- recoverable from papers list
- readable from workbench without turning workbench into another editor

This means the MVP should ship:
- `paper_note_text`
- `starred`
- `triage_labels[]` from a small closed vocabulary

This MVP should not ship:
- free-form passage annotation
- figure overlays
- sticker-like decoration
- project-level aggregation as a first-class runtime lane

## 3. Source-of-truth rule

Do not store v1 operator judgment in any of these existing fields or systems:
- note markdown body
- note frontmatter `status`
- note frontmatter `tags`
- SQLite `user_actions`
- canonical structured state

Reason:
- generated note markdown is already rewritten by runtime helpers
- `status` already carries processing/readiness semantics in list/detail filters
- `tags` already participate in retrieval and related-paper derivation
- `user_actions` is an audit log, not durable retrieval state
- canonical structured state must stay evidence-oriented

## 4. Proposed minimal contract

Recommended v1 contract shape:

```json
{
  "paper_id": "string",
  "note_slug": "string",
  "layer": "raw_memory",
  "canonical_status": "non_canonical",
  "paper_note_text": "string | null",
  "starred": true,
  "triage_labels": ["revisit", "needs_verification"],
  "created_at": "iso8601",
  "updated_at": "iso8601"
}
```

Recommended v1 vocabulary:
- `revisit`
- `needs_verification`
- `experiment_relevant`

Optional fourth label only if real use demands it:
- `presentation_candidate`

## 5. Storage rule

Preferred storage shape:
- per-paper sidecar under the existing paper note sidecar neighborhood

Suggested path:
- `.pp/operator_state/<paper-or-slug-key>-<hash>.json`

Why this is safer than note-body insertion:
- keeps generated markdown idempotent
- keeps operator state explicitly non-canonical
- makes future list aggregation straightforward
- leaves room for future migration to richer annotation contracts

## 6. API checklist

Before frontend work, define a thin FastAPI contract:
- `GET /paper-notes/{slug}/operator-state`
- `PUT /paper-notes/{slug}/operator-state`

The list/index path must also expose summary fields needed for retrieval:
- `starred`
- `has_operator_note`
- `triage_labels[]`

Do not add write semantics to generic event-log routes.

## 7. Frontend checklist

### `/papers/:slug`
- add one compact editable module for:
  - `My note`
  - `Starred`
  - `Triage labels`
- keep it visually separate from:
  - frontmatter `Properties`
  - structured saved state
  - claim/evidence review

### `/papers`
- show small retrieval-grade signals only:
  - star
  - note-present
  - triage labels
- add filters for:
  - starred
  - triage label

### `/workbench/:paperId`
- v1 should be read-only carryover only
- no editor
- no passage annotation controls

## 8. Information architecture rules

Keep these distinctions explicit:
- paper-level operator note:
  - “what I think about this paper right now”
- project memory:
  - “what this means for the broader project”
- evidence/claim review:
  - “what the current source-grounded verification state is”

Do not collapse these into one field, one badge family, or one editor.

## 9. Passage annotation defer checklist

Do not start passage-level annotation until all of the following are true:
- there is a first-class anchor contract
- the anchor target is defined against the correct surface
- the team decides whether the write surface is note detail, PDF workbench, or both
- the UI distinguishes personal notes from evidence-validation anchors
- retrieval requirements for anchored notes are specified

Future-ready fields to reserve conceptually:
- `annotation_id`
- `anchor_type`
- `anchor_target`
- `quote_text`
- `locator`

## 10. Explicit non-goals

The v1 MVP must not include:
- sticker packs
- emoji reactions
- free placement of markers in the reading body
- arbitrary color-coded visual systems
- collaborative comments or sharing semantics
- project-first inboxes, boards, or workspace rollups
- evidence-confidence inference from user-applied badges

## 11. Pre-implementation gate

Do not start implementation until these checks are answered in writing:
- what exact triage label vocabulary is allowed in v1?
- where is the operator-state sidecar stored?
- how does list aggregation read that sidecar?
- how are `status`, `tags`, and `triage_labels` visually differentiated?
- what appears on workbench in v1, and what is intentionally absent?
- what migration path exists if anchored annotation is added later?

## 12. Smallest safe PR split

Recommended PR order:

1. Backend contract PR
   - schema
   - store
   - `GET/PUT` API
   - list summary aggregation

2. Paper note detail + list retrieval PR
   - detail editor
   - row signals
   - filters

3. Workbench carryover PR
   - read-only summary only

4. Future RFC, not implementation
   - anchored annotation model

## 13. Done condition

This MVP is actually done only when:
- a user can save paper-level judgment from note detail
- that judgment is visible again in papers list
- papers list can filter by the new triage state
- the state remains explicitly non-canonical
- no generated note body or structured evidence contract was repurposed unsafely
