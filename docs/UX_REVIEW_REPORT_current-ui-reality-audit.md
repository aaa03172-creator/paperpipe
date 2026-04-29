# UX Review Report - Current UI Reality Audit

Status: Current review
Date: 2026-04-07
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Input
- Screen/Flow: `/` -> `/papers` -> `/papers/:slug` -> `/workbench/:paperId` -> artifact detail routes
- Goal action: 연구자가 논문을 가져오고, 읽고, claim/evidence를 검증하고, review state를 저장한 뒤, meeting/protocol/chart/image/method artifact로 자연스럽게 이어간다.
- Primary persona: local-first biomedical research workspace를 매일 사용하는 biomedical / medical researcher
- Current friction: 현재 제품은 더 이상 단순 viewer set은 아니지만, project context가 runtime-backed surface로 보이지 않고, papers list와 workbench control density 때문에 제품 차별점이 덜 직접적으로 드러난다.
- Success metric:
  - 첫 화면에서 `resume -> context -> queue lens`가 즉시 읽힌다
  - note/detail에서 reading과 structured review가 끊기지 않는다
  - artifact detail에서 canonical evidence boundary가 자연스럽게 이해된다
  - papers list가 단순 index가 아니라 "왜 이 앱을 써야 하는지"를 더 잘 보여준다
- Constraints:
  - FastAPI + Vite + React Router + TailwindCSS 유지
  - current paper/run/artifact runtime contract 유지
  - `--pp-*` token system과 dark-first Lattice tone 유지
  - incremental patch 우선, route rewrite 금지
  - current signoff slice를 깨지 않는 방향 우선

## 1. Executive summary

### Quick Review (5 min)
- 현재 UI는 예전보다 훨씬 명확하다. home은 `Continue current work`, `Workspace context`, `Queue lens`로 정리됐고, note/workbench/artifact detail도 하나의 research thread처럼 읽히기 시작했다.
- 지금 가장 큰 문제는 "화면이 없다"가 아니라 "강한 기능이 덜 직접적으로 가치로 읽힌다"는 점이다.
- 특히 papers list는 여전히 index처럼 보이고, workbench는 differentiated surface이지만 control density 때문에 핵심 task가 늦게 읽힌다.

현재 UI는 이미 `project-framed, paper-executed, source-grounded, review-forward` 방향으로 많이 정리되어 있다. 다만 runtime-backed project surface가 아직 없고, papers list가 여전히 viewer/index 성격에서 크게 벗어나지 못하며, workbench의 조작 밀도가 Linear식 고속 review surface보다 전문가용 콘솔처럼 읽히는 순간이 남아 있다. note detail과 artifact detail은 강해졌고 provenance boundary도 좋아졌지만, 제품의 차별점이 home과 papers list에서 아직 완전히 압축되어 전달되지는 않는다.

가장 큰 문제 3개
- `Paper Notes` list가 제품의 핵심 가치보다 검색/필터 index처럼 먼저 읽힌다.
- `AnalysisWorkbench`는 강력하지만 control density가 높아 review task보다 설정 표면이 먼저 보인다.
- `Project`는 제품 정체성에서 중요하지만, 아직 runtime contract가 없어 UI에서 강하게 세우면 과장된다.

가장 먼저 손대야 할 부분 3개
- papers list를 "searchable note warehouse"에서 "research handoff index"로 재프레이밍
- workbench 상단/rail의 고빈도 review action과 저빈도 session control 분리
- note/workbench/artifact를 잇는 provenance / next-action copy를 더 압축해서 첫 시선에 보이게 만들기

## 2. Current UI reality map

### 실제 존재하는 주요 화면 / 기능 / 흐름

#### Home / triage
- 파일: [TriageDashboard.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx)
- 역할:
  - `Continue current work`로 blocked/review/reading 재개
  - `Workspace context`로 현재 전체 workspace load 요약
  - `Queue lens`로 action-needed papers 정리
  - `Saved outputs`로 artifact family 진입
- 실제 사용자 경험:
  - 이제 첫 화면의 목적은 비교적 명확하다.
  - `reader app`보다 `work resumption surface`에 가깝다.
- 헷갈리는 지점:
  - `Workspace context`는 honest하지만 아직 project가 아니라 lightweight context라는 점을 사용자가 곧바로 이해해야 한다.
  - `Queue lens`는 잘 절제됐지만, 아직 real queue container는 아니다.

#### Paper Notes list
- 파일: [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx)
- 역할:
  - saved note index
  - PDF import
  - search / tags / status / structure / reading-assist filter
- 실제 사용자 경험:
  - 기능은 많고 실용적이다.
  - 하지만 첫인상은 "좋은 index"이지 "grounded research workspace"는 아니다.
- 헷갈리는 지점:
  - `Import PDF`, `check pickup`, search/filter density는 강하지만, note가 downstream review / artifact / meeting과 어떻게 연결되는지는 덜 보인다.
  - list에서 note의 "next best action"이 전면화되지 않는다.

