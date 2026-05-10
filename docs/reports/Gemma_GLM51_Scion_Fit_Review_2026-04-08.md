# Gemma / GLM-5.1 / Scion Fit Review

Status: completed fit review
Date: 2026-04-08
Lane: `pp` + `tool-intake-review`

## 1. Executive summary

Current PaperPipe is already opinionated:
- local-first
- paper/job/run/artifact-first
- schema-backed canonical state
- single-operator-first
- provenance-visible and review-forward

That means the right question is not "which new framework looks strongest?"

The right question is:
- which idea strengthens the current runtime owners
- which idea can stay additive
- which idea would accidentally reopen future-only workspace/platform lanes

Current repo-grounded judgment:
- adopt now:
  - GLM-5.1's *evaluation posture*, not the model itself
- defer:
  - Gemma Multimodal Fine-Tuner as a bounded local-only multimodal eval harness
  - Scion's isolation ideas only as future inspiration for narrower sandbox hardening
- not now:
  - Gemma as a primary training/runtime lane
  - GLM-5.1 as a provider swap or `/api/chat` unlock
  - Scion as a new orchestration substrate

Why:
- the current runtime already has durable job/run/event state in `src/db_utils.py`
- current long-run diagnostics already exist in `backend/services/job_runner.py`, `src/agents/reader_agent.py`, and `src/services/deepread_handoff_artifacts.py`
- canonical truth already lives in `StructuredPaperState` and run artifacts, not chat memory or planner outputs
- current repo still explicitly blocks broad project/platform and generalized multi-agent expansion

## 2. Adopt Now / Later / Not Now

| Reference / element | Bucket | Why now | Current owner / insertion point |
| --- | --- | --- | --- |
| GLM-5.1 long-running evaluation axis | Adopt Now | Repo already has long-running job state, timeout metrics, event logs, retry/fallback traces, and compact handoff artifacts. The missing piece is better measurement of drift, recovery, and tool-step reliability. | `backend/services/job_runner.py`, `src/agents/reader_agent.py`, `src/services/deepread_handoff_artifacts.py`, `tests/test_reader_runtime_metrics.py`, `tests/test_deepread_handoff_artifacts.py` |
| Gemma multimodal local eval harness | Later | Local-first and biomedical fit are strong, but current runtime does not yet have a multimodal extraction contract or a frozen benchmark for image/audio/chart truth. | `src/schemas/image_evidence.py`, `src/image_evidence/service.py`, `docs/IMAGE_EVIDENCE.md`, `scripts/eval/`, `goldset/manifests/` |
| Scion-inspired stronger isolation for selected high-risk lanes | Later | Some ideas overlap with current sandbox and policy posture, but only narrow execution isolation is relevant. The repo does not need a hub/broker/runtime rewrite. | `src/sandbox/docker_runner.py`, `config/skills_policy.yaml`, `src/skills/policy.py` |
| GLM-5.1 as model replacement | Not Now | Current provider layer is OpenAI/Ollama/Hybrid only, `/api/chat` is still stub-only, and the current value gap is measurement, not provider breadth. | `src/llm_provider.py`, `docs/API_CHAT_CONTRACT.md` |
| Gemma fine-tuning as primary biomedical training pipeline | Not Now | No current multimodal runtime contract, no approved training lane, no benchmark proving better downstream state quality, and a real risk of creating a second unsupported model ops surface. | keep out of core runtime |
| Scion whole-platform adoption | Not Now | Conflicts with current paper-first, single-operator, non-platform boundary and duplicates job/run/event/workspace separation already present in narrower form. | keep out of core runtime |

## 3. What to adopt now

### Adopt: GLM-5.1's long-running evaluation posture

Classification: `direct candidate`

Current bottleneck:
- PaperPipe already runs long-ish multi-step work, but the main weakness is not missing orchestration.
- The weakness is incomplete measurement of:
  - goal drift across steps
  - structured-output stability
  - recovery quality after timeout or partial failure
  - tool-step reliability inside the existing run path

Repo evidence:
- persistent run/job/event state:
  - `src/db_utils.py`
  - `src/services/event_log.py`
