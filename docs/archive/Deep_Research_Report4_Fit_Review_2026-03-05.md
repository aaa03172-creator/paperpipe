# Deep Research Report 4 검토 및 PaperPipe 맞춤 정리 (2026-03-05)

Status: Historical fit review  
Date: 2026-03-05  
Owner: Repository maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## 1) 결론 요약
- `deep-research-report-4.md`의 핵심 제안(구조화 파싱 -> IR 좌표 표준화 -> 표 멀티패스 -> 앵커 검증 -> 선택 페이지 폴백)은 PaperPipe 고도화 방향과 정합적이다.
- 다만 문서가 전제하는 Docling 중심 전환과 코어 라이선스 재정렬은 현재 코드 대비 변경 폭이 커서, 즉시 전면 적용보다 단계적 전환이 안전하다.
- 우리 상황에서는 "기존 v2 artifact + evidence UI + OCR fallback 기반 확장"이 최적이며, Docling/클라우드 폴백은 기능 플래그로 점진 도입하는 방식이 적합하다.

## 2) 문서 품질 검토 (신뢰도/주의점)
### 강점
- 좌표 포함 Evidence를 LLM 이전 IR에서 고정하자는 원칙은 정확성 관점에서 타당하다.
- 표 추출을 단일 도구가 아닌 멀티패스로 운영하자는 제안은 실무적인 접근이다.
- 값 단위 앵커 검증(PASS/WARN/FAIL/NO_API)은 감사 가능성과 회귀 테스트 설계에 유리하다.

### 주의점
- 인용 형식이 `turnXXsearchYY` 기반이라 외부 감사/법무 근거로는 직접 사용하기 어렵다.
- 문서가 제안하는 라이선스 전략(코어에서 AGPL/GPL 제거)은 방향성은 맞지만, 현재 코드의 PyMuPDF 의존 현실과 마이그레이션 비용이 반영되어 있지 않다.
- PR1~PR3 제안은 유효하나, 현재 스키마/백엔드 인터페이스를 어떻게 깨지 않게 이행할지에 대한 호환 설계가 부족하다.

## 3) 우리 코드베이스와 정합성 매핑
### 이미 갖춘 기반
- 로컬-first 기본값 반영
  - [`/Users/jangseongjin/paperpipe/src/config.py:84`](/Users/jangseongjin/paperpipe/src/config.py:84)
- Artifact v2 + bbox 규약 + stable id
  - [`/Users/jangseongjin/paperpipe/src/contracts/document_artifact_v2.py:7`](/Users/jangseongjin/paperpipe/src/contracts/document_artifact_v2.py:7)
  - [`/Users/jangseongjin/paperpipe/docs/document_artifact_v2.md:30`](/Users/jangseongjin/paperpipe/docs/document_artifact_v2.md:30)
- OCR fallback 경로 존재
  - [`/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:26`](/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:26)
- 프런트 evidence highlight 경로 존재
  - [`/Users/jangseongjin/paperpipe/frontend/src/app/components/PdfPanel.tsx:60`](/Users/jangseongjin/paperpipe/frontend/src/app/components/PdfPanel.tsx:60)
  - [`/Users/jangseongjin/paperpipe/frontend/src/app/lib/mock.ts:837`](/Users/jangseongjin/paperpipe/frontend/src/app/lib/mock.ts:837)

### 핵심 갭
- 파서 계층이 Docling 추상화가 아니라 PyMuPDF+pdfplumber에 고정
  - [`/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:3`](/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:3)
- 표 멀티패스(Camelot/Tabula -> TATR+OCR)와 실패 taxonomy가 코드화되어 있지 않음
  - [`/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:234`](/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py:234)
- EvidenceSpan에 `bbox/table_cell_link/unknown_reason` 1급 필드 부재
  - [`/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py:97`](/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py:97)
- Reader가 서버 레벨 constrained decoding이 아니라 `format="json"` 중심
  - [`/Users/jangseongjin/paperpipe/src/agents/reader_agent.py:111`](/Users/jangseongjin/paperpipe/src/agents/reader_agent.py:111)
- 의존성 관리 불일치
  - `requirements.txt`와 `pyproject.toml`의 런타임 의존성이 다름
  - [`/Users/jangseongjin/paperpipe/requirements.txt:14`](/Users/jangseongjin/paperpipe/requirements.txt:14)
  - [`/Users/jangseongjin/paperpipe/pyproject.toml:7`](/Users/jangseongjin/paperpipe/pyproject.toml:7)

