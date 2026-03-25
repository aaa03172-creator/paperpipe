# Teacher Review Major Bundle Focused Check

Status: Codex focused review
Date: 2026-03-23
Scope: two bundles flagged as `MAJOR_ISSUE` in round-1 precheck

## zotero:zhouGliatoNeuronConversionCRISPRCasRx2020

Bundle:
- `/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch01/teacher/zotero_zhouGliatoNeuronConversionCRISPRCasRx2020`

Claim under review:
- `CLM-002`: `Besides RGCs, the loss of glial identity after MG-to-RGC conversion.`

Observed issue:
- `teacher_output.json` cites chunk `572b3730-07d1-4246-a02a-e633272ca80a`, whose quoted text only supports expression of RGC subtype markers.
- However, adjacent selected chunk `41774e47-3468-4cc8-a14e-7813cb6b36f1` contains the fragmentary source text `We also found that, besides RGCs, the loss of glial identity after MG-to-RGC conversion.`

Judgment:
- `support_label = AMBIGUOUS`
- `location_label = MISLEADING`
- `keep_teacher_claim = no`

Reason:
- The bundle appears to preserve a source fragment rather than a stable inspectable claim.
- The cited evidence span does not directly support the retained statement.
- Even though adjacent selected text hints at the intended claim, manual rewrite is needed before keeping it.

## zotero:craftSafetyEfficacyFeasibility2020

Bundle:
- `/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch02/teacher/zotero_craftSafetyEfficacyFeasibility2020`

Claim under review:
- `CLM-001`: `Intranasal insulin administration did not show efficacy in treating mild cognitive impairment and Alzheimer disease dementia.`

Observed issue:
- `teacher_output.json` cites chunk `603c7623-6bc7-493f-8b2a-606b64f37c6d`, which only contains the study aim.
- But other selected chunks in the same bundle directly support the no-benefit conclusion:
  - `5fb8375d-dcd2-4741-afd0-a24d432afecb`
  - `7015d100-48fe-47cb-8d82-a7c6cf7fd08b`
  - `4dd2d4f8-361d-4fad-86de-3c39a3adb84d`
  - `5d2ccf08-982e-4d0a-a654-e090b62dd80b`

Judgment:
- `support_label = SUPPORTED`
- `location_label = MISLEADING`
- `keep_teacher_claim = yes`

Reason:
- The surviving claim is defensible.
- The precision problem is evidence anchoring, not claim survival.
- This should be treated as a teacher-review location failure pattern, not as unsupported scientific content.

## Implication

The first teacher-review precision follow-up should emphasize:
1. wrong-anchor detection for otherwise supported claims
2. fragmentary-claim suppression before teacher output is accepted
3. stronger preference for directly supporting quotes over adjacent or heading-level text
