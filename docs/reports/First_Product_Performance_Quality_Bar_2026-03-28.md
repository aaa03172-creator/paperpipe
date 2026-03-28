# First Product Performance & Quality Bar (2026-03-28)

Status: active summary note
Date: 2026-03-28
Owner: Runtime/product maintainers
Purpose: consolidate the current repo-grounded first-product performance/quality bar into one tracked note without inventing a new SLA layer.

## Why this note exists

The current repo already has release/readiness evidence, but the bar is spread across several notes:
- release rehearsal
- demo FAQ
- installability audit
- deferred-lane posture
- `Research DNA` quality policy

This note summarizes those existing criteria in one place.

This is not:
- a new runtime spec
- a new roadmap
- a promise of global latency or throughput SLA

## Bottom-line judgment

Current judgment on the bounded first-product slice:
- launch/release bar: **met**
- runtime/installability bar: **met for the bounded launcher-first local runtime story**
- search-quality bar: **met for the current bounded `Research DNA` lane**
- broad platform bar: **intentionally not in scope**

The current product can be presented honestly as:

> a local-first, paper-centered biomedical research workspace for one primary operator

## 1. Launch / release gate

This is the current top-level first-product bar.

| Area | Current bar | Current status | Source |
| --- | --- | --- | --- |
| Product story honesty | Must be demoable without hidden-truth narration | met | `Release_Rehearsal_Run_2026-03-25.md` |
| Must-Not-Ship rows | All must remain `false` | met | `Release_Rehearsal_Run_2026-03-25.md` |
| Core bounded loop | `paper -> structured understanding -> evidence review -> reproducible search design -> meeting-ready artifact` must be executable | met | `First_Product_Demo_FAQ_2026-03-27.md` |
| Scope discipline | No dependency on `Project`, chat/copilot-first, broad memory, or generalized workspace lanes | met | `First_Product_Demo_FAQ_2026-03-27.md`, `Deferred_Lanes_Recheck_2026-03-24.md` |

Practical meaning:
- the launch bar is **not** “every route is perfect”
- the launch bar **is** “the bounded first-product story is credible and honest”

## 2. Runtime / installability bar

There is no tracked global p95 latency SLA.

The current runtime bar is instead:
- launcher-first local runtime is credible
- built UI is served by the backend runtime
- readiness/self-test truthfully report whether the runtime can use its intended config root
- timeouts and partial failures are visible in runtime metadata, not hidden

| Area | Current bar | Current status | Source |
| --- | --- | --- | --- |
| Built UI shell | `/ui` should prefer built frontend assets, not source-only fallbacks | met | `Installability_Audit_2026-03-27.md` |
| Local runtime readiness | `/health/ready` and `lattice self-test` should distinguish readable config from writable config root | met | `Installability_Audit_2026-03-27.md` |
| Deepread timeout visibility | reader timeout budget and timeout-trigger state should be observable in metadata | met | `docs/bootstrap_meta_schema.md` |
| Deepread handoff visibility | handoff artifacts and quality-gate status should be inspectable | met | `Deepread_Handoff_Artifacts_Closeout_2026-03-28.md` |
| Reader/verifier observability | `reader_analysis` and `stats_fallback_eval` should be bounded runtime metadata, not hidden behavior | met | `Deepread_Runtime_Followups_Closeout_2026-03-28.md` |

Important non-goal:
- no tracked promise currently says “all deepread jobs complete within X seconds”

## 3. Retrieval / search-quality bar

This is the clearest numeric quality bar in the current repo.

`Research DNA` uses bounded evaluation metrics and promotion rules instead of vague “good search” claims.

Tracked metrics:
- `precision_proxy`
- optional `goldset_recall`
- optional `external_benchmark_recall`
- optional hit/total counts for those recalls

| Area | Current bar | Current status | Source |
| --- | --- | --- | --- |
| Search quality comparison | Query versions must be comparable through fixed eval artifacts and append-only run logs | met | `docs/RESEARCH_DNA.md` |
| Keep/discard policy | Decisions use `labeled_count + precision_delta + optional goldset/external benchmark deltas` rather than intuition only | met | `docs/RESEARCH_DNA.md` |
| External benchmark promotion | Stronger promotion requires adjudicated benchmark evidence, not just one optimistic run | met | `docs/RESEARCH_DNA.md` |
| Current bounded benchmark result | Current promoted probe reached `external_benchmark_recall = 1.0 (6/6)` on the approved union benchmark | met | `docs/RESEARCH_DNA.md` |

Important non-goal:
- this does **not** mean retrieval is globally solved for every topic
- it means the current bounded `Research DNA` lane has a real measurable bar

## 4. What is intentionally *not* the first-product bar

These should not be mistaken for launch-blocking performance criteria:

- global API latency SLA
- end-to-end ingest throughput SLA
- parser benchmark leadership
- multi-user collaboration
- project-first runtime
- broad workspace memory
- generalized chat/copilot workflow
- extension lanes such as `Method Comparison`, `Chart Pack`, `Image Evidence`, or `Protocol Knowledge`

Those may be real bounded lanes, but they are not the first-product identity.

## 5. The simplest decision rule

If someone asks “can we ship/demo this bounded first product honestly?”, the current rule is:

1. `Release_Rehearsal_Run_2026-03-25.md` stays green enough
2. all `Must-Not-Ship` rows remain false
3. launcher/runtime readiness remains truthful
4. `Research DNA` remains measurable through its existing quality contract
5. deferred platform lanes stay deferred

If those stay true, the first-product bar still holds.

## 6. What is still allowed to be weak

The current first-product bar allows weakness in:
- polish
- optional housekeeping
- historical artifact cleanup
- deferred platform lanes
- non-core extension viewers

It does **not** allow weakness in:
- truth visibility
- provenance honesty
- bounded core loop credibility
- pretending deferred lanes are already part of the live product

## References

- [Release_Rehearsal_Run_2026-03-25.md](/Users/jangseongjin/paperpipe/docs/reports/Release_Rehearsal_Run_2026-03-25.md)
- [First_Product_Demo_FAQ_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/First_Product_Demo_FAQ_2026-03-27.md)
- [Installability_Audit_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Installability_Audit_2026-03-27.md)
- [Deferred_Lanes_Recheck_2026-03-24.md](/Users/jangseongjin/paperpipe/docs/reports/Deferred_Lanes_Recheck_2026-03-24.md)
- [bootstrap_meta_schema.md](/Users/jangseongjin/paperpipe/docs/bootstrap_meta_schema.md)
- [Deepread_Handoff_Artifacts_Closeout_2026-03-28.md](/Users/jangseongjin/paperpipe/docs/reports/Deepread_Handoff_Artifacts_Closeout_2026-03-28.md)
- [Deepread_Runtime_Followups_Closeout_2026-03-28.md](/Users/jangseongjin/paperpipe/docs/reports/Deepread_Runtime_Followups_Closeout_2026-03-28.md)
- [RESEARCH_DNA.md](/Users/jangseongjin/paperpipe/docs/RESEARCH_DNA.md)

## Bottom line

The current first-product bar is real, but it is **not** a single global performance SLA.

It is a bounded combination of:
- honest launchability
- truthful runtime readiness
- inspectable failure/provenance
- measurable search-quality for `Research DNA`
- strict restraint on out-of-scope platform promises