## 4) 리포트4 기준 권장 방향
## 방향 A (권장): 점진 이행
- 현재 ingest/reader/verify 체인을 유지하면서, Evidence 정밀도와 표 추출 신뢰도부터 강화한다.
- Docling은 즉시 교체가 아니라 parser backend abstraction 뒤에 옵션 백엔드로 붙인다.

## 방향 B (비권장): 전면 교체
- Docling 전환, 표 멀티패스, 클라우드 폴백, 검증 체계를 한 번에 바꾸면 회귀 리스크가 크다.

## 5) 실행 계획 (리포트4 적응형 PR1~PR3)
### PR1: Parser/IR 인터페이스 확장 (무중단)
- `IngestAgent`에 parser backend 인터페이스 추가(`fitz_pdfplumber`, `docling`)
- 기본값은 현행 유지(`fitz_pdfplumber`), Docling은 feature flag로만 활성
- `bbox_pt_tl` 표준과 변환 유틸을 공통 모듈화

수용 기준:
- 기존 회귀 테스트 유지
- 좌표 변환 단위 테스트 추가

### PR2: Table 멀티패스 + 실패 taxonomy
- Pass-1: 현행 pdfplumber + (옵션) Camelot
- Pass-2: OCR 기반 복구 경로 강화
- taxonomy 기록: `NO_TABLE_FOUND`, `LOW_ACCURACY`, `BBOX_MISMATCH`, `OCR_LOW_CONF` 등

수용 기준:
- 복잡 표 케이스에서 evidence 링크율 상승
- 실패 사유가 `run_meta/bootstrap_meta`에 구조적으로 남음

### PR3: 앵커 검증 + 선택 페이지 폴백
- Crossref/S2 기반 앵커 검증 로그 스키마 추가
- 클라우드 폴백은 선택 페이지 + 페이지 예산 기반으로 제한
- NO_API를 정상 상태로 분류하고 지표화

수용 기준:
- 검증 로그 재현 가능
- 예산 초과 시 폴백 차단 정책 동작

## 6) 즉시 우선순위 Top 5
1. `EvidenceSpan`에 bbox/table link/unknown reason 확장
2. claim 추출 단계에서 evidence 부재 시 unknown 강제
3. 표 추출 실패 taxonomy를 표준 reason code로 저장
4. parser backend 추상화 초안 추가(기본 구현은 기존 유지)
5. 의존성 파일(`requirements`/`pyproject`) 동기화

## 7) 채택/보류 판정
- 채택:
  - IR 좌표 표준화
  - 표 멀티패스
  - 앵커 기반 검증 로그
  - 선택 페이지 폴백
- 조건부 채택:
  - Docling 코어 전환(backend abstraction 이후)
  - 라이선스 재정렬(배포 정책 확정 후)
- 보류:
  - 전면 교체형 리팩터(한 번에 스택 교체)

## 8) 메모
- 본 문서는 `/Users/jangseongjin/Downloads/deep-research-report-4.md`를 검토해, 현재 PaperPipe 구현 상태(2026-03-05)에 맞춰 실행 우선순위로 재구성한 내부 정리다.

## 9) 통합안 반영 메모 (2026-03-05)
- 통합 최종 설계 기준 문서: `/Users/jangseongjin/paperpipe/docs/archive/Deep_Research_Integrated_Final_Design_2026-03-05.md`
- 본 문서 제안 중 통합안 반영 상태:
  - 채택: 파싱->IR->멀티패스->검증->선택 페이지 폴백 순서, 실패 taxonomy
  - 조건부 채택: Docling core 전환, 라이선스 재정렬
  - 보류: 전면 교체형 리팩터
- 2026-03-06 재검토:
  - Pass3 클라우드 폴백은 기본 OFF, 명시적 활성화 run에서만 수행하도록 운영 원칙 확정.
  - 12개 문서 배치 검증 결과를 통합 설계 문서 16장에 반영 완료.
  - DOI/anchor 강화 후 30개 fast 배치에서 `ok=29`, `unavailable=1`, `no_doi=0`으로 anchor API 가용성 개선 확인.
  - 30개 full-timeout 배치에서 worker timeout 제어는 안정적이었으나, Reader claim 생성 안정화가 후속 과제로 확인됨.
