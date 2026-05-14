# Deep Research Report 3+4 통합 최종 설계안 (2026-03-05)

Status: Historical design consolidation  
Date: 2026-03-05  
Owner: Repository maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## 1. 목적과 범위
- 목적: `deep-research-report-3.md`와 `deep-research-report-4.md`의 제안을 PaperPipe 현재 코드베이스에 맞게 통합해, 실행 가능한 최종 설계로 고정한다.
- 범위: PDF 파싱/IR/표 추출/Claim-Evidence/검증/폴백/운영지표/라이선스 가드레일.
- 비범위: 즉시 전면 재작성(Big-bang rewrite), 즉시 추론 서빙 스택 전환(vLLM/llama.cpp 강제 도입).

## 2. 통합 결정 원칙
- API-first, Pydantic contract, idempotent update 원칙을 유지한다.
- 기존 동작을 깨지 않는 additive 변경을 우선한다.
- 정확성 우선 정책: 근거 없으면 생성하지 않고 `unknown`으로 남긴다.
- 비용/프라이버시 우선 정책: 클라우드 전송은 선택 페이지 + 예산 제한만 허용한다.

## 3. 최종 아키텍처 결정

```text
[PDF Ingest]
  -> [Parser Backend Abstraction]
      default: fitz+pdfplumber
      optional: docling
  -> [Document IR (bbox_pt_tl canonical)]
  -> [Table Multi-pass]
      Pass1: pdfplumber (+optional Camelot/Tabula)
      Pass2: OCR/vision recovery
      Pass3: optional cloud fallback (selected pages only)
  -> [Claim/Evidence Extraction]
      mandatory evidence link or unknown
  -> [Anchor-based Verification]
      PASS/WARN/FAIL/NO_API
  -> [Export/UI]
      evidence highlight + audit trail
```

핵심 결정:
- Parser는 단일 구현 고정이 아니라 backend abstraction으로 전환한다.
- IR의 canonical 좌표는 `bbox_pt_tl`로 통일한다.
- 표 추출은 멀티패스로 운영하고 실패 taxonomy를 구조적으로 기록한다.
- ClaimSet은 evidence-first로 강화하고 unknown 출구를 스키마 수준에서 강제한다.
- 검증은 전체 diff가 아니라 anchor-based 검증으로 고정한다.

## 4. 계약(스키마) 최종안

### 4.1 Evidence 계약 확장 (additive)
`src/schemas/agent_artifacts.py`의 `EvidenceSpan`을 다음 방향으로 확장한다.
- 추가 필드:
  - `bbox_pdf: Optional[list[float]]`  # [x0,y0,x1,y1] pt, top-left
  - `bbox_pct: Optional[dict[str, float]]`  # UI 호환용
  - `table_id: Optional[str]`
  - `cell_id: Optional[str]`
  - `unknown_reason: Optional[str]`
- 규칙:
  - evidence가 존재하면 `raw_text` 또는 `table_id/cell_id` 중 최소 하나는 필수.
  - evidence가 비어 있으면 claim은 `unknown=true` 또는 confidence 강등.

### 4.2 Claim 계약 강화
- `ScientificClaim`에 `unknown: bool = False`와 `unknown_reason: Optional[str]`를 additive로 도입.
- Gate 단계에서 evidence 누락 claim은 자동으로 `unknown` 처리.

### 4.3 메타/로그 계약 확장
`run_meta` 또는 `bootstrap_meta`에 아래를 추가 기록:
- `table_extraction_pass`: `pass1|pass2|pass3`
- `table_failure_taxonomy`: list[str]
- `fallback_used`: bool
- `fallback_pages`: list[int]
- `anchor_verify_summary`: `{pass,warn,fail,no_api}`

## 5. Parser Backend 설계

### 5.1 추상 인터페이스
- `ParserBackend` 프로토콜(신규)
  - `parse_document(pdf_path) -> DocumentArtifactV2`
  - `extract_table_candidates(...) -> list[TableCandidate]`
  - `name() -> str`

