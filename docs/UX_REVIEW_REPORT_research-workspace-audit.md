# UX Review Report - Research Workspace Audit

Status: Current review
Date: 2026-04-01
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-04-01
Reviewer: Codex

## Input
- Screen/Flow: `/` -> `/papers` -> `/papers/:slug` -> `/workbench/:paperId` -> downstream artifact lanes (`/meeting-packs`, `/protocol-cards`, plus sibling saved-artifact viewers)
- Goal action: 연구자가 논문을 가져와 읽고, claim/evidence/provenance를 검토하고, meeting/protocol/exportable artifact로 빠르게 이어간다.
- Primary persona: local-first biomedical research workspace를 일상적으로 쓰려는 biomedical/medical researcher
- Current friction: 개별 화면은 꽤 강하지만, 제품이 전달하는 경험은 아직 "connected research workspace"보다 "paper-centric viewers + artifact inspectors"에 더 가깝다.
- Success metric:
  - first-session에 `home -> note -> workbench`의 의미가 즉시 보인다
  - note에서 claim/evidence/provenance와 next action이 reading flow 안에서 더 직접 보인다
  - downstream artifact가 canonical evidence와 느슨하게 분리되지 않고 한 research thread로 인식된다
- Constraints:
  - FastAPI + Vite + React Router + TailwindCSS 유지
  - `--pp-*` 토큰과 dark-first Lattice tone 유지
  - current paper/run/artifact runtime contract 유지
  - incremental patch 우선, route rewrite 금지
  - `rules/product-psychology/SKILL.md`
  - `rules/product-psychology/references/review-checklist.md`
  - `rules/product-psychology/references/bias-framework.md`
  - `rules/product-psychology/references/ethics-checklist.md`
  - `rules/product-psychology/references/prompt-templates.md`

## Quick Review (5 min)
- 첫 인상은 "실제 연구용으로 꽤 많이 만들어진 앱"이다. 문제는 미완성보다 정체성 전달의 분산이다.
- home, note detail, workbench, artifact inspectors 각각은 괜찮다. 하지만 사용자는 이 앱을 아직 "하나의 project context 안에서 읽고, 검증하고, 넘기는 workspace"로 기억하기 어렵다.
- 가장 큰 gap은 새 기능 부족이 아니라 IA framing 부족이다. project container, research thread, canonical evidence boundary가 여러 화면에 흩어져 있다.
- provenance와 uncertainty는 구현돼 있으나 핵심 가치로 전면화되기보다 보조 패널 안에 숨어 있는 경우가 많다.
- screen-local polish보다 `note -> workbench -> artifact` continuity를 먼저 강화하는 편이 체감 개선이 크다.
- Review basis:
  - repo route/component read
  - local mock UI run
  - screenshot review from `output/playwright/`

## Full Review
### P0
- Product promise와 visible IA가 어긋난다. 현재 top-level route는 paper list와 artifact family 중심이며 project-level container가 없다. 그래서 제품 설명은 workspace인데 실제 navigation 기억은 viewer set으로 남기 쉽다.
- Paper note detail의 중앙 경험이 아직 markdown reading에 너무 치우쳐 있다. structured state, saved claims, evidence grounding, next action은 존재하지만 대부분 오른쪽 rail에 실려 있어 reading과 structuring 사이가 끊긴다.
- provenance/uncertainty/access boundary는 잘 구현돼 있지만 primary value proposition으로 충분히 전면화되지 않았다. 사용자는 "왜 이 앱을 믿고 다음 행동으로 넘어가도 되는지"를 중심 column과 entry surface에서 더 빨리 봐야 한다.

### P1
- Workbench는 매우 강한 differentiated surface지만 control density가 높다. reading style, context profile, refresh/repair/rebuild, verify, retrieval, theme, density, highlight가 동시에 보이며 핵심 task가 약간 흐려진다.
- Artifact family는 구현 품질이 좋지만 서로 분절돼 보인다. meeting pack과 protocol card는 모두 canonical evidence boundary를 말하지만, 상위 레벨에서 "derived artifact center"라는 공통 mental model이 약하다.
- Home와 Paper Notes list는 명확하지만 각각 queue/index 성격이 강하다. "이 논문이 지금 어떤 research thread를 전진시키는가"는 덜 보인다.

