# Lattice v3.0 Master Spec (Final Blueprint)
부제: **지식의 구조화를 위한 자율 진화형 통합 연구 시스템** — 로컬 LLM(Ollama) + effGen + FastAPI + Obsidian

> 이 문서는 사용자가 작성한 “[PaperPipe v3.0] Final Blueprint”를 **구현 가능한 마스터 스펙**으로 재정리한 버전입니다.  
> 목표는 “Antigravity(코딩 에이전트)에게 그대로 전달해도 흔들리지 않게” **계약(스키마/상태머신/API/DoD)** 을 명확히 하는 것입니다.
> 제품 공식 명칭은 **Lattice**이며, 코드/패키지 경로의 `paperpipe` 표기는 하위 호환(legacy namespace)으로 유지합니다.

---

## 0. 설계 원칙 (Non‑negotiables)

### 0.1 핵심 철학
1) **API‑First & UI‑Agnostic**  
- 코어 로직은 **FastAPI 기반 REST**로 감싼다. UI/CLI는 교체 가능해야 한다.

2) **Zero Hard‑coding (도메인 규칙 외부화)**  
- 도메인 지시사항(페르소나/판단 기준/예시)은 **YAML**로 외부화한다.  
- 단, **출력 스키마(계약)** / **보안 정책** / **상태머신** / **에러코드**는 **불변 계약**으로 코드에 고정한다. (재현성과 안정성 우선)

3) **Self‑Evolution (HITL + 동적 few‑shot)**  
- UI에서 교정된 피드백은 DB에 저장하고, 실행 시 **유사 성공 사례 Top‑K(기본 3)** 만 동적으로 주입한다.  
- YAML에 무한 Append 금지(토큰/잡음 방지).

---

## 1. 시스템 개요 (Project Overview)

### 1.1 End‑to‑End 범위
논문 수집 → PDF 파싱/표 추출 → 임베딩 인덱싱 → 심층 읽기(ClaimSet) → 통계 검증(PythonREPL) → 결과물(Artifact) 저장 → Obsidian 반영 → UI에서 교정/피드백 저장.

### 1.2 “유일한 저장소” 선언
- **Zotero(DB Layer)**: PDF 원문 및 메타데이터의 유일한 원본(SoT)  
- **Obsidian(Knowledge Layer)**: 검증된 결과물(Artifact)의 영구 지식화(SoK)

### 1.3 명칭 정책 (Brand Contract)
- 사용자 노출(UI/문서/로그 라벨)의 제품명은 `Lattice`를 사용한다.
- 코드 경로/CLI의 하위 호환 명령(`paperpipe`)은 유지하고, 동등 alias(`lattice`)를 제공한다.
- 대외 문서에서 `PaperPipe`가 등장하면 `legacy` 맥락임을 명시한다.

---

## 2. 5‑Tier Decoupled Architecture

### 2.1 레이어 정의
1) **DB Layer: Zotero**  
- Better BibTeX 기반 **CSL‑JSON export**를 `storage/zotero_export.json` 로 동기화  
- PDF 첨부 경로 포함

2) **Core API Layer: FastAPI (backend/)**  
- Zotero export 로더  
- Job 생성/상태 조회/취소  
- SSE 이벤트 스트림 제공  
- Artifact 조회/피드백 저장/Obsidian 반영 트리거

3) **Engine Layer: Lattice Engine (legacy package: PaperPipe + effGen) (src/)**  
- Ingest → Index → Read → Verify 워커  
- Ollama adapter로 로컬 LLM 호출  
- (옵션) effGen tool-use 기반 에이전트

4) **Control Layer: Web UI (frontend/)**  
- 논문 목록/상태 표시  
- 페르소나 선택/실행/모니터링  
- JSON Artifact 시각화/교정 입력(HITL)

5) **Knowledge Layer: Obsidian**  
- `{CiteKey}.md` 생성/업데이트(idempotent)  
- Related papers 링크/근거/요약/검증 결과 보존

### 2.2 Runtime Launcher Contract (필수)
- 런처 명령은 아래 2개를 **동일 동작**으로 보장한다.
  - `paperpipe start`
  - `lattice start`
- 런처 성공 조건:
  - 프로세스 기동 후 `GET /health`가 `200`으로 응답
  - 기본 타임아웃 내(권장 15초) 헬스체크 통과 실패 시 non-zero exit
- 런처 실패 조건:
  - 포트 충돌, 설정 로드 실패, DB bootstrap 실패 시 즉시 non-zero exit
- 런처 회귀 테스트:
  - 최소 `tests/test_cli_start_command.py`에서 명령 진입점/헬스체크/실패 코드를 검증

---

## 3. 실행 모델: Job/Worker 분리 (권장)

> 논문 파이프라인은 장시간/고부하가 될 수 있으므로, API 서버(FastAPI)와 워커(Engine)를 분리한다.

### 3.1 구성
- **API 서버**: 요청 수신/Job 생성/상태 관리/SSE 스트리밍
- **워커 프로세스**: 실제 파이프라인 수행 (Ingest/Index/Read/Verify)

### 3.2 구현 선택지 (스펙은 “인터페이스”만 고정)
- 큐/브로커: Redis/RabbitMQ 등
- 워커 프레임워크: Celery/RQ/Arq 등  
→ 구체 선택은 구현 단계에서 결정하되, **Job 상태머신/이벤트 포맷**은 본 스펙을 따른다.

