# 안티그래비티 제안: 데이터 식별자 발급 및 추적성 확보 방안 (개정판)

본 문서는 PaperPipe 시스템의 학술 데이터(PDF 및 서지 메타데이터) 식별용 고유 식별자(`userpdf-[Hash]`) 발급 체계에 대한 검토 내용과 실제 코드베이스 현황, 장기적인 확장성(Scalability) 및 물리적 추적성(Traceability) 확보를 위한 개선안, **데이터베이스 및 동기화 설계 결함**, **AI 기반 논문 검토 및 게이팅 기준(Gating Criteria)의 정밀 진단**, **인프라/성능 병목 요인**, **마크다운 프론트매터(Frontmatter) 스키마 불일치 문제**, 그리고 **페르소나 및 프로필 설정의 침묵적 무시 및 정보 노출 위험**을 정리한 통합 제안서입니다.

> **2026-05-24 Codex 재검증 메모**
>
> 이 문서는 현재 런타임의 canonical specification이 아니라, 코드 근거를 동반한 제안/검토 문서입니다. PaperPipe의 현재 운영 기준은 `docs/Lattice_v3_Master_Spec.md`, `docs/PERSONA_MODE_BOUNDARY.md`, `src/db_utils.py`의 런타임 DB/state 계층, 그리고 FastAPI/Pydantic 계약입니다. 아래 이슈 중 DB 스키마, API 응답, persisted artifact shape, frontmatter 계약을 바꾸는 항목은 별도 RFC/PR에서 호환성 영향과 테스트를 함께 다뤄야 합니다.
>
> 재검증 결과, PDF 업로드의 `userpdf-{sha1[:16]}` 발급은 현재 코드 기준 사실이며, 아래의 코드 결함 항목들은 Sprint 1-20에서 PR-sized 수정으로 해소, 부분 완화, 또는 compatibility-wrapper 수준까지 축소했습니다. 남은 항목은 proposal/RFC 성격의 장기 개선 과제(예: profile/gate 정책 고도화, institutional proxy 설정 discoverability, legacy compatibility retirement, artifact cleanup 계약화)입니다.
>
> 아래 각 항목의 `내용`/`문제점`은 원문 검토 당시의 결함 설명입니다. `구현 상태`와 `남은 작업`이 함께 있는 항목은 구현 상태가 현재 기준이며, 남은 작업만 후속 범위로 봐야 합니다.
>
> 다음 항목은 **부분 수정 또는 문서 보정 필요**: PDF binary hash 방식은 파일명/경로 독립성은 강하지만, 동일 논문의 다른 PDF 바이너리(워터마크, preprint/final version, metadata 차이)까지 동일 ID로 묶는 것을 "완벽 보장"하지는 않습니다. 기관 프록시 URL은 Sprint 21에서 `system.institutional_proxy_url` 설정 필드와 기존 `PAPERPIPE_INSTITUTIONAL_PROXY` fallback으로 정리했습니다.
>
> **Sprint 1 구현 상태:** `codex/antigravity-proposal-refresh` 브랜치에서 imported note alias에 `paper_id`를 추가했고, Obsidian study/clinical 템플릿은 `paper_id`/`id`가 있을 때 frontmatter `id`를 기록합니다. `process_daily_slots`의 Obsidian/RIS/DB 출력 실패는 더 이상 silent pass하지 않고 warning 로그를 남깁니다. `retraction.py`는 Crossref assertion value가 boolean `true`뿐 아니라 문자열 `"true"`일 때도 철회 신호로 처리합니다. DOI 중복 조회는 normalized DOI exact query를 먼저 시도하고, 레거시 접두사 값은 기존 scan fallback으로 유지합니다. ArXiv 수집은 더 이상 ArXiv ID를 `doi` 필드에 저장하지 않고, 실제 `arxiv_doi`/`doi` 값이 있을 때만 DOI로 저장합니다. `watcher.py`는 고정 `time.sleep(1)` 대신 downloads watcher의 stable-file 대기를 재사용합니다.
>
> **Sprint 2 구현 상태:** 직접 PDF import에서 추출한 DOI가 기존 paper row와 일치하면 더 이상 409로 차단하지 않고, 기존 canonical `paper_id`를 유지한 채 새 content-hash PDF 파일 경로와 Obsidian note 경로를 병합합니다. DOI 기반 `paper_id`에는 `/`가 포함될 수 있으므로 `/papers/{paper_id}/pdf` 라우트는 path parameter로 보강했습니다.
>
> **Sprint 3 구현 상태:** `save_paper_state`는 기존 `papers.ris_path` 컬럼이 있을 때 RIS export 결과 경로를 저장할 수 있습니다. `process_daily_slots`와 local PDF watcher는 `export_to_ris(...)`가 반환한 경로를 DB state 저장 호출로 전달합니다. RIS 파일 배치/동시성 문제는 Sprint 8에서 per-paper RIS atomic replace로 후속 해소했습니다.
>
> **Sprint 4 구현 상태:** canonical `src/fetch/pubmed.py`와 legacy `src/fetchers.py`의 PubMed ESearch 호출은 `term`을 URL 문자열에 직접 보간하지 않고 `requests.get(..., params=...)`로 전달합니다. `&`, `#`, 공백 같은 특수 문자가 검색식을 깨뜨리지 않도록 회귀 테스트를 추가했습니다.
>
> **Sprint 5 구현 상태:** `BibliometricScorer`의 미구현 venue 점수는 더 이상 모든 논문에 `0.5` 중립 보너스를 주지 않습니다. ISSN/SJR 등 명시적 venue-quality source가 연결될 때까지 `venue_score = 0.0`으로 두고 기존 가중치 구조만 유지합니다.
>
> **Sprint 6 구현 상태:** deprecated `src.db.save_paper_state`의 독립 SQL 구현을 제거하고 canonical `src.db_utils.save_paper_state`로 위임하도록 변경했습니다. legacy `src.db` 모듈 자체는 runs/embeddings 등 호환 API 때문에 남아 있지만, paper state 저장의 DOI 정규화와 non-DOI 처리 계약은 canonical 경로를 따릅니다.
>
> **Sprint 7 구현 상태:** deepread runner는 실제 profile hint가 생성된 경우에만 `"Profile context applied"` 이벤트와 `persona_applied` bootstrap flag를 남깁니다. `/jobs/deepread` API는 unknown `profile_id`를 400으로 거부합니다. Profile notes의 로컬 절대 경로는 YAML 원본을 보존하되 `/personas` 응답과 deepread prompt hint 표면에서 masking합니다.
>
> **Sprint 8 구현 상태:** `export_to_ris`는 더 이상 일별 공용 RIS 파일에 append하지 않습니다. 각 논문은 `export/ris/{stable-id}.ris` 형태의 독립 파일로 atomic replace 저장되며, `ris_path`에는 해당 per-paper RIS 파일 경로가 기록됩니다.
>
> **Sprint 9 구현 상태:** local PDF watcher는 더 이상 legacy `src.fetchers.fetch_pubmed`를 호출하지 않고 canonical `src.fetch.pubmed.PubMedFetcher`를 사용합니다. 이 시점에는 `src/fetchers.py` 자체가 아직 독립 호환 모듈로 남아 있어 완전 제거/축소가 별도 cleanup 단계로 남았습니다.
>
> **Sprint 10 구현 상태:** `make_runtime_paper_id(file_path=...)`는 파일이 실제로 존재하면 경로 문자열이 아니라 파일 내용 SHA-1 앞 16자리로 `userpdf-{hash}`를 생성합니다. 파일이 없거나 읽을 수 없을 때만 기존 `file:{path_hash}` fallback을 유지합니다.
>
> **Sprint 11 구현 상태:** `process_daily_slots`가 생성하는 `feedback_json`은 이제 `confidence`, `soft_tags`, `hard_tags`를 최상위에 항상 포함하여 `PaperTagging` 기본 계약으로 검증 가능합니다. `selection`, `escalation`, `clinical_data`, `intake_override_log`, 기관 proxy link 같은 부가 sidecar 필드는 기존처럼 같은 JSON 객체에 병합됩니다.
>
> **Sprint 12 구현 상태:** `exporter.py`의 스마트 덮어쓰기 비교는 DB `updated_at`을 UTC aware datetime으로 정규화하고, 파일 `mtime`도 `datetime.fromtimestamp(..., tz=timezone.utc)`로 비교합니다. naive DB timestamp는 SQLite/CURRENT_TIMESTAMP 계열의 UTC-like 값으로 해석하고, `Z` 접미사도 `+00:00`으로 처리합니다.
>
> **Sprint 13 구현 상태:** `src/fetchers.py`의 PubMed 독립 구현을 제거하고 deprecated compatibility wrapper로 축소했습니다. `_esearch_pubmed`, `_efetch_pubmed`, `fetch_pubmed`는 모두 canonical `src.fetch.pubmed.PubMedFetcher`로 위임하며, 호출 시 `DeprecationWarning`을 냅니다.
>
> **Sprint 14 구현 상태:** `process_daily_slots`의 기본 상태 결정은 더 이상 직접 confidence threshold 분기를 쓰지 않고 `GateEngine.evaluate(require_evidence=True)` 결과를 사용합니다. 고신뢰도라도 evidence가 없으면 `PENDING_REVIEW`/`EVIDENCE_MISSING`으로 남으며, escalation 승인만 명시적으로 `APPROVED`로 승격합니다.
>
> **Sprint 15 구현 상태:** ProfileChatAgent는 JSON code fence를 제거한 뒤 `PatchRequest`를 검증합니다. PubMed ESearch/EFetch는 NCBI `tool`과 설정된 contact email을 params로 전달하고, EFetch는 ID 목록을 chunk 처리합니다. ArXiv fetcher는 PubMed field tag를 제거하고 `published_parsed`가 없는 entry를 건너뜁니다. `db_utils` SQLite 연결은 명시 timeout을 사용하며, processor gate feedback parsing/schema 실패는 warning 로그와 traceback을 남깁니다.
>
> **Sprint 16 구현 상태:** `src/db_utils.py`는 SQLite 연결에 `busy_timeout`을 설정하고, lock/busy `OperationalError`에 한해서 bounded exponential backoff 재시도를 수행합니다. 핵심 paper state/status, Zotero sync, run stats, reconciliation write 경로의 SQL 실행 및 commit은 공통 retry helper를 통과하며, 최종 lock 실패는 error 로그로 승격합니다.
>
> **Sprint 17 구현 상태:** `src/processor.py`의 남은 silent fallback 경로를 재점검해 slot classification, daily-slot gate JSON parse, feedback JSON merge, local PDF metadata parse, optional source/score fallback에 로그를 추가했습니다. Output persistence, clinical extraction, escalation, bibliometric scoring 실패 로그도 traceback을 보존합니다.
>
> **Sprint 18 구현 상태:** `/paper-notes/import-pdf`는 PDF parsing/DB write를 event loop에서 직접 실행하지 않고 `anyio.to_thread.run_sync(...)`로 worker thread에 격리합니다. `process_daily_slots`는 `system.check_retraction_on_ingest`가 켜져 있고 DOI가 있을 때 Crossref retraction check를 실행해 retracted paper를 `QUARANTINED`로 저장하고 `is_retracted`를 표시합니다. `sync_zotero_to_db`는 장기 write lock을 줄이도록 기본 50개 write 단위 batch commit을 수행합니다.
>
> **Sprint 19 구현 상태:** Paper Notes 인덱스 빌드 경로는 frontmatter를 읽을 때 기존 `papers.paper_id` 행에 한해 `doi`, `obsidian_path`, `reading_status`, 허용된 처리 상태(`NEW`/`INDEXED` 등)를 보수적으로 역동기화합니다. 임의 노트에서 새 canonical DB 행을 만들지 않으며, `Inbox` 같은 읽기 상태는 pipeline `status`로 덮어쓰지 않습니다. 기존 인덱스 캐시는 format version bump로 한 번 무효화됩니다.
>
> **Sprint 20 구현 상태:** `PaperProcessor.run(...)`의 3연속 handler 예외는 더 이상 같은 run의 나머지 eligible 단계를 즉시 중단하지 않습니다. 실패 row는 기존처럼 `FAILED`로 격리하고 threshold 도달은 warning으로 남긴 뒤, 현재 pass의 뒤쪽 단계까지 계속 진행합니다. 단, 실패만 있고 처리 성공이 없으면 기존처럼 재시도 churn을 피하기 위해 run을 종료합니다.
>
> **Sprint 21 구현 상태:** 기관 프록시 설정 discoverability를 개선했습니다. `SystemConfig`와 `config.example.yaml`에 `institutional_proxy_url`을 명시했고, 기존 `PAPERPIPE_INSTITUTIONAL_PROXY`는 호환 fallback으로 유지합니다. 프록시 prefix가 없으면 더 이상 직접 DOI URL을 `institutional_proxy_url`로 저장하지 않습니다.