### P2
- command/shortcut/triage language는 일부 존재하지만 Linear 수준의 high-speed manipulation 감각은 아직 약하다.
- local-first trust는 runtime/access/trust boundary 문구로 드러나지만, export/share/sync 경계와 data control tone을 더 일관되게 묶을 수 있다.
- 일부 artifact viewers는 read-only/trust-boundary 설명이 좋지만, cross-artifact shared affordance가 더 있으면 recovery cost가 줄어든다.

### Full Review Coverage
- 6P storyboard context:
  - Problem: 연구자는 논문을 읽고 끝나지 않고, 구조화와 다음 행동까지 이어가야 한다.
  - Emotion: "이 claim을 믿어도 되나, 다음 회의/실험으로 바로 넘길 수 있나"가 핵심 감정이다.
  - Action: home에서 시작해 note를 열고, evidence를 보고, workbench에서 판단한 뒤 artifact를 만든다.
  - Struggle: 지금은 route 간 맥락이 살아 있지만 top-level framing이 약해 사용자가 매번 mental stitching을 해야 한다.
  - Attempt: visible thread, canonical boundary, next action, and provenance를 각 주요 화면의 first-class element로 끌어올린다.
  - Happy Ending: 사용자는 PaperPipe를 note viewer가 아니라 grounded research workspace로 기억한다.
- BMAP:
  - Motivation: 매우 높다. provenance-backed reading에서 바로 next action으로 가는 속도가 제품 차별점이다.
  - Ability: 개별 화면은 이미 충분히 usable하다. 큰 리라이트 없이도 hierarchy와 carry-over를 조정하면 효과가 크다.
  - Prompt: home CTA, note-level next action, workbench evidence priority, artifact-level continue links가 핵심 prompt다.
- B.I.A.S:
  - Block: top-level IA가 route family 중심이라 project/workspace 해석을 막는다.
  - Interpret: 사용자는 "여기는 뷰어 모음인가, 연구 workspace인가?"를 첫 세 화면에서 판단한다.
  - Act: note/workbench/artifact를 하나의 research thread로 다시 읽히게 해야 한다.
  - Store: provenance와 uncertainty가 전면에 있을수록 제품 기억이 더 강하고 차별적이다.
- Peak-End:
  - Peak: note detail의 review snapshot, workbench의 grounded evidence surface, artifact detail의 canonical boundary 문구
  - Pit: home/list에서 project/workflow framing 약함, note detail 중심부의 action scarcity, workbench control overload
  - Transition: `papers -> note -> workbench -> artifact`
  - End: artifact detail에서 note/workbench로 돌아갈 때 continuity를 더 강하게 만들 필요가 있다
- Ethics:
  - Regret: 낮다. 조작적 growth hack이 아니라 이해 가능성과 evidence clarity를 높이는 제안이다.
  - Black Mirror: 낮다. uncertainty를 숨기지 않고 더 전면화한다.
  - In Real-Life: 실제 연구 작업에서는 aesthetic novelty보다 provenance, recovery, and next-step clarity가 더 중요하다.

## BMAP diagnosis
- Motivation gap은 낮다. 연구자는 이미 "읽은 걸 다음 행동으로 넘기고 싶다"는 강한 동기를 가진다.
- Ability gap은 medium이다. 기능은 있지만, 화면 위계 때문에 사용자가 바로 활용하기 어려운 곳이 있다.
- Prompt gap은 높다. 특히 note detail과 artifact family에서 "지금 뭘 해야 하는지"와 "어디서 canonical evidence를 다시 열어야 하는지"를 더 빠르게 prompt해야 한다.

## B.I.A.S diagnosis
- Block:
  - project container 부재
  - reading 중심 column과 structuring/action rail의 분리
  - artifact family 간 공통 narrative 부족
