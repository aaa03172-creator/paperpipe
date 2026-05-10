# Lattice UI/UX Adoption Filter (2026-02-25)

Status: Active adoption record
Date: 2026-03-09
Owner: Frontend maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Current entrypoint: `docs/Lattice_v3_Master_Spec.md`, `AGENTS.md`, and active viewer specs
Current use: UI adoption/exclusion record for the imported reference materials; do not use as a standalone UI system, token contract, or permission to bypass current product-psychology and `--pp-*` viewer rules.

## 기준
- 1순위: `docs/Lattice_v3_Master_Spec.md`의 레이아웃/플로우/토큰/인지부하 가드레일
- 2순위: `Design UI_UX Enhancements-2.zip`의 재료 재사용

현재 기준 UI/UX 마스터 문서는 아래로 정리한다.
- 정식 운영본: `docs/Lattice_v3_Master_Spec.md`
- 호환용 retired stub: `docs/Lattice_v3_UIUX_MASTER.md` (신규 참조 금지)

## 채택
- `src/styles/theme.css`의 라이트/다크 구조 패턴만 채택
  - 실제 런타임 토큰은 `--pp-*`로 재정의
  - 적용 위치: `frontend/styles/pp-theme.css`
- `src/app/components/ui/*`에서 최소 UI 컴포넌트 세트 채택(레퍼런스 반입)
  - 위치: `frontend/references/shadcn-ui/`

## 제외
- `src/app/App.tsx` 전면 미채택
  - glassmorphism
  - glow 위주 시각 톤
  - 과한 모션/애니메이션

## 적용 결과
- 런타임 `/ui`는 운영형 워크벤치 톤으로 재작성
  - Navigation Rail / PDF Pane / Main Stage / Terminal Drawer
  - 논문선택 -> 실행 -> SSE 로그 -> artifact 요약 플로우
  - 인지부하 완화: 고급옵션 접기, 요약 우선, raw JSON 접기
