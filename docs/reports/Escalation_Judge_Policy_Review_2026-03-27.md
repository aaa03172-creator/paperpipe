# Escalation Judge Policy Review 2026-03-27

Date: 2026-03-27
Status: Applied; bounded baseline aligned
Owner: Runtime maintainers

## Goal

Resolve the remaining mismatch between the current deterministic escalation gate and the historic `gate_decision` labels without widening PaperPipe's current lane definitions.

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
- fast reject for papers outside current neuroscience lanes
- fast approve only for obvious Alzheimer/MCI clinical, mechanistic neuro, or concrete neuroscience methods cases
- broad or indirect papers stay pending review

This means the remaining disagreement is not a formatting bug or model instability. It is a product-policy mismatch against older approvals.

## Case Review

| Case ID | Historic label | Current gate | Why current gate rejects | Recommended product truth | Proposed action |
| --- | --- | --- | --- | --- | --- |
| `arnstenNeuromodulationThoughtFlexibilities2012` | `APPROVED` | `approved=false` | Review-style neuroscience paper on prefrontal cortical synapses and working memory. Strongly adjacent, but not obviously a direct Alzheimer/MCI clinical, biomarker, mechanistic AD, or methods auto-approve case from metadata alone. | `pending review` by default, unless PaperPipe explicitly wants foundational neuroscience reviews auto-approved. | Relabeled to `expected_approved=false` per default recommendation. |
| `fentonAdvancesBiomaterialsDrug2018` | `APPROVED` | `approved=false` | Generic biomaterials and drug-delivery review. Cross-domain and indirect for current PaperPipe neuroscience lanes. | `pending review` | Relabeled to `expected_approved=false`. |
| `huPolyLacticAcidRecent2025` | `APPROVED` | `approved=false` | Polymer/materials engineering paper. No immediate neuroscience lane fit from metadata. | `pending review` | Relabeled to `expected_approved=false`. |
| `xiaEngineeringMacrophagesCancer2020` | `APPROVED` | `approved=false` | Oncology and cancer immunotherapy focus. Immunology is relevant in the abstract sense, but the product lane is too indirect for auto-approval. | `pending review` | Relabeled to `expected_approved=false`. |

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
- Re-opening broad materials or oncology auto-approval would likely reintroduce noisy approvals outside the current product focus.

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
  - additional AD-adjacent microbiome reviews that still stay pending review under the current narrow policy

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

- `src/llm_provider.py` had broadened the escalation lane from the intended neuroscience/Alzheimer scope to a wider biomedical scope
- the widened focus terms and prompt language started auto-approving papers such as biomaterials, oncology-adjacent, and microbiome review cases that the bounded baseline was supposed to keep pending review
- the fixture structure tests still passed, but live smoke drifted

Repair:

- kept deterministic escalation decoding
- restored the narrow PaperPipe neuroscience lane for escalation fast-reject / fast-approve / prompt logic
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
