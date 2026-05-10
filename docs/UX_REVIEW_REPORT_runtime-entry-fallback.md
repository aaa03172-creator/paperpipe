# UX Review Report - Runtime Entry Fallback

Status: Current review artifact
Date: 2026-03-28
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-28
Reviewer: Codex

## Header
- Screen/Flow: local runtime start -> backend-served `/ui` entry -> `/papers` list -> `/papers/:slug` detail -> workbench placeholder PDF trust language
- Goal action: 사용자가 backend가 내려가 있거나 일부 endpoint가 비어 있어도 500 없이 viewer를 탐색하고, 현재 보고 있는 데이터가 fallback/mock인지 즉시 이해한다.
- Primary persona: 설치와 세팅 마찰에 민감한 1인 연구자 / 대학원생
- Current friction: documented start path failed early on optional runtime imports, viewer routes applied mock fallback inconsistently, and note/detail surfaces did not disclose when fallback content was being shown.
- Success metric: `self-test`에서 backend entrypoint readiness가 바로 드러나고, backend unavailable 상태에서도 `/papers`와 `/papers/:slug`가 500 대신 fallback content + visible fallback notice를 보여주며, backend-served UI는 direct entry/deep link에서도 API JSON이 아니라 SPA shell로 열린다.
- Constraints:
  - FastAPI + Vite + React Router + TailwindCSS 유지
  - `--pp-*` 토큰과 dark-first Lattice tone 유지
  - fallback는 viewer continuity를 위한 것이지 source evidence로 오해되면 안 된다.

## Quick Review (5 min)
- Start 경로는 optional `docker` import crash를 넘긴 뒤에도 필수 backend dependency 누락을 `start`에서만 traceback으로 보여줘 신뢰를 깎고 있었다.
- Notes viewer는 fallback data를 쓸 수 있게 바꿔도, 그 사실을 화면에 드러내지 않으면 사용자가 실제 저장 데이터로 오해할 위험이 있었다.
- backend-served entry는 `/ui`로 시작해도 deep link와 refresh 시 raw JSON으로 무너질 수 있었다.
- real runtime triage와 saved meeting-pack lists는 E2E/visual fixture rows가 상단을 점유해 첫인상을 흐리고 있었다.
- triage header와 top-nav copy는 여전히 내부 운영자 시점이 강해서 첫 1~3분 가치 해석을 늦추고 있었다.
- papers list와 meeting-pack index에는 `ClaimSet`, `Ops`, `Operational` 같은 내부자 용어가 남아 있었고, empty artifact routes는 “검색 결과 없음”과 “아직 저장된 항목 없음”을 구분하지 못했다.
- note detail과 workbench에도 `canonical sidecar state`, `Stats Snapshot`, `Repair Stats` 같은 내부 용어가 남아 있어, 깊은 화면으로 들어갈수록 다시 운영도구처럼 읽히는 문제가 있었다.
- rail, triage table, and workbench artifact headers still mixed older labels like `Navigation Rail`, `Content Review`, and `Stats Snapshot`, which made the newest copy pass feel inconsistent.
- 이번 slice의 목적은 기능 확장이 아니라 “안 열리던 화면을 열리게 하고, 지금 보는 것이 무엇인지 숨기지 않는 것”이다.

## Full Review
### P0
- `self-test`와 `start`가 같은 현실을 보여줘야 한다. backend entrypoint import 실패는 readiness 단계에서 먼저 보여야 한다.
- `/papers`와 `/papers/:slug`는 backend unavailable이어도 500 대신 fallback content를 노출해야 한다.
- fallback content는 그대로 보여줘도 되지만, fallback임을 분명히 밝혀야 한다.
- backend-served entry는 `/ui`만 열리는 수준으로 끝나면 안 된다. 사용자가 `/papers`를 직접 열거나 새로고침해도 앱 shell이 떠야 한다.

### P1
- placeholder PDF나 mock note는 탐색 continuity에는 도움이 되지만 원문 evidence처럼 읽히면 안 된다.
- fallback reason 문구는 개발자 진단보다 사용자의 해석 비용을 낮추는 방향이어야 한다.
- real 데이터가 있는 런타임에서는 fixture-like rows가 기본 목록 상단을 점유하지 않게 해야 한다.

