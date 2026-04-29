# Processor Gate Excluded Bucket Policy Runbook

Status: operational report; additive review-artifact runbook
Date: 2026-04-23
Lane: processor gate threshold review
Scope: excluded manual-override, indexed-pending, and fixture/test buckets from `local_processor_gate_drift_audit_reemit__threshold_review_scope16`

## Purpose

Record how operators should interpret excluded processor-gate drift rows without changing runtime gate behavior, live thresholds, or historical database rows.

This report is not a canonical state store and does not replace `src/db_utils.py`, gate runtime logic, or the paper/run/artifact model. It summarizes a completed review-artifact lane.

## Layer Classification

Layer: review/gate artifact.

The source run artifacts are derived from replay and manual-review evidence. They are useful for audit and calibration, but they are not replacement truth stores.

## Source Artifacts

Primary run directory:

- `snapshots/processor_gate_threshold_review/local_processor_gate_drift_audit_reemit__threshold_review_scope16/`

Key sidecars:

- `manual_review_codex_full.csv`
- `manual_review_outcome.json`
- `threshold_change_decision.json`
- `manual_override_policy_decision.json`
- `indexed_pending_policy_decision.json`
- `fixture_or_test_policy_decision.json`
- `audit.md`

Operator viewer:

```bash
.venv/bin/paperpipe show-processor-gate-threshold-review snapshots/processor_gate_threshold_review/local_processor_gate_drift_audit_reemit__threshold_review_scope16
```

## Current Decision

The completed review supports this interpretation:

- Keep manual or human override rows outside raw threshold tuning.
- Keep indexed-pending status-contract rows outside raw threshold tuning.
- Keep fixture/test hygiene rows outside raw threshold tuning.
- Keep the current high threshold unchanged.
- Do not mass-rewrite historical rows from these artifacts alone.
- Do not treat excluded bucket counts as evidence for lowering or widening gate thresholds.

Current artifact state:

- `manual_review_outcome.status=policy_only_confirmed`
- `threshold_change_decision.final_status=no_threshold_change_supported`
- `manual_override_policy_decision.final_status=manual_override_exception_policy_confirmed`
- `manual_override_policy_decision.recommended_action=exclude_manual_override_rows_from_threshold_tuning`
- `indexed_pending_policy_decision.final_status=indexed_pending_status_contract_confirmed`
- `indexed_pending_policy_decision.recommended_action=keep_indexed_pending_rows_out_of_threshold_tuning`
- `fixture_or_test_policy_decision.final_status=fixture_or_test_hygiene_exclusion_confirmed`
- `fixture_or_test_policy_decision.recommended_action=keep_fixture_or_test_rows_out_of_threshold_tuning`
- `runtime_change_ready=false`
- `historical_mutation_ready=false`
- `archive_action_ready=false`
- manual-override rows: `2`
- indexed-pending rows: `2`
- fixture/test rows: `1`

## Reviewed Excluded IDs

Manual override rows:

- `zotero:duboisAmnesticMCIProdromal2004`
- `zotero:grandeBloodbasedBiomarkersAlzheimers2025`

Indexed pending rows:

- `zotero:kowalskiBrainGutMicrobiotaAxisAlzheimers2019`
- `zotero:sochockaGutMicrobiomeAlterations2019`

Fixture/test rows:

- `phase0_test`

## Operator Rule

If this lane appears in future status checks, use the following default:

- Manual or human override rows: preserve as explicit policy exceptions unless a separate operator decision changes them.
- Indexed-pending rows: preserve as status-contract cases rather than threshold calibration examples.
- Fixture/test rows: preserve as hygiene-scope rows; use fixture hygiene tools for cleanup decisions, not threshold-review artifacts.
- Threshold tuning: use threshold-relevant review rows, not excluded policy buckets.
- Runtime, archive, or migration work: require a separate artifact that explicitly sets readiness for runtime change, archive action, or historical mutation.
- Threshold-change decision work: if a separate threshold-relevant review later finds high-threshold candidates, `threshold_change_decision.json` must include `threshold_change_preflight.ready=true` before `threshold_change_ready=true` is treated as actionable.
- Validation replay gate: `threshold_change_preflight.ready=true` requires the proposal validation replay to match the proposal. Missing or mismatched validation replay is a blocker, not a reason to change config.

## Do Not Do

Do not use this runbook to:

- lower the high threshold
- treat `threshold_change_ready=true` as actionable when `threshold_change_preflight.ready=false`
- rewrite historical processor-gate decisions
- convert manual overrides into automatic gate examples
- treat indexed-pending rows as false negatives for threshold calibration
- treat fixture/test rows as high-confidence threshold false negatives
- archive fixture rows from this review artifact alone
- treat review artifacts as canonical paper state
- widen inference payloads or send raw state externally

## Reopen Criteria

Reopen the lane only if one of these occurs:

- A future replay run shows excluded rows being mixed into threshold-relevant calibration buckets.
- A manual override row is later found to be a mislabeled normal gate decision.
- An indexed-pending row becomes a true runtime status bug rather than a status-contract case.
- A fixture/test row is later found to be a real non-fixture paper row.
- A separate migration proposal explicitly justifies rewriting historical rows.

## Verification Snapshot

Last checked on 2026-04-23:

```bash
python3 -m py_compile scripts/eval/summarize_processor_gate_manual_review.py src/services/processor_gate_replay_drift.py src/cli.py tests/test_processor_gate_manual_review_outcome.py tests/test_cli_processor_gate_threshold_review_show.py tests/test_cli_watch_commands.py
pytest tests/test_processor_gate_manual_review_outcome.py tests/test_cli_processor_gate_threshold_review_show.py tests/test_cli_watch_commands.py -q
python3 scripts/lint_docs.py
```

Result:

- `26 passed`
- docs lint passed
- live viewer exposed all three excluded-bucket policy sidecars
- `manual_override_count=2`
- `indexed_pending_count=2`
- `fixture_or_test_count=1`
- `runtime_change_ready=false`
- `historical_mutation_ready=false`
- `archive_action_ready=false`

## Next PR-Sized Actions

1. Leave runtime thresholds and historical rows unchanged.
2. Monitor future processor-gate replay runs for excluded-bucket leakage into threshold tuning.
3. Only open archive or migration work if a future artifact explicitly marks archive action, runtime change, or historical mutation as ready.
