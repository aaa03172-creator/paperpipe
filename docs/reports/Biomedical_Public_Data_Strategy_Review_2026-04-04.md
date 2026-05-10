# Biomedical Public Data Strategy Review (Repo-Grounded)

Date: 2026-04-04
Scope: Compare two user-provided dataset strategy documents against the current PaperPipe repo, then restate the recommendation under both conservative and expansion-friendly assumptions.
Status: Analysis record with follow-up implementation updates. Canonical runtime ownership remains unchanged; landed work stays in additive sidecar/eval lanes.

Update (same day):

- initial v1 implementation has now landed as a bounded additive sidecar:
  - `src/schemas/evidence_extraction.py`
  - `src/services/evidence_extraction_sidecar.py`
  - `backend/services/job_runner.py` write-time wiring
  - `backend/main.py` artifact exposure
- `BC5CDR` evaluator scaffolding has also landed:
  - `src/schemas/bc5cdr_eval.py`
  - `src/services/bc5cdr_eval.py`
  - `scripts/eval/evaluate_evidence_extraction_bundle.py`
  - `tests/test_bc5cdr_eval.py`
- current v1 scope is intentionally narrow:
  - claim-backed records from `claimset.resolved.json`
  - optional artifact-backed scalar field records from `clinical_extraction.json`
  - no canonical state promotion changes
  - `BC5CDR` gold comparison is now possible for entity/relation-shaped bundle records
  - no `BioRED` adapter yet

Update (2026-04-07):

- the first gold-alignment follow-up has now landed:
  - `src/services/bc5cdr_adapter.py`
  - `scripts/eval/convert_bc5cdr_to_evidence_bundle.py`
  - `tests/test_bc5cdr_adapter.py`
- this adds a bounded adapter path from `BC5CDRDocument` into `evidence_extraction_bundle.json`
- the adapter keeps the repo contract intact:
  - no second canonical truth store
  - no structured-state promotion changes
  - no runtime-default extractor promotion
- practical effect:
  - `BC5CDR` gold docs can now be converted into the bundle contract directly
  - bundle projection and bundle evaluation can be tested end-to-end against gold docs
  - the next widening step is `BioRED` contract coverage or a bounded prediction path that emits bundle-native entity/relation records

Update (2026-04-07, later):

- the first bounded prediction path has now landed in the eval lane:
  - `src/services/bc5cdr_prediction.py`
  - `scripts/eval/generate_bc5cdr_bundle_predictions.py`
  - `tests/test_bc5cdr_prediction.py`
- this adds a repo-native path from `document artifact -> BC5CDR-style prediction -> evidence_extraction_bundle.json -> BC5CDR eval report`
- important boundary details:
  - still no canonical structured-state promotion
  - still no runtime-default extractor promotion
  - still no second truth store
- practical effect:
  - the bundle contract can now be populated from real model predictions, not only gold adapters
  - `BC5CDR` evaluation now measures relation structure on span-anchored endpoints even when normalized IDs are missing
  - the next widening step is `BioRED` contract coverage and optional novelty handling on the same sidecar lane

Update (2026-04-07, BioRED first pass):

- the first `BioRED` contract pass has now landed:
  - `src/schemas/biored_eval.py`
  - `src/services/biored_adapter.py`
  - `src/services/biored_eval.py`
  - `scripts/eval/convert_biored_to_evidence_bundle.py`
  - `scripts/eval/evaluate_biored_evidence_bundle.py`
  - `tests/test_biored_adapter.py`
  - `tests/test_biored_eval.py`
- this keeps the same bounded sidecar lane and adds:
  - generic biomedical entity/relation gold projection
  - `BioRED` bundle round-trip and evaluator coverage
  - optional relation novelty in the first pass rather than deferring it
- important boundary details:
  - still no canonical structured-state promotion
  - still no runtime-default extractor promotion
  - still no second truth store
- practical effect:
  - `BC5CDR` is no longer the only gold contract on the lane
  - `BioRED` relation richness and novelty can now be measured against `evidence_extraction_bundle.json`
  - the next widening step is either a bounded `BioRED` prediction path or a decision about whether any stable bundle signals deserve promotion into canonical state

