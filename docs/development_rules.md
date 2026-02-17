# Development Rules & Principles (PaperPipe Legacy)

이 문서는 PaperPipe 프로젝트를 진행하며 정립된 **개발 원칙, 효율화 규칙, 오류 방지 가이드라인**을 정리한 것입니다. 향후 다른 프로젝트 개발 시에도 참고하여 생산성과 안정성을 유지하는 데 사용합니다.

---

## 1. 핵심 철학 (Core Philosophy)

### 1.1 API-First & UI-Agnostic
- **모든 로직은 API로 캡슐화한다.** UI는 단지 API의 소비자일 뿐이며, 언제든 교체 가능해야 한다.
- 핵심 로직이 UI 코드에 종속되지 않도록 한다.

### 1.2 Zero Hard-Coding (설정의 외부화)
- **도메인 규칙(프롬프트, 페르소나, 파라미터)은 코드에서 분리하여 YAML 파일로 관리한다.**
- 코드는 "어떻게(How)"를 처리하고, 설정 파일은 "무엇을(What)" 처리할지 정의한다.
- 단, **입출력 스키마(Schema), 보안 정책, 상태 머신** 등 시스템 안정성과 직결된 계약은 코드(Pydantic 등)로 강제한다.

### 1.3 Fail-Safe & Resilience (실패에 대한 내성)
- **개별 실패가 전체 프로세스를 중단시켜선 안 된다.** (Bulk 처리 시 필수)
- 실패한 항목은 에러 로그와 상태를 기록하고(`status: failed`), 다음 항목으로 **반드시 넘어간다(CONFIRM & CONTINUE).**
- 외부 API나 불확실한 작업은 재시도(Retry) 로직과 타임아웃을 반드시 포함한다.

---

## 2. 안전 및 데이터 무결성 (Safety & Integrity)

### 2.1 Read-Only 원칙
- **원본 데이터 소스(예: Zotero DB)는 절대 직접 수정하지 않는다.** (Read-Only)
- 데이터 수정이 필요할 경우, 별도의 포맷(.ris, .bib)으로 내보내거나 API를 통해 간접적으로 수행한다.

### 2.2 비파괴적 조작 (Non-Destructive Operations)
- 대량 삭제(Bulk Delete)와 같은 파괴적 작업은 **사용자 확인 절차** 없이는 절대 수행하지 않는다.

---

## 3. 방법론 및 지능형 처리 (Methodology & AI)

### 3.1 계층적 프롬프팅 (Hierarchical Prompting)
- 복잡한 판단을 한 번에 묻지 않는다. **단계별 논리(Step-by-Step Logic)** 를 사용한다.
  - 예: `Domain` 확인 -> `Topic` 분류 -> `Specific Keywords` 추출
- 예/아니오 질문보다는 근거를 먼저 찾고 결론을 내리도록 유도한다.

### 3.2 하이브리드 태깅 전략 (Hybrid Tagging)
- **Extraction (Hard Fields):** 텍스트에 명시된 값(용량, 수치 등)은 Regex나 추출 모델을 사용해 정확히 가져온다. (없으면 `unknown`)
- **Generation (Soft Tags):** 주제나 문맥 같은 추상적인 정보는 LLM을 통해 생성한다.

### 3.3 청킹 전략 (Chunking)
- 무조건적인 텍스트 분할보다는 **의미 단위(Section-level) 청킹**을 우선한다. (Intro, Methods, Results 등 논리적 구조 활용)

### 3.4 증거 기반 검증 (Evidence-Based Verification)
- LLM의 출력(Claim)에는 반드시 원문의 **출처(Evidence Span/Page)** 가 연결되어야 한다.
- 근거가 없는 주장은 신뢰도(Confidence)를 낮추거나 `unknown`으로 처리한다.

---

## 4. 기술 스택 및 코딩 표준 (Tech Stack & Coding Standards)

### 4.1 타입 안전성 (Type Safety)
- **Python Typing과 Pydantic을 적극 활용한다.**
- 데이터 구조를 명시적으로 정의하여 런타임 오류를 줄이고 IDE 지원을 극대화한다.

### 4.2 로깅 표준화 (Logging)
- 모든 중요 이벤트는 구조화된 로그로 남긴다.
- 단순 `print` 대신 `logging` 모듈을 사용하며, 실패 시 **Traceback**과 식별자(ID)를 포함한다.

### 4.3 설정 관리 (Layout)
- `configs/` 디렉토리에 모든 설정을 모아 관리한다.
- `schemas/`에는 데이터 계약(Pydantic 모델)을 위치시킨다.

---

## 5. 운영 효율화 (Operational Efficiency)

### 5.1 "Golden Data" 구축
- 개발 초기나 테스트 시, 신뢰할 수 있는 **정답 데이터셋(Golden Data)** 을 먼저 확보한다.
- 이를 통해 회귀 테스트(Regression Test)를 수행하고 모델의 성능 변화를 감지한다.

### 5.2 작업 경계 설정 (Task Boundary)
- 복잡한 작업은 **Task Boundary(작업의 정의, 상태, 목표)** 를 명확히 설정하고 시작한다.
- 작업 도중 맥락을 잃지 않기 위해 주기적으로 상태를 업데이트한다. (에이전트 협업 시 중요)

### 5.3 반복적인 작업의 자동화
- 자주 사용하는 워크플로우(예: 배포, 테스트 데이터 생성)는 스크립트나 명령어로 만들어 둔다.
