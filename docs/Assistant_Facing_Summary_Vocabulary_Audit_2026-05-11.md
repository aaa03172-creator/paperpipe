# Assistant-Facing Summary Vocabulary Audit

Status: review artifact / docs-only
Date: 2026-05-11
Owner: Runtime/integration maintainers
Review target:
- `docs/Assistant_Facing_Summary_Contracts_2026-05-10.md`

Canonical references checked:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Personal_Assistant_Integration_Seam_2026-05-10.md`
- `docs/Identity_Pathing_Audit_2026-03-13.md`
- `src/schemas/`
- `src/jobs/schemas.py`
- `backend/main.py`
- `backend/routers/meeting_packs.py`
- `backend/routers/chart_packs.py`
- `backend/routers/image_evidence.py`
- `backend/routers/protocol_cards.py`
- `backend/routers/paper_syntheses.py`

## Purpose

Review the proposed assistant-facing summary vocabulary against the current PaperPipe route and schema surface before any implementation work opens.

This audit is docs-only. It does not approve new runtime models, API routes, CLI commands, MCP tools, or persisted artifact shapes.

## Overall disposition

`accept but defer implementation`

The proposed summary family names are directionally compatible with the current PaperPipe runtime shape, but implementation should remain blocked until canonical identity/URI handling is settled for each object family.

## Summary

| Proposed family | Vocabulary disposition | Implementation disposition | Reason |
| --- | --- | --- | --- |
| `AssistantPaperSummary` | accept with minor field-source notes | defer | Existing paper response models are strong anchors, but `paper_id` pathing remains transitional. |
| `AssistantRunSummary` | accept | defer | `JobStatus` and `RunTimelineResponse` support the proposed operational vocabulary. |
| `AssistantMeetingPackSummary` | accept with field-source notes | defer | Meeting Pack schemas and routes already expose most proposed fields. |
| `AssistantResearchDnaSummary` | accept with route-scope notes | defer | Research DNA has bounded schemas and routes, but summary projection needs careful lane framing. |
| `AssistantArtifactSummary` | defer vocabulary finalization | defer | A generic `artifact_id` family is not yet canonical across artifact surfaces. |

## Findings

### 1. Paper summary

Disposition: `accept with minor field-source notes`

Current anchors exist:
- `src/schemas/papers.py::PaperSummaryResponse`
- `src/schemas/papers.py::PaperDetailResponse`
- `src/schemas/papers.py::PaperRailSummaryResponse`
- `src/schemas/paper_notes.py::PaperNoteOpsSummary`
- `src/schemas/papers.py::PaperAccessSummary`
- `backend/main.py` exposes `GET /papers`, `GET /papers/rail`, `GET /papers/recent`, `GET /papers/{paper_id}`, and `GET /papers/{paper_id}/pdf`.

The proposed fields mostly map cleanly:
- `paper_id`, `title`, `authors`, `year`, `status`, `issues_label`, `issues_state`, `latest_job_id`, `latest_run_id`, `updated_at`, `ops_summary`, and `access_summary` are present or directly derivable.
- `next_operator_action` can be derived from `ops_summary.recommended_action`.
- `source_refs` can point to note slug, PDF route, and paper detail route.

Field-source note:
- Keep `summary` explicitly non-scientific unless it is derived from a bounded artifact family. The current paper schemas expose metadata and operational state, not a canonical scientific synthesis.
- Include `note_slug` as a candidate source reference rather than hiding it behind prose.

Implementation blocker:
- `paperpipe://paper/{paper_id}` should wait for the identity/pathing follow-up because `docs/Identity_Pathing_Audit_2026-03-13.md` still marks `paper_id` and filesystem pathing as transitional.

### 2. Run summary

Disposition: `accept`

Current anchors exist:
- `src/jobs/schemas.py::JobStatus`
- `src/schemas/ops.py::RunTimelineResponse`
- `backend/main.py` exposes `GET /jobs/{job_id}`, `GET /runs/{run_id}`, and `GET /runs/{run_id}/timeline`.

