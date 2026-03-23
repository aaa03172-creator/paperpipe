# Teacher Review Spot-Check Protocol

Status: Open protocol
Date: 2026-03-23
Branch observed: `codex/agents-smoke-ci-check`
Scope: bounded manual review protocol only

Canonical inputs:
- `/Users/jangseongjin/paperpipe/src/quality/teacher_review.py`
- `/Users/jangseongjin/paperpipe/tests/test_teacher_review.py`
- `/Users/jangseongjin/paperpipe/docs/teacher_quality_loop.md`
- `/Users/jangseongjin/paperpipe/docs/reports/LLM_Touchpoint_Followup_Plan_2026-03-23.md`

## 0. Purpose

Define the smallest repeatable human spot-check protocol for teacher review outputs.

This protocol is meant to answer one question:
- is `teacher_review` precise enough to keep using as a benchmark-quality filtering layer?

This is not a rewrite plan.
This is not a new goldset policy.
This is a bounded operating protocol for checking agreement and surfacing repeated failure patterns.

## 1. What This Protocol Checks

Primary checks:
- supported-claim precision
- evidence location inspectability
- whether unsupported or weakly grounded claims survived the teacher filter
- whether location augmentation made outputs easier or harder to inspect

Secondary checks:
- whether `no_supported_claims` happened for a defensible reason
- whether bundle selection appears too narrow or too broad for the surviving claims

## 2. Non-Goals

Do not use this protocol to:
- relabel the whole goldset
- redesign teacher prompts
- fine-tune a model
- rewrite `teacher_review.py`
- change quarantine resolution semantics in the same step

## 3. Recommended Batch Size

Use a small repeated sample.

Default batch:
- `6` bundles per round

Why `6`:
- small enough to finish in one sitting
- large enough to catch repeated precision errors
- low enough cost to repeat after changes

## 4. Sampling Rule

Each round should include:
- `2` apparently clean accepted bundles
- `2` bundles with dense scientific wording or table-heavy context
- `2` edge bundles where support or location quality is less obvious

Use existing teacher artifacts first.
Do not regenerate outputs just to start spot-checking.

## 5. Starter Sample For First Round

Suggested first-round sample from existing artifacts:
1. `/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch01/teacher/zotero_hanssonBloodBiomarkersAlzheimers2023`
2. `/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch01/teacher/zotero_duboisAlzheimerDiseaseClinicalBiological2024`
3. `/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch01/teacher/zotero_zhouGliatoNeuronConversionCRISPRCasRx2020`
4. `/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch02/teacher/zotero_chandraGutMicrobiomeAlzheimers2023`
5. `/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch02/teacher/zotero_craftSafetyEfficacyFeasibility2020`
6. `/Users/jangseongjin/paperpipe/storage/artifacts/qualityloop_20260313_batch02/teacher/zotero_chiaravallotiCognitiveImpairmentMultiple`

Reason:
- mixes biomarker, diagnostic, intervention, microbiome, safety, and MS cognition contexts
- uses already-generated teacher bundles with full local artifact structure

## 6. Files To Open Per Bundle

For each bundle, inspect these files in order:
1. `manifest.json`
2. `prior_output.json`
3. `input_chunks.jsonl`
4. `teacher_output.json`
5. `teacher_output.meta.json`
6. `teacher_output.raw.txt`

If `teacher_output.json` does not exist and the bundle failed earlier, record that separately as generation failure, not as agreement failure.

## 7. Per-Bundle Review Checklist

Bundle-level checklist:
- Confirm `paper_id` and `doc_id` are coherent.
- Confirm `teacher_output.json` parses and contains the expected `doc_id`.
- Confirm `selected_chunk_ids` in meta look relevant to the surviving claims.
- Confirm the number of surviving claims is plausible for the bundle.
- Confirm there is no obviously unsupported claim that should have been dropped.
- Confirm there is no claim that is supported only by paraphrase without source-backed evidence text.
- Confirm evidence span location is inspectable enough to review.
- Confirm location augmentation did not create misleading confidence.