---

## 4. 데이터 모델 (Artifacts & Storage Contracts)

### 4.1 식별자 규칙
- `paper_id`: 내부 식별자(권장: Zotero key 또는 안정적 해시)
- `citekey`: Better BibTeX CiteKey(Obsidian 파일명 기본값)
- `run_id`: 실행(파이프라인 1회) 고유 ID (UUID 권장)
- `job_id`: 비동기 작업 ID (UUID 권장)
- `trace_id`: 로그 상관관계 ID (job_id 또는 run_id와 동일하게 사용 가능)

### 4.2 Artifact 저장 경로(표준)
- `storage/artifacts/{paper_id}/{run_id}/`
  - `document_artifact.json`
  - `chunks.jsonl` (또는 parquet)
  - `claimset.json`
  - `stats_report.json`
  - `run_meta.json`
  - `stdout.log` / `agent_trace.jsonl` 등

### 4.3 필수 Pydantic 스키마 (src/schemas/)
> 아래 스키마는 **하드코딩(불변 계약)** 한다. (Schema‑Persona Boundary)

#### 4.3.1 DocumentArtifact
- `paper_id`, `citekey`, `source_pdf_path`, `pdf_exists`
- `text_extraction`: `{status, pages, warnings, failure_reason}`
- `tables`: 배열
  - 각 테이블: `{table_id, page, caption, dataframe_json?, extraction_status, failure_reason}`
- `figures?`: `{figure_id, page, caption?}` (선택)
- `created_at`, `schema_version`

#### 4.3.2 Chunk (Index 단위)
- `chunk_id`, `paper_id`, `run_id`
- `section?`, `page_start`, `page_end`
- `char_start`, `char_end`
- `text`
- `embedding_model`, `embedding_vector?`(저장 정책에 따라 생략 가능)
- `schema_version`

#### 4.3.3 ClaimSet (Reader 출력)
- `paper_id`, `run_id`, `persona_id`
- `claims`: 배열
  - `{claim_id, claim_text, claim_type, confidence, evidence: [EvidenceSpan]}`
- `limitations`: 배열(각 항목도 evidence 필수)
- `heterogeneity`: 배열(각 항목도 evidence 필수)
- `gaps`: 배열(각 항목도 evidence 필수)
- `tags_soft`: 배열(의학/생물학 태깅)
- `schema_version`

#### 4.3.4 EvidenceSpan (근거 의무)
- `chunk_id` 또는 `{page, char_start, char_end}`
- `quote?` (선택, 짧게)
- `rationale` (왜 이 근거가 해당 claim을 지지하는지 1~2문장)

> **규칙:** evidence가 비어 있으면 해당 claim/항목은 자동으로 `confidence=low` 처리하거나 “검증 불가”로 표시한다.

#### 4.3.5 StatsReport (Verifier 출력)
- `paper_id`, `run_id`
- `input_tables_used`: 어떤 table_id를 사용했는지
- `checks`: 배열
  - `{check_id, hypothesis, method, code, outputs, verdict, p_value?, effect_size?, notes, evidence:[EvidenceSpan]?}`
- `sandbox`: `{path, time_limit_sec, packages_whitelist}`
- `schema_version`

#### 4.3.6 FeedbackCase (HITL)
- `feedback_id`, `paper_id`, `run_id`
- `user_correction`: `{field_path, before, after}`
- `accepted`: bool (검수 승인)
- `error_taxonomy`: 코드(선택)
- `embeddings`: `{query_embedding_id?, case_embedding_id?}`
- `created_at`

---

## 5. 에이전트/파이프라인 워크플로우 (Ingest → Index → Read → Verify)

### 5.1 Ingest Agent
**입력:** `paper_id`, PDF 경로  
**출력:** `DocumentArtifact`

- PDF 텍스트 추출: pymupdf/pdfplumber 등  
- 표 추출: 실패를 정상 케이스로 취급  
- 실패 시에도 `DocumentArtifact`는 생성(상태/이유 포함)

### 5.2 Indexer Agent
**입력:** `DocumentArtifact`  
**출력:** `Chunk` + 벡터스토어(ChromaDB)

- chunking 전략은 config로 조절하되, **Chunk 스키마는 고정**
- 모델: `nomic-embed-text` (기본)
- 재인덱싱 트리거: PDF 해시 변경, chunking 변경, embed model 변경

### 5.3 Scientific Reader Agent
**입력:** Chunks + Persona YAML + Few‑shot 사례(동적)  
**출력:** `ClaimSet` (근거(evidence) 의무)

- 기본 모델: `llama3:8b`
- Soft tag 전문 필요 시: `biomistral` 경유 가능
- **출력은 JSON 스키마를 만족해야 하며**, 스키마 미준수 시 재시도/실패 처리

### 5.4 Stats Verification Agent
**입력:** `DocumentArtifact.tables` + ClaimSet에서 필요한 항목  
**출력:** `StatsReport`

- tool: `effGen.tools.PythonREPL`
- 엄격 JSON 포맷이 필요하면 `openhermes2.5-mistral` 계열 활용(권장)
- 샌드박스 제한(필수):
  - 네트워크 금지
  - 파일 접근은 `storage/sandbox/{job_id}/`만
  - 시간 제한(예: 10~30초)
  - 패키지 화이트리스트(numpy/pandas/scipy 등)

