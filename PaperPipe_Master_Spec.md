# PaperPipe — Antigravity 개발용 마스터 명세서 (Single Source of Truth)

> **문서 버전:** 2.1 (Final MVP Edition)
> **목적:** PaperPipe 시스템의 최종 구현 상태와 아키텍처를 정의하는 기준 문서.
> **상태:** MVP 구현 완료 및 검증됨 (Tickets 1-5 Complete).

---

## 0. 프로젝트 한 줄 요약
로컬에서 자동으로 **논문 후보 수집 → 계층적 슬롯 판정(HierPrompt) → 하이브리드 태깅 → 품질 검증(Action Gates) → PDF 확보(OA/수동) → Obsidian/Zotero 연동**을 수행하는 자율 연구 파트너.

---

## 1. 환경 및 제약 (Strict Constraints)
- **실행 환경:** 로컬 사용자 PC (Python 3.10+).
- **Zotero:** **DB 직접 쓰기 절대 금지**. `export/` 폴더에 `.ris` 파일 생성 방식 사용.
- **PDF 정책:** Unpaywall API로 OA만 자동 다운로드. 실패 시 `pdf_missing` 태그 후 진행(Fail-safe).
- **설정:** 모든 변수(쿼리, 경로, 임계값, 프롬프트)는 `config.yaml`에서 관리.
- **데이터 보존:** `state.db` (SQLite)로 중복 방지, 처리 이력 관리.

---

## 2. 목표 (MVP Goals)
- **Daily Routine:** 매일 지정된 슬롯(Mechanism, Clinical, Methods) 별 Top-Pick 논문 자동 처리.
- **On-Demand:** 사용자가 원할 때 즉시 키워드로 검색/수집/노트생성.
- **Robustness:** 자동화된 품질 관리 (Retraction Check, Confidence Check, Gold Set Validation).

---

## 3. 핵심 방법론 (Methodology)

### 3.1 논문 선정: 계층적 프롬프트 (Hierarchical Prompting)
단순 질문 대신 단계별 질문으로 정확도를 높인다.
- **Slot A (Mechanism):**
  1. **L1 (Domain):** Neuroscience/Cell Biology인가?
  2. **L2 (Topic):** Neurodegeneration (AD/PD) 관련인가?
  3. **L3 (Specific)::** `ASM`, `sphingolipid`, `autophagy` 등이 핵심인가?

### 3.2 태깅: 하이브리드 전략 (Hybrid Tagging)
- **Hard Tags (Extraction):** 본문에 있는 단어/수치만 추출 (Regex/Rule-based).
  - 예: `dose:20g`, `sample_size:150`, `model:mouse`
- **Soft Tags (Generation):** LLM이 맥락을 통해 생성 (MeSH Term 기반).
  - 예: `#Autophagy`, `#Neuroinflammation`, `#KetogenicDiet`

### 3.3 품질 관리: Action Gates & Escalation
LLM의 환각을 방지하고 신뢰도를 보장하기 위한 3단계 검증.
1. **Confidence Check:**
   - **High (>0.9):** Auto-Approve (자동 통과).
   - **Low (<0.7):** Quarantine (격리 폴더로 이동).
   - **Medium (0.7~0.9):** Pending Review (검토 필요 태그 부착).
2. **Escalation (재심사):**
   - Medium 등급 논문 중 중요도가 높은 경우, 더 강력한 모델(Judge)이 재평가하여 Auto-Approve로 승격 가능.
3. **Retraction Watch:**
   - 모든 논문은 처리 전 Retraction Watch DB(Crossref)와 대조하여 철회된 논문인지 확인. 철회 시 즉시 격리(`QUARANTINED`).

### 3.4 아키텍처: Provider Pattern (Fetch Module)
확장성을 위해 수집 모듈을 플러그인 형태로 설계.
- **Core:** `src/fetch/` 패키지.
- **Factory:** `get_fetchers(config)`가 설정에 따라 활성화된 Fetcher 인스턴스 반환.
- **Source Config:** `config.yaml`의 `sources` 섹션에서 Provider별 Enable/Disable 및 Priority 제어.
- **Credentials:** API Key는 `credentials` 섹션 또는 환경변수로 관리.

### 3.5 온디맨드 검색 (On-Demand Search)
Daily Routine과 분리된 독립적인 검색/수집 파이프라인.
- **CLI:** `paperpipe fetch --query "..." --save`
- **Namespace:**
  - 노트: `Inbox/OnDemand/`
  - 인덱스: `00_Index/on_demand.csv`
  - 업로드: `NotebookLM_Upload/OnDemand/`
- **Logic:** 슬롯/날짜 제약 없이 쿼리 기반 수집 및 처리.

---

## 4. 폴더 및 모듈 구조
```text
paperpipe/
├── cli.py              # User Interface (Typer CLI)
├── config.yaml         # Central Configuration
├── src/                # Source Code
│   ├── fetch/          # [Provider Pattern] PubMed, ArXiv fetchers
│   ├── processor.py    # Main Orchestrator (Daily & On-Demand)
│   ├── llm_provider.py # LLM Inteface (Prompt, Tagging, Gates)
│   ├── obsidian.py     # Note Generation & Indexing
│   ├── zotero.py       # RIS Export
│   ├── retraction.py   # Retraction Watch Integration
│   ├── reporting.py    # Daily DoD Reporting
│   ├── watcher.py      # PDF Watch Folder Service
│   └── audit_retractions.py # Retraction Audit Script
├── tests/              # Validation
│   ├── gold_set/       # Gold Set Validation Logic
│   └── verify_*.py     # Unit/Integration Tests
└── storage/            # Data Storage
    ├── state.db        # Processing History
    └── export/         # RIS Files
```

