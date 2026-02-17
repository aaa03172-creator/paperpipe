[FOR CODEX — IMPLEMENTER]
Project: PaperPipe v3.0 — Casebook-Driven Dev Packet
Date: 2026-02-17 (KST)

너의 목표는 아래 “바인딩 원문(부록 A/B/C)”을 근거로,
레포에서 실제 엔트리포인트/모듈을 찾아 PR 단위로 구현+테스트까지 완료하는 것이다.
(설계/정책 확정은 Antigravity가 담당한다. 너는 구현/테스트/회귀 고정이 핵심이다.)

[절대 규칙]
- 원문 바인딩(부록 A/B/C)의 텍스트/수치/상태/정책을 임의로 변경하지 마라.
- 불확실하면 “확실하지 않음/추가 확인 필요”로 올리고, 대신 확인해야 할 파일/키워드/SQL을 제시하라.
- 모든 변경은 PR 단위로, 반드시 회귀 fixture/단위테스트를 포함하라.
- FAIL-safe 유지: 개별 논문 실패가 배치를 멈추지 않아야 한다.

[너의 즉시 행동(레포 탐색부터)]
1) 레포에서 다음 키워드로 위치를 확정하라:
   - Gatekeeper approve(Y/N) 처리: "APPROVE", "PENDING_REVIEW", "QUARANTINE", "Y/N", "gatekeeper card"
   - state.db 업데이트: "state.db", "sqlite", "INDEXED", "FAILED", "PENDING_REVIEW"
   - human_decisions.jsonl 기록: "human_decisions", ".jsonl"
   - JSON 파싱/복구: "json", "parse", "repair", "trailing", "brace", "extract_json", "chatty"
2) 발견한 파일/모듈/엔트리포인트를 목록화하고(경로 포함), 현재 동작을 한 줄 요약하라.
3) 아래 PR#1~#3를 순서대로 구현하라(각 PR은 테스트 포함):
   - PR#1: 상태/용어 매핑 + 스키마/문서/로그 통일(최소 변경, 마이그레이션 필요 시 포함)
   - PR#2: hansson JSON repair harness + fixture + 단위테스트(회귀 고정)
   - PR#3: approve(Y/N) 결정이 state.db에 반영되는 reconcile 경로 문서화/구현(없으면 추가)

[너의 출력 형식 — 반드시 이 순서로]
A) 레포 탐색 결과
   - 파일/모듈/엔트리포인트 목록(경로)
   - 사용한 검색 키워드(예: rg 패턴)
   - 각 항목의 현재 역할(1줄)
B) PR 계획서(3개)
   - PR 제목
   - Scope(변경 파일)
   - Implementation Plan(단계)
   - Acceptance Criteria(테스트로 검증 가능한 문장)
   - Rollback Plan
C) 테스트/검증 커맨드
   - pytest/스크립트 실행
   - fixture 생성/실행
   - state.db 검증(SQL 포함)
   - human_decisions.jsonl 검증

============================================================
[APPENDIX A] 원문 입력(바인딩): PaperPipe_Handover_Casebook_Updated.md (verbatim)
============================================================
# PaperPipe 인수인계 문서 (Handover) — 최신 사례 모음 포함
마지막 업데이트: **2026-02-17 12:30 (KST)**
대상: **논문 에이전트(PaperPipe)** / 개발·운영(Antigravity 중심, Codex 하이브리드 옵션)

---

## 0) 지금 상태 요약 (운영 스냅샷)
- **Backlog 처리/Flush 완료**: NEW backlog 없음
- **DB 총 논문 수**: 53편 (최근 로그 기준)
- **현재 상태(최근 의사결정 반영 후)**
  - **INDEXED**: 51 *(Flush 후 50 + grande 승인 1)*
  - **PENDING_REVIEW**: 1 *(dubois 보류)*
  - **FAILED**: 1 *(hansson JSON 파싱 실패)*
- **Gatekeeper 의사결정 로그**: `storage/human_decisions.jsonl`에 기록됨
  - grande → INDEXED 승인
  - dubois → PENDING_REVIEW 유지(HELD)

> 주의: 숫자는 “마지막 실행 로그” 기준이며, 이후 추가 실행이 있었다면 `storage/state.db`가 소스 오브 트루스.

---

## 1) 목표(프로젝트 목적)
PaperPipe는 로컬에서 다음을 자동 수행하는 **자율 연구 파트너 파이프라인**이다.
- 논문 후보 수집 → 슬롯 판정(HierPrompt) → 하이브리드 태깅(Hard/Soft) → 품질 검증(Action Gates)
→ PDF 확보(OA/수동) → Obsidian 노트 생성/링킹 → Zotero RIS export → NotebookLM 업로드 폴더 준비