---

## 6. 멀티 모델 매핑 (Model Routing)

> 모델 선택은 config로 “강제 매핑”한다. (일관성/재현성)

예시:
- Ingest: (LLM 불필요)  
- Index: `nomic-embed-text`  
- Read: `llama3:8b` (+ biomistral)  
- Verify: `openhermes2.5-mistral` (JSON 준수)  
- (옵션) Judge/QA: 상위 모델(클라우드)로 에스컬레이션 가능하나 기본은 로컬-first

---

## 7. 4대 절대 방어선 (Guardrails) — 코드로 강제

### 7.1 Pre‑flight File Check (실행 전 검증)
- API가 deepread 요청을 받으면 워커 실행 전에:
  - Zotero export에 명시된 PDF 절대 경로 존재 여부 확인(`os.path.exists`)
  - 없으면 즉시 `404/422` 에러 반환(정책에 따라)
  - PDF 해시/mtime 기록

### 7.2 Schema‑Persona Boundary (구조/내용 분리)
- Persona/지시사항/예시는 `configs/prompts/*.yaml`에서 동적 로드  
- 출력 스키마는 `src/schemas/*.py` Pydantic로 고정  
- 파싱 실패는 즉시 “형식 오류”로 처리하고, 재시도 정책을 따름

### 7.3 Real‑time Comms (비동기 + SSE)
- 장시간 작업은 **동기 실행 금지**
- UI로 진행 상태/로그는 SSE로 스트리밍
- SSE 재연결 지원:
  - `event_id` 포함
  - 클라이언트가 `Last-Event-ID`로 재요청 시 replay 지원(로그 저장소 기반)
  - `Last-Event-ID`가 현재 로그 길이를 초과하면(rotate/truncate) cursor를 0으로 보정하고 head부터 재생

### 7.4 Dynamic Few‑shot Injection (동적 프롬프트 주입)
- 피드백은 YAML에 Append하지 않는다.
- 피드백 DB에 저장 후, 실행 시:
  - 현재 쿼리 임베딩과 유사한 사례 최대 3개를 검색
  - 승인(accepted)된 성공 사례 우선
  - (옵션) 대표 실패 1개를 “금지 패턴”으로 함께 주입 가능

---

## 8. API 계약 (FastAPI Endpoints)

### 8.1 공통 규칙
- 모든 응답은 `trace_id`, `timestamp`, `schema_version`(해당 시) 포함 권장
- 에러는 표준 구조:
  - `{error_code, message, trace_id, details?}`

### 8.2 엔드포인트 목록(필수)
#### Health
- `GET /health` → OK

#### Papers (Zotero export)
- `GET /papers`  
  - 목록: `{paper_id, citekey, title, year, pdf_exists, last_run_status?}`
- `GET /papers/{paper_id}`  
  - 상세 메타 + pdf_path + preflight 결과
- `GET /papers/{paper_id}/pdf`
  - 등록된 원문 PDF 바이너리 스트림 반환(`application/pdf`)

#### Personas (YAML registry)
- `GET /personas?include_disabled=false`
  - response: `PersonaListResponse`
  - 기본 `default` persona + `config/profiles.yaml` 기반 persona 목록 반환

#### Jobs (비동기 실행)
- `POST /jobs/deepread`  
  - body: `JobCreate` (`paper_id`, `persona_id`, `clean_reindex`, `run_verify`)
  - response: `{job_id, run_id, status:"queued"}`
  - 충돌/백프레셔:
    - `409 JOB_ALREADY_OPEN` (동일 `paper_id` 열린 job 존재)
    - `429 QUEUE_FULL` (`LATTICE_MAX_QUEUED_JOBS` 상한 초과)
  - `clean_reindex=true`일 때, 기존 `doc_id` 벡터를 purge 후 재인덱싱
- `GET /jobs/{job_id}`  
  - `{status, progress, started_at, finished_at, run_id, error?}`
- `POST /jobs/{job_id}/cancel`  
  - 취소 요청
- `GET /jobs/{job_id}/events` (SSE)  
  - 이벤트: `progress`, `log`, `artifact_ready`, `error`, `completed`

#### Artifacts
- `GET /artifacts/{paper_id}/latest`  
- `GET /artifacts/{paper_id}/{run_id}`  
- `GET /artifacts/{paper_id}/{run_id}/{artifact_name}` (세분화 조회)
  - 지원 alias 예: `claimset`, `document`, `index`, `stats`, `bootstrap_meta`, `run_meta`, `chunks`

#### Feedback (HITL)
- `POST /feedback`  
  - body: `{paper_id, run_id, corrections:[...], accepted?}`
- `GET /feedback?paper_id=...` (선택)

#### Obsidian
- `POST /obsidian/sync`  
  - body: `{paper_id, run_id}`
  - 결과를 `{CiteKey}.md`에 반영(idempotent)
  - claimset 입력은 `claimset.resolved.json` 우선, 없으면 `claimset.json` fallback
- `GET /obsidian/artifacts?paper_id=...&run_id=...`
  - Obsidian 렌더용 artifact 묶음(claimset/chunks/stats) 조회
  - claimset은 `claimset.resolved.json` 우선, 없으면 `claimset.json` fallback

