---
title: PaperPipe Agent Personas (검증/운영용)
date: 2026-02-19
tags: [paperpipe, agents, personas, verified, audit]
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
  - 근거: `src/agents/reader_agent.py:26`
  - 근거: `src/agents/deep_reader.py:57`
- Mission (Verified):
  - `ReaderAgent`: `ClaimSet` JSON 스키마 강제 출력 (`src/agents/reader_agent.py:24`, `src/agents/reader_agent.py:38`)
  - `DeepReadAgent`: Markdown 분석 리포트 출력 (`src/agents/deep_reader.py:83`)
- Runtime 사용 경로 (Verified):
  - CLI 파이프라인은 `ReaderAgent` 사용 (`src/cli.py:676`)
  - `DeepReadAgent` 직접 호출 경로는 현재 미확인(미사용)

---

## 2) Stats Verification Agent (The Auditor)
- File (Verified): `src/agents/stats_agent.py`
- Persona/Mission (Verified): 통계 주장 추출 -> 검증 계획 -> 코드 생성 -> 샌드박스 실행 -> 판정
  - 근거: LangGraph 노드 체인 `parse_tables -> extract_stats -> plan_verification -> generate_code -> execute_sandbox -> reflect_analyze`
  - 위치: `src/agents/stats_agent.py:49-75`
- Docker sandbox 사용 (Verified):
  - `DockerSandbox` 사용 및 코드 실행
  - 위치: `src/agents/stats_agent.py:229-233`
- Output Contract (Verified): `StatsReport` / `StatCheckEntry` 스키마 사용
  - 위치: `src/schemas/agent_artifacts.py`

---

## 3) Ingest Agent (The Librarian)
- File (Verified): `src/agents/ingest_agent.py`
- Mission (Verified): PDF -> `DocumentArtifact` 구조화
  - 위치: `src/agents/ingest_agent.py:29`
- Tooling (Verified):
  - PyMuPDF(`fitz`) 텍스트/메타 추출 (`src/agents/ingest_agent.py:3`, `src/agents/ingest_agent.py:65`)
  - pdfplumber 표 추출 (`src/agents/ingest_agent.py:4`, `src/agents/ingest_agent.py:146`)

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
- 즉, 현재 코드베이스는 indexer 구현이 이원화되어 있어 기본 모델 정책이 경로별로 다를 수 있음

---

## 5) Audit Checklist (현시점)
- [x] `src/agents/` 실제 파일 존재 + 엔트리포인트 확인
- [x] 파이프라인에서 실제 호출 agent 확인 (CLI 경로)
- [x] `reader_agent` vs `deep_reader` 역할 차이 문서화
- [x] `stats_agent` Docker sandbox 사용 여부 확인
- [x] ingest 도구(PyMuPDF/pdfplumber) 확인
- [x] indexer가 agent/module인지 확정 + 정책 문서 연결

---

## 6) 운영 이슈 (Verified)
1. 백엔드 verify 호출 시그니처 불일치 이력
- 문제 지점: `backend/services/job_runner.py`에서 `StatsVerificationAgent.run` 인자 불일치가 있었음
- 현재 상태: 시그니처 정합화 반영 완료 (`job_id, doc, claims`)

2. API-First 관점의 연결 상태
- FastAPI `/jobs/deepread`는 enqueue만 수행 (`backend/main.py:38-41`)
- 현재 worker(`src/jobs/worker.py`)는 `backend/services/job_runner.py`의 실제 에이전트 체인을 호출하도록 연결됨
- 의미: API background worker 경로에서도 Ingest -> Index -> Read(-> Verify optional) 실행 가능

3. Obsidian idempotency
- 기존: 섹션 존재 시 skip
- 현재: `## 🤖 Agent Deep Read` 중복 섹션이 있으면 전부 제거 후 최신 섹션 1개만 유지하도록 정규화(upsert)됨 (`src/cli.py`)
