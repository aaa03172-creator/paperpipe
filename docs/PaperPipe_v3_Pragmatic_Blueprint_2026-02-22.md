# PaperPipe v3 Pragmatic Blueprint (2026-02-22)

## 0. 목적
- 본 문서는 PaperPipe를 `Discover -> Grounded Citation -> Triggered Stats` 흐름으로 안정적으로 고도화하기 위한 실행 명세서다.
- 기존 코드베이스 기준으로 "당장 구현 가능한 순서"와 "검증 가능한 완료 기준(AC)"을 고정한다.
- 본 문서는 기획 문서가 아니라 개발/리뷰/테스트의 기준 문서(Single Execution Blueprint)다.

## 1. 하드 원칙 (Must)
- API-First: 핵심 기능은 FastAPI 경로에서 호출 가능해야 하며 CLI 전용 경로로 고립시키지 않는다.
- Pydantic Contracts: 입출력 아티팩트는 `src/schemas/` 또는 `src/contracts/`에 고정된 스키마를 따른다.
- Idempotency: Obsidian 마크다운 업데이트는 섹션 교체(upsert) 방식으로 수행하며 append를 금지한다.
- Evidence Verifiability: LLM 출력은 반드시 시스템 검증이 가능한 형태(`chunk_id + quote`)를 포함한다.
- Conservative Parsing: MVP에서는 bbox/span 하이라이트를 기본 기능에서 제외하고 페이지 링크 + quote를 우선한다.

## 2. 현재 상태 요약 (코드 기준)
- `chunk_id`는 결정론적 형식(`p{page:02d}_c{chunk:02d}`)으로 전환되었다.
  - 참조: `src/agents/indexer_agent.py`
- Evidence는 `grounded/resolution/confidence_band` 검증 필드를 포함하고,
  reader 후처리에서 grounding resolver를 적용한다.
  - 참조: `src/schemas/agent_artifacts.py`, `src/core/evidence_resolver.py`, `backend/services/job_runner_stages.py`
- Reader는 여전히 claim/evidence 초안을 생성하지만,
  페이지/매칭 신뢰는 시스템 후처리에서 확정한다.
  - 참조: `src/agents/reader_agent.py`, `backend/services/job_runner_stages.py`
- OpenAlex는 seed 기준 backward/forward 확장 API를 제공하며,
  추천 후보를 DB(`RECOMMENDED`/`PENDING_QUEUE`) 및 Obsidian queue 섹션으로 반영한다.
  - 참조: `src/fetch/openalex.py`, `src/discovery_queue.py`, `backend/routers/discover.py`
- Stats는 선택 실행(`run_verify`) + 실행 프로파일(`run_profile`) + 태그 트리거(`#important`, `#action/stats_check`) + 캐시(`stats_cache_hit`) 구조를 갖고 있다.
  - 참조: `src/jobs/schemas.py`, `backend/services/job_runner.py`, `backend/services/stats_runtime.py`
- 런타임 품질 관측치(`evidence_grounded_ratio`, cache-hit rollup)를 API에서 조회할 수 있다.
  - 참조: `backend/main.py` (`/metrics/quality`)

## 3. 목표 아키텍처 (v1)
- Fast mode: `fast_ingest`
  - ingest + index + lightweight summary
  - discover queue 생성 가능
- Grounded mode: `grounded_read`
  - claim 추출 + evidence 검증(`quote in chunk_text`)
  - citation jump 렌더
- Deep mode: `deep_verify`
  - stats agent 실행(트리거 기반)
  - 캐시/동시성 제한 적용

## 4. 데이터 계약 v1 (핵심)

### 4.1 Chunk Contract
- `chunk_id`: `p{page:02d}_c{chunk:02d}` 예: `p03_c07`
- `page`: 1-based 저장 (표시/링크 일관성 유지)
- `text`: 검증 기준이 되는 표준 텍스트(정규화 규칙 고정)
- `section_hint`: optional
- 규칙
  - 동일 PDF + 동일 chunking 파라미터에서 `chunk_id` 세트는 동일해야 한다.
  - chunking 파라미터가 바뀌면 `chunk_id`도 재계산된다.

### 4.2 Claim/Evidence Contract
- Evidence 최소 필드
  - `chunk_id` (required)
  - `quote` (required)
  - `raw_text` (optional, fallback)
  - `page` (system-resolved, optional input)
- 검증 필드 (post-process 추가)
  - `grounded: bool`
  - `resolution: "OK" | "FAILED_MATCH" | "MISSING_CHUNK" | "AMBIGUOUS_MATCH"`
  - `confidence_band: "certain" | "estimated" | "hold"`

### 4.3 Evidence 검증 규칙
- 1차: `quote in chunk_text(chunk_id)` exact 매칭
- 2차(선택): 정규화 매칭(공백/인용부호 정리)
- 3차(최후): fuzzy 후보 1개일 때만 허용
- 실패 시
  - `grounded=false`
  - `confidence_band="hold"`
  - 렌더에서 원인 + 다음 행동을 표시

## 5. 기능 명세

### 5.1 Discover & Queue (OpenAlex + Zotero 역할 분리)
- OpenAlex 역할: 후보 탐색(discovery)
- Zotero 역할: 확정된 라이브러리 SoT
- 입력
  - seed: DOI 또는 OpenAlex Work ID
- 처리
  - backward(referenced works), forward(cited_by) 확장
  - 중복 제거(DOI 기준)
  - 점수 산정(최근성, 인용수, OA, seed와의 관계 근거)
- 출력
  - DB 상태: `RECOMMENDED` 또는 `PENDING_QUEUE`
  - Obsidian 섹션: `## Related Works (Queue)` 업서트
  - 각 항목에 "추천 이유 1줄" 필수

