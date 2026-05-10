# UX Review Report - Korean Reading Assist

Status: Current review artifact  
Date: 2026-03-17  
Owner: Lattice runtime maintainers  
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-17
Reviewer: Codex

## Input
- Screen/Flow: `/papers`, `/papers/:slug`, note summary and reading-assist localization boundary
- Goal action: 한국어 사용자가 논문 노트를 더 빨리 이해하되, canonical English/evidence judgment를 훼손하지 않는다.
- Primary persona: 영어 논문을 읽지만 한국어 보조 설명이 있으면 이해 속도가 빨라지는 연구자/대학원생
- Current friction: viewer/read surface는 성숙했지만, evidence grounding은 아직 완전히 hardened되지 않았고, 일부 생성 경로는 이미 한국어 출력을 직접 만들고 있어 canonical vs display 경계가 흐리다. 또한 실제 현재 계약을 다시 보면 `StructuredPaperState`에 translation field가 없고, `/paper-notes/{slug}`는 section payload가 아니라 `body_markdown` 하나를 내려서 broad EN|KO toggle을 바로 넣기 어렵다.
- Success metric: 한국어 사용자 기준 first-pass 이해 시간 단축, 그러나 search/screening/evidence judgment 경로에서 translation dependency는 0건 유지
- Constraints:
  - English remains canonical
  - Korean is display-only
  - partial translation only in v1
  - translation must never be used for inclusion/exclusion or final evidence judgment
  - current runtime is FastAPI + Vite + React Router + `--pp-*` token system

## 1) Quick Review (5 min)
- Block: 현재 가장 큰 위험은 "번역이 이미 있으니 core truth에도 써도 된다"는 오해다.
- Interpret: 한국어 번역의 가치는 읽기 속도 개선에 있고, 검색/스크리닝/근거 판정 자동화에 있지 않다.
- Act: v1은 viewer summary/tooltip 수준의 제한적 reading assist가 적절하다.
- Store: 영어 원문과 함께 보이는 보조 번역은 신뢰를 높이지만, 번역만 단독 노출되면 오히려 과신을 만든다.
- Ethics first pass: translation이 판단 레이어에 섞이면 사용자가 시스템 확실성을 과대평가할 위험이 있다.

## 2) Full Review (P0/P1/P2 prioritized)
### P0
- 번역을 inclusion/exclusion, claim truth, evidence judgment에 사용하면 안 된다. 현재 evidence grounding은 아직 deterministic resolver 단계가 아니기 때문이다.
- English/original canonical layer를 유지하지 않은 채 한국어를 정본처럼 저장하거나 노출하면 architecture contract와 사용자 신뢰 둘 다 깨진다.
- 현재 `src/llm_provider.py`의 한국어 직접 생성은 legacy convenience에 가깝다. 앞으로는 display-only derived layer로 해석되도록 경계를 다시 세워야 한다.
- 현재 `StructuredPaperState`에는 translation seam이 없고, `/paper-notes/{slug}`는 `body_markdown` + `structured_state` 계약이라 summary-level translation과 claim/meeting-pack translation을 한 번에 넣으면 범위가 과도하게 커진다.
- claim card에서 특히 `evidence.text` translation은 citation anchor처럼 오해될 위험이 높다. first slice에서는 영어 원문 유지가 맞다.

### P1
- `/papers/:slug`의 one-line summary, abstract, critical analysis, short synopsis, tooltip/glossary 보조는 한국어 reading assist로 가치가 높다.
- `/papers` 목록에서도 한국어 preview를 붙일 수는 있지만, relevance/search/filter의 기준이 돼서는 안 된다.
- claim card translation은 가능하더라도 follow-up slice로 분리하는 편이 맞다. 첫 범위는 `claim text`까지만 검토하고 `evidence.text`, locator, 숫자/단위는 영어 canonical 유지가 안전하다.
- Meeting Pack 같은 downstream draft surface에는 한국어 overview를 붙일 수 있으나, evidence ref와 claim truth는 영어/original canonical linkage를 유지해야 한다. 저장 위치도 paper `state.json`보다 pack artifact 쪽이 더 자연스럽다.

### P2
- full-body translation
- translation-aware search ranking
- translated claimset as a first-class state
- screening rationale bilingual expansion
- Meeting Pack translation을 summary-level viewer assist와 같은 PR로 묶는 것

