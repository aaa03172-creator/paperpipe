# Teacher Review Pre-Accept Suppression Replay

Status: Guardrail replay completed
Date: 2026-03-24
Branch observed: `codex/agents-smoke-ci-check`
Scope: bounded verifier replay only

## Purpose

Confirm that the new pre-accept suppression rule in `/Users/jangseongjin/paperpipe/scripts/verify_teacher_output.py`
quarantines the two currently known blocking anchor-quality patterns without widening scope.

Current blocking labels:
- `FRAGMENTARY_CLAIM`
- `MISALIGNED_QUOTE`

Current warning-only labels:
- `ADJACENT_SUPPORT`
- `HEADING_LEVEL_SUPPORT`

## Replay Set

1. `zotero:zhouGliatoNeuronConversionCRISPRCasRx2020`
2. `zotero:craftSafetyEfficacyFeasibility2020`
3. `zotero:hanssonBloodBiomarkersAlzheimers2023`

## Results

### zotero:zhouGliatoNeuronConversionCRISPRCasRx2020
- `accepted=false`
- target dir: `quarantine`
- reason codes:
  - `TEACHER_REVIEW_FRAGMENTARY_CLAIM`
- blocking anchor labels:
  - `FRAGMENTARY_CLAIM`

### zotero:craftSafetyEfficacyFeasibility2020
- `accepted=false`
- target dir: `quarantine`
- reason codes:
  - `TEACHER_REVIEW_MISALIGNED_QUOTE`
- blocking anchor labels:
  - `MISALIGNED_QUOTE`

### zotero:hanssonBloodBiomarkersAlzheimers2023
- `accepted=true`
- target dir: `accepted`
- reason codes: `[]`
- blocking anchor labels: `[]`

## Current Judgment

The new guardrail is aligned with the replay evidence.

It does not behave like a broad teacher-review rejection rule.
It suppresses only the two highest-risk anchor-quality failures that were already isolated in the replay taxonomy:
- fragmentary surviving claim
- supported claim with non-supporting selected quote

This keeps the current lane narrow:
- no prompt rewrite
- no bundle generation rewrite
- no parser/storage/orchestrator changes
- no escalation of `ADJACENT_SUPPORT` or `HEADING_LEVEL_SUPPORT`

## Recommendation

Treat this guardrail as the current stopping point for the teacher-review lane.

If the lane is resumed later, the next bounded decision is whether
`ADJACENT_SUPPORT` and `HEADING_LEVEL_SUPPORT` should remain warning-only or move to stronger review handling.