### P2
- forced mock와 auto fallback의 데이터 구성 차이는 여전히 남아 있다.
- title/PDF identity mismatch는 별도 후속 정합화가 필요하다.

### Full Review Coverage
- 6P storyboard context:
  - Problem: 사용자는 제품이 당장 열리고 첫 note를 볼 수 있어야 한다.
  - Emotion: 시작 단계에서 오류를 보면 제품 신뢰를 빨리 잃는다.
  - Action: 앱을 띄우고 note list/detail을 연다.
  - Struggle: 500, traceback, undisclosed fallback이 사용자 해석을 막는다.
  - Struggle: backend-served deep link가 API route와 충돌하면 사용자는 화면 대신 raw JSON을 보게 된다.
  - Attempt: fallback coverage를 늘리고 readiness를 더 앞단에서 체크한다.
  - Happy Ending: 사용자는 적어도 viewer를 열고, 지금 보는 데이터의 성격을 바로 이해한다.
- BMAP:
  - Motivation은 이미 높다.
  - Ability는 start failure와 500 때문에 무너졌다.
  - Prompt는 fallback banner가 있어야 회복된다.
- B.I.A.S:
  - Block: broken start path와 500.
  - Interpret: mock/fallback 여부가 보이지 않으면 잘못 해석한다.
  - Act: route가 열려야 다음 행동으로 간다.
  - Store: 첫 기억을 “깨짐”에서 “제한은 있지만 이해 가능”으로 바꿔야 한다.
- Peak-End:
  - Peak는 첫 note가 열리고 workbench로 이어지는 순간.
  - Pit는 traceback, 500, undisclosed mock.
  - Transition은 start -> list -> detail -> workbench.
  - End는 fallback임을 알지만 계속 탐색 가능한 상태여야 한다.
- Ethics:
  - fallback data를 source evidence처럼 보이게 하면 안 된다.

## BMAP diagnosis
- Motivation: 높음
- Ability: start preflight와 route fallback 정리가 핵심
- Prompt: fallback notice가 현재 상태를 짧게 설명해야 함

## B.I.A.S diagnosis
- Block: optional/required dependency failure가 start 시점에서 섞여 보였다.
- Interpret: note/detail에서 fallback disclosure가 없으면 실제 저장 데이터처럼 오인한다.
- Act: mock disclosure가 있어도 탐색은 계속 가능해야 한다.
- Store: “실패”보다 “제한된 fallback”으로 기억되게 해야 한다.

## Peak-End design notes
- Peak를 앞당기려면 `/papers`가 기본 모드에서도 열려야 한다.
- Pit를 줄이려면 traceback 전에 backend entrypoint failure를 짧게 알려야 한다.
- Transition 품질은 list/detail 모두에서 같은 disclosure 규칙을 쓸 때 좋아진다.
- End는 “지금은 fallback이지만 workbench handoff 구조는 볼 수 있다”여야 한다.