### 6P storyboard context
- Problem: 사용자는 영어 논문과 구조화 노트를 빠르게 훑고 싶지만, first-pass reading cost가 높다.
- Emotion: "핵심만 빨리 이해하고 싶다. 하지만 잘못 이해하고 싶지는 않다."
- Action: 사용자는 `/papers`나 `/papers/:slug`에서 논문 노트를 연다.
- Struggle: 현재 번역이 직접 생성 단계에 섞여 있어, 어디까지 보조 정보인지 경계가 불분명하다.
- Attempt: 영어 원문을 정본으로 두고, 한국어를 paired display-only assist로 제한한다.
- Happy Ending: 사용자는 한국어 보조로 빠르게 읽되, 중요한 판단은 항상 영어/original evidence로 검증한다.

## 3) BMAP diagnosis
- Motivation: 높음. 한국어 사용자에게 reading cost 감소는 분명한 가치다.
- Ability: 중간. viewer는 준비됐지만 canonical/display boundary와 schema seam은 아직 없고, 현재 detail contract는 section-aware translation slot을 기본 제공하지 않는다.
- Prompt: 현재는 약함. 제품이 번역을 어디까지 믿어도 되는지 명시적으로 알려주지 않는다.

## 4) B.I.A.S diagnosis
- Block: 번역이 정본인지 보조인지 한눈에 구분되지 않으면 사용자가 멈춘다.
- Interpret: 가치 제안은 "읽기 보조"여야지 "판단 자동화"처럼 읽히면 안 된다.
- Act: 가장 쉬운 행동은 상세 화면에서 허용된 블록만 translation을 켜고 끄는 것이다. 전역 replacement toggle은 지금 구조와도 잘 맞지 않는다.
- Store: 영어 원문과 한국어 보조를 함께 보여주고, machine-translated 표시를 명확히 하면 장기 신뢰가 남는다.

## 5) Peak-End design notes
- Peak: 사용자가 영어 원문 아래에서 짧고 정확한 한국어 보조를 보고 빠르게 맥락을 잡는 순간
- Pit: 번역이 evidence truth처럼 보이거나, screening/exclusion 결정을 좌우한다고 오해되는 순간
- Transition: `/papers` 목록 preview -> `/papers/:slug` 상세 읽기 전환에서 translation hierarchy가 특히 중요하다. claim/evidence panel과 Meeting Pack은 다음 단계로 분리할수록 혼선을 줄일 수 있다.
- End: 읽기 종료 시 사용자가 "번역은 편했지만 판단은 원문 기반으로 해야 한다"는 인상을 남겨야 한다

## 6) Concrete changes
- Component:
  - summary/synopsis 수준에만 locale-aware display slot을 연다
  - 영어 원문과 한국어 보조를 paired layout으로 유지한다
  - evidence quote, claim id, locator는 영어/original canonical rendering을 유지한다
- Route:
  - 1차 대상은 `/papers/:slug`
  - `/papers`는 preview-only 범위에서만 검토한다
- Scope order:
  - PR1: schema/API seam + `/papers/:slug` one-line summary / abstract / critical analysis
  - PR2: claim card `claim text` translation only if still needed
  - PR3: Meeting Pack overview/speaker notes translation on pack artifact layer
- Copy:
  - `Machine translated from English`
  - `English/original text remains canonical`
  - `Translation may be partial`
- Default action:
  - translation off 또는 collapsed-by-default가 안전하다
  - 사용자가 필요할 때만 보조 레이어를 펼치는 편이 신뢰 관리에 유리하다
- Data/API contract:
  - translation payload는 canonical field overwrite가 아니라 derived locale payload로만 다룬다
  - search/screening/evidence APIs는 translation dependency 없이 유지한다
  - paper note detail은 broad body translation 대신 section-aligned or source-field-aligned payload로 여는 편이 맞다
  - Meeting Pack translation이 필요하면 pack payload에 저장하고 paper `state.json` canonical layer와 섞지 않는다

