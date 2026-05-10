# Assistant-Facing Summary Contracts

Status: proposal / future seam
Date: 2026-05-10
Owner: Runtime/integration maintainers
Canonical parents:
- `docs/Personal_Assistant_Integration_Seam_2026-05-10.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`

Related docs:
- `docs/API_CHAT_CONTRACT.md`
- `docs/MEETING_PACK.md`
- `docs/RESEARCH_DNA.md`

## Purpose

Define the safest future assistant-facing summary contract for PaperPipe/Lattice.

This note answers one bounded question:

- if a separate personal assistant later reads PaperPipe state, what thin summary shapes should it consume instead of reconstructing meaning directly from raw API payloads, vault files, and artifact directories?

This note is for:

- thin summary/read-model planning
- stable projection rules over current route and schema vocabulary
- future CLI/API/MCP adapter planning

This note is not:

- a new truth store
- a replacement for current route response models
- permission to widen PaperPipe into a generic assistant or workspace platform

## Current rule

Assistant-facing summaries must be:

- thin
- bounded
- provenance-preserving
- explicitly non-canonical

They are projections over current PaperPipe truth.
They do not replace:

- paper-scoped structured state
- job/run state
- saved artifact bundles
- Research DNA records

## 1. Design rules

### 1.1 Projection, not reinvention

When possible, assistant-facing summaries should be derived from existing response models and schema families such as:

- `PaperSummaryResponse`
- `PaperDetailResponse`
- `PaperRailSummaryResponse`
- `PaperNoteOpsSummary`
- `JobStatus`
- `ArtifactBundleResponse`
- `MeetingPackListItem`
- `MeetingPackValidation`
- `MeetingPackTraceResponse`
- `ResearchDNAEnvelope`
- `ResearchDNAResumeEnvelope`
- `ResearchDNARunIndexEnvelope`

The goal is not to invent a parallel PaperPipe API.

### 1.2 Non-canonical by construction

Every assistant-facing summary should be interpreted as:

- a view
- a handoff surface
- a navigation surface

not as canonical scientific or runtime truth.

### 1.3 Short, explicit, operator-meaningful

Each summary should help answer:

- what is this object?
- what state is it in?
- what warnings matter?
- what should the operator do next?

### 1.4 Keep path and artifact details subordinate

Absolute file paths, artifact bundle members, and internal log locations may still exist in upstream responses.
Assistant-facing summaries should expose them only where they materially help navigation or safe replay.

## 2. Common summary spine

All assistant-facing summary families should prefer a shared spine when possible.

Recommended common fields:

- `id`
- `uri`
- `family`
- `title`
- `status`
- `summary`
- `warnings`
- `updated_at`
- `next_operator_action`
- `canonical_status`
- `source_refs`
- `artifact_refs`

### Notes

- `uri` should use the future canonical PaperPipe URI form described in `docs/Personal_Assistant_Integration_Seam_2026-05-10.md`.
- `canonical_status` should remain explicit and normally be `non_canonical` for assistant summary payloads.
- `warnings` should remain terse and operator-meaningful.

## 3. Summary families

## 3.1 Paper summary

### Current upstream anchors

- `src/schemas/papers.py::PaperSummaryResponse`
- `src/schemas/papers.py::PaperDetailResponse`
- `src/schemas/papers.py::PaperRailSummaryResponse`
- `src/schemas/paper_notes.py::PaperNoteOpsSummary`
- `src/schemas/papers.py::PaperAccessSummary`

### Future assistant projection

Suggested name:

- `AssistantPaperSummary`

Suggested fields:

- `id`
  - `paper_id`
- `uri`
  - `paperpipe://paper/{paper_id}`
- `family`
  - `paper`
- `title`
- `authors`
- `year`
- `status`
- `summary`
  - short assistant-facing summary, not a scientific synthesis
- `issues_label`
- `issues_state`
- `updated_at`
- `latest_job_id`
- `latest_run_id`
- `ops_summary`
  - thin pass-through/projection of `PaperNoteOpsSummary`
- `access_summary`
  - thin pass-through/projection of `PaperAccessSummary`
- `next_operator_action`
  - normally derived from `ops_summary.recommended_action`
- `warnings`
  - from issues/escalation/access friction
- `source_refs`
  - e.g. note slug, PDF route, structured state route when appropriate

### Rule

The assistant summary should not pretend to summarize the scientific content of the paper unless that summary is explicitly drawn from a bounded derived artifact family.

## 3.2 Run summary

### Current upstream anchors

- `src/jobs/schemas.py::JobStatus`
- `src/schemas/ops.py::RunTimelineResponse`

### Future assistant projection

Suggested name:

- `AssistantRunSummary`

Suggested fields:

- `id`
  - `run_id`
- `uri`
  - `paperpipe://run/{run_id}`
- `family`
  - `run`
- `paper_id`
- `job_id`
- `status`
- `stage`
- `progress`
- `summary`
  - short current-state summary for the run
- `updated_at`
  - prefer heartbeat/finished/latest meaningful run timestamp
- `claimset_readiness`
- `claimset_readiness_reason`
- `claimset_ops_action`
- `claimset_ops_note`
- `artifact_dir`
- `warnings`
  - failures, unresolved readiness, missing artifacts, stalled/stale signs
- `next_operator_action`
  - derived from readiness/action/failure state
- `artifact_refs`
  - bounded list of important produced artifact identifiers or paths

### Rule

The assistant should consume the run summary as an operational object, not as a scientific truth object.

## 3.3 Generic artifact summary

### Current upstream anchors

- `src/schemas/ops.py::ArtifactBundleResponse`
- family-specific summary classes such as:
  - `ChartPackSummary`
  - `ImageEvidenceSummary`
  - `ProtocolCardSummary`
  - `MeetingPackListItem`