## Concrete changes
- `src/services/runtime_readiness.py`: backend entrypoint import check 추가
- `src/cli.py`: `start`에서 backend entrypoint preflight 실패를 명시적으로 출력
- `README.md`: quickstart에 requirements install + `self-test` 경로 추가
- `frontend/src/app/lib/api.ts`: notes/detail 및 artifact viewers에 mock fallback 적용
- `frontend/src/app/pages/PaperNotesListPage.tsx`: fallback notice 추가
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`: fallback notice 추가
- `frontend/src/app/components/PdfPanel.tsx`: placeholder PDF가 source evidence가 아님을 강한 경고로 표시
- `frontend/src/app/lib/mock.ts`: notes fallback dataset과 structured state/context trace 정합화
- `frontend/public/sample.pdf`: 다른 논문처럼 보이는 sample을 generic placeholder PDF로 교체
- `frontend/src/main.tsx`: backend-served runtime에서 `BrowserRouter basename="/ui"`를 사용해 `/ui/*` 아래 client routes를 유지
- `backend/main.py`: `/ui`뿐 아니라 `/ui/{path:path}`에도 동일한 shell을 반환해 direct deep link/refresh를 복구
- `tests/test_ui_shell_api.py`: `/ui/papers` deep link가 HTML shell을 반환하는지 검증 추가
- `src/services/fixture_visibility.py`: paper rows와 meeting packs의 fixture-like records를 감지하고, real rows가 함께 있을 때만 기본 목록에서 숨김
- `backend/main.py`: `/papers` listing에서 fixture filtering 후 offset/limit를 다시 적용
- `src/meeting_packs/service.py`: saved meeting-pack list에서 fixture filtering 적용
- `tests/test_papers_api.py`: real+fixture 혼합 런타임과 fixture-only 런타임을 모두 검증
- `tests/test_meeting_pack_service.py`: meeting-pack fixture visibility fallback 규칙 검증
- `backend/main.py`: `/favicon.ico`를 built `vite.svg`로 서빙해 backend-served favicon 404 제거
- `frontend/src/app/pages/TriageDashboard.tsx`: header/CTA/loading/summary copy를 user-outcome 중심 문구로 조정하고, `Paper Notes`를 명시적 시작 CTA로 강조
- `frontend/src/app/lib/paperNoteOps.ts`: `ClaimSet`, `Stats Snapshot` 계열 문구를 `saved claims`, `saved note checks` 중심 문구로 정리
- `frontend/src/app/pages/PaperNotesListPage.tsx`: note list badges, filters, and status labels를 사용자 언어로 완화
- `frontend/src/app/pages/MeetingPackPage.tsx`: meeting-pack index header, trace filter, direct-open helper copy를 first-session 기준으로 완화
- `frontend/src/app/pages/ChartPackPage.tsx`, `frontend/src/app/pages/ImageEvidencePage.tsx`, `frontend/src/app/pages/MethodComparisonPage.tsx`, `frontend/src/app/pages/ProtocolCardPage.tsx`: “아직 저장된 항목 없음”과 “현재 검색 조건에 없음”을 구분하는 empty-state copy 추가
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`: detail sidebar와 saved-state panels를 `saved note state`, `saved claims`, `saved checks` 중심 문구로 정리
- `frontend/src/app/pages/AnalysisWorkbench.tsx`: `Repair Stats`, `Rebuild Stats`, `Stats Snapshot` 계열 workbench action/warning copy를 `Refresh checks`, `Rebuild checks`, `saved checks` 문구로 정리
- `frontend/src/app/lib/contentReview.ts`, `frontend/src/app/components/Rail.tsx`, `frontend/src/app/components/ArtifactPanel.tsx`, `frontend/src/app/pages/TriageDashboard.tsx`: rail/table/artifact headers를 `Papers`, `Claim review`, `Saved checks` 톤으로 맞추고 claim-review helper 문구를 동일 어휘로 정리
- `frontend/src/app/lib/paperNoteOps.ts`: legacy real-data ops reasons를 `saved note checks` 언어로 정규화해 rail/workbench에서 예전 `Stats report` 문구가 다시 드러나지 않게 함
- `frontend/e2e/mock.spec.ts`, `frontend/e2e/backend.spec.ts`, `frontend/e2e/visual-backend.backend.spec.ts`: 최신 user-facing labels에 맞춰 E2E expectations를 정리

## Ethics check results
- Regret: 개선. 사용자는 더 빨리 원인을 이해한다.
- Black Mirror: fallback data가 실제 source처럼 읽히지 않도록 disclosure를 유지해야 한다.
- In Real-Life: 설치가 덜 된 환경에서도 “보여줄 수 있는 것”과 “실제 source evidence”를 구분하는 수준의 정직한 UX다. backend-served direct entry도 이제 `/ui/*` 아래에서 일관되게 작동하고, 기본 목록은 fixture 노이즈가 줄어든다.

## Next PR-sized actions
1. auto fallback와 forced mock가 같은 sample identity를 쓰도록 통일하기
2. workbench stage labels와 debug affordance(`Stats Verify`, `Clean Reindex`, `Cell 1/2/3`)를 같은 plain-language 톤으로 계속 낮추기
3. triage summary strip와 rail affordance를 첫 세션용 plain-language mode로 더 줄일지 검토하기