---

## 5. 지식 관리 (Obsidian & Zotero)

### 5.1 Obsidian Integration
- **Frontmatter:**
  ```yaml
  aliases: ["Title"]
  tags: ["#Tag1", "#Tag2"]
  cssclasses: ["paper-note"]
  status: To Read
  slot: Mechanism
  ```
- **Smart Linking:** 새로운 논문 추가 시, 기존 논문들과 태그/슬롯 유사도를 분석하여 `## 🔗 Related Papers` 섹션에 자동 링크 생성.
- **Templates:** 연구 유형(Study vs Clinical Trial)에 따라 다른 템플릿 적용.

### 5.2 Zotero Integration
- **RIS Generation:**
  - **Abstract (`AB`)**: 포함.
  - **Keywords (`KW`)**: Hybrid Tags (Soft & Hard) 포함.
  - **Link (`L1`)**: 로컬 PDF 및 Obsidian 노트 링크 포함.

---

## 6. CLI 명령어 (Usage)

| Command | Description | Example |
| :--- | :--- | :--- |
| **`doctor`** | 환경 설정 및 의존성 점검 | `paperpipe doctor` |
| **`run`** | Daily Routine 실행 (설정된 슬롯 수집) | `paperpipe run` |
| **`fetch`** | 온디맨드 검색 (즉시 수집) | `paperpipe fetch -q "Key" --save` |
| **`watch`** | 폴더 감시 (PDF 자동 처리) | `paperpipe watch --path ./download` |
| **`reset`** | [주의] 데이터/로그 초기화 | `paperpipe reset` |
| **`test-fetch`** | 수집 모듈 연결 테스트 | `paperpipe test-fetch` |

---

## 7. 검증 및 품질 지표 (Validation)
- **Gold Set Validator:** 사용자가 구축한 정답셋(`gold_standard.csv`)과 시스템 출력을 비교하여 F1 Score 계산 (`tests/gold_set/validator.py`).
- **DoD Report:** 매일 실행 후 성공률, 에러율, 철회 논문 감지 수를 리포트 (`logs/sla_report_...txt`).

---

## 부록 A. config.example.yaml (Current Defaults)
```yaml
search:
  slots:
    mechanism:
      query: '(ASM OR "acid sphingomyelinase" OR sphingolipid OR ceramide OR autophagy OR lysosome) AND (microglia OR HMGB1 OR neuroinflammation)'
    clinical:
      query: '(MCI OR "Mild Cognitive Impairment") AND (MCT OR "Medium-chain triglyceride" OR ketone OR "ketogenic diet")'
    methods:
      query: '"Cre-ER" OR "Cre-loxP" OR tamoxifen OR genotyping OR "recombination efficiency"'
```

---

## 부록 D. Antigravity 운용 가이드 (Operational)
### D1. Single Agent vs Multi-Agent
- **Single/Pair Agent:** MVP 및 초기 개발 단계에서 권장. 컨텍스트 관리가 용이하고 디버깅이 쉬움.
- **Multi-Agent:** 대규모 확장이 필요할 때 도입 (Role-based separation). 메인 아키텍트 + 코더 + 테스터 구조 권장.

### D2. Prompt Principles
- **수도코드 우선:** 복잡한 로직은 말로 설명하기보다 수도코드(Pseudo-code)로 요청.
- **HTML Tables:** 데이터 분석 요청 시 테이블 포맷 사용 유도.

---

## 부록 E. Triage/Summary Template (Writing Style)
좋은 요약(Triage Note)의 4단계 구조:
1. **Context:** 세상은 지금 이런 문제/배경에 있다.
2. **Current State:** 기존 연구들은 이렇게 해결해왔다.
3. **The Gap (Crucial):** **하지만 결정적인 질문이 하나 남아 있다.**
4. **This Paper:** 이 논문은 그 질문을 다룬다.

> `llm_provider.py`의 프롬프트 작성 시 이 구조를 유도하도록 설계한다.

---

## 부록 G. Obsidian Knowledge Management Tips
### G1. Folder Naming (`10_ProjectA`)
- 숫자 접두어를 사용하여 폴더 정렬을 고정하고 검색 효율성을 높인다.
- PaperPipe는 `Inbox/` (임시) -> `10_Literature/` (영구) 이동 흐름을 지원하도록 설계.

### G2. Collection Note
- 단순 나열보다 "주제별 클러스터링" 노트 생성 권장.
- PaperPipe의 `00_Index/on_demand.csv`와 `Smart Linking` 기능이 이를 보조함.

---

## 부록 H. Reading Routine (Deep Read)
### H1. Deep Read Routine
1. **Main Figure:** 핵심 주장 1개 확인.
2. **Methods/Stats:** N수, 대조군, 통계 검증 확인 (서플리먼트).
3. **Impact:** 내 프로젝트 변수/가설에 주는 영향 1줄 정리.

---