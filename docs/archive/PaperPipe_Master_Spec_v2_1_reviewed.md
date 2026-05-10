# PaperPipe — Antigravity 개발용 마스터 명세서 (Single Source of Truth)

Status: Superseded spec  
Date: 2026-03-09  
Owner: Repository maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

> **문서 버전:** 2.1.1 (Final MVP Edition — QA/유지보수 강화본)  
> **목적:** PaperPipe 시스템의 최종 구현 상태 + 품질 유지·보수·리팩토링·리뷰·품질 게이트·검수·발전까지 포함한 **절대 기준 문서**  
> **상태:** MVP Tickets 1–5 완료를 전제로, **품질 시스템 레이어(게이트/검수/평가 하네스)** 를 SSOT에 포함

---

## 0. 변경 요약 (2.1 → 2.1.1)
이 문서는 기존 2.1 스펙의 핵심을 유지하되, “운영/유지보수 관점에서 빠지기 쉬운 것”을 SSOT에 **명시적으로 추가**했습니다.

- **Action Gates를 ‘명세 가능한 체크리스트’로 고정** (무엇을 어떻게 검사하는지)
- **상태 머신(State Machine)** 추가 → 멱등/재처리/복구가 설계로 보장
- **LLM 출력 계약(JSON Schema) + 프롬프트 버전 관리** 추가 → 리팩토링/모델 교체 시 회귀를 통제
- **Review Queue(HITL) 규격** 추가 → “보류/격리/재시도”가 자산으로 남음
- **데이터 아티팩트(인덱스/리포트/로그) 스키마** 명시 → 감사/디버깅/분석이 쉬움
- **Reset 안전장치/백업 정책** 명시

---

## 1. 프로젝트 한 줄 요약
로컬에서 자동으로 **논문 후보 수집 → 계층적 슬롯 판정(HierPrompt) → 하이브리드 태깅 → 품질 검증(Action Gates) → PDF 확보(OA/수동) → Obsidian/Zotero 연동**을 수행하는 자율 연구 파트너.

---

## 2. 환경 및 제약 (Strict Constraints)
- **실행 환경:** 로컬 사용자 PC (Python 3.10+).
- **Zotero:** **DB 직접 쓰기 절대 금지.** `storage/export/`에 `.ris` 생성 → 사용자가 Import.
- **PDF 정책:** Unpaywall OA만 자동 다운로드. 실패 시 `pdf_missing` 태그 후 진행(Fail-safe).
- **설정:** 쿼리/경로/임계값/모델/프롬프트는 `config.yaml`에서 관리.
- **데이터 보존:** `storage/state.db`(SQLite)로 중복 방지/처리 이력/재처리 기준 관리.
- **브라우저 자동화 최소화:** Selenium/Playwright 기반 스크래핑은 기본 비활성(필요 시 별도 Provider로 분리).
- **Fail-open:** 한 논문 실패가 전체 파이프라인 중단을 유발하지 않음(단, 실패는 반드시 기록).

---

## 3. 목표 (MVP Goals)
- **Daily Routine:** 슬롯(Mechanism/Clinical/Methods)별 Top-Pick 자동 처리.
- **On-Demand:** 사용자가 원할 때 키워드로 검색/수집/노트 생성.
- **Robustness:** 자동 품질 관리 (Confidence Gate, Retraction Gate, Gold Set Validation).
- **Maintainability:** 리팩토링/모델 교체/프롬프트 변경 시 회귀를 자동 감지할 수 있어야 함(Eval Harness).

---

## 4. 용어/정의 (Definitions)
- **Paper ID:** DOI 우선, 없으면 (PMID/ArXivID/TitleHash) 순으로 부여.
- **Hard Fields/Tags:** **문서에 존재하는 값만** 추출(추측 금지). 값 없으면 `unknown`.
- **Soft Tags:** LLM이 문맥 기반으로 부착(단, “확실성/근거” 필드로 관리).
- **Action Gate:** 단계별 자동 검증 규칙. 통과/보류/격리/재시도를 결정.
- **Review Queue:** Pending/Quarantine 항목의 사람 검수 워크플로우(카드화).

---

## 5. 핵심 방법론 (Methodology)

### 5.1 논문 선정: 계층적 프롬프트 (Hierarchical Prompting)
- **Slot A (Mechanism):**
  1) L1 Domain: Neuroscience/Cell Biology인가?  
  2) L2 Topic: Neurodegeneration(AD/PD) 관련인가?  
  3) L3 Specific: ASM/sphingolipid/autophagy/lysosome/microglia/neuroinflammation 핵심인가?