### 5.2 구현 전략
- 기본 backend: `fitz_pdfplumber` (현행 유지)
- 옵션 backend: `docling` (feature flag)
- 설정 예:
- `ingest.parser_backend: fitz_pdfplumber|docling`
- `ingest.enable_docling: false` (초기)

### 5.3 도입 원칙
- PR1에서는 backend abstraction만 도입, 기본 동작은 기존과 동일.
- Docling은 gated rollout으로만 활성.

## 6. 표 추출 멀티패스 최종안

### 6.1 Pass 구성
- Pass1: pdfplumber 기본, Camelot/Tabula optional
- Pass2: OCR/vision recovery (현재 OCR fallback 경로 강화)
- Pass3: 클라우드 폴백(optional)

### 6.2 실패 taxonomy 표준
- `NO_TABLE_FOUND`
- `DEGENERATE_SHAPE`
- `LOW_ACCURACY`
- `HIGH_WHITESPACE`
- `BBOX_MISMATCH`
- `OCR_LOW_CONF`
- `CELL_OVERLAP_HIGH`
- `CELL_COVERAGE_LOW`
- `BUDGET_EXCEEDED`

### 6.3 승격 규칙
- Pass1 FAIL + Pass2 FAIL + key table이면 Pass3 후보.
- Pass3는 문서당 페이지 예산(예: 2~4p) 내에서만 수행.
- 예산 초과 시 `BUDGET_EXCEEDED` 기록 후 중단.

## 7. Anchor 기반 검증 최종안
- 검증 단위: `anchor_id` (값+문맥+근거 bbox_ref)
- 결과 분류: `PASS|WARN|FAIL|NO_API`
- 필수 로그 필드:
  - `run_id`, `doc_id`, `anchor_id`, `normalized_value`, `bbox_ref`, `api_provider`, `result`, `reason_codes`
- API 우선순위:
  - 1순위 Crossref
  - 2순위 Semantic Scholar
  - 3순위 publisher API(조건부)

## 8. 라이선스/의존성 정책

### 8.1 코어 경로 정책
- 코어는 permissive(MIT/Apache/BSD) 중심으로 유지한다.
- copyleft 의존 가능성 있는 구성은 plugin/optional path로 격리한다.

### 8.2 현재 상태와 이행
- 현재 ingest 코어는 `pymupdf` 의존이 존재한다.
- 즉시 제거 대신 단계적 이행:
  - 1단계: parser abstraction
  - 2단계: Docling/pypdfium2 backend 옵션 검증
  - 3단계: 코어 default 전환 여부 결정

### 8.3 의존성 동기화
- `requirements.txt`와 `pyproject.toml` 런타임 의존성 불일치를 해소한다.
- 패키지 소스 단일화(권장: `pyproject.toml` 중심) 후 lock 정책 확정.

## 9. PR 통합 로드맵

### PR-A (1주)
- Evidence/Claim schema additive 확장
- unknown 강제 Gate 추가
- UI highlight 매핑 표준 경로(`bbox_pdf` 우선) 반영

수용 기준:
- 기존 테스트 통과
- `evidence_location_rate` 상승

### PR-B (1~2주)
- parser backend abstraction 도입
- 기본 backend 유지 + docling placeholder backend 추가
- 좌표 변환 유틸/테스트 도입

수용 기준:
- 기존 파이프라인 회귀 없음
- bbox 변환 단위 테스트 추가

### PR-C (2주)
- 표 멀티패스 및 taxonomy 기록
- Pass1/Pass2 결과 비교 및 승격 로직 도입

수용 기준:
- 복잡 표 실패율 감소
- taxonomy 로그 100% 기록

### PR-D (2주)
- anchor-based verify 로그 스키마 구현
- 선택 페이지 클라우드 폴백(옵션) + 예산 정책

수용 기준:
- `PASS/WARN/FAIL/NO_API` 집계 가능
- 폴백 예산 정책 동작 검증

## 10. 운영 지표/게이트
- `schema_valid_rate >= 0.98`
- `evidence_location_rate >= 0.90`
- `math_consistency_fail_rate <= 0.01`
- `fallback_rate` 추이 관리(초기 기준선 설정 후 단계별 강화)
- `ocr_page_ratio` 모니터링

