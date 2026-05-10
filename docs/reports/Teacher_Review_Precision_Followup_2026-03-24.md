# Teacher Review Precision Follow-up

Status: Guardrail follow-up in progress
Date: 2026-03-24
Branch observed: `codex/agents-smoke-ci-check`
Scope: additive validation and guardrails only

Canonical inputs:
- `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Review_Spot_Check_Protocol_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Review_Spot_Check_Round_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Review_Spot_Check_Round_2026-03-23_Precheck.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Review_Spot_Check_Major_Bundles_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/src/quality/teacher_review.py`

## 0. Purpose

Convert the round-1 teacher review spot-check into a bounded follow-up plan.

This note does not propose a rewrite.
This note does not broaden teacher-review scope.
It records what the first spot-check actually found and what should be fixed or measured next.

## 1. Current Judgment

The first round does not show a broad teacher-review collapse.
It shows a narrower precision problem.

Primary issue class:
- mis-anchored evidence spans

Secondary issue classes:
- fragmentary claim survival
- heading-level evidence retention
- adjacent-quote selection instead of the strongest supporting sentence

Important interpretation:
- the current teacher-review weakness is not mainly fabricated scientific content
- it is mainly weak claim packaging and weak evidence anchoring

## 2. Round-1 Findings That Matter

Observed round metrics:
- bundle count: `6`
- claim count: `15`
- supported claims: `13`
- ambiguous claims: `2`
- unsupported surviving claims: `0`
- misleading location count: `2`
- major-issue bundles: `2`

Critical examples:
1. `zotero:craftSafetyEfficacyFeasibility2020 / CLM-001`
- claim is defensible
- selected quote is not
- the bundle contains stronger supporting chunks, but teacher output points to the study aim text instead

2. `zotero:zhouGliatoNeuronConversionCRISPRCasRx2020 / CLM-002`
- the cited evidence span does not directly support the retained claim
- adjacent selected text contains fragmentary support language
- this should not remain as a stable teacher claim without manual rewrite

3. `zotero:chandraGutMicrobiomeAlzheimers2023 / CLM-001`
- broad claim survives with heading-level support only
- not obviously false, but not precise enough for benchmark-style trust

4. `zotero:duboisAlzheimerDiseaseClinicalBiological2024 / CLM-003`
- claim is supported
- chosen quote is weaker than the most directly supporting sentence in the selected chunk set

## 3. Non-Goals

Do not do these in this follow-up:
- rewrite `teacher_review.py`
- retune the model first
- change bundle generation semantics in the same step
- redefine quarantine or acceptance policy globally
- replace teacher output schema wholesale
- treat this as a parser problem first

## 4. Precision Failure Taxonomy

### P0: Must measure or gate now
- wrong-anchor supported claim
  - claim is supportable from selected material
  - cited quote/span is misleading or non-supporting
- fragmentary claim survival
  - retained statement is not a stable inspectable claim even if adjacent text hints at the intended meaning

### P1: Next batch
- heading-level evidence retention
  - quote is a section title or topic label rather than supporting text
- adjacent-quote selection
  - location is near the support but not the strongest supporting sentence

### P2: Later
- over-broad review claims in narrative papers
- mixed-support bundles where one claim is acceptable only after heavy human interpretation

## 5. What To Measure Next

Additive metrics to introduce before any prompt or model change:
- `direct_support_quote_rate`
  - fraction of surviving claims whose selected quote directly supports the claim statement
- `wrong_anchor_supported_claim_rate`
  - fraction of claims where support exists in selected chunks but not in the cited quote/span
- `fragmentary_claim_rate`
  - fraction of surviving claims that are not stable standalone statements
- `heading_level_quote_rate`
  - fraction of claims citing only headings/titles/topic labels
- `claim_keep_reversal_rate`
  - fraction of surviving claims the reviewer would drop
- `misleading_location_rate`
  - fraction of claims whose location gives false confidence

## 6. Safest Additive Improvements

### Workstream A
- add teacher-review evaluation sidecar
- keep it separate from canonical `teacher_output.json`
- record per-claim:
  - `support_label`
  - `location_label`
  - `keep_teacher_claim`
  - `issue_pattern`
  - `review_source`

### Workstream B
- add anchor-quality flags for teacher claims
- possible bounded flags:
  - `DIRECT_QUOTE_SUPPORT`
  - `ADJACENT_SUPPORT`
  - `HEADING_LEVEL_SUPPORT`
  - `MISALIGNED_QUOTE`
  - `FRAGMENTARY_CLAIM`

### Workstream C
- add pre-accept suppression rules for the worst cases
- first candidate rules:
  - suppress fragmentary claims before teacher output is accepted
  - flag non-supporting quote selection for review
  - prefer directly supporting quote text when available in selected chunks

Current implementation status:
- `teacher_review_eval.json` is now usable by `/Users/jangseongjin/paperpipe/scripts/verify_teacher_output.py`
- current blocking labels:
  - `FRAGMENTARY_CLAIM`
  - `MISALIGNED_QUOTE`
- current warning-only labels:
  - `ADJACENT_SUPPORT`
  - `HEADING_LEVEL_SUPPORT`

## 7. Acceptance Criteria For The Follow-up

Treat the next follow-up as successful only if all are true:
- the system can distinguish claim-validity failures from anchor-quality failures
- the follow-up produces a stable sidecar or audit artifact
- the two current major bundles can be bucketed without manual log spelunking
- at least one bad pattern can be flagged automatically without changing core teacher bundle semantics

## 8. Immediate PR-Sized Actions

1. Add a `teacher_review_eval` sidecar for manual and machine-assisted spot-check outcomes.
2. Add a narrow anchor-quality classifier for `DIRECT_QUOTE_SUPPORT` vs `MISALIGNED_QUOTE` vs `HEADING_LEVEL_SUPPORT` vs `FRAGMENTARY_CLAIM`.
3. Re-run the two major bundles plus one clean control bundle and confirm that the new taxonomy matches the focused review note.

Current replay entrypoint:
- `/Users/jangseongjin/paperpipe/scripts/build_teacher_review_eval.py`

## 9. Recommendation

The next teacher-review work should target evidence-anchor precision, not broad model retraining.

If this lane is resumed, start with:
1. sidecar
2. anchor-quality taxonomy
3. replay on the two major bundles

Do not start with prompt rewrite or model tuning.