- Interpret:
  - 현재 앱은 power-user tooling으로는 보이지만, "왜 이걸 계속 써야 하는지"는 일부 화면에서 늦게 읽힌다.
- Act:
  - note detail center에 claim/evidence/provenance 요약을 끌어오고
  - workbench controls를 task-first로 재배치하고
  - artifact pages에 shared thread context를 추가하는 것이 우선이다.
- Store:
  - provenance-aware action loop가 보일수록 사용자는 PaperPipe를 신뢰 가능한 연구 workspace로 저장한다.

## Peak-End design notes
- Peak를 더 앞당겨야 한다. 현재 가장 강한 경험은 workbench와 note detail 중후반에 나온다.
- Pit는 home/list에서 "workspace"보다 "queue/index"로 읽히는 지점이다.
- Transition quality는 note detail에서 가장 중요하다. 이 화면이 reading과 structuring 사이의 bridge이기 때문이다.
- End는 meeting/protocol detail에서 upstream note로 돌아가는 감각이다. 이미 링크는 있지만 더 명시적인 thread framing이 필요하다.

## Concrete changes
- Add a shared "Current research thread" context strip across note detail, workbench, and artifact detail surfaces.
  - contains: upstream note, saved state status, grounded/unresolved counts, next artifact actions
- Rebalance note detail so the center column shows a compact structured review block before or inside the reading surface.
  - claims count, grounded/unresolved badges, top unresolved claim/evidence, protocol/meeting actions
- Move low-frequency workbench controls under a single collapsed "Session controls" group and keep only run, cancel, refresh, and review repair visible by default.
- Rename workbench artifact language away from internal notebook implementation terms where appropriate.
  - prefer research-task labels over `Cell 2 Agent Plan` and `Cell 3 Sandbox Execution`
- Introduce a shared artifact-family affordance in artifact pages.
  - "Derived artifact"
  - "Canonical evidence lives in note/workbench"
  - "Continue in note"
  - "Reuse in meeting/protocol/export"
- Strengthen uncertainty and provenance messaging on primary surfaces.
  - note detail header
  - review snapshot
  - workbench notice area
  - artifact detail summary

## Ethics check results
- Regret:
  - low
  - proposed changes increase clarity and user control rather than persuasion pressure
- Black Mirror:
  - low
  - no hidden confidence inflation or AI certainty theater
- In Real-Life:
  - strong fit
  - the changes align with how researchers actually recover context, challenge claims, and prepare downstream outputs

## Next PR-sized actions
1. Add a shared research-thread context block to note detail, workbench header, and artifact detail sidebars without changing route structure.
2. Rebalance `PaperNoteDetailPage` so structured review and next action move closer to the reading column and stop feeling like a secondary debug rail.
3. Simplify `AnalysisWorkbench` controls into task-first defaults plus collapsed session settings, then rename artifact-panel sections toward evidence-review language.

## Implementation follow-up (2026-04-01)
- A first v1 home patch has been applied in `frontend/src/app/pages/TriageDashboard.tsx`.
- The current top-left emphasis now switches from `Start here` to `Continue current work` when the loaded home data contains a stronger blocked/review candidate.
- The v1 selector is intentionally conservative:
  - source from unfiltered `papers`
  - blocked and review resume only
  - no fake `Resume reading` action yet
- This follows the repo-grounded constraint that the current home payload does not yet include note slug/link data for a true reading-context resume target.
- Verification:
  - `cd frontend && npm run build` passed
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-01, reading resume extension)
- The home resume card now uses the existing paper-notes index as a frontend join to unlock a true `Resume reading` action without changing the backend papers contract.
- `TriageDashboard` now loads:
  - `getPapers()`
  - `getPaperNotesIndex({ pageSize: 5000 })`
