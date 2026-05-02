# Internal Data Readiness For Biomedical Workspace (Repo-Grounded)

Date: 2026-04-13
Status: Active implementation note
Purpose: record which internal-data surfaces already exist in the repo, what they are actually good for, and which minimal new events would close the highest-value gaps without reopening runtime ownership.

Related audit:
- [check_internal_data_readiness.py](/Users/jangseongjin/paperpipe/scripts/eval/check_internal_data_readiness.py)
- [check_artifact_history_promotion_gate.py](/Users/jangseongjin/paperpipe/scripts/eval/check_artifact_history_promotion_gate.py)
- [check_artifact_history_capture_candidates.py](/Users/jangseongjin/paperpipe/scripts/eval/check_artifact_history_capture_candidates.py)
- [Artifact_History_Promotion_Posture_Decision_2026-04-14.md](/Users/jangseongjin/paperpipe/docs/reports/Artifact_History_Promotion_Posture_Decision_2026-04-14.md)

## Summary

The repo already has enough internal-data surface to start a bounded proprietary flywheel.

That claim is true only in a narrow sense:
- enough for human correction capture
- enough for screening/state-transition telemetry
- enough for project-scoped raw memory
- enough for explicit project-context relevance decisions
- enough for explicit artifact-generation outcome decisions
- enough for request/flow observability

It is not yet enough for:
- any default runtime promotion based on internal behavior alone

So the right next move is not a new workspace database or generalized session memory layer.
The right next move is to instrument a few bounded artifact families and collect enough history to justify a later promotion gate.

## 1. Project-Context Relevance

Current usable surface:
- `Project Memory` exists as backend-only raw memory under `storage/project_memory/<project_id>/`
- schema is explicitly:
  - `layer="raw_memory"`
  - `canonical_status="non_canonical"`
- linked entities can already point at papers, runs, `Research DNA`, meeting packs, chart packs, image evidence, protocol cards, and method comparisons
- `project_context_links.jsonl` now captures explicit project-to-entity relevance decisions without opening a `Project Memory` API

What this is good for now:
- storing project-local notes, judgments, uncertainties, and decisions
- bootstrapping cross-paper context gathering without promoting a second truth store
- capturing explicit project-context relevance labels that can supervise later ranking or recommendation work

What is still missing:
- a downstream consumer that turns these labels into ranking behavior
- cross-project calibration beyond the current raw-log event lane

Repo-grounded judgment:
- `Project Memory` plus `project_context_links.jsonl` are enough to start collecting explicit project-context relevance supervision
- this lane is still raw-log support data, not canonical project truth

## 2. State Transition

Current usable surface:
- `Research DNA` already writes:
  - `logs/interview.jsonl`
  - `logs/runs.jsonl`
  - `logs/screening.jsonl`
  - `logs/approval_audit.jsonl`
- run-local sidecars already capture:
  - screening progress
  - guidance follow summary
  - reason-code summaries

What this is good for now:
- measuring operator decisions over screening queues
- reconstructing bounded state transitions inside the `Research DNA` lane
- learning where recommendations were followed or ignored

What is still missing:
- a generalized cross-artifact transition event outside screening
- explicit “why this changed state” outcome labels beyond the current lane-specific reason codes

Repo-grounded judgment:
- state-transition logging is already the strongest internal-data surface in the repo
- it is good enough for bounded `Research DNA` learning loops
- it is not yet a general workspace transition ledger

## 3. Artifact Generation

Current usable surface:
- saved downstream artifact families already exist:
  - meeting packs
  - chart packs
  - image evidence
  - method comparisons
  - protocol cards
- shared artifact review feedback now persists to `storage/artifact_review_feedback.jsonl`
- shared artifact generation outcomes now persist to `storage/artifact_generation_outcomes.jsonl`

What this is good for now:
- preserving outputs and provenance
- supporting review surfaces for saved artifacts
- capturing explicit accept / reject / correct / escalate decisions against saved artifact IDs
- capturing whether saved artifacts were actually reused, reused after correction, abandoned, or escalated
- capturing those outcome labels directly from selected artifact-family routes (`meeting_pack`, `protocol_card`) instead of inferring them from reads

What is still missing:
- a runtime consumer that turns outcome history into stable default behavior
- enough bounded history to justify any promotion beyond audit and supervision collection

Repo-grounded judgment:
- artifact storage is present
- artifact review feedback is now present as an additive raw-log contract
- artifact generation outcomes are now present as an additive raw-log contract
- selected artifact emitters now exist for `meeting_pack` and `protocol_card`
- the remaining gap is no longer schema coverage, but sufficient bounded history and promotion policy

