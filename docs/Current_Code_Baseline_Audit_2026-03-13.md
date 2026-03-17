# Current Code Baseline Audit

Status: Working baseline audit
Date: 2026-03-13
Branch observed: `codex/agents-smoke-ci-check`
Scope: product intent, development status, runtime architecture, code reality, test status, and immediate regressions

## 0. Executive Summary

This repository is no longer just the original `PaperPipe` research agent runtime. In the current workspace it is being actively expanded into `Lattice`: a broader local-first research operating surface with:

- FastAPI backend
- queue/worker execution
- paper notes viewer and workbench UI
- Obsidian and Zotero integration
- Research DNA workflows
- Meeting Pack generation
- quality/teacher loop utilities

The product direction is coherent. The current checkout can now be exercised as a stable runtime baseline, but it is not yet a stable repository baseline.

The main reasons:

1. the original runtime/test regression was repaired during the audit, so execution is now green
2. the working tree is still heavily in flight, with core feature files left untracked
3. several "completed" items listed in the queue are still only partially reflected in the current code
4. some earlier v2/H0-H2 contract work discussed in planning is still not present in this checkout

## 1. What The Product Is Trying To Be

### 1.1 Canonical product intent

The current canonical spec is `docs/Lattice_v3_Master_Spec.md`.

Confirmed intent:

- product-facing name is `Lattice`
- `paperpipe` remains as a legacy namespace/CLI alias
- architecture is API-first
- runtime center is FastAPI + worker
- Obsidian is the knowledge layer
- Zotero/metadata/PDF pipeline remain core inputs
- structured artifacts remain the backbone for downstream UX

### 1.2 Operational development queue

The most useful "what is happening now" document is `docs/Pending_PR_Queue.md`.

As of 2026-03-13, it shows active momentum on:

- Meeting Pack v1
- Workbench contextual state badges
- paper notes viewer/list UX hardening
- Research DNA v0
- teacher quality regression / quarantine probes

It also claims many backend hardening items are already completed:

- evidence contract
- citation jump MVP
- run profile
- discover queue
- stats trigger
- identity/event log
- buffered event writer
- artifact path `paper_key`
- H2 output contracts
- resolved Obsidian bridge

This queue is directionally useful, but the current checkout must still be verified against it file by file.

## 2. Verified Current Architecture

### 2.1 Confirmed runtime layers

| Area | Current reality | Evidence |
| --- | --- | --- |
| API server | FastAPI app is the main control plane | `backend/main.py` |
| CLI launcher | `paperpipe start` and `lattice start` are both wired | `src/cli.py`, `pyproject.toml` |
| Job queue | SQLite-backed queue with one-open-job guard and backpressure envs | `src/jobs/queue.py` |
| Worker | Polling worker executes `run_deepread_job` | `src/jobs/worker.py` |
| Orchestrator | Deepread pipeline remains centered on `job_runner` | `backend/services/job_runner.py` |
| Viewer API | paper notes list/detail and ops summary APIs exist | `backend/routers/paper_notes.py` |
| Obsidian mirror/sync | Obsidian artifact/mirror routes exist | `backend/routers/obsidian.py` |
| Meeting Pack | generate/get/markdown API exists | `backend/routers/meeting_packs.py`, `src/meeting_packs/service.py` |
| Research DNA | full API/service/store surface exists | `backend/main.py`, `src/profiles/research_dna_service.py` |
| Frontend app | React/Vite app exposes dashboard, paper notes, workbench | `frontend/src/App.tsx` |

### 2.2 Current artifact/runtime conventions that are actually in code

| Concern | Current implementation |
| --- | --- |
| artifact root | `storage/artifacts/{paper_id}/{run_id}` |
| queue identity | `job_id = uuid4`, `run_id = run_YYYYMMDD_HHMMSS` |
| output schema backbone | legacy `src/schemas/agent_artifacts.py` |
| event stream | job log file + SSE replay, not the planned DB-backed run/job event log |
| profiles path | resolved by `src/services/runtime_paths.py` |
| paper notes ops | derived from artifact snapshots, not from an event log |

## 3. Intent vs Implementation

### 3.1 Product direction alignment

