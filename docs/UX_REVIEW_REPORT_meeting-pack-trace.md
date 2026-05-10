# UX Review Report - Meeting Pack Trace Inspector

Status: Current review artifact  
Date: 2026-03-17  
Owner: Lattice runtime maintainers  
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-17
Reviewer: Codex

## Input
- Screen/Flow: `/meeting-packs` saved packs index + quick open -> `/meeting-packs/:packId` ops/debug detail
- Goal action: 운영자나 연구자가 saved meeting pack의 selector/load trajectory를 빠르게 확인하고, drift/regenerate 상태와 함께 문제를 진단한다.
- Primary persona: PaperPipe runtime maintainer, power user, or researcher debugging pack generation
- Current friction: guarded regenerate/rerender CTA는 열렸지만, regenerate가 새 pack route로 이동할 때 action success continuity가 약해질 수 있다. inspector는 action 결과를 route transition 뒤에도 이어서 보여주는 편이 낫다.
- Success metric: pack generation/support debugging time, source-resolution issue triage time, regenerate/drift diagnosis time
- Constraints:
  - FastAPI + Vite + React Router + TailwindCSS 유지
  - `--pp-*` 토큰과 dark-first Lattice tone 유지
  - `rules/product-psychology/SKILL.md`
  - `rules/product-psychology/references/review-checklist.md`
  - `rules/product-psychology/references/bias-framework.md`
  - `rules/product-psychology/references/ethics-checklist.md`
  - `rules/product-psychology/references/prompt-templates.md`
  - trace는 scientific truth가 아니라 operational observability metadata

## 1) Quick Review (5 min)
- Block: 현재 최대 block은 “recover action 뒤 route가 바뀌면 성공 상태가 끊길 수 있다”와 “trace가 json 내부에 숨어 있다”는 점이다.
- Interpret: inspector는 reader-facing 발표 뷰가 아니라 ops/debug view라는 정체성이 첫 화면에서 명확해야 한다.
- Act: `/meeting-packs` recent pack 선택 또는 direct pack-id 입력 -> `/meeting-packs/:packId` detail의 1-2 step이 가장 작은 행동 경로다.
- Store: trace summary와 validation 상태를 같은 화면에서 보면 “무엇을 봤고 왜 깨졌는지” 기억이 남는다.
- Ethics first pass: trace가 evidence truth처럼 보이지 않도록 operational copy와 warning을 같이 둬야 한다.
- Decision: new viewer를 만들지 않고, saved packs index + guarded draft actions + route-carried action notice를 포함한 pack-id-driven inspector를 additive로 연다.

## 2) Full Review (P0/P1/P2 prioritized)
### P0
- 6P storyboard context:
  - Problem: 운영자는 pack이 왜 이렇게 생성됐는지 빠르게 확인해야 한다.
  - Emotion: `meeting_pack.json`을 직접 열고 raw trace를 훑는 건 번거롭다.
  - Action: inspector entry에 pack id를 넣고 detail을 연다.
  - Struggle: trace가 scientific conclusion처럼 보이거나, validation/drift 정보와 recovery action 결과가 route transition에서 끊기면 다시 판단 비용이 커진다.
  - Attempt: summary + validation + guarded draft actions + carried success notice + trace timeline을 한 화면에 묶는다.
  - Happy Ending: source selection, load/reuse, drift/regenerate 상태를 한 번에 읽고 다음 조치를 결정한다.
- BMAP:
  - Motivation: 높다. pack debugging은 강한 즉시성 업무다.
  - Ability: recent saved packs가 보여야 하고, 그래도 direct pack id jump는 남아 있어야 한다. pack count가 늘어날수록 local search/filter도 필요하다.
- Prompt: `/meeting-packs` recent list + quick-open form + trace presence filter, detail의 guarded regenerate/rerender controls와 carried success notice가 적절하다.
- B.I.A.S:
  - Block: hidden trace / hidden route와 saved-pack narrowing friction이 핵심 block이다.
  - Interpret: “ops/debug inspector” 문구와 trace disclaimer가 해석 오류를 막는다.
  - Act: summary cards + trace timeline + warnings로 다음 액션 판단을 짧게 만든다.
  - Store: validation warnings와 source path list가 재진입 비용을 낮춘다.
- Peak-End:
  - peak는 trace summary에서 matched slugs와 source paths가 바로 보이는 순간이다.
  - pit는 raw JSON blob을 직접 읽어야 하는 순간이다.
  - transition은 pack id 입력 -> detail load -> trace inspection이다.
  - end는 regenerate/drift availability를 읽고 다음 운영 판단으로 끝나야 한다.
- Ethics:
  - Regret: 통과. trace를 truth가 아닌 observability로 명시한다.
  - Black Mirror: trace를 scientific evidence로 오독하게 만들면 위험하다.
  - In Real-Life: 조용한 운영 콘솔처럼 행동해야지, 발표 viewer처럼 꾸며선 안 된다.

### P1
- detail page는 draft context도 조금 보여줘야 한다. title/mode/readiness/source count/slide count가 없으면 trace만 보고 맥락이 끊긴다.
- trace entry는 selector ref, action/outcome, source path, matched slugs만 우선 노출하고 metadata JSON은 접어서 보여주는 편이 맞다.
- validation card는 can_regenerate, strategy, warnings를 compact하게 보여주고, markdown drift는 별도 badge로 읽히게 한다.
- detail page에는 canonical evidence를 건드리지 않는다는 copy와 함께 guarded regenerate/rerender CTA를 두고, regenerate success는 next pack route에서도 이어서 보이게 한다.

