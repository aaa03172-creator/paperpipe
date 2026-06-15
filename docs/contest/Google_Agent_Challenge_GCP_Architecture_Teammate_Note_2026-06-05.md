# GCP 아키텍처 설명 메모

Status: teammate-share note
Date: 2026-06-04
Target: Google Agent Challenge finals

## 한 문장 요약

이번 GCP 구조의 목적은 단순히 파일을 보내고 받는 것이 아니다. 기존 local app + FastAPI 서비스는 그대로 유지하고, 원본 PDF와 구조화된 분석 결과를 GCP에 보존해서 같은 논문 상태를 다시 찾고, 검증하고, 나중에 팀 단위로 재사용할 수 있게 만드는 것이다.

## 1. Firestore에는 메타데이터만 저장하는가? 목적이 뭔가?

맞다. Firestore에는 원본 PDF 자체를 넣는 것이 아니라, 논문 상태를 찾고 관리하기 위한 메타데이터를 저장한다.

여기서 메타데이터는 단순한 설명문이 아니다. 현재 코드 기준으로는 `paper_id`, `upload_intent_id`, `lab_id`, `upload_status`, `processing_status`, `warnings`, `source_pdf_sha256` 같은 값이 핵심이다.

역할을 나누면 이렇다.

- FastAPI: 브라우저와 백엔드 사이의 요청/응답 API
- GCS: 실제 원본 PDF, page artifact, derived artifact JSON 저장
- Firestore: 어떤 논문이 업로드됐는지, 현재 처리 상태가 무엇인지, 어떤 paper_id로 찾아야 하는지 관리

API만으로도 파일을 전송하고 응답을 받을 수는 있다. 하지만 API 응답은 그 순간의 통신이고, 나중에 다시 논문 목록을 보거나 처리 상태를 확인하거나 팀원이 같은 paper state를 열어보려면 지속적으로 남아 있는 index/state store가 필요하다. 그 역할이 Firestore다.

즉 Firestore의 목적은 전송이 아니라 persistence와 index다.

## 2. 그러면 GCP는 정확히 무엇을 해결하는가?

기존 local-only 구조의 한계는 다음과 같다.

1. 논문 상태가 한 기기에 묶인다.
2. 같은 논문을 다른 팀원이 다시 열거나 검색하기 어렵다.
3. downstream artifact가 어떤 원본 PDF와 연결됐는지 장기적으로 추적하기 어렵다.
4. 브라우저가 cloud 저장소 정보를 직접 알게 만들면 bucket 경로, signed URL, service account 같은 민감한 정보가 노출될 수 있다.

GCP 구조에서는 이걸 이렇게 나눈다.

- 원본 PDF와 artifact는 GCS에 저장한다.
- Firestore는 paper_id, 상태, checksum, lab/project context를 저장한다.
- 브라우저는 GCS를 직접 보지 않는다.
- FastAPI가 GCS/Firestore를 읽고, 브라우저에는 redacted public response만 준다.

그래서 GCP는 파일 전송용 장식이 아니라, paper state를 한 기기 밖에서 유지하기 위한 저장/상태 계층이다.

## 3. End-to-end 경로는 백엔드까지 보여줘야 한다

발표에서는 아래 경로를 보여주는 것이 맞다.

```text
User / Local Lattice App
  -> Browser UI
  -> same-origin /api/*
  -> FastAPI cloud_papers router
  -> cloud paper service layer
  -> storage adapter
  -> GCS raw PDF bucket
  -> page / derived artifact generation
  -> GCS page artifact bucket
  -> metadata store
  -> Firestore cloud_papers_demo collection
  -> FastAPI redacted public schema
  -> UI search / open / inspect
```

이 경로에서 중요한 점은 브라우저가 바로 GCS에 붙지 않는다는 것이다. 브라우저는 `/api/*`만 호출하고, 실제 GCS/Firestore 접근은 백엔드가 한다.

발표에서 `PDF -> structured state -> review gates -> downstream artifacts`만 말하면 너무 제품 설명처럼 들린다. 본선용으로는 반드시 `Browser UI -> FastAPI -> service layer -> GCS/Firestore -> public response` 흐름을 같이 보여줘야 한다.

## 4. 무엇이 불확실하거나 review-needed인가?

불확실하다는 말은 막연한 문구로 쓰면 안 된다. 실제로는 아래 상태들을 말한다.

1. 처리 상태가 아직 확정되지 않은 경우
   - `pending`
   - `running`
   - `failed`
   - `blocked`

2. 처리 중 문제가 생긴 경우
   - `warnings`에 code/message/severity가 남는다.
   - 예: source PDF checksum mismatch, processing failure, storage unavailable

3. downstream artifact가 아직 사람이 승인하지 않은 경우
   - `review_status = review_pending`
   - 이후 `review_approved` 또는 `review_rejected`로 바뀔 수 있다.

4. promotion이 막힌 경우
   - `review_pending`, `review_rejected`, `registry_empty` 같은 blocker가 남는다.

5. benchmark상 약한 부분
   - 예를 들어 locator precision이나 claim precision이 낮으면, 그 부분은 "성능이 해결됐다"가 아니라 "측정 가능한 repair target"으로 말해야 한다.

따라서 발표에서는 이렇게 말하는 편이 정확하다.

> Lattice는 결과를 그냥 ready로 올리지 않고, 처리 상태, warning, review status, blocker를 별도 상태로 남긴다. 그래서 어떤 결과가 바로 사용할 수 있는지, 어떤 결과가 검토가 필요한지 구분할 수 있다.