### 8.3 UI Surface ↔ API 매핑 (구현 오해 방지용)
| UI Surface | API | Request Contract | Response Contract |
| :--- | :--- | :--- | :--- |
| Navigation Rail 논문 목록 | `GET /papers` | query 없음 | papers 배열 (`paper_id`, `citekey`, `title`, `pdf_exists`, `last_run_status?`) |
| PDF Renderer 패널 | `GET /papers/{paper_id}/pdf` | path `paper_id` | PDF binary (`application/pdf`) |
| Persona 선택 드롭다운 | `GET /personas` | query `include_disabled?` | `PersonaListResponse` (`default` + YAML persona) |
| Run 버튼(Deep Read 시작) | `POST /jobs/deepread` | `JobCreate` (`paper_id`, `persona_id`, `clean_reindex`, `run_verify`) | `JobEnqueueResponse` (`job_id`, `run_id`, `status`) |
| Job 상태 배지/진행률 | `GET /jobs/{job_id}` | path `job_id` | `JobStatus` |
| Run 중심 상태 조회 | `GET /runs/{run_id}` | path `run_id` | `JobStatus` |
| 타임라인 패널 | `GET /runs/{run_id}/timeline` | path `run_id`, query `limit` | `RunTimelineResponse` (`events[]`) |
| 실시간 로그 스트림 | `GET /jobs/{job_id}/events` (SSE) | path `job_id`, header `Last-Event-ID?` | SSE events (`status`, `artifact_ready`, `log`, `done`, `error`) |
| Artifact 렌더러 | `GET /artifacts/{paper_id}/latest` | path `paper_id` | `ArtifactBundleResponse` |
| Artifact 버전 고정 조회 | `GET /artifacts/{paper_id}/{run_id}` | path `paper_id`, `run_id` | `ArtifactBundleResponse` |
| Artifact 단일 파일 조회 | `GET /artifacts/{paper_id}/{run_id}/{artifact_name}` | path `paper_id`, `run_id`, `artifact_name` | `ArtifactFileEntry` |
| HITL 피드백 저장 | `POST /feedback` | `FeedbackCase` | `{status, message}` |
| HITL 피드백 조회 | `GET /feedback` | query `paper_id?`, `run_id?`, `limit?` | `FeedbackCase[]` |
| Obsidian 렌더 번들 조회 | `GET /obsidian/artifacts` | query `paper_id`, `run_id` | `ObsidianArtifactsResponse` |
| Obsidian 반영 | `POST /obsidian/sync` | `{paper_id, run_id}` | `{status, file, message}` |

### 8.4 핵심 엔드포인트 스키마 예시
1) `POST /jobs/deepread` request
```json
{
  "paper_id": "paper_001",
  "persona_id": "senior_postdoc",
  "clean_reindex": false,
  "run_verify": true
}
```
2) `POST /jobs/deepread` response
```json
{
  "job_id": "4e4f4f77-6f5c-4f4a-90cf-ccf0fb7a9f8a",
  "run_id": "run_20260224_120001",
  "status": "queued"
}
```
3) `GET /artifacts/{paper_id}/{run_id}` response (요약)
```json
{
  "paper_id": "paper_001",
  "run_id": "run_20260224_120001",
  "files": {
    "document_artifact": {"exists": true, "path": "storage/artifacts/.../document_artifact.json", "data": {}},
    "claimset": {"exists": true, "path": "storage/artifacts/.../claimset.json", "data": {}},
    "stats_report": {"exists": false, "path": null, "data": null}
  }
}
```
4) `GET /runs/{run_id}/timeline` response (요약)
```json
{
  "run_id": "run_20260224_120001",
  "job_id": "4e4f4f77-6f5c-4f4a-90cf-ccf0fb7a9f8a",
  "paper_id": "paper_001",
  "events": [
    {"event": "log", "source": "job_log", "stage": "read", "progress": 70, "message": "analysis running"},
    {"event": "done", "source": "synthetic", "stage": "completed", "progress": 100, "message": "completed"}
  ]
}
```

---

## 9. Job 상태머신 (State Machine)

### 9.1 상태
- `queued` → `running` → `succeeded`
- `queued`/`running` → `failed`
- `queued`/`running` → `cancelled`

### 9.2 진행률(progress) 규칙
- 0~100 정수 또는 0.0~1.0 실수(둘 중 하나로 통일)
- 단계별 가중치 예:
  - preflight 5%
  - ingest 20%
  - index 25%
  - read 30%
  - verify 20%

### 9.3 재시도 정책(선택)
- LLM JSON 파싱 실패: 최대 N회 재시도(temperature=0 유지)
- 외부 파일 누락: 재시도하지 않음(사용자 조치 필요)

---

## 10. SSE 이벤트 포맷 (Streaming Contract)

### 10.1 이벤트 타입
- `progress`: `{job_id, progress, stage}`
- `log`: `{level, message, stage, ts}`
- `artifact_ready`: `{artifact_type, path}`
- `error`: `{error_code, message, details?}`
- `completed`: `{status:"succeeded"|"failed"|"cancelled"}`

