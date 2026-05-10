# UX Review Report - Primary Research Loop

Status: Current review plan
Date: 2026-03-30
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-30
Reviewer: Codex

## Input
- Screen/Flow: `/` -> `/papers` -> `/papers/:slug` -> `/workbench/:paperId` -> downstream handoff (`/protocol-cards`, `/meeting-packs`)
- Goal action: 연구자가 하나의 논문을 workspace로 가져와 읽고, review state를 확인한 뒤, workbench와 reusable artifact로 자연스럽게 이어간다.
- Primary persona: local-first biomedical research workspace를 daily driver로 쓰려는 연구자/대학원생
- Current friction: 개별 route는 많이 좋아졌지만, 전체 핵심 루프를 하나의 audit 단위로 보는 문서가 아직 없다. 그래서 patch는 누적돼도 전체 journey 기준의 gap과 regression 우선순위가 분산되기 쉽다.
- Success metric:
  - first-session `home -> paper detail -> workbench` completion
  - `note -> protocol` and `note -> meeting` handoff success
  - mock fallback/console noise 없는 primary loop 유지
- Constraints:
  - FastAPI + Vite + React Router + TailwindCSS 유지
  - `--pp-*` 토큰과 dark-first Lattice tone 유지
  - 현재 route structure와 existing UX reports 재사용
  - `rules/product-psychology/SKILL.md`
  - `rules/product-psychology/references/review-checklist.md`
  - `rules/product-psychology/references/bias-framework.md`
  - `rules/product-psychology/references/ethics-checklist.md`
  - `rules/product-psychology/references/prompt-templates.md`

## Quick Review (5 min)
- Block: 전체 product value는 `읽기 -> review -> handoff` 연결에서 드러나는데, review 문서는 아직 mostly screen-local이다.
- Interpret: triage, paper detail, workbench는 이미 강한 surfaces다. 다만 이 셋이 “하나의 biomedical research loop”로 얼마나 매끄럽게 이어지는지는 별도 audit이 필요하다.
- Act: 첫 정기 audit은 feature expansion보다 primary loop 유지/명확성/속도를 먼저 본다.
- Store: 사용자 기억에는 route보다 loop가 남는다. 이 문서는 그 loop를 canonical review unit으로 잡는다.
- Ethics first pass: route를 늘리는 대신 이미 있는 핵심 흐름의 이해 가능성과 trust를 먼저 점검하는 방향이라 안전하다.
- Decision: 이후 UI/UX review의 첫 번째 축은 항상 primary research loop로 둔다.

## Full Review
### P0
- `home -> papers -> note detail -> workbench`는 PaperPipe의 가장 높은 트래픽과 가장 높은 의미 밀도를 가진 경로다. 이 경로는 앞으로도 별도 regression and UX review rail로 유지해야 한다.
- 이 loop의 핵심 질문은 기능 유무가 아니다. “왜 여기서 시작해야 하는지”, “왜 note detail이 markdown viewer 이상인지”, “왜 workbench가 review surface인지”가 첫 30초 안에 읽히는지다.
- current route inventory를 보면 [TriageDashboard.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx), [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx), [PaperNoteDetailPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx), [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx) 가 사실상 one product loop다. 이 네 화면은 개별 화면보다 journey 묶음으로 검토해야 한다.

### P1
- downstream handoff는 이 primary loop의 일부다. 지금 기준으로는 `note -> protocol`과 `note/workbench -> meeting`이 가장 중요한 secondary exits다.
- 따라서 이 audit은 단순히 “workbench까지 가는가”에서 끝나지 않고, note context가 artifact create form에 carry-over 되는지, artifact detail이 다시 upstream note로 이어지는지까지 봐야 한다.
- handoff copy는 새 기능보다 먼저 점검해야 할 자산이다. `Save protocol card`, `Open in Workbench`, `Continue in note` 같은 명령형 affordance가 진짜 workflow language로 유지되는지 본다.

### P2
- primary loop review는 visual polish보다 finding/recovery를 같이 봐야 한다.
- 검색, note list filters, current-runtime honesty, mock banner absence, direct-open stability(`/ui/*`)는 이 loop의 보조 시스템이다.
- 즉 primary loop audit은 page beauty review가 아니라, reading and decision velocity review다.