Update (2026-04-07, BioASQ retrieval/evidence eval):

- the first `BioASQ`-style retrieval/evidence evaluator has now landed on the `Research DNA` lane:
  - `src/schemas/bioasq_eval.py`
  - `src/services/bioasq_eval.py`
  - `scripts/eval/evaluate_bioasq_research_dna_run.py`
  - `tests/test_bioasq_eval.py`
- this adds a bounded evaluator path from `Research DNA` pilot artifacts to a BioASQ-shaped report:
  - `screening_queue.jsonl` -> candidate/snippet/answer-alias metrics
  - optional `metrics.json` backfill under `bioasq_eval`
- the retrieval calibration follow-up is now also present in the same lane:
  - candidate first-hit rank
  - candidate reciprocal rank / MRR
  - candidate average precision / MAP
  - candidate nDCG@10
- the rerank-ready label export follow-up is now also present in the same lane:
  - per-question ranked candidate rows
  - binary support flags for identifier/snippet/answer overlap
  - bounded graded relevance for downstream rerank experiments
  - optional `metrics.json` backfill with rerank-label summary counts
- the bounded rerank experiment follow-up is now also present in the same lane:
  - original ranking vs heuristic rerank comparison
  - top-1 hit rate / MRR / MAP / nDCG@10 deltas
  - optional `metrics.json` backfill with rerank experiment summary
- important boundary details:
  - still no canonical structured-state promotion
  - still no runtime-default reranker promotion
  - still no second truth store
- practical effect:
  - public-data coverage now spans both extraction-sidecar eval and retrieval/evidence eval
  - `BioASQ` can be used to assess `Research DNA` candidate recall and evidence-text support without redesigning the runtime
  - `BioASQ` can now also surface bounded ranking quality signals suitable for rerank-ready calibration work
  - `BioASQ` can now also emit rerank-ready label rows from the same lane without promoting a runtime reranker
  - `BioASQ` can now also run a bounded rerank experiment from those labels without promoting a runtime reranker
  - the next meaningful choice is whether to turn that experiment into a real rerank worker slice or return to richer extraction prediction on the `BioRED` side

Update (2026-04-08, Research DNA rerank worker slice):

- the recommended `Research DNA` follow-up has now landed as an explicit bounded worker path:
  - `src/profiles/research_dna_service.py`
  - `src/profiles/research_dna_schema.py`
  - `src/schemas/research_dna.py`
  - `backend/main.py`
  - `src/cli.py`
  - `tests/test_research_dna_service.py`
  - `tests/test_research_dna_api.py`
  - `tests/test_research_dna_cli.py`
- this adds an explicit sibling artifact materialization step for an existing pilot run:
  - `screening_queue.jsonl` remains the original pilot owner
  - `reranked_screening_queue.jsonl` is written as a derived sibling artifact
  - `rerank_report.json` records algorithm/version/actor/score summary
  - `metrics.json` gets a bounded `research_dna_rerank` summary
- important boundary details:
  - still no canonical structured-state promotion
  - still no silent replacement of the original pilot queue
  - still no runtime-default reranker promotion
  - still no second truth store
