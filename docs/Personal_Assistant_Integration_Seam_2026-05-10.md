# Personal Assistant Integration Seam

Status: proposal / future seam
Date: 2026-05-10
Owner: Runtime/integration maintainers
Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`

Related docs:
- `docs/Assistant_Facing_Summary_Contracts_2026-05-10.md`

## Purpose

Define the safest future integration seam between PaperPipe/Lattice and a separate personal assistant OS.

This note exists to answer a narrow question:

- if a separate personal assistant later orchestrates `paperpipe`, what contracts should PaperPipe expose so the assistant can read and act safely without turning PaperPipe into a generic memory or workspace platform?

This note is for:

- stable identity and URI planning
- assistant-facing summary/read models
- write-safety and mutation boundaries
- future CLI/API/MCP adapter planning

This note is not:

- a product-shape decision to turn PaperPipe into a first-class assistant platform
- permission to make PaperPipe a broad personal memory or second-brain owner
- a replacement for current runtime/API/schema contracts

## Current boundary

PaperPipe remains:

- local-first
- paper-first
- job/run/artifact-first
- single-operator-first
- evidence-linked
- human-reviewable

The personal assistant, if added later, is an external orchestrator.

That means:

- PaperPipe remains the truth system for papers, runs, artifacts, Research DNA, and meeting packs
- the assistant may coordinate, summarize, and route actions
- the assistant must not silently become the owner of PaperPipe truth

## 1. Owner split

### PaperPipe owns

- imported paper identity
- canonical paper-scoped structured state
- job/run lifecycle
- saved artifact bundles
- Research DNA state
- Meeting Pack state
- evidence lineage and uncertainty signaling inside supported lanes

### The future assistant may own

- personal goals
- re-entry state
- cross-tool task queues
- personal preferences and playbooks
- user-facing summaries that point back to PaperPipe truth

### Current rule

Do not copy canonical PaperPipe truth into a separate assistant-owned store as if it were the new source of truth.

The assistant may cache references or derived summaries, but should always be able to jump back to canonical PaperPipe state.

## 2. Assistant-facing read contract

If PaperPipe is later exposed to an assistant, the assistant should not need to reconstruct meaning directly from raw route payloads, vault files, and artifact folders.

PaperPipe should expose thin assistant-facing read models for high-value objects.

### Minimum object families

1. `PaperSummary`
2. `RunSummary`
3. `ArtifactSummary`
4. `MeetingPackSummary`
5. `ResearchDnaSummary`

### Recommended common fields

- `id`
- `uri`
- `title`
- `status`
- `summary`
- `warnings`
- `updated_at`
- `source_refs`
- `artifact_refs`
- `next_operator_action`

These read models are not new canonical state.
They are assistant-facing views over existing canonical/runtime truth.

## 3. Canonical identity and URI seam

Before assistant integration is treated as implementation-ready, PaperPipe should converge on a stable identity/URI contract for assistant-safe linking.

### Desired canonical URI shape

- `paperpipe://paper/{paper_id}`
- `paperpipe://run/{run_id}`
- `paperpipe://job/{job_id}`
- `paperpipe://artifact/{artifact_id}`
- `paperpipe://meeting-pack/{pack_id}`
- `paperpipe://research-dna/{dna_id}`

### Why this matters

The assistant needs:

- stable references in its own continuity and goal systems
- durable backlinks from summaries to PaperPipe truth
- a transport-neutral way to refer to objects across CLI, API, and future MCP surfaces

### Current gap

`docs/Identity_Pathing_Audit_2026-03-13.md` already shows that PaperPipe identity/pathing is not yet standardized enough for this assistant seam to be considered implementation-ready across all object families.

## 4. Service boundary requirement

Assistant integration should reuse the existing PaperPipe architectural direction:

- domain/service logic
- FastAPI routes
- thin CLI wrappers
- later, thin MCP wrappers if needed

### Current rule

Do not make a CLI-only assistant path for core logic that should live behind the existing FastAPI/service boundary.

If a future assistant needs a capability, the safest path is usually:

1. service-layer function
2. bounded FastAPI route or existing route expansion
3. CLI wrapper
4. optional MCP adapter later

## 5. Mutation safety contract

The future assistant should only act against PaperPipe when a write belongs to a clearly classified safety lane.

### Suggested safety classes

1. `read_only`
   - inspect paper state
   - inspect run state
   - inspect artifact state

2. `additive_safe`
   - create a new run
   - generate a new artifact bundle
   - append a review artifact

3. `rerender_safe`
   - regenerate a derived artifact from canonical upstream state
   - rebuild a bounded presentation output

4. `operator_confirmed`
   - repair/backfill scripts
   - archive/migration tasks
   - write paths that can change interpretation of existing saved state

### Current rule

An assistant should never have to guess whether an operation is safe.

PaperPipe should document and, where practical, expose whether a given write path is:

- idempotent
- dry-run capable
- additive
- rerenderable
- confirmation-required

## 6. Assistant-safe summary expectations

The assistant should be able to ask questions like:

- what is the latest state of this paper?
- what is the latest relevant run?
- what warnings or uncertainty matter right now?
- what should the operator do next?

That means summary surfaces should prefer:

- short bounded summaries
- explicit warnings
- explicit uncertainty/readiness signals
- explicit next operator action

and should avoid:

- pretending saved artifacts are canonical truth
- hiding missing evidence or stale state behind polished language

## 7. Future MCP posture

If PaperPipe is later wrapped as an MCP server, the safest first mapping is narrow.

### Tools

- `list_papers`
- `get_paper_summary`
- `get_run_summary`
- `get_artifact_summary`
- `enqueue_deepread`
- `generate_meeting_pack`

### Resources

- `paperpipe://paper/{paper_id}`
- `paperpipe://run/{run_id}`
- `paperpipe://artifact/{artifact_id}`
- `paperpipe://meeting-pack/{pack_id}`
- `paperpipe://research-dna/{dna_id}`

### Prompts

- `summarize-paper-state`
- `prepare-meeting-pack-review`
- `triage-run-warning`

### Current rule

MCP, if adopted, should be a thin adapter over existing service/API boundaries.
It should not become a parallel owner of truth or a justification for widening the runtime into a generic assistant platform.

## 8. What to prepare now

The most valuable preparation work inside PaperPipe is not a full assistant implementation.

It is:

1. stable IDs and canonical URIs
2. thin assistant-facing summary/read models
3. explicit mutation safety classes
4. transport-neutral service boundaries
5. docs that state the owner split clearly

## 9. What not to do now

Do not:

- add broad personal memory ownership to PaperPipe
- turn PaperPipe into a generic project/workspace platform
- let compiled knowledge or assistant summaries override canonical state ownership
- add assistant-specific write paths that bypass existing API/service architecture
- expose destructive mutation paths without explicit safety classification

## 10. Near-term adoption checklist

Before implementation-level assistant integration, confirm:

- a canonical identity/URI contract exists for the target object family
- a bounded summary/read model exists for the target object family
- the relevant write path has a declared safety class
- provenance and uncertainty remain visible in the assistant-facing surface
- the integration does not widen PaperPipe’s current product boundary by accident

## Conclusion

The safest PaperPipe assistant integration is:

- orchestration-friendly
- summary-first
- identity-stable
- provenance-preserving
- mutation-classified
- and still subordinate to PaperPipe’s current paper/job/artifact-first runtime shape

That keeps PaperPipe useful to a future personal assistant without quietly turning it into the assistant’s second brain or truth owner.