#### Paper note detail
- 파일: [PaperNoteDetailPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx)
- 역할:
  - paper reading
  - note metadata / tags / aliases / references
  - `Review focus` bridge
  - workbench handoff
- 실제 사용자 경험:
  - reading surface가 중심이고, structured review bridge가 예전보다 훨씬 좋아졌다.
  - `Read / Open review / Save protocol card` 흐름이 실제 task language로 보인다.
- 헷갈리는 지점:
  - 여전히 중심 column은 reading 우위이고, full structured depth는 rail에 남아 있다.
  - provenance / uncertainty는 존재하지만 reading 도중 가장 강한 신호는 아직 아니다.

#### Analysis workbench
- 파일: [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx)
- 역할:
  - PDF / claim / evidence / saved checks / parser / artifact generation을 함께 다루는 review surface
- 실제 사용자 경험:
  - 제품에서 가장 differentiated surface다.
  - source-grounded review, highlight, claim repair, saved review state가 강하다.
- 헷갈리는 지점:
  - `Reading style`, `Context profile`, `View`, `Highlight`, refresh/repair/rebuild, claim review notice, artifact panel이 동시에 보여 인지 부하가 높다.
  - 핵심 task는 강하지만, 상단에서 "설정이 많은 파워툴"처럼 읽히는 순간이 있다.

#### Artifact detail family
- 파일:
  - [MeetingPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx)
  - [ProtocolCardPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ProtocolCardPage.tsx)
  - [ImageEvidencePage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ImageEvidencePage.tsx)
  - [MethodComparisonPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MethodComparisonPage.tsx)
  - [ChartPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ChartPackPage.tsx)
- 역할:
  - downstream artifact inspection / reuse / export
- 실제 사용자 경험:
  - 지금은 family coherence가 좋다.
  - `Derived artifact`와 `Canonical evidence lives upstream`가 명확하다.
- 헷갈리는 지점:
  - detail은 좋아졌지만, artifact index/create surface는 아직 family language가 상대적으로 약하다.

#### Runtime readiness
- 파일: [RuntimeReadinessPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/RuntimeReadinessPage.tsx)
- 역할:
  - local-first trust, mock/live boundary, dependency readiness 확인
- 실제 사용자 경험:
  - local-first / privacy / runtime readiness 신뢰감을 주는 좋은 supporting surface다.
- 헷갈리는 지점:
  - core research loop 안에서 직접 드러나기보다 별도 diagnostics page로 분리돼 있다.

## 3. Scorecard

| 기준 | 점수 | 근거 |
|---|---:|---|
| A. 첫 화면 명확성 | 4/5 | home은 이제 `Continue current work`, `Workspace context`, `Queue lens`로 제품 목적이 꽤 빨리 읽힌다. 다만 true project surface가 없어서 "project workspace" 감각은 아직 약하다. |
| B. 근거 추적성 | 4/5 | note/workbench/artifact detail에서 provenance boundary와 evidence-return path가 강하다. 다만 papers list와 일부 중심 column에서 uncertainty가 first-class signal은 아니다. |
| C. 정보 구조 일관성 | 3/5 | paper -> review -> artifact continuity는 좋아졌지만, project / meeting / decision / experiment를 묶는 runtime-backed container는 없다. |
| D. 읽기 경험 | 4/5 | note detail의 `Review focus` bridge로 reading과 structuring 사이가 훨씬 가까워졌다. 그러나 full structured depth는 여전히 rail 편중이다. |
| E. 작업 전환 속도 | 4/5 | home resume, `Open review`, artifact continuity 덕분에 next action이 빨라졌다. 다만 papers list에서 바로 review/action으로 넘어가는 힘은 아직 약하다. |
| F. 탐색성과 회수성 | 3/5 | list search/filter는 강하고 tags/status도 있다. 하지만 cross-object recovery, project-level recovery, "나중에 어디서 다시 찾는가"는 아직 paper-centric다. |
| G. 밀도와 피로도 균형 | 3/5 | workbench는 강하지만 피로도가 높고, papers list는 필터/조작 밀도에 비해 hierarchy peak가 약하다. home은 많이 나아졌다. |
| H. 고속 조작성 | 2/5 | 전역 command palette/shortcut flow는 거의 없고, rail shortcut nav 정도만 보인다. Linear식 triage speed는 아직 약하다. |
| I. local-first / privacy 신뢰감 | 4/5 | runtime readiness, fallback guidance, upstream/canonical boundary, mock/live distinction은 좋다. 이 감각이 home/list 전반에 더 일관되게 퍼지면 더 강해질 수 있다. |
| J. 결과물 생산성 | 4/5 | artifact family는 현재 강점이다. meeting/protocol/chart/image/method가 research loop에 연결돼 있다. 다만 index/create 단계의 framing은 detail보다 약하다. |

## 4. Benchmark translation

### NotebookLM
- 가져오면 좋은 것
  - source-grounded interaction이 항상 먼저 보이는 framing
  - source로 돌아가는 citation confidence
  - notebook 단위의 명시적 context
