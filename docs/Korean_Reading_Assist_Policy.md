# Korean Reading Assist Policy

Status: Active  
Date: 2026-03-17  
Owner: Lattice runtime maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`  
Applies to: `/papers`, `/papers/:slug`, note summaries, reader-facing help copy, future localized reading-assist surfaces

Related docs:
- `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
- `docs/RESEARCH_DNA.md`
- `docs/Citation_Grounding_Audit_2026-03-13.md`
- `docs/Current_Code_Baseline_Audit_2026-03-13.md`
- `docs/UX_REVIEW_REPORT_korean-reading-assist.md`

## 1. Purpose
이 문서는 Lattice/PaperPipe 현재 상태를 기준으로 한국어 번역의 제품 역할과 계약 경계를 고정한다.

핵심 판단은 단순하다.

- 한국어 번역은 가치가 있다.
- 하지만 2026-03-17 현재 시점에서는 P0 코어 기능이 아니다.
- 현재 제품의 P0는 evidence/search/screening 신뢰도를 먼저 고정하는 것이다.
- 따라서 한국어는 v1에서 `reading-assist` 레이어로만 다룬다.

2026-03-17 repo-grounded recheck 결과도 이 판단을 유지한다.

- 방향 자체는 맞다.
- 하지만 현재 구현 계약을 보면 broad v1 rollout보다 `schema/API seam -> summary-level viewer assist -> later follow-ups` 순서가 더 안전하다.

## 2. Current Product Reality

### 2.1 Search and screening are closer to P0 readiness than translation
현재 저장소에는 `Research DNA` 기반의 실제 실행 가능한 검색/스크리닝 레인이 존재한다.

- `pilot -> screening -> refine` 루프가 문서/스토어/API/CLI까지 연결돼 있다.
- append-only screening/audit 계약이 이미 명시돼 있다.
- search eval도 별도 harness로 관리된다.

즉, 검색/스크리닝은 아직 계속 다듬는 중이지만, 적어도 제품의 core decision lane으로 취급할 실체가 있다.

### 2.2 Reader surfaces are mature enough for assistive display
Paper Notes Viewer, list/detail route, related papers, workbench handoff는 이미 사용자-facing reading surface로 성숙해 있다.

이 말은 곧 번역이 들어간다면 viewer 레이어에서 보조적으로 붙는 것이 자연스럽다는 뜻이지, core research truth를 소유해야 한다는 뜻이 아니다.

### 2.3 Evidence grounding is not yet stable enough to let translation influence judgment
현재 citation/evidence 레인은 evidence-aware 하지만 strict grounded resolver 모델은 아직 아니다.

현재 audit 기준:
- unsupported claim downgrade는 있다
- page/location 기반 citation jump는 있다
- 하지만 deterministic chunk grounding과 verified resolver는 아직 없다

따라서 번역이 claim/evidence 판단 레이어에 섞이면, 현재 시스템이 실제로 보장하지 않는 확신을 UI가 과장하게 된다.

### 2.4 Current implementation already leaks Korean into generation
현재 구현에는 한국어가 이미 일부 생성 단계에 직접 들어가 있다.

예시:
- `src/llm_provider.py`는 deep read와 one-liner를 한국어로 생성하도록 프롬프트한다
- `src/services/summary_normalizer.py`는 translation tail 제거 로직을 갖고 있다
- `frontend/index.html`의 기본 문서 언어는 `ko`다

이 상태는 "한국어 지원이 이미 있다"는 의미가 아니라, 번역/표시/정본 경계가 아직 분리되지 않았다는 의미로 해석해야 한다.

### 2.5 Current implementation constraints make broad v1 scope premature
현재 repo 계약을 실제로 다시 확인하면, translation을 바로 넓게 넣기 어려운 구조적 이유가 있다.

- `StructuredPaperState`는 아직 `translations`나 locale-scoped display payload를 갖지 않는다.
- `GET /paper-notes/{slug}`는 note body를 section payload가 아니라 `body_markdown` 하나로 내린다.
- viewer는 `body_markdown` 전체를 그대로 렌더링하고, claim card는 별도 `structured_state.claimset[]`로만 렌더링한다.
- `MeetingPack`도 자체 schema를 갖지만 아직 translation field가 없다.

즉 현재 상태에서 아래를 한 PR로 묶으면 범위가 커진다.