> **필수:** L1→L3 각 단계에 **근거 문장(evidence snippet)** 1개 이상을 저장한다.

### 5.2 태깅: 하이브리드 전략 (Hybrid Tagging)
- **Hard (Extraction):** Regex/Rule 기반으로 “값 + 단위 + 근거 문장”을 추출  
  - 예: `dose_value=20`, `dose_unit=g`, `dose_text="20 g/day"`, `evidence="..."`  
- **Soft (Generation):** 상위 개념/주제 태그를 생성  
  - 예: `#Autophagy`, `#Neuroinflammation`

> **권장:** Soft Tag는 `soft_tag_confidence(0~1)`와 `soft_tag_rationale(1줄)`를 함께 저장.

### 5.3 품질 관리: Action Gates & Escalation (MVP 핵심)
Action Gate는 “검증 규칙”이므로 **명세 가능한 체크리스트**여야 한다.

#### Gate 1) Confidence Gate (LLM 출력 신뢰도)
- High(>0.9): **APPROVED**
- Medium(0.7~0.9): **PENDING_REVIEW**
- Low(<0.7): **QUARANTINED**

#### Gate 2) Schema Gate (구조화 출력 계약)
- LLM 출력은 반드시 JSON(또는 pydantic 모델)로 파싱되어야 함.
- 파싱 실패 → 1회 재시도(프롬프트/temperature 낮춤) 후 실패 시 `PENDING_REVIEW`.

#### Gate 3) Evidence Gate (근거 포인터)
- 아래 산출물에는 근거가 **필수**:
  - 슬롯 배정 근거
  - triage 요약의 핵심 주장 1~3개
  - Soft Tag 부착 이유(최소 1줄)
- 근거 누락 시 → `PENDING_REVIEW`.

#### Gate 4) Retraction Gate (철회/우려 논문)
- 철회/표현의 변경(Concern) 가능성 신호가 있으면 **즉시 QUARANTINED**.
- `retraction_reason`, `retraction_source`, `checked_at`을 저장한다.
- ※ “정확히 어떤 DB/엔드포인트를 쓰는지”는 구현 시점에 확정하여 SSOT에 링크로 고정(불명확하면 운영 리스크).

#### Escalation (재심사)
- Medium 중 “중요도 높음”(slot 우선순위/키워드 매칭/최근성 등) 항목은 **Judge 모델**로 1회 재평가 가능.
- 승격되면 `approved_by=judge`, `judge_confidence`, `judge_rationale` 기록.

---

## 6. 상태 머신 (State Machine — 멱등/재처리/복구의 기반)
각 논문은 아래 상태를 가진다. 상태 전이는 `processor.py`에서만 수행한다(단일 진실).

- NEW → FETCHED → CLASSIFIED → TAGGED → GATED(Approved|Pending|Quarantined)
- 이후 분기:
  - Approved/Pending: PDF_ATTEMPTED → (PDF_DOWNLOADED | PDF_MISSING)
  - Quarantined: QUARANTINED_DONE
- 최종: EXPORTED(RIS) + NOTED(Obsidian) + INDEXED(CSV) → DONE

> **규칙:** DONE 상태 논문을 다시 처리할 때는 “업데이트”만 수행(중복 노트/태그 폭발 금지).

---

## 7. 아키텍처: Provider Pattern (Fetch Module)
- **Core:** `src/fetch/`
- **Factory:** `get_fetchers(config)`가 enable된 fetcher를 priority 순서로 반환
- **Provider Interface(권장):**
  - `search(query, since, limit) -> List[PaperStub]`
  - `fetch(paper_id) -> PaperRecord`
  - `rate_limit_policy`, `retry_policy`를 provider별로 가짐

---

## 8. 온디맨드 검색 (On-Demand Search)
- **CLI:** `paperpipe fetch --query "..." --save`
- **Namespace**
  - 노트: `Inbox/OnDemand/`
  - 인덱스: `00_Index/on_demand.csv`
  - 업로드(옵션): `NotebookLM_Upload/OnDemand/`
- **로직:** 슬롯/날짜 제약 없이 처리하되, 동일 Gate/상태 머신 적용

---

