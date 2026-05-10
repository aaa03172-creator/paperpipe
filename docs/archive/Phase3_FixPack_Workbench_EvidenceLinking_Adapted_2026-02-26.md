# PaperPipe Phase 3 Control UI — Fix Pack (Adapted) : Workbench Evidence Linking

Status: Historical execution plan  
Date: 2026-02-26  
Owner: Frontend/runtime maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## 0) 목적
현재 UI는 기본 흐름(목록 -> 워크벤치, mock fallback)은 동작하지만, PDF evidence linking의 핵심 가치(클레임 클릭 -> 해당 근거 페이지/박스 강조)가 약하다.  
이 문서는 **현재 코드베이스를 최대한 보존**하면서 필요한 갭만 메우는 실행안이다.

---

## 1) 현재 상태 점검 (이미 충족됨, 재작업 금지)
- 라우팅
  - `/` -> Triage, `/workbench/:paperId` -> Workbench 이미 구성됨.
- Triage 클릭 동작
  - 다운로드가 아니라 Workbench 네비게이션으로 동작함.
- Mock fallback + Mock mode 표시
  - API 실패 시 mock 전환 및 UI 칩 표시가 동작함.
- Claim 리스트
  - Workbench Artifact 패널에서 claim 목록과 선택 상태 표시가 동작함.

---

## 2) 실제 갭 (이번 Fix Pack 대상)
1. PDF 렌더링이 `iframe` 기반이라 페이지 점프/정교한 하이라이트 연동이 제한됨.
2. claim 클릭 시 현재는 박스 강조만 있고, 페이지 점프(jumpToPage) 보장이 없음.
3. PDF 로딩이 URL 직결 방식이라 `Content-Disposition: attachment` 케이스에서 다운로드 우회가 약함.
4. Evidence 강조를 "선택 1개" 원칙으로 더 명확하게 강제해야 함.

---

## 3) 구현 원칙 (우리 코드 기준)
- 기존 API/타입(`paper_id`, `claim_id`, `highlights`)은 유지하고, UI 전용 파생 타입만 추가한다.
- 기존 Workbench/Artifact 구조를 유지하고, PDF 패널만 교체한다.
- mock fallback 정책은 유지하되, 유효한 4xx(예: duplicate job)는 mock으로 덮지 않는다.
- PDF blob URL은 생성/해제 수명주기를 명확히 관리한다.

---

## 4) 기술 스택 반영
- 유지: Vite + React + TypeScript + Tailwind + Zustand + react-router-dom + lucide-react
- 추가:
  - `@react-pdf-viewer/core`
  - `@react-pdf-viewer/highlight`
  - `@react-pdf-viewer/page-navigation`
  - `pdfjs-dist` (viewer worker 설정용)

---

## 5) 파일 단위 작업

## A. API / Data Layer
- `frontend/src/app/lib/api.ts`
  - `getPaperPdfBlobUrl(paperId, useMock)` 추가:
    - `fetch -> blob -> URL.createObjectURL`
    - 실패 시 mock PDF blob으로 fallback
  - 기존 `getPaperPdfUrl()`는 점진 폐기(호환 위해 남기되 신규 호출 금지).
- `frontend/src/app/lib/types.ts`
  - UI 전용 타입 추가:
    - `BBoxPct` (`left/top/width/height` 0~100)
    - `ClaimUi` (`id`, `label`, `text`, `pageIndex`, `bboxPct`)
  - 기존 `NotebookClaim`, `EvidenceHighlight`는 유지.

## B. Workbench 상태 연결
- `frontend/src/app/pages/AnalysisWorkbench.tsx`
  - `selectedClaimId` 유지.
  - `notebook.claims + notebook.highlights`를 `ClaimUi[]`로 매핑하는 selector 추가.
  - `PdfPanel`에 `claims`, `selectedClaimId` 전달.
  - claim 선택 시 기존처럼 `setActiveClaimId` 호출(단일 선택 유지).
  - blob URL 수명관리:
    - paper 변경 시 새 URL 로드
    - 언마운트/교체 시 `URL.revokeObjectURL`.

## C. PDF 패널 교체 (핵심)
- `frontend/src/app/components/PdfPanel.tsx`
  - `iframe` 제거.
  - `Viewer` + `highlightPlugin` + `pageNavigationPlugin` 적용.
  - claim 클릭 연동:
    - 선택 claim 변경 감지 -> `jumpToPage(claim.pageIndex)`.
  - 하이라이트 렌더:
    - `renderHighlights`에서 **선택 claim 1개만** 렌더
    - bbox `%` 좌표를 viewer layer 기준 style로 변환
    - 선택 강조 스타일(두꺼운 border + higher opacity)
    - 작은 label 배지(① 등) 오버레이.

## D. Claim 표시
- 기존 `ArtifactPanel` claim 리스트를 우선 활용.
- 라벨 표기는 `circledNumber(index)`를 그대로 사용하거나 `ClaimUi.label`을 사용.
- 클릭 핸들러는 현재 `onSelectClaim(claim_id)` 유지.

## E. Mock/오류 UX 유지
- Mock mode 칩/사유 표시는 현재 구조 유지.
- PDF blob fetch 실패 시 fallback reason을 mock mode로 누적 표시.

---

## 6) 수용 기준 (현실화 버전)
1. Triage 행 클릭 시 `/workbench/:paperId`로 이동한다.
2. Workbench PDF가 `iframe` 없이 viewer 컴포넌트로 렌더된다.
3. Claim 클릭 시:
   - 해당 페이지로 이동한다.
   - 선택 claim 1개 bbox만 강조된다.
   - 강조 박스에 라벨 배지가 보인다.
4. API 서버가 죽어도 mock으로 Workbench 전체가 렌더된다.
5. API 장애 시 Mock mode 칩이 노출되고 이유가 표시된다.

---

## 7) 테스트 계획
- 정적: `npm run lint`, `npm run build`
- E2E(mock):
  - Triage -> Workbench 라우팅
  - claim 클릭 후 viewer 페이지 이동/하이라이트 표시
  - Mock mode 표시 유지
- E2E(backend):
  - Mock mode 비표시
  - 실제 PDF blob 로딩 및 claim 클릭 동작

---

## 8) 구현 순서 (권장)
1. dependency 추가 + worker 설정
2. `getPaperPdfBlobUrl` + URL lifecycle
3. `PdfPanel` viewer 전환 + jump/highlight
4. Workbench claim mapping 연결
5. E2E 보강 및 회귀 검증
