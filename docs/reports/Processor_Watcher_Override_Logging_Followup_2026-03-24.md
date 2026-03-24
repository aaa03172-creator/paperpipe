# Processor / Watcher Override Logging Follow-up

Status: Next bounded LLM follow-up
Date: 2026-03-24
Branch observed: `codex/agents-smoke-ci-check`
Scope: additive logging and bounded replay/reporting only

Canonical parent:
- `/Users/jangseongjin/paperpipe/docs/reports/LLM_Touchpoint_Followup_Plan_2026-03-23.md`

## 0. Purpose

Start the next post-teacher-review LLM follow-up without widening scope.

This lane is not about changing intake semantics.
It is about measuring how often LLM-produced intake judgments are later overridden, ignored, or bypassed.

## 1. Why This Is Next

Workstreams already completed in bounded form:
- reader evaluation sidecar
- stats fallback taxonomy
- teacher-review spot-check, eval sidecar, anchor-quality taxonomy, and pre-accept suppression

The next unresolved question is no longer claim extraction quality.
It is intake quality drift:
- how often tags/slots are later changed
- how often analysis is unavailable
- how often issues-state becomes unavailable because upstream analysis did not exist

This lane remains lower risk than reader/stats because it mostly affects routing and triage rather than scientific artifact truth.

## 2. Target Files

- `/Users/jangseongjin/paperpipe/src/processor.py`
- `/Users/jangseongjin/paperpipe/src/watcher.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Issues_State_Persistence_Staging_Prep_2026-03-23.md`

## 3. Bounded Questions

1. How often does the LLM-produced slot differ from the final stored slot?
2. How often do LLM-produced tags differ from the final stored tags?
3. How often is analysis unavailable, forcing the system into a non-LLM or partial path?
4. How often does `issues_state` become unavailable because analysis was unavailable?

## 4. Deliverables

- additive intake override log or sidecar
- bounded replay/report over a small curated sample
- decision note on whether processor/watcher disagreement is frequent enough to justify later model work

## 5. Checklist

- record original LLM slot when available
- record final stored slot after deterministic handling
- record original LLM tags when available
- record final stored tags after deterministic handling
- record whether downstream override occurred
- record whether analysis was unavailable
- record whether `issues_state` was unavailable
- keep watcher logging separate from processor batch logging
- keep canonical stored outputs unchanged

## 6. Suggested Metrics

- `triage_override_rate`
- `slot_disagreement_rate`
- `tag_disagreement_rate`
- `analysis_unavailable_rate`
- `issues_state_unavailable_rate`

## 7. Acceptance Criteria

Treat this lane as successful only if all are true:
- one bounded report can show whether intake disagreement is common or rare
- the logging stays additive and does not change intake decisions
- replay/report generation does not require rewriting processor or watcher semantics

## 8. Explicit Non-Goals

Do not do these in this lane:
- rewrite processor flow
- rewrite watcher flow
- change slot taxonomy
- retune the model first
- merge intake logging with reader/stats/teacher-review sidecars

## 9. Recommendation

Start with `processor` first, then mirror the same logging shape into `watcher`.

That keeps the next lane narrow:
1. batch-ish path first
2. local watcher path second
3. bounded replay/report third