- durable job orchestration and cancel/progress hooks:
  - `src/jobs/queue.py`
  - `src/jobs/worker.py`
  - `backend/services/job_runner.py`
- reader-attempt metrics and timeout handling:
  - `src/agents/reader_agent.py`
  - `src/timeout_policy.py`
- compact context and gate artifacts:
  - `src/services/deepread_handoff_artifacts.py`
  - `src/schemas/deepread_handoff.py`

What to add now:
1. A drift-and-recovery metric layer for deep-read runs.
2. A compact tool-step reliability summary inside `run_meta.json` and `quality_gate.json`.
3. A regression harness that scores long-run behavior across fixed papers, rather than changing the runtime model.

### Repo-specific implementation points

| Proposal | Why needed | Where to implement | Difficulty | Expected effect | Main risk |
| --- | --- | --- | --- | --- | --- |
| Add `goal_drift` metrics to deep-read handoff artifacts | Current run artifacts show attempt order and timeout, but not whether later steps drifted from requested scope or degraded into heuristic fallback. | `src/services/deepread_handoff_artifacts.py`, `src/schemas/deepread_handoff.py`, `backend/services/job_runner.py` | M | Makes "long task stayed on goal" inspectable without raw logs. | Overfitting drift rules to current deep-read only. |
| Add tool-step stability summary per run | Current run path logs progress and failures, but there is no single summary for parser/read/verify step reliability and fallback usage. | `backend/services/job_runner.py`, `src/services/event_log.py`, optional `src/schemas/ops.py` if response exposure is needed | M | Makes step failure patterns and retries comparable across runs. | Can become duplicate truth if written as a separate owner instead of a derived summary. |
| Add recovery-quality regression tests | Existing tests already cover timeout, cancel, handoff, and worker interrupt. A small scored suite can formalize recovery quality. | `tests/test_reader_runtime_metrics.py`, `tests/test_deepread_handoff_artifacts.py`, `tests/test_worker_interrupt_handling.py`, `tests/test_jobs_events_persistence.py` | S | Gives a stable bar for future provider/model changes. | Metric inflation if the score is not tied to fixed fixtures. |

## 4. What to defer

### Defer: Gemma Multimodal Fine-Tuner as a bounded local eval candidate

Classification: `defer`

Current bottleneck:
- PaperPipe does have image-adjacent and hard-document problems.
- But the repo does **not** currently have a first-class multimodal reasoning lane that owns:
  - image interpretation truth
  - audio dictation truth
  - chart screenshot extraction truth

Current owner path:
- image sidecar and lineage:
  - `src/schemas/image_evidence.py`
  - `src/image_evidence/service.py`
  - `docs/IMAGE_EVIDENCE.md`
- OCR/document hard-case evaluation:
  - `docs/reports/PaddleOCR_Fallback_Pilot_2026-04-01.md`
  - `scripts/eval/compare_ocr_backends.py`
  - `goldset/manifests/hard_pdf_eval_slice_20260401.json`

Why defer, not reject:
- local-first on Apple Silicon matches repo posture well
- biomedical examples are relevant
- the repo already prefers bounded eval harnesses before runtime adoption

Why not now:
- `Image Evidence` is explicitly metadata-first, not an image-analysis runtime
- there is no audio ingestion or multimodal structured-output contract under `src/schemas/`
- current repo policy for runtime-visible skills is allowlist-only via `config/skills_policy.yaml`
- the current OCR pilot already showed that "installable locally" is not enough; cost and fit still matter

### Safest later insertion point

Use Gemma only if reopened as:
- local-only eval harness
- frozen fixture slice
- derived sidecar outputs only
- no change to canonical runtime truth

Best later targets:
- chart/screenshot interpretation compare harness under `scripts/eval/`
- optional image-evidence derived output comparison
- narrow audio-to-structured-note compare harness only after an explicit schema exists

### Repo-specific implementation points