### 10.2 로그 저장(필수)
- `logs/jobs/{job_id}.jsonl` 에 구조화 저장  
- SSE는 “저장된 로그를 tail”하는 형태로 구현(재연결/replay 지원)
- `Last-Event-ID=done-{n}`가 현재 terminal seq와 같으면 `done` 이벤트를 중복 재전송하지 않음(상태 스냅샷만 전달)
- `done-*` cursor가 비정상(비터미널/길이 초과)이면 cursor를 head로 보정해 replay

---

## 11. Obsidian Integration (Idempotent 규칙)

### 11.1 파일명
- 기본: `{CiteKey}.md`

### 11.2 업데이트 규칙(중복 방지)
- frontmatter에 최소 필드:
  - `paper_id`, `citekey`, `last_run_id`, `updated_at`, `artifact_schema_version`
- 본문은 섹션 단위로 관리:
  - `## Summary (Agent)`
  - `## Claims (Evidence-linked)`
  - `## Stats Verification`
  - `## Limitations / Gaps`
  - `## Related Papers`
- 같은 `run_id` 재반영 시 **동일 섹션 replace** (append-only 금지)

---

## 12. Configuration (configs/)

### 12.1 configs/config.yaml (시스템 설정)
- `agents.enabled: true`
- 모델 매핑, chunking, 임계값, 경로, 샌드박스 제한, 도구 정책 등

### 12.2 configs/prompts/*.yaml (Persona/도메인 지시)
- 예: `senior_postdoc.yaml`, `biomed_ra.yaml`
- 포함 요소:
  - role/system prompt
  - extraction focus(한계점/이질성/공백/근거 필수)
  - style(출력은 schema를 만족)

---

## 13. Logging 정책 (logs/)

### 13.1 필수 필드(구조화 로그)
- `ts`, `level`, `trace_id`, `job_id`, `run_id`, `paper_id`, `citekey`
- `stage`, `message`, `exception?`, `stacktrace?`

### 13.2 로그 레벨
- `INFO`: 단계 진행
- `WARNING`: 비정상(하지만 계속 진행 가능)
- `ERROR`: 실패/중단

---

## 14. Security / Safety (필수)

### 14.1 PythonREPL 샌드박스
- 네트워크 차단
- 경로 제한(`storage/sandbox/{job_id}/`)
- 시간/메모리 제한
- 패키지 화이트리스트

### 14.2 외부 검색(선택)
- 기본은 로컬-first
- 만약 웹검색 도구를 붙이면:
  - 기본 OFF
  - 사용 시 출처/검색어/요약을 trace에 저장
  - 토큰 폭증 방지를 위한 호출 상한 규칙 적용

---


---

## Phase 0 (Optional): AI‑Assisted Bootstrapping **with Cross‑Teacher Validation**
별칭: **Prompt-level distillation / Golden‑Shot bootstrapping**

> 목적: 시스템 본격 가동 전에, “사람이 UI에서 교정해야 할 초기 구간”을 **교사(클라우드 LLM)에게 외주**하여  
> **고품질 Golden examples(권장 30~50개)** 를 피드백 DB에 미리 적재한다.  
> 단, **대규모 오염(잘못된 정답 주입)** 을 막기 위해 **교사 2명(교차검증)** + 자동 검증 게이트를 필수로 둔다.

### 0A. 역할 정의 (Teacher‑Student)
- **Student (로컬)**: llama3:8b (PaperPipe deepread 기본 엔진)
- **Teacher‑1 (Editor)**: “교정자” — 학생 JSON을 논문 근거에 맞게 수정해 **정답 JSON** 생성
- **Teacher‑2 (Auditor/Judge)**: “감사/채점자” — Teacher‑1의 정답 JSON을 **루브릭으로 검수**하고 PASS/FAIL 및 수정 지시를 산출

> Teacher‑2는 Teacher‑1과 **다른 모델/다른 제공자**를 권장(동일 편향 감소).  
> 예: Teacher‑1=OpenAI, Teacher‑2=Anthropic (또는 반대).  
> (가격/모델명은 시점에 따라 변동될 수 있으므로 스펙에는 고정하지 않음)

### 0B. 데이터 최소 전송(권장)
저작권/프라이버시/비용을 위해 Teacher에게 **PDF 전문 전체**를 보내지 않는다.  
대신 아래를 최소 단위로 전송:
- 학생이 참조한 **관련 chunks**(Top‑N, 예: 8~20개)
- 표(table) JSON + 캡션/페이지
- 필요한 경우 methods/results 일부 chunk
- 학생 출력 JSON (원본)
- (중요) **EvidenceSpan 규칙**(근거 없는 항목은 unknown 처리)

### 0C. 부스팅 루프(외장 스크립트: `bootstrap.py`) — 아키텍처 무수정
1) **Student run**  
   - 대상 PDF 폴더(또는 paper_id 목록)에서 `POST /jobs/deepread` 호출  
   - 산출물: `claimset.json`, `document_artifact.json` (필요 시 index/verify 포함)
2) **Teacher‑1 correction (Editor)**  
   - 입력: 최소 전송 패킷 + 학생 JSON  
   - 출력: `teacher1_answer.json` (스키마 준수, evidence 의무)
3) **Teacher‑2 audit (Auditor/Judge)**  
   - 입력: 동일 근거 패킷 + Teacher‑1 정답 + 루브릭  
   - 출력: `teacher2_audit.json`  
     - `verdict: PASS|FAIL`  
     - `score: 0~1`  
     - `major_issues[]` / `minor_issues[]`  
     - `required_fixes[]` (FAIL일 때)