### 5.2 Citation Jump MVP (보수적)
- LLM에게 페이지 번호 판단을 맡기지 않는다.
- 시스템이 `chunk_id -> page`를 resolve한다.
- 렌더 규칙
  - 1순위: 페이지 링크(`[p.X]`)
  - 2순위: 링크 불가 시 `p.X + quote + 검색 가이드`
- 상태 뱃지
  - `certain` (근거 검증 성공)
  - `estimated` (약한 매칭)
  - `hold` (매칭 실패/추가 확인 필요)

### 5.3 Stats Trigger
- 기본값: 미실행
- 실행 트리거
  - `run_verify=true`
  - 또는 명시 액션 태그(`#important`, `#action/stats_check`) 매핑
- 운영 규칙
  - 동시 실행 제한: 1~2
  - 캐시 키: `paper_hash + stats_profile + schema_version`
  - 캐시 히트 시 재실행 금지

## 6. API 명세 변경안
- 기존 `/jobs/deepread` 입력 확장
  - `run_profile: "fast_ingest" | "grounded_read" | "deep_verify"` (optional)
  - `run_verify`는 하위호환 유지
- 응답/상태 확장
  - `claimset_readiness` 유지
  - `evidence_grounded_ratio` 추가 권장
  - `stats_cache_hit` 추가 권장

## 7. 저장소/렌더 Idempotency 규칙
- Obsidian
  - Deep Read, Related Works, ClaimSet 섹션은 marker 기반 업서트
  - 동일 입력 재실행 시 문서 중복 블록이 생기지 않아야 한다.
- Artifacts
  - 경로: `storage/artifacts/{paper_id}/{run_id}/`
  - 최소 산출물: `document_artifact.json`, `index_artifact.json`, `claimset.json`
  - 조건 산출물: `stats_report.json`

## 8. PR 분해 및 AC

### PR-0: EVIDENCE_CONTRACT_V1
- 변경
  - 결정론적 `chunk_id` 생성
  - Evidence 검증기 추가(`grounded/resolution`)
  - Reader 출력 후 post-process 검증 파이프라인 추가
- AC
  - 동일 PDF 재실행 시 `chunk_id` 세트 동일
  - claim evidence가 자동으로 `grounded true/false` 판정
  - page 미기입이어도 `chunk_id` 기반 페이지 확정 가능
- 상태
  - 완료 (코드/테스트 반영됨)

### PR-1: DISCOVER_QUEUE_V1
- 변경
  - OpenAlex 확장(fetch referenced/cited_by)
  - seed 기반 추천 생성
  - DB 상태 저장 + Obsidian queue 섹션 업서트
- AC
  - seed 1개로 연관 논문 5~10편 생성
  - 각 항목 추천 이유 출력
  - 중복 없이 재실행 가능
- 상태
  - 완료 (API/DB/Obsidian queue 업서트 + 테스트 반영됨)

### PR-2: CITATION_JUMP_MVP_V1
- 변경
  - claim 렌더 시 `[p.X]` 링크 생성
  - 링크 실패 폴백 UX 추가
  - 상태 뱃지(certain/estimated/hold) 반영
- AC
  - 정상 환경에서 페이지 점프 동작
  - 매칭 실패 시 "보류 + 원인 + 다음 행동" 출력
- 상태
  - 완료 (코드/테스트 반영됨)

### PR-3: RUN_PROFILE_V1
- 변경
  - 실행 모드(`fast_ingest/grounded_read/deep_verify`) 도입
  - 단계별 캐시 적용
- AC
  - 모드별 불필요 단계 스킵
  - 변경 없는 입력에서 재실행 시간 단축(캐시 히트)
- 상태
  - 완료 (API/Queue/Worker/Runner 계약 반영됨)

### PR-4: STATS_TRIGGER_V1
- 변경
  - 태그/플래그 기반 stats 트리거
  - 캐시/동시성 제한 고정
- AC
  - 트리거 논문에만 stats 실행
  - 동일 논문 재요청 시 캐시 히트로 스킵
- 상태
  - 완료 (trigger/tag mapping + cache contract + API meta 반영)

## 9. 테스트 전략
- Unit
  - deterministic chunk_id 생성 테스트
  - evidence 검증기 성공/실패/애매 케이스
  - discover dedupe/정렬 테스트
- Integration
  - `ingest -> index -> read -> verify(optional)` E2E
  - Obsidian 업서트 idempotency 테스트
- Regression
  - 기존 `run_verify` 경로 하위호환 확인
  - 기존 ClaimSet 렌더 테스트 유지

## 10. Non-Goals (현재 범위 제외)
- bbox 기반 정밀 하이라이트 완성
- 표(Table) 완전 구조 파싱 자동화
- scite급 supporting/contrasting 자동 판정
- 멀티문서 상충 판정 자동 확정

## 11. 운영 체크리스트
- 배포 전
  - DB 마이그레이션 확인
  - OpenAlex rate-limit 보호(재시도/타임아웃)
  - 워커 동시성 설정 확인
- 배포 후
  - grounded ratio 모니터링
  - unresolved evidence 비율 모니터링
  - stats 실행/캐시 히트율 모니터링

## 12. 즉시 착수 순서
- 1순위: v2 전환 전 `paper_key`/event-log 도입 여부 결정
- 2순위: v2 docs 승인 후 identity/event-log migration 착수

---

문서 버전: `blueprint.pragmatic.2026-02-22.v1`  
소유: PaperPipe Core  
리뷰 기준: "계약 강제 -> 링크 UX -> 선택 검증" 순서 준수
