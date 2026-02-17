[FOR CODEX — IMPLEMENTATION PACKET]
Title: PaperPipe — Local Biomedical Embedding Indexer + Obsidian/Zotero Linking (Strict, No-Guess)
Date: 2026-02-17 (KST)
Owner: Codex (Implementer)
Reviewer/Approver: Antigravity (Lead)

============================================================
0) HARD RULES (절대 위반 금지)
============================================================
R0. 본 패킷은 “바인딩 입력(원문)”을 포함한다. 원문(특히 DDL)은 임의 수정/축약/추론 금지.
R1. 기존 PaperPipe 철학/제약 준수:
  - Fail-safe / Continue-on-error
  - unknown/uncertain 허용(추측 금지)
  - evidence-first
  - Zotero DB 직접 write 금지(.ris 생성 후 사용자가 import)
  - paywall PDF 자동 다운로드 목표 금지(OA만)
R2. “모델/상태/용어” 충돌 가능 시 멈추고 Antigravity에 에스컬레이션:
  - 기존 Master Spec 또는 state machine과 충돌하면 코드를 임의로 바꾸지 말고 “충돌 지점”을 문서화한다.
R3. 모든 변경은 PR 단위이며, 최소 1개 이상의 자동 테스트(로컬) 포함이 필수.

============================================================
1) 목표 / 범위
============================================================
Goal A) SQLite(papers)에서 “인덱싱 대상”을 읽어 로컬 임베딩(sentence-transformers)으로 벡터화 후
        ChromaDB(Persistent) 컬렉션에 UPSERT한다.
Goal B) Obsidian 노트(frontmatter)에 PDF/Zotero 딥링크를 넣는 exporter 템플릿을 고도화한다.

Out of Scope:
- 외부 API 기반 클라우드 임베딩
- Zotero DB 직접 수정
- paywall PDF 다운로드 자동화
- “tags 컬럼 추가” 같은 스키마 변경(추후 PR로 별도 제안 가능)

============================================================
2) 결정 고정(Freeze) — 임의 변경 금지
============================================================
D1. 기본 임베딩 모델(1차 릴리즈 기본값):
  - NeuML/pubmedbert-base-embeddings (도메인 IR 우선, 로컬 ST 사용)
  - 단, 구현은 모델명을 옵션으로 받을 수 있어야 함(--model)

D2. Chroma 컬렉션 메트릭:
  - cosine (hnsw:space="cosine")
  - 메트릭 변경은 “새 컬렉션 생성”으로만 처리(기존 컬렉션 메트릭 변경 금지)

D3. 재인덱싱 정책:
  - 모델/메트릭이 바뀌면 반드시 “새 컬렉션 이름”을 사용한다.
  - 컬렉션 네이밍 규칙(고정):
    paper_pipe_bio__{model_slug}__v{N}
    예: paper_pipe_bio__neuml_pubmedbert_base_embeddings__v1

D4. 인덱싱 대상 선택 정책(고정):
  - 기본: gate_decision='APPROVED' 인 논문만
  - 호환 fallback: status IN ('APPROVED','INDEXED') 포함(있을 경우)
  - 위 규칙을 코드로 명시하고 옵션(--all)로 전체 인덱싱 가능하게

D5. “tags 결합 임베딩” 전략의 현실 제약(고정):
  - 현재 스키마에 tags 컬럼/테이블이 없다.
  - 따라서 tags는 “feedback_json 안에 존재할 때만” best-effort로 추출한다.
  - tags를 환각/추론으로 생성 금지(없으면 빈 리스트).

============================================================
3) 구현 요구사항 — src/indexer.py
============================================================
3.1 파일/CLI 요구사항
- 경로: src/indexer.py
- 실행:
  - python -m src.indexer --db ./storage/state.db index
  - python -m src.indexer --db ./storage/state.db search "query" --k 5
- 옵션:
  --db (필수) SQLite DB path
  --chroma (기본 ./storage/vector_db)
  --collection (미지정 시 자동 생성: 규칙 D3 적용)
  --model (기본 D1)
  index 서브커맨드:
    --all (승인 필터 무시)
  search 서브커맨드:
    --k (기본 5)

3.2 인덱싱 입력 텍스트 구성(고정)
- 문서(doc) 구성(순서 권장):
  1) summary(있으면) / 없으면 title + evidence_snippet
  2) Tags: ... (feedback_json에서 추출된 경우에만)
  3) Meta: slot, venue, gate_reason, evidence_snippet(최대 500자)
- 금지: 없는 정보를 요약으로 생성(환각)하거나 tags를 새로 만들기

3.3 메타데이터 저장(Chroma metadatas)
- 필수 키:
  paper_id, title, year, venue, slot, status, gate_decision, doi
  embedding_model, collection_name, indexed_at(UTC ISO)
  tags_count
- 목적: 추후 디버깅/재인덱싱 추적