4) **Reconcile(합의/수정 루프)**  
   - PASS이면: “부스팅 후보”로 저장 (`accepted=false` 상태)  
   - FAIL이면: Teacher‑1에게 `required_fixes`를 넣어 **최대 1~2회 재수정**(권장 1회)  
   - 재수정 후에도 FAIL이면: **human review queue**로 이동(자동 주입 금지)
5) **Feedback injection (PaperPipe API)**  
   - 부스팅 후보를 `POST /feedback`로 저장하되, 기본값은 `accepted=false`  
   - 샘플 인간 검수 후 `accepted=true`로 승격(또는 별도 승격 API/플래그)

### 0D. 자동 검증 게이트(필수, “오염 방지”)
부스팅 후보는 아래를 모두 통과해야만 DB에 저장 가능(미통과 시 폐기 또는 human review):
1) **Schema validation**: Pydantic 파싱 성공
2) **Evidence validation**: Claim/limitation/heterogeneity/gap/stats 항목에 EvidenceSpan이 1개 이상
3) **Numeric sanity checks** (최소):
   - p-value ∈ [0,1]
   - N(표본수) > 0
   - SD/SE/CI 변환 시 단위/정의 일관성(가능한 범위 내)
4) **Cross‑teacher agreement**:
   - Teacher‑2 `verdict=PASS` AND `score >= threshold`(예: 0.85)
   - major issue 0개

> Evidence가 없거나, Teacher‑2가 FAIL이면 **절대 accepted=true로 저장 금지**.

### 0E. 루브릭(Teacher‑2 Auditor에게 제공) — 필수
Auditor 프롬프트에 다음 규칙을 명시:
- 근거(페이지/스팬/청크) 없는 값은 **추측으로 간주 → FAIL 또는 unknown으로 수정 요구**
- 숫자(Mean/SD/SE/CI, p-value)는 근거가 표/텍스트에서 확인되어야 함
- 불확실하면 unknown/NA로 남기고 이유를 쓰게 함
- 스키마 필드 누락/불일치/타입 오류는 즉시 FAIL

### 0F. 저장/추적(재현성 필수)
`storage/artifacts/{paper_id}/{run_id}/bootstrap/`에 아래를 저장:
- `student_output_claimset.json` (원본)
- `teacher1_answer.json`
- `teacher2_audit.json`
- `reconcile.json` (PASS/FAIL, revision count, 최종 결정)
- `bootstrap_meta.json`:
  - `teacher1_model`, `teacher2_model`, `provider`, `prompt_version`
  - `budget_limits`, `token_usage?`(가능하면), `timestamp`

### 0G. 권장 운영 방식(미니 배치)
- Test 5편 → 프롬프트/스키마/게이트 확인
- Pilot 15~20편 → 케이스 커버리지(표 유형/변칙) 확인
- Full 30~50편 → Golden examples 확보

> **중요:** 비용은 모델/시점/텍스트 길이에 따라 크게 달라질 수 있으므로,  
> 스펙에는 고정 금액을 넣지 말고 `budget_cap`(예: 하루/배치 상한)과 실제 사용 로그로 관리한다.


## 15. 테스트 & 품질(DoD)

### 15.1 Phase별 DoD (Milestones)

#### Phase 1 (API & Zotero)
- [x] `/papers` 목록 반환
- [x] `/papers/{id}`에서 `pdf_exists` 포함
- [x] 누락 PDF는 명확히 상태 표시

#### Phase 2 (Agent & SSE)
- [x] Job 큐 기반 실행(워커 분리)
- [x] `/jobs/{id}/events` SSE 스트림
- [x] 서버 재시작 후에도 job 상태/로그 보존

#### Phase 3 (Control UI)
- [x] UI에서 논문 선택→deepread 실행→artifact 렌더링(`GET /ui` + `GET /papers/{paper_id}/pdf`)
- [x] persona 선택이 YAML 기반으로 반영(코드 수정 없이, `GET /personas` + `persona_id`)

#### Phase 4 (HITL & Verification)
- [x] 교정 UI → feedback DB 저장
- [x] 다음 실행에서 유사 사례 Top‑3 동적 주입(로그로 확인)
- [x] StatsReport에 code+outputs+verdict가 저장됨

#### Phase 5 (Obsidian Integration)
- [x] `{CiteKey}.md` 업데이트가 idempotent(중복 폭증 없음)
- [x] related papers/근거 링크 섹션 생성

### 15.2 정량 Acceptance Criteria (권장값, UI/운영 공통)
- API `POST /jobs/deepread` 응답시간: p95 <= 500ms (로컬 기준, 큐 적재만 수행)
- API `GET /runs/{run_id}` 응답시간: p95 <= 200ms
- API `GET /runs/{run_id}/timeline?limit=500` 응답시간: p95 <= 350ms
- API `GET /artifacts/{paper_id}/latest` 응답시간: p95 <= 500ms (artifact 총 5MB 이하)
- SSE 재연결 목표: 네트워크 단절 후 2초 이내 복구, 중복 허용/유실 0건 목표
- UI 가상 스크롤 성능: 2,000 rows 렌더 시 55 FPS 이상(중앙값 기준)
- UI 첫 상호작용 가능 시간(TTI): 1.5초 이내(로컬 개발 빌드, warm start)
- 런처 신뢰성: `paperpipe start`/`lattice start` 20회 반복 실행 시 성공률 100%

