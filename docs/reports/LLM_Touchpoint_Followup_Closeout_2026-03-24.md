# LLM Touchpoint Follow-up Closeout

Status: Core bounded stack completed
Date: 2026-03-24
Branch observed: `codex/agents-smoke-ci-check`
Scope: closeout note for the current measurement-first LLM follow-up stack

Canonical parent:
- `/Users/jangseongjin/paperpipe/docs/reports/LLM_Touchpoint_Followup_Plan_2026-03-23.md`

## 0. Purpose

Record what has now been completed from the current LLM touchpoint follow-up sequence.

This note is not a new roadmap.
It closes the current bounded stack and identifies the safe stopping point.

## 1. What Was Completed

### Workstream 1: Reader evaluation sidecar
- bounded schema/service hook added
- real-paper replay completed
- mixed-quality replay completed
- key outputs:
  - `/Users/jangseongjin/paperpipe/src/schemas/reader_eval.py`
  - `/Users/jangseongjin/paperpipe/src/services/reader_eval_sidecar.py`
  - `/Users/jangseongjin/paperpipe/docs/reports/Reader_Eval_Sidecar_Mixed_Replay_Batch_2026-03-23.md`

### Workstream 2: Stats fallback taxonomy
- bounded sidecar added
- fallback taxonomy replay completed
- `NO_API_CONTEXT` split out from generic `UNSPECIFIED_UNVERIFIABLE`
- key outputs:
  - `/Users/jangseongjin/paperpipe/src/schemas/stats_fallback_eval.py`
  - `/Users/jangseongjin/paperpipe/src/services/stats_fallback_eval_sidecar.py`
  - `/Users/jangseongjin/paperpipe/docs/reports/Stats_Fallback_Taxonomy_Real_Replay_Batch_2026-03-23.md`

### Workstream 3: Teacher-review precision
- spot-check packet and precheck created
- eval sidecar added
- anchor-quality taxonomy added
- pre-accept suppression added for:
  - `FRAGMENTARY_CLAIM`
  - `MISALIGNED_QUOTE`
- warning-only metadata retained for:
  - `ADJACENT_SUPPORT`
  - `HEADING_LEVEL_SUPPORT`
- key outputs:
  - `/Users/jangseongjin/paperpipe/src/schemas/teacher_review_eval.py`
  - `/Users/jangseongjin/paperpipe/src/services/teacher_review_eval_sidecar.py`
  - `/Users/jangseongjin/paperpipe/scripts/verify_teacher_output.py`
  - `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Review_Anchor_Quality_Full_Replay_2026-03-24.md`
  - `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Review_Pre_Accept_Suppression_Replay_2026-03-24.md`

### Workstream 4: Processor / watcher override logging
- additive intake logging added under `feedback_json.intake_override_log`
- both processor and watcher now persist:
  - analysis availability
  - original vs stored slot
  - original vs stored tags
  - processing status
  - issues-state
- key outputs:
  - `/Users/jangseongjin/paperpipe/src/schemas/intake_override_log.py`
  - `/Users/jangseongjin/paperpipe/src/services/intake_override_log.py`
  - `/Users/jangseongjin/paperpipe/docs/reports/Processor_Watcher_Override_Logging_Replay_2026-03-24.md`

### Workstream 5: Cloud table fallback cost/fidelity review
- current posture reviewed
- cost-justification gap documented
- no policy broadening recommended
- key output:
  - `/Users/jangseongjin/paperpipe/docs/reports/Cloud_Table_Fallback_Cost_Fidelity_Review_2026-03-24.md`

## 2. What Changed in Practice

The repo is now better at distinguishing:
- supported vs unsupported vs unknown reader output
- grounded vs ambiguous vs failed evidence attachment
- stats `unverifiable` buckets
- teacher-review claim-validity vs anchor-quality failures
- intake classification availability vs disagreement
- bounded cloud-fallback usefulness vs policy uncertainty

This is the main improvement:
- the system did not become less LLM-driven in the research layer
- it became more inspectable before artifact outputs harden

## 3. What We Intentionally Did Not Do

These were correctly avoided:
- no full rewrite
- no parser replacement
- no storage/orchestrator redesign
- no main-model fine-tuning
- no forced contract migration just because multiple artifact layers exist
- no widening of `Meeting Pack`, `Research DNA`, or viewer architecture in response to LLM concerns

## 4. Current Safe Stopping Point

The current bounded stack is complete enough to stop here.

Why:
- the highest-risk LLM surfaces now have additive measurement or guardrail coverage
- the next meaningful question is no longer “what basic sidecar should exist?”
- the next meaningful question is “do these new measurements justify later tuning, stronger policy, or more targeted runtime guardrails?”

## 5. Current Recommendation

Do not open a new LLM-facing runtime lane immediately.

The safest next decision is a bounded review, not new runtime work:
1. accumulate more real runs using the new sidecars/logs
2. review whether repeated failure patterns are stable across runs
3. only then decide whether a later training-candidacy review is warranted

## 6. Commit Anchors

Current bounded stack anchors:
- `eed6d2c` `feat(teacher-review): add eval sidecar and suppression guardrails`
- `dd4a51c` `feat(teacher-review): surface warning-only anchor labels`
- `b10e121` `feat(intake): add processor watcher override logging`
- `635e2dd` `docs(llm): review cloud table fallback cost posture`

Related earlier anchors in the same sequence:
- reader sidecar and replay work
- stats fallback sidecar and replay work
- handoff docs for the processor/watcher lane

## 7. Recommendation

Treat the current LLM follow-up stack as closed.

Resume only if one of these becomes true:
- a repeated failure pattern appears in the new sidecars/logs
- a product-facing regression shows current guardrails are insufficient
- a training-candidacy review is explicitly requested
