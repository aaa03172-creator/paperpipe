# External Reference Action Order (2026-04-01)

Status: Concluded execution note
Date: 2026-04-01
Owner: Lattice runtime maintainers
Canonical: `docs/reports/External_Reference_Action_Order_2026-04-01.md`

Related notes:
- `docs/Product_Positioning_Principles.md`
- `docs/reports/Research_Workspace_Core_Structure_Decisions_2026-04-01.md`
- `docs/reports/Harness_Design_Fit_Review_2026-03-27.md`
- `docs/reports/Local_Deep_Read_Runtime_Measurement_2026-03-28.md`
- `docs/reports/Focused_First_Reader_Benchmark_2026-03-28.md`
- `docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md`
- `docs/Pending_PR_Queue.md`
- `docs/reports/Reader_Attempt_Order_Reopen_Check_2026-04-01.md`
- `docs/reports/External_Reference_Followups_Closeout_2026-04-01.md`

## Purpose

Turn the 2026-04-01 external-reference review into a short, execution-ordered action list.

This note is intentionally narrow.

It is not:
- a reason to reopen generalized workspace/platform work
- a reason to widen `/api/chat` or session memory lanes
- a reason to replace the current FastAPI/Pydantic/job/artifact runtime
- a reason to adopt browser-first inference or agent-harness clones

It answers one narrower question:
- based on the current repo and the reviewed references, what is actually worth doing next?