---

## 16. 디렉토리 구조 (Implementation Tree)

```text
paperpipe/
├── backend/                 # FastAPI core API (control plane)
├── frontend/                # Control Web UI
├── src/                     # Engine/Workers
│   ├── agents/              # Ingest/Index/Read/Verify classes
│   ├── schemas/             # Pydantic schemas (hard contract)
│   ├── adapter.py           # Ollama JSON communication adapter
│   └── jobs/                # (권장) job runner / worker entrypoints
├── configs/
│   ├── config.yaml
│   └── prompts/             # persona YAMLs
├── storage/
│   ├── rag/                 # ChromaDB vector store
│   ├── sandbox/             # PythonREPL isolated workdir
│   ├── artifacts/           # run outputs (json/jsonl)
│   └── zotero_export.json
└── logs/                    # system/job logs (jsonl + text)
```

---

---

## 18. 운영/비용/신뢰성 하드닝 (Hardening Addendum)

> 이 섹션은 “구현 후 반드시 터지는 운영 이슈”를 미리 막기 위한 **필수 보강 명세**입니다.  
> Antigravity에 전달 시, 아래 항목을 **기본값으로 구현**하도록 요구하세요.

### 18.1 Job 지속성(서버 재시작 내구성) — 필수
- Job 상태/메타데이터는 **메모리만 사용 금지**. 최소한 아래 중 하나로 영속 저장:
  - SQLite (로컬 단일 사용자 MVP)
  - Redis + 영속 옵션
  - Postgres (멀티유저/장기 운영)
- Job 레코드 최소 필드:
  - `job_id, run_id, paper_id, status, progress, stage, created_at, started_at, finished_at`
  - `artifact_dir, log_path, error_code?, error_message?`

### 18.2 동시성/백프레셔(폭주 방지) — 필수
- 동시 실행 제한(예: `max_concurrent_jobs=1~N`)을 config로 제공
- 같은 `paper_id`에 대해 동시에 2개 deepread 실행 금지(락/세마포어)
- 큐 길이 상한 및 “거절(429)” 정책 명시
- 현재 구현(2026-02-25):
  - worker claim 시 동시 실행 상한 `LATTICE_MAX_CONCURRENT_JOBS`(legacy: `PAPERPIPE_MAX_CONCURRENT_JOBS`, 기본값 `1`) 적용
  - `POST /jobs/deepread`는 같은 `paper_id`의 열린 job(`queued|running`)이 존재하면 `409 JOB_ALREADY_OPEN` 반환
  - 큐 상한은 `LATTICE_MAX_QUEUED_JOBS`(legacy: `PAPERPIPE_MAX_QUEUED_JOBS`)로 제어, 초과 시 `429 QUEUE_FULL`

### 18.3 취소(Cancel) 의미론 — 필수
- `POST /jobs/{id}/cancel`은 “요청 접수”일 뿐, 즉시 중단이 아님  
- 워커는 단계별 체크포인트에서 `cancel_flag`를 폴링해 **협력적 취소(cooperative cancellation)** 수행
- 취소 시:
  - 상태 `cancelled`
  - 부분 산출물은 `partial=true` 메타를 남기고 보존 가능(옵션)

### 18.4 재현성(Research-Grade Reproducibility) — 필수
각 run마다 아래를 `run_meta.json`에 반드시 저장:
- `pdf_sha256`, `pdf_mtime`
- `config_snapshot`(해당 run에 사용된 config.yaml의 스냅샷 경로)
- `prompts_snapshot`(persona YAML 스냅샷 경로)
- `models_used`(모델명 + 버전/태그)
- `llm_params`(temperature, top_p, num_ctx 등)
- `embed_params`(chunking, embed model)
- `tool_policy_version`(샌드박스/도구 호출 제한 버전)
- 현재 구현(2026-02-25):
  - worker가 `storage/artifacts/{paper_id}/{run_id}/run_meta.json` 생성
  - `pdf_sha256`, `pdf_mtime`, `llm_params`, `embed_params`, `models_used`, `tool_policy_version` 기록
  - `storage/artifacts/{paper_id}/{run_id}/snapshots/`에 `config.yaml`, `config/profiles.yaml` 스냅샷(존재 시) 저장

> 권장: run 시작 시점에 `storage/artifacts/{paper_id}/{run_id}/snapshots/`에 config/prompt를 복사해 “나중에 바뀌어도 과거 run 재현 가능”하게 한다.

### 18.5 API 보안(로컬이라도 최소 보호) — 권장(실전에서는 필수)
- 기본 배포는 `localhost` 또는 내부망으로 제한
- 옵션: 간단한 **API Key 헤더 인증**(예: `X-API-Key`) 지원
- CORS는 `frontend` 오리진만 허용(와일드카드 금지)
- 로그/응답에 로컬 파일 절대경로를 그대로 노출하지 않도록 마스킹 옵션 제공
- 현재 기본값: `http://127.0.0.1:8000`, `http://localhost:8000` (환경변수로 확장 가능)
- 현재 구현(2026-02-25):
  - `LATTICE_API_KEY`(legacy: `PAPERPIPE_API_KEY`)가 설정되면 쓰기 엔드포인트 인증 활성화
  - `X-API-Key` 헤더 불일치/누락 시 `401 UNAUTHORIZED`
  - 보호 대상: `POST /jobs/deepread`, `POST /jobs/{id}/cancel`, `POST /feedback`, `POST /obsidian/sync`
  - 응답 경로 마스킹 옵션: `LATTICE_MASK_LOCAL_PATHS=true` (legacy: `PAPERPIPE_MASK_LOCAL_PATHS`)
  - 운영 예시 문서: `docs/runtime_security_env.md`