- This keeps the extension small and avoids backend schema drift while allowing the home card to navigate to `/papers/:slug` when a ready paper has a resolvable note.
- Verification:
  - `cd frontend && npm run build` passed again after the note-link join
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-01, Read/Review language cleanup)
- `PaperNoteDetailPage` and `AnalysisWorkbench` now use more task-facing public language.
- The note surface now foregrounds `Read` instead of `Paper note detail`, and review handoff labels now use `Open review`.
- The workbench header now uses the paper title as the main title, with review intent carried by the subtitle instead of the route name `Analysis Workbench`.
- `WorkbenchLayout` now uses `Open reading` and `Review controls` wording to better match the shared paper-workspace model.
- Verification:
  - `cd frontend && npm run build` passed
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-01, mock verification closure)
- The remaining mock verification failures were narrowed to the PDF/highlight lane and resolved without changing the public IA decisions.
- `frontend/src/app/lib/mock.ts` now emits structured-state evidence in the same shape the workbench parser expects:
  - best highlight per claim
  - zero-based page indices
  - bbox payload when available
- This restores the intended ambiguous-claim behavior where bbox anchors outrank text-match fallback when both exist.
- The mock visual helper in `frontend/e2e/visual-mock.mock.spec.ts` now scrolls the PDF viewer back into view before checking the highlight overlay, which stabilizes mobile screenshot capture after selecting a claim from the artifact panel.
- Mock visual snapshots were regenerated after the helper/runtime stabilized.
- Verification:
  - `cd frontend && npm run verify:frontend:mock` passed (`33 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-01, note-detail review bridge)
- `PaperNoteDetailPage` now keeps a compact `Review focus` bridge inside the center reading surface instead of forcing users to jump mentally from markdown into the right rail.
- The new bridge lives above the markdown body and keeps four things visible while reading:
  - saved review-state status
  - compact structured counts
  - one saved claim/evidence focus target
  - direct `Open review` / `Save protocol card` handoff actions
- This patch intentionally reuses existing review-state and ops-summary signals instead of introducing a new note-detail data model.
- The right rail still carries the full `Saved note state`, `Actions`, `Run history`, and `Saved claims` depth; the center bridge is meant to reduce the reading-to-review gap, not replace those panels.
- A mock regression was added so structured note detail now verifies that the bridge remains visible near the reading flow.
- Verification:
  - `cd frontend && npm run build` passed
  - `mkdir -p frontend/test-results && cd frontend && npm run verify:frontend:mock` passed (`34 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-01, backend Playwright language alignment)
- Backend Playwright expectations for the shared paper workspace were updated to match the current public task language:
  - `Analysis Workbench` heading checks now key off the stable review subtitle instead of the old route label
  - note-detail handoff copy now expects `Open review`
  - mobile sheet copy now expects `Note panels`
  - note view-mode checks now expect `Read / Review` language instead of `Learner / Inspect`
- The backend functional lane was also updated to recognize the new center-column `Review focus` bridge on structured note detail.
- Verification:
  - `cd frontend && npm run lint` passed
  - `cd frontend && npm run build` passed
  - targeted backend Playwright execution now runs in the repo E2E environment using `.venv/bin/python`
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-01, home resume-card contract fix)
- The home `Continue current work` join originally asked `/paper-notes?page_size=5000`, which violates the backend contract (`page_size <= 200`) and caused an accidental `422 -> mock fallback -> Mock mode` regression on backend home.
- `TriageDashboard` now treats paper-note lookup as auxiliary enrichment instead of a primary mock-signal source:
  - home paper-note loading is paged in `200`-item chunks
  - the main home `Mock mode` banner is still driven by primary surfaces (`/health`, `/papers`)
  - an auxiliary paper-notes fallback no longer promotes the whole home route into mock mode when the primary backend data is real
- This keeps the resume-reading extension while respecting the actual FastAPI paper-notes contract and avoids mixing a real backend home with a mock note-index banner.
- Verification:
  - `cd frontend && npm run lint` passed
  - `cd frontend && npm run build` passed
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend mode stays out of mock fallback"` passed
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend mode stays out of mock fallback|backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser|mobile backend UX|paper notes detail renders structured actions, run history, and structured claims cards|paper notes detail supports learner and builder debug view modes"` passed (`10 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-02, backend visual alignment and stabilization)
- After the home resume-card and note-detail bridge changes, the backend visual lane drifted in exactly the surfaces we expected:
  - triage dashboard
  - paper note detail
  - structured paper note detail
