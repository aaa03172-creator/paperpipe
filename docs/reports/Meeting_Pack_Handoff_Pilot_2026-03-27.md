Status: Active bounded pilot note
Date: 2026-03-27
Owner: Lattice runtime maintainers
Purpose: record the smallest Meeting Pack pilot that borrows structured-handoff and bounded quality-gate ideas without opening a generic multi-agent harness.

## Scope

This pilot is intentionally narrow.

It adds two additive bundle-local files under `storage/meeting_packs/<pack_id>/`:
- `acceptance_contract.json`
- `quality_gate.json`

It does not:
- change the Meeting Pack API contract
- change pack readiness semantics
- add a planner/generator/evaluator runtime
- replace `meeting_pack.json`, `meeting_pack.md`, `retrieval_trace[]`, or `validate`

## Current Contract

The pilot is bounded to:
- `src/meeting_packs/service.py`
- `src/meeting_packs/store.py`

Current intent:
- make the saved pack contract more legible for operator/debug use
- compact current pack-usable signals into one additive summary
- keep `validate` as the authoritative current regenerate-availability check

## Artifact Semantics

### `acceptance_contract.json`

This file records:
- requested scope
- expected outputs
- bounded acceptance checks
- the saved operator contract for regenerate and discussion-readiness interpretation

It is not scientific truth and does not replace `meeting_pack.json`.

### `quality_gate.json`

This file records:
- compact `pass/warn/fail` checks
- whether the saved bundle is `bundle_ready`
- whether the saved bundle is `discussion_ready`
- reason codes for background-only or incomplete operator states

This file is additive bundle-local metadata only.
It does not replace `validate`, `retrieval_trace[]`, or `meeting_pack.json`.

## Current Rules

- `bundle_ready` means:
  - deterministic regenerate intent is available from a saved request or bounded deterministic fallback
  - markdown was in sync at write time
- `discussion_ready` is stricter:
  - bundle ready
  - `readiness = evidence_backed`

This lets the runtime distinguish:
- operator-usable but background-only drafts
- discussion-ready drafts
- bundles that should be treated as incomplete

without changing existing Meeting Pack truth or API semantics.

## Why this fits the repo

- It reuses the current saved pack bundle and validate lane.
- It reinforces file-based handoff over long chat memory.
- It does not reopen product scope beyond the current paper/evidence/runtime slice.
- It keeps `validate` and `retrieval_trace[]` as the authoritative operational surfaces.

## Verification

Targeted verification for this pilot:

```bash
pytest -q tests/test_meeting_pack_handoff_artifacts.py tests/test_meeting_pack_service.py tests/test_meeting_pack_store.py
python3 scripts/lint_docs.py
```

Representative runtime validation also passed:

- pack: `meetingpack_20260325T062516207912Z_journal_club_0409564f`
- action: bounded `rerender`
- result: `markdown_sync = in_sync`
- observed additive files:
  - `storage/meeting_packs/meetingpack_20260325T062516207912Z_journal_club_0409564f/acceptance_contract.json`
  - `storage/meeting_packs/meetingpack_20260325T062516207912Z_journal_club_0409564f/quality_gate.json`
- observed gate summary:
  - `overall_status = pass`
  - `bundle_ready = true`
  - `discussion_ready = true`

This confirms the pilot is not only test-backed but also emitted on the current saved-pack runtime path.

## Next Reopen Condition

Only broaden this pilot if the additive files clearly improve:
- regenerate diagnosis
- operator trust in bundle completeness
- background-only vs discussion-ready interpretation

Without that evidence, keep the pilot bounded to Meeting Pack only.
