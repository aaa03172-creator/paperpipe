Status: Active release evidence note  
Date: 2026-03-24  
Owner: Runtime/product maintainers  
Canonical parents:
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

# Deep Read Release Acceptance Spot Check

## Purpose

Run a narrow real-paper acceptance spot check against the current `Minimum Deep Read Success Bar` without opening a new feature lane.

This note is evidence only.
It is not a redesign proposal.
It records a legacy/current-state baseline inspection pass, not the final release judgment by itself.

## Scope

Sampled real papers:
- `zotero:parkDiscoveryDualactionSmall2022`
- `zotero:johnsonLargescaleDeepMultilayer2022`
- `zotero:arnstenNeuromodulationThoughtFlexibilities2012`
- `zotero:craftSafetyEfficacyFeasibility2020`
- `zotero:coricTargetingProdromalAlzheimer2015`

Checked surfaces:
- latest local artifact directory under `storage/artifacts/<paper_id>/...`
- `GET /paper-notes/resolve-by-paper-id`
- `GET /paper-notes/{slug}`
- `GET /papers/{paper_id}`

Did not do in this pass:
- execute a fresh deep-read job
- execute a rerun/regenerate mutation against sampled papers
- widen this lane into Docling/eval, frontend, or feature work

## Method

For each sampled paper, check:
- latest artifact bundle shape
- whether claim payloads include evidence spans
- whether note detail opens against the current backend
- whether the paper/workbench backing route opens against the current backend
- whether canonical structured state is surfaced in note detail
- whether run linkage is surfaced through the current runtime DB/API

## Result Summary

- `pass`: `0/5`
- `partial`: `1/5`
- `fail`: `4/5`

Working judgment:
- the release-scoped deep-read spot check is now complete as a bounded evidence pass
- this note still matters for the legacy/partial sampled slice
- this note no longer stands alone as the current runtime judgment after the later successful representative rerun recorded in `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md`
- this note also no longer defines the launch slice by itself after the explicit boundary decision in `docs/reports/Deep_Read_Legacy_Bundle_Release_Boundary_2026-03-25.md`
- the main issue is no longer “we have not checked”
- the main issue is now narrower: legacy/partial real-paper state surfacing is still weaker than the release bar requires, even though the current rerun path is now greener

## Per-Paper Results

| Paper | Latest artifact shape | Note detail | Paper API | Evidence-linked claims | Verdict | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `zotero:parkDiscoveryDualactionSmall2022` | `bootstrap_meta`, `run_meta`, `claimset`, `claimset.resolved`, `document_artifact`, `index_artifact`, `stats_report` present | `200`, body/references present, `structured_state` missing | `200`, `issues_state=clear`, `ops_summary=Healthy`, `latest_run_id=run_20260313_110600` | yes | `partial` | Best current sample, but canonical note-side structured state is still absent. |
| `zotero:johnsonLargescaleDeepMultilayer2022` | `bootstrap_meta`, `claimset`, `document_artifact`, `index_artifact` present; `run_meta`, `claimset.resolved`, `stats_report` missing | `200`, body/references present, `structured_state` missing | `200`, `ops_summary=Action needed`, `latest_run_id=run_20260223_140928` | yes | `fail` | Real note/workbench backing exists, but current saved-state shape remains legacy/partial. |
| `zotero:arnstenNeuromodulationThoughtFlexibilities2012` | `bootstrap_meta`, `claimset`, `document_artifact`, `index_artifact` present; `run_meta`, `claimset.resolved`, `stats_report` missing | `200`, body/references present, `structured_state` missing | `200`, `ops_summary=Action needed`, `latest_run_id=run_20260223_133239` | yes | `fail` | Same core gap as `johnson`: inspectable note exists, canonical deep-read runtime state does not. |
| `zotero:craftSafetyEfficacyFeasibility2020` | `bootstrap_meta`, `claimset`, `document_artifact`, `index_artifact` present; `run_meta`, `claimset.resolved`, `stats_report` missing | `200`, body/references present, `structured_state` missing | `200`, `ops_summary=Action needed`, `latest_run_id=run_20260223_134233` | yes | `fail` | Viewer surface is real, but release-bar state surfacing remains incomplete. |
| `zotero:coricTargetingProdromalAlzheimer2015` | `bootstrap_meta`, `claimset`, `document_artifact`, `index_artifact` present; `run_meta`, `claimset.resolved`, `stats_report` missing | `200`, body/references present, `structured_state` missing | `200`, `ops_summary=Action needed`, `latest_run_id=run_20260223_134233` | yes | `fail` | Same pattern as other legacy/partial papers in this sample. |

## Key Findings

### Confirmed

1. Real-paper backend note detail is available now.
- `5/5` sampled papers resolved through `GET /paper-notes/resolve-by-paper-id`
- `5/5` note detail pages opened through `GET /paper-notes/{slug}`

