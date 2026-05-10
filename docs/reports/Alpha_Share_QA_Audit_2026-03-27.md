# Alpha Share QA Audit

Status: Active audit note
Date: 2026-03-27
Owner: Lattice runtime maintainers
Purpose: record a repo-grounded release QA audit for the current bounded first-product slice and decide whether close-person alpha sharing is credible.
Canonical parents:
- `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`
- `docs/reports/First_Product_Demo_Runbook_2026-03-27.md`

## 1. Executive Verdict

The current product is credible for **limited close-person alpha sharing** on the bounded first-product slice.

This verdict applies to the current paper-centered runtime only:
- `/`
- `/papers`
- `/papers/:slug`
- `/workbench/:paperId`
- `Research DNA` API/CLI lane
- `/meeting-packs`

It does **not** promote broader `Project`, memory/chat, repo-wide decision/task/experiment orchestration, or generalized workspace claims.

## 2. Audit Mode Chosen And Why

Chosen mode:
- **partial runtime verification + code-assisted audit**

Why:
- the current repo is a local-first web UI plus FastAPI backend, not a packaged desktop app
- the bounded first-product slice is executable in the current environment
- several core user-visible surfaces can be checked end-to-end with real runtime plus Playwright
- a few lanes still require code inspection or API/runtime checks instead of full UI walkthrough

## 3. What Was Actually Verified vs Not Verified

### Verified by execution

- fresh backend startup via `bash frontend/scripts/run_backend_for_real_smoke.sh`
- real-smoke environment preflight via `python3 scripts/check_frontend_real_smoke_env.py --require-candidates`
- backend smoke via `./scripts/run_backend_api_smoke.sh`
- targeted `Research DNA` test slice
- targeted `Meeting Pack` test slice
- frontend build via direct Node CLI (`tsc -b` + `vite build`)
- frontend lint via direct Node CLI (`eslint .`)
- real frontend smoke via direct Playwright CLI
- targeted backend Playwright coverage for:
  - triage dashboard
  - paper list
  - paper detail
  - workbench
- manual runtime/API checks for:
  - representative paper list/detail
  - representative `Research DNA`
  - representative `Meeting Pack`

### Verified by code inspection only

- execution entrypoint semantics for `frontend/package.json`
- route map in `frontend/src/App.tsx`
- backend route ownership in `backend/routers/paper_notes.py` and `backend/routers/meeting_packs.py`
- current config/runtime path defaults

### Not verified in this pass

- packaged installer or desktop-shell launch
- multi-user or collaboration behavior
- broad extension viewers as part of the first-product score
- fresh `Meeting Pack` generation from scratch during this audit pass
- full deep-read rerun during this audit pass

### Blocked by environment

- none of the core bounded-slice checks remained blocked after switching from `npm`/`npx` wrappers to direct Node CLI

## 4. Runtime / Launch Status

Current product form:
- local-first web UI + FastAPI backend + local state/artifact roots

Current realistic launch path:
- fresh backend via `frontend/scripts/run_backend_for_real_smoke.sh`
- frontend dev/build via Vite/TypeScript
- user-visible runtime via browser against local backend

Important runtime caveats found during the audit:
- a long-lived stale backend on `localhost:8000` had drifted from current repo routes; fresh restart fixed that
- the representative `Meeting Pack` bundle had drifted out of the active runtime root into `.codex-trash`; it was restored to `storage/meeting_packs/` during this audit
- in the current shell, `npm run ...` / `npx ...` wrappers were less reliable than direct Node CLI; direct CLI verification succeeded

## 5. Core User Flows Selected For This Repo

### Flow 1: Paper review to inspectable structured state
- flow name: `paper review loop`
- start point: `/papers`
- expected end state: operator opens a real note, sees saved-state truth, and reaches workbench with evidence-linked review state
- why this matters: this is the most honest first-product entry flow
- verification planned: targeted Playwright + fresh runtime/API checks

### Flow 2: Reproducible search-design inspection
- flow name: `research dna inspection`
- start point: `GET /research-dna/{dna_id}` or CLI
- expected end state: operator sees a real bounded search-design asset with revision and status
- why this matters: `Research DNA` is the current reproducible-search backbone
- verification planned: live API check + targeted pytest