| Theme | Intended direction | Current code status | Assessment |
| --- | --- | --- | --- |
| Lattice branding | User-facing product should be `Lattice` | Present in README/spec/API title/CLI alias | Confirmed |
| API-first | Core logic should sit behind FastAPI | Present | Confirmed |
| Worker separation | Long-running pipeline should be worker-driven | Present | Confirmed |
| Paper notes viewer | Obsidian-like reading surface | Present in backend + frontend | Confirmed |
| Meeting Pack | Evidence-linked lab meeting artifact | Present | Confirmed |
| Research DNA | Search-design lifecycle with API/store | Present | Confirmed |
| Structured evidence contracts | Claims/evidence should be structured and reusable | Present only in older `agent_artifacts` form | Partial |
| Stable IDs / memory-ready hooks | paper/job/run/chunk/claim should be standardized for future memory | Not implemented in the expected H0/H1/H2 shape | Missing/Partial |
| Buffered DB event log | expanded execution log schema (`runs + job_events + user_actions`) in SQLite | Not present in current runtime path, although the basic `jobs` queue table does exist | Missing |
| Grounded citation jump via chunk contract | LLM should not own page truth | Not enforced in current claim/evidence flow | Missing/Partial |

### 3.2 What is mature vs what is still transitional

More mature now:

- paper notes viewer/list/workbench
- Meeting Pack
- Research DNA
- quality/teacher loop tooling
- runtime launcher and CI-oriented local gates

Still transitional:

- deepread contract hardening
- artifact identity standardization
- event log architecture
- citation grounding model
- discover queue implementation depth

## 4. Document vs Code Reality

### 4.1 Strong matches

| Documented intent | Code reality | Result |
| --- | --- | --- |
| `Lattice` is the official product name | `FastAPI(title="Lattice API")`, README, master spec | Match |
| CLI alias parity is required | `paperpipe` and `lattice` both point to `src.cli:entrypoint` | Match |
| paper notes viewer/workbench are active surfaces | backend routes and frontend pages exist | Match |
| Meeting Pack v1 is real | service/router/schema/store exist | Match |
| Research DNA is real | schema/store/service/router exist | Match |

### 4.2 Partial matches

| Queue/spec claim | Current code | Assessment |
| --- | --- | --- |
| `PR-BE-Stats-Trigger-v1` completed | queue/job schema has `run_verify`, worker passes it into runner | Partial: trigger concept exists, but broader action/event memory hook is not visible |
| `PR-BE-Citation-Jump-MVP` completed | artifacts/routes mention `claimset.resolved.json`, Obsidian mirror surfaces page quote fields | Partial: no strong deterministic chunk validation path is visible |
| `PR-BE-Discover-Queue-v1` completed | OpenAlex wrapper exists, and legacy related-paper/bibliometric helpers also exist | Partial: there is no clear dedicated OpenAlex-based related-paper queue engine in the current active runtime path |
| `PR-BE-H2-Obsidian-Resolved-Bridge` completed | Obsidian router prefers `claimset.resolved.json` over legacy `claimset.json` | Partial: bridge behavior exists, but not the full H2 contract layer previously discussed |

### 4.3 Clear mismatches

| Queue/spec claim | Current code reality | Why it matters |
| --- | --- | --- |
| `PR-BE-ArtifactPath-PaperKey` completed | runtime still uses `storage/artifacts/{paper_id}/{run_id}` in multiple places | path safety/canonical identity migration is not fully landed |
| `PR-BE-V2-Identity-EventLog` completed | no runtime expanded `runs + job_events + user_actions` DB contract was found in the current active path | memory-ready audit trail is not actually established |
| `PR-BE-EventWriter-Buffered` completed | SSE is still based on log file replay and job polling | observability is file/log driven, not event-log driven |
| `PR-BE-H2-Output-Contracts` completed | current backbone is still `src/schemas/agent_artifacts.py`; no `src/contracts/output_contracts.py` exists | contract migration is not fully present |
| earlier H0/H1/H2 planning assumed `src/core/*` helpers | current `src/core` directory is empty | previous assumptions cannot be treated as current reality |

## 5. Claimed Completed Items vs Actual Files

### 5.1 Items that are genuinely visible in the code

| Item | Visible implementation |
| --- | --- |
| Meeting Pack v1 | `src/meeting_packs/*`, `backend/routers/meeting_packs.py`, `src/schemas/meeting_pack.py` |
| Research DNA v0 | `src/profiles/research_dna_*`, API in `backend/main.py`, `docs/RESEARCH_DNA.md` |
| paper notes operational summary | `src/services/paper_ops_summary.py`, `backend/routers/paper_notes.py`, frontend paper note pages |
| workbench/list operational badges | frontend `OperationalState*` components and paper note pages |
| legacy related-paper helpers | `src/obsidian.py`, `src/ranking.py`, `src/exporter.py` |

### 5.2 Items that look older/legacy but still drive the runtime

