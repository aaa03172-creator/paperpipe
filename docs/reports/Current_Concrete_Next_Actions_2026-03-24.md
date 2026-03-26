# Current Concrete Next Actions (2026-03-24)

Status: Active execution note  
Date: 2026-03-24  
Owner: Lattice runtime maintainers  
Canonical: `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`

## Purpose

Turn the current audit/alignment findings into a short, execution-ordered action list.

This note is not:
- a roadmap rewrite
- a reason to reopen future-only lanes
- a signal to widen the product beyond the current paper-centered runtime

It answers one narrower question:
- based on the current checks, what should we fix or prove next?

## Current Judgment

The repo no longer needs a broad architecture reset.

The current state is:
- product/runtime boundary is materially cleaner
- viewer truth visibility on paper-note list/detail is materially stronger
- deep-read note-state promotion is now implemented and regression-covered
- one fresh representative real-paper rerun has now completed successfully after the bounded reader-timeout-budget patch, which means the main remaining gap is no longer representative-paper reader completion under the current runtime
- the narrow release verification set has now rerun green enough to move past release-note closeout
- the legacy/partial bundle release boundary is now explicit, so legacy bundles no longer silently define the launch proof slice
- one bounded release rehearsal run is now on record, no `Must-Not-Ship` row turned `true`, the representative-paper discoverability partial in `/papers` is now closed, and a newer non-fixture `Meeting Pack` representative with trace coverage is now on record

So the next actions should be:
1. treat the current repo as ready for bounded demo/reveal usage
2. only if historical cleanup matters, keep older legacy/non-fixture packs out of the external story
3. keep legacy backfill as an optional later bounded task rather than a first-product blocker

## Concrete Action Order

### 1. Default next move: stop here and use the current bounded demo/reveal slice

Why first:
- the representative rerun, the release-set rerun, and the bounded release rehearsal are all now on record
- the remaining issues are smaller than architecture or runtime viability questions

Current command set:

```bash
./scripts/run_backend_api_smoke.sh
pytest -q tests/test_research_dna_service.py tests/test_evaluate_search.py tests/test_research_dna_cli.py
cd frontend && npm run verify:frontend:backend
./scripts/run_meeting_pack_verify.sh
python3 scripts/lint_docs.py
cd frontend && npm run e2e:backend:real-smoke
```

Primary anchor:
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/reports/Deep_Read_Legacy_Bundle_Release_Boundary_2026-03-25.md`
- `docs/reports/Release_Rehearsal_Checklist_2026-03-25.md`
- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`

Current rerun result:
- `./scripts/run_backend_api_smoke.sh` -> passed
- `pytest -q tests/test_research_dna_service.py tests/test_evaluate_search.py tests/test_research_dna_cli.py` -> passed
- `./scripts/run_meeting_pack_verify.sh` -> passed
- `python3 scripts/lint_docs.py` -> passed
- `cd frontend && npm run e2e:backend:real-smoke` -> passed
- `cd frontend && npm run build` -> passed
- `cd frontend && npm run verify:frontend:backend` -> passed after aligning paper-note detail E2E expectations with the `Saved state` panel
- bounded release rehearsal result -> `green enough`
- representative `Meeting Pack` closeout -> a newer non-fixture journal-club pack now exists with `readiness = evidence_backed`, `can_regenerate = true`, and trace coverage for `zoterocoricTargetingProdromalAlzheimer2015`

### 2. Second action only if historical polish matters: keep older artifacts in the right role

Only do this after the successful representative rerun, release-set pass, and representative `Meeting Pack` closeout.

Most credible remaining small follow-ups:
- keep older non-fixture packs documented as historical reference artifacts, not demo representatives
- provenance/trust wording or status consistency only if a concrete external-demo gap still appears

Do not default to:
- new feature lanes
- `Project` promotion
- broad `Decision` / `Task` / `Experiment` object modeling
- reopening memory/chat/product-platform framing

### 3. Third action only if later worth the cost: bounded legacy backfill

This is no longer a first-product blocker.

Possible later follow-up:
- backfill a bounded subset of legacy/partial papers into canonical note-side state
- or leave them as inspectable historical bundles outside the launch-defining slice

Primary anchor:
- `docs/reports/Deep_Read_Legacy_Bundle_Release_Boundary_2026-03-25.md`

Do not:
- reopen artifact-first fallback
- widen note detail into a second structured-state assembly path
- treat legacy backfill as required to preserve the current first-product story

## Current Do / Do Not

Do:
- prioritize release rehearsal over more architecture prose
- treat the deep-read/job path as green on the bounded current-runtime proof slice
- keep the product boundary paper-centered, paper-first, single-operator-first
- keep legacy bundles outside the launch-defining slice unless explicitly backfilled later

Do not:
- reopen `Project`, memory/chat, or generalized workspace lanes
- convert legacy-data gaps into a broad storage-contract redesign
- treat earlier failed reruns as the current runtime truth after the successful representative rerun and explicit release-boundary decision
- spend the next pass on UI polish unless a concrete release blocker requires it

## Completion Condition

This note has done its job if the next person can answer all three questions immediately:

1. what is the highest-value remaining runtime proof step?
2. what exact verification set should run after that?
3. what should stay out of scope while closing the release bar?

## Conclusion

The current best next move is no longer “one more closeout PR.”

It is:
- treat the current repo as demo-ready on the bounded current-runtime slice
- only do smaller historical cleanup if it materially helps the external story

Anything broader than that is probably scope drift.
