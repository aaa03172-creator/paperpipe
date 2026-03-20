# Deep Research Report 3 검토 및 PaperPipe 맞춤 정리 (2026-03-05)

Status: Historical fit review  
Date: 2026-03-05  
Owner: Repository maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## 1) 결론 요약
- 원문 리포트의 핵심 방향(로컬-first, IR 우선, 구조화 출력 강제, 멀티패스 표 추출)은 **우리 아키텍처 목표와 대체로 일치**한다.
- 다만 리포트의 제안 중 일부는 현재 코드베이스 대비 **점프 폭이 큰 재설계**(Docling 전면 전환, 신규 서빙 계층 도입)를 요구하므로, 그대로 일괄 채택하면 리스크가 크다.
- 현재 PaperPipe에는 이미 v2 artifact/bbox 규약, OCR fallback, evidence-linked 워크벤치가 있으므로, **기존 기반을 확장하는 단계적 적용**이 최적이다.

## 2) 문서 자체 품질 검토 (신뢰도/주의점)
### 강점
- 좌표 기반 Evidence를 LLM 출력 이전 IR 단계에서 고정해야 한다는 주장: 타당.
- 표 추출을 멀티패스로 설계(텍스트 기반 -> 이미지/OCR 기반 -> 선택적 클라우드): 운영 현실에 맞다.
- `unknown` 출구를 스키마에 넣어 환각을 누락/보류로 유도: 현재 Gate/QA 정책과 정합성이 높다.

### 주의점
- 문서 인용이 `turnXXsearchYY` 형태라 원본 링크가 사라져 있어, 법무/라이선스 확정 근거로는 바로 쓰기 어렵다.
- 제안 스택(vLLM/SGLang/llama.cpp)은 유효하지만, 현재 런타임(ollama adapter 중심)과의 전환 비용/운영 복잡도 분석이 부족하다.
- 일부 제안은 이미 구현된 내용(v2 bbox contract, OCR fallback)을 "신규"처럼 다루므로 중복 투자 위험이 있다.

## 3) 우리 코드베이스와의 정합성 매핑
### 이미 반영되어 있는 항목 (채택 완료/부분 완료)
- 로컬-first 방향 + ClaimSet 구조화 출력 계약
  - [Lattice_v3_Master_Spec.md](/Users/jangseongjin/paperpipe/docs/Lattice_v3_Master_Spec.md)
- LLM 기본값 local화(최근 반영)
  - [`/Users/jangseongjin/paperpipe/src/config.py:84`](/Users/jangseongjin/paperpipe/src/config.py:84)
- DocumentArtifact v2 + bbox 규약 + stable id
  - [`/Users/jangseongjin/paperpipe/src/contracts/document_artifact_v2.py:7`](/Users/jangseongjin/paperpipe/src/contracts/document_artifact_v2.py:7)
  - [`/Users/jangseongjin/paperpipe/docs/document_artifact_v2.md:30`](/Users/jangseongjin/paperpipe/docs/document_artifact_v2.md:30)
- OCR fallback(감지/실행/메타 기록)
  - [`/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:26`](/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:26)
- UI evidence 하이라이트(직접 bbox + 텍스트 매칭 fallback)
  - [`/Users/jangseongjin/paperpipe/frontend/src/app/components/PdfPanel.tsx:60`](/Users/jangseongjin/paperpipe/frontend/src/app/components/PdfPanel.tsx:60)
  - [`/Users/jangseongjin/paperpipe/frontend/src/app/lib/mock.ts:837`](/Users/jangseongjin/paperpipe/frontend/src/app/lib/mock.ts:837)

### 현재 갭 (우선 보완 대상)
- ClaimSet EvidenceSpan에 `bbox`/`table_cell_link` 1급 필드가 없음
  - 현재 EvidenceSpan은 page/chunk/text 중심
  - [`/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py:97`](/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py:97)
- Reader가 서버 레벨 constrained decoding이 아니라 프롬프트+`format="json"`에 의존
  - [`/Users/jangseongjin/paperpipe/src/agents/reader_agent.py:111`](/Users/jangseongjin/paperpipe/src/agents/reader_agent.py:111)
- Ingest v2에서 block bbox는 있으나 line/span bbox는 대부분 unavailable
  - [`/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:306`](/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:306)
- 표 추출 멀티패스 게이트(Camelot 지표, taxonomy 기반 승격)가 코드화되어 있지 않음
  - 현재는 pdfplumber 중심 단일 경로
  - [`/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:234`](/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:234)