| Legacy path still active | Evidence |
| --- | --- |
| `src/schemas/agent_artifacts.py` is still the main artifact schema | imported by reader/obsidian/note writer |
| UUID chunk IDs are still generated at index time | `src/agents/indexer_agent.py` |
| LLM/page-based evidence hints are still allowed | `src/agents/reader_agent.py`, `src/schemas/agent_artifacts.py` |
| `storage/artifacts/{paper_id}/{run_id}` pathing remains active | `backend/main.py`, `backend/routers/obsidian.py`, `src/exporter.py` |

### 5.3 Items that are missing despite being expected from recent planning

| Expected item | Current state |
| --- | --- |
| `src/core/ids.py` | missing |
| `src/core/evidence_resolver.py` | missing |
| `src/contracts/output_contracts.py` | missing |
| `src/db_bootstrap.py` | missing |
| `paper_key` artifact path helper | not found in active runtime path |
| SQLite `job_events` / `user_actions` writer | not found in active runtime path |

## 6. Immediate Regressions And Risks

### 6.1 P0 runtime/test regression (resolved during audit follow-up)

`backend/services/job_runner.py` imports:

- `DEFAULT_PROFILE_PATH`

But `src/profiles/profile_store.py` no longer defines it.

Original impact:

- `pytest --collect-only -q` collected `446` tests
- collection stopped with `7` import errors
- all 7 errors stem from the missing `DEFAULT_PROFILE_PATH` symbol

Affected test modules:

- `tests/test_job_runner_ingest_backend.py`
- `tests/test_job_runner_pdf_lookup.py`
- `tests/test_job_runner_persona.py`
- `tests/test_job_runner_table_meta.py`
- `tests/test_jobs_api_smoke.py`
- `tests/test_worker_interrupt_handling.py`
- `tests/test_worker_job_runner_chain.py`

Follow-up resolution:

- compatibility alias restored in `src/profiles/profile_store.py`
- `backend/services/job_runner.py` updated to snapshot `profiles_config_path()` directly
- `pytest --collect-only -q` now succeeds
- full suite now passes after additional runtime path cleanup: `518 passed, 1 skipped`

### 6.2 Runtime path contract regression (resolved during audit follow-up)

During stabilization, `src/services/runtime_paths.py` had drifted into an inconsistent state:

- `state_db_path()` and related runtime helpers were using `storage_root()`
- `artifacts_root()` had been changed to a separate direct path rule

This broke cross-surface assumptions in:

- frontend real-smoke preflight
- stats repair API
- Obsidian sync/path masking flows

Resolved contract:

1. if `PAPERPIPE_STORAGE_DIR` is set, storage-scoped paths derive from it
2. otherwise, if `PAPERPIPE_HOME` is set, storage defaults to `<paperpipe_home>/storage`
3. otherwise, runtime defaults to the current workspace `storage/`

With this repair, these surfaces are aligned again:

- `state_db_path()`
- `artifacts_root()`
- `meeting_packs_root()`
- scripts that use runtime path helpers

### 6.3 High codebase volatility

The working tree is heavily modified.

Observed characteristics:

- many tracked modifications across backend/frontend/docs/tests
- many untracked feature files
- multiple deleted historical docs
- snapshots and runtime outputs also exist in-tree

Consequence:

- current code reality must be treated as "integration in progress"
- completed queue items cannot be trusted without direct file verification

### 6.4 Contract drift risk

The codebase currently mixes:

- newer product surfaces (`Lattice`, paper notes, meeting packs, research DNA)
- older runtime contracts (`agent_artifacts`, UUID chunk ids, page-owned evidence hints)
- partially landed migration ideas (`claimset.resolved.json`, artifact mirror improvements)

This is manageable, but it means contract decisions have not yet been fully consolidated.

### 6.5 Naming collision risk around `runs`

`src/db.py` already defines a `runs` table for daily run stats keyed by `date`.

That is not the same thing as the planned execution-level `runs` table discussed for memory-ready hooks.

If a future event-log migration also introduces `runs`, it must not reuse this meaning without an explicit migration plan.

## 7. Test And Verification Baseline

### 7.1 Backend

Verified:

- test suite is large enough to matter
- import collection regression is no longer present
- current full-suite baseline is green

Most recent verification:

- `pytest -q`
- result: `518 passed, 1 skipped, 8 warnings`

Focused regressions rechecked and now green:

- frontend real-smoke preflight
- stats repair API
- path masking / Obsidian sync
- Meeting Pack API
- Meeting Pack source resolver
- runtime path helper tests

### 7.2 Frontend

Verified package scripts:

- `build`
- `lint`
- `e2e:mock`
- `e2e:backend`
- `verify:frontend`
- `e2e:backend:real-smoke`

Important:

- there is no generic `npm test` script
- frontend verification is intentionally build/lint/Playwright based

### 7.3 Working-tree baseline candidates