## 11. 리포트3 재검토 정리

### 채택
- IR 우선 고정
- unknown 출구
- 표 멀티패스
- anchor-based verification

### 조건부 채택
- OpenAI-compatible boundary layer 확장
- 서빙 스택 다변화(vLLM/llama.cpp)

### 보류
- Docling 전면 즉시 전환
- 추론 스택 즉시 교체

### 리포트3 대비 최종 통합 변화
- 기존 문서의 "단계적 적용" 방향을 유지하되, parser abstraction을 독립 PR로 분리해 실행 순서를 더 명확히 고정.

## 12. 리포트4 재검토 정리

### 채택
- 구조화 파싱 -> IR 표준화 -> 멀티패스 -> 앵커 검증 -> 선택 페이지 폴백 순서
- 실패 taxonomy 운영
- 페이지 예산 기반 폴백 정책

### 조건부 채택
- Docling core 전환
- 코어 라이선스 재정렬(운영/법무 정책 확정 이후)

### 보류
- 라이선스 정책만 근거로 즉시 코어 교체

### 리포트4 대비 최종 통합 변화
- 리포트4의 PR1~PR3를 현재 코드 구조에 맞춰 PR-A~PR-D로 재배치하고, 호환성 보장을 수용 기준에 명시.

## 13. 즉시 실행 항목 (다음 작업 순서)
1. `EvidenceSpan`/`ScientificClaim` additive 스키마 확장
2. unknown 강제 Gate 구현
3. parser backend abstraction 도입(기본 backend 유지)
4. 표 추출 taxonomy 기록 경로 추가
5. 의존성 파일 동기화

## 14. 참조 문서
- `/Users/jangseongjin/Downloads/deep-research-report-3.md`
- `/Users/jangseongjin/Downloads/deep-research-report-4.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Deep_Research_Report3_Fit_Review_2026-03-05.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Deep_Research_Report4_Fit_Review_2026-03-05.md`

## 15. 구현 상태 업데이트 (2026-03-05)

### 완료
- PR-A: Evidence/Claim 스키마 additive 확장 + unknown 강제 정책 반영 완료.
  - `EvidenceSpan`: `bbox_pdf`, `bbox_pct`, `table_id`, `cell_id`, `unknown_reason` 추가.
  - `ScientificClaim`: `unknown`, `unknown_reason` 추가.
- PR-A: UI highlight 표준 경로 반영 완료.
  - 우선순위: `bbox_pct` -> `bbox_pdf` -> 텍스트 매칭 fallback.
- PR-B: parser backend abstraction 도입 완료.
  - 기본 `fitz_pdfplumber` backend 유지.
  - `docling` backend 실구현 경로(문서 변환/텍스트/마크다운 표 파싱) + 실패 시 자동 fallback 반영.
- PR-C: 표 추출 taxonomy 기록 경로 반영 완료.
  - `table_extraction_pass`, `table_failure_taxonomy`, `fallback_used`, `fallback_pages`를 bootstrap/run meta에 기록.
  - Pass2 OCR 복구(옵션) + Pass3 클라우드 테이블 폴백 실제 호출(OpenAI-compatible, 선택 페이지/예산 제한) 반영.
  - Pass3 품질 게이트 taxonomy(`CELL_COVERAGE_LOW`, `CELL_OVERLAP_HIGH`) 반영.
  - ingest 기본값은 로컬 우선(`enable_cloud_table_fallback=false`, `cloud_table_page_budget=1`)으로 유지.
  - Pass3는 운영자가 명시적으로 활성화한 run에서만 수행.
- PR-D: anchor verify 요약/로그 + API 컨텍스트 반영 완료.
  - `anchor_verify_summary` + `anchor_verify_log`를 run meta에 기록.
  - `anchor_verify_api`(provider/status/reason_codes) 반영.
  - Crossref 우선, 실패 시 Semantic Scholar fallback 연계.
  - verdict별 reason code 표준화(`VERDICT_*`) 반영.
  - verify 런타임 실패 시(`docker_unavailable` 등)도 `anchor_verify_api`/요약/로그 빈 배열을 일관 기록.
  - stats 실행 실패/리플렉션 파싱 실패 시 `UNVERIFIABLE` fallback check를 자동 생성해 `checks=[]` 종료를 방지.
  - tables=0 문서는 verify를 `no_table_data` 단축 경로로 처리해 불필요한 sandbox 실행을 방지.
  - sandbox 이미지에 `numpy/pandas/scipy/statsmodels`를 내장해 계산 검증 런타임 준비.
  - 결과 분류: `PASS/WARN/FAIL/NO_API`.
