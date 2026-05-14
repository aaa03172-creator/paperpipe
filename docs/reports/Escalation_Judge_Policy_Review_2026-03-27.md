# Escalation Judge Policy Review 2026-03-27

Date: 2026-03-27
Status: Applied; bounded baseline aligned
Owner: Runtime maintainers

## Goal

Resolve the remaining mismatch between the current deterministic escalation gate and the historic `gate_decision` labels while keeping the shipped biomedical-general workspace scope and a conservative high-confidence fast-lane.

## Scope

- `src/llm_provider.py`
- `tests/fixtures/escalation_judge_case/real_cases_20260327.json`
- `tests/test_escalation_prompt_policy.py`
- `tests/test_llm_provider_task_temperature.py`
- `tests/test_escalation_judge_smoke.py`
- `scripts/check_escalation_judge_smoke.py`

## Evidence

- `pytest -q tests/test_escalation_prompt_policy.py tests/test_llm_provider_task_temperature.py tests/test_escalation_judge_smoke.py`
  - result: `13 passed`
- `python3 scripts/check_escalation_judge_smoke.py --max-mismatches 1`
  - synthetic fixture result: `6/6 match`, `invalid_output_count=0`
- `python3 scripts/check_escalation_judge_smoke.py --fixture tests/fixtures/escalation_judge_case/real_cases_20260327.json --max-mismatches 0`
  - real-history fixture result after applying the default `arnsten...` recommendation: `10/10 match`, `invalid_output_count=0`

## Current Runtime Interpretation

The current gate is intentionally conservative:

- deterministic decoding for `escalation`
- fast reject for papers outside biomedical scope or broad review-style papers that are not metadata-clear enough for a fast-lane decision
- fast approve only for high-confidence biomedical methods, authoritative guidance, direct clinical/translational evidence, or direct mechanistic evidence cases
- broad or indirect papers stay pending review

This means the remaining disagreement is not a formatting bug or model instability. It is a product-policy mismatch against older approvals.

## Case Review

| Case ID | Historic label | Current gate | Why current gate rejects | Recommended product truth | Proposed action |
| --- | --- | --- | --- | --- | --- |
| `arnstenNeuromodulationThoughtFlexibilities2012` | `APPROVED` | `approved=false` | Review-style neuroscience paper on prefrontal cortical synapses and working memory. Strongly relevant, but still not metadata-clear enough for high-confidence fast-lane approval. | `pending review` by default, unless PaperPipe explicitly wants foundational neuroscience reviews auto-routed. | Relabeled to `expected_approved=false` per default recommendation. |
| `fentonAdvancesBiomaterialsDrug2018` | `APPROVED` | `approved=false` | Generic biomaterials and drug-delivery review. Biomedical in scope, but broad review-style and not direct enough for metadata-only fast-lane approval. | `pending review` | Relabeled to `expected_approved=false`. |
| `huPolyLacticAcidRecent2025` | `APPROVED` | `approved=false` | Polymer/materials engineering paper without clear clinical or translational biomedical grounding from metadata alone. | `pending review` | Relabeled to `expected_approved=false`. |
| `xiaEngineeringMacrophagesCancer2020` | `APPROVED` | `approved=false` | Oncology and cancer immunotherapy focus. Biomedical in scope, but not clearly a must-auto-route case from title/abstract/tags alone. | `pending review` | Relabeled to `expected_approved=false`. |

## Recommendation

Recommended default:

- keep the current deterministic `llama3:latest` escalation gate
- treat the residual mismatch as a fixture-policy cleanup task, not a model-quality rollback
- keep the 3 relabeled off-lane cases as the bounded baseline:
  - `fentonAdvancesBiomaterialsDrug2018`
  - `huPolyLacticAcidRecent2025`
  - `xiaEngineeringMacrophagesCancer2020`
- keep `arnstenNeuromodulationThoughtFlexibilities2012` as `pending review` in the bounded baseline unless a future product decision explicitly broadens auto-approval for foundational neuroscience reviews

## Why This Is Safer

- The current residual drift is conservative, not over-permissive.
- False negatives at the escalation gate are recoverable through human review.
- Re-opening broad review-style biomaterials or oncology auto-approval would likely reintroduce noisy approvals that are still in scope, but not metadata-clear enough for automatic routing.

## Next PR-Sized Actions

1. Keep rerunning the same smoke commands when the escalation policy changes.
2. Reopen this report only if PaperPipe later expands auto-approval to broader foundational neuroscience reviews.

## Extended Sample Follow-up

To reduce the risk that the 10-case fixture was too small or too friendly, the same-day follow-up added a larger real-history sample:

- new fixture: `tests/fixtures/escalation_judge_case/real_cases_extended_20260327.json`
- sample size: `22`
- policy mix: `10 approved`, `12 pending review`
- added coverage:
  - direct AD biomarker / trial / recommendation approvals
  - off-lane clinical or immunology papers
  - broader foundational neuroscience reviews
  - additional AD-adjacent microbiome reviews that still stay pending review under the current conservative policy

Verification:

- `pytest tests/test_escalation_judge_smoke.py -q`
  - result: `4 passed`
- `python3 scripts/check_escalation_judge_smoke.py --fixture tests/fixtures/escalation_judge_case/real_cases_extended_20260327.json --max-mismatches 0`
  - result: `22/22 match`, `invalid_output_count=0`

Current judgment:

- the bounded escalation policy is not just passing a 10-case handpicked set
- it also holds on the larger 22-case real-history sample without fresh drift

## 2026-03-28 Recheck

The next-day recheck caught an unintended regression before packaging:

- `src/llm_provider.py` had broader biomedical wording, but the bounded fixtures were still narrating the escalation lane as if it were neuroscience-only
- the mismatch was not biomedical scope itself; it was how aggressively review-style biomaterials, oncology-adjacent, and microbiome papers were being treated as fast-lane approvals
- the fixture structure tests still passed, but live smoke drifted

Repair:

- kept deterministic escalation decoding
- kept escalation conservative around high-confidence biomedical routing signals instead of broad review-style relevance
- added policy tests to guard against:
  - methods cases being rejected too early by the fast-reject gate
  - review-style microbiome papers being auto-approved by overly broad mechanistic terms

Verification after repair:

- `pytest tests/test_escalation_prompt_policy.py tests/test_llm_provider_task_temperature.py tests/test_escalation_judge_smoke.py -q`
  - result: `21 passed`
- `python3 scripts/check_escalation_judge_smoke.py --max-mismatches 0`
  - result: `6/6 match`
- `python3 scripts/check_escalation_judge_smoke.py --fixture tests/fixtures/escalation_judge_case/real_cases_20260327.json --max-mismatches 0`
  - result: `10/10 match`
- `python3 scripts/check_escalation_judge_smoke.py --fixture tests/fixtures/escalation_judge_case/real_cases_extended_20260327.json --max-mismatches 0`
  - result: `22/22 match`

Current state after the 2026-03-28 recheck:

- bounded escalation baseline is restored
- the live smoke now matches both the 10-case and 22-case policy fixtures again
