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
# dev-only: Vite server proxy target (server-side only, not exposed to the browser bundle)
LATTICE_UI_BACKEND_URL=http://localhost:8000
# 선택: 자동 mock fallback 비활성화(운영/검증 모드)
VITE_STRICT_API=1
```
- 브라우저는 항상 same-origin `/api/*`만 호출합니다.
- dev에서는 Vite proxy가 `/api/*`를 `LATTICE_UI_BACKEND_URL`로 전달합니다.
- backend-served `/ui` 런타임에서는 FastAPI가 `/api/*`를 내부 backend route로 브리지하고, `LATTICE_API_KEY`가 설정된 경우 서버 환경변수에서만 `X-API-Key`를 주입합니다.
- hosted beta에서 backend가 `LATTICE_BETA_PASSWORD`를 설정하면 `/ui`와 same-origin `/api/*`는 HTTP Basic gate 뒤에 놓입니다.
- `VITE_API_KEY`는 제거되었습니다. 브라우저 env에 backend secret을 넣지 마세요.
- Vite proxy:
  - 프론트 요청 `/api/*`
  - 개발서버가 `LATTICE_UI_BACKEND_URL/api/*`로 프록시

## 백엔드가 없을 때
- 앱은 자동으로 **Mock mode**로 전환됩니다.
- 상단에 `Mock mode` 칩이 표시됩니다.
- 다음이 mock 시뮬레이션으로 동작합니다.
  - 논문 목록/Triage 상태
  - Workbench Stepper 단계 진행
  - Terminal 로그 스트리밍
  - Timeline 이벤트
  - Artifact(JSON) + Notebook 셀
  - PDF 패널(`public/sample.pdf`, source evidence가 아닌 placeholder)

## 강제 Mock 모드
- 백엔드 연결 상태와 무관하게 항상 mock 데이터만 사용하려면 아래 환경변수를 추가하세요.
```bash
VITE_FORCE_MOCK=1
```
- 허용 값: `1`, `true`, `yes`, `on` (대소문자 무시)
- E2E `e2e:mock`는 이 값을 자동으로 켜고 실행됩니다.

## Strict API 모드
- `VITE_STRICT_API=1`이면 API 실패 시 mock fallback으로 전환하지 않고 에러를 UI에 표시합니다.
- 운영 점검이나 백엔드 회귀 검증 시 권장됩니다.

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
- backend-served hosted beta gate readiness 시나리오:
```bash
cd frontend
npm run build
npm run e2e:backend:gated
```
- parser worker가 필요한 bounded browser fallback 시나리오:
```bash
cd frontend
npm run e2e:backend:parser-worker
```
- 실데이터 real smoke 시나리오:
```bash
cd frontend
npm run e2e:backend:real-smoke
```
- `e2e:backend:real-smoke`는 seeded E2E harness를 쓰지 않고, 현재 `PAPERPIPE_CONFIG_PATH`/`PAPERPIPE_STORAGE_DIR`/`PAPERPIPE_DB_PATH`/`PAPERPIPE_ARTIFACTS_DIR` 환경을 그대로 사용합니다.
- 기본 동작은 `config.yaml` 기준이며, 후보 paper가 없으면 `skip`이 아니라 실패합니다.
- 실행 전 `python ../scripts/check_frontend_real_smoke_env.py --require-candidates` preflight가 자동으로 수행됩니다.
- backend launch는 이제 `python ../scripts/run_backend_for_real_smoke.py` 경로를 사용합니다.
- `e2e:backend`는 내부적으로 백엔드 서버를 기동하기 전에 `storage/state.db`에 E2E seed paper(`paper-e2e-001`)를 주입합니다.
- `e2e:backend:gated`는 built frontend bundle을 backend `/ui` 경계로 직접 서빙한 뒤, HTTP Basic gate가 켜진 상태에서 `/ui/ready`가 browser-safe readiness summary를 유지하는지 검증합니다.
- `e2e:backend:parser-worker`는 같은 seeded harness를 쓰되, parser fallback browser-flow 검증을 위해 opt-in fake worker sidecar를 함께 띄웁니다.
- GitHub Actions에서 같은 경로를 수동 실행하려면 workflow 파일이 repo default branch에 등록돼 있어야 합니다. 현재 default branch는 `main`입니다.
- 따라서 `.github/workflows/frontend-real-smoke.yml`는 `main`에 등록돼 있고, 실제 테스트 대상은 `--ref`로 별도 브랜치를 지정합니다. 예: `gh workflow run frontend-real-smoke.yml --ref codex/agents-smoke-ci-check -f config_path=config.yaml`
- repo에 `self-hosted`, `paperpipe-real-smoke` 라벨을 가진 러너가 없으면 dispatch는 성공해도 job은 계속 `queued` 상태로 남습니다.
- 시각 회귀 스냅샷 갱신(의도된 UI 변경 시만):
```bash
cd frontend
npm run e2e:mock:update
npm run e2e:backend:update
```

## UI 품질 게이트 (권장)
아래 순서로 실행하면 Workbench 핵심 UX(Claim jump + bbox highlight + mock/backend fallback)를 빠르게 검증할 수 있습니다.
```bash
cd frontend
npm run lint
npm run build
npm run e2e:mock
npm run e2e:backend
npm run e2e:backend:gated
npm run e2e:backend:parser-worker
```

## GitHub Actions 연동
- 워크플로우: `.github/workflows/frontend-e2e.yml`
- 현재 repo default branch는 `main`이지만, 이 workflow의 PR 트리거는 아직 `master` 대상입니다.
- `e2e:mock`:
  - `master` 대상 PR에서 항상 실행
- `e2e:backend`:
  - `master` 대상 PR에서 항상 실행
  - 수동 실행(`workflow_dispatch`) 시 `run_backend_e2e=true`로 실행
  - 또는 Repository Variable `RUN_FRONTEND_BACKEND_E2E=1` 설정 시 실행
- `real smoke`:
  - 워크플로우: `.github/workflows/frontend-real-smoke.yml`
  - workflow 파일은 GitHub 등록을 위해 `main`에 존재해야 함
  - `self-hosted`, `paperpipe-real-smoke` 라벨을 가진 러너에서만 수동 실행
  - 필수 입력: runner-local `config_path`
  - 선택 입력: `storage_dir`, `db_path`, `artifacts_dir`
  - 주의: Playwright OS dependency와 `python3`/`node`/`npm`은 러너에 미리 준비되어 있어야 합니다.
  - 러너가 없으면 run은 실패하지도 시작하지도 않고 `queued`에 머뭅니다.

## 스택
- Vite + React + TypeScript
- Tailwind CSS (토큰 `--pp-*` 기반)
- Zustand
- lucide-react
- PDF: `@react-pdf-viewer/core` + highlight/page-navigation/search plugins

## 주요 디렉토리
- `src/app/layouts/`
- `src/app/components/`
- `src/app/lib/`
- `src/styles/`
- `public/sample.pdf` (mock viewer placeholder, not source evidence)
