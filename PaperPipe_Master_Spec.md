# PaperPipe — Antigravity 개발용 마스터 명세서 (Single Source of Truth)

> **문서 버전:** 2.0 (Antigravity Edition)
> **목적:** PaperPipe를 점진적으로 구현하기 위한 절대 기준 문서.
> **핵심 변경점:** `논문 자동 태깅 및 분류 방법론`의 기법(HierPrompt, Hybrid Tagging, Section Chunking) 반영.

---

## 0. 프로젝트 한 줄 요약
로컬에서 자동으로 **논문 후보 수집 → 계층적 슬롯 판정(HierPrompt) → 하이브리드 태깅 → PDF 확보(OA/수동) → Obsidian/Zotero 연동**을 수행하는 자율 연구 파트너.

---

## 1. 환경 및 제약 (Strict Constraints)
- **실행 환경:** 로컬 사용자 PC (Python 3.10+).
- **Zotero:** **DB 직접 쓰기 절대 금지**. `export/` 폴더에 `.ris` 파일 생성 방식 사용.
- **PDF 정책:** Unpaywall API로 OA만 자동 다운로드. 실패 시 `pdf_missing` 태그 후 진행(Fail-safe).
- **설정:** 모든 변수(쿼리, 경로 등)는 `config.yaml`에서 관리.

---

## 2. 목표 (MVP)
- **완료 조건:** `paperpipe run` 실행 시,
  1. 수집(PubMed)
  2. 계층적 분류(Slot A/B/C)
  3. 태깅(Extraction/Generation)
  4. Obsidian 노트 생성 & Zotero 내보내기
  이 과정이 **하루치라도 에러 없이 End-to-End로 작동**하는 것.

---

## [cite_start]3. 핵심 방법론 (Methodology) [cite: 36, 46, 68]

### 3.1 논문 선정: 계층적 프롬프트 (Hierarchical Prompting)
단순 질문 대신 단계별 질문으로 정확도를 높인다.
- **Slot A (Mechanism):**
  1. **L1 (Domain):** Neuroscience/Cell Biology인가?
  2. **L2 (Topic):** Neurodegeneration (AD/PD) 관련인가?
  3. **L3 (Specific):** `ASM`, `sphingolipid`, `autophagy` 등이 핵심인가?

### 3.2 태깅: 하이브리드 전략 (Hybrid Tagging)
- **Hard Fields (Extraction):** 본문에 있는 단어/수치만 추출 (KeyBERT/Regex).
  - 예: `tamoxifen_dose`, `sample_size`, `model_species`
- **Soft Tags (Generation):** LLM이 맥락을 통해 생성.
  - 예: `#topic/autophagy`, `#trend/prevention`

### 3.3 청킹 (Chunking)
- 초록이나 본문을 통으로 넣지 않고 **Section-level Chunking** (Intro / Methods / Results)을 수행하여 요약 품질 향상.

---

## 4. 폴더 및 모듈 구조
```text
paperpipe/
├── cli.py              # 진입점
├── config.py           # 설정 로더
├── pipeline/
│   ├── harvest.py      # 수집
│   ├── classify.py     # 지능 (HierPrompt)
│   ├── tagging.py      # 태깅 (Hybrid)
│   └── process.py      # 청킹
└── storage/
    ├── notes.py        # Obsidian 생성
    └── export.py       # Zotero .ris 생성
```

## 5. 태깅 및 분류 설계 (Tagging & Taxonomy Design)

### 5.1. 계층적 분류 (Hierarchical Tags) - **Obsidian Compatible**
- **Format**: `#Category/Subcategory` (Note the `/` separator and `#` prefix)
- **Rules**: 
    - **No Spaces**: Use `CamelCase` or `snake_case` (e.g., `#ClinicalTrial`, `#Neurology_Neuroscience`).
    - **No Special Chars**: Avoid `>`, `&`, etc. Use `/` for hierarchy.
- **Example**: 
    - `#Medicine/Neurology`
    - `#LifeScience/CellBiology`

### 5.2. 키워드 태그 (Keyword Tags / Soft Tags)
- **Format**: `#Keyword`
- **Source**: **MeSH Terms** (Medical Subject Headings) preferred.
- **Context Rule**: **Avoid duplicating Title words**.
- **Example**:
    - `#Autophagy`
    - `#AlzheimersDisease` (No apostrophe, no space)
    - `#DietaryFats`

### 5.3 키워드 생성 규칙 (Keyword Rules)
1. **MeSH 용어 사용:** 가능한 한 MeSH(의학주제표제) 통제 어휘를 우선 사용.
2. **제목 중복 방지:** 제목에 이미 포함된 단어는 키워드로 반복하지 않음. (제목에 없는 맥락 추가)
3. **구체성:** `Cancer` 대신 `Breast Cancer Genomics` 같이 구체적으로 작성.

---

## 6. 구현 티켓 (MVP)
Ticket 1: 환경 설정, 로깅, config.yaml 로더 구현.

Ticket 2: PubMed 수집기 & Config 기반 쿼리 구현.

Ticket 3: 지능형 분류기 (HierPrompt + Hybrid Tagging).

Ticket 4: PDF 처리 (Unpaywall) & Watch Folder 로직.

Ticket 5: 산출물 생성 (Obsidian MD, Zotero RIS).