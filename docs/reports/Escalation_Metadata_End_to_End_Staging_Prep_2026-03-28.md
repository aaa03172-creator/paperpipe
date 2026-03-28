# Escalation Metadata End-to-End Staging Prep

Date: 2026-03-28
Status: Patch-staged and index-verified; blind staging still unsafe for remaining mixed worktree changes
Owner: Runtime maintainers

## Goal

Package the end-to-end escalation metadata lane that now covers:

- deterministic biomedical-general escalation policy
- structured escalation output and canonical reason-code normalization
- main gate-path persistence in `feedback_json["escalation"]`
- legacy batch-path persistence for note/report rendering
- API exposure on `/papers`
- note and daily-report consumption
- smoke and regression coverage

This is the smallest bundle that preserves the current runtime story from producer to consumer without requiring DB migrations.

## Intended Include

Runtime and contracts:

- `src/llm_provider.py`
- `src/config.py`
- `src/services/runtime_paths.py`
- `src/schemas/core.py`
- `src/schemas/papers.py`
- `src/obsidian.py`
- `src/processor.py`
- `src/reporting.py`
- `backend/main.py`

Scripts and fixtures:

- `scripts/check_escalation_judge_smoke.py`
- `scripts/run_escalation_judge_verify.sh`
- `tests/fixtures/escalation_judge_case/cases.json`
- `tests/fixtures/escalation_judge_case/real_cases_20260327.json`
- `tests/fixtures/escalation_judge_case/real_cases_extended_20260327.json`

Tests:

- `tests/test_escalation_judge_smoke.py`
- `tests/test_escalation_prompt_policy.py`
- `tests/test_escalation_structured_output.py`
- `tests/test_llm_provider_task_temperature.py`
- `tests/test_obsidian_institutional_block.py`
- `tests/test_obsidian_save.py`
- `tests/test_papers_api.py`
- `tests/test_processor_gate_integration.py`
- `tests/test_processor_institutional_proxy.py`
- `tests/test_reporting.py`

Docs:

- `docs/reports/Escalation_Judge_Policy_Review_2026-03-27.md`
- `docs/reports/Escalation_Judge_Recovery_Staging_Prep_2026-03-28.md`
- `docs/reports/Escalation_Metadata_Handoff_2026-03-28.md`
- `docs/reports/Escalation_Metadata_End_to_End_Staging_Prep_2026-03-28.md`

## Why This Bundle Boundary

This lane is no longer only `llm_provider` plus smoke fixtures.

Current closure requires:

- `src/llm_provider.py` for structured escalation output and normalized reason codes
- `src/processor.py` for main `_step_gate()` persistence and legacy `process_daily_slots()` persistence
- `backend/main.py` and `src/schemas/papers.py` for API exposure
- `src/obsidian.py` for note rendering
- `src/reporting.py` for daily report consumption
- `src/schemas/core.py` for note/runtime-facing additive fields
- `src/config.py` and `src/services/runtime_paths.py` because the present `llm_provider` path depends on them in the current worktree

Leaving out the API/report/note consumers would package only half of the currently verified behavior.

## Exclude

- frontend viewer/UI work
- meeting-pack, deep-read, runtime-readiness, and unrelated biomedical extraction lanes
- unrelated docs and reports created on 2026-03-27 and 2026-03-28
- any new runtime path that does not already read or write `feedback_json["escalation"]`

## Verification

Targeted regression bundle:

- `pytest tests/test_reporting.py tests/test_papers_api.py tests/test_processor_gate_integration.py -q`
  - result: `19 passed`

Broader runtime bundle:

- `pytest tests/test_full_pipeline.py tests/test_processor_institutional_proxy.py tests/test_obsidian_institutional_block.py tests/test_obsidian_save.py tests/test_escalation_structured_output.py tests/test_escalation_judge_smoke.py tests/test_llm_provider_task_temperature.py -q`
  - result: `40 passed`

Live smoke:

- `python3 scripts/check_escalation_judge_smoke.py --max-mismatches 0`
  - result: `10/10 match`, `invalid_output_count=0`

Docs:

- `python3 scripts/lint_docs.py`
  - result: `docs lint passed`

Index-snapshot verification of the staged bundle:

- exported index snapshot with current staged files only
- `PAPERPIPE_CONFIG_PATH=/Users/jangseongjin/paperpipe/config.yaml pytest tests/test_escalation_prompt_policy.py tests/test_escalation_judge_smoke.py tests/test_llm_provider_task_temperature.py tests/test_processor_gate_integration.py tests/test_papers_api.py tests/test_obsidian_institutional_block.py tests/test_reporting.py -q`
  - result: `44 passed`
- `PAPERPIPE_CONFIG_PATH=/Users/jangseongjin/paperpipe/config.yaml python3 scripts/check_escalation_judge_smoke.py --max-mismatches 0`
  - result: `6/6 match`, `invalid_output_count=0`

## Current Packaging Reality

Do not blindly stage the full include list from the current worktree.

Recheck findings:

- `backend/main.py` is mixed:
  - escalation API response exposure is in scope
  - access-summary work, runtime-readiness endpoint work, frontend shell asset routing, and fixture-visibility filtering are not part of this lane
- `src/processor.py` is mixed:
  - main `_step_gate()` escalation persistence is in scope
  - generic clinical extraction support in `process_daily_slots()` is a broader lane
- `src/obsidian.py` is mixed:
  - escalation metadata rendering is in scope
  - broader clinical template and extraction rendering changes are not purely escalation-metadata work
- `tests/test_papers_api.py` is mixed:
  - escalation response assertions are in scope
  - access-summary and fixture-visibility coverage are separate concerns

