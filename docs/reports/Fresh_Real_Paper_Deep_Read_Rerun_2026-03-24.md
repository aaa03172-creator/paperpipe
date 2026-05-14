Status: Active release evidence note  
Date: 2026-03-24  
Owner: Runtime/product maintainers  
Canonical parents:
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

# Fresh Real-Paper Deep Read Rerun

## Purpose

Record one bounded fresh real-paper deep-read rerun after the deep-read note-state promotion work and the local Ollama timeout patch.

This note is evidence only.
It is not a redesign proposal.

## Scope

Primary representative rerun target:
- `zotero:coricTargetingProdromalAlzheimer2015`

Observed stale pre-patch cleanup:
- `zotero:parkDiscoveryDualactionSmall2022`
  - stale `running` job row from a pre-timeout-patch attempt had to be cancelled before a new queued job could be claimed

Boundaries:
- one fresh deep-read rerun only
- current queue/worker/job-runner path
- no feature-lane widening

## Pre-Run State

`zotero:coricTargetingProdromalAlzheimer2015`
- note resolved through `/paper-notes/resolve-by-paper-id`
- `/paper-notes/{slug}` opened successfully
- `structured_state` was still missing
- note `ops_summary.latest_run_id = run_20260223_134233`
- note `ops_summary.state = action_needed`

## Patch Under Test

Two bounded runtime patches were tested in sequence.

Pass 1:
- wire `config.llm.timeout_seconds` into `ollama.Client(...)` initialization

Files:
- `src/llm_provider.py`
- `tests/test_ollama_provider_timeout.py`

Intent:
- convert local deep-read reader hangs from indefinite wait into explicit timeout failure
- preserve the current runtime contract and avoid widening the reader/storage path

Pass 2:
- reuse the adaptive reader timeout budget inside `backend/services/job_runner.py`
- record `reader_timeout_budget_sec` and related runtime metadata in `bootstrap_meta.json` / `run_meta.json`
- apply the reader timeout budget to the current reader instance instead of leaving the local provider at the base `llm.timeout_seconds`

Files:
- `backend/services/job_runner.py`
- `tests/test_worker_job_runner_chain.py`

Intent:
- keep the backend deep-read path aligned with the CLI timeout policy
- make reader/runtime budget inspectable in artifact metadata
- raise the effective reader timeout for representative real-paper runs without broad provider redesign

## Execution Path

Used the current real queue/worker path for both passes:
1. enqueue queued job for `zotero:coricTargetingProdromalAlzheimer2015`
2. claim via `JobQueue`
3. process via `Worker.process_job(...)`

Run info:

Pass 1:
- `job_id = 7a2f324a-313c-4429-a13c-43659c9eeb22`
- `run_id = run_20260324_032707`
- `run_verify = false`

Pass 2:
- `job_id = 52951fd7-a1a9-4e7f-8acc-9de9f6d6c7c2`
- `run_id = run_20260324_143902`
- `run_verify = false`

## Result

### Pass 1 Result

Outcome:
- rerun did **not** complete successfully
- it failed in the reader stage with explicit `httpx.ReadTimeout`
- this was still useful because it converted the previous silent stall into a bounded, inspectable failure

Observed runtime facts:
- ingest completed
- index completed
- new artifact run directory was created
- partial artifact files were written:
  - `bootstrap_meta.json`
  - `document_artifact.json`
  - `index_artifact.json`
  - `run_meta.json`
- no canonical note-side `.pp/<slug>/state.json` was created
- `/paper-notes/{slug}` still returned `structured_state = null`
- `/papers/{paper_id}` did update `latest_run_id` to `run_20260324_032707`

Terminal job state:
- `status = failed`
- `error_message = timed out`

### Pass 2 Result

Outcome:
- rerun completed successfully
- reader finished within the adaptive budget
- canonical note-side state was promoted successfully

Observed runtime facts:
- ingest completed
- index completed
- reader succeeded with `4 claims`
- new artifact run directory was created
- `bootstrap_meta.json` recorded:
  - `reader_timeout_budget_sec = 360`
  - `reader_provider_timeout_sec = 360`
  - `reader_timeout_triggered = false`
  - `claimset_readiness = ready`
- canonical note-side `.pp/<slug>/state.json` was created
- the note-side state existed before the run: `false`
- the note-side state existed after the run: `true`

Terminal job state:
- `status = completed`
- `run_meta.status = succeeded`

## Interpretation

This rerun sequence closed the main runtime uncertainty that was still open after the first timeout patch.

Closed:
- the current local Ollama reader path no longer waits indefinitely when the model does not answer in time
- the backend deep-read job runner now applies an adaptive reader timeout budget that reaches the actual reader call
- a fresh representative real-paper rerun can now complete all the way to canonical note-side `.pp/<slug>/state.json`

Still open:
- the narrow release verification set had not yet been rerun at the time of this evidence pass
- legacy/older artifact bundles may still need an explicit release boundary even though the current runtime path is now credible

## Practical Consequence

Current best reading:
- both bounded runtime patches should stay
- the current runtime no longer has a representative-paper reader completion blocker on this sample
- the next bounded step after this note was the narrow release verification rerun, not another reader-budget redesign
- if any yellow remains after that rerun, it is more likely to be a legacy-bundle boundary question than a current-runtime completion question

## Verification

Executed in this pass:

```bash
pytest -q tests/test_ollama_provider_timeout.py tests/test_deepread_state_projection.py tests/test_worker_job_runner_chain.py -q
./scripts/run_backend_api_smoke.sh
python3 scripts/check_frontend_real_smoke_env.py --require-candidates
```

Also executed:
- one fresh real-paper rerun through the queue/worker path for `zotero:coricTargetingProdromalAlzheimer2015` after the timeout wiring patch
- one follow-up fresh real-paper rerun through the same queue/worker path after the adaptive reader-timeout-budget patch

## Conclusion

The bounded fresh real-paper rerun sequence is now good enough to change the runtime judgment:

- the local reader path first became bounded and inspectable
- the follow-up adaptive reader-timeout-budget patch then carried the same representative paper through reader completion
- canonical note-side `.pp/<slug>/state.json` promotion is now proven on a fresh representative real-paper run

The next step is no longer another reader/runtime budget design pass.

It is:
- update release-facing notes from this new green representative rerun and the later release-set rerun
- then decide whether any remaining yellow is only a legacy-bundle boundary issue
