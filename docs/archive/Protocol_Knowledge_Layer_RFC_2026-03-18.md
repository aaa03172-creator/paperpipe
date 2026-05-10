# Protocol Knowledge Layer RFC

Status: Historical proposal  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related:
- `docs/archive/Agent_Proposal_Fit_Review_2026-03-18.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/document_artifact_v2.md`
- `docs/PERSONA_MODE_BOUNDARY.md`

## Purpose

External proposal docs argued for a first-class protocol knowledge system with versioning, source linkage, and change reasons.

That idea is valid, but it must be adapted to the current Lattice architecture:
- paper-centric runtime
- artifact-first derived state
- local-first file storage
- Zotero as source-of-truth for papers
- Obsidian as knowledge surface

This RFC defines the smallest future protocol layer that fits those constraints.

## Current fit

Current repo reality:
- protocol- and method-like content already appears in papers and reader outputs
- paper notes and Obsidian are already used as long-lived knowledge surfaces
- there is no first-class `protocol_cards` runtime yet
- there is no approved top-level `projects/documents/protocols` platform model

So the correct move is not to import the external protocol schema wholesale.

The correct move is:
- add a bounded protocol knowledge layer only if it remains evidence-linked
- keep it derived from current paper/runtime assets
- keep it file-first unless a stronger DB need appears later

## Non-goals

- not a lab automation runtime
- not a protocols.io mirror
- not an execution guarantee for wet-lab success
- not a replacement for paper notes or source PDFs
- not a reason to introduce a full `projects/documents` platform baseline

## Boundary rules

### What this layer may do

- capture protocol-oriented knowledge extracted from papers or internal notes
- separate protocol identity from version snapshots
- preserve why a version changed
- preserve where a protocol claim came from

### What this layer must not do

- silently fill missing conditions
- collapse internal modifications and paper-derived steps into one undifferentiated blob
- overwrite source paper truth
- present draft protocol content as experimentally validated fact

## Proposed phase-0 model

### `ProtocolCard`

Identity-level record for a reusable protocol concept.

Suggested fields:
- `protocol_id`
- `title`
- `purpose`
- `context`
- `source_kind`
  - `paper_derived`
  - `internal_adaptation`
  - `mixed`
- `linked_paper_ids[]`
- `linked_note_slugs[]`
- `current_version_id`
- `validation_status`
  - `unreviewed`
  - `draft`
  - `reviewed`
  - `verified_by_user`
  - `deprecated`
- `created_at`
- `updated_at`

### `ProtocolVersion`

Snapshot-level record for actual protocol content at a point in time.

Suggested fields:
- `version_id`
- `protocol_id`
- `version_number`
- `key_steps_summary`
- `materials`
- `equipment`
- `critical_conditions`
- `readouts`
- `cautions`
- `content_snapshot`
- `change_reason`
- `status`
  - `draft`
  - `active`
  - `deprecated`
- `created_by`
- `created_at`
- `source_refs[]`

### `ProtocolEvidenceRef`

Use the current evidence-link style rather than inventing a second locator family.

Suggested shape:
- `paper_id`
- `run_id?`
- `claim_id?`
- `evidence_id?`
- `locator?`
  - follow current claim/evidence locator conventions when available
- `source_type`
  - `paper_claim`
  - `paper_table`
  - `paper_note`
  - `internal_note`

## Storage proposal

Prefer a separate derived root, similar to `meeting_packs`, instead of forcing this into the current runtime DB first.

Suggested layout:

```text
storage/protocol_cards/<protocol_id>/
  protocol_card.json
  versions/
    <version_id>.json
  protocol_card.md
```

Why this fits better than a DB-first import:
- current repo already uses file-backed bounded assets
- single-user local-first operation remains simpler
- version snapshots become naturally inspectable and portable
- later DB indexing can still be added if lookup needs grow

## API proposal

Not approved for immediate implementation. If pursued, keep the surface bounded:

- `POST /protocol-cards`
- `GET /protocol-cards`
- `GET /protocol-cards/{protocol_id}`
- `POST /protocol-cards/{protocol_id}/versions`
- `GET /protocol-cards/{protocol_id}/versions`
- `POST /protocol-cards/{protocol_id}/activate-version`

Do not introduce:
- generic `/documents` or `/projects` dependencies as a prerequisite
- broad protocol CRUD that ignores evidence lineage

## Integration rules

### Evidence

- paper-derived protocol claims should carry `source_refs[]`
- if evidence is incomplete, mark the step or card as incomplete rather than upgrading confidence

### Obsidian

- an Obsidian mirror may exist
- the mirror is not the canonical write target for protocol version state
- sync should remain idempotent if added

### Persona/profile/mode

- protocol cards are not personas
- protocol cards are not profiles
- output/view modes must not change protocol truth

## Suggested PR sequence

1. `PR-DOC-ProtocolKnowledge-RFC`
- keep this RFC as the first boundary document

2. `PR-BE-ProtocolKnowledge-SchemaStore-v0`
- add file-backed schema/store only
- no UI, no broad DB migration

3. `PR-BE-ProtocolKnowledge-API-v0`
- add thin bounded API surface

4. `PR-FE-ProtocolKnowledge-Inspector-v0`
- add read-first UI before broad editing UI

## Adoption gate

Do not implement this layer just because the external proposal contained it.

Implement only if:
- protocol handling is still a product priority
- evidence-link and versioning discipline can be preserved
- it can be added without redefining the whole product around `projects/documents`