### Future assistant projection

Suggested name:

- `AssistantArtifactSummary`

Suggested fields:

- `id`
- `uri`
- `family`
  - e.g. `meeting_pack`, `chart_pack`, `image_evidence`, `protocol_card`, `paper_synthesis`
- `title`
- `status`
- `summary`
- `updated_at`
- `readiness`
  - when the family has a readiness notion
- `warnings`
- `source_refs`
  - paper ids, run ids, dna ids, selectors, etc.
- `artifact_refs`
  - bounded artifact members or primary file refs
- `next_operator_action`

### Rule

Do not expose every bundle file by default.
Assistant-facing artifact summaries should point to the primary operator-relevant bundle members only.

## 3.4 Meeting Pack summary

### Current upstream anchors

- `src/schemas/meeting_pack.py::MeetingPackListItem`
- `src/schemas/meeting_pack.py::MeetingPackValidation`
- `src/schemas/meeting_pack.py::MeetingPackTraceResponse`

### Future assistant projection

Suggested name:

- `AssistantMeetingPackSummary`

Suggested fields:

- `id`
  - `pack_id`
- `uri`
  - `paperpipe://meeting-pack/{pack_id}`
- `family`
  - `meeting_pack`
- `title`
- `mode`
- `output_mode_family`
- `status`
- `readiness`
- `summary`
  - short operator-facing description
- `created_at`
- `source_count`
- `slide_count`
- `trace_entry_count`
- `primary_source_title`
- `warnings`
  - from validation/trace/readiness
- `next_operator_action`
  - rerender, regenerate, review, reopen markdown, inspect trace
- `artifact_refs`
  - markdown, trace, validation, key bundle members

### Rule

Meeting Pack summaries should preserve the distinction between:

- evidence-backed readiness
- background-only material
- rerender/regenerate availability

They must not flatten those differences into one generic “ready” label.

## 3.5 Research DNA summary

### Current upstream anchors

- `src/schemas/research_dna.py::ResearchDNAEnvelope`
- `src/schemas/research_dna.py::ResearchDNAResumeEnvelope`
- `src/schemas/research_dna.py::ResearchDNARunIndexEnvelope`
- `src/profiles/research_dna_schema.py::ResearchDNARunSummary`
- `src/profiles/research_dna_schema.py::ResearchDNAResumeSnapshot`

### Future assistant projection

Suggested name:

- `AssistantResearchDnaSummary`

Suggested fields:

- `id`
  - `dna.id`
- `uri`
  - `paperpipe://research-dna/{dna_id}`
- `family`
  - `research_dna`
- `title`
- `status`
  - e.g. `DRAFT`, `PILOT`, `LOCKED`
- `summary`
- `query_version_count`
- `latest_run_id`
- `run_count`
- `has_runs`
- `screening_state`
  - thin derived cue from resume/session/progress
- `warnings`
  - low signal, incomplete screening, stale pilot, missing guidance artifacts
- `next_operator_action`
  - pilot, rerank, screen current, refine, lock, inspect resume
- `source_refs`
  - run/resume/guidance references
- `artifact_refs`
  - run dir, queue/guidance/recommendation artifacts when relevant

### Rule

Research DNA is a bounded operator lane, not a generic project-memory object.
Assistant-facing summaries should keep that narrow lane identity visible.

## 4. Common substructures

Where possible, reuse or thinly project existing bounded structures instead of flattening them into opaque strings.

### 4.1 `ops_summary`

For paper-facing summaries, preserve `PaperNoteOpsSummary` fields where they exist:

- `state`
- `label`
- `reason`
- `recommended_action`
- `latest_run_id`

### 4.2 `warnings`

Warnings should stay as a short list of bounded strings.
Do not replace structured readiness or gate fields with one unstructured warning blob.

### 4.3 `next_operator_action`

This field should be present when PaperPipe can already express a bounded next step, such as:

- `repair_stats`
- `open_workbench`
- `rerender`
- `regenerate`
- `screen_current`
- `inspect_trace`

If the current runtime cannot honestly suggest one bounded action, prefer `null` over invented orchestration prose.

## 5. Projection rules for adapters

Future adapters should follow this order:

1. service/runtime truth
2. current route/schema response
3. assistant-facing thin projection
4. CLI rendering / MCP resource / assistant retrieval payload

### Current rule

Do not make:

- one projection for CLI
- another for API
- another for MCP
- another for the assistant

when one bounded assistant-facing summary contract can sit above the existing route/schema layer.

## 6. Near-term implementation order

If these summaries are implemented later, the safest order is:

1. `AssistantPaperSummary`
2. `AssistantRunSummary`
3. `AssistantMeetingPackSummary`
4. `AssistantResearchDnaSummary`
5. family-specific `AssistantArtifactSummary` projections

Why this order:

- papers and runs are the current product center
- meeting packs and Research DNA are already bounded downstream lanes
- a generic artifact summary should come after the assistant has a stable paper/run vocabulary

## 7. What not to do

Do not:

- create a parallel canonical summary database
- treat assistant summaries as biomedical truth
- flatten bounded lane semantics into one global project/task vocabulary
- hide readiness, uncertainty, or warning states behind polished one-liners
- widen PaperPipe’s current product boundary just to satisfy a future assistant

## Conclusion

The safest assistant-facing summary contract for PaperPipe is:

- thin
- route/schema-aligned
- provenance-preserving
- non-canonical
- and bounded by the current paper/run/artifact product shape

That gives a future assistant something stable to read without forcing PaperPipe to become the assistant’s memory system or workspace truth owner.
