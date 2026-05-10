# Agent Proposal Fit Review

Status: Historical fit review  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Scope: external proposal-doc review against current PaperPipe/Lattice runtime and canonical docs

Reviewed external docs:
- `/Users/jangseongjin/Library/CloudStorage/OneDrive-개인/ai논문에이전트/제안서/agent_project_definition_v1_1.md`
- `/Users/jangseongjin/Library/CloudStorage/OneDrive-개인/ai논문에이전트/제안서/agent_execution_backlog_v1.md`
- `/Users/jangseongjin/Library/CloudStorage/OneDrive-개인/ai논문에이전트/제안서/agent_prd_technical_spec_v1_2.md`
- `/Users/jangseongjin/Library/CloudStorage/OneDrive-개인/ai논문에이전트/제안서/agent_db_schema_api_contract_v1.md`

Reference baseline:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/README.md`
- current backend routes in `backend/main.py`
- current runtime DB bootstrap in `src/db_utils.py`

Follow-on docs created from this review:
- `docs/Product_Positioning_Principles.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/archive/Proposal_to_Lattice_Mapping_2026-03-18.md`
- `docs/archive/Protocol_Knowledge_Layer_RFC_2026-03-18.md`
- `docs/archive/Method_Comparison_Layer_RFC_2026-03-18.md`
- `docs/archive/Project_Memory_Layer_RFC_2026-03-18.md`
- `docs/archive/Local_Backup_and_Restore_Semantics_RFC_2026-03-18.md`

## Executive judgment

Do not adopt the external proposal set as a new top-level master spec or direct runtime contract.

Use it as:
- a product-positioning reference
- a future subsystem idea pack
- a source of reusable guardrails for evidence tracing, local-first storage, uncertainty handling, and backup semantics

Do not use it as:
- a replacement for `docs/Lattice_v3_Master_Spec.md`
- a direct replacement for the current API surface
- a direct replacement for the current runtime DB model

## What the external docs get right

- The product framing is strong on local-first biomedical research support, evidence traceability, uncertainty labeling, and reducing repeated formatting/search overhead.
- The separation of raw data, structured data, context, and output layers is conceptually sound.
- The PRD correctly pushes for idempotency, lifecycle rules, backup thinking, and non-destructive job execution.
- The DB/API draft is coherent if the product were to become a project-centric document/protocol platform.

## Why it does not fit the current repo as-is

### 1. Product model mismatch

The external set assumes a core model of:
- `projects`
- `documents`
- `document_references`
- `extraction_records`
- `method_records`
- `protocol_cards`
- `project_memory_items`
- `output_artifacts`

Current Lattice/PaperPipe is instead centered on:
- `papers`
- deep-read `jobs`
- run `artifacts`
- `feedback`
- Obsidian sync/mirror
- bounded `Research DNA`
- bounded `Meeting Pack`

This is reflected in the current canonical spec and backend:
- `docs/Lattice_v3_Master_Spec.md` defines the end-to-end system as Zotero -> jobs/artifacts -> Obsidian.
- `backend/main.py` exposes `/papers`, `/jobs/deepread`, `/artifacts`, `/feedback`, `/obsidian`, `/research-dna`, `/meeting-packs`, and `/api/chat` stub.

### 2. DB contract mismatch

The external DB spec assumes a normalized app database with first-class `projects`, `documents`, `protocols`, and memory entities.

Current runtime DB bootstrap in `src/db_utils.py` primarily initializes:
- `jobs`
- `execution_runs`
- `job_events`
- `user_actions`

and extends the existing `papers` table opportunistically.

That means the external DB schema is not a spec update. It is a proposal for a different persistence model.

### 3. API contract mismatch

The external API draft assumes new first-class surfaces such as:
- `POST /projects`
- `POST /documents`
- `POST /projects/{project_id}/extractions`
- `POST /projects/{project_id}/methods`
- `POST /projects/{project_id}/protocols`
- `POST /projects/{project_id}/memory-items`
- `POST /projects/{project_id}/artifacts/generate-summary`
- `POST /projects/{project_id}/backup`

None of these are part of the current shipped backend contract.

### 4. Missing current agent boundary

The current repo has an explicit conceptual split between:
- core reasoning personas
- profile context
- output/view modes

This is normative in:
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/Lattice_v3_Master_Spec.md`

The external documents do not encode this boundary, so adopting them directly would regress the current persona/profile/mode discipline.

## Fit classification by document

### `agent_project_definition_v1_1.md`

Fit: partial

Reusable:
- user-value framing
- local-first rationale
- evidence traceability emphasis
- protocol caution language

Not directly reusable:
- module map as product architecture
- MVP definition as current roadmap baseline

Recommended use:
- source material for `docs/Product_Positioning_Principles.md`
- source material for future protocol/method-comparison subsystem rationale

### `agent_execution_backlog_v1.md`

Fit: low

Problem:
- it assumes the project should prioritize CRUD and schema work for `Document/Project/Protocol/Memory` first
- it ignores already-landed bounded systems such as `Research DNA`, `Meeting Pack`, paper notes viewer, and current artifact/job flows

Recommended use:
- mine individual user stories only after remapping them onto the current repo baseline

### `agent_prd_technical_spec_v1_2.md`

Fit: medium as future design reference, low as current contract

Reusable:
- lifecycle thinking
- idempotency rules
- raw vs derived separation
- backup semantics
- job non-destructive principles

Not directly reusable:
- project-scoped API assumptions
- entity set as the present canonical data model

Recommended use:
- split into future RFC inputs for:
  - protocol knowledge layer
  - method comparison layer
  - project memory layer

### `agent_db_schema_api_contract_v1.md`

Fit: low as current runtime contract, medium as future subsystem proposal

Reusable:
- normalized relation bias
- revision history approach
- soft-delete preference
- explicit enums and error policy style

Not directly reusable:
- top-level table set
- `/projects` and `/documents` API family
- jobs model tied to `project_id` and `document_id`

Recommended use:
- treat as a greenfield data-model proposal for a future project-centric subsystem, not as a drop-in migration target

## Recommended adaptation strategy

### Keep as canonical

- `docs/Lattice_v3_Master_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- the current bounded spec family listed in `docs/README.md`

### Promote selectively

Adopt ideas from the external docs only where they strengthen current bounded specs:
- evidence tracing and uncertainty rules into reader/output contracts
- local-first backup/restore semantics into ops/runbook docs
- protocol versioning ideas into a future bounded protocol spec
- method-comparison concepts into a future bounded comparison spec

### Do not do next

- Do not replace the current master spec with the external PRD set.
- Do not introduce `/projects` and `/documents` as canonical API surfaces without an explicit product decision.
- Do not rewrite the runtime DB around the external normalized schema as a “spec update.”

## Concrete next actions

1. If protocol/method/project-memory features are still desired, write separate bounded RFCs instead of importing the external docs wholesale.
2. If product positioning needs refresh, extract only the reusable framing from `agent_project_definition_v1_1.md` into the current canonical docs.
3. If backup/restore semantics need to become broader than the current script-by-script local discipline, keep that as a bounded ops RFC rather than a stealth `/projects/.../backup` platform decision.
4. If long-term product direction is shifting toward a project-centric research workspace, make that a deliberate v4 product decision and document the migration impact explicitly.
