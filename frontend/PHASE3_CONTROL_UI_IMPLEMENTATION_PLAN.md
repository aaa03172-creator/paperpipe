# PaperPipe v3.0 Phase 3 Control UI 구현 계획/체크리스트

Status: Historical working plan  
Canonical references: `docs/README.md`, `docs/Lattice_v3_Master_Spec.md`, `docs/UIUX_Adoption_Filter_2026-02-25.md`

## 1) SSOT 및 참조 우선순위
1. `docs/README.md` (문서 진입점)
2. `docs/Lattice_v3_Master_Spec.md` (운영 SSOT)
3. `docs/UIUX_Adoption_Filter_2026-02-25.md` (채택/제외 가드레일)

## 2) 이번 구현 범위 (요청 + SSOT 보완)
- 기술 스택 고정: Vite + React + TypeScript + Tailwind + Zustand + lucide-react
- 화면: `/`(Triage Dashboard), `/workbench/:paperId`(Analysis Workbench)
- 필수 UI: Navigation Rail, PDF Panel, Artifact/Notebook Panel, Pipeline Stepper, Terminal Drawer, Timeline
- API + Mock 이중 모드:
  - 기본 시도: `/api/*`
  - 실패 시 mock fallback
  - Mock mode 배너/칩 노출
- SSE 준비:
  - 기본 엔드포인트 가정: `/api/sse/jobs/:jobId`
  - 백엔드 실구현 호환: `/api/jobs/:jobId/events`
  - 재연결(backoff) + mock 스트리밍 시뮬레이터

## 3) 프롬프트 대비 보완 반영 항목
- Persona 선택 UI + 목록 로드 (`GET /api/personas`) 
- Deep Read 실행 트리거 (`POST /api/jobs/deepread`) 
- Artifact latest 로드 (`GET /api/artifacts/:paperId/latest`) 
- Run timeline 로드 (`GET /api/runs/:runId/timeline`) 
- PDF 로더는 paper endpoint 우선 (`GET /api/papers/:paperId/pdf`), 실패 시 샘플 PDF
- Evidence linking은 Claim 1개 활성 상태만 강조(스파게티 방지)

## 4) 구현 체크리스트 (사전)
- [x] `frontend/` Vite React TS 초기화
- [x] Tailwind + 토큰(`--pp-*`) + 다크 기본/라이트 준비
- [x] 라우팅 2개 경로 구성
- [x] 공통 컴포넌트/레이아웃 구조 구성
- [x] API 클라이언트/환경변수/프록시 구성
- [x] Mock 데이터 + fallback + mock mode 배너
- [x] SSE 클라이언트 + mock stream 구현
- [x] PDF 패널 실제 렌더 + 더미 highlight
- [x] Terminal toggle + streaming 로그
- [x] Artifact(JSON/Notebook) 렌더
- [x] README 작성
- [x] `npm run build` 검증

## 5) 완료 더블체크 (사후)
- [x] 브라우저 로드 깨짐 없음
- [x] Triage -> Workbench 이동 동작
- [x] Stepper mock 진행 동작
- [x] Terminal 로그 토글/스트리밍 동작
- [x] PDF 실제 표시 + highlight 표시
- [x] Artifact 패널 렌더
- [x] Mock mode 표시 정확성
- [x] 실행 가이드 문서 확인