## 9. 폴더 및 모듈 구조
```text
paperpipe/
├── cli.py
├── config.yaml
├── src/
│   ├── fetch/
│   ├── processor.py
│   ├── llm_provider.py
│   ├── gates.py             # (추가 권장) GateEngine: confidence/schema/evidence/retraction
│   ├── obsidian.py
│   ├── zotero.py
│   ├── retraction.py
│   ├── reporting.py
│   ├── watcher.py
│   └── audit_retractions.py
├── tests/
│   ├── gold_set/
│   ├── regression/          # (추가 권장) 노트 스냅샷/태그 회귀
│   └── verify_*.py
└── storage/
    ├── state.db
    ├── export/
    ├── logs/
    └── reports/
```

---

## 10. 데이터/산출물 스키마 (운영 품질의 핵심)

### 10.1 Master Index CSV (권장: storage/index/paper_collection.csv)
필수 컬럼(최소):
- `paper_id, doi, title, year, venue, source, slot`
- `status` (state machine)
- `confidence, gate_decision, gate_reason`
- `evidence_snippet`
- `pdf_status, pdf_path`
- `obsidian_path, ris_path`
- `processed_at, agent_version, prompt_version`

### 10.2 Review Queue (권장: storage/review_queue.csv)
- `paper_id, decision(pending/quarantine), reason, owner, created_at, resolved_at, resolution`

### 10.3 Logs/Reports
- `storage/logs/run_YYYYMMDD.log`
- `storage/reports/dod_YYYYMMDD.txt` (성공률/에러율/게이트 분포/철회 감지 수)

---

## 11. 지식 관리 (Obsidian & Zotero)

### 11.1 Obsidian Integration
Frontmatter 최소 표준:
```yaml
aliases: ["Title"]
tags: ["#Tag1", "#Tag2"]
status: "To Read"
slot: "Mechanism"
paper_id: "DOI:..."
confidence: 0.82
gate: "PENDING_REVIEW"
evidence: "..."
agent_version: "2.1.1"
prompt_version: "triage.v3"
```

- **Smart Linking:** 태그/슬롯 유사도 + (옵션) 임베딩 유사도 기반으로 `## Related Papers` 구성  
- **주의:** 링크 생성도 Gate 대상(불필요한 링크 폭발 방지)

### 11.2 Zotero Integration (.ris)
- AB(초록) 포함
- KW(태그) 포함
- L1(링크)에 PDF/노트 경로 포함(경로 표준화 필요)

---

## 12. CLI 명령어 (Usage)
- `doctor`: 의존성/경로/권한 점검
- `run`: Daily Routine
- `fetch`: On-Demand
- `watch`: PDF Watch Folder
- `reset`: **안전장치 필수**(백업 생성 + 2중 확인)
- `test-fetch`: Provider 연결 테스트
- (권장) `qa`: review_queue를 열람/해결/재처리

---

## 13. 검증 및 품질 지표 (Validation)
- **Gold Set Validator:** `gold_standard.csv`와 비교해 F1 계산
- **Regression Harness(권장):**
  - 노트 템플릿 스냅샷 테스트
  - 태그/슬롯 판정 회귀 테스트
- **SLA/DoD Report:** 성공률, 에러율, gate 분포, 철회 논문 감지 수

---

## 14. 운영 규칙 (Operational Rules)
- SSOT 우선: 코드가 문서와 다르면 코드 수정
- Fail-safe: 실패는 멈춤이 아니라 “기록 + 분기”
- 보수적 파일 작업: 덮어쓰기/삭제는 백업 후 진행
- 프롬프트/모델 변경 시: 골드셋 회귀 통과가 “배포 조건”

---

## 부록: config.example.yaml (요지)
```yaml
search:
  slots:
    mechanism:
      query: '(ASM OR "acid sphingomyelinase" OR sphingolipid OR ceramide OR autophagy OR lysosome) AND (microglia OR HMGB1 OR neuroinflammation)'
    clinical:
      query: '(MCI OR "Mild Cognitive Impairment") AND (MCT OR "Medium-chain triglyceride" OR ketone OR "ketogenic diet")'
    methods:
      query: '"Cre-ER" OR "Cre-loxP" OR tamoxifen OR genotyping OR "recombination efficiency"'

quality:
  confidence:
    high: 0.90
    low: 0.70
  escalation:
    enabled: true
    judge_model: "..."
  evidence_gate:
    enabled: true
    require_for: ["slot_decision", "triage_claims", "soft_tags"]
```

---