3.4 Upsert/Idempotency
- 같은 paper_id 재실행 시 중복 없이 갱신되어야 함
- Chroma collection에 upsert가 있으면 사용, 없으면 delete+add fallback

3.5 normalize_embeddings
- SentenceTransformer.encode 호출 시 normalize_embeddings=True 적용(기본)
- 단, 모델 호환 문제 발생 시 테스트에서 즉시 드러나야 함(조용히 꺼버리지 말 것)

============================================================
4) 구현 요구사항 — src/exporter.py (딥링크)
============================================================
목표: Obsidian 노트 frontmatter에 아래를 안전하게 포함.
- Zotero item deep link: zotero://select/library/items/{zotero_key}
- (가능하면) Zotero PDF open link: zotero://open-pdf/library/items/{zotero_key}?page={page}
- 로컬 PDF 링크(옵션):
  - 파일이 vault attachment로 연결 가능하면 [[paper.pdf]]
  - 아니면 file:///absolute/path/to/paper.pdf

규칙:
- zotero_key가 없으면 Zotero 링크 섹션을 만들지 않는다(빈 링크 금지).
- pdf_path가 없으면 PDF 링크 섹션을 만들지 않는다.
- page/annotation 같은 세부 파라미터는 “DB에 실제 필드가 있을 때만” 넣는다(현재 스키마에는 없음).

산출물:
- exporter 템플릿(또는 생성 함수) 1개
- 생성된 md 파일 예시 1개(테스트 fixture로도 사용 가능)

============================================================
5) 테스트 요구사항(필수)
============================================================
PR에 최소 아래 테스트 포함.

T1. SQLite fixture 생성 테스트
- 임시 sqlite db 생성
- [APPENDIX A]의 DDL로 테이블 생성
- papers에 샘플 row 2개 삽입:
  - approved row: gate_decision='APPROVED', summary 있음, feedback_json에 tags/soft_tags 케이스 포함
  - non-approved row: gate_decision='PENDING_REVIEW'
- index 실행 후:
  - Chroma 컬렉션에 approved row만 존재 (기본 모드)
  - --all이면 둘 다 존재

T2. Idempotent upsert 테스트
- 같은 DB로 index를 2번 실행
- Chroma에 동일 id가 1개만 유지되고 metadata/indexed_at이 갱신(또는 update 호출됨)

T3. search smoke test
- query로 search 호출 시 결과 구조(ids/metadatas/documents)가 비어있지 않음(approved가 있을 때)

T4. exporter 템플릿 테스트(최소)
- zotero_key 있을 때: frontmatter에 zotero://select... 포함
- pdf_path 있을 때: PDF 링크 포함
- 없을 때: 해당 섹션이 생성되지 않음

============================================================
6) PR 단위 작업 분해(고정)
============================================================
PR#1: src/indexer.py + tests (T1~T3)
PR#2: src/exporter.py 딥링크 고도화 + tests (T4)
PR#3(옵션/후속): tags 정규화를 위한 paper_tags 테이블 제안서(코드X, 문서/이슈 only)

============================================================
7) “확실하지 않음” 처리 규칙
============================================================
- 레포에 기존 indexer/exporter 구현이 있으면:
  - 기존 엔트리포인트를 유지하며 최소 변경으로 기능 추가
  - 충돌 나는 정책/상태 값은 “명확한 근거(파일/라인)”를 첨부해 Antigravity에 질문(코드로 임의 해결 금지)

============================================================
[APPENDIX A] 바인딩 입력 — SQLite DDL (verbatim, DO NOT MODIFY)
============================================================
CREATE TABLE papers (
    paper_id TEXT PRIMARY KEY,
    doi TEXT,
    title TEXT NOT NULL,
    year INTEGER,
    venue TEXT,
    source TEXT,
    slot TEXT,
    status TEXT NOT NULL DEFAULT 'NEW',
    confidence REAL,
    gate_decision TEXT,
    gate_reason TEXT,
    evidence_snippet TEXT,
    pdf_status TEXT,
    pdf_path TEXT,
    obsidian_path TEXT,
    ris_path TEXT,
    feedback_json TEXT,
    agent_version TEXT,
    prompt_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
, summary TEXT);
CREATE INDEX idx_papers_status ON papers(status);
CREATE INDEX idx_papers_slot ON papers(slot);
CREATE INDEX idx_papers_doi ON papers(doi);
CREATE TABLE review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT,
    owner TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution TEXT,
    FOREIGN KEY(paper_id) REFERENCES papers(paper_id)
);

============================================================
[APPENDIX B] 바인딩 입력 — 필요한 상태/필드 의미(요약, DO NOT INVENT)
============================================================
- status: 파이프라인 단계(NEW, FETCHED, CLASSIFIED, GATED, APPROVED 등)
- gate_decision: 게이트 결과(APPROVED, PENDING_REVIEW, QUARANTINED)
- 인덱싱 대상 기본: gate_decision='APPROVED' (fallback: status APPROVED/INDEXED)

============================================================
END OF PACKET
