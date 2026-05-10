# Cloud Table Fallback Cost / Fidelity Review

Status: Bounded review completed
Date: 2026-03-24
Branch observed: `codex/agents-smoke-ci-check`
Scope: current-code review and bounded evidence readout only

## 0. Purpose

Review the current `cloud_table_fallback` lane without widening parser/runtime policy.

This note does not propose enabling cloud fallback by default.
This note does not propose replacing the current parser stack.
It records what the current code already guarantees, what bounded evidence exists, and what is still missing before any policy expansion.

## 1. Current Runtime Posture

Primary files:
- `/Users/jangseongjin/paperpipe/src/ingest/cloud_table_fallback.py`
- `/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py`
- `/Users/jangseongjin/paperpipe/src/config.py`

Current posture:
- optional pass-3 fallback only
- disabled by default in config
- bounded by explicit page budget
- explicit failure taxonomy on miss

Code-confirmed details:
- config default:
  - `enable_cloud_table_fallback=false`
  - `cloud_table_page_budget=1`
  - source: `/Users/jangseongjin/paperpipe/src/config.py`
- ingest runtime only reaches pass-3 if earlier table passes did not recover usable tables
  - source: `/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py`
- pass-3 diagnostics are explicit:
  - `table_extraction_pass`
  - `table_failure_taxonomy`
  - `fallback_used`
  - `fallback_pages`
  - source: `/Users/jangseongjin/paperpipe/src/ingest/cloud_table_fallback.py`

Important current mismatch:
- config default page budget is `1`
- job-runner ingest runtime resolver default is `2`
- source:
  - `/Users/jangseongjin/paperpipe/src/config.py`
  - `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`

Current judgment on that mismatch:
- it is not a blocker for the review lane
- but it should be treated as a policy-detail mismatch if this lane is resumed for runtime tightening

## 2. What Current Tests Already Guarantee

Focused tests:
- `/Users/jangseongjin/paperpipe/tests/test_cloud_table_fallback.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_parser_backend.py`
- `/Users/jangseongjin/paperpipe/tests/test_job_runner_ingest_backend.py`
- `/Users/jangseongjin/paperpipe/tests/test_job_runner_table_meta.py`

Current guarantees:
- low-coverage table outputs are rejected
- overlap-heavy table outputs are rejected
- invalid cloud tables still emit explicit taxonomy
- ingest metadata preserves pass/fallback fields
- job runner bootstrap/run meta exposes whether pass-3 was enabled and what page budget was used

This is good enough to treat the current lane as bounded and inspectable.

## 3. What Bounded Evidence Exists Today

Evidence already on disk:
- `/Users/jangseongjin/paperpipe/docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Stats_Fallback_Taxonomy_Real_Replay_Batch_2026-03-23.md`

Useful current bounded signals:
- in the expanded docling pilot:
  - `candidate docs with table fallback: 1 / 18`
- in stats fallback replay:
  - pass/fallback reasons are already bucketed into
    - `degenerate_table_shape`
    - `no_extractable_stats`
    - `no_table_data`
    - `NO_API_CONTEXT`

Interpretation:
- cloud fallback is real and already participates in bounded ingest behavior
- but current evidence is still sample-sized and lane-specific
- it is not yet a fleet-level cost justification dataset

## 4. What Is Still Missing

The current code does **not** yet answer these questions at fleet scale:
- actual invocation rate across real ingest runs
- accepted recovered table count per run
- useful recovery rate compared with parser-only output
- token/cost per useful recovered table
- whether recovered tables materially reduce downstream `unverifiable` stats outcomes

That means the current lane is inspectable, but not yet cost-justified at runtime-policy level.

## 5. Current Recommendation

Keep the current posture unchanged:
- keep `enable_cloud_table_fallback=false` as the default policy
- keep the current fallback strictly optional and bounded
- do not broaden page budget or enable-by-default behavior from the current evidence alone

Reason:
- quality guards exist
- bounded utility exists
- cost justification is still missing

## 6. Safest Next Step If This Lane Resumes

Do the smallest additive measurement step:

1. add a bounded cloud-fallback usage summary artifact
- count invocation
- count accepted recovered tables
- count fallback pages
- keep it sidecar/meta-only

2. run one small curated replay/report
- compare parser-only vs parser-plus-cloud on a fixed sample
- report useful recovery, not raw table count alone

3. only then reconsider policy details
- default enablement
- page-budget mismatch
- threshold tuning

## 7. Bottom Line

`cloud_table_fallback` is currently:
- technically bounded
- quality-guarded
- runtime-disabled by default
- not yet sufficiently measured to justify broader use

That is a healthy place to stop for now.