- 그대로 맞지 않는 것
  - chat-first 경험을 제품 중심으로 두는 것
  - source를 대화의 부속물처럼 취급하는 것
- PaperPipe 번역안
  - chat surface를 새로 키우기보다 note/workbench에서 `evidence-return path`를 더 직접 드러내기
  - home/papers list에서 "이 note가 어떤 review loop로 이어지는가"를 보이게 하기

### Obsidian
- 가져오면 좋은 것
  - note를 정적 문서가 아니라 연결 가능한 knowledge node로 보는 감각
  - local-first / user-controlled data 신뢰감
  - backlinks / related context의 회수성
- 그대로 맞지 않는 것
  - graph 자체를 전면 제품 표면으로 끌어올리는 것
  - free-form note graph에 product meaning을 과도하게 맡기는 것
- PaperPipe 번역안
  - full graph view보다 note/workbench/artifact 간 reversible links 강화
  - runtime readiness, source path, saved state path를 더 일관된 local-first language로 묶기

### Notion
- 가져오면 좋은 것
  - 같은 정본을 여러 view에서 재사용하는 linked database 감각
  - entity relation이 드러나는 summary strip
  - object 간 relation을 숨기지 않는 layout
- 그대로 맞지 않는 것
  - generic database SaaS 느낌
  - biomedical evidence review를 table CRUD로 환원하는 것
- PaperPipe 번역안
  - `HomeWorkspaceSummary`처럼 summary contract를 먼저 강화
  - project surface는 later, but when real, it should be `paper context wrapper`, not object owner

### Linear
- 가져오면 좋은 것
  - triage language
  - 빠른 상태 전이
  - dense but fast interface
- 그대로 맞지 않는 것
  - issue tracker semantics를 그대로 paper/review 흐름에 덮는 것
  - 모든 연구 객체를 status machine으로 보는 것
- PaperPipe 번역안
  - `Queue lens`를 operational lens로 유지
  - workbench에서 고빈도 action은 전면, 저빈도 control은 접기
  - papers list에서 `next review action`을 더 직접 노출

### Elicit
- 가져오면 좋은 것
  - screening / extraction / report 단계의 연구 workflow 감각
  - AI 출력 옆에 근거를 붙여 검증하게 하는 구조
  - question refinement에서 claim/evidence relationship을 강조하는 방식
- 그대로 맞지 않는 것
  - stage wizard처럼 forward-only flow를 강제하는 것
  - source-grounded local workspace보다 extraction pipeline 중심으로 보는 것
- PaperPipe 번역안
  - note/workbench/artifact를 단계라기보다 reversible surfaces로 유지
  - claim/evidence/provenance를 reading 중에도 더 visible하게 유지

### 추가로 참고할 만한 구조
- Airtable/Coda 류의 linked summary pattern
  - 그대로 table SaaS를 모방할 필요는 없다.
  - 대신 `summary strip + linked object handoff`는 home/papers list에 번역 가능하다.
- Roam식 backlink recovery
  - full graph는 과하지만, "이 artifact를 만든 upstream note / 이 note가 연결된 downstream artifact" 회수성은 더 강화할 만하다.

## 5. Priority fixes

### Full Review (P0 / P1 / P2)

### P0

#### 1. Paper Notes list가 제품의 차별점을 가장 약하게 보여준다
- 문제
  - [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx)는 강력한 index지만, 현재는 `import + search/filter + pagination`이 앞에 보이고, review/artifact continuity는 거의 보이지 않는다.
- 왜 문제인지
  - home에서 올라온 연구 흐름이 list에서 다시 "문서 창고"로 평평해진다.
- 사용자 손실
  - 사용자는 list를 "다시 찾아보는 페이지"로만 쓰고, `다음 행동이 뭐지?`를 빨리 못 본다.
- 개선 방향
  - 각 row 또는 상단 summary에 `next action`, `saved review state`, `artifact-ready` 같은 research handoff 신호를 더 붙인다.
- 구현 단위
  - 페이지: [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx)
  - 컴포넌트: existing `StatusBadge`, `OperationalStateSummary`, `ContentReviewSummary` 재사용
  - 문구: header/subcopy를 index language에서 handoff language로 조정

#### 2. Workbench는 강하지만 너무 많은 control이 동시에 전면에 있다
- 문제
  - [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx)의 상단과 notice area는 review보다 session tuning이 먼저 보이는 순간이 있다.
- 왜 문제인지
  - power-user에게는 유용하지만, 핵심 differentiated value인 claim/evidence review가 덜 직접 읽힌다.
- 사용자 손실
  - 사용자는 "여기서 뭘 먼저 하면 되는지"보다 "설정이 많다"를 먼저 느낄 수 있다.
- 개선 방향
  - 고빈도 review action만 전면에 두고, 저빈도 session controls는 기본 접기
  - claim review / saved review / access route를 더 압축된 one-scan hierarchy로 유지
- 구현 단위
  - 페이지: [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx)
  - 레이아웃: [WorkbenchLayout.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/layouts/WorkbenchLayout.tsx)

