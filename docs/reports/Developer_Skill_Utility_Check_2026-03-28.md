# Developer Skill Utility Check

Status: Active review note
Date: 2026-03-28
Owner: Skills maintainers

## Scope

This note records whether the newly added developer-only skill scaffolds were actually useful on real repo work.

Reviewed skills:
- `.codex/skills/meeting-pack-verifier/`
- `.codex/skills/chart-figure-hardening/`

## 1. `meeting-pack-verifier`

### Review target
- representative saved bundle:
  - `storage/meeting_packs/meetingpack_20260325T062516207912Z_journal_club_0409564f/meeting_pack.json`
  - `storage/meeting_packs/meetingpack_20260325T062516207912Z_journal_club_0409564f/acceptance_contract.json`
  - `storage/meeting_packs/meetingpack_20260325T062516207912Z_journal_club_0409564f/quality_gate.json`

### Utility judgment
- high utility

### Why it helped
- the skill matched the current contract in `docs/MEETING_PACK.md`
- the output contract was concrete enough to review:
  - bundle status
  - canonical input ownership
  - trace/regenerateability signals
  - smallest follow-up
- additive handoff artifacts made the review cleaner rather than noisier

### What was directly confirmed
- representative bundle exists
- `meeting_pack.json` is the primary bundle-local manifest
- additive `acceptance_contract.json` and `quality_gate.json` align with current saved pack semantics
- targeted API coverage exists for `trace`, `validate`, `markdown_sync`, and regenerateability in:
  - `tests/test_meeting_packs_api.py`

### Conclusion
- keep this skill as-is
- it is immediately useful for bounded runtime diagnosis and review

## 2. `chart-figure-hardening`

### Review target
- active specs:
  - `docs/CHART_PACK.md`
  - `docs/IMAGE_EVIDENCE.md`
  - `docs/METHOD_COMPARISON.md`
- fixture-backed or targeted-test-generated lanes:
  - `tests/test_chart_packs_api.py`
  - `tests/test_image_evidence_fixture_hardening.py`
  - frontend backend E2E generation paths in `frontend/e2e/backend.spec.ts`

### Utility judgment
- medium utility

### Why it helped
- it gave a clean truth-ownership checklist across multiple bounded artifact lanes
- it focused the review on:
  - source/canonical/derived separation
  - warning visibility
  - bundle-local manifest identity

### What limited it
- there is currently no representative live saved artifact under:
  - `storage/chart_packs/`
  - `storage/image_evidence/`
  - `storage/method_comparisons/`
- that means the first real use was fixture-backed rather than live-runtime-backed

### Adjustment made
- the skill now explicitly allows fixture-backed review when no representative live bundle exists

### Conclusion
- keep this skill
- treat it as best for bounded artifact-lane hardening, especially when combined with targeted pytest or backend E2E generation

## 3. Recommendation

Current judgment:
- keep both new developer-only skills
- do not add more scaffolds immediately
- use these two in actual review/hardening work before expanding the skill inventory

Next reasonable trigger for another scaffold:
- only after a repeated workflow gap appears that is not already covered by:
  - `meeting-pack-verifier`
  - `chart-figure-hardening`
  - `smallest-safe-patch`
  - `tool-intake-review`

## Verification

Ran:
- `pytest -q tests/test_meeting_packs_api.py -q`
- `pytest -q tests/test_chart_packs_api.py tests/test_image_evidence_fixture_hardening.py -q`