- Those three snapshot changes were intentional and the baselines were regenerated to reflect the current UX contract:
  - home now foregrounds `Continue current work`
  - note detail now includes the center-column `Review focus` bridge
- One additional backend visual flake surfaced in the desktop workbench rail:
  - the rail screenshot occasionally captured before the paper list finished loading, showing `No papers available`
  - the visual helper now waits for seeded paper content in the rail before taking the screenshot, without forcing the mobile-collapsed rail to open
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "visual regression \\(backend, desktop\\): paper note detail layout|visual regression \\(backend, desktop\\): structured paper note detail layout|visual regression \\(backend, desktop\\): workbench shell layout|visual regression \\(backend, desktop\\): workbench rail layout|triage dashboard layout|paper note detail layout|structured paper note detail layout|workbench shell layout"` passed (`9 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-02, artifact continuity slice)
- The first artifact-continuity slice now lands in the two downstream viewers where evidence drift risk is highest:
  - `MeetingPackPage`
  - `ProtocolCardPage`
- `ArtifactHeaderContext` now supports an emphasized first item, and these two detail routes use it to carry a shared continuity signal:
  - `Derived artifact`
  - `Canonical evidence lives upstream`
  - `Continue in note` guidance stays explicit before regenerate/share or claim/version edits
- This was kept intentionally narrow:
  - only detail routes receive the emphasized continuity card
  - index routes keep the older lighter header context
  - no backend schema, route, or artifact payload contract changed
- Verification:
  - `cd frontend && npm run build` passed
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts e2e/protocol-card.mock.spec.ts` passed (`5 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route|backend protocol knowledge inspector loads a saved protocol card and keeps note handoff on the real route|backend protocol knowledge index can create a new protocol card from the browser"` passed (`3 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "meeting pack detail layout|protocol knowledge detail layout|mobile.*meeting pack detail layout|mobile.*protocol knowledge detail layout"` passed (`4 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-02, artifact continuity slice extended to image and method viewers)
- The same derived-artifact continuity pattern now extends to the next two downstream viewers in the family:
  - `ImageEvidencePage`
  - `MethodComparisonPage`
- Both detail routes now foreground the same compact mental model before the rest of the artifact metadata:
  - `Derived artifact`
  - `Canonical evidence lives upstream`
  - note-first continuation guidance before reuse, export, or downstream handoff
- The wording stays viewer-specific without changing the underlying artifact contract:
  - image evidence points back to the linked paper note before reuse in packs, charts, or downstream review
  - method comparison points back to the linked compared paper notes before exporting or reusing the grid
- Scope stayed intentionally narrow, matching the earlier meeting/protocol slice:
  - detail routes only
  - index routes unchanged
  - no backend schema, route, or artifact payload contract changed
- Verification:
  - `cd frontend && npm run build` passed
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/image-evidence.mock.spec.ts e2e/method-comparison.mock.spec.ts` passed (`4 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend method comparison viewer loads a generated comparison and keeps export on the real csv route|backend method comparison index can create a new comparison from the browser|backend image evidence viewer loads a registered bundle and keeps note handoff on the real route"` passed (`3 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "image evidence detail layout|method comparison detail layout|mobile.*image evidence detail layout|mobile.*method comparison detail layout" --update-snapshots` regenerated the four touched detail baselines
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "image evidence detail layout|method comparison detail layout|mobile.*image evidence detail layout|mobile.*method comparison detail layout"` passed (`4 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-02, chart pack continuity alignment)
- The same detail-route continuity contract now extends to `ChartPackPage`, which was the last major artifact viewer in this family still reading more like a standalone export tool than a derived review surface.
- `ChartPackPage` detail now foregrounds the same shared continuity frame:
  - `Derived artifact`
  - canonical evidence lives upstream
  - continuation points back to linked paper review/source items before CSV/spec export or downstream chart reuse
