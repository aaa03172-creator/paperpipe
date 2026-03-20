---
title: PaperPipe Agent Personas (검증/운영용)
date: 2026-02-21
tags: [paperpipe, agents, personas, verified, audit]
status: historical_audit
owner: repository_maintainers
canonical_parent: docs/Indexer_Model_Policy_Blueprint_2026-02-18.md
---

## 0) 문서 상태
- Verified: 코드/파일로 직접 확인한 사실
- Assumed: 코드 근거 없이 추정한 내용
- Policy 참조: Indexer 모델 정책은 `docs/Indexer_Model_Policy_Blueprint_2026-02-18.md`를 단일 참조로 사용

---

## 1) Reader Agent (Senior Postdoc)
- Files (Verified):
  - `src/agents/reader_agent.py`
  - `src/agents/deep_reader.py`
- Persona (Verified): Senior Postdoc, Critical/Gap 중심 분석
  - 근거: `src/agents/reader_agent.py`
  - 근거: `src/agents/deep_reader.py`
- Mission (Verified):
  - `ReaderAgent`: `ClaimSet` JSON 스키마 강제 출력
  - `DeepReadAgent`: Markdown 분석 리포트 출력
- Runtime 사용 경로 (Verified):
  - CLI 파이프라인은 `ReaderAgent` 사용 (`src/cli.py`)
  - 백엔드 잡 파이프라인도 `ReaderAgent` 사용 (`backend/services/job_runner.py`)
  - `DeepReadAgent` 직접 호출 경로는 현재 미확인(미사용)

---

## 2) Stats Verification Agent (The Auditor)
- File (Verified): `src/agents/stats_agent.py`
- Persona/Mission (Verified): 통계 주장 추출 -> 검증 계획 -> 코드 생성 -> 샌드박스 실행 -> 판정
  - 근거: LangGraph 노드 체인 `parse_tables -> extract_stats -> plan_verification -> generate_code -> execute_sandbox -> reflect_analyze`
- Docker sandbox 사용 (Verified):
  - `DockerSandbox` 사용 및 코드 실행
- Output Contract (Verified): `StatsReport` / `StatCheckEntry` 스키마 사용
  - 위치: `src/schemas/agent_artifacts.py`

---

## 3) Ingest Agent (The Librarian)
- File (Verified): `src/agents/ingest_agent.py`
- Mission (Verified): PDF -> `DocumentArtifact`/`DocumentArtifactV2` 구조화
- Tooling (Verified):
  - PyMuPDF(`fitz`) 텍스트/메타/레이아웃 추출
  - pdfplumber 표 추출
  - OCR fallback 연결 (`src/ingest/ocr_fallback.py`)

---

## 4) Indexer (Knowledge Manager) — Agent + Module 공존
- Agent (Verified): `src/agents/indexer_agent.py`
  - `nomic-embed-text` + Chroma 기반 RAG 인덱싱
- Module (Verified): `src/indexer.py`
  - 독립 인덱서 (`PaperIndexer`) + 컬렉션 버저닝/모델 정책 축
- Policy 문서 (Verified): `docs/Indexer_Model_Policy_Blueprint_2026-02-18.md`

참고:
- `src/agents/indexer_agent.py` 기본 임베딩: `nomic-embed-text`
- `src/indexer.py` 기본 임베딩 상수: `NeuML/pubmedbert-base-embeddings`
- 즉, indexer 구현이 이원화되어 경로별 기본 모델 정책이 다를 수 있음

---

## 5) Audit Checklist (현시점)
- [x] `src/agents/` 실제 파일 존재 + 엔트리포인트 확인
- [x] 파이프라인에서 실제 호출 agent 확인 (CLI + Worker 경로)
- [x] `reader_agent` vs `deep_reader` 역할 차이 문서화
- [x] `stats_agent` Docker sandbox 사용 여부 확인
- [x] ingest 도구(PyMuPDF/pdfplumber/OCR fallback) 확인
- [x] indexer가 agent/module인지 확정 + 정책 문서 연결

---

## 6) 운영 이슈 (Verified)
1. Worker -> JobRunner 실제 체인 연결
- FastAPI `/jobs/deepread`는 enqueue를 수행하고, Worker가 `run_deepread_job`를 호출함 (`src/jobs/worker.py`, `backend/services/job_runner.py`).
- 회귀 가드: `tests/test_worker_job_runner_chain.py`에서 Worker -> JobRunner 실체 체인 스모크를 검증함.

2. Obsidian idempotency
- `## 🤖 Agent Deep Read` 섹션은 단일 첫 매치 교체가 아니라, 정규식 매치되는 기존 Deep Read 섹션들을 정리한 뒤 최신 섹션 1개를 upsert함 (`src/services/deepread_note_writer.py`).
- CLI/백엔드 모두 동일 upsert 함수를 사용함 (`src/cli.py`, `backend/services/job_runner.py`).

3. Reader vs DeepRead 운영 역할
- 운영 경로 핵심 출력은 `ReaderAgent`의 구조화 `ClaimSet`.
- `DeepReadAgent`는 코드에 존재하지만 현재 운영 호출 경로는 확인되지 않음.