Because these files are mixed, a blind `git add` of the intended include list would stage unrelated work.

What changed since the first mapping:

- the escalation-runtime slice has now been staged with explicit patch-based index updates
- the staged snapshot has been verified outside the dirty worktree
- the remaining risk is no longer "can this bundle be staged at all?"
- the remaining risk is "do not accidentally stage the unrelated unstaged parts of the same owner files"

## Safe Packaging Guidance

Current safe options:

1. Split mixed files into a dedicated branch or patch series before staging.
2. If the goal is only documentation/handoff, stage only the report files and leave runtime code unstaged.
3. If the goal is a clean runtime commit, extract only the escalation hunks from mixed files with explicit patch-based staging, then rerun the verification bundle below.

Current recommendation:

- keep using this document as the boundary map
- treat the current staged bundle as the verified commit candidate
- do not run broad staging commands from the dirty worktree
- only reopen patch-based staging if more escalation-lane files need to join this bundle

## Current Staged Bundle

Currently staged runtime and contract files:

- `src/config.py`
- `src/llm_provider.py`
- `src/obsidian.py`
- `src/processor.py`
- `src/reporting.py`
- `src/schemas/core.py`
- `src/schemas/papers.py`
- `src/services/runtime_paths.py`
- `backend/main.py`

Currently staged scripts, fixtures, and tests:

- `scripts/check_escalation_judge_smoke.py`
- `scripts/run_escalation_judge_verify.sh`
- `tests/fixtures/escalation_judge_case/real_cases_20260327.json`
- `tests/fixtures/escalation_judge_case/real_cases_extended_20260327.json`
- `tests/test_escalation_judge_smoke.py`
- `tests/test_escalation_prompt_policy.py`
- `tests/test_llm_provider_task_temperature.py`
- `tests/test_obsidian_institutional_block.py`
- `tests/test_papers_api.py`
- `tests/test_processor_gate_integration.py`
- `tests/test_reporting.py`

Currently staged docs:

- `docs/reports/Escalation_Judge_Policy_Review_2026-03-27.md`
- `docs/reports/Escalation_Judge_Recovery_Staging_Prep_2026-03-28.md`
- `docs/reports/Escalation_Metadata_Handoff_2026-03-28.md`
- `docs/reports/Escalation_Metadata_End_to_End_Staging_Prep_2026-03-28.md`

## Whole-File Safe Candidates

These files currently read as escalation-metadata lane only and are the safest first-stage candidates once staging resumes:

- `src/reporting.py`
- `tests/test_processor_gate_integration.py`
- `tests/test_reporting.py`
- `docs/reports/Escalation_Metadata_Handoff_2026-03-28.md`
- `docs/reports/Escalation_Metadata_End_to_End_Staging_Prep_2026-03-28.md`

Recheck note:

- this list is intentionally conservative
- mixed files below still require patch-based staging or prior disentangling

## Mixed Owner Hunk Map

### `backend/main.py`

In scope:

- lines `287-336`: `_apply_escalation_response_fields`
- lines `1158-1159`: list response application of escalation fields
- lines `1186-1187`: detail response application of escalation fields

Out of scope for this lane:

- lines `262-284`: `access_summary`
- lines `782-796`: runtime readiness endpoint
- lines `1060-1107`: frontend shell / asset routing
- line `1161`: fixture-visibility filtering

### `src/processor.py`

In scope:

- lines `68-114`: escalation sidecar helpers
- lines `327-382`: main `_step_gate()` escalation persistence and status upgrade
- lines `514-617`: legacy `process_daily_slots()` escalation sidecar and row metadata

Out of scope for this lane:

- lines `482-505`: generic clinical extraction runtime
- lines `618-623`: `clinical_data` sidecar write
- line `628`: `save_paper_to_obsidian(..., extraction=clinical_extraction)`

### `src/obsidian.py`

In scope:

- lines `11-28`: escalation metadata formatter
- lines `30-55`: status callout escalation rendering
- line `59`: study template status callout owner
- line `110`: study template insertion point
- line `255`: clinical template status callout insertion point

Out of scope for this lane:

- lines `120+`: broader biomedical/specialty clinical template rewrite

### `tests/test_papers_api.py`

In scope:

- lines `246-347`: escalation metadata API exposure regression

Out of scope for this lane:

- lines `18-157`: access-summary coverage
- line `467`: ops-summary wording drift expectation
- lines `480+`: fixture-visibility listing coverage

### `src/schemas/papers.py`

Mixed:

- escalation response fields are in scope
- `PaperAccessSummary` and `access_summary` response surface are not escalation-only

Current recommendation:

- do not whole-file stage `src/schemas/papers.py` as part of the pure safe subset
- stage it later only together with the matching API response lane, or after a separate split

## Patch-Based Staging Order

If patch-based staging is chosen later, the safest order is:

1. whole-file safe candidates
2. `src/processor.py` in-scope hunks
3. `backend/main.py` in-scope hunks
4. `src/obsidian.py` in-scope hunks
5. `tests/test_papers_api.py` in-scope hunk
6. rerun the verification bundle in this document

## Practical Packaging Note

Because the current worktree contains many unrelated dirty files, prefer packaging by explicit include list rather than broad `git add .`.

Recommended review order:

1. `src/llm_provider.py`
2. `src/processor.py`
3. `backend/main.py`
4. `src/obsidian.py`
5. `src/reporting.py`
6. schemas/tests/docs

## Suggested Commit Message

If the mixed files are disentangled first:

`feat(runtime): wire escalation metadata through gate, api, notes, and reports`
