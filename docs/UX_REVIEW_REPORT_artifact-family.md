# UX Review Report - Artifact Family

Status: Current review plan
Date: 2026-03-30
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-30
Reviewer: Codex

## Input
- Screen/Flow: `/meeting-packs`, `/protocol-cards`, `/chart-packs`, `/method-comparisons`, `/image-evidence` and their detail routes
- Goal action: 연구자가 artifact lane을 별도 툴이 아니라 same research state의 downstream view로 이해하고, 언제 열어야 하는지와 어디서 파생됐는지를 즉시 읽는다.
- Primary persona: note/workbench 이후 reusable output을 만들고 재검토하는 연구자
- Current friction: 개별 lane UX는 많이 좋아졌지만, lane 간 공통 review contract는 아직 문서화가 약하다. 그래서 artifact family 전체의 정보 위계와 handoff 일관성을 같은 기준으로 보기 어렵다.
- Success metric:
  - artifact header에서 `when to use`와 `derived from` immediately visible
  - upstream note/workbench return path visibility
  - lane purpose confusion 감소
- Constraints:
  - FastAPI + Vite + React Router + TailwindCSS 유지
  - `--pp-*` tokens 유지
  - existing artifact pages and shared components 재사용
  - `rules/product-psychology/SKILL.md`
  - `rules/product-psychology/references/review-checklist.md`
  - `rules/product-psychology/references/bias-framework.md`
  - `rules/product-psychology/references/ethics-checklist.md`
  - `rules/product-psychology/references/prompt-templates.md`

## Quick Review (5 min)
- Block: artifact lane들은 각각 좋아졌지만, family-level contract가 아직 약하다.
- Interpret: 사용자는 chart/protocol/meeting/method/image lane을 별도 tool set이 아니라 one downstream artifact family로 느껴야 한다.
- Act: review 기준을 lane별 화면이 아니라 artifact family matrix로 재정렬한다.
- Store: artifact routes는 “saved object viewers”가 아니라 “grounded research outputs”로 기억돼야 한다.
- Ethics first pass: 새 entity system을 만들지 않고, existing lanes의 meaning consistency를 보는 계획이라 안전하다.
- Decision: artifact review는 이제 screen-by-screen보다 lane-family audit을 기본으로 삼는다.

## Full Review
### P0
- artifact family review의 첫 질문은 feature parity가 아니라 header semantics다.
- 모든 lane은 header에서 최소한 아래를 답해야 한다.
  - 언제 이 lane을 쓰는가
  - 어디서 파생됐는가
  - upstream note/workbench로 어떻게 돌아가는가
- 현재 repo는 이미 [ArtifactHeaderContext.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/components/ArtifactHeaderContext.tsx) 같은 shared primitive를 갖고 있어, family-level consistency audit이 현실적이다.

### P1
- family audit은 각 lane의 “next action”도 같이 본다.
- meeting/protocol/image는 note-first continuation이 강하고, chart/method는 downstream comparison or report stage framing이 중요하다.
- 따라서 artifact review 기준은 공통 header contract + lane-specific continuation contract의 2단 구조가 적절하다.

### P2
- empty states와 create entry points도 artifact family review 범위에 포함해야 한다.
- current runtime에서는 chart/image/method inventory가 zero일 수 있으므로, list/index honesty와 create CTA clarity 역시 artifact family UX의 일부다.
- saved detail만 보는 review는 불충분하다.

### Full Review Coverage
- 6P storyboard context:
  - Problem: artifact lanes가 separate tools처럼 읽히면 전체 product coherence가 약해진다.
  - Emotion: 사용자는 “이건 언제 열지?”를 lane마다 다시 해석해야 한다.
  - Action: saved artifact를 열고 검토하거나 새 artifact를 만든다.
  - Struggle: lane별로 purpose framing과 continuation language가 미세하게 달라질 수 있다.
  - Attempt: artifact family를 one matrix로 묶어 공통 contract를 검토한다.
  - Happy Ending: 사용자는 artifact lane을 같은 workspace의 downstream views로 자연스럽게 이해한다.
- BMAP:
  - Motivation: 높다. artifact는 읽기 이후 결과물 생산 단계다.
  - Ability: header meaning, continuation path, create CTA clarity가 핵심이다.
  - Prompt: `When to use`, `Derived from`, `Continue in note`, `Create ...`가 family prompts다.
