# PaperPipe v3.0 Phase 3 Control UI (`frontend/`)

## 설치
```bash
cd frontend
npm install
```

## 실행
```bash
npm run dev
```

## 접속
- [http://localhost:5173](http://localhost:5173)
- 화면:
  - `/` Triage Dashboard
  - `/workbench/:paperId` Analysis Workbench

## 백엔드 연동
- 기본 API 대상: `http://localhost:8000`
- 환경변수 (`.env` 또는 `.env.local`):
```bash
VITE_API_BASE_URL=http://localhost:8000
```
- Vite proxy:
  - 프론트 요청 `/api/*`
  - 개발서버가 `http://localhost:8000/*`로 rewrite 프록시

## 백엔드가 없을 때
- 앱은 자동으로 **Mock mode**로 전환됩니다.
- 상단에 `Mock mode` 칩이 표시됩니다.
- 다음이 mock 시뮬레이션으로 동작합니다.
  - 논문 목록/Triage 상태
  - Workbench Stepper 단계 진행
  - Terminal 로그 스트리밍
  - Timeline 이벤트
  - Artifact(JSON) + Notebook 셀
  - PDF 패널(`public/sample.pdf`)

## E2E 스모크 테스트 (Playwright)
- mock fallback 시나리오:
```bash
cd frontend
npm run e2e:mock
```
- 실백엔드 연동 시나리오:
```bash
cd frontend
npm run e2e:backend
```
- `e2e:backend`는 내부적으로 백엔드 서버를 기동하기 전에 `storage/state.db`에 E2E seed paper(`paper-e2e-001`)를 주입합니다.

## GitHub Actions 연동
- 워크플로우: `.github/workflows/frontend-e2e.yml`
- `e2e:mock`:
  - `master` 대상 PR에서 항상 실행
- `e2e:backend`:
  - 수동 실행(`workflow_dispatch`) 시 `run_backend_e2e=true`로 실행
  - 또는 Repository Variable `RUN_FRONTEND_BACKEND_E2E=1` 설정 시 실행

## 스택
- Vite + React + TypeScript
- Tailwind CSS (토큰 `--pp-*` 기반)
- Zustand
- lucide-react
- PDF: iframe renderer

## 주요 디렉토리
- `src/app/layouts/`
- `src/app/components/`
- `src/app/lib/`
- `src/styles/`
- `public/sample.pdf`