- summary/abstract/critical analysis translation
- claim/evidence card translation
- Meeting Pack summary/speaker note translation

따라서 현실적인 첫 단계는 broad feature가 아니라, additive display seam을 먼저 여는 것이다.

## 3. Product Decision

### 3.1 Priority call
- 한국어 번역은 `P1 reading-assist`
- P0는 `search -> screening -> evidence`의 신뢰도와 canonical contract
- 번역은 core workflow가 안정된 뒤에 붙는 보조 레이어다

### 3.2 Current decision as of 2026-03-17
현재 게이트는 아직 완전히 닫히지 않았다.

이유:
- `Research DNA` 검색/스크리닝 레인은 실체가 있다
- viewer도 읽기 표면으로 충분히 성숙했다
- 하지만 evidence grounding/citation truth는 아직 transitional하다

따라서 현재 시점의 결론은 아래와 같다.

- 한국어는 제품 방향상 `valuable`
- 하지만 아직 `promotion-ready core feature`는 아니다
- 지금은 정책/경계 문서화와 display seam 설계까지만 허용한다
- broad rollout이나 canonical-state 통합은 보류한다

2026-03-17 recheck 기준으로는 이 결론을 조금 더 구체화한다.

- 먼저 허용할 범위는 `/papers/:slug` summary-level reading assist다
- claim card translation은 한 단계 뒤로 미룬다
- Meeting Pack translation은 paper `state.json`이 아니라 pack artifact layer에서 별도로 다루는 편이 맞다

## 4. Non-Negotiables

### 4.1 English remains canonical
아래는 영어 또는 원문 기반 canonical layer로 유지한다.

- search query design
- screening decision
- include/exclude rationale
- claim/evidence truth
- final evidence judgment
- review queue reason codes
- eval/baseline comparison
- canonical note/sidecar state의 의미 판단 필드

### 4.2 Korean is display-only
한국어는 사용자 읽기 보조를 위한 display layer로만 취급한다.

- canonical truth를 대체하지 않는다
- canonical search/screening/evidence state를 덮어쓰지 않는다
- 한국어가 없으면 영어 원문으로 자연스럽게 fallback한다

### 4.3 Partial translation only in v1
v1에서는 부분 번역만 허용한다.

허용 방향:
- one-line summary
- short section synopsis
- glossary/tooltip형 용어 보조
- UI help/copy 보조
- viewer에서 영어 본문 아래 붙는 보조 요약

비허용 방향:
- full note body 자동 번역
- full claimset replacement
- translated evidence quote를 정본처럼 노출
- translation-first search index
- 번역본만 보고 screening/judgment를 내리게 만드는 UX

### 4.4 Translation must never drive research judgment
번역은 아래 판단의 근거가 될 수 없다.

- 논문 포함/제외 결정
- claim acceptance/rejection
- evidence strength 판정
- final synthesis or recommendation

판단은 항상 canonical English/original layer에서 이뤄지고, 한국어는 그 결과를 읽기 쉽게 돕는 보조물로만 사용한다.

## 5. Allowed Scope For v1

### 5.1 Viewer surfaces
`/papers`와 `/papers/:slug`에서 아래 정도의 보조 레이어는 허용 가능하다.

- 영어 canonical summary 옆/아래에 붙는 한국어 요약
- selected terminology tooltip
- section-level micro-summary
- empty/help/error copy의 한국어 현지화

조건:
- 영어 원문 또는 canonical label이 항상 함께 남아 있어야 한다
- evidence quote와 locator는 원문 기준을 유지해야 한다
- translation이 없더라도 core reading flow가 깨지면 안 된다

2026-03-17 기준 첫 구현 권장 범위:

- `/papers/:slug` only
- one-line summary
- abstract
- critical analysis

첫 구현에서 보류:

- note body 전체 EN | KO replacement
- evidence text 자체의 한국어 치환
- `/papers` 목록 relevance/search에 영향을 주는 preview translation

claim card는 장기적으로 가능하지만, 첫 slice에서는 `claim text` translation만 검토하고 `evidence.text`는 영어 원문 유지가 안전하다.

### 5.2 Meeting Pack and downstream presentation copy
Meeting Pack은 원래도 canonical research state를 새로 소유하지 않는 downstream draft artifact다.

따라서 장기적으로는 한국어 overview/speaker-note 보조가 가능하다. 다만 v1에서는 아래 조건을 지킨다.