#### 3. provenance / uncertainty는 강점인데 primary reading surfaces에서 여전히 약간 숨는다
- 문제
  - note detail에서 `Review focus` bridge는 좋아졌지만, 핵심 provenance / uncertainty signal은 여전히 right rail이나 downstream surface에 더 강하다.
- 왜 문제인지
  - PaperPipe의 차별점은 "읽기"가 아니라 "근거 기반 다음 행동"인데, 그 차별점이 reading first glance에서 완전히 압축되지는 않는다.
- 사용자 손실
  - 읽는 중 claim confidence나 unresolved evidence를 빨리 판단하지 못한다.
- 개선 방향
  - note detail center에서 top unresolved claim / provenance cue를 더 명시적으로 유지
  - reading body 시작부의 hierarchy를 조금 더 review-forward하게 재조정
- 구현 단위
  - 페이지: [PaperNoteDetailPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx)
  - 컴포넌트: existing `Review focus`, `WorkspaceContextStrip`

### P1

#### 4. `Project`는 중요하지만 UI가 아니라 contract가 먼저다
- 문제
  - 제품 정체성은 workspace / project를 말하지만, 실제 runtime에는 project route나 summary payload가 없다.
- 왜 문제인지
  - 지금 여기서 project rows를 키우면 capability over-promise가 된다.
- 사용자 손실
  - 과장된 chrome은 오히려 신뢰를 깬다.
- 개선 방향
  - 당분간 `Workspace context`와 `Queue lens`를 honest하게 유지
  - 다음 단계는 `ProjectSummaryLite` contract discovery이지 UI 확장이 아니다
- 구현 단위
  - 문서/contract: [Project_Queue_Runtime_Contract_Scoping_2026-04-03.md](/Users/jangseongjin/paperpipe/docs/reports/Project_Queue_Runtime_Contract_Scoping_2026-04-03.md)
  - backend 후보: `/workspace-summary`와 유사한 작은 summary contract

#### 5. Artifact detail은 강한데 index/create surface는 상대적으로 덜 강하다
- 문제
  - detail route의 continuity copy는 좋지만, artifact family index/create entry는 아직 उत्पाद surface로서의 family coherence가 detail만큼 강하지 않다.
- 왜 문제인지
  - 결과물을 만들기 전 단계에서 family value를 덜 직관적으로 느낀다.
- 사용자 손실
  - 사용자는 artifact family를 "결과물 보기 도구"로만 이해할 수 있다.
- 개선 방향
  - index/create empty state나 subcopy에서 `derived artifact from saved review` language를 더 일관되게 사용
- 구현 단위
  - 페이지:
    - [MeetingPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx)
    - [ProtocolCardPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ProtocolCardPage.tsx)
    - [ImageEvidencePage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ImageEvidencePage.tsx)
    - [MethodComparisonPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MethodComparisonPage.tsx)
    - [ChartPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ChartPackPage.tsx)

### P2

#### 6. 고속 조작성은 아직 약하다
- 문제
  - 전역 keyboard flow, command palette, rapid triage command가 거의 없다.
- 왜 문제인지
  - 바쁜 연구자는 반복 작업이 빠르게 압축되길 원한다.
- 사용자 손실
  - 반복 review, jump, open, save 작업이 클릭 기반으로 남는다.
- 개선 방향
  - global command palette보다 먼저 local hot action shortlist부터 도입
- 구현 단위
  - home / list / workbench의 keyboard-first action affordance부터 작은 범위로 시작

### 6P storyboard context
- Problem: 연구자는 논문을 읽고 끝내는 것이 아니라, 근거를 검증하고 다음 행동으로 넘겨야 한다.
- Emotion: `이 claim을 믿어도 되나`, `바로 회의/실험 산출물로 넘겨도 되나`가 핵심 감정이다.
- Action: home -> papers list or note -> workbench -> artifact detail
- Struggle: 현재는 강한 기능이 흩어져 있어 list와 workbench에서 mental stitching cost가 남는다.
- Attempt: home은 이미 많이 좋아졌고, 이제 list handoff와 workbench hierarchy를 더 다듬어야 한다.
- Happy Ending: 사용자는 PaperPipe를 paper viewer가 아니라 grounded research workspace로 기억한다.

### BMAP diagnosis
- Motivation
  - 높다. 사용자는 already evidence-backed review와 artifact handoff를 원한다.
- Ability
  - 중상이다. 주요 기능은 구현돼 있고, hierarchy 조정만으로 체감 개선 여지가 크다.
- Prompt
  - home은 좋아졌다.
  - papers list와 workbench의 first-scan prompt는 아직 더 좋아질 수 있다.

### B.I.A.S diagnosis
- Block
  - project runtime 부재
  - list surface의 index framing
  - workbench control density
- Interpret
  - home과 artifact detail은 잘 읽히지만, papers list는 여전히 warehouse처럼 읽힌다.
- Act
  - next action / unresolved evidence / saved review state를 papers list와 note center에서 더 전면화해야 한다.
- Store
  - provenance와 continuity가 더 직접 보일수록 제품 기억이 `viewer set`이 아니라 `research workspace`로 고정된다.

