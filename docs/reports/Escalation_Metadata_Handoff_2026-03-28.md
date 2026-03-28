# Escalation Metadata Handoff 2026-03-28

Date: 2026-03-28
Status: Active runtime map
Owner: Runtime maintainers

## Goal

Record the current producer/consumer map for structured escalation metadata so future work does not confuse:

- canonical gate status
- escalation fast-lane metadata
- where the metadata is stored
- which surfaces already read it

## Current Runtime Truth

- `GateEngine` remains the canonical status policy for `APPROVED / PENDING_REVIEW / QUARANTINED / FAILED`.
- `evaluate_escalation()` is a secondary fast-lane decision used only after a paper lands in `PENDING_REVIEW`.
- escalation metadata is additive and does not replace the canonical gate state machine.
- current transport is `feedback_json["escalation"]` sidecar, not dedicated DB columns.

## Structured Payload

Current sidecar shape:

```json
{
  "escalation": {
    "approved": true,
    "reason": "Authoritative biomedical guidance is explicit; safe to auto-approve.",
    "final_route": "FAST_LANE_APPROVE",
    "in_biomedical_scope": true,
    "reason_codes": ["FASTLANE_GUIDANCE"]
  }
}
```

Current canonical route values:

- `FAST_LANE_APPROVE`
- `QUEUE_HUMAN_REVIEW`

Current canonical reason-code examples:

- `FASTLANE_CLINICAL`
- `FASTLANE_METHOD`
- `FASTLANE_GUIDANCE`
- `FASTLANE_MECHANISTIC`
- `REVIEW_STYLE_LOW_CLARITY`
- `OUT_OF_BIOMEDICAL_SCOPE`
- `MODEL_REVIEW_REQUIRED`

## Producers

Primary producer logic:

- `src/llm_provider.py`
  - normalizes reason codes
  - emits `approved`, `reason`, `final_route`, `in_biomedical_scope`, `reason_codes`

Runtime writers:

- `src/processor.py`
  - main `_step_gate()` path:
    - calls escalation only when base gate result is `PENDING_REVIEW`
    - stores sidecar in `feedback_json["escalation"]`
    - upgrades both `status` and `gate_decision` to `APPROVED` on fast-lane success
  - legacy `process_daily_slots()` path:
    - stores the same sidecar
    - also carries row-level convenience fields for note/report rendering

## Consumers

Already wired:

- `scripts/check_escalation_judge_smoke.py`
  - consumes structured fields for summary diagnostics
- `src/obsidian.py`
  - renders `Final Route`, `Biomedical Scope`, `Reason Codes`
- `backend/main.py`
  - exposes escalation metadata on `/papers` list/detail responses
  - falls back to `feedback_json["escalation"]` when dedicated row fields are absent
- `src/reporting.py`
  - summarizes route counts and top reason codes in daily reports

Support schemas:

- `src/schemas/core.py`
  - note/runtime-facing additive paper fields
- `src/schemas/papers.py`
  - API response fields for escalation metadata

## Verification Anchors

Relevant tests:

- `tests/test_escalation_structured_output.py`
- `tests/test_escalation_judge_smoke.py`
- `tests/test_processor_gate_integration.py`
- `tests/test_processor_institutional_proxy.py`
- `tests/test_papers_api.py`
- `tests/test_obsidian_institutional_block.py`
- `tests/test_reporting.py`

Useful runtime smoke:

- `python3 scripts/check_escalation_judge_smoke.py --max-mismatches 0`

## Practical Rules

- If a new runtime path writes escalation results, write the sidecar under `feedback_json["escalation"]`.
- If a new consumer wants escalation context, prefer reading the normalized API fields or the sidecar instead of inventing a second storage format.
- If a path marks a paper fast-lane approved, update both:
  - `status`
  - `gate_decision`

This keeps indexing and reconcile behavior aligned with the canonical approved path.

## Known Limitation

There are still no dedicated DB columns for:

- `escalation_final_route`
- `escalation_in_biomedical_scope`
- `escalation_reason_codes`

That is intentional for now. The sidecar is the current storage contract.

## Next Follow-up Only If Needed

Only reopen this lane if one of these becomes necessary:

1. frontend viewer needs first-class escalation badges or filters
2. analytics needs SQL-native aggregation over escalation routes/reason codes
3. a second processor path starts producing escalation decisions and needs the same sidecar contract