- practical effect:
  - `BioASQ`-driven ranking work now has a real repo-native worker landing zone instead of only an offline experiment lane
  - rerank output can be inspected and consumed as a file-backed derived artifact with explicit provenance
  - the new opt-in consumption surface is now also present:
    - FastAPI `GET /research-dna/{dna_id}/runs/{run_id}/screening-queue?variant=original|reranked`
    - CLI `paperpipe research-dna queue --variant original|reranked`
  - the next-candidate operator flow is now also present:
    - FastAPI `GET /research-dna/{dna_id}/runs/{run_id}/next-screening-candidate?variant=original|reranked`
    - CLI `paperpipe research-dna next --variant original|reranked`
  - the screening-session snapshot flow is now also present:
    - FastAPI `GET /research-dna/{dna_id}/runs/{run_id}/screening-session?variant=original|reranked`
    - CLI `paperpipe research-dna session --variant original|reranked`
  - the screening-advance operator flow is now also present:
    - FastAPI `POST /research-dna/{dna_id}/screening/advance`
    - CLI `paperpipe research-dna screen-next --variant original|reranked`
    - the advance response can now carry a refreshed bounded session snapshot, so operators can write one decision and immediately inspect the updated queue state without a second read round-trip
  - the current-next screening shortcut is now also present:
    - FastAPI `POST /research-dna/{dna_id}/screening/current`
    - CLI `paperpipe research-dna screen-current --variant original|reranked`
    - it consumes the current next candidate for the chosen variant and can optionally guard on `expected_candidate_id` to avoid stale operator actions
  - the new session shell stays read-only and additive: it summarizes queue state, recent screening decisions, and the next candidate without changing the original pilot owner
  - the next meaningful choice is now whether to deepen operator-side screening ergonomics beyond this bounded session shell and current-next shortcut or return to richer extraction prediction on the `BioRED` side

Update (2026-04-13, repo-grounded replay coverage and bootstrap audit):

- the bounded public-data lanes now each have repo-resident replay coverage:
  - `BC5CDR` prediction replay manifest
  - `BioRED` prediction replay manifest
  - `PubTatorCentral` silver batch manifest
  - `BioASQ` repo-grounded run fixture
- a compact audit surface is now also present:
  - `scripts/eval/check_public_data_bootstrap_status.py`
  - `tests/test_public_data_bootstrap_status.py`
- practical effect:
  - the repo can now summarize, from saved local fixtures, which public-data lanes are replay-ready today
  - the same audit also makes the remaining boundary explicit: public data is enough for bounded eval/bootstrap lanes, but still not enough for project-context relevance, state-transition supervision, artifact-generation supervision, or default runtime promotion

Update (2026-04-13, internal-data readiness audit):

- the companion internal-data audit is now also present:
  - `scripts/eval/check_internal_data_readiness.py`
  - `tests/test_internal_data_readiness.py`
  - `docs/reports/Internal_Data_Readiness_For_Biomedical_Workspace_2026-04-13.md`
- practical effect:
  - the repo now has a compact, code-backed summary of which proprietary-data surfaces already exist
  - the audit confirms that human correction and bounded state-transition telemetry already exist in usable form
  - the cleanest remaining gap is explicit artifact-generation supervision, not a missing generalized workspace-memory substrate

## Executive Summary

The two external memos agree on the high-order shape:

- public data is enough to bootstrap parser quality, narrow extraction, and evidence-linking components
- public data is not enough for project-context ranking, time-series state transitions, or downstream artifact supervision
- license and rights-chain discipline matter as much as benchmark quality

The main disagreement is not about whether the datasets are good. It is about which product shape they assume.

- Document A assumes a faster move toward an end-to-end biomedical agent stack and therefore rates `TrialSieve`, `Docling`, `SciFact`, `ScholarQABench`, and `SciRIFF` more aggressively
- Document B assumes a tighter repo-fit, evaluator-first, and rights-safe bootstrap path and therefore rates `BC5CDR`, `BioRED`, `PubTatorCentral`, `BioASQ`, and layout/table datasets more highly

For the current repo, Document B is the better default anchor.

If broader changes are allowed, the recommendation changes only partly:

- `BioRED` and `BioASQ` move up
- the first move becomes defining a bounded `evidence extraction bundle` sidecar contract
- `TrialSieve` rises only if the product wedge narrows toward trial-centric review
- `ScholarQABench` and `SciRIFF` remain too early

## A. Current Repo Shape

### Data flow

Current runtime is paper-first and run/artifact-first.

- ingest -> document artifact
- index -> chunks/index artifact
- read -> claimset / resolved claimset
- optional verify -> stats report
- handoff artifacts
- note/state promotion

Primary runtime owner references:

- `backend/services/job_runner.py`
- `src/services/deepread_state_projection.py`
- `src/services/deepread_handoff_artifacts.py`
- `src/profiles/research_dna_service.py`

