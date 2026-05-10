Status: Active fit review note
Date: 2026-03-27
Owner: Lattice runtime maintainers
Purpose: evaluate whether Anthropic-style harness design principles for long-running agentic work are worth adopting in the current Lattice repo, without reopening product shape or introducing a heavy autonomous app-builder framework.

Reference reviewed:
- [Anthropic: Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)

# 1. Current repo long-running workflow summary

- Current repo long-running structure is real, but it is not a generic multi-agent harness.
- The strongest long-running runtime lane is the deep-read job path in `backend/services/job_runner.py`.
- The current system already persists multi-step state in structured artifacts and append-only logs rather than relying on chat memory:
  - `jobs`, `execution_runs`, `job_events`, `user_actions` in `src/db_utils.py`
  - per-run artifact bundles with `run_meta.json` and `bootstrap_meta.json` in `backend/services/job_runner.py`
  - note-side canonical state promotion into `.pp/<slug>/state.json` in `src/services/deepread_state_projection.py`
  - append-only interview, run, screening, and approval logs in `Research DNA` via `src/profiles/research_dna_service.py` and `docs/RESEARCH_DNA.md`
  - saved request, retrieval trace, validate/regenerate/rerender metadata in `Meeting Pack` via `src/meeting_packs/service.py` and `docs/MEETING_PACK.md`
- Current chat/session dependence is intentionally weak:
  - `/api/chat` is still stub-only in `docs/API_CHAT_CONTRACT.md`
  - active product truth stays in schema-backed structured state, as fixed in `docs/Product_Positioning_Principles.md` and `docs/Lattice_v3_Master_Spec.md`
- Current role separation already exists in bounded form:
  - generator-like lanes: `ReaderAgent` and `Meeting Pack` generation
  - verifier/evaluator-like lanes: `StatsVerificationAgent`, `reader_eval` sidecar, `GateEngine`, teacher-review verification, and `Meeting Pack` validate
  - there is not currently a real planner agent; the closest current equivalent is operator-defined or operator-refined intent captured through bounded state such as `Research DNA` and saved generation requests
- The current long-running stack clearly does:
  - decompose work into persisted steps
  - record progress and artifacts
  - support bounded retry/cancel/status visibility
  - preserve provenance and review metadata
- The current stack is weaker at:
  - explicit cross-step handoff contracts between substeps
  - one shared done-definition artifact for complex runs
  - one shared quality-gate summary across heterogeneous lanes
  - generic checkpoint/resume beyond the current persisted artifact and rerun model
- Structural risks that plausibly exist today:
  - handoff failure between artifact generation and promotion can happen if step assumptions drift; this risk is reduced, but not abstracted into a generic contract
  - self-evaluation bias still exists inside bounded loops such as `StatsVerificationAgent` reflection/retry, because generation and reflection are inside one agent graph
  - retry instability is plausible in long LLM-heavy steps where the runtime currently depends on step-local prompts and artifact files rather than explicit inter-step contracts
  - context drift is less severe than in chat-first systems because current truth is file/state-backed, not session-backed
- Not confirmed:
  - a current user-facing workflow that depends on multi-hour autonomous agent handoff between multiple independent agent processes
  - a current product requirement for generalized planner -> generator -> evaluator orchestration across the whole workspace

# 2. Fit assessment for Anthropic harness principles

## 2.1 Strong fit

- Structured handoff artifacts fit the repo well.
  - The current system already prefers file/state-backed transfer over chat-memory continuity: `run_meta.json`, `bootstrap_meta.json`, `reader_eval.json`, `state.json`, `generation_request`, `retrieval_trace[]`, and `Research DNA` append-only logs all point in this direction.
  - This matches the Anthropic article's emphasis on file/artifact handoff and clean state transfer between sessions rather than long chat continuity.
- Separate verifier/review gates fit the repo well.
  - Biomedical workflows benefit from skeptical post-generation checks more than from self-congratulatory single-agent loops.
  - Current examples already exist:
    - `StatsVerificationAgent` in `src/agents/stats_agent.py`
    - `GateEngine` in `src/quality/gates.py`
    - teacher-review routing in `scripts/verify_teacher_output.py`
    - `Meeting Pack` validate/regenerate boundaries in `src/meeting_packs/service.py`