### P2
- trace action/outcome filtering, diff compare, markdown/source split view는 후속 범위다.

## 3) BMAP diagnosis
- Motivation: pack generation debugging은 강한 운영 동기다.
- Ability: recent list + local search/filter + direct id jump를 같이 두면 능력 장벽이 가장 낮다.
- Prompt: index search, trace presence filter, validation card의 guarded CTA와 carried action notice가 적절한 prompt다.

## 4) B.I.A.S diagnosis
- Block: route invisibility, recent-pack narrowing friction, raw JSON reliance가 가장 큰 block이다.
- Interpret: operational inspector copy와 trace disclaimer로 오해를 막는다.
- Act: detail에서 validation + guarded CTA + carried action notice + trace + summary를 같이 보여 판단 단계를 줄인다.
- Store: source path와 warnings를 명시해 다음 reopen 시 기억 비용을 낮춘다.

## 5) Peak-End design notes
- Peak: “matched paper slugs”와 `state.json` source path가 한 번에 잡히는 순간
- Pit: trace metadata가 evidence truth처럼 읽히는 순간
- Transition: recent list search/filter or 입력 -> fetch -> 요약 -> timeline
- End: regenerate 이후 next pack route에서도 action success를 확인하는 순간

## 6) Ethics Check
- Regret: 통과. 운영 정보임을 숨기지 않는다.
- Black Mirror: trace를 사람에게 scientific authority처럼 보이게 만들면 실패다.
- In Real-Life: 친절한 운영 콘솔처럼 보여야 한다.
- 대응:
  - “Operational trace only” 고정 copy
  - warnings와 validation을 같은 시야에 배치
  - trace metadata JSON은 접어두기

## 7) Concrete changes
- Route:
  - `GET /meeting-packs`
  - `GET /meeting-packs/:packId`
  - `GET /meeting-packs/:packId/trace`
  - `GET /meeting-packs/:packId/validate`
  - frontend routes `/meeting-packs` and `/meeting-packs/:packId`
- Component:
  - saved packs index
  - local search by title / `pack_id` / primary source / mode
  - trace-presence quick filter (`all`, `with trace`, `legacy trace-free`)
  - quick-open form
  - pack summary card
  - validation card
  - guarded regenerate/rerender CTA in detail validation
  - carried success notice across regenerate route transition
  - retrieval trace summary + timeline card
- Copy:
  - “Operational inspector for saved meeting pack artifacts.”
  - “Trace is selector/load observability only. It does not replace canonical evidence review.”
  - “These controls only rewrite or regenerate the saved draft artifact. They do not replace canonical evidence review.”
  - regenerate success notice persists onto the next pack route
- Default action:
  - `/meeting-packs`에서 recent saved pack 검색/필터 후 선택 또는 pack id 입력
  - detail에서는 summary 먼저, validation/action second, carried notice third, trace fourth, metadata JSON collapsed

## 8) Next PR-sized actions
1. retrieval trace filtering by action/outcome이 필요해질 때만 trace controls를 추가하기
2. saved packs index가 더 커지면 mode/readiness filters나 URL-state persistence를 검토하기
3. action 결과를 longer-lived activity log로 남길 필요가 생기면 lightweight action history를 검토하기

## 9) Review State Before Handoff Checkpoint (2026-05-10)
- Screen/Flow: `/meeting-packs/:packId` detail right rail
- Goal action: 사용자가 note handoff, rerender, regenerate, sharing 판단 전에 draft의 review/readiness state를 먼저 확인한다.
- Primary persona: saved meeting draft를 lab meeting이나 journal club에 재사용하기 전에 upstream note와 validation 상태를 점검하는 연구자
- Current friction:
  - detail header에는 readiness badge가 있었지만, right rail의 첫 action은 `Continue from this draft`였다.
  - Lazyweb reference pilot의 approval/review workflow 패턴은 generated artifact가 polished output처럼 보이기 전에 state/limitation cue를 action 가까이에 둬야 함을 시사했다.
- Quick Review (5 min):
  - 새 approval engine, route, schema, export flow는 추가하지 않는다.
  - read-only `Review state` summary를 right rail 맨 위에 추가해 readiness, markdown sync, validation warnings, linked notes, evidence refs를 먼저 보여준다.
- Full Review:
  - P0: 통과. generated meeting draft를 canonical evidence나 reviewed claim truth로 승격하지 않는다.
  - P1: 통과. handoff/maintenance 전에 review gate language가 먼저 보인다.
  - P2: 통과. 기존 `Validation` card와 guarded maintenance details는 유지한다.
  - 6P: problem은 draft reuse 전 과신이고, action은 pack detail review이며, happy ending은 upstream note와 validation state를 확인한 뒤 안전하게 handoff하는 것이다.
  - BMAP: motivation은 높고, ability는 compact rail summary로 좋아지며, prompt는 action 전 review-state card다.
  - B.I.A.S: Block은 action-first rail, Interpret는 draft/readiness separation, Act는 safer note/maintenance choice, Store는 반복 가능한 review-state rhythm이다.
  - Peak-End: peak는 detail 진입 직후 generated draft의 status를 읽는 순간이고, end는 maintenance action이 여전히 guarded details 안에 남는 것이다.
  - Ethics: Regret/Black Mirror/In Real-Life 모두 통과. sharing/export 확신을 부추기지 않고, generated artifact의 한계를 먼저 말한다.
- Concrete changes:
  - `frontend/src/app/pages/MeetingPackPage.tsx` right rail 상단에 read-only `Review state` card를 추가한다.
  - mock/backend Playwright tests에 right-rail heading order assertion을 추가한다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