### Storage structure

- per-run bundles under `storage/artifacts/{paper_segment}/{run_id}/`
- promoted note-backed structured state under `vault/.pp/{slug}/state.json`
- SQLite-backed paper metadata / runtime state via `src/db_utils.py`
- evaluator and pilot assets already live under `goldset/` and `snapshots/`

### Agent / service boundary

Current canonical owner is still the paper/job/artifact runtime, not a broad universal research graph.

- canonical state: `StructuredPaperState` in `src/schemas/skills.py`
- extraction contracts: `BiomedicalClinicalExtraction` and `SpecialtyTrialExtraction` in `src/schemas/core.py`
- retrieval/search refinement: `Research DNA`
- downstream surfaces: Meeting Pack, Method Comparison, Chart Pack, Image Evidence, Protocol Knowledge

### What this means for data strategy

The repo already likes:

- additive sidecars
- bounded artifact families
- explicit lineage
- evaluator-first adoption

The repo explicitly resists:

- second canonical truth stores
- large knowledge-graph-first redesigns
- silent runtime replacement based on narrow benchmark wins

This matters because the best public data strategy is not "train a new end-to-end agent." It is "add bounded extraction/evidence capabilities without breaking the current canonical owner."

## B. Comparison of the Two External Documents

| Topic | Document A | Document B | Repo-grounded judgment | Re-verify needed |
| --- | --- | --- | --- | --- |
| Public data scope | Can get close to product-ready baseline for parsing, extraction, verification | Can bootstrap component lanes, but public data is not enough for full workspace behavior | B is more precise for this repo | No |
| Parser strategy | Adopt Docling now as core engine; use DocLayNet if needed | Use layout/table datasets to improve ingestion quality | For this repo, neither "Docling default now" nor "train our own parser first" is the right first move. Keep Docling in the current optional hybrid lane | No |
| Extraction strategy | TrialSieve should be the core extraction asset | BC5CDR, BioRED, PubTatorCentral are safer bootstrap assets | B fits the current repo better. A becomes more plausible only if the product wedge narrows to trial review | No |
| Verification strategy | SciFact is the clearest first verifier asset | SciFact + BioASQ are useful for evidence-linked loops | B is more realistic. SciFact should stay eval-first until license surface is re-confirmed | Yes |
| Downstream generation | ScholarQABench and SciRIFF deserve early attention | Public data for artifact generation is weak and risky | B is more credible for current product stage | No |
| License posture | Flags multiple NC / taint risks, including BioRED ambiguity | Prioritizes NCBI/NLM public-domain resources | A is directionally helpful on legal caution, but too pessimistic on current NCBI FTP BioRED packaging | Yes |
| Internal data boundary | Personalization and artifact quality eventually need internal data | Ranking, state transition, and artifact supervision need internal data early | B is the better operating model | No |

## C. Shared Conclusions That Survive Double-Check

### Strong common ground

- public data can support parser baselines, extraction baselines, and evidence-linking baselines
- public data alone does not provide high-quality labels for workspace-specific ranking, state transitions, or artifact supervision
- rights-chain risk is highest where datasets aggregate upstream corpora or mix multiple constituent benchmarks
- the first useful assets are the ones that connect directly to provenance and structured state, not just leaderboard tasks

### Where both documents overreach if read too literally

- public evidence datasets do not automatically create product-grade biomedical verification
- parser benchmark quality does not by itself justify runtime-default parser replacement
- good scientific QA or instruction-tuning sets do not automatically map to PaperPipe's artifact-first workspace

## D. Conservative vs Expanded Recommendation

### D1. Conservative path

Use the current repo shape as-is and add only bounded evaluator/bootstrap assets.

Adopt now:

- `BC5CDR`
- `PubTatorCentral`
- `Docling` only as the already-approved optional hybrid parser lane

Look next:

- `BioRED`
- `BioASQ`
- `SciFact` as eval-only after license re-check
- `PubLayNet`, `PubTabNet`, `PubTables-1M`
- `TrialSieve` only as a specialty sidecar experiment

