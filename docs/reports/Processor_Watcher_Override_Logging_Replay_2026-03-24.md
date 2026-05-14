# Processor / Watcher Override Logging Replay

Status: Initial bounded replay completed
Date: 2026-03-24
Branch observed: `codex/agents-smoke-ci-check`
Scope: synthetic bounded replay only

## Purpose

Confirm that the new intake override logging shape is persisted without changing intake decisions.

## Current Output Contract

Persisted under `feedback_json.intake_override_log`:
- `schema_version`
- `producer`
- `analysis_available`
- `llm_tagging_used`
- `llm_slot_classification_used`
- `input_slot`
- `stored_slot`
- `slot_changed`
- `input_tags`
- `stored_tags`
- `tags_changed`
- `processing_status`
- `issues_state`
- `confidence`

## Replay Results

### processor_daily_slots

- producer: `processor_daily_slots`
- analysis available: `true`
- input slot: `mechanism`
- stored slot: `clinical`
- slot changed: `true`
- input tags: `[#flagged]`
- stored tags: `[#flagged]`
- tags changed: `false`
- processing status: `PENDING_REVIEW`
- issues state: `flagged`
- confidence: `0.74`

### watcher_local_pdf

- producer: `watcher_local_pdf`
- analysis available: `true`
- input slot: `test`
- stored slot: `test`
- slot changed: `false`
- input tags: `[#clear]`
- stored tags: `[#clear]`
- tags changed: `false`
- processing status: `APPROVED`
- issues state: `clear`
- confidence: `0.95`

## Current Judgment

The logging is additive and stable enough for the current lane.

What it already answers:
- whether analysis was available
- whether slot classification changed the stored slot
- what tags were produced and stored
- what processing status and `issues_state` were persisted

What it does not answer yet:
- how frequent these overrides are in a real bounded batch
- whether watcher and processor disagreement rates justify later model work

## Recommendation

Keep the logging shape as-is for now.

The next bounded step should be a small curated replay/report that measures:
- `slot_disagreement_rate`
- `tag_disagreement_rate`
- `analysis_unavailable_rate`
- `issues_state_unavailable_rate`