---

## 1. 실제 코드베이스 현황 분석 (Ground Truth)

현재 PaperPipe 코드베이스를 분석한 결과, 제안된 구조의 많은 부분이 이미 최적화된 방식으로 구현되어 있습니다.

### ① PDF 임포트 식별자 생성 방식
* **파일 위치:** [paper_notes.py](file:///Users/jangseongjin/paperpipe/backend/routers/paper_notes.py#L982-L983)
* **현황:** 사용자가 로컬 PDF를 업로드하면, 시스템은 파일명이나 데이터베이스 일련번호가 아닌 **PDF 파일 바이너리 내용 전체에 대한 SHA-1 해시값**을 생성하여 앞 16자리를 활용합니다.
  ```python
  digest = hashlib.sha1(payload).hexdigest()
  content_paper_id = f"userpdf-{digest[:16]}"
  ```
* **평가:** 파일명이 변경되거나 데이터베이스 인스턴스가 달라지더라도 동일한 PDF 파일이라면 **항상 동일한 식별자**를 도출하는 결정론적(Deterministic)이고 불변인(Immutable) 설계가 이미 적용되어 있습니다.

### ② DOI 기반 중복 방지 및 병합 (Idempotency)
* **파일 위치:** [db_utils.py](file:///Users/jangseongjin/paperpipe/src/db_utils.py#L380-L389)
* **현황:** `save_paper_state` 호출 시, 새로 임포트하려는 PDF의 DOI가 기존 데이터베이스에 존재하는 논문의 정규화된 DOI와 일치하면, 기존에 저장되어 있던 `paper_id`로 자동 병합 및 업데이트 처리가 수행됩니다.
  ```python
  if "paper_id" in columns and "doi" in columns and doi_value:
      cursor.execute(
          "SELECT paper_id, doi FROM papers WHERE doi IS NOT NULL AND paper_id <> ?",
          (identifier,),
      )
      for existing in cursor.fetchall():
          if normalize_doi(str(existing["doi"] or "")) == doi_value and existing["paper_id"]:
              identifier = str(existing["paper_id"])
              break
  ```

### ③ Zotero 연동 식별자 체계
* **파일 위치:** [db_utils.py](file:///Users/jangseongjin/paperpipe/src/db_utils.py#L610)
* **현황:** Zotero와 연동된 항목은 Zotero의 `citationKey`(예: 저자명+연도)를 `paper_id`로 취급하며, 마찬가지로 DOI 매핑을 통해 로컬 PDF 임포트 내역과 유기적으로 동기화됩니다.

---

## 2. 검토 의견 및 아키텍처 비교

### 사용자 제안안 vs 현재 구현 방식 비교

| 비교 항목 | 사용자 제안안 (DS PK, 파일명, RIS 조합) | 현재 코드베이스 방식 (PDF 콘텐츠 해시 + DOI 정규화) |
| :--- | :--- | :--- |
| **식별자 안정성** | **취약:** PDF 파일명이 바뀌거나 RIS 메타데이터 오타를 수정하면 해시가 변경되어 기존 링크(`[[userpdf-hash]]`)가 깨짐. | **매우 우수:** 파일 이름이나 경로가 바뀌어도 PDF 본문 자체가 변경되지 않으면 ID가 영구히 유지됨. |
| **분산 Scalability** | **취약:** DB PK(Auto-increment ID)는 데이터베이스마다 다르므로 분산 환경이나 협업 시 충돌 발생. | **강함:** 중앙 DB 없이 동일한 PDF 바이너리는 같은 ID를 얻는다. 단, 동일 논문의 다른 PDF 바이너리/버전까지 동일 ID로 묶지는 못한다. |
| **메타데이터 편차** | **취약:** 가져온 곳에 따라 RIS 파일 서식이 다르면 다른 해시가 생성됨. | **안전:** 표준 식별자인 DOI를 정규화하여 중복 매핑 및 병합 도구로 활용. |

### 최종 결론 및 제안
현재 코드베이스의 **"PDF 바이너리 해시(SHA-1 16자) + DOI 정규화 병합"** 구조는 사용자 제안안(DB PK, 파일명 기반)보다 설계 결합도(Decoupling) 및 파일명/경로 독립성 측면에서 더 안정적인 기준입니다. 다만 콘텐츠 해시만으로는 DOI 기반 bibliographic identity, Zotero citation key, ArXiv/preprint version, 동일 논문의 서로 다른 PDF 파일을 모두 하나의 canonical identity로 병합할 수 없으므로, 장기적으로는 `paper_id`와 physical file binding/version mapping을 분리하는 설계가 필요합니다.

따라서 신규 툴을 개발하거나 연동할 때는 **현재 코드베이스 방식(콘텐츠 해시 기반 발급 및 DOI 정규화 역참조)을 기본 규격으로 유지**하되, `paper_id`, DOI, Zotero key, `pdf_path`, RIS path, Obsidian note path의 역할을 혼합하지 않도록 별칭/바인딩 계층을 별도 RFC로 다뤄야 합니다.

---

## 3. 구조도 아키텍처

### 1단계 제안 구조 (기존 설계 기반 흐름)
기존의 가변성/종속성 한계가 존재하기 전, 직관적인 입력 기반의 발급 흐름도입니다.

![기존 설계 기반 흐름도](data_trace_id.png)

### 2단계 제안 구조 (불변성 확보 개선 설계 - 현재 코드베이스 사상 반영)
가변 요소(파일명, 로컬 PK)를 제거하고 PDF 본문 해시와 정규화된 DOI를 조합하여 불변성과 상호 운용성을 확보한 실제 코드베이스 기반의 개선 아키텍처입니다.

![개선안 설계 기반 흐름도](improved_hash_slide.png)

> **그림 주의:** 위 그림의 `SHA-256` 표기는 장기 개선 방향을 설명하는 개념도 표기입니다. 현재 코드의 실제 PDF content ID 계약은 `userpdf-{sha1[:16]}`이며, 해시 알고리즘/슬라이스 길이 변경은 아래 "해시 충돌 방지를 위한 식별자 크기 확장" 항목처럼 별도 호환성 RFC가 필요합니다.

---

## 4. 연동 시 주의 및 안전 규칙 (Safety Constraints)

1. **Zotero DB 직접 쓰기 금지 (Master Rule 준수)**
   * Zotero에 고유 식별자를 기록할 때는 `zotero.sqlite` 파일을 직접 수정해서는 안 됩니다.
   * `export/` 폴더에 고유 ID(`userpdf-hash`)가 포함된 `.ris` 또는 `.bib` 파일을 생성한 뒤 Zotero가 이를 가져오도록(Import) 설계해야 DB 오염을 방지할 수 있습니다.
2. **Obsidian Wiki-link의 네이티브 연동 한계와 개선 방안**
   * **현재 코드 분석:** [storage.py](file:///Users/jangseongjin/paperpipe/src/skills/storage.py#L210-L238)와 [paper_notes.py](file:///Users/jangseongjin/paperpipe/backend/routers/paper_notes.py#L861) 확인 결과, Python 백엔드 내부에서는 노트를 찾기 위해 frontmatter의 `id` 필드를 정상 검색합니다. 하지만, markdown 노트 생성 시 `aliases` 리스트에는 오직 논문 제목(`title`)만 포함됩니다.
   * **문제점:** 사용자가 Obsidian 앱 안에서 `[[userpdf-hash]]`와 같은 wiki-link로 해당 논문 노트를 가리키려 할 때, Obsidian 인덱서에 해당 식별자가 별칭(alias)으로 지정되어 있지 않으므로 **새로운 빈 노트 생성을 유도하거나 링크가 정상 연결되지 않습니다.**
   * **2026-05-24 구현 상태:** [paper_notes.py](file:///Users/jangseongjin/paperpipe/backend/routers/paper_notes.py)에서 imported note markdown 생성 시 **`aliases` 리스트에 `paper_id`를 함께 추가**하도록 변경했습니다.
     ```python
     # 변경 전
     "aliases": [title]
     
     # 변경 후 (Obsidian 네이티브 별칭 지원)
     "aliases": [title, paper_id]
     ```

---

## 5. 추가 발견 아키텍처 결함 및 충돌 (Additional Architectural Gaps)

실제 시스템의 동기화 및 쿼리 동작을 정밀 분석한 결과, 아래와 같은 추가적인 결함과 충돌 지점이 식별되었습니다.

### ① PDF 직접 임포트와 Zotero 연동 간의 DOI 충돌 (HTTP 409) 현상
* **파일 위치:** [paper_notes.py:1001-1006](file:///Users/jangseongjin/paperpipe/backend/routers/paper_notes.py#L1001-L1006)
* **내용:** 기존 구현에서는 사용자가 이미 Zotero 연동 등을 통해 DOI 정보가 등록된 상태에서, 동일한 논문의 PDF 파일을 마우스 드래그 등으로 직접 임포트(`import-pdf`)하려고 하면 아래 예외가 발생하며 업로드가 완전히 차단되었습니다.
  ```python
  existing_paper_id = _find_imported_paper_id_by_doi(doi)
  if existing_paper_id and existing_paper_id != paper_id:
      raise HTTPException(
          status_code=409,
          detail=f"A paper with DOI {doi} already exists.",
      )
  ```
* **문제점:** 동일 논문인데 임포트 경로가 달라 ID가 불일치(`zotero:citationKey` vs `userpdf-hash`)하게 되고, 결국 PDF 파일을 기존 논문에 병합/연결하지 못한 채 사용자에게 오류만 반환하는 심각한 UX 장벽이 존재했습니다.
* **2026-05-24 재확인:** 이 동작은 `tests/test_paper_notes_api.py`의 `test_paper_notes_import_pdf_rejects_duplicate_existing_doi`에서 409 계약으로 고정되어 있었습니다. 즉 구현만의 버그라기보다, 테스트 계약을 포함해 "중복 DOI는 차단"으로 정해진 상태였습니다.
* **2026-05-24 구현 상태:** 409 계약을 `test_paper_notes_import_pdf_merges_duplicate_existing_doi`로 교체했습니다. 이제 기존 DOI row가 있으면 `import-pdf` 응답의 `paper_id`는 기존 canonical row를 반환하고, PDF 파일은 content hash 기반 `userpdf-{hash}.pdf` 이름으로 저장되며, DB의 `pdf_path`/`obsidian_path`가 기존 row에 업데이트됩니다.
* **후속 주의:** 이 수정은 신규 import note를 생성하고 그 note path를 기존 row에 연결합니다. 이미 canonical Obsidian note가 있는 Zotero/Paper Notes 항목과의 note 병합 정책은 별도 UX/API 계약으로 다뤄야 합니다.

### ② 로컬 파일 경로 기반 ID 생성과 콘텐츠 해시 ID의 이중성
* **파일 위치:** [identity.py:34-37](file:///Users/jangseongjin/paperpipe/src/services/identity.py#L34-L37)
* **내용:** 기존 CLI 환경이나 파일 실행 콘텍스트(`make_runtime_paper_id`)에서 로컬 PDF 파일 경로를 통해 식별자를 파싱할 때, 파일 내용 해시가 아닌 **물리적 파일 경로 문자열을 해싱**하여 `file:{path_hash}` ID를 부여했습니다.
  ```python
  if lowered.startswith("file:"):
      value = text.split(":", 1)[1].strip()
      stable = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
      return f"file:{stable}"
  ```
* **문제점:** 백엔드 API 업로드를 거친 파일은 `userpdf-{content_hash}`를 가지지만, 로컬에서 경로로 직접 실행한 분석 작업은 `file:{path_hash}`를 가져 다른 ID 체계를 가졌습니다. 동일한 논문 파일에 대해 시스템이 **서로 다른 아티팩트 폴더 및 분석 결과를 별도로 관리**하게 되는 일관성 문제가 발생했습니다.
* **2026-05-24 구현 상태:** `make_runtime_paper_id(file_path=...)`는 파일이 존재하면 파일 내용을 chunk로 읽어 `userpdf-{sha1[:16]}`를 반환합니다. 파일이 없거나 읽을 수 없을 때만 기존 `file:{path_hash}` fallback을 유지합니다.
* **개선 제안:** 아직 명시적 `file:...` doc_id를 직접 bridge하는 경로는 path-hash compatibility를 유지하므로, 필요하면 별도 alias/backfill 정책으로 기존 `file:*` artifact를 `userpdf-*`와 연결해야 합니다.

### ③ 데이터베이스 쿼리 비효율성 (메모리 로딩 루프)
* **파일 위치:** [paper_notes.py:920-941](file:///Users/jangseongjin/paperpipe/backend/routers/paper_notes.py#L920-L941)
* **내용:** 기존 `_find_imported_paper_id_by_doi` 함수는 DOI가 존재하는 중복 논문을 확인하기 위해 DB에 존재하는 **모든 논문 레코드를 메모리로 한 번에 불러온 후** Python 루프 내에서 정규화 및 비교 연산을 수행했습니다.
  ```python
  cursor.execute("SELECT paper_id, doi FROM papers WHERE doi IS NOT NULL")
  for row in cursor.fetchall():
      if normalize_doi(str(existing["doi"] or "")) == doi_value: ...
  ```
* **문제점:** 논문 데이터베이스가 수천~수만 건 이상으로 증가할 경우, 단순 PDF 하나를 임포트할 때마다 막대한 메모리와 CPU 낭비가 발생하여 성능이 저하될 수 있었습니다.
* **2026-05-24 구현 상태:** `backend/routers/paper_notes.py`와 `src/db_utils.py`는 normalized DOI exact query를 먼저 수행하고, 과거에 `https://doi.org/...`처럼 저장된 레거시 값만 기존 scan fallback으로 처리합니다.
* **남은 작업:** 다음 단계에서는 `doi` 컬럼 정규화/인덱스 마이그레이션을 별도 DB 호환성 작업으로 다뤄 fallback scan 의존도를 제거해야 합니다.

### ④ Zotero RIS 내보내기 동시성(Race Condition) 및 `ris_path` 스키마 비일관성 문제
* **파일 위치:** [zotero.py:8-19](file:///Users/jangseongjin/paperpipe/src/zotero.py#L8-L19) 및 [db_utils.py:84](file:///Users/jangseongjin/paperpipe/src/db_utils.py#L84)
* **내용:** 기존 `export_to_ris` 함수는 데이터 분석 완료 시 Zotero 연동을 위해 RIS 데이터를 공용 일별 파일(`{today}_import.ris`)에 추가(append) 방식으로 기록했습니다.
* **문제점:**
  1. **동시성 충돌 (Race Condition):** 배치(Batch) 처리나 멀티프로세스로 논문 여러 개가 병렬 분석될 때, 동일한 파일에 동시 접근하여 쓰기를 수행하기 때문에 RIS 포맷이 뒤엉키거나 깨지는 현상이 발생할 수 있었습니다.
  2. **Orphan Schema (방치된 DB 스키마):** SQLite 데이터베이스 스키마에는 `ris_path TEXT` 컬럼이 기획 단계부터 할당되어 있었으나, 실제 `save_paper_state` 구현 시 해당 인자 입력 및 저장 처리 부분이 완전히 누락되어 비어 있는 필드로 유지되고 있었습니다.
* **2026-05-24 구현 상태:** `save_paper_state`에 `ris_path` 입력을 추가했고, `process_daily_slots` 및 local PDF watcher가 `export_to_ris(...)` 반환 경로를 DB 저장 호출에 전달하도록 수정했습니다. 또한 `export_to_ris`는 공용 일별 append 파일 대신 논문별 독립 RIS 파일(`export/ris/{stable-id}.ris`)을 atomic replace로 저장합니다.
* **개선 제안:** 남은 작업은 Zotero import watcher가 새 `export/ris/` 하위 디렉터리를 명시적으로 감시해야 하는지 운영 문서에 반영하고, 필요하면 per-paper RIS 파일의 cleanup/retention 정책을 추가하는 것입니다.

### ⑤ 수집 경로에 따른 마크다운 프론트매터(Frontmatter) 스키마 불일치 문제
* **파일 위치:** [obsidian.py:106-116](file:///Users/jangseongjin/paperpipe/src/obsidian.py#L106-L116) (get_template_study) 및 [obsidian.py:256-266](file:///Users/jangseongjin/paperpipe/src/obsidian.py#L256-L266) (get_template_trial)
* **내용:** 수동 PDF 업로드 경로(`import-pdf`)로 생성된 마크다운에는 `id: paper_id` 프로퍼티가 정상 생성되지만, 기존 스크리닝 분석 파이프라인에서 자동으로 노트를 생성해주는 두 템플릿 코드에는 `id` 필드가 빠져 있었습니다.
* **문제점:** 이종 파이프라인을 거치며 프론트매터 데이터 스키마의 일관성이 무너졌습니다. 특히 DOI가 존재하지 않는 논문의 경우, Obsidian 노트 파일명이 수정되면 `id` 값마저 부재하여 추후 백엔드가 이 노트를 마스터 DB 레코드와 매핑할 때 식별 실패를 유발할 수 있었습니다.
* **2026-05-24 구현 상태:** [obsidian.py](file:///Users/jangseongjin/paperpipe/src/obsidian.py)의 study/clinical 템플릿은 `paper_id` 또는 `id`가 주어질 때 frontmatter `id`를 기록합니다.
* **후속 주의:** 모든 생성 경로에서 `paper_id`가 실제로 전달되는지, 그리고 legacy note backfill이 필요한지는 별도 마이그레이션 검토가 필요합니다.

---

## 6. AI 기반 논문 검토 및 게이팅 기준(Gating Criteria) 정밀 진단

기준을 코드로 구현해 일관된 반복(Repeatability)이 가능해졌으나, 코드 내 판정 논리의 완성도가 부족할 경우 **잘못된 판정을 정교하게 반복**하는 기계적 오판 문제가 발생할 수 있습니다.

### ① LLM 점수 편차(Drift)와 고정 임계값 필터의 충돌
* **파일 위치:** [gates.py:64-71](file:///Users/jangseongjin/paperpipe/src/gates.py#L64-L71) 및 [config.yaml:38-40](file:///Users/jangseongjin/config.yaml#L38-L40)
* **내용:** LLM이 논문 분석 후 부여하는 신뢰도 점수가 설정값(`high: 0.90`, `low: 0.70`)과 고정 비교되어 게이팅 결정이 내려집니다.
  ```python
  def _confidence_decision(self, confidence: float, reasons: List[ReasonCode]) -> GateDecision:
      if confidence >= self.high_threshold:
          return GateDecision.APPROVED
      if confidence < self.low_threshold:
          return GateDecision.QUARANTINED
      return GateDecision.PENDING_REVIEW
  ```
* **문제점:** LLM의 점수 분배는 모델 종류(Ollama Llama3 vs OpenAI GPT-4o), 온도(Temperature) 및 프롬프트의 미세 수정에 크게 의존합니다. 특정 업데이트 후 LLM이 전반적으로 후한 점수(예: 평균 0.95 이상)를 반환하면 **불량 데이터 자동 승인 폭발**이 발생하고, 반대로 짠 점수를 주면 **모든 데이터가 격리(Quarantine)**되어 자동화 흐름이 붕괴됩니다.
* **개선 제안:** 고정 점수 외에 **필수 추출 정보(Claims)의 개수**, **검증 근거(Evidence)의 신뢰성** 등을 가중합산(Weight Sum)하거나 다각도 다면 평가(Score Card) 모델로 로직을 정교화해야 합니다.

### ② 형식적 검증(Key Presence) vs 실질적 검증(Value Validation)의 간극
* **파일 위치:** [gates.py:81-85](file:///Users/jangseongjin/paperpipe/src/gates.py#L81-L85)
* **내용:** 필수 필드 누락 검사 시 JSON 응답 딕셔너리에 단순 키(Key)가 존재하는지만 체크합니다.
  ```python
  required = ["confidence", "soft_tags", "hard_tags"]
  missing = [field for field in required if field not in analysis]
  ```
* **문제점:** LLM이 파싱 오류나 정보 미추출로 인해 `soft_tags: []` (빈 리스트), `hard_tags: {}` (빈 딕셔너리)와 같이 **빈 껍데기 값**을 리턴하더라도 게이팅 엔진은 이를 유효한 응답으로 인지하고 최종 APPROVED 상태로 통과시킬 수 있습니다.
* **개선 제안:** 필수 정보 필드의 실제 데이터 개수가 최소 기준을 만족하는지(예: `len(soft_tags) >= 1`), 내부 주요 속성이 비어있지 않은지 검증하는 **벨류 유효성 체크(Value Validation)** 단계가 강제되어야 합니다.

### ③ 수집 쿼리(Search Query)와 AI 판정 질문(Research Question)의 지향성 불일치
* **파일 위치:** [config.yaml:49-62](file:///Users/jangseongjin/config.yaml#L49-L62)
* **내용:** 각 주제 슬롯(Slot)마다 검색엔진에 던지는 `query` 문자열과 LLM이 논문을 판정하는 `research_question` 지침이 다르게 코딩되어 있습니다.
  * 예: `methods` 슬롯의 수집 쿼리에는 오가노이드(`organoid`), 바이오소재(`biomaterial`) 등 광범위한 실험 재료가 잡히도록 되어 있으나, 정작 AI 판정 가이드라인은 측정 방식 개선 및 샘플 핸들링 개선 위주로 협소하게 정의되어 있습니다.
* **문제점:** 수집된 재료 중심의 논문들이 AI의 기능 중심 가이드라인을 통과하지 못해 불필요한 보류(`PENDING_REVIEW`) 상태로 적체되거나 격리되어 스크리닝 효율이 하락합니다.
* **개선 제안:** 수집 쿼리의 목표 인벤토리 범위와 LLM의 의사결정 연구 질문 가이드라인을 일관되게 정합(Alignment)시키는 설계 싱크 조정이 주기적으로 이루어져야 합니다.

---

## 7. 추가 시스템 및 인프라 관점 정밀 진단 (Additional Infrastructure Diagnostics)

코드가 작동하는 비동기 런타임 및 파일 시스템 수준에서 병목 및 동기화 괴리 요소를 발굴했습니다.

### ① FastAPI 비동기 이벤트 루프 블로킹 문제 (CPU-bound PDF parsing in async route)
* **파일 위치:** [paper_notes.py:2273-2285](file:///Users/jangseongjin/paperpipe/backend/routers/paper_notes.py#L2273-L2285)
* **내용:** 기존 `/import-pdf` 라우트는 `async def` 비동기 함수로 선언되어 있으나, 내부에서 매우 무거운 CPU 연산 및 동기식 파일 I/O를 수행하는 `import_pdf_payload` 함수를 직접(Directly) 호출했습니다.
* **문제점:** `import_pdf_payload` 안에서는 PDF 텍스트 추출(PyPDF 최대 16페이지 스캔), 마크다운 작성, SQLite 쓰기 등이 한꺼번에 실행됩니다. FastAPI의 단일 스레드 비동기 루프에서 이 같은 무거운 동기 함수가 호출되면 **연산이 끝날 때까지 서버 전체가 일시 동결(Freeze)되어 다른 모든 API 요청에 전혀 응답하지 못할 수 있었습니다.**
* **원래 개선 제안:** 동기 함수 실행부를 `anyio.to_thread.run_sync` 또는 `asyncio.to_thread.run_sync`를 사용해 백그라운드 스레드 풀로 격리합니다.
* **2026-05-24 구현 상태:** `/paper-notes/import-pdf`는 업로드 바이트를 읽고 닫은 뒤, `import_pdf_payload(filename=..., payload=...)` 호출을 `anyio.to_thread.run_sync(...)`로 격리합니다. PDF parsing, markdown write, SQLite write가 FastAPI event loop를 직접 점유하지 않도록 회귀 테스트를 추가했습니다.

### ② Obsidian 수동 수정 사항의 SQLite DB 역동기화 부재 (Obsidian-to-SQLite Data Drift)
* **파일 위치:** [paper_notes.py:836](file:///Users/jangseongjin/paperpipe/backend/routers/paper_notes.py#L836) (`_sync_note_frontmatter_to_paper_state`), [paper_notes.py:671](file:///Users/jangseongjin/paperpipe/backend/routers/paper_notes.py#L671) (`_build_index_item` 호출부) 참고
* **내용:** 기존 백엔드는 프론트엔드 출력을 위해 Obsidian 마크다운 파일을 로드하여 임시 JSON 인덱스를 업데이트했지만, 사용자가 Obsidian 앱 안에서 노트의 frontmatter 속성(예: `status`, `doi`, `tags`)을 직접 수정하거나 파일을 삭제하더라도 이 변경 사항을 PaperPipe 마스터 DB인 `state.db` SQLite 테이블로 역방향 반영(Sync-Back)하지 않았습니다.
* **문제점:** Obsidian 파일 시스템과 데이터베이스 테이블 간의 **데이터 괴리(Data Drift)**가 영구히 누적될 수 있었습니다. 상태 관리가 이원화되어 배치 파이프라인 작동 시 심각한 상태 혼선이 생길 수 있습니다.
* **2026-05-24 구현 상태:** [paper_notes.py](file:///Users/jangseongjin/paperpipe/backend/routers/paper_notes.py)의 Paper Notes 인덱스 빌더는 candidate paper note의 frontmatter를 파싱할 때 기존 `papers.paper_id` 행만 갱신하는 보수적 sync-back 기준선을 추가했습니다. 갱신 대상은 normalized DOI, `obsidian_path`, `reading_status`, 그리고 allowlist에 포함된 pipeline `status`로 제한합니다. `Inbox` 같은 노트/읽기 상태는 DB `reading_status` 컬럼이 있을 때만 반영하고 canonical pipeline `status`는 보존합니다.
* **남은 개선 제안:** 파일 와처(Watcher)에서 Obsidian 노트 수정 감지 시, 프론트매터 파싱 내용을 파싱하여 SQLite DB에 실시간 `UPDATE papers`를 적용하는 양방향 동기화 핸들러를 보완합니다.
* **남은 작업:** 실시간 watcher, 삭제 감지, tags/confidence/date_processed 같은 derived/user-facing 필드의 canonical 채택 여부는 아직 별도 RFC/호환성 검토가 필요합니다.

### ③ 프로세서 실패 복구 회복력 및 찌꺼기 파일 누적 문제 (Partial writes & orphan run directories)
* **파일 위치:** [processor.py:611-665](file:///Users/jangseongjin/paperpipe/src/processor.py#L611-L665) (`run` 루프 참고)
* **내용:** 기존 분석 프로세스(`PaperProcessor`)는 구동 시 3번의 연속적인 예외 실패(`consecutive_failures >= 3`)가 발생하면 전체 수집 루프를 전면 중단(Abort)했습니다.
* **문제점:**
  1. **배치 탄력성 부족:** 특정 PDF 파일 깨짐 등으로 연속 실패가 발생하면, 이후 대기 중인 정상 논문들까지 수집이 전면 중단되는 문제를 초래합니다.
  2. **Orphan Artifacts (남겨진 임시 디렉토리):** 분석 도중 예외가 발생해 프로세스가 튕기면, `storage/artifacts/[paper_id]/[run_id]/`에 쓰이다 만 불완전한 부분 아티팩트 파일과 빈 폴더가 영구적으로 지워지지 않고 누적되어 스토리지 용량을 차지합니다.
* **2026-05-25 구현 상태:** [processor.py](file:///Users/jangseongjin/paperpipe/src/processor.py)의 `PaperProcessor.run(...)`은 `_process_step(...)`이 handler 예외를 잡아 row를 `FAILED`로 격리한 뒤에도 같은 pass의 남은 eligible 단계들을 계속 확인합니다. Threshold 도달은 warning 로그로 남기며, 처리 성공이 하나도 없는 pass는 기존처럼 종료되어 무한 재시도를 피합니다.
* **원래 개선 제안:** 중단 스레시홀드를 완화하고 예외 처리 catch 블록에서 작업이 중단된 아티팩트 디렉토리를 깨끗하게 롤백(Clean-up)하는 복구 회복력(Resiliency) 메커니즘을 추가합니다.
* **남은 작업:** 부분 artifact/run directory cleanup은 저장소 계층과 run manifest 계약을 건드리므로 별도 PR에서 소유 경로와 안전한 삭제 기준을 먼저 고정해야 합니다.

### ④ Zotero 일괄 동기화(Bulk Sync) 시 SQLite 락(Locked) 발생 위험
* **파일 위치:** [db_utils.py:610-734](file:///Users/jangseongjin/paperpipe/src/db_utils.py#L610-L734) (`sync_zotero_to_db` 함수)
* **내용:** 기존에는 Zotero에서 추출된 다량의 논문 목록 데이터를 SQLite DB에 마이그레이션할 때, 대량의 조회 및 쓰기 연산을 루프로 실행한 후 맨 마지막에 일괄적으로 `conn.commit()`을 수행했습니다.
* **문제점:** 동기화되는 논문 개수가 많아질수록 단일 트랜잭션이 차지하는 잠금(Write Lock) 시간이 비정상적으로 길어질 수 있었습니다. 이 동기화 트랜잭션이 작동하는 긴 시간 동안, 다른 사용자가 웹 프론트엔드를 통해 읽기 상태를 바꾸거나 PDF를 업로드하려고 하면 SQLite 기본 타임아웃(5초)을 초과하여 `sqlite3.OperationalError: database is locked` 예외가 발생할 수 있었습니다.
* **원래 개선 제안:** 대량 동기화 수행 시 일정 개수(예: 30~50개 단위)마다 분할 커밋(Batch Commit)을 수행해 데이터베이스 잠금을 주기적으로 반환하고, DB 연결 모듈([db_utils.py:278](file:///Users/jangseongjin/paperpipe/src/db_utils.py#L278))에서 `sqlite3.connect` 호출 시 `timeout=30.0`과 같이 커넥션 busy timeout을 안전하게 높여 설정합니다.
* **2026-05-24 구현 상태:** `sync_zotero_to_db`는 write operation 50개마다 batch commit을 수행하고 마지막 잔여 write만 final commit합니다. 이전 Sprint 16의 `timeout=30.0`, `PRAGMA busy_timeout=30000`, lock/busy retry와 함께 장기 write lock 위험을 낮춥니다.

### ⑤ DOI 표현 포맷의 미세 불일치로 인한 DB 조회 누락
* **파일 위치:** [db_utils.py:19-23](file:///Users/jangseongjin/paperpipe/src/db_utils.py#L19-L23) (`_normalized_doi_or_none`) 및 [paper_notes.py:603-611](file:///Users/jangseongjin/paperpipe/backend/routers/paper_notes.py#L603-L611) (`_normalize_doi`)
* **내용:** `db_utils`는 수집된 DOI 정보에서 접두사를 완전히 제거한 순수 번호(`10.xxxx/yyyy`)만 데이터베이스 `doi` 컬럼에 보관합니다. 반면, Obsidian 인덱서 등 백엔드 일부 모듈은 DOI를 출력할 때 항상 URL 프로토콜 접두사(`https://doi.org/10.xxxx/yyyy`)가 붙은 완성형 문자열로 인덱싱합니다.
* **문제점:** 외부 툴이나 내부 추가 로직에서 정규화 함수를 우회하여 DB 쿼리를 다이렉트로 날릴 때, 접두사 유무(`10.xxxx` vs `https://doi.org/...`) 차이로 인해 분명 존재하는 논문임에도 매핑에 실패하여 데이터가 중복 인서트되는 불일치 오류가 발생할 수 있습니다.
* **개선 제안:** 내부 모든 컴포넌트 간에 DOI를 활용할 때 항상 명시적인 `normalize_doi` 헬퍼 함수를 필수 거치도록 규정(Lint 및 가이드)하거나, 데이터베이스 저장 값과 프론트매터 출력 규격을 동일한 완전형태(혹은 순수번호형태)로 통일해야 합니다.

---

## 8. 추가 발굴 이슈: 예외 처리 및 파이프라인 스키마 분기

### ① 파이프라인 출력 경로에서의 사일런트 예외 삼킴 (Silent Exception Swallowing)
* **파일 위치:** [processor.py:1058-1081](file:///Users/jangseongjin/paperpipe/src/processor.py#L1058-L1081)
* **내용:** 기존 `process_daily_slots` 함수 내 Obsidian 노트 저장, RIS 내보내기, DB 최종 저장이라는 세 가지 핵심 출력 단계가 각각 독립적인 `try/except Exception: pass` 블록으로 감싸여 있었습니다.
  ```python
  try:
      save_paper_to_obsidian(row, config, extraction=clinical_extraction)
  except Exception:
      pass
  try:
      export_to_ris(row, Path(config.paths.export_dir))
  except Exception:
      pass
  try:
      save_paper_state(...)
  except Exception:
      pass
  ```
* **문제점:** 분석 결과(tags, clinical_data, confidence)가 성공적으로 산출되었더라도 Obsidian 노트 생성 실패, RIS 내보내기 실패, 또는 DB 저장 실패 시 **어떤 로그도 기록되지 않은 채 조용히 넘어갔습니다.** 결과적으로 논문이 DB에 존재하지 않는데도 UI에서 `APPROVED` 상태처럼 보이거나, Obsidian 노트가 생성되지 않은 채 파이프라인만 정상 완료된 것으로 보고되는 **불완전 상태(Phantom Success)**가 발생할 수 있었습니다. 특히 `save_paper_state` 실패는 파이프라인 재실행 시 동일 논문의 중복 처리를 유발할 수 있었습니다.
* **2026-05-24 구현 상태:** Obsidian 저장, RIS export, DB state 저장 실패는 paper id와 exception context를 포함해 warning 로그로 남습니다. Sprint 17에서 processor fallback 경로의 남은 silent exception들도 warning/traceback 보존으로 정리했습니다.
* **남은 작업:** `save_paper_state` 실패를 재처리 큐에 등록하는 보상 트랜잭션은 아직 별도 workflow/RFC 범위로 남아 있습니다.

### ② 두 파이프라인 간 `feedback_json` 스키마 분기 문제 (Dual-pipeline Schema Drift)
* **파일 위치:** [processor.py:753-756](file:///Users/jangseongjin/paperpipe/src/processor.py#L753-L756) (`PaperProcessor._step_analyze`) vs [processor.py:1036-1054](file:///Users/jangseongjin/paperpipe/src/processor.py#L1036-L1054) (`process_daily_slots`)
* **내용:** PaperPipe에는 두 개의 독립적인 처리 파이프라인이 공존합니다.
  - **`PaperProcessor` (상태 머신 방식):** `_step_analyze`에서 태깅 결과 전체를 그대로 `json.dumps(tags_data)`하여 `feedback_json`에 저장합니다. 이후 `_step_gate`에서 이를 역파싱하여 `PaperTagging.model_validate(analysis)`로 검증합니다.
  - **`process_daily_slots` (레거시 배치 방식):** `feedback_json`에 태깅 데이터 외에도 `selection`(후보 선택 근거), `escalation`(에스컬레이션 결과), `clinical_data`, `intake_override_log` 등 다수의 추가 필드를 병합하여 저장합니다.
* **문제점:** 기존에는 두 파이프라인이 생성한 `feedback_json`의 구조가 완전히 달랐습니다. `reconcile_approved_decisions`([db_utils.py:887](file:///Users/jangseongjin/paperpipe/src/db_utils.py#L887))나 뷰어 레이어 등 `feedback_json`을 소비하는 코드가 두 포맷 중 어느 한 가지를 가정하고 파싱하면, 나머지 파이프라인 산출물에서 **키 미스 또는 잘못된 필드 해석**이 발생할 수 있었습니다. 특히 레거시 파이프라인은 게이트 로직(GateEngine)을 완전히 우회하고 임계값 비교만으로 상태를 결정하여, 두 경로에서 동일 논문에 대해 다른 판정이 내려질 수 있었습니다.
* **원래 개선 제안:** `feedback_json`의 최상위 스키마를 명시적인 Pydantic 모델(`FeedbackPayload`)로 고정하고, 태깅/에스컬레이션/임상 데이터 등을 각각 명명된 서브 필드로 분리하여 두 파이프라인 모두 동일한 스키마를 준수하도록 통일해야 합니다. 레거시 파이프라인의 직접 임계값 분기도 `GateEngine.evaluate()`를 공유 경유하도록 리팩토링해야 합니다.
* **2026-05-24 구현 상태:** `process_daily_slots`는 LLM 분석 성공 여부와 무관하게 `feedback_json` 최상위에 `confidence`, `soft_tags`, `hard_tags`를 저장합니다. 이로써 레거시 배치 산출물도 `PaperTagging.model_validate(...)`로 읽을 수 있으며, 기존 sidecar 필드들은 additive metadata로 유지됩니다.
* **2026-05-24 추가 구현 상태:** `process_daily_slots`의 status 결정은 `GateEngine.evaluate(require_evidence=True)` 결과를 사용합니다. `gate_decision`/`gate_reason`도 row와 `feedback_json`에 남기며, escalation 승인만 기존 정책대로 `APPROVED`로 승격합니다.
* **남은 작업:** `feedback_json` 전체를 별도 Pydantic 모델로 고정해 sidecar 필드까지 정식 계약화하는 작업은 별도 schema/RFC로 남아 있습니다.

### ③ 기관 프록시 설정 경로의 discoverability 문제 (Institutional Proxy Configuration)
* **파일 위치:** [institutional_access.py:7](file:///Users/jangseongjin/paperpipe/src/institutional_access.py#L7), [config.py:28-33](file:///Users/jangseongjin/paperpipe/src/config.py#L28-L33)
* **2026-05-24 상태:** 원문 주장은 현재 코드와 맞지 않습니다. 기관 도서관 프록시 URL 문자열은 소스 코드에 직접 박혀 있지 않고, `PAPERPIPE_INSTITUTIONAL_PROXY` 환경 변수에서 로드됩니다.
  ```python
  PROXY_PREFIX = os.getenv("PAPERPIPE_INSTITUTIONAL_PROXY", "")
  ```
* **남은 문제점:** `config.yaml` 및 `SystemConfig`에는 아직 `institutional_proxy_url` 같은 명시 필드가 없어서, 운영자가 어떤 환경 변수를 설정해야 하는지 앱 설정 경로에서 발견하기 어렵습니다. 또한 `generate_institutional_proxy_url()`은 `PROXY_PREFIX`가 비어 있어도 DOI URL을 그대로 반환하므로, "프록시 없음"과 "직접 DOI URL 생성"의 의미가 호출부에서 혼동될 수 있습니다.
* **2026-05-26 구현 상태:** `SystemConfig.institutional_proxy_url`와 `config.example.yaml` 예시 필드를 추가했고, `docs/institutional_access.md`에 설정 우선순위를 명시했습니다. `generate_institutional_proxy_url(...)`은 명시 prefix 또는 env fallback이 없으면 `None`을 반환하므로, 직접 DOI URL을 기관 프록시 링크로 저장하지 않습니다.
* **남은 작업:** 운영 문서/배포 템플릿에서 실제 기관별 prefix 값을 주입하는 것은 환경별 설정 작업으로 남깁니다.

### ④ `src.db` 레거시 모듈 이중 DB 경로 문제 (Legacy Module Dual DB Path Risk)
* **파일 위치:** [db.py:6-9](file:///Users/jangseongjin/paperpipe/src/db.py#L6-L9), [db.py:283-352](file:///Users/jangseongjin/paperpipe/src/db.py#L283-L352)
* **내용:** `src.db`는 "deprecated" 경고를 내도록 일부 정리되어 있으나, 기존 `save_paper_state` 함수가 `src.db`에 **독립 구현체**로 존재했습니다. 두 구현체는 동일한 논리를 담고 있지 않았습니다. 기존 `src.db.save_paper_state`는 `doi` 컬럼과 `paper_id` 컬럼에 동일 값(`identifier`)을 삽입하고, 오류 시 `logger.error` 대신 `print(f"DB Error: {e}")`로만 기록했습니다.
* **문제점:** 레거시 경로가 살아 있는 한 `src.db`를 임포트하는 코드가 다른 경로로 DB에 쓰는 상황이 발생할 수 있었습니다. 두 경로가 **같은 식별자를 다른 방식으로 INSERT**하면 `ON CONFLICT` 해석이 달라져 데이터 무결성 오류가 발생할 수 있습니다.
* **2026-05-24 구현 상태:** `src.db.save_paper_state`는 더 이상 독립 SQL을 실행하지 않고 `src.db_utils.save_paper_state`로 위임합니다. 따라서 non-DOI identifier를 DOI 컬럼에 저장하지 않는 규칙과 normalized DOI 저장 규칙을 canonical 경로와 공유합니다.
* **개선 제안:** `src.db` 모듈 자체의 나머지 runs/embeddings 호환 API도 단계적으로 canonical 모듈로 접거나, 최소한 프로덕션 코드 경로에서 신규 import가 생기지 않도록 현재의 `tests/test_no_new_src_db_imports.py` 가드를 유지해야 합니다.

### ⑤ 비서메트릭 점수의 `venue_score` 상수 하드코딩 (Bibliometric Dead-Weight Score)
* **파일 위치:** [ranking.py:58](file:///Users/jangseongjin/paperpipe/src/ranking.py#L58)
* **내용:** 기존 `BibliometricScorer`의 가중 합산 점수(`manual_rank_score`) 계산 시 저널 점수(`venue_score`)가 항상 `0.5` 상수로 고정되어 있었습니다.
  ```python
  venue_score = 0.5  # Todo: Map ISSN to SJR list if available
  ```
* **문제점:** 가중치 설정(`config.yaml`의 `ranking.bibliometrics.weights.venue: 0.2`)이 아무 효과 없이 항상 `0.5 * 0.2 = 0.1`의 상수 기여값을 만들어 냈습니다. 즉, **저널 점수는 실질적으로 비교·변별 기능 없이 모든 논문 점수에 동일한 상수를 더하는 바이어스**로만 작동했습니다.
* **2026-05-24 구현 상태:** `venue_score`는 `0.0`으로 변경했습니다. 즉, venue-quality source가 실제로 연결되기 전까지 venue 항목은 점수에 보너스를 추가하지 않습니다.
* **개선 제안:** 장기적으로는 ISSN-SJR 매핑 테이블을 도입하거나 OpenAlex의 venue/source metadata를 명시적 품질 신호로 정규화해야 합니다.

### ⑥ `watcher.py` 파일 핸들러의 블로킹 `time.sleep(1)` (Blocking File Handle Wait)
* **파일 위치:** [watcher.py:42](file:///Users/jangseongjin/paperpipe/src/watcher.py#L42)
* **내용:** 기존 `PaperFileHandler.on_created` 이벤트 핸들러는 파일 핸들이 해제될 때까지 `time.sleep(1)`로 무조건 1초를 대기했습니다.
  ```python
  time.sleep(1)  # Wait briefly to ensure file handle is released
  ```
* **문제점:** watchdog 라이브러리는 이벤트를 워커 스레드에서 동기 실행합니다. 핸들러 내부의 `time.sleep(1)`은 해당 워커 스레드 전체를 1초간 블록했습니다. 단일 워커 스레드 모드에서 **초당 1개 이상의 PDF가 감지되면 뒤에 들어오는 이벤트들이 큐에 쌓이며 처리 지연**이 발생할 수 있었습니다. 또한 파일 핸들 해제 여부를 전혀 검증하지 않으므로 1초 대기 후에도 파일이 잠겨 있으면 파싱 단계에서 에러가 날 수 있었습니다. 반면 `downloads_watcher.py`는 `_wait_for_stable_file()`로 파일 크기·mtime 기반 안정성 확인을 올바르게 구현하고 있어 **두 watcher 간 불일치**가 존재했습니다.
* **2026-05-24 구현 상태:** local PDF watcher는 downloads watcher의 stable-file 대기 로직을 재사용해 고정 `time.sleep(1)` 의존을 제거했습니다.

---

## 8b. 추가 발굴 이슈: 수집·다운로드·내보내기 계층

### ⑦ ArXiv 수집 시 `doi` 필드에 ArXiv ID 대입 (DOI 필드 오염)
* **파일 위치:** [fetch/arxiv.py:69](file:///Users/jangseongjin/paperpipe/src/fetch/arxiv.py#L69)
* **내용:** 기존 ArXiv 수집 경로는 `Paper` 스키마의 `doi` 필드에 `arxiv_id`(예: `2401.12345`)를 그대로 저장했습니다.
  ```python
  doi=arxiv_id, # ArXiv doesn't always have DOI, use ID
  ```
* **문제점:** ArXiv ID는 DOI가 아닙니다. 이 값이 `doi` 컬럼에 저장되면 다음 문제가 연쇄될 수 있었습니다:
  1. `normalize_doi()`로 조회 시 ArXiv ID와 실제 DOI가 혼용되어 **중복 방지 로직이 오작동**합니다. 동일 논문의 PubMed 버전과 ArXiv 버전이 별도 레코드로 삽입됩니다.
  2. `retraction.py`의 `check_retraction(doi)`에 ArXiv ID가 전달되면 Crossref는 항상 404를 반환합니다.
  3. `institutional_access.py`의 프록시 URL 생성 시 `https://doi.org/2401.12345` 형태의 잘못된 URL이 생성됩니다.
  4. RIS 내보내기의 `DO` 필드에 비표준 식별자가 들어가 Zotero 임포트 품질이 저하됩니다.
* **2026-05-24 구현 상태:** ArXiv 수집은 더 이상 ArXiv ID를 `doi` 필드에 저장하지 않습니다. 실제 `arxiv_doi`/`doi` 값이 있을 때만 DOI로 저장하고, 없으면 DOI를 비워 둡니다.
* **남은 작업:** ArXiv ID를 별도 canonical 필드로 승격할지는 스키마/RFC 범위로 남아 있습니다.

### ⑧ Worker의 `asyncio.run()` 사용 및 러너 계약 드리프트 위험 (Worker Event Loop / Runner Contract Risk)
* **파일 위치:** [jobs/worker.py:132](file:///Users/jangseongjin/paperpipe/src/jobs/worker.py#L132), [jobs/worker.py:142](file:///Users/jangseongjin/paperpipe/src/jobs/worker.py#L142), [jobs/worker.py:150](file:///Users/jangseongjin/paperpipe/src/jobs/worker.py#L150)
* **내용:** `Worker.process_job()`은 동기 컨텍스트(스레드)에서 `asyncio.run(run_deepread_job(...))`을 호출합니다.
* **문제점:** 현재 호출 위치가 워커 스레드라면 `asyncio.run()` 자체는 허용될 수 있으므로, 이 항목은 즉시 재현되는 nested loop 버그로 단정하지 않습니다. 더 확실한 위험은 `run_deepread_job` 호출 계약이 바뀔 때마다 `TypeError`를 잡아 kwargs를 제거하며 재시도하는 호환성 우회가 누적되어 있다는 점입니다. 이는 워커-러너 인터페이스가 명시적 Pydantic 계약으로 고정되어 있지 않음을 보여줍니다.
* **개선 제안:** 워커를 완전히 별도 프로세스(subprocess) 또는 `ProcessPoolExecutor`에서 실행하거나, `anyio.from_thread.run_sync` / `asyncio.get_event_loop().run_until_complete` 중 프레임워크-권장 방식으로 교체해야 합니다. 워커-러너 인터페이스는 Pydantic 스키마로 고정하여 TypeError 우회 코드를 제거해야 합니다.

### ⑨ `retraction.py`의 철회 감지 로직 오류 (Retraction Check Logic Bug)
* **파일 위치:** [retraction.py:64-66](file:///Users/jangseongjin/paperpipe/src/retraction.py#L64-L66)
* **내용:** 기존 `retraction.py`는 Crossref API의 `assertions` 필드에서 `is-retracted` 값을 확인할 때 `assertion.get("value") is True`로 파이썬 `bool`과 비교했습니다.
  ```python
  if assertion.get("name") == "is-retracted" and assertion.get("value") is True:
  ```
* **문제점:** Crossref API는 JSON 응답에서 `"value": true`를 반환하는데, Python의 `json.loads()`는 이를 `True`로 올바르게 변환합니다. 그러나 일부 Crossref 응답에서 `"value"` 필드가 `"true"` **문자열**로 반환되는 경우가 있습니다. 이 경우 `"true" is True`는 `False`이므로 **철회된 논문이 철회되지 않은 것으로 잘못 판정**될 수 있었습니다. 또한 `check_retraction_on_ingest: bool = False`가 기본값이고 실제 파이프라인에서 이 플래그를 체크하는 코드가 `src/` 내에 존재하지 않았습니다(테스트 파일에만 존재). 즉 **철회 감지 기능 자체가 파이프라인에 연결되어 있지 않은 미완성 기능**이었습니다.
* **원래 개선 제안:** 문자열 truthy assertion을 철회 신호로 처리하고, `check_retraction_on_ingest` 플래그를 `processor.py`의 인제스트 경로에서 실제로 읽어 `check_retraction(doi)`를 호출하도록 파이프라인에 연결합니다.
* **2026-05-24 구현 상태:** 문자열 truthy assertion 처리는 Sprint 1에서 수정했습니다. Sprint 18에서는 `process_daily_slots`가 `system.check_retraction_on_ingest`와 DOI를 확인한 뒤 `check_retraction(...)`을 호출합니다. 철회 논문은 `QUARANTINED`/`RETRACTED` reason으로 남고, `feedback_json.retraction_check`에 Crossref 결과를 보존하며, DB 저장 후 `mark_as_retracted(...)`로 `is_retracted`를 표시합니다.

### ⑩ `exporter.py`의 타임존 인식 없는 날짜 비교 (Naive Datetime Comparison)
* **파일 위치:** [exporter.py:753-756](file:///Users/jangseongjin/paperpipe/src/exporter.py#L753-L756)
* **내용:** 기존 Obsidian 노트의 스마트 덮어쓰기 로직은 DB의 `updated_at` 문자열과 파일의 `mtime`을 비교했습니다.
  ```python
  dt_db = datetime.fromisoformat(db_updated_str)
  ts_db = dt_db.timestamp()
  if ts_db > file_mtime:
      should_write = True
  ```
* **문제점:** `datetime.fromisoformat()`은 Python 3.10 이하에서 타임존 접미사(`+00:00`, `Z`)를 지원하지 않으며, Python 3.11 이상이어도 `db_updated_str`이 타임존 없는 naive datetime(`"2024-01-15 09:30:00"`)으로 저장되어 있으면 `dt_db`는 로컬 시간으로 해석됩니다. 반면 `file_mtime`은 UTC epoch입니다. 사용자의 시스템 시간대가 UTC가 아니면(예: KST=UTC+9) **최대 9시간의 비교 오차**가 발생하여:
  - DB가 실제로 최신임에도 파일이 덮어쓰여지지 않거나
  - 파일이 더 최신임에도 불필요하게 덮어쓰여지는 오작동이 발생합니다.
  또한 비교 실패 시 `except Exception: pass`로 silently skip되어 노트가 갱신되지 않아도 알 수 없습니다.
* **원래 개선 제안:** DB에 저장 시 `updated_at`을 UTC ISO 8601 형식(`datetime.now(timezone.utc).isoformat()`)으로 통일하고, 비교 시에는 `datetime.fromtimestamp(file_mtime, tz=timezone.utc)`를 사용하여 양쪽 모두 타임존-인식(aware) 객체로 비교합니다.
* **2026-05-24 구현 상태:** 비교 경로는 UTC aware datetime으로 정규화되었습니다. 기존 naive timestamp는 UTC-like DB 값으로 취급하며, `Z` 접미사도 파싱 가능합니다.
* **남은 작업:** 비교 실패 시 조용히 skip하는 동작은 사용자 편집 보호를 위한 fail-closed 정책으로 남겨두었습니다. 필요하면 별도 UX/API 작업에서 warning surface를 추가해야 합니다.

### ⑩b. PubMed 수집 시 `term` 쿼리 파라미터 URL 인코딩 누락 결함
* **파일 위치:** [pubmed.py:65](file:///Users/jangseongjin/paperpipe/src/fetch/pubmed.py#L65) (`_esearch`) 및 [fetchers.py:50](file:///Users/jangseongjin/paperpipe/src/fetchers.py#L50) (`_esearch_pubmed`)
* **내용:** 기존 PubMed ESearch API 호출 시 검색 식(Boolean Query String)을 담은 `term` 파라미터를 URL에 직접 보간(Interpolation)했습니다.
  ```python
  search_url = f"{base_url}/esearch.fcgi?db=pubmed&term={term}&retmode=json&retmax={max_results}&sort=date"
  ```
* **문제점:** 검색어가 URL 인코딩(URL Encoding)되지 않고 전송되었습니다. 만약 사용자가 작성한 검색식이나 프로필 키워드 내에 `&` (예: `R&D`, `TGF-beta & Smad` 등), `#`, 또는 특수 문자나 공백이 포함될 경우, HTTP 프로토콜 상 `&`는 쿼리 파라미터 구분 기호로 파싱되므로 검색식이 중간에 끊기고 뒤에 오는 조건들이 통째로 손실되어 수집 결과가 왜곡되거나 API 에러를 유발했습니다.
* **2026-05-24 구현 상태:** canonical `src/fetch/pubmed.py`와 legacy `src/fetchers.py` 모두 `requests.get(..., params=...)`로 `term`을 전달하도록 변경했습니다.
* **원래 개선 제안:** URL 문자열 보간 대신 `requests.get(..., params=...)`로 `term`을 전달합니다.
  ```python
  params = {"db": "pubmed", "term": term, "retmode": "json", "retmax": max_results, "sort": "date"}
  resp = requests.get(f"{base_url}/esearch.fcgi", params=params, timeout=10)
  ```
* **남은 작업:** 기존 import 호환성을 위해 남긴 `src.fetchers` deprecated wrapper를 외부 operator script 영향 확인 후 별도 compatibility-retirement PR에서 제거할지 결정합니다.

### ⑩c. PubMed 수집 모듈의 중복 구현 및 관리 분기 (Code Duplication)
* **파일 위치:** [pubmed.py](file:///Users/jangseongjin/paperpipe/src/fetch/pubmed.py) (클래스 기반) vs [fetchers.py](file:///Users/jangseongjin/paperpipe/src/fetchers.py) (독립 함수 기반)
* **내용:** 기존에는 PubMed ESearch/EFetch 기능을 구동하는 로직이 두 군데에 완전히 별도로 구현되어 병존했습니다.
* **문제점:**
  1. **코드 중복:** 메인 수집 파이프라인 및 Research DNA 서비스에서는 [pubmed.py](file:///Users/jangseongjin/paperpipe/src/fetch/pubmed.py)의 `PubMedFetcher` 클래스를 호출하지만, 기존 로컬 파일 감지기인 [watcher.py](file:///Users/jangseongjin/paperpipe/src/watcher.py#L10)는 [fetchers.py](file:///Users/jangseongjin/paperpipe/src/fetchers.py)의 `fetch_pubmed` 독립 함수를 호출했습니다.
  2. **관리 분기:** 수집 기능 버그(예: ⑩b의 URL 인코딩 결함)나 스키마 수정 시 두 곳의 구현을 각각 수정해야 하므로 코드 드리프트와 동기화 오류 발생 위험이 높았습니다.
* **2026-05-24 구현 상태:** local PDF watcher는 canonical `PubMedFetcher`를 사용하도록 변경했습니다. watcher의 PubMed lookup 회귀 테스트도 canonical fetcher 사용을 확인합니다.
* **2026-05-24 추가 구현 상태:** [fetchers.py](file:///Users/jangseongjin/paperpipe/src/fetchers.py)는 독립 PubMed ESearch/EFetch/XML parsing 구현을 더 이상 갖지 않습니다. 기존 import 호환성을 위해 함수 이름만 유지하고, 내부는 canonical `PubMedFetcher`에 위임하는 deprecated wrapper입니다.
* **남은 작업:** 외부 operator script까지 더 이상 `src.fetchers`를 import하지 않는 것이 확인되면 모듈 삭제를 별도 compatibility-retirement 작업으로 진행할 수 있습니다.

---

## 8c. 추가 발견 이슈: 페르소나 및 프로필 컨텍스트 결함 (Persona and Profile Context Gaps)

### ⑪ 비활성화(Disabled) 프로필 선택 시 무시 현상 및 허위 성공 로그 이벤트 방출
* **파일 위치:** [job_runner.py:350-368](file:///Users/jangseongjin/paperpipe/backend/services/job_runner.py#L350-L368) (`_resolve_persona_hint`), [job_runner.py:1593-1594](file:///Users/jangseongjin/paperpipe/backend/services/job_runner.py#L1593-L1594) (`read` 단계 이벤트 방출)
* **내용:** 기존에는 사용자가 수동 분석 요청 시 비활성화된 프로필(예: `neuroscience_mechanism`)을 지정하면, `_resolve_persona_hint` 함수 내 `and profile.enabled` 조건으로 인해 힌트 정보가 무시되고 `None`이 반환되었습니다. 하지만 러너 모듈은 이를 검증하지 않고 `selection.profile_id`가 지정되어 있으면 그대로 `"Profile context applied: [profile_id]"` 이벤트를 브라우저/API 클라이언트에 전송할 수 있었습니다.
* **문제점:** 사용자는 프로필 설정(쿼리 제약 및 가이드라인)이 적용된 분석 결과라고 신뢰하지만, 실제 백엔드에서는 프로필이 완전히 배제된 채 기본값으로 LLM을 구동하는 **사기성/기만적 성공 알림(Phantom Context Success)**이 생성될 수 있었습니다.
* **2026-05-24 구현 상태:** deepread runner는 실제 `profile_hint`가 생성된 경우에만 `"Profile context applied"` 이벤트를 방출합니다. 유사 피드백 주입만으로 `persona_applied`가 true가 되거나 profile 적용 이벤트가 나가지 않도록 적용 이벤트를 별도 추적합니다.
* **개선 제안:** 비활성 프로필을 선택했을 때 아예 API에서 거부할지, 또는 수동 deepread에서는 disabled profile도 명시적으로 적용할지는 별도 UX/API 정책으로 정해야 합니다.

### ⑫ 미등록 프로필 ID 유효성 검사 누락
* **파일 위치:** [queue.py:83](file:///Users/jangseongjin/paperpipe/src/jobs/queue.py#L83) (`JobQueue.enqueue`) 및 [persona_modes.py:69-92](file:///Users/jangseongjin/paperpipe/src/persona_modes.py#L69-L92) (`normalize_persona_selection`)
* **내용:** 기존에는 작업을 큐에 추가할 때 입력받은 `profile_id`가 `profiles.yaml` 내에 실제로 존재하는 유효한 ID인지 사전에 체크하지 않았습니다.
* **문제점:** 클라이언트가 오타가 있거나 존재하지 않는 프로필 ID로 작업을 요청하더라도 데이터베이스에 정상 입력되고 예외 없이 작업이 실행되나, 런타임 단계에서 존재하지 않는 프로필은 조용히 무시되므로(No Hint) 의도하지 않은 기본 모드로 동작하는 침묵적 실패가 발생했습니다.
* **2026-05-24 구현 상태:** `/jobs/deepread` API는 normalized selection의 `profile_id`가 `profiles.yaml`에 없으면 `UNKNOWN_PROFILE_ID` 400 응답으로 거부합니다.
* **개선 제안:** 하위 `JobQueue.enqueue`를 직접 호출하는 내부/테스트 경로까지 강제 검증할지는 compatibility 영향이 크므로 별도 단계에서 결정해야 합니다.

### ⑬ 프로필 설명 내 개인 파일 시스템 절대 경로 유출
* **파일 위치:** [profiles.yaml:65](file:///Users/jangseongjin/paperpipe/config/profiles.yaml#L65) (`notes` 설명 내 `source_of_truth` 경로)
* **내용:** Research DNA 프로필 컴포넌트(`research_dna_dna_mci_medium_chain_triglycerides_probe_20260312`)의 `notes` 문자열 안에 개발자의 로컬 절대 경로(`source_of_truth: /Users/jangseongjin/paperpipe/...`)가 고스란히 하드코딩되어 있습니다.
* **문제점:** 이 정보는 public API 엔드포인트 `/personas`를 호출하는 모든 클라이언트에 노출될 뿐 아니라, 프롬프트 힌트 결합 과정에서 `/Users/jangseongjin/...` 절대 경로 정보가 외부 LLM API 서비스(OpenAI 등) 페이로드에 그대로 전달되어 개인 정보 유출 및 보안 위생 상의 결함을 초래할 수 있었습니다.
* **2026-05-24 구현 상태:** YAML 원본은 보존하되, `/personas` 응답과 `_resolve_persona_hint`가 만드는 deepread prompt hint에서는 profile notes 내 로컬 절대 경로를 masking합니다.
* **개선 제안:** 장기적으로는 ResearchDNA projection metadata의 `source_of_truth` 자체를 상대 경로나 opaque reference로 저장하는 것이 더 바람직합니다.

---

## 8d. 검색식 생성 및 API 연동 취약점 (Search Query & API Vulnerabilities)

새로운 분석 세션(2026-05-24)을 통해 검색식을 작성하고 외부 API로 전달하는 구간에서 파싱 오류 및 통신 취약점이 추가로 발견되었습니다.

### ⑭ ProfileChatAgent의 JSON 파싱 취약점 (JSON Parsing Fragility)
* **파일 위치:** `src/agents/profile_chat_agent.py` (Line 90)
* **문제점:** 기존 `ProfileChatAgent`는 생성한 검색식 패치 데이터를 `json.loads(response.text)`로 파싱할 때, LLM이 반환하는 마크다운 코드 블록(예: ` ```json `)을 제거하는 전처리 로직이 없었습니다.
* **원래 영향 및 개선 제안:** 텍스트에 백틱이 포함되면 즉시 `JSONDecodeError`가 발생하여 프로필 업데이트 기능이 마비됩니다. 정규식 등을 활용한 마크다운 스트립(Strip) 로직을 추가합니다.
* **2026-05-24 구현 상태:** `ProfileChatAgent`는 fenced JSON 응답을 strip한 뒤 `json.loads`와 `PatchRequest` 검증을 수행합니다. 일반 patch 생성과 audit-fix 생성 양쪽에 회귀 테스트를 추가했습니다.

### ⑮ NCBI E-utilities API 인증 및 Rate-limit 방어 파라미터 누락
* **파일 위치:** `src/fetch/pubmed.py` (`_esearch`, `_efetch`)
* **문제점:** 기존 PubMed API 요청에는 `tool` 및 `email` 파라미터가 포함되어 있지 않았습니다.
* **원래 영향 및 개선 제안:** NCBI는 익명 API 요청에 대해 초당 3회로 매우 엄격한 Rate Limit을 적용하며 트래픽 몰림 시 IP를 차단할 수 있습니다. 설정 파일의 시스템 이메일을 연동하여 식별 파라미터를 주입합니다.
* **2026-05-24 구현 상태:** `PubMedFetcher`는 `tool=paperpipe`를 항상 전달하고, `system.unpaywall_email` 또는 `unpaywall.email`이 설정된 경우 `email`도 ESearch/EFetch params에 포함합니다.

### ⑯ EFetch ID 목록 길이 한계 (URI Too Long)
* **파일 위치:** `src/fetch/pubmed.py` (Line 77)
* **문제점:** 기존 EFetch 경로는 `id_str = ",".join(ids)`를 통해 검색된 모든 PMID를 쉼표로 이어붙여 URL 쿼리스트링에 직접 삽입했습니다.
* **원래 영향 및 개선 제안:** `max_results`가 클 경우 URL 길이가 2,000자를 초과해 `HTTP 414 URI Too Long` 에러로 전체 데이터 다운로드가 실패할 수 있습니다. ID 목록을 청크(Chunk)로 나누거나 POST 방식으로 전환합니다.
* **2026-05-24 구현 상태:** `PubMedFetcher.fetch`는 EFetch ID 목록을 100개 단위로 나누어 요청합니다. EFetch도 URL 문자열 보간 대신 `requests.get(..., params=...)`를 사용합니다.

### ⑰ ArXiv와 PubMed 간의 검색식 문법(Syntax) 호환성 부재
* **파일 위치:** `src/fetch/arxiv.py` (Line 64) 및 `config.yaml`
* **문제점:** PubMed 전용 필드 태그(예: `[Title/Abstract]`, `[MeSH]`)가 포함된 쿼리가 그대로 ArXiv API(`search_query=all:...`)로 넘어갈 경우 구문 분석 오류로 빈 결과를 반환합니다.
* **개선 제안:** 서로 다른 타겟 데이터베이스에 쿼리를 쏘기 전, 특정 DB의 전용 문법 태그를 정제(Strip)하는 노멀라이저를 배치하거나, 프로필별로 타겟 DB 전용 쿼리 필드를 확실히 분리해야 합니다.
* **2026-05-24 구현 상태:** `ArXivFetcher`는 ArXiv 요청 전에 PubMed bracket field tag를 제거합니다. 완전한 DB별 query DSL 분리는 장기 개선 과제로 남겨둡니다.

### ⑱ ArXiv 날짜 파싱 중 예외 발생 위험
* **파일 위치:** `src/fetch/arxiv.py` (Line 79)
* **문제점:** `datetime(*entry.published_parsed[:6])` 언패킹 시 feedparser가 비표준 날짜 형식을 만나 `None`을 반환하면 `TypeError`가 발생해 해당 논문이 유실됩니다.
* **원래 개선 제안:** `if not getattr(entry, "published_parsed", None): continue` 방어 코드를 삽입합니다.
* **2026-05-24 구현 상태:** `published_parsed`가 없는 ArXiv entry는 warning 로그를 남기고 건너뜁니다.

### ⑲ SQLite 동시성 제어 및 타임아웃 누락 (SQLite Lock Handling & Timeout Gap)
* **파일 위치:** `src/db_utils.py` (`get_db_connection` 및 제반 DB 조작 함수)
* **문제점:** 기존 `sqlite3.connect` 호출에는 `timeout` 파라미터가 명시되지 않아 기본값(5초)이 사용되었습니다. 이로 인해 백그라운드 워커와 API가 동시에 대량 쓰기 작업(Zotero 동기화 등)을 수행하면 `sqlite3.OperationalError: database is locked`가 발생할 수 있었습니다.
* **치명적 결과:** `is_paper_processed`, `save_paper_state`, `mark_as_retracted` 등의 핵심 함수들이 이 예외를 잡은 후 **아무런 재시도 없이 조용히 무시(Silently fail)**하고 `False`나 기본값을 반환할 수 있었습니다. 이는 데이터 저장 유실 및 중복 처리 등 심각한 데이터 무결성 훼손으로 직결될 수 있었습니다.
* **원래 개선 제안:** DB 커넥션 생성 시 `timeout=30.0` 등으로 대기 시간을 늘리고, 락 발생 시 치명적 로그를 남기거나 지수 백오프 기반 재시도(Exponential Backoff Retry) 메커니즘을 도입합니다. 예외를 조용히 묻어버리는(`pass` 또는 `return False`) 로직을 정리합니다.
* **2026-05-24 구현 상태:** `src/db_utils.py`의 DB 초기화 및 `get_db_connection()`은 `timeout=30.0`과 `PRAGMA busy_timeout=30000`을 설정합니다. Lock/busy 에러만 감지하는 공통 retry helper를 추가했고, 핵심 쓰기 경로의 SQL 실행 및 commit은 bounded exponential backoff를 적용합니다. 재시도 후에도 lock이 지속되면 error 로그를 남기고 기존 호출 경로의 실패 처리로 넘깁니다.
* **2026-05-24 추가 구현 상태:** Sprint 18에서 Zotero sync write loop는 50개 write 단위 batch commit으로 변경되었습니다. 남은 작업은 운영 데이터 규모에 맞춰 batch size를 설정화하거나 sync progress/event 표면을 추가하는 성능/UX 개선입니다.

### ⑳ 프로세서 모듈의 예외 삼킴 (Silent Exception Swallowing in Processor)
* **파일 위치:** `src/processor.py` (다수 `except Exception:` 블록)
* **문제점:** 기존 `build_gate_persistence_outcome` 등에서 LLM 응답을 파싱하거나 Pydantic 유효성 검사를 수행할 때, `JSONDecodeError` 또는 `ValidationError`가 발생하면 에러 로그 없이 파싱 실패 플래그(`parse_ok = False`)만 설정하고 넘어갈 수 있었습니다.
* **치명적 결과:** LLM이 비정상적인 출력을 반환하여 핵심 데이터 파싱이 실패했음에도 로그에 흔적이 남지 않아 장애 원인 분석이 어려웠습니다.
* **원래 개선 제안:** 모든 `except Exception:` 블록을 최소한 `except Exception as exc: logger.warning("...", exc_info=True)`로 변경하여 실패의 원인 예외 스택(Context)을 보존합니다.
* **2026-05-24 구현 상태:** `build_gate_persistence_outcome`의 feedback JSON parse failure와 `PaperTagging` schema validation failure는 paper id와 exception context를 warning 로그로 남깁니다. 추가로 `process_daily_slots`의 slot classification fallback, gate JSON parse fallback, feedback merge fallback, local PDF metadata parse fallback도 로그를 남기며, output persistence/clinical extraction/escalation/bibliometric scoring 실패 로그는 traceback을 보존합니다.
* **남은 작업:** Broad exception handler를 `JSONDecodeError`, Pydantic `ValidationError`, provider-specific errors 등 더 구체적인 타입으로 좁히는 cleanup은 별도 리팩터링으로 남길 수 있습니다. 다만 원문에서 지적한 “로그 없이 삼킴” 문제는 현재 핵심 processor 경로에서 해소되었습니다.

---

## 9. 향후 확장 및 개선 가능성 (Future Scalability & Improvements)

시스템이 대규모 데이터셋으로 성장하고 타 플랫폼과의 상호운용성을 확대하기 위해 아래와 같은 확장 및 개선 방안을 추가 검토할 수 있습니다.

### ① 해시 충돌 방지를 위한 식별자 크기 확장
* **현황:** 현재 코드는 SHA-1 해시의 앞 16자리(64비트)를 잘라서 식별자로 사용하고 있습니다.
* **개선 가능성:** 데이터가 수백만 건 단위로 확장될 경우 생일 역설(Birthday Paradox)에 의한 해시 충돌 확률이 아주 낮게나마 존재합니다. 이를 방지하기 위해 **SHA-256** 알고리즘을 도입하고 슬라이스 길이를 **24~32자리**로 늘리는 것을 고려할 수 있습니다.
* **예시:** `userpdf-f1a7d6e8b2c4d5e6...` (256비트 해시의 일부 추출)

### ② 텍스트 정규화 기반 유사도 해시(Semantic Deduplication) 도입
* **현황:** 현재 방식은 파일 내 바이너리 바이트 하나만 달라도(예: 다운로드 시 포함된 출판사 워터마크, 메타데이터 인코딩 차이) 다른 ID가 부여됩니다.
* **개선 가능성:** 논문의 첫 페이지 또는 특정 색인 정보의 텍스트(Text Content)만 추출하여 공백 및 인코딩을 정규화한 후 해싱하는 **텍스트 유사 해시(SimHash / MinHash)** 기술을 적용하면 물리적 파일 상태가 미세하게 다르더라도 동일한 논문으로 묶어주는 스마트 중복 방지가 가능해집니다.

### ③ PDF 미보유 상태의 가상 식별자 연동
* **현황:** PDF 파일이 없이 서지 메타데이터(Zotero Citation Key 등)만 존재하는 논문은 `citationKey`가 임시 ID로 동작하며, PDF 유무에 따라 식별 구조가 다릅니다.
* **개선 가능성:** PDF가 없는 메타데이터 전용 레코드는 결정론적으로 `meta-[DOI_Hash]` 형식의 식별자를 임시 부여하고, 향후 PDF가 확보되었을 때 백링크와 DB 레코드를 깨뜨리지 않고 `userpdf-[PDF_Hash]`와 다대일(N:1) 매핑 또는 부모-자식(Parent-Child) 관계로 병합할 수 있는 **유연한 매핑 구조**로 개선할 수 있습니다.

### ④ 다중 버전 관리(Multi-Version & File Binding)
* **현황:** 아카이브(arXiv) 프리프린트 버전과 정식 출판 저널 버전은 내용이 유사해도 파일 해시가 달라 별도의 레코드로 생성됩니다.
* **개선 가능성:** 논문 식별자에 **버전 속성(Version Property)**을 추가하여 상위 개념의 `master_paper` 그룹 아래에 복수의 프리프린트 및 최종 저널 PDF 해시 ID를 자식 객체로 묶는 **버전 체인 구조**를 형성합니다.

### ⑤ 로컬 퍼스트(Local-first) 보안 동기화 최적화
* **현황:** 사용자가 자신의 로컬 환경에서 기기 간 동기화를 진행할 때, 메타데이터와 메모리가 안전하게 싱크되어야 합니다.
* **개선 가능성:** 파일 내용 자체를 전달하지 않더라도 식별자가 결정론적 해시로 이루어져 있으므로, 암호화된 메타데이터 및 노트만 클라우드를 통해 공유하고 각 로컬 기기에서는 동일한 PDF가 감지되는 순간 자동으로 노트를 매핑해 주는 **제로 노리지(Zero-Knowledge) 동기화** 설계로 응용이 가능합니다.