Hold:

- `ScholarQABench`
- `SciRIFF`

### D2. Expanded path

Allow a broader but still repo-native extension:

- add a new bounded `evidence extraction bundle` or sibling sidecar artifact family
- do not replace canonical structured state ownership
- do not begin with a large standalone knowledge graph

Under this assumption, the recommended stack becomes:

- gold: `BC5CDR` + `BioRED`
- silver bootstrap: `PubTatorCentral`
- retrieval/evidence loop: `BioASQ`
- parser lane: keep `Docling hybrid`; revisit layout training only if parser quality becomes the bottleneck

This is broader than the conservative path, but it still respects the repo's artifact-first and bounded-sidecar posture.

### D3. Trial-centric wedge variant

If the product wedge intentionally narrows to clinical-trial review:

- `TrialSieve` moves into the top tier
- a trial-specific extraction bundle becomes justified
- broad biomedical relation modeling can move behind it

This is a real strategy change, not just a dataset swap.

It requires an explicit product decision because current repo posture keeps specialty runtime blocked by default and treats sidecar extraction as the canonical signoff lane.

## E. Special Review of the Named Assets

| Asset | Role | Strengths | Main risks | License / ops note | Repo position | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| Docling / DocLayNet | parser runtime / parser training data | practical parser value, permissive surface, strong table/layout utility | current repo evidence supports only bounded hybrid use, not default promotion | `Docling` MIT, Granite Docling Apache-2.0, DocLayNet CDLA-Permissive-1.0 | parser backend / eval lane | `Docling now`, `DocLayNet later` |
| TrialSieve | trial-centric structured extraction | CC0, hierarchical intervention/comparator structure | abstract-centric, trial-specific, can pull product scope toward trial review | CC0-1.0 confirmed | specialty sidecar or future trial lane | `Later`, unless wedge becomes trial-first |
| SciFact | claim-evidence-stance verification | clear rationale supervision | claim style is synthetic/scientific, not a full biomedical workspace proxy; public license surface still looks inconsistent across distribution points | re-verify before product training | evaluator / verifier prototype | `Later`, eval-first only |
| BioASQ | evidence-linked biomedical QA / retrieval | explicit question -> snippet -> answer loop | registration gate, task decomposition still needed | official datasets page says CC BY 2.5 with registration flow | Research DNA eval / rerank / grounded generation | `Now` under expanded path, otherwise `Later` |
| BC5CDR | chem/disease extraction and relation baseline | small, clean, public-domain packaging, direct provenance fit | narrow schema, abstract-level | NCBI FTP public-domain notice | extraction evaluator / baseline | `Now` |
| BioRED | richer document-level relation + novelty | closer to deep read than BC5CDR | higher schema and integration complexity | NCBI FTP public-domain notice | extraction bundle gold / evaluator | `Now` under expanded path, otherwise `Later` |
| PubTatorCentral | large-scale weak supervision | scale, coverage, updates, ontology-linked annotations | noisy labels, operations at scale, not gold truth | NCBI / public bulk access; use with provenance discipline | silver bootstrap, indexing, coverage eval | `Now` |
| PubLayNet / PubTabNet / PubTables-1M | parser/layout/table training | useful if parser training becomes necessary | storage/training cost, source-page rights-chain tracking, may widen scope too early | annotations are permissive but source-page obligations still matter | parser R&D lane | `Later` |
| ScholarQABench | cited scientific synthesis benchmark | attractive downstream artifact benchmark | constituent-license chain, too downstream for current bottlenecks | benchmark/test bundle requires constituent dataset compliance | late evaluator only | `Hold` |
| SciRIFF | instruction tuning for scientific workflows | potentially useful for local-model alignment | upstream source-task license chain, weak direct mapping to current bottlenecks | Apache-2.0 repo, but upstream task provenance still matters | late research only | `Hold` |

## F. Core Conflict Checks

### F1. TrialSieve-first vs BC5CDR/BioRED/PubTatorCentral-first