- 운영 설정/의존성 정리 완료.
  - `IngestConfig` 추가.
  - `pyproject.toml` 런타임 의존성 동기화.
  - LLM local-first 기본 라우팅 정렬.

### 보류/다음 단계
- Docling 전용 구조 객체(cell bbox/page 매핑)까지 직접 활용하는 고정밀 파싱 경로.
- Pass3 클라우드 폴백의 품질 게이트(`CELL_COVERAGE_LOW`, `CELL_OVERLAP_HIGH`)와 비용 대시보드 연동.
- Anchor reason code를 verifier 내부 판정 규칙과 완전 동일 스키마로 통합(현재 `VERDICT_*` 표준화까지 완료).

## 16. 재검증 업데이트 (2026-03-06)
- 로컬 우선 기본값 재확인:
  - `enable_cloud_table_fallback=false`
  - `cloud_table_page_budget=1`
- 배치 검증(12개 문서) 결과:
  - `pass_distribution`: `pass1=12`
  - `total_checks=12`
  - `no_api_ratio=0.9167` (11/12)
  - `no_table_data_ratio=0.5833` (7/12)
- 산출물:
  - `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06.json`
  - `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06.md`
- 해석:
  - 로컬-only 설계는 의도대로 동작한다.
  - 단, DOI 부재/외부 API 미사용으로 `NO_API` 비율이 높아 anchor 검증 심도 개선이 다음 우선순위다.

## 17. DOI/Anchor 재검증 업데이트 (2026-03-06)
- 변경 요약:
  - parser 단계 DOI 추출/정규화 강화(메타 + 초기 본문 스캔).
  - anchor API 컨텍스트 해석에 `doi_hint/source_ref/id_hint` 힌트 경로 추가.
  - job runner에서 문서 메타 DOI/소스 경로를 anchor API 해석기에 전달.
- 30개 문서 fast 배치(ingest + anchor context) 결과:
  - `doc_id DOI ratio=100.00%` (30/30)
  - `metadata DOI ratio=100.00%` (30/30)
  - `anchor no_doi ratio=0.00%` (0/30)
  - `anchor status`: `ok=29`, `unavailable=1`
- 해석:
  - 파일명/본문 패턴 보강 후 `no_doi`는 제거됐다.
  - `1411.2441.pdf`는 arXiv DOI(`10.48550/arXiv.1411.2441`)로 해석되지만 Crossref 미등록으로 `unavailable`로 남는다.
- 산출물:
  - `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06_30_fast.json`
  - `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06_30_fast.md`

## 18. Full Verify Timeout 배치 업데이트 (2026-03-06)
- 실행 방식:
  - 문서별 독립 worker(`subprocess`) + per-doc timeout(80s)
  - worker 내부 단계 제한: reader 20s, stats 25s
- 30개 배치 결과:
  - `completed=30`, `timeout=0`, `error=0`
  - `reader_status: ok=30`
  - `stats_status: skipped_no_claims=30`
  - `doc_id DOI ratio=100.00%`, `anchor no_doi ratio=0.00%`
  - `anchor status: ok=29`, `unavailable=1`
- 해석:
  - timeout 제어 자체는 안정적으로 동작한다.
  - 다만 Reader 결과가 전량 `claims=0`으로 수렴해 통계 재계산 검증(`checks`)은 생성되지 않았다.
  - 다음 우선순위는 Reader claim 추출 안정화(최소 claim floor 정책 or fallback claim seed)다.
- 산출물:
  - `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06_30_full_timeout.json`
  - `/Users/jangseongjin/paperpipe/docs/reports/Local_Batch_Validation_2026-03-06_30_full_timeout.md`
