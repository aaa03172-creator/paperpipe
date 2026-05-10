# Deep Research Report 5 검토 및 PaperPipe 맞춤 정리 (2026-03-11)

Status: Historical fit review  
Date: 2026-03-11  
Owner: Repository maintainers  
Canonical parent: `docs/Pending_PR_Queue.md`

## 1) 결론 요약
- `deep-research-report-5.md`의 전체 방향은 좋다.
- 특히 SR 검색전략을 **재현 가능한 Search Profile 자산**, **pilot 기반 refinement 루프**, **append-only query/run/approval 로그** 로 다루자는 점은 현재 PaperPipe의 search/profile 확장 방향과 정합적이다.
- 다만 원문은 표준(PRESS / PRISMA-S / Cochrane / IOM)을 강하게 반영하면서 v1 범위를 넓게 잡고 있어, 그대로 구현하면 초기 범위가 과도해진다.
- 따라서 PaperPipe v1은 **표준의 정신은 유지하되, 실행 범위는 축소** 해야 한다.

## 2) 채택 / 수정 / 보류

### 채택 (P0)
- standards-backed Search Profile 구조
- two-round interview
- append-only `query_versions`
- `run_log` / `approval_audit`
- `pilot -> screening -> refine` loop
- `reason_code`-based query refinement

### 수정 (v1 축소)
1. 질문 수 축소
- 원문은 Researcher/Librarian 라운드 각각 6~8개 질문을 제안한다.
- v1은 다음으로 축소하는 것이 맞다:
  - `Researcher 4`
  - `Librarian 4`
- 이유:
  - 현재 PaperPipe는 interactive wizard/UI가 아니라 backend/service/doc-first 단계다.
  - 질문 수가 많으면 Search Profile 생성보다 인터뷰 자체가 병목이 된다.

2. goldset sanity check는 optional
- 원문은 사실상 quality gate로 밀고 있다.
- v1에서는 optional이 맞다.
- 이유:
  - known relevant set을 항상 확보할 수 있는 팀/주제만 있는 것이 아니다.
  - goldset이 없다고 pilot loop를 막으면 실사용성이 떨어진다.

3. DB 추천 세트와 실제 사용 가능 세트 분리
- 원문은 최소 DB 세트 추천이 강하다.
- v1에서는 반드시 다음을 분리해야 한다:
  - `recommended_databases`
  - `available_databases`
- 이유:
  - Cochrane식 최소 세트 권고는 방법론적으로 맞지만, 실제 운영 환경에서는 라이선스/기관 접근/네트워크 제약이 다르다.
  - “추천”과 “실행 가능”을 섞으면 운영 로그가 왜곡된다.

4. 샘플 주제는 biomedical domain으로 교체
- 원문의 `MCI + Metacognitive Therapy (MCT)` 예시는 우리 도메인과 맞지 않는다.
- v1 문서 예시는 biomedical domain으로 바꾸는 것이 맞다.
- 권장 예시:
  - `mild cognitive impairment + medium-chain triglycerides`
- 단, 여기서도 `MCT` 약어는 남용하지 말고, full phrase를 기본으로 두고 약어는 보조 alias로만 다룬다.

### 보류 (P1)
- full PRESS automation
- mandatory grey literature at intake
- external DOI archiving
- OpenAlex-first design

## 3) 우리 상황에 맞춘 해석

### 맞는 부분
- Search Profile을 “대화 결과”가 아니라 “재현 가능한 실행 자산”으로 본 점
- query version과 run audit를 append-only로 본 점
- 파일럿 스크리닝으로 노이즈 유형을 분해하고 `reason_code` 기반으로 refinement 하자는 점
- DB별 실행 문자열과 실행 메타데이터를 남겨야 한다는 점

### 그대로 쓰면 안 되는 부분
- PRESS를 v1에서 자동화 리뷰까지 끌어오는 것
- grey literature를 intake hard stop으로 강제하는 것
- OpenAlex 같은 메타 인덱스를 설계 중심에 두는 것
- goldset 회수율을 모든 흐름의 필수 게이트로 두는 것

