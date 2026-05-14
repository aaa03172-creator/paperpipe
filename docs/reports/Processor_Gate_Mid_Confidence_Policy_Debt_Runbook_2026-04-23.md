# Processor Gate Mid-Confidence Policy Debt Runbook

Status: operational report; additive review-artifact runbook
Date: 2026-04-23
Lane: processor gate threshold review
Scope: historical mid-confidence `APPROVED` rows from `local_processor_gate_drift_audit_reemit__threshold_review_scope16`

## Purpose

Record how operators should interpret the reviewed historical processor-gate drift rows without changing runtime gate behavior or historical database rows.

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
- `mid_confidence_policy_decision.json`
- `mid_confidence_policy_debt_reconciliation.json`
- `audit.md`

Operator viewer:

```bash
.venv/bin/paperpipe show-processor-gate-threshold-review snapshots/processor_gate_threshold_review/local_processor_gate_drift_audit_reemit__threshold_review_scope16
```

## Current Decision

The completed review supports this interpretation:

- Treat the reviewed historical mid-confidence `APPROVED` rows as legacy policy debt.
- Keep the current high threshold unchanged.
- Keep current mid-confidence rows on the pending-review policy path.
- Do not mass-rewrite historical `APPROVED` rows from this artifact alone.

Current artifact state:

- `manual_review_outcome.status=policy_only_confirmed`
- `threshold_change_decision.final_status=no_threshold_change_supported`
- `mid_confidence_policy_decision.final_status=mid_confidence_escalation_policy_confirmed`
- `mid_confidence_policy_debt_reconciliation.final_status=legacy_policy_debt_confirmed`
- `runtime_change_ready=false`
- `historical_mutation_ready=false`
- reviewed policy-debt rows: `21`
- high-threshold support rows: `0`

## Operator Rule

If this lane appears in future status checks, use the following default:

- Historical reviewed `APPROVED` rows: keep as legacy policy debt unless a separate migration plan is approved.
- Future mid-confidence rows: keep routing to pending review.
- High threshold: keep unchanged for this evidence.
- New threshold or migration work: require a separate artifact that explicitly sets readiness for runtime change or historical mutation.
- Threshold-change decision work: if manual review ever finds high-threshold boundary candidates, `threshold_change_decision.json` must include `threshold_change_preflight.ready=true` before `threshold_change_ready=true` is treated as actionable.
- Validation replay gate: `threshold_change_preflight.ready=true` requires the proposal validation replay to match the proposal. Missing or mismatched validation replay is a blocker, not a reason to change config.

## Do Not Do

Do not use this runbook to:

- lower the high threshold
- treat `threshold_change_ready=true` as actionable when `threshold_change_preflight.ready=false`
- auto-approve future mid-confidence rows
- rewrite historical `APPROVED` rows in SQLite or exported notes
- treat review artifacts as canonical paper state
- widen inference payloads or send raw state externally

## Reopen Criteria

Reopen the lane only if one of these occurs:

- A future manual review finds concrete high-threshold boundary candidates and the matching proposal validation replay sets `threshold_change_preflight.ready=true`.
- A separate migration proposal explicitly justifies rewriting historical rows.
- A replay run shows future current-runtime mid-confidence rows being incorrectly promoted or suppressed.
- Operator workload from pending review becomes high enough to justify a new policy review.

## Verification Snapshot

Last checked on 2026-04-23:

```bash
python3 -m py_compile scripts/eval/summarize_processor_gate_manual_review.py src/services/processor_gate_replay_drift.py src/cli.py tests/test_processor_gate_manual_review_outcome.py tests/test_cli_processor_gate_threshold_review_show.py tests/test_cli_watch_commands.py
pytest tests/test_processor_gate_manual_review_outcome.py tests/test_cli_processor_gate_threshold_review_show.py tests/test_cli_watch_commands.py -q
```

Result:

- `26 passed`
- live viewer JSON exposed the reconciliation sidecar
- `policy_debt_ids=21`
- `historical_mutation_ready=false`

## Next PR-Sized Actions

1. Leave runtime thresholds and historical rows unchanged.
2. Monitor future processor-gate replay runs for new non-legacy drift.
3. Only open a migration lane if a future artifact explicitly marks historical mutation as ready.