- claim/evidence ref는 영어/original canonical linkage 유지
- translation은 presentation aid일 뿐 evidence truth가 아님
- screening/context wording은 계속 framing layer에만 머문다

2026-03-17 recheck 권고:

- Meeting Pack translation은 summary-level viewer assist 다음 단계로 미룬다
- 저장이 필요하면 paper-scoped `state.json`이 아니라 Meeting Pack artifact payload에 locale-derived field로 둔다

### 5.3 UI chrome localization
버튼, helper text, status explanation 같은 UI chrome 현지화는 허용 가능하다.

단:
- enum/contract 값 자체를 바꾸지 않는다
- API/DB/storage 레벨 canonical 값은 유지한다

## 6. Explicitly Out Of Scope For v1
- 번역을 query generation 또는 query refinement 입력으로 사용
- translated screening rationale를 정책 truth처럼 재사용
- `state.json`, `claimset`, `screening.jsonl`, `approval_audit`, `profiles.yaml` canonical 필드를 한국어로 저장
- 한국어 번역만을 기준으로 relevance ranking, filtering, inclusion/exclusion을 수행
- evidence quote를 한국어로 바꾼 뒤 이를 citation anchor처럼 사용하는 것
- 한국어 번역 결과를 Obsidian note 본문에 무분별하게 append하는 것
- `body_markdown` 전체를 EN/KO replacement view로 뒤집는 것
- translated claim evidence text를 claim/evidence truth처럼 표시하는 것
- Meeting Pack translation payload를 paper-scoped canonical sidecar에 섞는 것

## 7. Implementation Contract For Future PRs

### 7.1 API-first and schema-first
번역 기능이 실제로 들어가면 core logic는 여전히 FastAPI 뒤에 있어야 하며, 번역 payload도 `src/schemas/` 하위의 명시적 Pydantic 계약으로 정의해야 한다.

UI에서 ad hoc으로 영어 문자열을 직접 변환해 canonical state처럼 다루는 방식은 금지한다.

### 7.2 Derived field only
번역 데이터가 저장돼야 한다면, canonical field overwrite가 아니라 derived display field로만 저장한다.

예:
- locale-scoped display payload
- translation provenance
- source field pointer
- translator/model/version metadata

기본 원칙:
- canonical English/original field는 그대로 둔다
- Korean field는 optional derived payload다

### 7.3 Idempotent write rule
Obsidian이나 sidecar에 번역 결과를 쓰는 경우에도 blind append는 금지한다.

기본 v1 권장 경로:
- note mutation보다 API response 또는 UI-layer cache 우선
- persistent write가 필요해도 section-replace safe 규칙을 따라야 한다

### 7.4 Trust signaling
번역이 생성형이라면 아래 신호를 명시한다.

- `Machine translated` 또는 동등한 표시
- source language is canonical
- translation may be partial

사용자가 번역을 정본으로 오인하게 만드는 copy는 금지한다.

## 8. Current Gaps To Resolve Before Promotion
한국어를 P1 실험에서 더 넓은 기본 기능으로 승격하려면 최소 아래가 필요하다.

1. evidence resolver / grounding semantics가 현재보다 명확해질 것  
2. canonical English summary/claim/evidence boundary가 storage/API에서 더 분명해질 것  
3. translation payload를 derived layer로 수용하는 schema/API 계약이 추가될 것  
4. viewer에서 영어 원문과 번역 보조의 hierarchy가 명확히 검증될 것

2026-03-17 현재는 이 승격 조건이 아직 충족되지 않았다.

## 9. Execution Guidance
다음 translation 관련 PR은 아래 순서를 따른다.

1. canonical vs display boundary 문서/스키마를 먼저 연다  
2. `StructuredPaperState` / `PaperNoteDetailResponse`에 additive translation seam을 정의한다  
3. `/papers/:slug`에서 one-line summary / abstract / critical analysis만 제한적으로 실험한다  
4. claim card translation은 별도 follow-up으로 분리하고, first slice에서는 evidence text를 영어로 유지한다  
5. Meeting Pack translation은 paper state와 분리된 pack payload follow-up으로 다룬다  
6. search/screening/evidence judgment path에는 translation dependency를 추가하지 않는다  
7. broad rollout 전에는 이 문서와 `docs/UX_REVIEW_REPORT_korean-reading-assist.md`를 함께 갱신한다