## 4) 이전 프롬프트/레퍼런스와 통합했을 때 유용한 것

### 가져와야 하는 것
1. `autoresearch`에서
- fixed evaluation harness
- keep/discard 기준 로그
- 작은 editable surface 원칙
- 연결 문서:
  - `docs/archive/Prompt_Review_01_Autoresearch_Search_2026-03-11.md`

2. `Research DNA` prompt에서
- `DRAFT -> PILOT -> LOCKED` 상태 머신
- append-only decision logs
- service-layer first 원칙
- 연결 문서:
  - `docs/archive/Prompt_Review_05_Research_DNA_2026-03-11.md`

3. 통합 우선순위 문서에서
- `ResearchDNA -> Profile` projection 경계
- search-eval artifact contract
- actor attribution contract
- search-source policy contract
- 연결 문서:
  - `docs/archive/Prompt_Review_Integrated_Priority_2026-03-11.md`

4. report 5 자체에서
- standards-backed field structure
- `approval_audit`
- `pilot -> screening -> refine`
- `reason_code` taxonomy thinking

### 참고만 하고 당장 가져오지 않을 것
1. `Auton`
- blueprint/runtime separation은 나중에 하되, 지금 search lane의 선결 과제는 아니다.

2. `fireauto`
- bounded loop/process discipline만 참고한다.
- plugin command system은 가져오지 않는다.

3. `DeerFlow`
- memory/sandbox/platform runtime은 현재 범위 밖이다.
- markdown skill metadata도 지금 search v1의 핵심은 아니다.

## 5) v1 최소 구조 권장안

### 인터뷰
- Round 1 `Researcher 4`
  - intent
  - question structure
  - population/context
  - intervention/exposure
- Round 2 `Librarian 4`
  - recommended DB set vs available DB set
  - recall vs precision default
  - controlled vocabulary + free-text usage
  - acronym/noise blocking rules

### 로그
- `query_versions`
  - append-only
- `run_log`
  - source별 결과 수
  - dedupe 전후 수
  - pilot size
  - precision proxy
- `approval_audit`
  - actor
  - role
  - action
  - rationale
- `screening_log`
  - `include | exclude | unclear`
  - `reason_code`
  - optional note

### 정책
- `recommended_databases`와 `available_databases` 분리
- goldset sanity check는 optional
- grey literature는 optional expansion
- OpenAlex는 supplemental candidate이지, 기본축이 아님

## 6) 예시 교체 권고
문서 예시는 아래로 교체하는 것이 맞다.
- 기존 비권장 예시:
  - `MCI + Metacognitive Therapy`
- 권장 예시:
  - `mild cognitive impairment + medium-chain triglycerides`

예시 작성 원칙:
- full phrase 우선
- acronym은 alias로만 추가
- biomedical domain과 현재 PaperPipe 문맥에 맞출 것

## 7) 지금 기준 최종 판정
- 이 리포트는 **방향 문서로는 채택 가능** 하다.
- 다만 v1 구현은 반드시 다음처럼 축소해야 한다:
  - `Search Profile + 2x4 interview + append-only logs + pilot refine loop`
- 이 축소안은 이전 prompt reviews와 충돌하지 않고, 오히려 그것들을 더 실행 가능한 형태로 좁혀준다.

## 8) 이후 문서화 권장
이 리포트를 바탕으로 이후 활성 문서에서 다룰 항목은 다음 세 개면 충분하다.
- `docs/RESEARCH_DNA.md`
- `docs/BLUEPRINT_RUNTIME.md` (later)
- `docs/AUDIT_TRAIL.md` (later)

추가 top-level 참고 문서(`PARKING_LOT`, `REF_*`)는 만들지 않는 것이 맞다.

## 9) 메모
- 본 문서는 `/Users/jangseongjin/Downloads/deep-research-report-5.md`를 검토하고, 2026-03-11 기준 PaperPipe search/profile 방향에 맞게 축소/통합한 내부 정리 문서다.