## 7) Ethics check results
- Regret: 현재 단계에서 translation을 P0처럼 밀면 나중에 후회할 가능성이 높다. 사용자가 실제 grounding 수준보다 더 강한 신뢰를 느낄 수 있기 때문이다.
- Black Mirror: 번역이 판단 근거처럼 소비되면, 언어 능력 차이가 연구 판단 품질 차이로 증폭될 수 있다.
- In Real-Life: 좋은 연구 도구는 "읽기 쉽게 도와주는 조수"여야지, 근거 수준을 숨긴 채 결론을 대신 내리는 사람이면 안 된다.

## 8) Next PR-sized actions
1. translation을 위한 canonical-vs-display schema/API seam을 먼저 정의하기
2. `/papers/:slug`에서 one-line summary / abstract / critical analysis만 다루는 summary-level paired translation PR로 좁히기
3. `src/llm_provider.py`의 한국어 직접 생성 경로를 future derived-display contract 관점에서 정리하고, claim card 및 Meeting Pack translation은 각각 별도 follow-up으로 분리하기

## 9) Implementation checkpoint (2026-04-04)
- 첫 slice는 `StructuredPaperState.reading_assists[]`와 `PaperNoteDetailResponse.reading_assist`를 여는 additive seam으로 제한한다.
- `/papers/:slug`에서는 Korean reading-assist를 collapsed-by-default panel로 노출한다.
- trust signal은 viewer 안에서 명시적으로 유지한다:
  - `Machine translated from English`
  - `English/original text remains canonical`
  - `Translation may be partial`
- 첫 구현 범위는 summary-level blocks only:
  - one-line summary
  - abstract
  - critical analysis
- evidence quote, claim truth, search/screening path는 이번 slice에 포함하지 않는다.

## 10) Implementation checkpoint (2026-04-07)
- discoverability를 조금만 높이되 reading flow를 바꾸지 않는 방향으로 확장한다.
- `/papers` 목록에서는 기존 state badge 줄 안에 `Korean assist` availability badge만 추가한다.
- `/papers/:slug` 상세에서는 새 패널이나 toggle을 늘리지 않고 `Properties` 안에 `Korean available` availability row만 추가한다.
- 이 표시는 `StructuredPaperState.signals.has_reading_assists` / `reading_assist_locales` 기반으로만 노출되고, relevance/search/filter 기준으로는 사용하지 않는다.
- trust hierarchy는 그대로 유지한다:
  - availability badge는 “있다”만 알려준다
  - 실제 canonical-vs-derived 경계와 machine-translation 신호는 collapsed reading-assist panel 안에서 계속 설명한다

## 11) Implementation checkpoint (2026-04-07, opt-in filter)
- `/papers`에는 opt-in `Only Korean assist` filter를 추가할 수 있다.
- 이 필터는 relevance ranking을 바꾸지 않고, availability가 이미 있는 note만 좁혀보는 utility control로만 동작해야 한다.
- copy는 “한국어가 더 좋은 note”처럼 읽히면 안 되고, 단지 “derived reading assist is available”을 뜻해야 한다.
- active filter chip과 empty-state copy에서도 같은 hierarchy를 유지한다:
  - list narrowing only
  - not a relevance or evidence-quality signal

## 12) Implementation checkpoint (2026-04-07, availability-first filter)
- `/papers`에서는 `Reading assist available`를 locale-agnostic 1차 narrowing control로 두고, `Only Korean assist`는 그보다 더 좁은 2차 control로 유지한다.
- `Only Korean assist`는 독립적인 quality signal이 아니라 `has_reading_assist=true` 위에 얹히는 locale-specific narrowing으로 해석되어야 한다.
- active-state UX도 같은 hierarchy를 따라야 한다:
  - `Reading assist available` = any saved derived reading assist
  - `Korean assist only` = saved derived reading assist 중 `ko` locale만
- empty-state copy는 “관련성이 낮다”가 아니라 “저장된 derived assist availability가 아직 없다”는 뜻으로 끝나야 한다.
- URL/query contract도 그 의도를 보존해야 한다:
  - `has_reading_assist=true` for availability narrowing
  - `reading_assist_locale=ko` only for locale narrowing within that availability set

## 13) Implementation checkpoint (2026-04-07, response-driven locale controls)
- `/paper-notes` list response는 현재 검색/태그/상태/structured 컨텍스트 안에서의 reading-assist metadata를 함께 내려야 한다:
  - `available_reading_assist_note_count`
  - `available_reading_assist_locales`