- Gradable criteria fit bounded biomedical tasks.
  - Claim extraction, evidence linkage, screening outcomes, meeting-pack readiness, and search evaluation already have or can support concrete pass/warn/fail criteria better than open-ended chat judgment.
  - `Research DNA` already treats evaluation as a bounded fixed harness with append-only artifacts and comparable metrics.
- Context reset is less important than context externalization.
  - The core useful idea is not "reset chat because Anthropic did it"; it is "persist the work in structured artifacts so no single session owns the truth."
  - Lattice already aligns with that.

## 2.2 Partial fit

- Planner / generator / evaluator separation is only partially needed.
  - A generic planner agent is not obviously needed because current product intent is already expected to come from operator inputs, saved selectors, and `Research DNA`, not from prompt-to-spec expansion.
  - A bounded verifier/evaluator separation is more useful than a full three-agent harness.
- Sprint contract / done-definition is partially useful.
  - It does not fit as a product-wide runtime layer right now.
  - It does fit as bounded work metadata for:
    - deep-read verification
    - protocol extraction review
    - meeting-pack generation acceptance
    - search-eval / screening slices
- Context reset plus handoff can help selected long tasks, but current repo is not primarily chat-session-driven.
  - If adopted, it should be implemented as file/JSON handoff between persisted run steps, not as a generalized multi-agent conversation framework.
- Evaluator scoring rubrics are useful where the task already has bounded truth contracts.
  - Good candidates: claim support quality, evidence-location coverage, verification completeness, meeting-pack readiness, protocol field extraction quality.
  - Poor candidates: broad project synthesis without canonical structured anchors.

## 2.3 Mismatch / risk

- A full Anthropic-style harness would conflict with current product identity.
  - The Anthropic article is about long-running autonomous application building.
  - Lattice is a paper-centered biomedical research workspace, not an autonomous app-builder harness.
- Planner-first generation from a short prompt is a mismatch.
  - Current product intentionally keeps canonical truth in structured runtime state, not in speculative spec files generated from one sentence.
  - A planner agent that expands vague prompts into major workspace plans would risk reopening the future-only `Project` and platform lanes.
- Heavy multi-agent orchestration is likely too expensive and operationally heavy right now.
  - The Anthropic article explicitly reports multi-hour runs and large cost increase.
  - Current Lattice value is concentrated in bounded evidence workflows, where much smaller verifier-side improvements are likely cheaper and safer.
- A generic evaluator loop can become redundant or misleading.
  - Current repo already has several bounded validators and review artifacts.
  - Adding one umbrella evaluator agent on top of everything could duplicate existing contracts and blur ownership.
- Artifact fan-out risk is real.
  - Current repo already has many artifact families.
  - New planner/generator/evaluator layers that produce their own parallel handoff files can easily create second-truth drift unless tightly scoped.

# 3. Adoption recommendation

- Primary recommendation: some principles are worth adopting now.
- Secondary recommendation: limited pilot value is high for specific workflows only.
- Not recommended: full planner/generator/evaluator harness adoption as a product-wide framework.

Judgment:
- Do not adopt the Anthropic harness wholesale.
- Do adopt selected design principles where they reinforce the current paper/job/artifact runtime:
  - structured handoff artifacts
  - explicit done-definition metadata
  - skeptical verifier gates
  - gradable acceptance criteria for bounded outputs

Why:
- These principles match current repo reality in `jobs/runs/events/artifacts`, `Research DNA`, `Meeting Pack`, and existing quality gates.
- They improve reliability without changing product shape.
- They reinforce local-first, structured-state, provenance-first behavior instead of replacing it.

Why not full adoption:
- Full harness adoption would over-center autonomous orchestration and speculative planning.
- It would add token, latency, orchestration, and maintenance cost before the current product has proven that such complexity is load-bearing.
- It would likely pull the system toward a generalized agent framework rather than a biomedical workspace.

Preconditions before any wider adoption:
- keep all new handoff artifacts explicitly subordinate to existing canonical owners
- do not introduce a new top-level truth root for planner/evaluator files
- keep pilots inside one bounded workflow at a time
- require measurable benefit over the current simpler path

# 4. Minimal adaptation path

- Smallest viable adaptation:
  - introduce a bounded handoff/contract artifact for one long-running workflow
  - pair it with a bounded verifier summary
  - do not introduce a general multi-agent runner