## 4) 우리 상황에 맞는 적용 방향 (권고)
## 방향 A (권장): "기존 파이프라인 확장" 전략
- 이유: 이미 v2 artifact/OCR/UI 하이라이트 기반이 있고, 전체 교체보다 리스크가 낮다.
- 핵심: Docling/vLLM 전면 도입보다, 현재 ingest->reader->verify 경로에 evidence 정밀도 계층을 점진 삽입.

## 방향 B (비권장): "신규 스택 전면 교체" 전략
- 이유: 서빙 계층, 파서 체인, 스키마를 동시 교체해야 해 회귀 위험이 크고 일정 불확실성이 높다.

## 5) 실행 계획 (단계별)
### Phase 1 (즉시, 1~2주)
- EvidenceSpan 스키마 확장:
  - `bbox_pct` 또는 `bbox_pdf`, `table_id`, `cell_id`, `unknown_reason` 추가
- Reader output gate 강화:
  - evidence 없는 claim은 `unknown=true` 또는 confidence 강등 강제
- UI/Exporter 연동:
  - claim -> span/cell direct-link 우선, 텍스트 fallback은 보조로 유지

성공 기준:
- `evidence_location_rate` 상승
- `NEEDS_EVIDENCE_LINK` 큐 비율 감소

### Phase 2 (중기, 2~4주)
- 표 추출 멀티패스 도입:
  - Pass1: 기존 pdfplumber + (옵션) Camelot
  - Pass2: OCR + 구조 복구 (필요 시)
- 실패 taxonomy 도입:
  - `NO_TABLE_FOUND`, `STRUCTURE_DEGENERATE`, `OCR_LOW_CONF`, `MATH_INCONSISTENT`
- 승격 규칙(클라우드/수동검토) 명시

성공 기준:
- 핵심 표 FAIL율 감소
- 수동 검토 투입량 감소

### Phase 3 (선택, 인프라 여건 시)
- OpenAI-compatible boundary layer 정식화:
  - 현행 Ollama adapter + 추가 백엔드(vLLM/llama.cpp) 토글
- 이 단계는 성능/운영 요구가 명확할 때만 진입

성공 기준:
- p95 latency, throughput, structured output 안정성 KPI 충족

## 6) 지금 당장 해야 할 일 (우선순위 Top 5)
1. `EvidenceSpan` 계약 확장안 초안 작성 및 Pydantic 반영
2. Reader 출력 검증 규칙(`unknown` 강제) 추가
3. claimset -> frontend highlight 매핑에서 `bbox_pdf` 표준 경로 확정
4. 표 추출 실패 taxonomy를 `run_meta/bootstrap_meta`에 기록
5. 품질 지표 대시보드에 `evidence_location_rate`, `math_consistency_fail_rate`, `fallback_rate`를 운영 기준선으로 고정

## 7) 이번 리포트에서 "채택/보류" 판정
- 채택:
  - IR 우선 + evidence 후보 고정
  - unknown 출구
  - 멀티패스 표 추출
  - anchor-based 검증 로그
- 조건부 채택:
  - OpenAI-compatible boundary layer 확장(현행 adapter와 공존 전제)
- 보류:
  - Docling 전면 전환
  - 신규 서빙(vLLM/SGLang/llama.cpp) 즉시 교체

## 8) 메모
- 본 문서는 `/Users/jangseongjin/Downloads/deep-research-report-3.md`를 검토한 뒤, 현재 PaperPipe 구현 상태(2026-03-05)와 맞춰 실행 우선순위를 재정의한 내부 정리 문서다.

## 9) 통합안 반영 메모 (2026-03-05)
- 통합 최종 설계 기준 문서: `/Users/jangseongjin/paperpipe/docs/archive/Deep_Research_Integrated_Final_Design_2026-03-05.md`
- 본 문서 제안 중 통합안 반영 상태:
  - 채택: IR 우선, unknown 출구, 멀티패스 표 추출, anchor 검증
  - 조건부 채택: boundary layer 확장, 서빙 다변화
  - 보류: Docling 즉시 전면 전환
- 2026-03-06 재검토:
  - 로컬 우선 설정 유지(`enable_cloud_table_fallback=false`)로 통합 설계와 운영값을 동기화.
  - 12개 문서 배치 검증 결과를 통합 설계 문서 16장에 반영 완료.
  - DOI/anchor 강화 후 30개 fast 배치에서 `doc_id DOI ratio=100.00%`, `anchor no_doi ratio=0.00%` 확인.
  - 30개 full-timeout 배치에서 timeout/error 없이 완료됐으나, Reader `claims=0` 수렴으로 stats 검증은 `skipped_no_claims`가 다수 발생.
