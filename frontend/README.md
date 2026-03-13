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
# 선택: 백엔드 API 키 보호가 켜진 경우 POST 보호 엔드포인트 호출용
VITE_API_KEY=your-api-key
# 선택: 자동 mock fallback 비활성화(운영/검증 모드)
VITE_STRICT_API=1
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
- 실데이터 real smoke 시나리오:
```bash
cd frontend
npm run e2e:backend:real-smoke
```
- `e2e:backend:real-smoke`는 seeded E2E harness를 쓰지 않고, 현재 `PAPERPIPE_CONFIG_PATH`/`PAPERPIPE_STORAGE_DIR`/`PAPERPIPE_DB_PATH`/`PAPERPIPE_ARTIFACTS_DIR` 환경을 그대로 사용합니다.
- 기본 동작은 `config.yaml` 기준이며, 후보 paper가 없으면 `skip`이 아니라 실패합니다.
- 실행 전 `python ../scripts/check_frontend_real_smoke_env.py --require-candidates` preflight가 자동으로 수행됩니다.
- `e2e:backend`는 내부적으로 백엔드 서버를 기동하기 전에 `storage/state.db`에 E2E seed paper(`paper-e2e-001`)를 주입합니다.
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
  - 주의: Playwright OS dependency는 러너에 미리 준비되어 있어야 합니다.
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
- `public/sample.pdf`
