# /ux-review Report — Triage + Analysis Workbench

Date: 2026-03-05  
Reviewer: Codex (runtime verification + code inspection)

## Input
- Target screen/flow:
  - `/` (Triage Dashboard)
  - `/workbench/:paperId` (Analysis Workbench, claims/evidence linking)
- User goal:
  - Quickly find a paper, open Workbench, validate claims against evidence, launch Deep Read safely.
- Current pain points:
  - Mobile readability and action clarity under dense data.
  - Issue-first routing salience in long queue.
- Constraints:
  - Existing dark design system 유지
  - Backend may fail -> mock fallback must remain intact
  - Current routing and API contract must not break

---

## 1) Quick Review (5 min)
1. 선택지 과다 여부 (Block): **부분 미통과**
   - Triage row 내 액션이 많고(행 클릭 + issues 버튼 + open 링크), 모바일에서는 정보 밀도가 높아 인지 부하가 큼.
2. 혜택 선노출 (Interpret): **부분 통과**
   - Workbench 가치(근거-주장 연결)는 보이지만 Triage 단계에서는 “왜 지금 이 논문을 열어야 하는지” 우선순위 힌트가 약함.
3. 다음 행동 명확성 (Act): **통과(Workbench), 부분 미통과(Triage)**
   - Workbench claim 클릭 -> 페이지 점프/박스 강조는 명확.
   - Triage는 행 클릭과 버튼 클릭의 의미 구분이 약함.
4. 즉시 피드백 (Store): **통과**
   - Claim Link badge, highlight, timeline으로 상태 피드백 존재.
5. 윤리 기본 점검: **통과**
   - 다크패턴, 과도한 강제, 숨은 결제 유도 없음.

---

## 2) Full Review (P0/P1/P2 prioritized)

### P0 (critical)
- 현재 기준 **없음**.
- 핵심 플로우(논문 선택 -> Workbench 진입 -> claim 클릭 -> jump/highlight)는 실동작 확인 완료.

### P1 (high)
1. 모바일 Triage 테이블 가로 스크롤 의존
   - 증상: `table min-w-[760px]`로 모바일에서 가로 스크롤 필요.
   - 영향: Block 단계에서 즉시 의미 파악 어려움, 핵심 열 우선순위 인지 저하.
   - 위치: [TriageDashboard.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx)

2. Triage 액션 의미 구분 약함 (행 클릭 vs Open vs Issues)
   - 증상: 같은 row에 3개 진입 경로가 존재하나 시각적 위계가 약함.
   - 영향: Act 단계에서 결정 마찰 증가, 오클릭 가능성.
   - 위치: [TriageDashboard.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx)

3. Workbench 상단 컨트롤 밀도 과다 (모바일/태블릿)
   - 증상: persona/verify/reindex/theme/refresh/deepread가 한 영역에 집중.
   - 영향: Interpret 단계 인지 부하 증가, 핵심 CTA(Deep Read) 대비 가독성 저하.
   - 위치: [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx), [WorkbenchLayout.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/layouts/WorkbenchLayout.tsx)

### P2 (medium)
1. Triage에서 “Issue-first” 가치 신호 약함
   - 현재 issues badge는 있으나 우선순위 설명/필터 진입이 부족.
2. Timeline 로그가 길 때 주요 이벤트(실패/완료/artifact ready) 스캔성이 낮음
   - severity 시각 분리 강화 여지.

---

## Full Review Coverage (5 frameworks)

### 6P context
- Problem: 사용자는 “많은 논문 중 지금 뭘 먼저 볼지” 결정 피로를 겪음.
- Emotion: 빠르게 신뢰 가능한 후보를 골라야 한다는 압박.
- Action: Triage 진입 후 검색/상태/이슈 신호를 스캔.
- Struggle: 모바일에서 테이블 스크롤 + 다중 액션 구조로 판단 지연.
- Attempt: issues 버튼/행 클릭으로 Workbench 진입.
- Happy Ending: claim 클릭 시 근거 하이라이트와 함께 검토 완료.

### BMAP
- Motivation: 높음 (리스크 논문 먼저 보고 싶음).
- Ability: 중간 (모바일 테이블/컨트롤 밀도로 능력 장벽 발생).
- Prompt: 중간 이상 (status, issues badge, deep read 버튼 존재)이나 우선순위 프롬프트 강화 필요.

### B.I.A.S
- Block: 모바일 Triage 정보밀도 높아 초기 필터 통과 비용 증가.
- Interpret: Workbench에서는 claim/evidence 해석 명확.
- Act: claim 클릭 액션은 우수하나 Triage의 다중 진입 액션은 마찰 존재.
- Store: claim jump/highlight + timeline 피드백으로 기억 형성 요소 양호.

### Peak-End
- Peak: Workbench에서 claim 클릭 시 즉시 하이라이트되는 순간.
- Pit: Triage 첫 진입에서 우선순위 판단(특히 모바일).
- Transition: Triage -> Workbench 전환은 빠르나 목적 기반 전환 힌트(“이슈 많은 것부터”) 강화 가능.
- End: 검토 종료 시점의 명시적 성공/다음 액션 안내는 보강 여지.

### Ethics (요약)
- Regret: 조작형 UI 없음, 사용자가 의도를 알더라도 수용 가능.
- Black Mirror: 특정 집단 차별/착취형 넛지 없음.
- In Real-Life: 전반적으로 도우미형 톤, 단 정보 과밀 구간은 피로 유발 가능.

---

## 3) Concrete Changes (component/route/copy/default-action level)

1. Component: `TriageDashboard` 테이블 -> 모바일 카드 리스트 분기(`md` 미만)
   - 기본 열: 제목, 상태, issues, updated 축약
   - 상세 열은 expandable panel로 이동

2. Component: `TriageDashboard` row action 정리
   - 기본 액션을 하나로 통일(`Open Workbench`)
   - `Issues first`는 보조 CTA로 명확 라벨링

3. Route/default-action:
   - 이슈가 있는 논문 기본 진입을 `?focus=issues`로 유도하는 토글 제공
   - 사용자 opt-out 가능하게 유지

4. Component: `AnalysisWorkbench` 상단 컨트롤 그룹화
   - `Run controls`(verify/reindex/deepread), `View controls`(theme/terminal) 분리
   - 모바일에선 collapse/overflow menu 적용

5. Copy:
   - Triage subtitle 아래 “Issue-first recommended” 보조 카피 추가
   - Workbench verdict 카드에 “다음 행동” 문장 1줄 고정

6. Timeline:
   - `error/done/status` 이벤트 뱃지 대비 강화 (색 + 아이콘 + pinned summary)

---

## 4) Ethics Check Results
- Regret Test: **Pass**
- Black Mirror Test: **Pass**
- In Real-Life Test: **Pass with caution**
  - 주의: 정보밀도 높은 화면에서 사용자 피로를 줄이기 위한 정리 필요.

---

## 5) Next PR-sized Actions (1-3 items)
1. PR-1: Triage 모바일 카드화 + row action 단순화 (`TriageDashboard.tsx`)
2. PR-2: Workbench 상단 컨트롤 그룹화/모바일 collapse (`AnalysisWorkbench.tsx`, `WorkbenchLayout.tsx`)
3. PR-3: Timeline 중요 이벤트 summary/pinning (`TimelinePanel.tsx`)