### Peak-End design notes
- Peak
  - home `Continue current work`
  - note `Review focus`
  - workbench evidence surface
  - artifact detail continuity card
- Pit
  - papers list header/rows
  - workbench 상단 설정 밀도
- Transition
  - `home -> papers list`
  - `note -> workbench`
  - `artifact detail -> upstream note`
- End
  - 현재 detail artifact end는 좋다. list 진입부와 workbench 시작부를 더 정리하면 loop가 더 강해진다.

### Ethics check results
- Regret: 낮음
- Black Mirror: 낮음
- In Real-Life: 높음
- 메모:
  - local-first trust, runtime clarity, provenance boundary를 강화하는 방향은 실제 연구 workflow와 맞다.
  - fake project chrome은 여전히 피해야 한다.

## 6. Proposed UX structure

### 정보 구조 제안
- Home
  - `Continue current work`
  - `Workspace context`
  - `Queue lens`
  - `Saved outputs`
- Paper surfaces
  - `Paper Notes` list
  - `Read` surface
  - `Review` surface
- Artifact surfaces
  - downstream derived artifact family
- Supporting trust surface
  - `Runtime readiness`

### 화면 간 이동 구조
- home -> note detail
- home -> workbench
- home -> queue lens row -> note/workbench
- papers list -> note detail
- note detail -> workbench
- workbench -> artifact detail
- artifact detail -> upstream note / review

### 핵심 3개 작업 흐름

#### 1. Resume existing review
- Home `Continue current work`
- note or workbench directly
- save/repair review state
- artifact detail only when downstream result is needed

#### 2. Find and continue a paper
- `Paper Notes` list
- note detail
- `Review focus`
- workbench
- derived artifact if needed

#### 3. Start from a downstream artifact and recover upstream truth
- artifact detail
- continuity card
- upstream note
- workbench if claim/evidence validation is needed

### 첫 화면 / 프로젝트 화면 / paper deep read / evidence view / artifact export 제안
- 첫 화면
  - 현재 구조 유지. 이미 correct하다.
- 프로젝트 화면
  - 지금은 만들지 않는다.
  - `Workspace context`를 lightweight project proxy로 유지한다.
- paper deep read
  - note detail을 계속 중심 surface로 유지하되, reading body 시작부를 더 review-forward하게 정리
- evidence view
  - workbench를 계속 primary evidence surface로 유지
  - settings보다 review action 우선
- artifact export
  - current artifact detail continuity 유지
  - index/create에서도 same family language 강화

## 7. Concrete implementation suggestions

### 실제 수정 후보 파일 / 컴포넌트
- home
  - [TriageDashboard.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx)
- papers list
  - [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx)
- note detail
  - [PaperNoteDetailPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx)
- workbench
  - [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx)
  - [WorkbenchLayout.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/layouts/WorkbenchLayout.tsx)
- shared primitives
  - [WorkspaceContextStrip.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/components/WorkspaceContextStrip.tsx)
  - [OperationalStateSummary.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/components/OperationalStateSummary.tsx)
  - [ContentReviewSummary.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/components/ContentReviewSummary.tsx)

### 문구 수정안
- papers list header
  - 현재: `Search saved notes, filter by extracted structure, and open the paper detail you need.`
  - 제안: `Find the next paper to review, reopen saved structure, or continue grounded evidence work.`
- papers list import card
  - 현재 import utility 중심
  - 제안: `Start a new paper note when automatic pickup is not ready. Review and artifact flows stay attached once the note is saved.`
- workbench controls
  - `View` -> `Panel density`
  - `Highlight` -> `Evidence highlight`
  - low-frequency controls는 `Session controls` 안으로

### 버튼 / 패널 / 탭 / 레이아웃 개선안
- papers list
  - 상단 filter band 유지
  - 대신 summary strip 추가:
    - saved notes
    - structured notes
    - review-needed
    - latest updated
  - row에 small handoff cell 추가:
    - `Resume review`
    - `Open reading`
    - `Artifact ready` if applicable
- note detail
  - `Review focus` card의 top unresolved / saved evidence link를 한 단계 더 눈에 띄게
  - right rail의 중복 설명은 줄이고, center bridge의 next action은 유지
- workbench
  - header `Workspace context` strip 유지
  - session tuning details는 collapsed by default
  - claim review notice는 stronger, settings noise는 lower

### 삭제해도 되는 UI
- workbench 상단의 항상 노출되는 저빈도 control 조합 일부
- papers list에서 설명 없이 많이 노출되는 filter helper text 일부
- artifact create/index surfaces의 중복 explanatory copy 일부

### 오히려 강조해야 할 UI
- `Continue current work`
- `Review focus`
- `Workspace context`
- `Queue lens`
- `Derived artifact`
- `Canonical evidence lives upstream`

## 8. Patch plan

### PR1. Papers list를 handoff index로 재프레이밍
- 목적
  - 가장 약한 "why PaperPipe" surface 개선
- 수정 범위
  - [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx)
  - existing badges/summaries 재사용