Important posture note:
- this document does **not** replace `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- the current default posture remains: stop at the bounded release-closeout slice unless external-reference-driven work is explicitly reopened
- if that narrower reference-driven work is reopened, use this note to keep scope bounded

## Current judgment

The current repo does not need a broad architecture reset.

The external references only justify a small number of near-term moves:
- tighten hard-case ingest measurement
- test one stronger OCR fallback candidate inside the existing fallback lane
- continue harness-first reader/runtime tuning
- make provenance/locator quality more visible in gates
- measure context composition more explicitly on long deep-read runs

The references do **not** justify:
- a model-serving rewrite
- browser inference as a core runtime path
- generalized multi-agent orchestration
- unofficial Claude/Claw-style runtime adoption
- reopening future-only `Project`, memory, or platform lanes

## Current completion snapshot

This note has now been executed to the current bounded stop point.

Current state:
- action 1 is done enough for this review:
  - the hard-PDF slice is frozen
- action 2 is done enough for this review:
  - locator-quality visibility is now additive in eval/gate artifacts
- action 3 was reopened, measured, and is now a hold:
  - the PaddleOCR candidate is installable, but still over-budget for the current fallback lane
- action 4 was fresh-checked and remains a hold:
  - `focused_first` remained useful as an opt-in path
  - but opposite-winner behavior and claim-yield tradeoffs still blocked a broader reopen
- action 5 is done enough for this review:
  - `context_manifest.json` is now emitted as an additive artifact

So there is no remaining external-reference-driven integration work that should be opened by default from this note.

## Selected actions only

These are the only actions worth opening from this review.

### 1. Build a bounded hard-PDF evaluation slice

Why first:
- the strongest candidate in the reference set is `PaddleOCR`, but it is only worth touching if the repo has a fixed hard-case benchmark to judge it against
- current repo guidance already favors bounded evaluation over architecture churn

Current status:
- initial v0 slice is now frozen in `goldset/manifests/hard_pdf_eval_slice_20260401.json`
- selection rationale lives in `docs/reports/Hard_PDF_Evaluation_Slice_2026-04-01.md`
- current scope is layout-heavy and table-heavy biomedical PDFs only; real scanned/image-based cases remain a separate later freeze

What to define:
- a tiny fixture slice of scanned, table-heavy, and layout-heavy biomedical PDFs
- per-paper notes for:
  - OCR needed or not
  - table extraction difficulty
  - locator quality expectations
  - downstream claim-support expectations

Likely touch points:
- `docs/reports/`
- `scripts/`
- focused tests around current ingest/eval paths such as:
  - `tests/test_job_runner_ingest_backend.py`
  - `tests/test_citation_grounding.py`

Success condition:
- a future OCR/parser comparison can be decided by saved measurements rather than by anecdotes

Owner:
- `ingest`

Size:
- `S`

### 2. Add locator-quality visibility to the current quality-gate path

Why second:
- current product trust depends more on evidence location quality than on abstract “model intelligence”
- the repo already enforces an evidence-first policy, but gate outputs still have room to make locator quality more explicit

Current status:
- additive locator-source counts are now exposed in `reader_eval.json`
- deep-read `quality_gate.json` now includes a compact `evidence_locator_quality` check
- current gate semantics were not tightened yet; this step is visibility-first

What to add:
- compact metrics for:
  - bbox-backed evidence count
  - text-match-only evidence count
  - approximate/unresolved evidence count
  - ambiguous grounding count

Likely touch points:
- `src/quality/claimset_policy.py`
- `src/services/citation_grounding.py`
- `src/services/reader_eval_sidecar.py`
- `src/services/deepread_handoff_artifacts.py`

Success condition:
- operators can distinguish “claim extracted” from “claim grounded well enough to trust”

Owner:
- `backend`

Size:
- `S`

### 3. Run a PaddleOCR fallback-only pilot

Why third:
- among the reviewed references, this is the most direct fit for a real current bottleneck
- the current runtime already has the right insertion point: OCR fallback, not a new ingest architecture

Current status:
- a bounded OCR compare harness now exists at `scripts/eval/compare_ocr_backends.py`
- the harness is tied to `goldset/manifests/hard_pdf_eval_slice_20260401.json`
- current state after follow-up:
  - `ocrmypdf` baseline path is installable and now writes output PDFs on the frozen hard slice
  - `paddleocr` plus `paddlepaddle` are installable in an isolated pilot-only env on this machine
  - the first real pilot exposed and fixed two compatibility issues:
    - invalid `ocrmypdf` CLI flags in `src/ingest/ocr_fallback.py`
    - outdated PaddleOCR API handling in `scripts/eval/compare_ocr_backends.py`
  - current blocker is no longer installation; it is candidate runtime/ops cost
  - full-slice and single-doc candidate probes remained too slow for the current bounded lane, so there is still no completed candidate comparison worth treating as adoption evidence
  - practical current decision:
    - keep the runtime unchanged and treat the candidate as a measured hold unless a materially faster bounded configuration appears

How to scope it:
- keep the current parser path as-is
- only run PaddleOCR when the existing hard-case evaluation slice says OCR fallback is warranted
- compare it against the current OCR fallback on:
  - text recovery quality
  - table recovery
  - locator quality
  - downstream claim/evidence yield
  - runtime/ops cost

Likely touch points:
- `src/agents/ingest_agent.py`
- `src/ingest/ocr_fallback.py`
- additive eval/reporting in `scripts/` or `docs/reports/`

Stop condition:
- stop immediately if the integration burden is high and the measured downstream benefit is weak
- current practical read: this stop condition is now close to being met unless a much narrower candidate lane or a materially faster configuration appears

Owner:
- `ingest`

Size:
- `M`

### 4. Reopen reader attempt-order work as a tiny gated pilot, not a broad redesign

Why fourth:
- current repo measurements already show that reader time dominates runtime
- current repo benchmarks already suggest that `focused_first` may cut prompt budget and wall time without obviously hurting claim yield on a small sample

Current status:
- the config-gated path already exists through `llm.reader_attempt_order`
- the default runtime order is still unchanged
- prior bounded benchmark and tiny pilot notes already exist:
  - `docs/reports/Focused_First_Reader_Benchmark_2026-03-28.md`
  - `docs/reports/Reader_Attempt_Order_RFC_2026-03-28.md`
  - `docs/reports/Focused_First_Gated_Pilot_Acceptance_2026-03-28.md`
- fresh 2026-04-01 reopen check now also exists:
  - `docs/reports/Reader_Attempt_Order_Reopen_Check_2026-04-01.md`
- so this lane is not missing implementation, and it also does not currently justify another bounded pilot

Pilot rule:
- do not change the default runtime immediately
- run a config-gated pilot with downstream checks on:
  - evidence linkage quality
  - note-side state quality
  - promotion/gate status
  - artifact quality on a tiny representative paper set

Likely touch points:
- `src/agents/reader_agent.py`
- `backend/services/job_runner.py`
- `src/services/reader_eval_sidecar.py`
- `src/quality/gates.py`

Success condition:
- the policy reduces cost/time without degrading support/grounding/promotion quality

Current practical read:
- keep this lane closed by default
- only reopen if a broader fixed-slice comparison shows that fresh reader pain remains worth paying for another pilot

Owner:
- `eval`

Size:
- `S`

### 5. Add a bounded `context_manifest`-style artifact for deep-read runs

Why fifth:
- the most useful lesson from Claude/Meta-harness references is bounded context discipline, not generalized agent sprawl
- current runtime now measures attempts and prompt budgets, but it still does not compactly summarize what context was actually sent

Current status:
- `context_manifest.json` is now written as an additive deep-read handoff artifact when `reader_analysis` exists
- it summarizes configured/effective attempt order plus per-attempt context composition
- the current note for this additive lane is:
  - `docs/reports/DeepRead_Context_Manifest_Artifact_2026-04-01.md`

What to record:
- selected attempt label
- context mode
- chunk count
- section count
- sentence-focus usage
- truncation flags
- optional summary of why the selected attempt won

Likely touch points:
- `backend/services/job_runner.py`
- `src/agents/reader_agent.py`
- additive artifact writing next to existing run metadata

Success condition:
- future cost/quality debugging no longer requires reading raw logs or digging through prompt assembly by hand

Owner:
- `backend`

Size:
- `S`

## Priority order

Open work in this order:

1. hard-PDF evaluation slice
2. locator-quality visibility
3. PaddleOCR fallback-only pilot
4. reader attempt-order gated pilot
5. `context_manifest` artifact

Reason for this order:
- first make the measurements credible
- then test the highest-fit ingest candidate
- then continue bounded harness tuning with better visibility

## Simple execution plan

### Phase 1: measurement before new integrations

Do:
- define the hard-PDF evaluation slice
- add locator-quality metrics to existing gate/eval outputs

Do not:
- add new OCR dependencies yet
- change the default reader policy yet

### Phase 2: bounded pilots

Do:
- run the PaddleOCR fallback-only comparison
- only reopen the reader attempt-order gated pilot if fresh representative runs still show unresolved pain

Do not:
- replace the default parser path
- widen the pilot into a generic model/runtime experiment lane

### Phase 3: runtime observability hardening

Do:
- use the new `context_manifest.json` artifact first when runtime cost/quality debugging needs context-composition visibility

Do not:
- reopen `/api/chat`
- create general session memory or planner-agent infrastructure

## Explicit non-actions from this review

Do not open these now:
- `transformers.js v4` integration
- `Bonsai-8B` runtime work
- `LFM2.5-350M` primary reader replacement
- `claw-code` or similar unofficial harness adoption
- generalized Claude-style sub-agent/runtime/plugin orchestration

Conditional later watchlist only:
- a tiny lightweight-model benchmark for narrow routing/query-rewrite work
- only after the five actions above are either completed or clearly not worth continuing

## Reopen conditions

Only reopen lower-priority references if one of these becomes true:
- hard-PDF ingest remains a real bottleneck after the PaddleOCR pilot
- reader/runtime cost remains high after bounded attempt-policy tuning
- current local deployment constraints prove that a smaller local helper model is worth the benchmark cost

If those conditions are not met, keep the remaining references as watchlist items only.

## Bottom line

This review does not justify a new platform direction.

It justified five bounded actions, in order:
- measure hard ingest cases
- expose locator-quality more clearly
- test one stronger OCR fallback
- continue bounded reader-policy tuning
- tighten context observability

Current stop point:
- those bounded actions have now either been completed to a useful stop point or reduced to reopen-only watchlist status
- anything broader than that is probably scope drift