The proposed fields map cleanly:
- `run_id`, `paper_id`, `job_id`, `status`, `stage`, `progress`, `artifact_dir`, `claimset_readiness`, `claimset_readiness_reason`, `claimset_ops_action`, and `claimset_ops_note` are present or directly derivable.
- `updated_at` should prefer `heartbeat_at`, then `finished_at`, then `started_at`, then `created_at`.
- `warnings` can be derived from failed/cancelled status, error fields, stale heartbeat signs, and unresolved claimset readiness.

Field-source note:
- `summary` should remain an operational state sentence. It should not summarize paper content or artifact contents.

Implementation blocker:
- `paperpipe://run/{run_id}` should wait for the identity/pathing follow-up because `run_id` generation has historical inconsistency across queue, job runner, skills, and eval tooling.

### 3. Meeting Pack summary

Disposition: `accept with field-source notes`

Current anchors exist:
- `src/schemas/meeting_pack.py::MeetingPackListItem`
- `src/schemas/meeting_pack.py::MeetingPackValidation`
- `src/schemas/meeting_pack.py::MeetingPackTraceResponse`
- `backend/routers/meeting_packs.py` exposes `/meeting-packs`, `/meeting-packs/{pack_id}`, `/meeting-packs/{pack_id}/trace`, `/meeting-packs/{pack_id}/validate`, `/meeting-packs/{pack_id}/regenerate`, `/meeting-packs/{pack_id}/rerender`, and `/meeting-packs/{pack_id}/markdown`.

The proposed fields mostly map cleanly:
- `pack_id`, `title`, `mode`, `output_mode_family`, `created_at`, `readiness`, `source_count`, `slide_count`, `trace_entry_count`, and `primary_source_title` are present in `MeetingPackListItem`.
- `warnings`, `can_regenerate`, and `regenerate_strategy` are present in `MeetingPackValidation`.
- trace availability and trace summary are present in `MeetingPackTraceResponse`.

Field-source notes:
- `status` exists on full `MeetingPack`, not on `MeetingPackListItem`. A summary implementation should either load the full pack or mark status unavailable when using list-only input.
- `summary` can derive from `one_page_summary` on full `MeetingPack`, but this should be a bounded operator-facing description, not a new truth claim.
- `next_operator_action` should be derived from validation and route availability, especially `rerender`, `regenerate`, `review`, `reopen_markdown`, or `inspect_trace`.

Implementation blocker:
- `paperpipe://meeting-pack/{pack_id}` is directionally acceptable, but should wait for the broader URI helper decision.

### 4. Research DNA summary

Disposition: `accept with route-scope notes`

Current anchors exist:
- `src/schemas/research_dna.py::ResearchDNAEnvelope`
- `src/schemas/research_dna.py::ResearchDNAResumeEnvelope`
- `src/schemas/research_dna.py::ResearchDNARunIndexEnvelope`
- `src/profiles/research_dna_schema.py::ResearchDNA`
- `src/profiles/research_dna_schema.py::ResearchDNARunSummary`
- `src/profiles/research_dna_schema.py::ResearchDNAResumeSnapshot`
- `backend/main.py` exposes bounded `/research-dna` routes for create, fetch, update, interview, pilot, rerank, guidance, run index, resume, screening, refine, lock, unlock, and profile projection.

The proposed fields mostly map cleanly:
- `dna.id`, `title`, `status`, `query_versions`, run index, latest run, resume, screening session, progress, recommendation, and gate all have bounded upstream anchors.
- `screening_state` can be a thin derived cue from resume/session/progress, but should not become a parallel project-status model.
- `next_operator_action` can be derived from current DNA status, run availability, screening progress, and gate state.

Route-scope note:
- Research DNA has many route-specific envelopes. A future summary should be a small projection over `ResearchDNAEnvelope`, `ResearchDNARunIndexEnvelope`, and `ResearchDNAResumeEnvelope`, not a flattening of all Research DNA sub-artifacts.

