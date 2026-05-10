# Inference Data Boundary

Status: Active operating note
Date: 2026-04-13
Owner: Runtime/security maintainers
Canonical: `docs/inference_data_boundary.md`

Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/runtime_security_env.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`

Related docs:
- `docs/inference_strategy.md`
- `docs/inference_routing_policy.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/reports/Inference_Backend_Strategy_Review_2026-04-10.md`

## Purpose

Define the smallest durable rule set for what inference payloads may stay local, may go to a lab-managed backend, or may go to an external commercial backend.

This note is for:

- payload classification before any new inference path is added
- preventing accidental over-sharing of canonical state or private research material
- making inference routing decisions auditable and reviewable

This note is not:

- a new auth system
- a replacement for `docs/runtime_security_env.md`
- a claim that every current inference path is already fully redaction-hardened

## Core Rule

Before adding or changing any inference request path, classify the payload as one of:

- `local_only`
- `lab_allowed`
- `external_allowed`

If the classification is ambiguous, default to the stricter class.

## 1. Payload classes

### 1.1 `local_only`

Definition:

- must remain inside the operator runtime
- must not be sent to a public commercial inference backend
- must not be sent to an institution server by default unless a future policy explicitly approves it

Typical examples:

- full PDF text
- raw PDF pages or images containing unpublished or sensitive content
- full note vault content
- full structured state dumps
- backend-only project memory
- execution logs and raw traces
- absolute local paths
- user action history that is not strictly required for the specific inference call
- any mixed bundle that contains more information than the task actually needs

### 1.2 `lab_allowed`

Definition:

- may leave the operator machine only for an explicitly approved institution-managed inference backend
- should not be sent to a public commercial API by default

Typical examples:

- richer excerpts from internal papers
- bounded claim/evidence bundles from private local data
- paper-local synthesis inputs that still contain institution-sensitive context
- payloads acceptable within a lab's internal trust boundary but not for public vendor routing

### 1.3 `external_allowed`

Definition:

- may be sent to a public commercial inference backend
- only in the minimum form needed for the task

Typical examples:

- title
- abstract
- selected evidence snippets
- de-identified methods excerpt
- question-specific top-k excerpt bundle
- short claim bundle
- bounded evaluator/judge prompt built from already selected evidence

Current rule:

- `external_allowed` does not mean `send the whole paper bundle`
- it means `send the minimum excerpt set required for this task`

## 2. Current safe default examples

### 2.1 Usually `local_only`

- canonical structured state as a whole object
- complete local wiki or compiled knowledge corpus
- complete meeting-pack working bundle before narrowing
- full logs, traces, or debug payloads
- filesystem-derived absolute paths

### 2.2 Usually `lab_allowed`

- private institutional paper excerpt sets
- larger internal-context prompts that a lab is comfortable keeping on internal infra only
- open-model evaluation on internal GPU hosts where the trust boundary is explicit

### 2.3 Usually `external_allowed`

- title + abstract summary prompts
- title + abstract + small methods snippet extraction prompts
- title + abstract + selected evidence span synthesis prompts
- bounded escalation/evaluator prompts that do not require full runtime state

## 3. Required minimization rules

Whenever payload is not `local_only`, apply all of the following:

- excerpt only what is needed
- prefer selected evidence spans over full document text
- prefer structured refs over full internal objects
- drop absolute local paths
- drop logs, traces, and unrelated history
- avoid sending full note or wiki bodies when selected excerpts suffice
- avoid sending full canonical state when the task can run on a bounded derivative

## 4. Required request metadata

Each new inference lane should be able to record, directly or indirectly:

- `selected_backend`
- `payload_class`
- `redaction_applied`
- request purpose or task label

Good additive extras when available:

- `token_estimate`
- source refs used to build the prompt
- whether local retrieval narrowed the payload first

This is for reviewability.

It is not permission to promote the metadata itself into canonical truth.

## 5. Privacy preflight contract

Before a runtime privacy preflight pilot is wired into any export or external-inference path, its output must follow the Pydantic contract in `src/schemas/privacy_preflight.py`.

The reserved contract is:

- `schema_version`: `privacy_preflight.v1`
- `mode`: `off`, `report_only`, or `block_on_review`
- `status`: `disabled`, `pass`, `review_required`, or `blocked`
- `rollback_flag`: `LATTICE_PRIVACY_PREFLIGHT_MODE`
- `payload_class`: `local_only`, `lab_allowed`, or `external_allowed`
- `redaction_applied`: whether the payload presented to the downstream lane was redacted
- `mutation_applied`: must remain `false` for the first pilot
- `findings`: detector, deterministic scanner, preserve-rule, or policy findings
- `manual_review`: human-review routing items
- `summary`: aggregate counts for review, false-negative risk, preserve conflicts, and unexpected predictions

Rollback rule:

- Default and rollback value is `LATTICE_PRIVACY_PREFLIGHT_MODE=off`.
- `report_only` may emit a preflight report but must not block or mutate text.
- `block_on_review` may block export or external inference when review items exist, but must not silently mutate canonical state.

Current narrow pilot:

- `backend/services/job_runner.py` wires this contract only around the `clinical_extraction` external-inference payload.
- Default mode remains `off`.
- In `report_only`, the lane records privacy preflight metadata under `run_meta.inference_lanes.clinical_extraction.privacy_preflight` and still runs the extraction.
- In `block_on_review`, only the clinical extraction sidecar is skipped when review items exist; the rest of the deep-read job may continue.
- Local filesystem paths and signed private URLs are dropped from the clinical extraction `link` field before the provider call.
- Artifact bundle read APIs expose this metadata under `inference_summary.lanes.<lane>.privacy_preflight` for review only.
- Runtime readiness exposes the current `LATTICE_PRIVACY_PREFLIGHT_MODE` validity and effective mode as `privacy_preflight_config` without echoing invalid values or payload content.

This contract is intentionally not a production enforcement default. It is a reviewable boundary for a narrow pilot.

## 6. Backend-specific rules

### 6.1 Local backend

- may access `local_only`, `lab_allowed`, and `external_allowed`
- still should minimize payload size for performance and reproducibility

### 6.2 Lab backend

- may access `lab_allowed` and `external_allowed`
- should not receive `local_only` unless a future doc explicitly approves that lane
- must be treated as a separate trust boundary, not as an invisible extension of local memory

### 6.3 Commercial backend

- may access only `external_allowed`
- must never rely on client-side vendor keys
- should be reached only through same-origin backend routing or a thin relay

## 7. Current repo implications

This note fits the current repo because:

- the runtime already distinguishes canonical state from compiled/export layers
- browser access already routes through same-origin backend paths
- backend secrets are already expected to stay out of `VITE_*`
- `/api/chat` is still stub-only, so future answer generation can adopt this boundary before any broad chat lane opens

## 8. When unsure

If there is doubt:

1. classify the payload as `local_only`
2. narrow the excerpt set further
3. prefer local retrieval and local composition first
4. escalate only the smaller derived prompt

## 9. What this note deliberately does not adopt

This note does not adopt:

- a claim that institution servers are always safe
- automatic approval of full-document external reasoning
- vendor-side storage assumptions as a substitute for minimization
- a rule that every task must support every backend
