# Inference Routing Policy

Status: Active operating note
Date: 2026-04-13
Owner: Runtime maintainers
Canonical: `docs/inference_routing_policy.md`

Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/inference_strategy.md`
- `docs/inference_data_boundary.md`

Related docs:
- `docs/runtime_security_env.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/reports/Inference_Backend_Strategy_Review_2026-04-10.md`

## Purpose

Define the smallest current task-to-backend routing policy that fits the repo today.

This note is for:

- current and near-term inference lanes
- backend preference order
- payload-class expectations per task family

This note is not:

- a guarantee that every task already has every backend implemented
- a promise of a broad user-facing backend selector
- a replacement for model-specific config

## 1. Current recommendation

Use a policy that is effectively:

- local retrieval first
- local data ownership always
- local model when the task is lightweight or the environment is provisioned
- commercial inference for difficult reasoning and evaluator/judge lanes
- lab server as an optional middle slot

## 2. Routing table

| Task family | Current repo anchor | Preferred backend | Allowed fallback | Payload class |
| --- | --- | --- | --- | --- |
| embeddings | `get_embedding()` | local | lab, then commercial if explicitly allowed | `external_allowed` or stricter depending on source |
| slot classification | `classify_slot()` | local | commercial | `external_allowed` when built from title/abstract/tags only |
| paper tagging | `tag_paper()` | local | commercial | `external_allowed` when built from title/abstract/tags only |
| one-liner generation | `generate_one_liner()` | local | commercial | `external_allowed` |
| biomedical clinical extraction | `extract_biomedical_clinical_data()` | local | commercial | `external_allowed` when limited to title/abstract/methods excerpt |
| specialty trial extraction | `extract_specialty_trial_data()` | local | commercial | `external_allowed` only after minimization |
| deep-read generation | `generate_deep_read()` | commercial for average-hardware distribution, local when operator machine is provisioned | local or lab depending on deployment | usually `external_allowed` if prompt is title/abstract based; stricter if widened |
| relevance analysis | `analyze_relevance()` | commercial for difficult synthesis | local when operator machine is provisioned | `external_allowed` with bounded excerpts |
| escalation judge | `evaluate_escalation()` | commercial | local | `external_allowed` |
| future bounded answer composition | future `/api/chat` or lane-specific answer path | commercial | local or lab | start from `external_allowed`; escalate to stricter class if the prompt widens |

## 3. Important clarifications

### 3.1 "Preferred backend" is not "required backend"

Preferred backend means:

- the default operator-facing recommendation
- the backend that best matches average-hardware distribution and current risk posture

It does not mean:

- every runtime must have that backend configured
- every task must fail if that backend is unavailable

### 3.2 "Commercial for deep-read" is a deployment recommendation, not a canonical-state change

If deep-read or relevance synthesis is routed to commercial inference:

- canonical state still stays local
- retrieval still stays local first
- prompt construction still must obey `docs/inference_data_boundary.md`

### 3.3 Local backend remains important

Local backend is still strategically important for:

- offline fallback
- privacy-sensitive runs
- power users with stronger hardware
- institution-free deployments

The routing policy simply avoids making that path the required baseline for every operator machine.

## 4. Current chat boundary

Current `/api/chat` remains stub-only.

So this policy does not reopen a broad live chat lane.

If a future bounded answer path is implemented, it should:

- route through evidence-linked state first
- follow payload classification first
- prefer smaller derived prompts over full-state dumps
- keep memory-like layers subordinate to canonical evidence-linked state

## 5. Deployment interpretations

### 5.1 Average-hardware personal runtime

Recommended:

- local retrieval/index/state
- commercial inference enabled
- local model optional

### 5.2 Power-user local runtime

Recommended:

- local retrieval/index/state
- local model enabled for more lanes
- commercial inference optional for hardest reasoning only

### 5.3 Institution runtime with lab server

Recommended:

- local retrieval/index/state
- lab server preferred for approved `lab_allowed` and `external_allowed` tasks
- commercial fallback optional

## 6. Required review questions for any new lane

Before adding a new inference lane, answer:

1. What is the payload class?
2. Can local retrieval narrow it further first?
3. Is local backend actually required, or only desirable?
4. Would average-hardware operators still succeed if local inference is slow or unavailable?
5. Does the lane risk treating compiled knowledge or raw memory as stronger truth than canonical evidence-linked state?

## 7. What this note deliberately does not adopt

This note does not adopt:

- a product promise that every backend is equally supported everywhere
- a universal automatic backend selector across all future lanes
- a broad inference orchestration framework detached from current paper/job/artifact scope
