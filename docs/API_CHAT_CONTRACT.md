# API Chat Contract

Status: Stub-only compatibility surface
Date: 2026-04-08
Owner: Chat/runtime maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Scope
- `/api/chat` exists only as a stub-only integration hook.
- shared `output_mode_family` is now accepted as an additive request hint and echoed in the stub response.
- The current runtime does not implement:
  - LLM provider calls
  - chat UI
  - memory or conversation persistence
  - RAG or retrieval orchestration
- When `CHAT_ENABLED=false` (default), the endpoint returns `501 Not Implemented`.
- When `CHAT_ENABLED=true`, the endpoint still returns `501 Not Implemented` in the current runtime.

## Canonical State Source
- Structured paper state lives at `.pp/<slug>/state.json` inside the Obsidian vault.
- The backend detail API exposes this sidecar as `structured_state` on `GET /paper-notes/{slug}`.
- `frontmatter.pp` remains a light index only:
  - `pp.structured_path`
  - `pp.last_run`
  - `pp.actions_done`
  - `pp.signals`

## Stable ID Contract
- `run.id`
  - Existing structured run id, for example `skill-20260309T000000Z-critical_appraisal`
  - Stable for that recorded run entry
- `claim.id`
  - Deterministic id in `state.json`
  - New writes use a content-derived stable id
  - Legacy `source_claim_id` is preserved when present
- `evidence.id`
  - Deterministic id in `state.json`
  - Derived from claim identity plus locator/text payload

## Deep Link Contract
- Claim focus: `/papers/<slug>?focus=claim:<claim.id>`
- Evidence focus: `/papers/<slug>?focus=evidence:<evidence.id>`
- Run focus: `/papers/<slug>?focus=run:<run.id>`

## Structured State Shape

Minimum kept for chat readiness:

```json
{
  "schema_version": "2026-03-09.chat-hooks.v1",
  "paper_slug": "example-paper",
  "updated_at": "2026-03-09T00:00:00Z",
  "runs": [],
  "signals": {
    "has_claimset": true,
    "claim_count": 2,
    "evidence_count": 3,
    "run_count": 1,
    "last_run_id": "skill-20260309T000000Z-critical_appraisal"
  },
  "claimset": [],
  "entities": [],
  "mesh": [],
  "outcomes": []
}
```

Claim and evidence shape:

```json
{
  "id": "claim_abc123",
  "source_claim_id": "CLM-001",
  "run_id": "skill-20260309T000000Z-critical_appraisal",
  "claim": "Example claim text",
  "evidence_ids": ["evidence_def456"],
  "evidence": [
    {
      "id": "evidence_def456",
      "claim_id": "claim_abc123",
      "run_id": "skill-20260309T000000Z-critical_appraisal",
      "text": "Quoted or extracted evidence text",
      "locator": {
        "page": 2,
        "span": [120, 188],
        "section": "Results",
        "chunk_id": "chunk_12",
        "char_start": 120,
        "char_end": 188,
        "bbox_pct": { "left": 0.12, "top": 0.33, "width": 0.48, "height": 0.06 }
      }
    }
  ]
}
```

## ChatResponse Contract

```ts
type ChatResponse = {
  answer: string;
  output_mode_family: "learner" | "lab_meeting" | "project_update" | "builder_debug";
  evidence_refs: Array<{
    paper_slug: string;
    claim_id?: string;
    evidence_id?: string;
    run_id?: string;
    locator?: {
      page?: number;
      span?: number[];
      section?: string;
      chunk_id?: string;
      char_start?: number;
      char_end?: number;
      bbox_pdf?: number[];
      bbox_pct?: Record<string, number>;
      table_id?: string;
      cell_id?: string;
      source?: string;
    };
  }>;
  suggested_actions?: Array<{
    action: string;
    reason: string;
  }>;
};
```

## Example Response Payload

```json
{
  "answer": "The note suggests the intervention reduced IL-1b release, but the confidence is mixed.",
  "evidence_refs": [
    {
      "paper_slug": "wenzelShortchainFattyAcids2020",
      "claim_id": "claim_4d5f89ab12cd",
      "evidence_id": "evidence_81b6d88e2f43",
      "run_id": "skill-20260309T000000Z-critical_appraisal",
      "locator": {
        "page": 1,
        "section": "Abstract"
      }
    }
  ],
  "suggested_actions": [
    {
      "action": "critical_appraisal",
      "reason": "Refresh the claim/evidence state before answering with stronger certainty."
    }
  ]
}
```

## Stub Behavior

Request:

```json
{
  "paper_slug": "example-paper",
  "message": "What is the main claim?",
  "focus": "claim:claim_abc123",
  "output_mode_family": "learner"
}
```

Current response:

```json
{
  "error_code": "CHAT_NOT_IMPLEMENTED",
  "chat_enabled": false,
  "output_mode_family": "learner",
  "message": "CHAT_ENABLED=false. /api/chat is a stub-only compatibility surface; no LLM provider, memory, or RAG call is executed.",
  "external_calls": false
}
```

## Output Mode Behavior
- `output_mode_family` is presentation-only.
- It does not enable a separate agent runtime or retrieval policy.
- Current stub behavior:
  - if omitted, the effective family defaults to `learner`
  - if provided, the stub echoes the requested family in the response
  - endpoint behavior remains `501 Not Implemented` either way

## Future Answer-Generation Boundary
- If `/api/chat` becomes live later, evidence-backed biomedical answers should route through current structured paper state and upstream evidence refs first.
- `output_mode_family` may change wording density or framing, but it must not select a looser truth policy.
- Raw memory, backend-only `Project Memory`, compiled knowledge assets, and review/gate artifacts may help focus retrieval or answer composition, but they must not become stronger truth owners than canonical evidence-linked state.
- If a future answer path cannot recover a clear canonical/evidence trace, the response should stay explicitly uncertain or background-only rather than sounding fully grounded.