- This kept the viewer-specific reality intact:
  - chart packs are still review-first rather than note-first because the concrete downstream handoff already lives on saved source items and workbench review links
  - index/create routes remain unchanged
  - no backend schema, route, or chart-pack payload contract changed
- Verification:
  - `cd frontend && npm run build` passed
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/chart-pack.mock.spec.ts` passed (`3 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack viewer loads a generated chart pack and keeps exports on real routes|backend chart pack index can create a new chart pack from the browser|backend chart pack quick-pick journey stays connected in the browser"` passed (`3 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack detail layout|mobile.*chart pack detail layout" --update-snapshots` regenerated the two touched detail baselines
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack detail layout|mobile.*chart pack detail layout"` passed (`2 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-02, home workspace-context framing)
- The next IA move after closing the artifact family was intentionally **not** a fake `Active projects` list.
- The repo still has no true project-list contract on the home route, and the only visible `project_note` signal today lives in meeting-pack selectors as context-only framing.
- So the home patch stayed honest to the current runtime and introduced a lighter context block instead:
  - `Workspace context`
  - saved notes count
  - structured notes count
  - needs-review count
  - blocked count
  - latest note update hint
  - lightweight actions: `Browse Paper Notes` and `Open queue`
- This keeps the intended product direction visible without implying a heavy project-ownership system that the repo does not yet implement.
- It also rebalances the right side of home so `Saved outputs` remains secondary to context, rather than acting like the only non-resume block.
- Verification:
  - `cd frontend && npm run build` passed
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend mode stays out of mock fallback|backend triage summarizes repair, review, and ready buckets|backend triage separates content review cues from operational state"` passed (`3 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "triage dashboard layout" --update-snapshots` regenerated the two touched dashboard baselines
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "triage dashboard layout"` passed (`2 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-02, home workspace-context semantics cleanup)
- The next home pass stayed on the same surface and fixed semantics rather than adding more chrome.
- Three meaning mismatches were resolved inside `TriageDashboard`:
  - `Workspace context` now uses **global** repair/review counts from the full paper set instead of mixing filtered counts with global note totals.
  - note-index degradation no longer reads like an honest zero state; saved/structured note tiles now surface `Unavailable` and the footer explains that note context is temporarily limited.
  - the secondary CTA now matches the current runtime reality by saying `Jump to action list` instead of implying a fully separate `Queue` surface.
- This keeps the product direction visible without over-promising a project system or a stronger queue container than the repo currently implements.
- Verification:
  - `cd frontend && npm run build` passed
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend mode stays out of mock fallback|backend triage summarizes repair, review, and ready buckets|backend triage separates content review cues from operational state|backend workspace context keeps global counts while search filters the action list"` passed (`4 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "triage dashboard layout"` passed (`2 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-02, shared note/workbench workspace-context strip)
- After the home semantics cleanup, the next smallest-safe move was to bring the same context-strip discipline into the two primary paper surfaces instead of inventing more top-level IA.
- A new shared `WorkspaceContextStrip` now keeps header context explicit on:
  - `PaperNoteDetailPage`
  - `AnalysisWorkbench`
- The strip stays honest to the current runtime:
  - note detail shows `Saved note`, `Structured state`, and `Workspace mode`
  - workbench shows `Access route`, `Saved review state`, and `Claim review`
- This is intentionally a header-clarity patch, not a new workflow:
  - no route or API changes
  - no project model changes
  - no artifact contract changes
  - existing review snapshot / review focus / workbench notice behavior stays intact
- Verification:
  - `cd frontend && npm run build` passed
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "structured paper note detail keeps review focus close to reading|workbench rail keeps parser pilot query when selecting another paper"` passed (`2 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workbench preserves content review context when opened in issue focus mode|paper notes detail renders structured actions, run history, and structured claims cards"` passed (`2 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "paper note detail layout|structured paper note detail layout|workbench shell layout" --update-snapshots && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "paper note detail layout|structured paper note detail layout|workbench shell layout"` passed (`6 passed`)
  - touched visual baselines were limited to:
    - `backend-desktop-paper-note-detail-darwin.png`
    - `backend-desktop-paper-note-detail-structured-darwin.png`
    - `backend-desktop-workbench-shell-darwin.png`
    - `backend-mobile-paper-note-detail-darwin.png`
    - `backend-mobile-paper-note-detail-structured-darwin.png`
    - `backend-mobile-workbench-shell-darwin.png`
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-02, queue-lens naming alignment)
- With home context and shared paper-surface context now in place, the next small IA cleanup was to make the lower triage section say what it actually is: an operational lens, not a hidden second home and not a project container.
- `TriageDashboard` now calls the lower section `Queue lens` and explains its scope:
  - it is an operational view over the current papers
  - search narrows this queue view without changing workspace context