For the current broad biomedical workspace:

- `BC5CDR/BioRED/PubTatorCentral` should win first
- they align better with paper-scoped evidence extraction, ID normalization, and relation grounding
- they do not force the product to become trial-centric

For a trial-review wedge:

- `TrialSieve` can become the lead dataset
- but that is a product choice, not just a technical optimization

### F2. Immediate Docling adoption vs self-training parser on PubLayNet family

Both extremes are wrong for this repo right now.

The better answer is:

- keep the current `Docling` hybrid lane
- continue explicit parser/fallback audits
- only open PubLayNet-family training if parser quality becomes the top bottleneck

### F3. SciFact / BioASQ as evidence verification core

Realistic:

- component-level evaluation
- evidence sentence selection
- stance/rationale prototypes

Not realistic by themselves:

- full biomedical evidence verification
- workspace-grade state-update supervision
- high-trust artifact finalization

### F4. ScholarQABench / SciRIFF now or later

Still later.

Even after broadening scope, current leverage is higher in:

- extraction repeatability
- normalized IDs and relation grounding
- evidence anchoring
- retrieval/evidence loop quality

### F5. What public data can do vs where internal data becomes mandatory

Public data can cover:

- parser/layout baselines
- entity/relation extraction baselines
- evidence-linking components
- weak supervision bootstrap

Internal data becomes mandatory for:

- project-context relevance ranking
- `(previous state, new evidence) -> updated state` supervision
- artifact generation grounded in current workspace state
- human correction learning loops

## G. Recommended First Move

### Conservative first move

Build a `BC5CDR` sidecar evaluator and prove that PaperPipe can emit:

- mention spans
- normalized IDs
- relation edges
- source-anchored evidence

without changing runtime canonical ownership.

### Expanded first move

Define a bounded `evidence extraction bundle` artifact family first, then target it with:

- `BC5CDR` + `BioRED` as gold
- `PubTatorCentral` as silver bootstrap

This is the best first move if broader changes are allowed because it:

- respects current canonical owners
- makes later trial-specific or QA-specific assets composable
- creates one place to measure relation grounding and evidence lineage

### Why this wins over TrialSieve-first

- broader biomedical fit
- stronger compatibility with current repo contracts
- lower risk of over-committing to one product wedge too early

Implementation note:

- v1 of this step is now present as `evidence_extraction_bundle.json`
- v1 should be treated as contract scaffolding plus current-runtime projection, not as a finished biomedical entity/relation extractor
- `BC5CDR` adapter coverage is now present for bundle conversion and end-to-end gold-eval checks
- a bounded `BC5CDR` prediction generator is now present for document-artifact-driven bundle population and eval
- `BioRED` gold adapter/evaluator coverage is now present, including first-pass optional novelty scoring
- `BioASQ` retrieval/evidence evaluator coverage is now present on the `Research DNA` lane, including optional run-metrics backfill
- `BioASQ` ranking calibration metrics are now present on the `Research DNA` lane without changing runtime ownership
- rerank-ready label export is now present on the `Research DNA` lane without changing runtime ownership
- a bounded rerank experiment is now present on the `Research DNA` lane without changing runtime ownership
- the next meaningful upgrade is to decide whether to turn that rerank experiment into a real rerank worker slice or add a bounded `BioRED` prediction path while bundle summary signals remain sidecar-only

## H. Internal Data Flywheel Recommendation

### H1. Project-context relevance

Start logging:

- workspace state hash
- query / reformulation
- viewed papers / passages
- accept, reject, save, cite, reopen actions

Target training object:

- `(workspace_state, query, candidates) -> pairwise or listwise preference`

### H2. State transition

Start storing:

- previous structured state snapshot
- new evidence references
- proposed update
- human patch
- accepted final delta

Target training object:

- `(previous state, new evidence) -> updated state + rationale`

### H3. Artifact generation

Every artifact draft should retain:

- source state version
- evidence references
- user edits
- approval / rejection outcome

Target training object:

- `(state snapshot) -> artifact draft + grounded edits`

