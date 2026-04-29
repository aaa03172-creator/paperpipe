# UX Review Report - Backend Visual Dark Theme

Status: Current review artifact
Date: 2026-03-31
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-31
Reviewer: Codex

## Input
- Screen/Flow: backend-backed paper notes, triage, workbench, and artifact viewers across desktop/mobile visual regression coverage
- Goal action: 사용자가 backend runtime에서 dark-first Lattice UI를 일관되게 보고, 첫 진입부터 note/workbench/artifact 흐름을 혼란 없이 이어간다.
- Primary persona: 로컬 runtime으로 논문 note와 downstream artifacts를 검토하는 연구자/운영자
- Current friction: system theme가 `light`일 때 visual baseline과 실제 런타임이 어긋나면서 screenshot 회귀가 대량으로 깨졌고, dark-first Lattice 톤도 환경 의존적으로 흔들렸다.
- Success metric: backend visual suite가 desktop/mobile 전 범위에서 안정적으로 통과하고, runtime이 저장 상태가 없는 첫 진입에서도 dark theme로 시작한다.
- Constraints:
  - existing `--pp-*` tokens and dark-first Lattice tone must remain the visual contract
  - no broad layout redesigns; smallest safe change only
  - verification must be repo-grounded with real backend Playwright coverage

## Quick Review (5 min)
- Block: visual contract가 OS theme에 종속되어 baseline과 런타임이 엇갈렸다.
- Interpret: 사용자는 같은 product를 보고 있는데도 환경마다 다른 화면을 받았다.
- Act: 기본 theme를 dark로 고정하고 visual tests도 same contract로 시작시키는 것이 가장 작은 수리다.
- Store: 첫 진입과 artifact viewer 전반의 시각적 신뢰를 회복하는 변화다.
- Ethics first pass: 사용자 선택을 빼앗는 강제 UI가 아니라, baseline과 product contract를 일치시키는 안전장치다.

## Full Review
### P0
- dark-first 계약이 환경 의존으로 깨지면 screenshot drift뿐 아니라 첫 인상도 바뀌므로 우선 복구해야 한다.
- workbench rail visual test는 실제 rail 부재가 아니라 selector 계약 오류였으므로 test target을 정확한 textbox anchor로 바로잡아야 했다.

### P1
- visual suite는 stale baseline과 live regression을 구분해야 하므로, representative desktop/mobile 화면을 먼저 다시 실행해 dark mismatch가 주원인인지 확인하는 절차가 필요했다.
- baseline refresh는 representative 샘플이 깨진 UI가 아니라 현행 UI 계약을 반영하고 있다는 확인 뒤에만 진행해야 한다.

### P2
- 이후 theme toggle preferences를 더 세밀하게 다듬을 수는 있지만, 현재 범위에서는 dark-first bootstrap 안정화가 우선이다.

### Full Review Coverage
- 6P storyboard context: Problem은 환경마다 다른 theme, Emotion은 “왜 화면이 갑자기 다른가”라는 불신, Action은 note/workbench/artifact 진입, Struggle은 visual drift와 unstable screenshots, Attempt는 representative reruns와 baseline refresh, Happy Ending은 clean backend suite 통과다.
- BMAP: Motivation은 높음, Ability는 theme bootstrap 한 곳과 test bootstrap 한 곳을 고치면 충분, Prompt는 visual suite failure 자체가 명확한 신호였다.
- B.I.A.S: Block은 OS theme 의존성, Interpret는 stale baseline처럼 보이는 대량 실패, Act는 dark bootstrap 강제와 selector repair, Store는 backend visual contract의 재안정화다.
- Peak-End: peak는 clean visual suite 회복, pit는 light-mode actual screenshot이 dark baseline과 크게 벌어진 순간, end는 full backend suite green이다.
- Ethics: Regret/Black Mirror/In Real-Life 모두 통과. 사용자 조작이 아니라 product contract 복구다.

## BMAP diagnosis
- Motivation: 연구자는 viewer보다 결과 해석에 집중하고 싶어 하므로 환경 차이 없이 같은 화면을 기대한다.
- Ability: theme default와 Playwright init script 한정 수정으로 해결 가능했다.
- Prompt: visual failures가 충분히 선명한 prompt였고, representative rerun이 root cause를 빠르게 드러냈다.

## B.I.A.S diagnosis
- Block: system theme fallback이 dark-first contract를 막았다.
- Interpret: 대량 visual failure가 실제 레이아웃 파손처럼 보였지만, 샘플 확인 후 stale baseline 중심 문제로 재해석됐다.
- Act: app default를 dark로 옮기고, visual suite는 localStorage + media emulation으로 같은 시작점에서 실행되게 했다.
- Store: 사용자는 어느 runtime에서도 같은 Lattice 분위기를 기억하게 된다.

## Peak-End design notes
- Peak: paper notes/workbench/artifact surfaces가 모두 같은 dark tone으로 이어질 때 신뢰감이 높다.
- Pit: system theme에 따라 첫 화면이 달라지는 순간, 사용자는 saved-state/health보다 먼저 시각적 불일치를 감지한다.
- Transition: list -> detail -> workbench -> artifact viewer 전환에서 theme가 유지돼야 flow가 하나의 product처럼 느껴진다.
- End: visual suite clean pass가 곧 사용자 첫인상 consistency의 대리 지표가 된다.

## Concrete changes
- `frontend/src/app/store/useAppStore.ts`
  - first-load theme default를 `dark`로 고정해 저장 상태가 없는 런타임도 dark-first로 시작하게 했다.
- `frontend/e2e/visual-backend.backend.spec.ts`
  - each visual test beforeEach에서 `pp-theme=dark`를 주입하고 dark color scheme을 emulate 하도록 고정했다.
  - desktop workbench rail locator를 placeholder 텍스트가 아닌 실제 `Search papers` textbox 기준으로 고쳤다.
- `frontend/e2e/visual-backend.backend.spec.ts-snapshots/*`
  - current backend-backed desktop/mobile UI 기준으로 visual baselines를 새로 생성했다.

## Ethics check results
- Regret: 통과. 사용자가 나중에 봐도 “같은 product를 같은 tone으로 보이게 한 수리”로 이해된다.
- Black Mirror: 통과. 사용자를 특정 테마에 가두는 조작이 아니라 계약과 테스트 안정성을 맞추는 변경이다.
- In Real-Life: 통과. 다크 중심 분석 도구가 환경에 따라 흔들리지 않는 편이 실제 연구 맥락에 더 맞다.

## Next PR-sized actions
- theme toggle가 `light`로 저장된 기존 사용자도 의도대로 복원되는지 작은 focused check를 추가한다.
- visual snapshot drift가 다시 커질 때 stale baseline인지 live regression인지 구분하는 triage note를 `frontend/e2e/README` 성격 문서에 남긴다.
- 필요한 경우 runtime readiness 쪽에도 current theme/debug surface를 작게 추가해 QA가 원인을 더 빨리 읽게 한다.
