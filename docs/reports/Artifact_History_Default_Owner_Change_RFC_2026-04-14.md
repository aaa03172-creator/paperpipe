# Artifact History Default-Owner Change RFC

Status: bounded RFC note, discussion opened explicitly, default unchanged
Date: 2026-04-14
Owner: runtime/product maintainers
Canonical parents:
- `docs/reports/Artifact_History_Promotion_Posture_Decision_2026-04-14.md`
- `docs/reports/Artifact_History_Promotion_Note_2026-04-14.md`
- `docs/reports/Internal_Data_Readiness_For_Biomedical_Workspace_2026-04-13.md`
- `docs/Lattice_v3_Master_Spec.md`

## Purpose

Record the smallest decision boundary for a possible future default-owner change tied to the bounded
`meeting_pack` / `protocol_card` artifact-history lane.

This RFC is not:

- an approval to change a runtime default
- an approval to enable automatic runtime promotion
- a reason to treat raw-log history as new canonical truth
- a reason to widen this lane beyond the selected artifact families

It is a narrow RFC that answers:

> should PaperPipe eventually allow the selected artifact-history lane to support a default-owner
> change or stronger runtime promotion posture?

## Executive Call

Safest current direction:

1. do **not** change any default owner yet
2. keep `runtime_promotion_discussion_ready=true` as a discussion signal only
3. keep `runtime_promotion_ready=false`
4. keep the active `manual_review_only` policy unchanged

## Confirmed current evidence

Current repo facts:

- bounded active-root history now exists for both required families
- the advisory artifact-history gate now passes on real active-root history
- the internal-data readiness summary now reports:
  - `runtime_promotion_discussion_ready=true`
  - `runtime_promotion_ready=false`
  - blocker: `automatic_default_promotion_not_allowed_by_policy`

Grounding artifacts:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/internal_data_readiness/internal_data_active_root_history_20260414/summary.json)
- [active_root_artifact_history_capture_20260414.json](/Users/jangseongjin/paperpipe/.codex/work/2026-04-03_public-data-strategy/active_root_artifact_history_capture_20260414.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/artifact_history_capture_candidates/artifact_history_capture_candidates_after_active_history_20260414/summary.json)

Reviewed active-root samples:

- 2 `meeting_pack` artifacts
  - both reviewed as `correct`
  - both ended as `abandoned`
- 2 `protocol_card` artifacts
  - one `correct` then `abandoned`
  - one `reject` then `abandoned`

Repo-grounded inference:

- the lane is operational
- the lane is capturing meaningful human judgment
- the current history is still narrow and mostly negative

## Why this is not adopted yet

### 1. Passing the gate is not the same as earning a default change

The current gate proves:

- selected-family history can be collected
- paired review/outcome traces can be captured in active roots
- promotion discussion can be opened without adding another store

The gate does not prove:

- downstream artifact quality is consistently reusable
- the lane should drive a stronger runtime default
- negative and verification-only samples should influence owner policy equally

### 2. Current active-root evidence is still too narrow

Current post-capture candidate audit still shows:

- `meeting_pack`: many active-root candidates still have no history
- `protocol_card`: the small visible set includes verification/smoke-style items

That matters because the current lane is still answering:

- “can we record useful bounded history?”

more than:

- “should runtime defaults trust this lane strongly enough to change ownership?”

### 3. The current reviewed samples are mostly negative

That is still useful evidence.

But it supports a conservative conclusion:

- the review lane is informative
- the lane is not yet showing positive reuse confidence
- negative history should not be misread as readiness for a stronger default

## Candidate change if later adopted

If this lane is ever promoted later, the smallest possible change would be:

1. keep the existing artifact-history policy file and gate machinery
2. revisit only the policy posture, not the raw-log contracts
3. discuss whether `manual_review_only` should remain unchanged or move to a stronger reviewed posture
4. keep any default-owner change separate from the evidence-capture implementation lane

Current expectation if reopened later:

- no new canonical store
- no implicit trust upgrade from bounded logs alone
- no widening beyond selected artifact families in the same move

## What to reject

Reject these by default:

1. changing a default owner because the gate passed once
2. treating verification/smoke artifact history as equivalent to reusable operator history
3. using mostly negative history as justification for automatic promotion
4. combining policy change with a broader runtime redesign

## Current decision

Current best judgment:

> keep the current default owner unchanged, keep artifact-history as a discussion-ready lane only,
> and require future positive reusable evidence before reopening any stronger promotion posture.

## Reopen trigger

Reopen this RFC only when one of these becomes true:

1. selected families accumulate broader real operator coverage, not just a tiny active-root sample
2. recent reviewed artifacts show positive downstream reuse rather than mainly `abandoned`
3. verification/smoke-style `protocol_card` items stop dominating the small visible protocol-card lane
4. product/runtime maintainers explicitly want to debate a policy change

Until then, this RFC should stay closed with default unchanged.