| Proposal | Why needed | Where to implement | Difficulty | Expected effect | Main risk |
| --- | --- | --- | --- | --- | --- |
| Freeze a multimodal benchmark manifest before any Gemma work | Prevents anecdotal adoption and keeps biomedical multimodal evaluation comparable. | `goldset/manifests/`, `docs/reports/` | S | Creates a real adoption gate. | Time spent freezing a benchmark before a concrete user pain is proven. |
| Add an eval-only image/chart sidecar comparator | Lets the team measure whether local multimodal models improve chart/image extraction without changing runtime truth. | `scripts/eval/`, `src/image_evidence/`, `src/schemas/image_evidence.py` | M | Preserves local-first experimentation while keeping product boundaries honest. | Easy to drift into image-analysis scope. |
| Define a bounded multimodal extraction schema before any runtime path | Structured outputs must exist before any model integration. | new schema under `src/schemas/` only if benchmark proves value | M | Keeps natural language secondary to structured truth. | Premature schema design if the benchmark is weak. |

### Defer: Scion ideas only as inspiration for narrower isolation

Classification: `reference only`

What is useful:
- workspace separation
- credentials minimization
- runtime execution/log separation

Why only later:
- current repo already has partial equivalents:
  - docker sandbox for constrained execution
  - policy-gated runtime skills
  - job/run/event persistence
- the actual missing problem is not "no broker exists"
- the missing problem is "selected high-risk lanes may need slightly stronger isolation semantics"

Possible future fit:
- stronger per-action sandbox metadata for approved runtime skills
- more explicit run workspace roots for eval-only helpers
- separate scratch directories for high-risk local tool execution

## 5. What not to do now

### Not now: GLM-5.1 model swap

Classification: `not now`

Do not:
- replace OpenAI/Ollama/Hybrid with GLM-5.1
- widen `/api/chat`
- treat MCP/function-calling support as immediately relevant runtime value

Why:
- `docs/API_CHAT_CONTRACT.md` keeps `/api/chat` stub-only
- `src/llm_provider.py` is still a narrow provider layer optimized around current tasks
- the repo already gets most of the relevant benefit by measuring long-run reliability on the existing runtime

### Not now: Gemma as a core training/runtime lane

Classification: `not now`

Do not:
- create a new main training pipeline
- introduce Gemma-specific runtime dependencies into core ingest/read flows
- make image or audio interpretation first-class without a schema and benchmark first

Why:
- violates smallest-safe change
- creates model ops surface area the repo does not currently own
- risks producing outputs that are not yet attached to current provenance and uncertainty contracts

### Not now: Scion wholesale adoption

Classification: `not now`

Do not:
- add hub / broker / container-per-agent orchestration
- introduce credentials/workspace routing as a new central subsystem
- rebuild current worker/job paths around a new multi-agent runtime

Why:
- current product boundary is still paper-first and single-operator-first
- `Project` and queue remain intentionally light or deferred
- current repo does not have a planner-agent platform problem
- this would duplicate `jobs`, `execution_runs`, `job_events`, artifact bundles, and existing sandbox/policy paths

## 6. Repo-specific implementation plan

### Priority 0

Add long-run evaluation metrics to the existing deep-read lane.

- why needed:
  - this is the highest-value, lowest-risk interpretation of the GLM-5.1 reference
- where:
  - `backend/services/job_runner.py`
  - `src/services/deepread_handoff_artifacts.py`
  - `src/schemas/deepread_handoff.py`
- difficulty:
  - medium
- expected effect:
  - better visibility into drift, fallback, timeout, and recovery
- risk:
  - derived metric design could become noisy if not tied to existing artifacts

### Priority 1

Add regression coverage for recovery quality and tool-step stability.

- why needed:
  - current repo already has the right tests; we should score behavior before touching providers
- where:
  - `tests/test_reader_runtime_metrics.py`
  - `tests/test_deepread_handoff_artifacts.py`
  - `tests/test_jobs_events_persistence.py`
  - `tests/test_worker_interrupt_handling.py`
- difficulty:
  - small
- expected effect:
  - future provider/model experiments gain a stable acceptance bar
- risk:
  - false confidence if fixtures are too synthetic

### Priority 2

Freeze a multimodal benchmark note and manifest for future Gemma-style evaluation.

- why needed:
  - avoids model-led scope creep
- where:
  - `docs/reports/`
  - `goldset/manifests/`
  - optional `scripts/eval/`