Claim-level checklist for every surviving claim:
- Read the claim statement.
- Read every evidence span in `teacher_output.json`.
- Find the matching source text in `input_chunks.jsonl`.
- Mark the claim as `SUPPORTED`, `UNSUPPORTED`, or `AMBIGUOUS`.
- Mark evidence location quality as `GOOD`, `WEAK`, or `MISLEADING`.
- Mark whether the claim should remain in teacher output if reviewed manually.

## 8. Required Review Labels

For each surviving claim, record:
- `paper_id`
- `claim_id`
- `support_label`
  - `SUPPORTED`
  - `UNSUPPORTED`
  - `AMBIGUOUS`
- `location_label`
  - `GOOD`
  - `WEAK`
  - `MISLEADING`
- `keep_teacher_claim`
  - `yes`
  - `no`
- `notes`

For each bundle, also record:
- `bundle_outcome`
  - `AGREE`
  - `MINOR_ISSUE`
  - `MAJOR_ISSUE`
- `issue_pattern`
  - free text but keep short

## 9. Agreement Rules

Use these rules consistently:
- `SUPPORTED`
  - source chunk text directly supports the teacher claim
  - evidence span text is inspectable without guesswork
- `UNSUPPORTED`
  - source text does not support the claim
  - claim should have been dropped by teacher review
- `AMBIGUOUS`
  - source relation is possible but not strong enough to keep without human judgment

Location rules:
- `GOOD`
  - chunk and page context are enough to inspect quickly
- `WEAK`
  - support may be real, but finding the exact source takes noticeable effort
- `MISLEADING`
  - location or quote gives a false sense of precision

## 10. Pass/Fail Thresholds For A Round

Treat a round as acceptable if all are true:
- `supported_claim_precision >= 0.85`
- `unsupported surviving claims <= 1`
- `misleading location count = 0`
- `major_issue bundles <= 1`

If any condition fails:
- do not propose training
- do not broaden teacher usage claims
- first document the repeated failure pattern

## 11. Output Location

Store spot-check outcomes outside canonical teacher output artifacts.

Recommended path:
- `/Users/jangseongjin/paperpipe/goldset/reviews/spot_checks/teacher_review_spot_check_YYYYMMDD.jsonl`

Recommended summary note:
- `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Review_Spot_Check_Round_YYYY-MM-DD.md`

## 12. Minimal JSONL Row Shape

Example row:
```json
{
  "reviewed_at": "2026-03-23T00:00:00Z",
  "paper_id": "zotero:testPaper2026",
  "bundle_dir": "...",
  "claim_id": "CLM-001",
  "support_label": "SUPPORTED",
  "location_label": "GOOD",
  "keep_teacher_claim": true,
  "bundle_outcome": "AGREE",
  "issue_pattern": "",
  "reviewer": "human",
  "notes": ""
}
```

## 13. What To Compute After Each Round

Round summary metrics:
- `bundle_count`
- `claim_count`
- `supported_claim_precision`
- `unsupported_surviving_claim_count`
- `ambiguous_claim_count`
- `good_location_rate`
- `weak_location_rate`
- `misleading_location_count`
- `major_issue_bundle_count`
- `no_supported_claims_bundle_count`

## 14. Escalation Rules

Escalate immediately if either happens:
- the same unsupported claim pattern appears in `2+` bundles in one round
- any teacher output gives a misleading location that would likely fool a downstream reviewer

If escalation happens:
- log the pattern
- keep the protocol going
- do not jump straight to prompt or model changes without at least one repeated pattern

## 15. Safest Immediate Use

Use this protocol after:
- reader sidecar replay batches
- stats fallback taxonomy batches
- before any teacher-review training discussion

Current recommended next step:
1. run the first `6`-bundle spot-check round using the starter sample above
2. write one round summary note
3. only then decide whether teacher review needs prompt work, logging work, or no change