## 5. state, gate, attach는 각각 무슨 뜻인가?

### State

여기서 state는 그냥 텍스트 요약본이 아니다. 코드 기준으로는 다음 구조를 합쳐서 paper state라고 부른다.

- `CloudPaperMetadataRecord`
  - paper_id
  - upload_status
  - processing_status
  - warnings
  - upload intent

- `CloudPaperPageArtifactInternal/Public`
  - paper_id
  - run_id
  - source_pdf_sha256
  - page_schema_version
  - blocks
  - warnings
  - provenance summary

- downstream artifact registry
  - candidate_ids
  - lane
  - review_status
  - canonical_status
  - source_pdf_sha256

즉 state는 "논문에서 나온 분석 결과와 그 결과의 근거, 처리 상태, 검토 상태를 schema로 보존한 것"이다.

### Gate

Gate는 결과를 다음 단계로 넘겨도 되는지 확인하는 조건이다.

예시는 다음과 같다.

- 업로드된 PDF가 기대한 SHA256과 맞는지 확인
- `upload_status`와 `processing_status`가 맞는 조합인지 확인
- 처리 실패나 blocked 상태면 ready로 넘기지 않음
- browser response에서 GCS ref, bucket, signed URL, service account 같은 private 정보가 빠졌는지 확인
- downstream artifact가 review_pending이면 외부 계약이나 최종 산출물로 승격하지 않음
- final readiness gate에서 rehearsal, redaction, package hash, endpoint smoke를 확인

따라서 gate는 화려한 AI 기능이 아니라, 잘못된 결과가 조용히 최종 결과처럼 보이지 않게 막는 장치다.

### Attach

Attach는 page structure 안에 모든 것을 계속 밀어 넣는다는 뜻이 아니다.

정확히는 downstream artifact를 별도 record로 만들고, `paper_id`, `run_id`, `source_pdf_sha256`, `candidate_ids`로 원본 paper state에 연결한다는 뜻이다.

예를 들어 meeting pack, chart pack, image evidence, method comparison, obsidian export 같은 결과는 page artifact 자체를 덮어쓰는 것이 아니라, 같은 source PDF와 page/derived artifact를 참조하는 sibling artifact 또는 registry entry로 붙는다.

그래서 page artifact는 원본 page/block 구조를 보존하고, downstream artifact는 그 위에 연결되는 파생 결과로 관리된다.

## 6. Firestore는 Google Cloud인가? Firestore에 저장한다는 말이 맞나?

맞다. Firestore는 Google Cloud 안에 있는 managed database 서비스다.

정확한 표현은 다음이 좋다.

> GCP 중에서는 GCS를 파일/object storage로 사용하고, Firestore를 paper metadata와 processing state를 저장하는 managed database로 사용한다.

부정확한 표현은 피하는 게 좋다.

- "GCP에 저장한다"만 말하면 너무 넓다.
- "Firestore에 PDF를 저장한다"는 틀렸다.
- "API로 주고받으니 Firestore가 필요 없다"는 persistence와 transport를 섞은 말이다.

## 7. 반드시 지킬 경계를 풀어서 설명

### 현재 demo claim

현재 말할 수 있는 것은 다음이다.

- 실제 34페이지 PDF를 사용했다.
- upload는 backend-mediated다.
- GCS에 source PDF와 page/derived artifact를 저장하는 경로를 검증했다.
- Firestore에 paper metadata와 processing state를 저장하는 경로를 검증했다.
- FastAPI가 redacted public response를 UI에 반환한다.
- final gate가 redaction, hash, packaged app proof, endpoint smoke를 확인했다.

### 아직 말하면 안 되는 것

아래는 production-ready로 말하면 안 된다.

- production SSO가 구현됐다.
- Cloud Run/Cloud Tasks가 현재 demo processing을 live로 돌린다.
- project/lab sharing이 production-ready다.
- 사용자가 만든 tool을 아무거나 바로 붙일 수 있다.
- paper understanding accuracy가 해결됐다.
- extracted protocol이 승인된 SOP다.
- downstream artifact가 canonical scientific truth다.

### Production 방향

생산 단계로 가려면 아래가 추가로 필요하다.

- first-class auth
- lab/user/device identity
- role-based permission
- Cloud Run worker
- Cloud Tasks dispatch
- retention/delete policy
- durable audit
- signing/notarization for public macOS distribution

## 팀원에게 설명할 때 쓸 수 있는 짧은 버전

Firestore는 API 대체재가 아니라 paper state를 다시 찾기 위한 metadata/index store다. PDF와 artifact JSON은 GCS에 있고, Firestore에는 paper_id, upload/processing status, warnings, lab context 같은 상태가 들어간다. 브라우저는 GCS를 직접 보지 않고 FastAPI의 redacted public contract만 받는다.

End-to-end로 보면 `Local App -> Browser UI -> FastAPI -> cloud paper service -> GCS/Firestore -> redacted response -> UI`다. 이 구조 덕분에 기존 local app 경험은 유지하면서도, 같은 논문 상태를 한 기기 밖에서 보존하고 나중에 팀 단위 재사용으로 확장할 수 있다.

다만 지금 단계에서 production sharing, Cloud Run/Tasks live worker, production auth, signed installer, paper-understanding accuracy solved는 주장하면 안 된다. 현재 claim은 GCS/Firestore/FastAPI 기반 cloud-paper demo path가 측정됐다는 것이다.