## 4. Human Correction

Current usable surface:
- `/feedback` persists `FeedbackCase` rows to `storage/feedback.jsonl`
- each row already carries:
  - `paper_id`
  - `run_id`
  - optional `original_claim_id`
  - `user_correction`
  - `accepted`
  - `timestamp`
- accepted feedback can also be indexed for later retrieval bootstrap

What this is good for now:
- claim-level correction memory
- few-shot retrieval bootstrap
- run-linked operator feedback capture

What is still missing:
- explicit correction type taxonomy
- correction events tied to project-level relevance rather than only paper/run/claim scope

Repo-grounded judgment:
- human correction capture already exists and is useful
- it is still too narrow to supervise the whole biomedical workspace

## 5. Logs Design

Current usable surface:
- request-level browser/API observability already exists via `request_audits`
- `Research DNA` carries actor-attributed screening and approval logs
- project-level raw memory has a stable backend storage contract
- saved artifacts are already file-backed and traceable

Design conclusion:
- the repo does not need a generalized conversation-memory redesign first
- the repo now has the minimum raw-log event contracts needed for the bounded biomedical workspace flywheel
- the next step is bounded collection and review, not another contract

## Conclusion

The internal-data story is no longer “missing.”

The more accurate repo-grounded conclusion is:
- raw human correction exists
- bounded state-transition telemetry exists
- raw project memory exists
- request/flow observability exists
- explicit project-context relevance labels now exist as a shared raw-log contract
- artifact review feedback now exists as a shared raw-log contract
- artifact-generation outcomes now exist as a shared raw-log contract
- runtime promotion is still not justified by contract presence alone
- the new artifact-history promotion gate should stay advisory-only until bounded `meeting_pack` and `protocol_card` history is actually collected
- `check_internal_data_readiness.py` now embeds that advisory gate, so the repo has one summary surface for both contract presence and current history blockers
- `check_internal_data_readiness.py` now also reads an explicit repo-level artifact-history promotion policy, so gate-passing history no longer implies a missing-policy ambiguity
- selected `meeting_pack` and `protocol_card` routes now expose both review and outcome emitters, so that bounded history can accumulate inside the artifact-family workflow instead of only through generic log endpoints
- selected `meeting_pack` and `protocol_card` CLI commands now expose the same bounded review/outcome writes without requiring operators to hit the API directly
- an isolated CLI-driven pilot has now shown that those bounded history thresholds can be satisfied without a new store; with the policy now present, the remaining blocker becomes the policy's intentional manual-review-only posture rather than missing history shape
- a read-only candidate audit can now point at real active-root `meeting_pack` / `protocol_card` artifacts that still need review/outcome capture, so we do not have to write synthetic history into the default roots just to find the next artifact
- that candidate audit now also distinguishes obvious verification/smoke-style `protocol_card` entries from ordinary review candidates, so operator follow-up can stay focused on reusable-looking artifacts first
- bounded active-root history has now been captured for two real `meeting_pack` artifacts and two active-root `protocol_card` drafts, so the default-root readiness summary can now reach `runtime_promotion_discussion_ready=true`
- even after that active-root capture, `runtime_promotion_ready` correctly remains `false` because the explicit repo policy is still `manual_review_only`; the remaining work is policy-governed review / RFC, not automatic default promotion
- a bounded promotion note now records the reviewed active-root samples and explicitly concludes that current history is discussion-worthy but still insufficient for any default-owner change:
  - [Artifact_History_Promotion_Note_2026-04-14.md](/Users/jangseongjin/paperpipe/docs/reports/Artifact_History_Promotion_Note_2026-04-14.md)
- the explicit RFC boundary for any future default-owner debate now exists, and it keeps the current decision conservative:
  - [Artifact_History_Default_Owner_Change_RFC_2026-04-14.md](/Users/jangseongjin/paperpipe/docs/reports/Artifact_History_Default_Owner_Change_RFC_2026-04-14.md)
- the candidate audit is now direct-CLI-safe under plain `python3` and the refreshed snapshot shows a clearer lane split:
  - real `meeting_pack` candidates remain the next useful history-capture surface
  - the small current `protocol_card` lane is still dominated by verification/smoke artifacts rather than reusable protocol artifacts

So the next proprietary flywheel move should be collecting bounded history from these contracts and defining a promotion gate, not adding a new canonical store.