- 기대 효과
  - list가 warehouse보다 research handoff surface로 읽힘
- 리스크
  - row density 증가
  - filter band와 summary band가 충돌할 수 있음

### PR2. Workbench controls를 task-first로 재배치
- 목적
  - evidence review를 settings보다 먼저 보이게
- 수정 범위
  - [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx)
  - [WorkbenchLayout.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/layouts/WorkbenchLayout.tsx)
- 기대 효과
  - 첫 시선에서 핵심 task가 더 빨리 읽힘
- 리스크
  - power-user가 기존 control 위치 변화에 적응 필요

### PR3. Note detail center bridge를 provenance-forward하게 강화
- 목적
  - reading과 structuring 사이의 마지막 마찰 줄이기
- 수정 범위
  - [PaperNoteDetailPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx)
- 기대 효과
  - note detail이 진짜 evidence-assisted reading surface로 더 가까워짐
- 리스크
  - center column 과밀 위험

### PR4. Artifact index/create family language 정리
- 목적
  - detail에서 강한 continuity를 entry surfaces까지 확장
- 수정 범위
  - artifact family pages index/create copy
- 기대 효과
  - 결과물 생산성이 더 일관되게 보임
- 리스크
  - copy-only change처럼 보여 체감 개선이 제한적일 수 있음

### PR5. ProjectSummaryLite는 UI가 아니라 contract discovery로만 시작
- 목적
  - fake `Active projects` 없이 다음 단계 열 준비
- 수정 범위
  - backend / schema scoping only
- 기대 효과
  - future project surface를 위한 honest foothold
- 리스크
  - 너무 빨리 UI를 붙이면 다시 과설계로 돌아감

## 가장 적은 수정으로 가장 큰 체감 개선을 만드는 5개 변경
- [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx) header와 row를 `index`에서 `handoff` language로 바꾸기
- [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx) 상단에 compact research summary strip 추가하기
- [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx) 저빈도 controls를 `Session controls` 아래로 접기
- [PaperNoteDetailPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx) `Review focus` 안의 unresolved evidence cue를 더 눈에 띄게 만들기
- artifact family index/create copy를 `Derived artifact from saved review` 언어로 통일하기

## Implementation follow-up (2026-04-08, papers list handoff framing)
- `PaperNotesListPage` now frames the list as a research handoff surface, not just a saved-note warehouse.
- The header copy now points users toward review continuation instead of generic detail lookup.
- A compact `Visible now` strip was added above the list body. It uses only current-page counts and explicitly says it reflects the currently visible notes after filters and pagination.
- Each row now carries a `Next action` block using existing note/runtime truth:
  - `Refresh checks in Workbench` when saved checks are missing
  - `Review in Workbench` or `Resume review` when saved review work is ready
  - `Open note` when the note should be reopened before deeper review
- This patch intentionally avoided adding:
  - project chrome
  - fake queue semantics
  - new backend payloads
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "paper notes list surfaces action-needed state using workbench vocabulary|paper notes list finds structured-signal matches and surfaces structured affordances|backend paper notes index can import a local PDF from the browser"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "paper notes list layout" --update-snapshots`

## Implementation follow-up (2026-04-08, workbench control compression)
- `AnalysisWorkbench` now keeps the highest-frequency review actions visible on desktop:
  - `Run deep read`
  - `Refresh`
  - `Refresh checks`
  - reading style / context profile
- Lower-frequency tuning and maintenance controls now live inside a collapsed `Session controls` block on desktop.
- The moved controls are still available, but they no longer compete with the main review loop in the first scan:
  - `Verify checks`
  - `Fresh retrieval`
  - `Theme`
  - `Panel density`
  - `Evidence highlight`
  - `Rebuild saved checks`
- This keeps the workbench differentiated as an evidence-review surface without pretending the settings disappeared.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend workbench preserves content review context when opened in issue focus mode"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench shell layout|mobile.*workbench shell layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench shell layout|mobile.*workbench shell layout"`

## Implementation follow-up (2026-04-08, note detail provenance-forward bridge)
- `PaperNoteDetailPage` now makes the saved review trust state more explicit inside the center-column `Review focus` bridge.
- The bridge now exposes a dedicated `Trust state` summary before the focus card. It keeps the distinction between:
  - missing structured review state
  - unresolved evidence blocking downstream trust
  - ambiguous evidence that still needs review
  - grounded evidence
  - thin-but-saved evidence depth
- The focus card now labels the anchor explicitly as a saved evidence or saved claim anchor instead of relying on surrounding context alone.
- The bridge also surfaces a provenance line even when a human-readable page/section location is missing:
  - `Source anchor: ...` when a concrete location exists
  - `Source anchor lives in saved structured state.` when the saved structured anchor is present but not rendered as a human-readable location
- This keeps note detail closer to an evidence-assisted reading surface without inventing certainty or pretending every saved anchor has a clean textual citation.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "structured paper note detail keeps review focus close to reading"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "paper notes detail renders structured actions, run history, and structured claims cards"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "structured paper note detail layout|paper note detail layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "structured paper note detail layout|paper note detail layout"`