- B.I.A.S:
  - Block: lane purpose가 늦게 보이면 artifact가 generic saved viewer처럼 읽힌다.
  - Interpret: provenance와 workflow purpose를 바로 말해야 한다.
  - Act: upstream/downstream handoff를 쉽게 해야 한다.
  - Store: 같은 family contract가 반복될수록 제품 전체가 더 일관되게 기억된다.
- Peak-End:
  - Peak: detail header에서 purpose와 provenance를 즉시 읽는 순간이다.
  - Pit: body를 훑어야 lane meaning을 이해하던 상태다.
  - Transition: create/index -> detail -> upstream note/workbench return이다.
  - End: artifact를 보고 끝나는 게 아니라, 다음 review action으로 이어지는 감각이다.
- Ethics:
  - Regret: 낮다. existing artifact들을 더 명확하게 설명하는 review 계획이다.
  - Black Mirror: 낮다. artifact를 canonical truth처럼 과장하지 않는다.
  - In Real-Life: 연구자는 artifact를 결과물로 쓰되, 항상 source note/evidence로 되돌아간다.

## BMAP diagnosis
- Motivation: artifact는 결과물 생산성과 바로 연결돼 있다.
- Ability: family-wide header and continuation consistency가 ability를 크게 좌우한다.
- Prompt: `When to use`, `Derived from`, `Continue in note`, `Continue after note review`, `Create ...`를 공통 prompt set으로 본다.

## B.I.A.S diagnosis
- Block: lane별로 meaning contract가 흐려질 수 있다.
- Interpret: artifact family를 one product layer로 읽히게 해야 한다.
- Act: header semantics와 continuation semantics를 같이 검토한다.
- Store: 같은 contract가 반복될수록 artifact lanes가 더 쉽게 기억된다.

## Peak-End design notes
- peak는 shared artifact header contract다.
- pit는 saved-object viewer처럼 보이는 순간이다.
- transition은 index/create -> detail -> upstream/downstream handoff다.
- end는 “artifact를 본 뒤 next step이 바로 보인다”는 느낌이다.

## Concrete changes
- 이 문서는 다음 family matrix로 사용한다.
  - `Meeting Pack`: meeting-ready narrative, note-first continuation
  - `Protocol Card`: note-linked protocol snapshot, note reopen
  - `Chart Pack`: chart/report output, source refs and downstream reuse
  - `Method Comparison`: compare methods/papers, selection rationale
  - `Image Evidence`: evidence bundle, note-first then downstream lane reopen
- 우선 체크할 실제 파일:
  - [MeetingPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx)
  - [ProtocolCardPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ProtocolCardPage.tsx)
  - [ChartPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ChartPackPage.tsx)
  - [MethodComparisonPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MethodComparisonPage.tsx)
  - [ImageEvidencePage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ImageEvidencePage.tsx)
  - [ArtifactHeaderContext.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/components/ArtifactHeaderContext.tsx)

## Ethics check results
- Regret: 낮음
- Black Mirror: 낮음
- In Real-Life: artifact family 전체를 같은 provenance contract로 보는 게 실제 연구 흐름에 맞다.

## Next PR-sized actions
1. artifact lanes를 family matrix 기준으로 점수화하는 follow-up section을 각 lane report에 추가한다.
2. zero-data lane도 index/create honesty를 포함해 audit checklist에 넣는다.
3. family review 결과에서 공통 copy/components를 더 재사용할 부분을 추린다.

## Implementation follow-up (2026-04-10, chart/protocol recommended-path emphasis)
- Scope:
  - [ChartPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ChartPackPage.tsx)
  - [ProtocolCardPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ProtocolCardPage.tsx)
- What changed:
  - chart-pack create now emphasizes `Recent saved runs` before manual paper/run entry
  - protocol-card create now emphasizes `Recent notes` before manual linked note/paper entry
  - both pages explicitly describe manual identifiers as fallback, not co-primary paths
- Why this matters:
  - family semantics were already correct at the header level, but create surfaces still asked the user to translate workflow intent into IDs too early
  - this patch keeps the artifact-family contract while reducing the first-scan friction on index/create lanes
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/chart-pack.mock.spec.ts e2e/protocol-card.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack index can create a new chart pack from the browser|backend chart pack quick-pick journey stays connected in the browser|backend protocol knowledge index can create a new protocol card from the browser|backend paper note detail can start a protocol card with note context from the browser"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack index layout|protocol knowledge index layout|mobile.*chart pack index layout|mobile.*protocol knowledge index layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack index layout|protocol knowledge index layout|mobile.*chart pack index layout|mobile.*protocol knowledge index layout"`