The current runtime baseline depends on several files that are still untracked in git.

Core candidates:

- `backend/routers/meeting_packs.py`
- `src/meeting_packs/source_resolver.py`
- `tests/test_meeting_pack_api.py`
- `tests/test_meeting_pack_source_resolver.py`
- `tests/test_runtime_paths_research_dna.py`
- `docs/Current_Code_Baseline_Audit_2026-03-13.md`

Meaning:

- execution baseline: stable
- repository baseline: not yet frozen

These files are no longer behaving like scratch work. They currently define real runtime behavior and regression coverage.

## 8. Baseline Judgement

### 8.1 What can be treated as real right now

- `Lattice` rebrand and API-first runtime
- queue + worker execution model
- paper notes viewer/workbench
- Meeting Pack implementation
- Research DNA implementation
- quality loop infrastructure
- repaired runtime path contract
- current Meeting Pack selector slice:
  - `paper_slug`
  - `paper_state`
  - `paper_note`
  - `project_note`
  - `research_note`
  - `screening_decision`
  - `topic`
  - projection-backed `project_profile`
  - projection-backed `research_profile`

### 8.2 What is real in execution but not yet fixed as repository baseline

- Meeting Pack router/source-resolver/test package currently lives in untracked files
- the current audit document itself is still untracked
- path-helper refinements exist in modified/untracked form, not a committed baseline

### 8.3 What should not be treated as done yet

- stable identity and paper-key migration
- memory-ready event log
- H2 output contract migration
- deterministic citation grounding
- full related-paper discover queue

## 9. Recommended Next Sequence

1. Freeze the repository baseline around the now-green runtime snapshot.
   - Decide whether the current untracked Meeting Pack/runtime-path/audit files are accepted as canonical working files.
   - Until that happens, execution is reproducible but repository state remains ambiguous.
   - `docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md` is now the concrete baseline-freeze note for this slice, re-verified with the expanded Meeting Pack + projection/profile-store guard set (`90 passed` on 2026-03-17).
   - that note now also narrows the working set to exact source dependencies (`src/skills/storage.py`, `src/services/identity.py`, `src/profiles/profile_schema.py`, etc.), explicitly excludes generated runtime byproducts, and keeps `src/profiles/research_dna_projection.py` out of `PR-M0` because the current Meeting Pack slice consumes projection metadata but does not import the producer module.
   - it also records that `backend/main.py` cannot be adopted as a whole-file diff here; only the narrow `meeting_packs.router` import/include hunk belongs to `PR-M0`.
   - `/Users/jangseongjin/paperpipe/docs/archive/PR_M0_Staging_Dry_Run_2026-03-17.md` now confirms the whole-file and tracked-diff sets are stageable via `git add -n`, while `backend/main.py` still requires edited-patch handling.
   - `/Users/jangseongjin/paperpipe/docs/archive/PR_M0_Staged_Candidate_Validation_2026-03-17.md` now confirms that the currently staged candidate parses cleanly, passes `git diff --cached --check`, and still leaves the broader `runtime_paths` / `identity` tails out of scope.
   - the remaining decision is no longer whether a viable candidate exists, but whether to execute repository-baseline adoption on the already confirmed staged `PR-M0` set.

2. Freeze one canonical current-state contract document after the baseline files are adopted.
   - Decide whether the active runtime stays on `agent_artifacts` temporarily or resumes the H0/H1/H2 migration.

3. Run a focused reconciliation audit for four infrastructure lanes:
   - identity/pathing
   - event logging
   - output contracts
   - citation grounding

4. Only after that, resume feature-forward work on:
   - discover queue depth
   - citation jump reliability
   - stats trigger UX
   - Meeting Pack follow-ups

## 10. Verified Evidence Used For This Audit

Primary documents:

- `README.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Pending_PR_Queue.md`

Primary runtime files:

- `backend/main.py`
- `backend/services/job_runner.py`
- `backend/routers/obsidian.py`
- `backend/routers/paper_notes.py`
- `src/jobs/queue.py`
- `src/jobs/worker.py`
- `src/profiles/profile_store.py`
- `src/schemas/agent_artifacts.py`
- `src/agents/reader_agent.py`
- `src/agents/indexer_agent.py`
- `src/fetch/openalex.py`
- `src/exporter.py`
- `src/services/runtime_paths.py`
- `src/meeting_packs/service.py`
- `src/profiles/research_dna_service.py`
- `frontend/src/App.tsx`
- `frontend/package.json`

Verification commands:

- `git status --short`
- `git rev-parse --abbrev-ref HEAD`
- `pytest --collect-only -q`
- `pytest -q`
- targeted file inspection via `sed` / `rg`