- The home CTA was aligned to the same language by moving from `Jump to action list` to `Jump to queue lens`.
- This was intentionally naming-only and scope-preserving:
  - no route change
  - no queue container added
  - no summary math or paper ownership logic changed
- Verification:
  - `cd frontend && npm run build` passed
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend mode stays out of mock fallback|backend triage summarizes repair, review, and ready buckets|backend triage separates content review cues from operational state|backend workspace context keeps global counts while search filters the action list"` passed (`4 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "triage dashboard layout"` passed (`2 passed`)
  - no snapshot regeneration was required for this wording-only alignment
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch

## Implementation follow-up (2026-04-02, broader backend stabilization after home/read-review IA updates)
- After the home `Queue lens` wording and the shared note/workbench `Workspace context` strip were in place, the next safest move was to stop adding IA and run the broader backend verification lane end to end.
- The broader run surfaced only three visual diffs, and all three were tied to the same intentional cause:
  - the shared workbench header/context strip slightly changed the stable header height
  - this produced a small, repeatable viewport shift in the workbench-rail and PDF claim-highlight screenshots
- No route logic, parser behavior, or claim-link behavior regressed in this pass.
- Only the three touched visual baselines were refreshed after checking the actual rendered images:
  - `backend-desktop-workbench-rail-darwin.png`
  - `backend-desktop-claim-highlight-darwin.png`
  - `backend-mobile-claim-highlight-darwin.png`
- The parser-worker lane also completed successfully, so the broader backend suite now reflects the updated home/read-review vocabulary and the current visual contract.
- Verification:
  - `cd frontend && npm run verify:frontend:backend` passed
  - result: `98 passed, 4 skipped`
  - skipped cases remained the expected conditional lanes rather than new regressions
  - parser-worker phase passed (`2 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this stabilization pass

## Implementation follow-up (2026-04-03, backend home workspace summary contract)
- After the broader stabilization pass, the next step was intentionally **not** more chrome.
- Instead, the home `Workspace context` block was given a tiny backend-owned summary contract so the current counts stop depending only on client-side assembly.
- The new backend contract is intentionally small and still avoids pretending there is already a heavier project system:
  - `saved_notes`
  - `structured_notes`
  - `needs_review`
  - `blocked`
  - `latest_note_updated_at`
  - `note_context_limited`
- The frontend still behaves conservatively:
  - if `/workspace-summary` is available, home uses it
  - if it is unavailable, home falls back to the existing client-side summary assembly
  - this means the endpoint improves truthfulness without becoming a new hard dependency for the whole screen
- This is a runtime-contract patch, not a visual redesign:
  - no layout change
  - no new project route
  - no queue container added
  - no visual baseline changes were needed
- Verification:
  - `cd frontend && npm run build` passed
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "mock mode fallback renders full phase3 flow|issue button routes with focus=issues and selects risk claim"` passed (`2 passed`)
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend mode stays out of mock fallback|backend triage separates content review cues from operational state|backend triage summarizes repair, review, and ready buckets|backend workspace context keeps global counts while search filters the action list"` passed (`4 passed`)
  - existing `pdfjs-dist` eval warning remains non-blocking and unchanged by this patch