### H4. Human correction

Treat the following as gold, not as disposable UI events:

- evidence relinking
- entity/relation correction
- claim merge/split
- artifact sentence-level edits

### H5. Logging shape

Minimum durable fields:

- `paper_id`
- `paper_slug`
- `run_id`
- `state_version`
- `artifact_id`
- `claim_id`
- `evidence_id`
- `model/prompt hash`
- `before`
- `after`
- `user action`
- `timestamp`

## I. Recommended Execution Order

1. Decide whether PaperPipe remains a broad biomedical workspace or intentionally narrows to a trial-review wedge.
2. If broad: define the bounded `evidence extraction bundle` contract and run `BC5CDR` / `BioRED` against it.
3. Add `PubTatorCentral` only after the gold evaluator exists.
4. Add `BioASQ` as a retrieval/evidence evaluator for `Research DNA`.
5. After `BioASQ` lands, add bounded ranking calibration metrics on `Research DNA`.
6. Then add rerank-ready label export on `Research DNA`.
7. Then add a bounded rerank experiment on `Research DNA`.
8. Then decide whether the next leverage is a real rerank worker slice or `BioRED` prediction support.
9. Revisit `SciFact` only after license surface is re-confirmed.
10. Leave `ScholarQABench` and `SciRIFF` out of the first implementation wave.

Implementation status update:

- steps 2 through 8 are now materially landed in bounded form:
  - `BC5CDR` gold/prediction coverage exists on `evidence_extraction_bundle.json`
  - `BioRED` gold/eval/prediction coverage exists on the same bundle lane
  - a repo-resident `BioRED` replay manifest now pressure-tests that lane on local pages/sections fixtures
  - `PubTatorCentral` silver bootstrap now projects PubTator-style annotations into the same bundle lane with explicit silver provenance
  - a repo-resident `PubTatorCentral` batch manifest now materializes multiple silver source docs into per-document bundle outputs plus run-level summary/metrics
- `BioASQ` eval, ranking calibration, rerank labels, rerank experiment, and bounded rerank worker support exist on `Research DNA`
- `Research DNA` now also has an advisory-only screening recommendation surface that compares `original` and `reranked` queues without changing owner/default status
- `Research DNA` now also has a bounded rerank gate report that classifies the current rerank state as `eligible`, `not_eligible`, or `insufficient_signal` without changing owner/default status
- the next repo-fit decision is no longer whether to add `BioRED` prediction support itself or whether to add first silver bootstrap support, but whether to widen the new extraction replay/bootstrap batch lanes or keep deepening operator-default behavior on retrieval

## J. Source Notes

Repo sources reviewed:

- `README.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `backend/services/job_runner.py`
- `src/services/deepread_state_projection.py`
- `src/services/deepread_handoff_artifacts.py`
- `src/schemas/skills.py`
- `src/schemas/core.py`
- `src/profiles/research_dna_service.py`
- repo-local reports on Docling posture, extraction posture, and hard-PDF eval

External source notes reviewed:

- user-provided document A: `Biomedical AI 연구 데이터셋 조사.txt`
- user-provided document B: `deep-research-report-5.md`
- official / primary source checks for `BC5CDR`, `BioRED`, `TrialSieve`, `Docling`, `Granite Docling`, `DocLayNet`, `PubLayNet`, `PubTabNet`, `PubTables-1M`, `BioASQ`, `PubTatorCentral`, `SciFact`, `ScholarQABench`, and `SciRIFF`

## K. Final Judgment

The best default strategy is still not "pick one flashy dataset."

For PaperPipe, the correct move is:

- stay evidence-first and artifact-first
- use public data to harden bounded extraction/evidence components
- build one reusable sidecar contract before widening training scope
- save the proprietary moat for project-context relevance, state transitions, and artifact correction

Under current repo reality, that means Document B remains the better default anchor.

Under broader modification scope, the recommendation broadens to `BC5CDR + BioRED + PubTatorCentral + BioASQ`, but still does not justify moving `ScholarQABench` or `SciRIFF` into the first wave.