2. Real-paper workbench-backing paper state is available now.
- `5/5` sampled papers returned `200` from `GET /papers/{paper_id}`
- `5/5` exposed `issues_state` and `ops_summary`

3. Claims are not bare text-only payloads in the sampled artifacts.
- `5/5` sampled `claimset.json` files included `evidence_spans`

4. Canonical structured state is not currently surfaced in note detail for this sample.
- `5/5` sampled notes returned `structured_state = null`
- `load_structured_state()` only reads the note-side canonical sidecar at `.pp/<slug>/state.json` or a frontmatter `pp.structured_path` override
- sampled real deep-read papers had artifact bundles under `storage/artifacts/...`, but no matching `.pp/<slug>/state.json`

5. Runtime run linkage exists locally and is now surfaced in the paper API.
- sampled papers do have matching `jobs.run_id` rows
- `_latest_run_id_for_paper()` resolves real run ids for all five sampled papers
- current `/papers` and `/papers/{paper_id}` responses now surface `latest_run_id` for the sampled slice after the bounded API patch

6. Most sampled papers still look legacy/partial rather than release-ready.
- `4/5` sampled papers were missing `run_meta.json`
- `4/5` sampled papers were missing `claimset.resolved.json`
- `4/5` sampled papers were missing `stats_report.json`

### Inference

- This sampled baseline shows that older/partial real-paper bundles still do not meet the current canonical deep-read success bar consistently.
- The blocker is not “no real data exists.”
- The older sampled blocker is “real data exists, but the release-bar state shape is not consistently surfaced through the current canonical runtime path.”
- More specifically:
  - note detail expects a note-side `.pp/.../state.json` canonical sidecar, which the deep-read artifact lane is not currently writing for the sampled papers
  - run linkage is now surfaced in `/papers`, but note detail still depends on note-side `.pp` state rather than bridging directly from deep-read artifact bundles

Later evidence now narrows that inference:
- the fresh representative rerun on `zotero:coricTargetingProdromalAlzheimer2015` did complete successfully
- that rerun promoted canonical note-side `.pp/<slug>/state.json`
- so this spot-check note should now be read as a legacy/partial-bundle baseline, not as proof that the current rerun path cannot meet the bar

### Unknown

- This pass did not execute a fresh deep-read rerun, so non-destructive rerun behavior remains unclosed here.
- This pass did not prove whether the missing structured-state/runtime-link gaps are due to older artifact vintages, note-sidecar wiring drift, or DB/runtime persistence gaps.

## Release Implication

This spot check closes one uncertainty and sharpens another:

- closed uncertainty:
  - a bounded real-paper acceptance check is now on record
- remaining release gap:
  - older/partial sampled bundles still do not consistently surface canonical structured saved state and run linkage at the level the current product bar expects
  - the later successful representative rerun means the current runtime path itself is no longer the main blocker

Practical consequence:
- this note should not by itself keep the launch row `yellow`
- the next deep-read blocker is no longer “prove that a representative fresh rerun can succeed”
- the remaining question is only whether later legacy backfill is worth doing after v1

See also:
- `docs/reports/Deep_Read_Structured_State_Gap_2026-03-24.md`
- `docs/reports/Deep_Read_Legacy_Bundle_Release_Boundary_2026-03-25.md`

## Safest Next Actions

1. Use `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md` together with this note so release judgment distinguishes the current rerun path from legacy/partial sampled bundles.
2. Use `docs/reports/Deep_Read_Legacy_Bundle_Release_Boundary_2026-03-25.md` so this legacy baseline stays outside the bounded v1 proof slice unless a later backfill is explicitly chosen.
3. Keep `docs/reports/Deep_Read_Note_State_Promotion_Design_2026-03-24.md` as the bounded implementation note for canonical note-side `.pp/<slug>/state.json` materialization.

## Verification Used

Runtime/data inspection used:
- `sqlite3 storage/state.db ".tables"`
- `sqlite3 storage/state.db "select count(*) as jobs_count from jobs;"`
- `sqlite3 storage/state.db "select count(*) as execution_runs_count from execution_runs;"`
- targeted artifact inspection under `storage/artifacts/<paper_id>/...`
- FastAPI `TestClient` requests against:
  - `/paper-notes/resolve-by-paper-id`
  - `/paper-notes/{slug}`
  - `/papers/{paper_id}`
- `pytest -q tests/test_papers_api.py -k "operational_summary_from_artifacts or latest_run_id_from_jobs"`

## Conclusion

The release-scoped deep-read acceptance spot check is now done.

This specific sampled baseline did not produce a `green` result.

Current best judgment:
- real-paper note/workbench inspection is credible
- evidence-bearing claim payloads exist
- canonical note-side structured-state surfacing is still not strong enough across older sampled bundles to call the whole historical sample uniformly release-ready
- but the later representative rerun and explicit legacy-boundary decision mean the bounded current-runtime launch slice is now materially stronger than this baseline note alone suggests
