# Project Memory Layer RFC

Status: Historical proposal  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related:
- `docs/archive/Agent_Proposal_Fit_Review_2026-03-18.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`

## Purpose

External proposal docs argue that the product becomes much more valuable if it can preserve project-scoped questions, judgments, decisions, and links between papers, protocols, and outputs.

That need is directionally correct.

But current Lattice already has adjacent concepts:
- `Research DNA` for search-design assets
- paper notes for per-paper knowledge
- meeting packs for presentation artifacts
- jobs/events/user-actions for operational traces

This RFC defines a future project-memory layer that does not collapse those existing concepts into one vague “project” bucket.

## Current fit

Current repo does not have a first-class project entity.

Current repo does have:
- paper-level state
- profile context
- Research DNA projections
- meeting-pack draft outputs
- Obsidian-backed note context

So any future project-memory layer must respect these boundaries:
- `Project memory` is not `Research DNA`
- `Project memory` is not `profile context`
- `Project memory` is not `output mode`
- `Project memory` is not general chat memory

## Non-goals

- not a generic task manager
- not multi-user collaboration or permissions
- not a replacement for `Research DNA`
- not a replacement for paper notes
- not an excuse to put output/view modes into project metadata

## Boundary rules

### What this layer may do

- store project-scoped questions, judgments, TODOs, decisions, and uncertainties
- link those items to current paper/run/meeting-pack/DNA assets
- preserve confidence and freshness explicitly

### What this layer must not do

- duplicate paper truth into project notes without linkback
- act as the canonical owner of search-profile logic
- mutate `Research DNA` authority silently
- leak decisions across projects by default

## Proposed phase-0 model

### `ProjectWorkspace`

Suggested fields:
- `project_id`
- `title`
- `objective`
- `status`
  - `active`
  - `archived`
- `notes`
- `linked_paper_ids[]`
- `linked_research_dna_ids[]`
- `linked_meeting_pack_ids[]`
- `created_at`
- `updated_at`

### `ProjectMemoryItem`

Suggested fields:
- `item_id`
- `project_id`
- `item_type`
  - `question`
  - `judgment`
  - `note`
  - `todo`
  - `uncertainty`
  - `decision`
- `content`
- `confidence_status`
  - `tentative`
  - `working`
  - `confident`
  - `superseded`
- `freshness_status`
  - `current`
  - `aging`
  - `stale`
  - `superseded`
- `linked_entities[]`
- `created_at`
- `updated_at`

### `ProjectEntityLink`

Suggested fields:
- `entity_type`
  - `paper`
  - `run`
  - `meeting_pack`
  - `research_dna`
  - `paper_note`
  - `protocol_card`
- `entity_id`
- `relationship_type`
  - `references`
  - `supports`
  - `blocks`
  - `decides`
  - `mentions`

## Storage proposal

Phase 0 should stay file-first unless an explicit product decision moves Lattice toward a true project workspace model.

Suggested layout:

```text
storage/project_memory/<project_id>/
  project.json
  memory.jsonl
```

Why this is safer than importing the external DB design directly:
- current repo has no approved `projects` canonical root
- file-backed local assets match the existing single-user operating model
- the layer can prove value before forcing a broad relational migration

## API proposal

Not approved for immediate implementation.

If the product explicitly chooses to add first-class project workspaces, the first bounded API could be:
- `POST /projects`
- `GET /projects`
- `GET /projects/{project_id}`
- `POST /projects/{project_id}/memory-items`
- `GET /projects/{project_id}/memory-items`

Optional later surface:
- `GET /projects/{project_id}/search`

But this API family should not be introduced by stealth as a “small doc update.” It is a product-shape decision.

## Integration rules

### With `Research DNA`

- `Research DNA` remains the owner of search-design state
- project memory may link to DNA assets
- project memory must not silently replace DNA governance or query-version history

### With paper notes

- paper notes remain paper-scoped knowledge objects
- project memory should prefer link refs over copying note content

### With meeting packs

- meeting packs remain presentation artifacts
- project memory may link to a pack as a decision checkpoint
- project memory does not become the hidden canonical store for meeting-pack content

### With persona/profile/mode boundary

- project memory is not a persona
- project memory is not a profile
- project memory is not an output mode
- output/view modes must not be encoded as project truth

## Suggested PR sequence

1. `PR-DOC-ProjectMemory-RFC`
- keep the boundary explicit before implementation

2. `PR-BE-ProjectMemory-FileStore-v0`
- file-backed local model only

3. `PR-BE-ProjectMemory-API-v0`
- add minimal project and memory-item APIs only if explicitly approved

4. `PR-FE-ProjectMemory-Panel-v0`
- add narrow inspection surface after data shape is stable

## Adoption gate

Implement only if the product intentionally decides to add a first-class project workspace layer.

Until then:
- keep this as a future bounded proposal
- do not let it backdoor a full rewrite of the current paper/job/artifact architecture