- 이 metadata는 pagination 전, but reading-assist self-filter 적용 전 기준이 더 안전하다. 그래야 locale control이 자기 자신의 필터 때문에 사라지지 않는다.
- `/papers` filter UI는 locale button을 하드코딩하지 않고 response metadata 기반으로 그린다.
- locale label은 사용자-facing display concern일 뿐이며, sorting/ranking/evidence quality와 연결되면 안 된다.
- 현재 locale이 `ko`뿐이어도 contract는 generic하게 유지하고, 실제 copy는 여전히 “reading assist availability”를 의미해야 한다.

## 14) Implementation checkpoint (2026-04-07, detail locale-aware copy)
- `/papers/:slug` detail panel 안에 남아 있던 locale-specific hardcoding은 response locale 기반 display label로 정리한다.
- 안전한 대상은 copy layer만이다:
  - panel title
  - show/hide button label
  - translated-column heading
- canonical warning 문구와 display-only hierarchy는 그대로 유지한다.
- 현재 `ko`에서는 화면상 텍스트가 거의 같아 보여도, contract는 future locale을 막지 않는 방향이어야 한다.

## 15) Implementation checkpoint (2026-04-08, descriptive provenance)
- detail reading-assist panel은 provenance를 더 보여줄 수 있지만, 그것은 어디까지나 descriptive metadata여야 한다.
- 안전한 표시는 아래처럼 limited metadata만 포함한다:
  - canonical locale
  - source locale
  - translator label
  - model label
  - version label
- 이 정보는 trust calibration을 돕는 용도이지, quality score나 evidence strength처럼 해석되면 안 된다.
- provenance는 block-level로 다를 수 있으므로, per-block metadata가 top-level 단정 문구보다 안전하다.

## 16) Implementation checkpoint (2026-04-08, locale continuity into detail)
- `/papers`에서 locale-specific reading-assist filter를 걸고 note detail로 들어갈 때, detail도 같은 locale preference를 유지하는 편이 더 자연스럽다.
- 안전한 구현은 detail API에 optional `reading_assist_locale` query를 여는 것이다.
- fallback behavior는 그대로 둔다:
  - requested locale가 있으면 우선 시도
  - 없거나 payload가 비어 있으면 기존 default preference (`ko`, then first available)로 복귀
- 이 query는 display-locale continuity를 위한 것이지, canonical note routing이나 evidence semantics를 바꾸는 기능이 아니다.

## 17) Implementation checkpoint (2026-04-13, detail in-screen locale switch)
- list에서 detail로 넘어온 locale continuity만으로는, detail 안에서 다른 saved locale을 비교하거나 전환하기 어렵다.
- 현재 contract 위에서 가장 안전한 확장은 detail panel 안에 explicit locale switch를 두는 것이다.
- switch는 아래 조건을 지켜야 한다:
  - available locale이 2개 이상일 때만 보인다
  - existing `reading_assist_locale` query contract만 사용한다
- selection은 display-only derived payload만 바꾸고 canonical markdown/body는 바꾸지 않는다
- locale switch label은 locale-aware display concern일 뿐이며, quality score, trust rank, evidence strength처럼 보이면 안 된다.
- multi-locale mock fixture (`ko`, `ja`)로 interaction을 검증해, future locale이 들어와도 현재 viewer contract를 유지할 수 있게 한다.

## 18) Implementation checkpoint (2026-04-13, explicit auto/default view state)
- locale switch가 생긴 뒤에는, 사용자가 현재 manual locale을 보고 있는지 아니면 note의 default/fallback view를 보고 있는지 더 명확히 드러내는 편이 안전하다.
- 현재 contract 위에서 가장 작은 보강은 아래 두 가지다:
  - detail panel locale switcher에 explicit `Auto` option 추가
  - `Properties` rail에 현재 assist view 상태(`Manual selection` vs `Auto default`) 추가
- `Auto`는 new backend semantics가 아니라 기존 `reading_assist_locale` query 제거를 의미해야 한다.
- 이 affordance는 locale ranking이나 trust grading이 아니라 display-state clarity를 위한 것이어야 한다.
- multi-locale detail flow는 `ko -> ja -> Auto(default)` 복귀까지 검증해서, active state와 fallback state를 모두 안전하게 고정한다.