### Flow 3: Meeting-ready downstream artifact review
- flow name: `meeting pack review`
- start point: `/meeting-packs` or `/meeting-packs/:packId`
- expected end state: operator sees a real saved pack with readiness, trace, and validate/regenerate state
- why this matters: it proves the downstream artifact claim without pretending artifacts are the truth store
- verification planned: live API check + page-load check + targeted pytest

## 6. End-to-End User Flows Tested

| Flow | Start | End | Result | Notes |
| --- | --- | --- | --- | --- |
| Paper review loop | `/papers` | `/workbench/:paperId` | `verified` | Paper list, detail, and workbench were all checked with real or backend-real Playwright coverage. |
| Research DNA inspection | `GET /research-dna/dna_mci_medium_chain_triglycerides_probe_20260312` | real JSON payload with `PILOT` revisioned asset | `verified` | Live API response plus targeted pytest slice. |
| Meeting Pack review | `/meeting-packs` | `/meeting-packs/:packId` with trace/validate | `verified` | Representative pack had to be restored into active runtime root first; after restore, list/detail/trace/validate all worked. |
| Deep-read rerun from scratch during this pass | enqueue new run | note-side state generated | `not reached` | Earlier evidence exists, but this audit did not rerun deep-read from scratch. |

## 7. Screen-by-Screen Implementation Audit

| Screen / surface | Status | Evidence | Judgment |
| --- | --- | --- | --- |
| `/` triage dashboard | `verified` | targeted Playwright (`backend triage summarizes repair, review, and ready buckets`) | Real backend-connected landing screen for current runtime. |
| `/papers` | `verified` | targeted Playwright + fresh API check | Real list screen with saved-state truth cues. |
| `/papers/:slug` | `verified` | targeted Playwright + fresh API check | Real detail screen with saved-state visibility and structured review panels. |
| `/workbench/:paperId` | `verified` | real-paper smoke + targeted Playwright | Strongest review surface in the current runtime. |
| `/meeting-packs` | `verified` | manual page load + live API | Works once representative pack exists in active runtime root. |
| `/meeting-packs/:packId` | `verified` | manual page load + live API + validate/trace | Real user-visible downstream artifact screen. |
| `/method-comparisons*` | `out-of-scope` | route exists; not audited in this pass | Bounded extension, not first-product core scoring target. |
| `/chart-packs*` | `out-of-scope` | route exists; not audited in this pass | Bounded extension, not first-product core scoring target. |
| `/image-evidence*` | `out-of-scope` | route exists; not audited in this pass | Bounded extension, not first-product core scoring target. |
| `/protocol-cards*` | `out-of-scope` | route exists; not audited in this pass | Bounded extension, not first-product core scoring target. |

## 8. Scored Release Checklist (100-point)

| Area | Applicability | Score | Evidence / reason | Method | Confidence |
| --- | --- | ---: | --- | --- | --- |
| A. 실행 가능성 / 런치 안정성 (15) | applicable | 12/15 | Fresh backend starts; frontend build works via direct CLI; wrapper-path quirks remain. | mixed | high |
| B. 핵심 사용자 흐름 완성도 (20) | applicable | 16/20 | Core paper review loop, `Research DNA`, and `Meeting Pack` review all completed; deep-read-from-scratch was not rerun in this pass. | mixed | high |
| C. 화면 구현 완성도 (15) | applicable | 12/15 | Triage, papers list/detail, workbench, and Meeting Pack list/detail are real and usable; bounded extension screens were not audited. | mixed | medium |
| D. 결과 품질 / 작업 가치 (15) | applicable | 11/15 | Representative structured state and Meeting Pack are useful and evidence-linked; sample size is still narrow. | mixed | medium |
| E. 안정성 / 상태 유지 / 복구성 (10) | applicable | 7/10 | Saved state and Meeting Pack validate/regenerate behave credibly, but representative pack drifted out of active root before this audit and needed restoration. | mixed | medium |
| F. 에러 처리 / 진단 가능성 (10) | applicable | 7/10 | Missing-state truth is visible; stale backend drift was diagnosable; some wrapper-path failures were opaque until direct CLI fallback. | mixed | medium |
| G. 응답성 / UX 피드백 (5) | applicable | 4/5 | Current core UI routes load and expose status/truth cues; no major silent waits seen in the bounded slice. | execution | medium |
| H. LLM 품질 / 출력 안정성 / 연구 도구 적합성 (10) | partially applicable | 8/10 | Current representative outputs remain evidence-linked and bounded; this pass did not perform a broader hallucination sampling audit. | mixed | medium |