- difficulty:
  - small to medium
- expected effect:
  - future multimodal work becomes measurable and reversible
- risk:
  - may stay unused if no real multimodal pain reaches the bar

## 7. PR breakdown

### PR1 - Deep-read long-run metrics hardening

Scope:
- add `goal_drift` and `tool_step_stability` derived summaries to deep-read handoff artifacts
- surface recovery-relevant reason codes without changing canonical ownership

Files:
- `backend/services/job_runner.py`
- `src/services/deepread_handoff_artifacts.py`
- `src/schemas/deepread_handoff.py`
- targeted tests

Priority:
- P0

Rollback:
- stop emitting the new derived fields/artifacts
- no storage migration required

### PR2 - Long-run recovery regression suite

Scope:
- encode acceptance checks for:
  - timeout recovery
  - cancellation completion semantics
  - worker interrupt handling
  - handoff artifact integrity after failure

Files:
- `tests/test_reader_runtime_metrics.py`
- `tests/test_deepread_handoff_artifacts.py`
- `tests/test_jobs_events_persistence.py`
- `tests/test_worker_interrupt_handling.py`

Priority:
- P0

Rollback:
- remove the new assertions only; runtime stays untouched

### PR3 - Multimodal benchmark freeze

Scope:
- define the smallest biomedical multimodal fixture set worth measuring
- no runtime integration

Files:
- `docs/reports/`
- `goldset/manifests/`
- optional `scripts/eval/compare_*`

Priority:
- P1

Rollback:
- archive the manifest/note
- no runtime code rollback needed

### PR4 - Optional future Gemma eval harness

Scope:
- local-only, off-by-default comparison harness
- no change to canonical state owners

Priority:
- P2

Guardrail:
- do not open unless PR3 shows a real benchmark and a real downstream gap

## 8. Evaluation plan

These criteria should be measured inside the current runtime, not as a new platform:

| Metric | Definition | Current best owner | How to measure |
| --- | --- | --- | --- |
| Long-task goal drift | Whether later steps stay aligned with requested paper/run scope rather than degrading into unsupported fallback or unrelated output | `backend/services/job_runner.py`, `src/services/deepread_handoff_artifacts.py` | Compare requested scope, selected attempt, final return mode, fallback usage, and final claim quality |
| Tool calling stability | Whether parser/read/verify steps complete with expected outputs and bounded retries/failures | `backend/services/job_runner.py`, `src/services/event_log.py` | Per-step success/failure/retry counts and error-type summaries |
| Structured output accuracy | Whether outputs conform to schema and preserve minimum evidence requirements | `src/agents/reader_agent.py`, `src/quality/gates.py`, `src/quality/claimset_policy.py` | schema-valid claimset rate, evidence-required pass rate, gate pass/warn/fail counts |
| Provenance linkage rate | Whether outputs point back to chunks/pages/locators or explicit source refs | `src/services/reader_eval_sidecar.py`, `src/services/deepread_state_projection.py`, `src/schemas/skills.py` | bbox/text-match/approx/unresolved counts and structured-state linkage completeness |
| Failure recovery quality | Whether cancel/timeout/error paths leave inspectable artifacts and terminal states without silent corruption | `src/jobs/worker.py`, `src/services/event_log.py`, existing worker/job tests | terminal-state correctness, preserved run_meta/bootstrap_meta, post-failure handoff artifact completeness |

Recommended thresholds for a reopened provider/model experiment:
- no regression in schema-valid output rate
- no regression in provenance linkage rate
- improved or flat recovery quality
- reduced drift or better diagnosability on fixed fixtures

## 9. Final recommendation

The safest move is:
- adopt GLM-5.1's evaluation posture now
- defer Gemma into a benchmark-first local multimodal eval lane
- keep Scion as a reference, not a platform decision

PaperPipe does **not** need a new architecture to benefit from these references.

It needs one smaller thing:
- measure long-running reliability and recovery more explicitly on the runtime it already has

That is the highest-confidence path that improves:
- local-first operation
- biomedical workflow fit
- provenance and auditability
- structured-state alignment

without reopening:
- project-platform redesign
- model-serving churn
- generalized multi-agent orchestration
