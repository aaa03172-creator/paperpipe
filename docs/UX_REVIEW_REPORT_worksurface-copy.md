# UX Review Report: Core Worksurface Copy

Status: Active
Date: 2026-03-23
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: `/` triage header, `/workbench/:paperId` mobile controls, global lazy-load fallback
- Goal action: 사용자가 첫 진입과 workbench handoff에서 현재 작업 표면을 즉시 이해한다.
- Primary persona: triage와 workbench를 오가며 논문 상태와 evidence를 검토하는 연구자
- Current friction: `Phase 3 Control UI`, `Run & View Controls`, `Loading...` 같은 copy가 내부 단계/도구 shell처럼 읽혀 현재 작업 책임을 늦게 설명한다.
- Success metric: triage 진입 후 첫 스캔에서 queue/workbench 목적을 더 빨리 해석하고, mobile workbench controls를 바로 찾을 수 있다.
- Constraints: copy-only lane, 기존 route/layout 구조 유지, `--pp-*` token과 dark-first Lattice tone 유지

## Quick Review (5 min)
- 첫 화면과 handoff 순간의 wording만 더 직접적으로 바꾸면 충분하다.
- 내부 단계명보다 queue/workbench vocabulary가 현재 작업을 더 빨리 설명한다.
- 구조나 CTA를 바꾸지 않고 header/control copy만 정리하는 게 가장 안전하다.

## Full Review
### P0
- 현재 치명적 플로우 단절은 없지만, 내부 단계명은 first-read 해석을 늦춘다.

### P1
- triage eyebrow와 subtitle은 queue -> workbench 흐름을 직접 설명해야 한다.
- mobile workbench controls summary는 기능 묶음보다 작업 표면 이름을 먼저 말해야 한다.
- global suspense fallback도 generic shell보다 workspace-oriented wording이 낫다.

### P2
- 결과 수/로딩 문구도 queue vocabulary와 맞추면 list surface의 톤이 더 일관된다.

### Full Review Coverage
- 6P storyboard context: Problem은 내부 shell copy가 현재 화면 책임을 늦게 설명하는 것, emotion은 약한 혼란, action은 triage에서 workbench로 이동, struggle은 surface purpose 해석, attempt는 calmer product wording, happy ending은 첫 스캔에서 현재 작업을 바로 이해하는 것.
- BMAP: Motivation은 높고, Ability는 copy만 바꿔도 충분히 개선되며, Prompt는 short queue/workbench wording으로 해결 가능하다.
- B.I.A.S: Block은 internal wording, Interpret는 queue/workbench vocabulary가 개선, Act는 workbench controls를 더 빨리 찾게 되고, Store는 calm, credible product language가 남는다.
- Peak-End: Peak는 현재 화면 목적이 바로 읽히는 순간, pit는 내부 console처럼 읽히는 순간, transition은 triage -> workbench handoff, end는 workspace loading까지 같은 tone으로 닫히는 것이다.
- Ethics: 과장이나 urgency를 더하지 않고 현재 작업만 더 직접적으로 설명한다.

## BMAP diagnosis
- Motivation: 높음. 사용자는 현재 무엇을 검토하는지 바로 알고 싶다.
- Ability: 높음. header/control/fallback copy만 바꿔도 해석 비용이 줄어든다.
- Prompt: `Research queue`, `Workbench controls`, `Loading workspace...` 정도의 짧은 prompt면 충분하다.

## B.I.A.S diagnosis
- Block: 내부 단계/도구 명명이 current surface를 즉시 설명하지 못한다.
- Interpret: queue/workbench 중심 언어가 현재 작업 책임을 바로 읽게 한다.
- Act: triage에서 deeper inspection으로 넘어갈 준비가 더 빨라진다.
- Store: 절제된 wording이 research tool다운 인상을 남긴다.

## Peak-End design notes
- Peak: 첫 화면에서 queue 목적이 바로 읽히는 순간
- Pit: stage/control wording이 internal shell처럼 읽히는 순간
- Transition: triage queue -> workbench
- End: global loading copy도 같은 workspace grammar로 닫히는 것

## Concrete changes
- `App` suspense fallback을 `Loading workspace...`로 교체
- triage eyebrow를 `Research queue`로 교체
- triage subtitle, section title, count/loading copy를 queue vocabulary로 정리
- workbench terminal button을 `Terminal logs`로 축약
- mobile controls summary를 `Workbench controls`로 교체

## Ethics check results
- Regret: 통과. 현재 작업을 더 분명히 설명하는 수준이다.
- Black Mirror: 통과. 조급함이나 전환 압박을 추가하지 않는다.
- In Real-Life: 통과. 실제 연구 도구의 절제된 안내처럼 읽힌다.

## Next PR-sized actions
- workbench header subtitle이 필요해지면 별도 copy lane으로 분리한다.
- triage/workbench document title을 더 넓게 정리할 때는 route-level naming만 묶어서 다룬다.
- future viewer lanes에서도 internal shell wording이 남아 있으면 같은 방식으로 copy-only split을 유지한다.
