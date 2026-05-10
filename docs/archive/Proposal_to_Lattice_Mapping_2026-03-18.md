# Proposal to Lattice Mapping

Status: Historical adaptation note  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Scope: remap the external proposal set into current PaperPipe/Lattice vocabulary and adoption lanes

Related docs:
- `docs/archive/Agent_Proposal_Fit_Review_2026-03-18.md`
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/Local_Backup_Branch_Retention_2026-02-24.md`
- `docs/archive/Local_Backup_and_Restore_Semantics_RFC_2026-03-18.md`
- `docs/archive/Protocol_Knowledge_Layer_RFC_2026-03-18.md`
- `docs/archive/Method_Comparison_Layer_RFC_2026-03-18.md`
- `docs/archive/Project_Memory_Layer_RFC_2026-03-18.md`

Source proposal set:
- `agent_project_definition_v1_1.md`
- `agent_execution_backlog_v1.md`
- `agent_prd_technical_spec_v1_2.md`
- `agent_db_schema_api_contract_v1.md`

## Reclassification

The external proposal set should be treated as:
- a `v4 direction hypothesis`
- a product-positioning reference
- a bounded RFC source pack

It should not be treated as:
- a replacement for `docs/Lattice_v3_Master_Spec.md`
- a direct replacement for the current API surface
- a direct replacement for the current runtime DB model

## Document Placement

| External doc | New classification | Current use |
| --- | --- | --- |
| `agent_project_definition_v1_1.md` | Product positioning reference | Mine product framing and local-first/evidence language into `docs/Product_Positioning_Principles.md` only |
| `agent_execution_backlog_v1.md` | Historical story pool | Reuse only after remapping onto current `papers/jobs/artifacts` baseline |
| `agent_prd_technical_spec_v1_2.md` | Future subsystem proposal input | Split into bounded RFCs instead of treating it as the present runtime contract |
| `agent_db_schema_api_contract_v1.md` | Greenfield persistence/API proposal | Keep as a future design reference, not a drop-in migration plan |

## Concept Mapping

| External concept | Current Lattice equivalent | Fit | Decision | Notes |
| --- | --- | --- | --- | --- |
| Local-first research workspace | `docs/Lattice_v3_Master_Spec.md`, local artifact storage, Obsidian mirror | High | Adopt | Already aligned with current runtime philosophy |
| Evidence tracing | `ClaimSet`, `EvidenceSpan`, `claimset.resolved.json`, chat/meeting-pack `evidence_refs[]` | High | Adopt | Keep one locator family across downstream surfaces |
| Uncertainty labeling | `unknown`, `unknown_reason`, `grounded`, `resolution`, pack conflicts/readiness | High | Adopt | Surface uncertainty instead of hiding it in rendering |
| Non-destructive jobs | `jobs`, `execution_runs`, artifact writes, regenerate/rerender flows | High | Adopt | Preserve additive writes and rollback-safe artifact generation |
| Backup/restore semantics | local backup policy plus future runtime backup RFC lane | Medium | Adopt later | Valuable philosophy, but not a reason to redefine current top-level model |
| `projects` | No current top-level equivalent | Low | Reject now | Would redefine the product around a different primary entity |
| `documents` | Split across `papers`, `document_artifact`, note `state.json`, and saved artifacts | Low | Remap only | Do not introduce `documents` as a new canonical umbrella without a product reset |
| `document_references` | paper-note references, Zotero identity, artifact lineage | Medium | Remap | Keep under current paper-centric identity model |
| `protocol_cards` | Future protocol knowledge layer | Medium | Defer | Start as a bounded layer, not a new platform root |
| `method_records` | Future method comparison layer | Medium | Defer | Should stay paper-centric and evidence-linked |
| `project_memory_items` | Future project memory layer | Medium | Defer | Do not collapse this into `Research DNA` |
| `output_artifacts` | `storage/artifacts/*`, Obsidian outputs, `Meeting Pack` bundles | Medium | Adopt via remap | Reuse existing artifact/storage vocabulary first |
| `/projects` API family | No current equivalent | Low | Reject now | Not part of the shipped backend contract |
| `/documents` API family | No current equivalent | Low | Reject now | Current runtime is `papers/jobs/artifacts`, not document CRUD-first |
| Normalized `projects/documents/protocols/memory` DB | `papers` plus `jobs/execution_runs/job_events/user_actions` | Low | Reject now | This is a future persistence redesign, not a spec update |
| Protocol versioning | Future protocol knowledge layer, append-only/versioned artifacts patterns | Medium | Defer | Good idea, but bounded and future-facing |
| Method comparison workspace | Future method comparison layer | Medium | Defer | Useful once it can reuse current claim/evidence lineage |
| Project memory workspace | Future project memory layer | Medium | Defer | Requires an explicit product decision before becoming first-class |

## Vocabulary Remap Rules

- `documents` must be resolved into one of: `papers`, `document_artifact`, note `state.json`, or saved artifact bundles.
- `project memory` must stay separate from `Research DNA`; `Research DNA` is a search-design asset, not general workspace memory.
- `protocol cards` should begin as a bounded protocol layer or artifact family, not as a new top-level CRUD platform.
- `method records` should be derived from current paper/evidence state, not stored as truth detached from claim lineage.
- `output artifacts` should extend the current artifact family, not create a second parallel output stack.

## Recommended Adoption Order

1. Consolidate current evidence and uncertainty rules into an active bounded spec.
2. Keep protocol, method comparison, and project memory as separate future RFC lanes.
3. Revisit backup/restore semantics only after deciding whether a broader workspace layer should become first-class.

## Bottom Line

The external proposal set is not a bad fit because the ideas are weak. It is a bad fit only if treated as a current-system replacement.

The accurate placement is:
- keep current Lattice docs as SSOT
- treat the external set as a `vision pack / RFC source pack`
- import ideas only after remapping them into current PaperPipe vocabulary and bounded surfaces