### 18.6 SSE 안정성 — 권장
- 15~30초 간격 `ping` 이벤트로 커넥션 유지(프록시 타임아웃 방지)
- 이벤트에 `id:`(event_id)와 `retry:`를 포함해 클라이언트 재연결을 안정화
- 대용량 로그는 SSE로 “요약”만 흘리고, 원문은 `logs/jobs/{job_id}.jsonl`로 저장 후 필요 시 fetch

### 18.7 Obsidian 파일 업데이트 안정성 — 권장
- 원자적 업데이트(atomic write):
  1) 임시 파일에 작성
  2) rename으로 교체
- 파일 락(동시 업데이트 방지)
- 섹션 replace는 “명확한 마커”로 구간을 잡아 덮어쓰기:
  - 예: `<!-- BEGIN CLAIMS --> ... <!-- END CLAIMS -->`
- 현재 구현(2026-02-25):
  - `POST /obsidian/sync`에서 노트 단위 락(`.<note>.lock`) 후 atomic rename(`os.replace`) 적용
  - 기존 AI 블록(`<!-- AI_AGENT_START --> ... <!-- AI_AGENT_END -->`)은 append 대신 구간 교체

### 18.8 비용 관리(로컬 자원) — 권장
- Ollama 모델별 메모리/VRAM 요구사항을 문서화
- run 옵션으로 “index-only / read-only / verify-only” 제공(불필요 단계 스킵)
- LLM 호출 재시도 횟수/최대 토큰/최대 컨텍스트를 config로 제어



## 17. Open Questions (결정 필요 항목)
- Job 큐/워커 프레임워크 선택(Celery/RQ/Arq 등)
- Zotero export 업데이트 감지 방식(폴링 vs 파일 watch)
- PDF 경로 깨짐 대응(대체 경로 탐색 정책)
- ClaimSet/StatsReport의 “최소 근거 단위”(chunk_id vs page/offset)
- UI에서 교정 가능한 필드 범위(ClaimSet만? Tags 포함?)

### 17.1 구현-명세 패리티 점검 (2026-02-24)
- 반영 완료:
  - `GET /papers/{paper_id}/pdf` (Control UI PDF renderer source)
  - `GET /personas` (UI persona selector, YAML registry)
  - `GET /artifacts/{paper_id}/latest`
  - `GET /artifacts/{paper_id}/{run_id}`
  - `GET /artifacts/{paper_id}/{run_id}/{artifact_name}`
  - `GET /runs/{run_id}`
  - `GET /runs/{run_id}/timeline`
  - `GET /feedback` (filter: `paper_id`, `run_id`, `limit`)
  - `POST /jobs/deepread` 응답에 `run_id` 포함
  - `clean_reindex` 런타임 연결(큐 플래그 -> worker -> index reset)
  - `run_meta.json` 재현성 필드 기록 + snapshots 복사(config/profiles)
  - SSE `Last-Event-ID` 기반 로그 replay(`log-*`), terminal replay(`done-*`)
  - SSE `retry` 힌트(2s) + heartbeat ping(20s)
  - CORS 기본 정책 localhost 제한 + 환경변수 확장(`LATTICE_CORS_ALLOW_ORIGINS`)
  - 선택적 API Key 인증(`LATTICE_API_KEY`) + 쓰기 엔드포인트 가드(`X-API-Key`)
  - 응답 절대경로 마스킹 옵션(`LATTICE_MASK_LOCAL_PATHS`)
  - `Last-Event-ID=done-*` 동일 terminal cursor 재접속 시 중복 `done` 미재생(상태만 전송)
  - stale `Last-Event-ID`(로그 길이 초과) 자동 보정(head replay)
  - `GET /obsidian/artifacts` (claimset/chunks/stats bundle, resolved 우선 fallback)
  - `POST /obsidian/sync` (note-level lock + atomic write + marker-block replace)
  - `POST /jobs/deepread` duplicate guard (`paper_id` open job 충돌 시 409)
  - `POST /jobs/deepread` queue backpressure (`LATTICE_MAX_QUEUED_JOBS` 초과 시 429)
- 추적 필요(후속):
  - 없음(현 시점 기준 API/런타임 패리티 항목 소진)

---

## 부록 A. “Antigravity 작업 지시문” 템플릿(복붙용)

**규칙 요약(필수 준수):**
- 출력 JSON 스키마는 Pydantic 계약을 따라야 한다.
- 장시간 작업은 동기 실행 금지, Job 큐 기반 + SSE로 로그 스트리밍.
- EvidenceSpan 없는 claim은 confidence를 자동으로 낮추고 “검증 불가” 표시.
- PythonREPL은 sandbox 제한(네트워크/경로/시간/패키지) 강제.