## Implementation follow-up (2026-04-08, artifact entry family language)
- Artifact detail pages were already using `Derived artifact` and explicit upstream-evidence continuity.
- This patch brings the same family language to the entry surfaces for:
  - `MeetingPackPage`
  - `ProtocolCardPage`
  - `MethodComparisonPage`
  - `ChartPackPage`
  - `ImageEvidencePage`
- The entry surfaces now speak more consistently about:
  - saved derived artifacts
  - downstream reuse
  - upstream note/review continuity
  - trust calibration before export or handoff
- The patch stayed bounded to copy and helper-callout hierarchy only:
  - no route changes
  - no schema changes
  - no new project or queue chrome
- The main design intent is that artifact detail should no longer feel like one product and artifact index/create should no longer feel like another.
- One small test-stabilization change accompanied this copy pass:
  - meeting-pack backend visual index now masks dynamic count summaries and “older drafts hidden” controls that drift as backend visual fixtures accumulate over time
  - the visual helper also normalizes those dynamic labels before screenshot capture so desktop/mobile meeting-pack index snapshots no longer depend on accumulated fixture counts
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts e2e/protocol-card.mock.spec.ts e2e/image-evidence.mock.spec.ts e2e/method-comparison.mock.spec.ts e2e/chart-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route|backend protocol knowledge index can create a new protocol card from the browser|backend method comparison index can create a new comparison from the browser|backend chart pack index can create a new chart pack from the browser"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "meeting pack index layout|protocol knowledge index layout|image evidence index layout|method comparison index layout|chart pack index layout|mobile.*meeting pack index layout|mobile.*protocol knowledge index layout|mobile.*image evidence index layout|mobile.*method comparison index layout|mobile.*chart pack index layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "meeting pack index layout|protocol knowledge index layout|image evidence index layout|method comparison index layout|chart pack index layout|mobile.*meeting pack index layout|mobile.*protocol knowledge index layout|mobile.*image evidence index layout|mobile.*method comparison index layout|mobile.*chart pack index layout"`

## Implementation follow-up (2026-04-10, papers-list hierarchy tune and meeting-pack visual harness correction)
- This patch stayed inside the current audit recommendation:
  - no route rewrite
  - no new summary surface
  - no new backend payload
- `PaperNotesListPage` now makes the manual PDF import lane read more clearly as a fallback instead of a co-primary action:
  - the existing `Add your own PDF` card was visually demoted into an `Optional fallback`
  - the import CTA now uses the existing outline button treatment
  - helper copy was shortened so search/filter/review work stays visually ahead of setup explanation
- The existing row-level `Next action` block was not replaced. It was given a clearer boxed surface so the already-shipped handoff model reads earlier in the first scan.
- Filter helper copy was also shortened in-place:
  - tag helper text is tighter
  - the filter explanation now states only that filters narrow the current list
- No new IA was added here on purpose. The design intent is to make the current list structure read more clearly, not to introduce another layer of chrome.
- One test-only stabilization fix was paired with this patch:
  - the meeting-pack backend visual helper now checks for grouped title labels instead of assuming those titles live inside each `article`
  - this matches the current grouped DOM on the saved meeting-pack index and restores screenshot signoff without changing product behavior
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "paper notes list surfaces action-needed state using workbench vocabulary|paper notes list active filters keep removal and recovery controls in keyboard order|backend paper notes index can import a local PDF from the browser"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "paper notes list layout|meeting pack index layout|mobile.*meeting pack index layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "paper notes list layout|meeting pack index layout|mobile.*meeting pack index layout"`

## Implementation follow-up (2026-04-10, workbench review-focus de-duplication)
- This patch stayed inside the current audit recommendation:
  - no route rewrite
  - no new header surface
  - no backend/schema change
- `AnalysisWorkbench` already had a stronger top summary strip than earlier versions. This follow-up keeps that strip as the primary one-scan status surface instead of layering another summary on top of it.
- The old claim-review notice under the header repeated information that was already visible in `Workspace context`:
  - claim review state
  - issue-focus mode
  - saved review state separation
- The notice now reads as `Review focus` instead of a second `Claim review` summary:
  - flagged states emphasize what still needs checking before downstream reuse
  - unavailable states explain that saved checks can continue independently
  - clear states explain what focus mode changes without pretending a new issue exists
