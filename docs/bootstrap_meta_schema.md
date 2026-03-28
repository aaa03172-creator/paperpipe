# bootstrap_meta.json Schema

This file is written per deepread run at:
`storage/artifacts/<paper_id>/<run_id>/bootstrap_meta.json`

## Purpose
- Keep lightweight run reproducibility metadata next to artifacts.
- Make persona + feedback injection observable without parsing logs.

## Fields
- `job_id` (string): Queue job identifier.
- `run_id` (string): Run identifier for artifact directory.
- `paper_id` (string): Paper ID used for the run.
- `persona_id` (string): Requested persona profile id.
- `persona_applied` (bool): Whether any persona/feedback hint was actually applied to reader prompt.
- `similar_feedback_count` (int): Number of injected similar feedback examples.
- `similar_feedback_paper_ids` (array[string]): Source paper IDs for injected feedback snippets.
- `run_verify` (bool): Whether stats verification was requested.
- `reader_model` (string|null): Reader model name selected for this run.
- `reader_timeout_base_sec` (int): Base timeout seed derived from the configured provider timeout before page/table scaling.
- `reader_timeout_budget_sec` (int): Effective timeout budget applied to the guarded reader call for this run.
- `reader_timeout_adaptive` (bool): Whether the effective timeout budget was scaled from page/table counts rather than left fixed.
- `reader_page_count` (int): Page count used when estimating the reader timeout budget.
- `reader_table_count` (int): Table count used when estimating the reader timeout budget.
- `reader_timeout_triggered` (bool): Whether the guarded reader step actually timed out for this run.
- `reader_timeout_error_type` (string|null): Timeout exception class name when the guarded reader step timed out, otherwise `null`.
- `reader_provider_timeout_override_applied` (bool): Whether a provider-specific timeout override was applied to the reader lane for this run.
- `verifier_used` (bool): Whether verifier path is enabled for this run.
- `verifier_status` (string): `not_run` | `completed` | `failed`.
- `stats_report_written` (bool): Whether `stats_report.json` was written.
- `artifact_document_written` (bool): Whether `document_artifact.json` was written.
- `artifact_index_written` (bool): Whether `index_artifact.json` was written.
- `artifact_claimset_written` (bool): Whether `claimset.json` was written.
- `artifact_stats_written` (bool): Whether `stats_report.json` was written.
- `claimset_readiness` (string): `unknown` | `ready` | `not_ready`.
- `claimset_ready` (bool|null): Convenience boolean for consumers (`null` when unknown/not evaluated).
- `claimset_claim_count` (int): Number of extracted claims saved in `claimset.json`.
- `claimset_readiness_reason` (string): Machine-friendly reason such as `not_evaluated`, `claims_present`, `empty_claims`.
- `claimset_readiness_badge` (string): UI-friendly badge label (`UNKNOWN` | `READY` | `NOT_READY`).
- `claimset_ops_action` (string): Operational next action (`none` | `manual_review_queued` | `manual_review_required` | `retry_suggested`).
- `claimset_ops_alert` (bool): Whether operational attention is required immediately.
- `claimset_ops_note` (string): Additional action context (e.g., `ready`, `queued`, `already_open`, `queue_unavailable`, `runtime_error:*`).
- `timestamp` (string, ISO-8601): UTC timestamp when metadata was initialized.

## Example
```json
{
  "job_id": "c826...",
  "run_id": "0d59...",
  "paper_id": "paper_chain_001",
  "persona_id": "smoke-persona",
  "persona_applied": true,
  "similar_feedback_count": 2,
  "similar_feedback_paper_ids": ["p123", "p456"],
  "run_verify": true,
  "reader_model": "llama3:latest",
  "reader_timeout_base_sec": 90,
  "reader_timeout_budget_sec": 123,
  "reader_timeout_adaptive": true,
  "reader_page_count": 12,
  "reader_table_count": 3,
  "reader_timeout_triggered": false,
  "reader_timeout_error_type": null,
  "reader_provider_timeout_override_applied": false,
  "verifier_used": true,
  "verifier_status": "completed",
  "stats_report_written": true,
  "artifact_document_written": true,
  "artifact_index_written": true,
  "artifact_claimset_written": true,
  "artifact_stats_written": true,
  "claimset_readiness": "ready",
  "claimset_ready": true,
  "claimset_claim_count": 4,
  "claimset_readiness_reason": "claims_present",
  "claimset_readiness_badge": "READY",
  "claimset_ops_action": "none",
  "claimset_ops_alert": false,
  "claimset_ops_note": "ready",
  "timestamp": "2026-02-20T00:00:00+00:00"
}
```