### Score summary

- Raw score: **77/100**
- Adjusted score: **82/100**

Adjusted-score note:
- adjusted score discounts two items that were environmental or stage-bounded rather than current product failures:
  - wrapper-path instability in the current shell despite successful direct CLI verification
  - unaudited extension screens that are not part of the first-product promise

## 9. Hard Blockers

No hard blocker was confirmed on the bounded first-product slice.

What nearly counted but was resolved:
- stale backend on `localhost:8000`
- representative `Meeting Pack` bundle missing from active runtime root

## 10. Environment Blockers

- long-lived stale local backend processes can misrepresent the current repo unless a fresh restart is used
- current shell/tool context is more reliable with direct Node CLI than with some `npm run ...` / `npx ...` wrappers

These are real operational caveats, but they did not block the bounded slice once handled correctly.

## 11. Out-of-Scope Items For Current Stage

- packaged desktop-shell or installer UX
- multi-user/lab collaboration
- `Project`-first runtime
- memory/chat/copilot-first product lanes
- repo-wide `Decision`, `Task`, or `Experiment` object model
- bounded extension viewers as launch-defining screens

## 12. Nice-to-Have Improvements

- make the preferred fresh-start launch path more explicit for operators
- keep the representative `Meeting Pack` anchored in the active runtime root
- add direct UI regression coverage for `Meeting Pack` list/detail so it is not only manually checked
- reduce wrapper-path quirks by standardizing the operator-facing frontend verification path

## 13. Concrete Next Fixes In Priority Order

1. Add one tiny operator preflight that confirms:
   - fresh backend
   - representative paper exists
   - representative `Meeting Pack` exists in `storage/meeting_packs/`
2. Add a narrow Playwright check for `Meeting Pack` list/detail
3. If operator friction matters, add a documented direct CLI verification path beside `npm run ...`

## A. Verified User-Visible Completion Map

| Item | Status | Notes |
| --- | --- | --- |
| Triage dashboard (`/`) | `verified` | Backend-real Playwright coverage passed. |
| Papers list (`/papers`) | `verified` | Saved-state truth cues visible and tested. |
| Paper detail (`/papers/:slug`) | `verified` | Structured state, missing-state distinction, and detail panels tested. |
| Workbench (`/workbench/:paperId`) | `verified` | Real-paper smoke passed; evidence/highlight flow stable. |
| `Research DNA` lane | `verified` | API/CLI only, but live runtime response and tests passed. |
| Meeting Pack list/detail (`/meeting-packs`) | `verified` | Manual page load plus API/trace/validate checks succeeded after bundle restore. |
| Method Comparison | `out-of-scope` | Real extension lane, not scored in this bounded first-product audit. |
| Chart Pack | `out-of-scope` | Real extension lane, not scored in this bounded first-product audit. |
| Image Evidence | `out-of-scope` | Real extension lane, not scored in this bounded first-product audit. |
| Protocol Knowledge | `out-of-scope` | Real extension lane, not scored in this bounded first-product audit. |
| Project/chat/memory lanes | `out-of-scope` | Not part of the current product promise. |

## B. Close-Person Distribution Decision

- Raw score: **77/100**
- Adjusted score: **82/100**
- Decision: **제한적 배포 가능**
- Why:
  - the bounded paper-centered slice is real, executable, and user-visible
  - the core paper review loop, `Research DNA`, and `Meeting Pack` review all work now
  - no hard blocker remained once stale runtime state was removed and the representative pack was restored
- Hard blockers:
  - none on the bounded first-product slice
- Environment blockers:
  - stale long-lived backend can mislead verification
  - current shell prefers direct Node CLI over some wrapper commands
- What must be fixed before sharing:
  - nothing blocker-shaped for bounded close-person alpha sharing
  - before each share/demo, use a fresh backend and confirm the representative `Meeting Pack` remains in `storage/meeting_packs/`
- What can wait:
  - extension-lane UI audits
  - wrapper-path polish
  - broader product/platform lanes
- Recommended tester profile:
  - technically comfortable researcher or close collaborator who can tolerate a local-first alpha workflow
- Recommended max number of testers now:
  - **3**
