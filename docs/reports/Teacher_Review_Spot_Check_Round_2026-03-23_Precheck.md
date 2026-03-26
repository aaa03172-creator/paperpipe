# Teacher Review Spot-Check Round 1 Precheck

Status: Codex precheck completed
Date: 2026-03-23
Protocol: `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Review_Spot_Check_Protocol_2026-03-23.md`
Packet: `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Review_Spot_Check_Round_2026-03-23.md`
Reviewed JSONL: `/Users/jangseongjin/paperpipe/goldset/reviews/spot_checks/teacher_review_spot_check_20260323_round1_codex_precheck.jsonl`
Focused review note: `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Review_Spot_Check_Major_Bundles_2026-03-23.md`

## Scope

This is a machine-assisted first-pass review of the prepared round-1 teacher bundles.
It is not a substitute for final human spot-check signoff.
Its purpose is to surface obvious unsupported or weakly grounded teacher claims before manual review.

## Round Metrics

- Bundle count: `6`
- Claim count: `15`
- Supported claims: `13`
- Unsupported surviving claims: `0`
- Ambiguous claims: `2`
- Supported claim precision: `1.000`
- Good location count: `10`
- Weak location count: `3`
- Misleading location count: `2`
- Agree bundles: `2`
- Minor-issue bundles: `2`
- Major-issue bundles: `2`
- Round pass under protocol thresholds: `false`

## Bundle Outcomes

- `zotero:hanssonBloodBiomarkersAlzheimers2023`: `AGREE`
- `zotero:duboisAlzheimerDiseaseClinicalBiological2024`: `MINOR_ISSUE`
  - pattern: `adjacent-quote-selection`
- `zotero:zhouGliatoNeuronConversionCRISPRCasRx2020`: `MAJOR_ISSUE`
  - pattern: `fragmentary-claim-and-misaligned-evidence`
- `zotero:chandraGutMicrobiomeAlzheimers2023`: `MINOR_ISSUE`
  - pattern: `heading-level-evidence`
- `zotero:craftSafetyEfficacyFeasibility2020`: `MAJOR_ISSUE`
  - pattern: `supported-claim-wrong-anchor`
- `zotero:chiaravallotiCognitiveImpairmentMultiple`: `AGREE`

## Main Findings

1. The most serious teacher-review problem in this round is not broad claim fabrication but mis-anchored evidence spans.
2. `zotero:craftSafetyEfficacyFeasibility2020 / CLM-001` is a supported claim with a misleading selected quote.
3. `zotero:zhouGliatoNeuronConversionCRISPRCasRx2020 / CLM-002` appears to depend on fragmentary adjacent source text and should not remain without manual rewrite.
4. `zotero:chandraGutMicrobiomeAlzheimers2023 / CLM-001` remains a broad claim with heading-level support that should be manually confirmed.
5. `zotero:duboisAlzheimerDiseaseClinicalBiological2024 / CLM-003` remains supported but uses a weaker adjacent quote than the strongest supporting sentence.

## Threshold Check

The round does not pass the current protocol thresholds.

Reasons:
- misleading location count = `2` > allowed `0`
- major-issue bundles = `2` > allowed `1`

## Recommended Next Step

1. Keep this precheck as a triage layer only.
2. Run human spot-check on the two `MAJOR_ISSUE` bundles first.
3. Treat evidence-anchor repair as the first teacher-review precision follow-up theme.