- This keeps the workbench differentiated as an evidence-review surface while reducing duplicated cognitive load in the first scan.
- The design intent here is compression, not expansion:
  - `Workspace context` stays responsible for status summary
  - `Review focus` now behaves like a use-rule card for the current review mode
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workbench preserves content review context when opened in issue focus mode|backend keeps unavailable content review distinct from clear state|backend workbench reuses the same operational state summary language as list and rail"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench shell layout|mobile.*workbench shell layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench shell layout|mobile.*workbench shell layout"`

## Implementation follow-up (2026-04-10, chart/protocol create-path hierarchy tune)
- This patch stayed inside the current audit recommendation:
  - no route rewrite
  - no backend/schema change
  - no new artifact-family chrome
- `ChartPackPage` and `ProtocolCardPage` already had the right downstream semantics, but their index/create surfaces still made manual form entry compete too early with the recommended review-backed path.
- The patch shifts emphasis without changing the underlying flow:
  - recent saved runs now read first on chart-pack create
  - recent notes now read first on protocol-card create
  - manual paper/run or note/paper entry is still present, but explicitly framed as fallback
- This keeps the current product contract intact:
  - chart packs still derive from saved runs
  - protocol cards still derive from note-backed review context
  - no new object model or wizard flow was introduced
- The design intent is to make the recommended path readable sooner:
  - recommended quick-pick first
  - manual identifiers second
  - existing create behavior unchanged
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/chart-pack.mock.spec.ts e2e/protocol-card.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack index can create a new chart pack from the browser|backend chart pack quick-pick journey stays connected in the browser|backend protocol knowledge index can create a new protocol card from the browser|backend paper note detail can start a protocol card with note context from the browser"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack index layout|protocol knowledge index layout|mobile.*chart pack index layout|mobile.*protocol knowledge index layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack index layout|protocol knowledge index layout|mobile.*chart pack index layout|mobile.*protocol knowledge index layout"`

## Implementation follow-up (2026-04-10, protocol create-context confirmation placement)
- This patch stayed inside the current audit recommendation:
  - no route rewrite
  - no backend/schema change
  - no new create fields or actions
- `ProtocolCardPage` already emphasized recent-note quick-picks, but the confirmation card for the selected note context still appeared later, below the manual note fallback fields.
- The patch moves `Current note context` directly under the recent-note selection area:
  - quick-pick choice now confirms earlier in the scan
  - note-started prefill from paper detail also confirms earlier
  - manual note/paper entry remains available below as fallback
- This keeps the protocol capture contract intact while reducing the extra mental stitching between:
  - `which recent note did I just choose?`
  - `which note context will this saved protocol actually use?`
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/protocol-card.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend protocol knowledge index can create a new protocol card from the browser|backend paper note detail can start a protocol card with note context from the browser"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "protocol knowledge index layout|mobile.*protocol knowledge index layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "protocol knowledge index layout|mobile.*protocol knowledge index layout"`

## Implementation follow-up (2026-04-10, note detail primary-source-anchor lift)
- This patch stayed inside the current audit recommendation:
  - no route rewrite
  - no backend/schema change
  - no new note-detail chrome
- `PaperNoteDetailPage` already exposed `Trust state` and a center-column `Review focus` bridge, but the actual provenance cue still read too late in the scan.
- The patch keeps the current bridge and only changes the order of existing information:
  - the focus card now opens with `Primary source anchor`
  - the saved anchor location remains explicit even when the location text is sparse
  - a short urgency-specific review hint now explains whether that saved anchor is flagged, unresolved, or ready to reuse
- This keeps note detail closer to a source-grounded reading surface without inventing a new citation layer:
  - provenance now reads before claim text
  - uncertainty now reads before narrative summary
  - the existing `Open saved evidence` / `Open saved claim` and `Open review` actions remain unchanged
- The design intent is to strengthen the existing center-column bridge rather than add another summary surface.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "structured paper note detail keeps review focus close to reading"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "paper notes detail renders structured actions, run history, and structured claims cards"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "paper note detail layout|structured paper note detail layout|mobile.*paper note detail layout|mobile.*structured paper note detail layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "paper note detail layout|structured paper note detail layout|mobile.*paper note detail layout|mobile.*structured paper note detail layout"`

## Implementation follow-up (2026-04-10, workbench task-first control grouping)
- This patch stayed inside the current audit recommendation:
  - no route rewrite
  - no backend/schema change
  - no new workbench pane
- `AnalysisWorkbench` already had the right actions, but the first scan still mixed review-critical work with session tuning.
- The patch keeps the same controls and only changes their grouping:
  - `Run deep read`, `Refresh`, and `Refresh checks` now sit inside a visible `Review actions` group
  - `Reading style`, `Context profile`, and parser-status copy now live inside `Session controls`
  - mobile review controls now follow the same order: review actions first, session setup second, maintenance controls last
- This keeps workbench closer to a task-first evidence surface without hiding power-user controls:
  - primary review actions stay visible
  - session setup still stays one click away
  - maintenance/rebuild behavior remains unchanged
- The design intent is hierarchy, not simplification theater:
  - first scan should answer “what do I do now?”
  - deeper controls should answer “how do I tune this session?”
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend mode stays out of mock fallback|backend keyboard focus keeps primary actions ahead of static content on core routes|backend workbench preserves content review context when opened in issue focus mode|mobile workbench renders collapsed controls without mock fallback|backend workbench shows requested and resolved parser backends separately|backend workbench does not infer requested parser from route query when persisted job metadata is absent|backend parser completion does not overwrite the next selected paper"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench shell layout|mobile.*workbench shell layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench shell layout|mobile.*workbench shell layout"`