Best current contact points:
- deep-read job lane in `backend/services/job_runner.py`
- reader evaluation sidecar in `src/services/reader_eval_sidecar.py`
- gate logic in `src/quality/gates.py`
- meeting-pack generation/validation lane in `src/meeting_packs/service.py`
- search-design review loop in `src/profiles/research_dna_service.py`

Recommended minimal shape:
- Add an optional `work_contract.json` or `acceptance_contract.json` artifact for a selected workflow.
- Fields should be concrete and narrow:
  - requested scope
  - expected outputs
  - acceptance checks
  - gate owner
  - promotion rule
- Add an optional `quality_gate.json` summary artifact that compacts the verifier outputs already produced by the workflow.
- Keep promotion logic tied to existing canonical state, not to the new files themselves.

Current best first target:
- deep-read verification/promotion
  - because it already has persisted artifacts, promotion semantics, reader eval, stats verification, and release relevance

Lower-risk second target:
- meeting-pack generation
  - because it already has saved request, trace, validate, rerender, and regenerate behavior

Collision risk:
- medium if the new artifacts start behaving like a second truth store
- low if they stay strictly additive and derived from the existing run/artifact bundle

Rollback:
- easy if implemented as additive artifacts plus a narrow gating hook
- difficult only if it gets folded into generic planner/evaluator orchestration too early

# 5. Suggested experiment plan

- Apply candidate principles to one workflow only:
  - primary candidate: deep-read job
  - fallback candidate: meeting-pack generation

Experiment shape:
1. Baseline
   - current workflow with existing artifacts, events, and validator outputs
2. Pilot
   - add a narrow handoff/acceptance artifact plus a compact verifier summary
3. Compare
   - failure diagnosis speed
   - retry stability
   - promotion clarity
   - operator trust / manual explanation burden

Recommended evaluation criteria:
- Can an operator tell why a run was promotable or not without reading raw logs?
- Does rerun behavior remain non-destructive?
- Does the new artifact reduce ambiguity between "generated", "reviewed", and "promotable"?
- Does the pilot reduce handoff drift between generation and promotion?
- Does it avoid creating a parallel canonical truth source?

Suggested success criteria:
- at least one workflow becomes more diagnosable without adding a second truth store
- no increase in silent partial-state failures
- no meaningful product-shape drift
- modest extra artifact/storage overhead only

Suggested failure criteria:
- the pilot adds more complexity than clarity
- operators still need raw logs to understand promotion status
- artifact proliferation creates ownership confusion
- new contract files become the de facto truth instead of existing structured state

# 6. Patch / implementation impact

If the team chooses to pilot this, the smallest plausible touch set is:

- `backend/services/job_runner.py`
  - purpose: emit an optional per-run contract or handoff summary artifact
  - difficulty: medium
  - risk: medium

- `src/services/deepread_state_projection.py`
  - purpose: optionally read a bounded promotion-quality summary before promotion, or record why promotion was skipped
  - difficulty: medium
  - risk: medium

- `src/services/reader_eval_sidecar.py`
  - purpose: serve as one source for a compact graded quality summary rather than raw sidecar only
  - difficulty: low
  - risk: low

- `src/quality/gates.py`
  - purpose: reuse or extend bounded pass/warn/fail criteria for generated outputs
  - difficulty: low
  - risk: low

- `src/meeting_packs/service.py`
  - purpose: optional future pilot for request contract plus validate summary compaction
  - difficulty: low to medium
  - risk: low

- `docs/reports/...`
  - purpose: document the pilot as a bounded evaluation lane, not a new runtime architecture
  - difficulty: low
  - risk: low

What should not be touched first:
- no generic planner-agent framework
- no product-wide multi-agent orchestration layer
- no reopening of `/api/chat` or memory as the vehicle for handoff
- no new top-level project/decision/experiment graph to justify the harness

## Bottom line

Anthropic's harness design principles are useful here mostly as:
- a reminder to externalize long-running work into structured artifacts
- a reason to separate generation from skeptical verification
- a reason to define bounded acceptance criteria before promotion

They are not a good reason to turn Lattice into a heavy planner/generator/evaluator platform right now.

The right current move is:
- borrow a few principles
- pilot them in one bounded workflow
- keep the product paper-centered and structured-state-centered
- reject full harness adoption unless a future workload proves the added complexity is load-bearing