핵심 철학
- **Fail-safe / Continue-on-error**: 개별 논문 실패가 전체 배치를 멈추지 않음
- **unknown/uncertain 허용**: “모름”은 정상 값(추측 금지)
- **근거 우선(evidence)**: 판단에는 근거 스니펫/포인터를 남겨 사람 검수 가능하게

---

## 2) 현재 구현(또는 합의)된 핵심 설계
### 2.1 로컬/보안 제약
- **Zotero DB 직접 Write 금지**: `.ris` 생성 → 사용자가 Zotero Import
- **PDF 정책**: 유료 저널 자동 다운로드를 목표로 하지 않음
  - **Unpaywall로 OA 링크가 있을 때만** 다운로드 시도
  - 실패 시 `pdf_missing` + **Watch Folder(Inbox)로 수동 보완**

### 2.2 슬롯 기반 Top Picks (예시)
- Slot A: Mechanism/Lab Anchor (PubMed 1편 고정)
- Slot B: Clinical/Translation (PubMed 우선 1편)
- Slot C: Methods/Practical (1편)
> 실제 Slot 정의/쿼리는 **config.yaml**에서 변경 가능하도록 설계(하드코딩 금지)

### 2.3 Action Gates (운영 합의)
- Confidence Gate 예:
  - High(>0.9): APPROVE
  - Medium(0.7~0.9): PENDING_REVIEW
  - Low(<0.7): QUARANTINE
- Retraction Check: 철회/우려 신호가 있으면 QUARANTINED (세부 데이터 소스/룰은 구현에 따라 명시 필요)
- 결과는 DB 상태 + 로그 + Review Queue로 남겨 HITL 루프를 가능하게 함

---

## 3) 다음 우선순위(가장 중요한 To-do)
### P0 (즉시): Pending/Failed 해결로 “완전 clean” 만들기
1) **dubois Minimal Evidence Expansion**
2) **hansson JSON parsing repair harness**

### P1 (품질/유지보수): Quality OS 도입
- GateEngine 모듈화(`gates.py`) + reason_code 표준화
- Regression harness(골드셋) + PR/merge gate(회귀 통과 조건)
- Observability: JSONL 로그 표준 + run report(성공률/게이트 분포/비용/시간)

### P2 (확장): 하이브리드 개발 체계 고도화
- **Antigravity**: 로컬 실행·운영 디버깅 중심(실 데이터 검증)
- **Codex**: 리팩토링/테스트/리뷰/품질 게이트 자동화 중심(브랜치/PR 기반)

---

## 7) 다음 액션(체크리스트)
- [ ] dubois Minimal Evidence Expansion 실행 → Gatekeeper 승인 여부 결정
- [ ] hansson JSON repair harness 제작(실패 분류 + 회귀 fixture)
- [ ] GateEngine 모듈화 + reason_code 표준화 + PR 품질 게이트
- [ ] 골드셋 최소 30 케이스 구축 + 자동 회귀 실행
- [ ] Dev Container 도입(선택): 환경 재현성 확보

[문서 끝]

============================================================
[APPENDIX B] 원문 입력(바인딩): 최신 Gatekeeper Card (verbatim)
============================================================
GATEKEEPER CARD: duboisAmnesticMCIProdromal2004

Status: PENDING_REVIEW (Current)
Title: Amnestic MCI or prodromal Alzheimer's disease?
Venue: The Lancet Neurology

HARD TAGS:
sample_size: None (Review)
study_type: Review/Proposal
population: Human
design: Consensus/Guidelines

SOFT TAGS (Top 3):
#AlzheimersDisease/Prodromal (Conf: 0.95)
#MildCognitiveImpairment
#Diagnosis/Criteria (Conf: 0.9)

EVIDENCE SNIPPETS:
[Abstract] "We propose a set of diagnostic criteria for 'prodromal Alzheimer'..." -> Study Type: Review/Criteria
[Introduction] "MCI is a heterogeneous entity... new criteria include memory..." -> #DiagnosticCriteria
[Discussion] "Specific biomarkers (CSF, MRI) are required to increase spec..." -> #Biomarkers

CONFIDENCE: 0.94 (Meta: 1.0, Hard: 0.8, Evidence: 1.0)
RECOMMENDATION: APPROVED
APPROVE duboisAmnesticMCIProdromal2004? (Y/N)

============================================================
[APPENDIX C] 외부 레퍼런스 링크(참고용; 구현 요구사항 아님)
============================================================
- microgpt gist: https://gist.github.com/karpathy/8627fe009c40f57531cb18360106ce95
- microgpt 설명(karpathy blog): https://karpathy.github.io/2026/02/12/microgpt/
- OpenAI “Scaling social science research” (GABRIEL): https://openai.com/index/scaling-social-science-research/
- Beaver (Zotero AI): https://www.beaverapp.ai/
============================================================
END (CODEX PACKET)