### Full Review Coverage
- 6P storyboard context:
  - Problem: 연구자는 논문을 읽는 데서 끝내지 않고, structured review와 reusable artifact까지 이어가야 한다.
  - Emotion: “지금 읽고 있는 이 paper를 바로 다음 작업으로 넘기고 싶다”는 압축된 동기가 있다.
  - Action: 홈에서 시작해 note를 열고, workbench로 가고, 필요하면 protocol/meeting으로 넘긴다.
  - Struggle: 화면이 좋더라도 loop language가 약하면 사용자는 route 간 맥락을 다시 복구해야 한다.
  - Attempt: primary loop를 별도 audit unit으로 고정해 화면 사이의 transition quality를 같이 본다.
  - Happy Ending: 사용자는 PaperPipe를 “논문 뷰어”가 아니라 “읽기에서 artifact까지 이어지는 research workspace”로 기억한다.
- BMAP:
  - Motivation: 매우 높다. primary loop는 제품의 존재 이유와 직결된다.
  - Ability: 개별 화면은 좋아졌으니, 이제 context carry-over와 next-step clarity를 계속 유지하는 게 중요하다.
  - Prompt: home CTA, note CTA, workbench CTA, artifact handoff copy가 loop prompt의 핵심이다.
- B.I.A.S:
  - Block: route별 review는 있어도 loop-level review가 없으면 전체 product meaning이 분산될 수 있다.
  - Interpret: 사용자는 route들을 각각 해석하는 대신 한 흐름으로 제품을 기억한다.
  - Act: note -> workbench -> artifact handoff friction을 우선 점검한다.
  - Store: primary loop가 부드러울수록 제품 전체가 더 명확하게 기억된다.
- Peak-End:
  - Peak: note detail과 workbench는 이미 가장 강한 screens다.
  - Pit: home와 list 단계에서 loop framing이 약하면 그 강점이 늦게 보인다.
  - Transition: list -> note -> workbench -> artifact transitions가 review 핵심이다.
  - End: saved artifact detail에서 다시 note/workbench로 이어지는 감각까지 포함한다.
- Ethics:
  - Regret: 낮다. 새 기능을 늘리기보다 이미 있는 핵심 흐름을 더 명확히 보는 계획이다.
  - Black Mirror: 낮다. route catalog를 화려하게 포장하는 대신 실제 working loop를 점검한다.
  - In Real-Life: 실제 연구자 입장에서는 개별 화면보다 “한 paper가 내 workflow 안에서 어떻게 이어지나”가 더 중요하다.

## BMAP diagnosis
- Motivation: primary loop는 제품 가치를 가장 빠르게 검증하는 경로라 동기가 강하다.
- Ability: route별 UI는 이미 좋아졌기 때문에, 이제는 context carry-over와 action wording 유지가 핵심이다.
- Prompt: `Start here`, `Open in Workbench`, `Save protocol card`, `Continue in note`를 primary prompts로 고정해서 봐야 한다.

## B.I.A.S diagnosis
- Block: review 문서가 route별로 흩어져 있다.
- Interpret: 사용자는 screen set이 아니라 research loop로 제품을 이해한다.
- Act: 가장 먼저 보는 루프를 review의 canonical unit으로 삼는다.
- Store: primary loop audit이 쌓일수록 PaperPipe의 정체성이 더 일관되게 남는다.

## Peak-End design notes
- peak는 note detail과 workbench의 structured/review surfaces다.
- pit는 home/list 단계에서 loop framing이 약해질 수 있는 구간이다.
- transition은 `home -> papers -> note -> workbench -> protocol/meeting`이다.
- end는 artifact detail에서 upstream note/workbench로 돌아가는 continuity다.

## Concrete changes
- 이 문서는 다음 review loop에서 아래 순서로 사용한다.
  1. `/` first-session clarity
  2. `/papers` ingestion and recovery
  3. `/papers/:slug` review/provenance visibility
  4. `/workbench/:paperId` review depth and action tone
  5. `note -> protocol` handoff
  6. `meeting/protocol detail -> note` continuation
- 우선 체크할 실제 파일:
  - [TriageDashboard.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx)
  - [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx)
  - [PaperNoteDetailPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx)
  - [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx)
  - [ProtocolCardPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ProtocolCardPage.tsx)
  - [MeetingPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx)

## Ethics check results
- Regret: 낮음
- Black Mirror: 낮음
- In Real-Life: 이 계획은 실제 연구 작업의 핵심 루프를 먼저 보호한다.

## Next PR-sized actions
1. 다음 UX review 라운드에서 이 문서를 기준으로 `home -> papers -> note -> workbench` walkthrough를 한 번에 평가한다.
2. current runtime direct verify와 seeded backend rail을 이 loop 기준으로 묶어 체크리스트화한다.
3. `primary loop`에서 나온 finding만 따로 모아 다음 UI patch priority queue를 만든다.