Implementation blocker:
- `paperpipe://research-dna/{dna_id}` is directionally acceptable, but should wait for the URI helper decision and should preserve Research DNA as a bounded operator lane.

### 5. Generic artifact summary

Disposition: `defer vocabulary finalization`

Current anchors exist but are not one canonical artifact identity family:
- `src/schemas/ops.py::ArtifactBundleResponse` uses `paper_id`, `run_id`, and `files`.
- family-specific summaries use family-specific identifiers such as `chart_pack_id`, `image_evidence_id`, `protocol_id`, `pack_id`, and paper synthesis IDs.
- route surfaces are family-specific: `/artifacts`, `/chart-packs`, `/image-evidence`, `/protocol-cards`, `/paper-syntheses`, and `/meeting-packs`.

Concern:
- `paperpipe://artifact/{artifact_id}` is too broad until PaperPipe defines what `artifact_id` means across runtime bundles, individual artifact files, and family-specific artifacts.

Smallest fix direction:
- Defer `AssistantArtifactSummary` as a generic contract.
- Prefer family-specific summaries first: `AssistantMeetingPackSummary`, future `AssistantChartPackSummary`, future `AssistantImageEvidenceSummary`, future `AssistantProtocolCardSummary`, and future `AssistantPaperSynthesisSummary`.
- If a generic artifact summary is later needed, define its identity as a typed composite reference, such as `{family, object_id, paper_id?, run_id?, artifact_name?}`, before exposing a URI.

## URI family audit

| Proposed URI | Disposition | Note |
| --- | --- | --- |
| `paperpipe://paper/{paper_id}` | accept directionally, block implementation | `paper_id` is active runtime vocabulary, but pathing remains transitional. |
| `paperpipe://run/{run_id}` | accept directionally, block implementation | Runtime route exists, but run ID generation needs project-wide confidence. |
| `paperpipe://job/{job_id}` | accept directionally, block implementation | Job status routes exist; job/run relationship should stay explicit. |
| `paperpipe://meeting-pack/{pack_id}` | accept directionally, block implementation | Pack ID is bounded and route-backed. |
| `paperpipe://research-dna/{dna_id}` | accept directionally, block implementation | DNA ID is bounded and route-backed. |
| `paperpipe://artifact/{artifact_id}` | defer | Generic artifact identity is not yet canonical. |

## Recommended edits to the contract doc

1. Add a note that `AssistantArtifactSummary` remains deferred until generic artifact identity is defined.
2. Add a note that `MeetingPackListItem` does not carry full `status`; status requires full `MeetingPack` input or should be nullable.
3. Add `note_slug` as an explicit candidate `source_refs` value for `AssistantPaperSummary`.
4. Clarify that `updated_at` for `AssistantRunSummary` should be derived from `heartbeat_at`, `finished_at`, `started_at`, or `created_at` in that order.
5. Add a URI blocker note: all `paperpipe://...` URI shapes are planning vocabulary until a shared URI/identity helper is adopted.

## Next PR-sized actions

1. Patch `docs/Assistant_Facing_Summary_Contracts_2026-05-10.md` with the five recommended edits above.
2. Create a separate identity helper RFC for `paperpipe://...` URI generation and object-family mapping.
3. Keep all assistant-facing summary implementation out of scope until the contract doc is patched and the URI helper direction is accepted.

## Verification

Verification performed:
- Read `docs/Assistant_Facing_Summary_Contracts_2026-05-10.md`.
- Checked route vocabulary in `docs/Lattice_v3_Master_Spec.md`.
- Checked active FastAPI routes in `backend/main.py` and relevant router modules.
- Checked current Pydantic anchors in `src/schemas/`, `src/jobs/schemas.py`, and `src/profiles/research_dna_schema.py`.

No runtime tests were run because this is a docs-only review artifact.
