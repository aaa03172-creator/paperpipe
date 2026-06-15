# Google Agent Challenge 발표자 / 심사위원 대비 쉬운 숙지 문서

Status: presenter prep guide
Date: 2026-06-05
Purpose: 발표자가 심사위원 질문에 기술적으로 틀리지 않게 답하기 위한 쉬운 설명서

## 0. 이 문서만 보고 외울 것

발표에서 계속 붙잡아야 하는 중심은 하나다.

> Lattice는 논문을 단순 요약하는 도구가 아니라, 원본 논문에서 나온 근거와 상태를 재사용 가능한 데이터 구조로 보존하는 연구 워크스페이스다.

이번 본선에서 GCP를 붙인 이유도 이 중심에서 벗어나지 않는다.

> GCP는 AI가 논문을 대신 읽어주는 곳이 아니라, 원본 PDF와 분석 artifact를 저장하고, paper metadata와 processing state를 관리해서 같은 논문 상태를 나중에 다시 찾고 재사용할 수 있게 하는 저장/상태 계층이다.

짧게 말하면:

```text
Lattice backend가 작업한다.
GCS가 파일을 저장한다.
Firestore가 metadata/index/status를 저장한다.
FastAPI가 브라우저에 안전한 응답만 내려준다.
```

## 1. 30초 핵심 설명

발표 시작이나 질문 답변에서 가장 안전한 버전이다.

> 연구를 하다 보면 논문을 한 번 요약하는 것보다, 시간이 지난 뒤 그 요약이 원문 어디에 근거했는지 다시 찾는 것이 더 어렵습니다. Lattice는 논문에서 나온 claim, evidence, uncertainty, provenance를 구조화된 상태로 보존하고, 그 위에 발표자료, 미팅팩, 그래프, figure 설명 같은 후속 산출물을 연결할 수 있게 만든 도구입니다.
>
> 이번 본선에서는 이 구조를 한 기기 안에만 두지 않고, GCP 기반 cloud-paper 경로로 확장했습니다. 원본 PDF와 artifact JSON은 GCS에 저장하고, paper_id와 processing status 같은 metadata는 Firestore에 저장합니다. 실제 처리와 검증은 Lattice의 FastAPI backend/service layer에서 수행하고, 브라우저에는 GCS 경로나 credential이 빠진 redacted public response만 반환합니다.

## 2. 한 줄씩 쉽게 정의

### Lattice

논문을 요약하는 챗봇이 아니라, 논문에서 나온 근거와 상태를 구조화해서 보존하는 연구 워크스페이스다.

### GCP

Google Cloud Platform 전체를 말한다. 이번 데모에서는 그중 `GCS`와 `Firestore`를 쓴다.

### GCS

Google Cloud Storage. 실제 파일 저장소다.

저장 대상:

- 원본 PDF
- page artifact JSON
- derived artifact JSON

### Firestore

Google Cloud 안에 있는 managed database다. PDF를 저장하는 곳이 아니다.

저장 대상:

- paper_id
- upload_status
- processing_status
- warnings
- source_pdf_sha256
- lab_id 같은 context

쉽게 말하면:

```text
GCS = 파일 창고
Firestore = 파일을 찾기 위한 관리대장 / index / 상태표
```

### FastAPI

브라우저와 backend service layer 사이의 API 서버다. 브라우저는 FastAPI만 호출한다.

### Cloud paper service layer

GCP가 제공하는 서비스가 아니다. Lattice backend 코드 안에 있는 중간 로직이다.

역할:

- GCS에 파일 저장/조회
- Firestore에 metadata 저장/조회
- processing status 변경
- warning 처리
- public response 생성
- private 정보 제거

### State

별도 GCP 서비스 이름이 아니다. 자료가 시스템 안에서 어떤 상태인지 표현하는 데이터 구조다.

예:

- 업로드됨
- 처리 중
- ready
- failed
- blocked
- warning 있음
- 어떤 PDF checksum에서 나온 결과인지
- 어떤 run에서 나온 artifact인지

### Gate

GCP 기능이나 Firestore plugin이 아니다. Lattice backend에서 수행하는 검증/차단 로직이다.

예:

- checksum이 맞는지 확인
- processing_status가 ready인지 확인
- public response에 GCS 경로나 signed URL이 섞이지 않았는지 확인
- review_pending artifact가 최종 산출물처럼 승격되지 않게 막음

### Downstream artifact

원본 논문에서 파생되는 2차 산출물이다.

예:

- meeting pack
- chart pack
- image evidence
- method comparison
- obsidian export
- 발표자료나 figure 설명으로 확장될 수 있는 산출물

핵심은 산출물을 그냥 파일로 만드는 것이 아니라, `paper_id`, `run_id`, `source_pdf_sha256`, `candidate_ids`, `review_status`로 원본 근거에 연결한다는 점이다.

### Redacted public schema

브라우저에 내려주는 안전한 응답 구조다.

내부에는 GCS object ref, bucket name, worker metadata 같은 값이 있을 수 있다. 이 값들을 그대로 브라우저에 주면 안 된다. 그래서 FastAPI가 public schema로 변환해서 필요한 정보만 내려준다.

## 3. 실제 아키텍처를 한 번에 설명하기

발표에서 아키텍처를 설명할 때는 아래 흐름을 그대로 말하면 된다.

```text
Local Lattice App
  -> Browser UI
  -> same-origin /api/*
  -> FastAPI cloud_papers router
  -> cloud paper service layer
  -> GCS raw PDF / artifact storage
  -> Firestore paper metadata / processing state
  -> FastAPI redacted public schema
  -> UI search / open / inspect
```

레이어별 설명:

1. `Local Lattice App`
   - 사용자가 실행하는 앱이다.
   - 기존 사용 경험을 유지한다.

2. `Browser UI`
   - 사용자가 보는 화면이다.
   - GCS나 Firestore에 직접 접근하지 않는다.

3. `same-origin /api/*`
   - 브라우저가 호출하는 안전한 API 입구다.
   - credential을 브라우저에 두지 않는다.

4. `FastAPI cloud_papers router`
   - cloud paper 관련 요청을 받는 backend API다.
   - list, search, upload, page 조회, artifact 조회를 처리한다.

5. `cloud paper service layer`
   - 우리 backend 코드 안에 있는 중간 로직이다.
   - GCS/Firestore adapter를 호출하고, 상태 전이와 validation을 담당한다.

6. `GCS raw PDF / artifact storage`
   - 실제 파일이 저장되는 곳이다.
   - PDF, page.json, derived.json이 들어간다.

7. `Firestore paper metadata / processing state`
   - 파일을 찾고 상태를 관리하는 곳이다.
   - paper_id, upload_status, processing_status, warnings가 들어간다.

8. `FastAPI redacted public schema`
   - backend가 내부 정보를 제거하고 브라우저용 응답으로 바꾼 것이다.

9. `UI search / open / inspect`
   - 사용자가 최종적으로 논문을 검색하고 열고 상태를 확인하는 화면이다.

가장 중요한 문장:

> 브라우저는 GCP에 직접 붙지 않습니다. 브라우저는 FastAPI만 호출하고, FastAPI 뒤쪽에서 Lattice service layer가 GCS와 Firestore를 사용합니다.

## 4. 실제 작업은 어디서 일어나는가?

현재 데모 기준으로는 실제 작업은 Lattice backend에서 일어난다.

GCP에서 하는 일:

- 파일 저장
- metadata 저장
- processing state 저장

Lattice backend에서 하는 일:

- upload intent 생성
- PDF checksum 확인
- GCS에 PDF 저장
- Firestore metadata record 생성
- page artifact 생성
- derived artifact 생성
- warnings 생성
- public schema 변환
- redaction
- downstream artifact 등록
- readiness gate 실행

현재 demo 구조:

```text
작업 실행 위치 = local machine의 Lattice backend
저장 위치 = GCS + Firestore
```

production 방향:

```text
작업 실행 위치 = Cloud Run worker로 옮길 수 있음
비동기 작업 큐 = Cloud Tasks로 옮길 수 있음
저장 위치 = GCS + Firestore 유지 가능
```

주의:

> 현재 데모에서 Cloud Run/Cloud Tasks가 live로 processing을 돌린다고 말하면 안 된다.

## 5. Firestore 구조를 쉽게 설명하기

Firestore는 collection/document 구조다.

이번 데모에서는 이렇게 보면 된다.

```text
collection: cloud_papers_demo

document id: paper_id

document body:
  paper_id
  upload_intent_id
  request:
    filename
    content_type
    source_pdf_sha256
    lab_id
  upload_status
  processing_status
  warnings
```

예시:

```json
{
  "paper_id": "paper_mock_000001",
  "upload_intent_id": "upl_mock_000001",
  "request": {
    "filename": "demo.pdf",
    "content_type": "application/pdf",
    "source_pdf_sha256": "5f9a...",
    "lab_id": "lab_001"
  },
  "upload_status": "ready",
  "processing_status": "ready",
  "warnings": []
}
```

설명 문장:

> Firestore에는 PDF 자체를 저장하지 않습니다. PDF와 artifact JSON은 GCS에 저장하고, Firestore에는 paper_id를 key로 하는 metadata record를 저장합니다. 이 record는 나중에 논문을 다시 찾고, 처리 상태를 확인하고, 같은 paper state를 재사용하기 위한 index 역할을 합니다.

## 6. State를 쉽게 설명하기

state는 지어낸 서비스 이름이 아니다. backend에서 흔히 쓰는 말이고, 여기서는 “논문이 시스템 안에서 어떤 상태인지 나타내는 데이터 구조”를 뜻한다.

Lattice에서 state는 크게 세 덩어리다.

### 6.1 Metadata state

Firestore에 들어가는 상태다.

포함:

- paper_id
- upload_status
- processing_status
- warnings
- source_pdf_sha256
- lab_id

### 6.2 Page artifact state

GCS에 저장되는 page artifact JSON이다.

포함:

- paper_id
- run_id
- source_pdf_sha256
- page_schema_version
- page blocks
- warnings
- provenance summary

### 6.3 Downstream artifact state

2차 산출물을 원본 논문과 연결하는 registry 상태다.

포함:

- artifact_id
- lane
- candidate_ids
- review_status
- source_pdf_sha256

한 문장:

> 여기서 state는 요약문이 아니라, 논문과 산출물이 어떤 원본에서 왔고, 어떤 처리 상태이며, 검토가 필요한지 표현하는 schema-backed data structure입니다.

## 7. Gate를 쉽게 설명하기

Gate는 GCP 서비스가 아니다.

Gate는 다음 단계로 넘어가기 전에 확인하는 backend 검증 로직이다.

예시:

- PDF checksum이 맞는가?
- upload_status와 processing_status 조합이 맞는가?
- processing_status가 ready인가?
- failed 또는 blocked 상태는 아닌가?
- warning이 있는가?
- public response에 GCS ref나 signed URL이 섞이지 않았는가?
- downstream artifact가 review_pending인가?
- package hash와 endpoint smoke가 통과했는가?

쉽게 말하면:

```text
Gate = 잘못된 결과가 최종 결과처럼 보이지 않게 막는 체크포인트
```

심사위원이 “Gate는 Firestore 기능인가요?”라고 물으면:

> 아닙니다. Gate는 Firestore나 GCP가 제공하는 별도 기능이 아니라 Lattice backend의 검증 로직입니다. Firestore는 gate 판단에 필요한 상태값을 저장하고, FastAPI/service layer가 그 값을 읽어서 다음 단계로 넘길지 판단합니다.

## 8. Downstream artifact를 쉽게 설명하기

Downstream artifact는 원본 논문에서 파생되는 후속 산출물이다.

예:

- meeting pack
- chart pack
- image evidence
- method comparison
- obsidian export
- 발표자료
- figure 설명
- 비교표

중요한 점:

> downstream artifact는 page structure 안에 무작정 추가되는 것이 아니라, 별도 record로 등록되고 `paper_id`, `run_id`, `source_pdf_sha256`, `candidate_ids`로 원본 paper state와 연결된다.

발표 문장:

> 저희는 모든 발표자료나 그래프 도구를 직접 만들겠다는 것이 아니라, 그런 도구들이 안전하게 붙을 수 있는 원본 evidence state를 만들고자 했습니다. downstream artifact는 이 evidence state에 연결되는 후속 산출물입니다.

## 9. 발표 흐름별로 외울 말

발표자는 모든 기술 디테일을 한꺼번에 말하려고 하지 말고, 아래 순서로만 밀고 가면 된다.

### 9.1 문제 제기

말할 핵심:

> 학부연구생으로 실제 연구 환경을 경험하면서, 논문을 읽는 일 자체보다 나중에 근거 위치와 판단 이유를 다시 찾는 일이 더 자주 반복되고 더 불편하다는 점을 느꼈습니다. 주변 선배들도 발표자료, 실험 계획, 미팅 준비를 할 때 같은 논문을 다시 열고 같은 표와 figure를 다시 확인하는 일이 많았습니다.

피해야 할 방향:

- AI가 논문을 완전히 대신 읽어준다고 말하지 않는다.
- 연구자의 판단을 대체한다고 말하지 않는다.

### 9.2 해결 방향

말할 핵심:

> 그래서 저희는 최종 PPT나 그래프를 먼저 자동 생성하는 것보다, 그 산출물들이 믿고 붙을 수 있는 원본 paper/evidence state를 먼저 만들고자 했습니다. claim, evidence, uncertainty, provenance, warning을 구조화해두면 이후의 발표자료, 미팅팩, figure 설명, 비교표가 같은 근거 위에서 만들어질 수 있습니다.

### 9.3 제품 설명

말할 핵심:

> Lattice는 논문 중심 연구 워크스페이스입니다. 사용자는 논문을 넣고, 시스템은 원본 PDF에서 page artifact와 derived artifact를 만들며, 후속 산출물은 이 state에 연결됩니다. 중요한 점은 결과물이 그냥 텍스트로 끝나는 것이 아니라 paper_id, run_id, source_pdf_sha256으로 원본과 연결된다는 점입니다.

### 9.4 GCP 아키텍처 설명

말할 핵심:

> 이번 본선에서 GCP를 사용한 이유는 기존 local 앱 경험은 유지하면서도, 논문 상태를 한 기기 안에만 묶어두지 않기 위해서입니다. GCS는 원본 PDF와 artifact JSON을 저장하고, Firestore는 paper metadata와 processing status를 저장합니다. 브라우저는 GCP에 직접 붙지 않고 FastAPI만 호출합니다.

### 9.5 데모 설명

말할 핵심:

> 데모에서는 PDF input에서 시작해서, upload intent, source PDF 저장, metadata record 생성, page/derived artifact 생성, redacted public response, downstream artifact registry까지 이어지는 end-to-end 경로를 보여줍니다. 현재 작업 실행은 local Lattice backend에서 일어나고, 저장과 상태 관리는 GCS/Firestore를 사용합니다.

### 9.6 확장 가능성

말할 핵심:

> 앞으로는 이 paper/evidence state 위에 발표자료 생성, 그래프 생성, figure 설명, protocol reference, project/lab sharing을 붙일 수 있습니다. 다만 이것들은 모두 원본 근거를 대체하는 것이 아니라, 같은 원본 state를 참조하는 reviewable downstream artifact로 관리되어야 합니다.

## 10. 정량지표를 질문받았을 때 말하는 법

심사위원이 "벤치마크가 있나요?"라고 물으면, 정확도를 과장하지 말고 측정된 사실과 아직 측정 중인 항목을 분리해서 말한다.

### 10.1 지금 바로 말할 수 있는 측정값

| 항목 | 값 | 의미 |
| --- | --- | --- |
| 데모 PDF | 34 pages | 실제 논문 단위 입력을 사용했다 |
| source PDF size | 8,460,622 bytes | 입력 파일 크기까지 기록했다 |
| source PDF SHA256 | `5f9a0e...24f40` | 같은 원본인지 재확인할 수 있다 |
| upload mode | `backend_mediated` | 브라우저가 직접 GCS credential을 들고 있지 않다 |
| Firestore collection | `cloud_papers_demo` | paper metadata/status가 저장되는 위치 |
| paper id | `paper_mock_000001` | paper state를 재조회하는 key |
| final readiness gate | passed | 데모 경로가 마지막 점검을 통과했다 |
| gate time | 24 sec | 점검 시간이 기록되어 있다 |
| public redaction | passed | public response에 private ref가 빠지는지 확인했다 |
| endpoint proof | all 200 | packaged/extracted endpoint smoke가 성공했다 |
| goldset readiness | 8/8 ready | benchmark fixture 준비가 끝났다 |

### 10.2 정확도 질문에는 이렇게 답한다

> 지금은 "정확도를 완전히 해결했다"가 아니라, claim recall, evidence support, locator precision 같은 항목을 반복 측정할 수 있는 goldset과 scorecard를 만든 단계입니다. 이 benchmark의 목적은 성능을 부풀리는 것이 아니라, 어떤 claim이 근거 위치를 잘못 잡았는지, 어떤 figure/table 후보가 review가 필요한지 다시 고칠 수 있게 만드는 것입니다.

### 10.3 지표를 말할 때의 경계

- readiness gate passed는 production-ready와 같은 뜻이 아니다.
- goldset 8/8 ready는 fixture 준비가 됐다는 뜻이지, 모든 논문 이해가 해결됐다는 뜻이 아니다.
- endpoint all 200은 API smoke가 통과했다는 뜻이지, 연구 품질을 자동 보증한다는 뜻이 아니다.
- public redaction passed는 browser-safe response 검증이지, 전체 보안 체계 완성을 뜻하지 않는다.

한 문장:

> 저희가 제시하는 정량지표는 "AI가 논문을 완벽히 이해했다"는 점수가 아니라, 원본 입력과 산출물, 상태, endpoint, redaction, review-needed 지점을 재현 가능하게 확인하기 위한 운영 지표입니다.

## 11. 처음 접하는 연구자에게 설명하는 법

처음 보는 연구자는 GCP나 schema보다 "내 연구에 그래서 뭐가 좋아지는가?"를 먼저 궁금해한다. 이때는 아래 순서로 설명한다.

### 11.1 연구자용 20초 설명

> 논문을 읽고 나면 요약은 남지만, 나중에 그 문장이 어느 page, figure, table에서 왔는지 다시 확인해야 하는 경우가 많습니다. Lattice는 그 근거 위치와 불확실성, 처리 상태를 함께 저장해서, 나중에 미팅자료나 발표자료를 만들 때 같은 논문을 처음부터 다시 읽지 않아도 되게 만드는 도구입니다.

### 11.2 연구자가 바로 이해하는 예시

예를 들어 선배가 "이 논문에서 실험 조건이 뭐였지?"라고 물었을 때:

1. 기존 방식은 PDF를 다시 열고, figure/table/caption을 다시 찾고, 이전 메모를 다시 확인한다.
2. Lattice 방식은 같은 paper state를 열고, 관련 block, table, figure 후보와 warning을 같이 확인한다.
3. 발표자료나 미팅팩은 이 상태 위에 붙는 downstream artifact로 만든다.

### 11.3 연구자에게 강조할 점

- "자동으로 정답을 내준다"가 아니라 "근거를 잃지 않게 정리한다"가 핵심이다.
- "요약 결과"보다 "다시 검토 가능한 evidence state"가 핵심이다.
- "내가 만든 산출물"보다 "팀이 같은 원본 상태를 보고 재사용할 수 있는 구조"가 핵심이다.
- GCP는 연구자가 직접 만지는 화면이 아니라, 뒤에서 원본과 상태를 보존하는 저장/상태 계층이다.

## 12. 코드 근거를 물어보면 볼 위치

발표 중 코드를 직접 열 필요는 없지만, 팀원과 리허설할 때는 아래 파일을 근거로 삼으면 된다.

| 질문 | 근거 파일 | 확인할 내용 |
| --- | --- | --- |
| Firestore에 무엇을 저장하나 | `src/services/cloud_paper_metadata.py` | `CloudPaperFirestoreMetadataStore`가 `CloudPaperMetadataRecord`를 document로 저장 |
| Firestore record 모양 | `src/schemas/cloud_paper.py` | `CloudPaperMetadataRecord`: `paper_id`, `upload_intent_id`, `request`, `upload_status`, `processing_status`, `warnings` |
| GCS에 무엇을 저장하나 | `src/services/cloud_paper_storage.py` | `source.pdf`, `page.json`, `derived.json` object path |
| upload 방식 | `src/services/cloud_paper_storage.py` | GCS adapter의 `upload_mode="backend_mediated"` |
| 브라우저 API 경로 | `backend/routers/cloud_papers.py` | router prefix가 `/cloud/papers`; frontend에서는 same-origin `/api/*` 경유 |
| 브라우저 secret 방지 | `frontend/README.md` | 브라우저는 same-origin `/api/*`만 호출하고 backend secret을 env에 넣지 않는다는 설명 |
| public redaction | `src/schemas/cloud_paper.py` | `_redact_public_metadata`, `derive_cloud_page_artifact_public` |
| downstream registry | `src/schemas/cloud_paper.py`, `src/services/cloud_paper_downstream.py` | `review_status`, `canonical_status="derived_noncanonical"`, candidate/source checksum 연결 |

짧게 설명하면:

```text
저장 근거 = cloud_paper_storage.py
index/status 근거 = cloud_paper_metadata.py + cloud_paper.py
API 근거 = backend/routers/cloud_papers.py
browser-safe 근거 = frontend/README.md + cloud_paper.py redaction
downstream 근거 = cloud_paper_downstream.py + schema downstream models
```

## 13. 심사위원 예상 질문과 답변

### Q1. GCP로는 데이터 저장만 하나요?

현재 데모 기준으로는 주로 저장과 상태 관리 역할이다.

답변:

> 현재 demo에서는 Lattice backend가 실제 작업을 수행하고, GCP는 source PDF, artifact JSON, metadata/status를 저장하는 cloud-backed persistence layer로 사용했습니다. GCS는 파일 저장소, Firestore는 metadata/index/status store입니다. Production 단계에서는 Cloud Run/Cloud Tasks를 통해 작업 실행 공간까지 GCP로 옮길 수 있습니다.

### Q2. 실제 작업은 어디서 일어나나요?

답변:

> 현재 demo에서는 local machine에서 실행되는 Lattice FastAPI backend/service layer에서 처리됩니다. PDF checksum 확인, artifact 생성, redaction, gate check는 Lattice backend가 수행하고, 결과 파일과 상태만 GCS/Firestore에 저장합니다.

### Q3. API는 GCP랑만 연결되나요?

답변:

> 아닙니다. FastAPI는 GCP 전용 API가 아니라 Lattice의 중앙 backend layer입니다. 브라우저는 FastAPI만 호출하고, FastAPI가 내부에서 local runtime, cloud paper service layer, GCS, Firestore, downstream artifact logic, validation/gate logic을 연결합니다.

### Q4. Cloud paper service layer는 GCP 서비스인가요?

답변:

> 아닙니다. Cloud paper service layer는 Lattice backend 코드 안에 구현된 중간 로직입니다. GCP가 제공하는 managed service가 아니라, FastAPI router 뒤에서 GCS와 Firestore adapter를 호출하는 우리 서비스 레이어입니다.

### Q5. Firestore는 GCP 안에 포함되나요?

답변:

> 네. Firestore는 Google Cloud 안에 있는 managed database 서비스입니다. 이번 구조에서는 GCS를 object storage로, Firestore를 metadata/index/status store로 사용합니다.

### Q6. Firestore에 PDF를 저장하나요?

답변:

> 아닙니다. PDF와 artifact JSON은 GCS에 저장합니다. Firestore에는 paper_id, upload_status, processing_status, warnings, checksum 같은 metadata와 상태를 저장합니다.

### Q7. API만 있으면 되지 Firestore가 왜 필요한가요?

답변:

> API는 순간적인 요청/응답 통신입니다. 하지만 나중에 논문 목록을 다시 보고, 처리 상태를 확인하고, 같은 paper state를 재사용하려면 지속적으로 남는 index와 state store가 필요합니다. Firestore는 그 역할을 합니다.

### Q8. State는 정확히 뭔가요?

답변:

> 여기서 state는 별도 서비스 이름이 아니라, 논문이 시스템 안에서 어떤 상태인지 표현하는 데이터 구조입니다. 업로드 상태, 처리 상태, checksum, warning, provenance, page blocks, review status 같은 정보를 포함합니다.

### Q9. Gate는 GCP 기능인가요?

답변:

> 아닙니다. Gate는 GCP 기능이 아니라 Lattice backend의 검증 로직입니다. Firestore는 gate 판단에 필요한 상태값을 저장하고, FastAPI/service layer가 그 값을 읽어 다음 단계로 넘길지 판단합니다.

### Q10. 무엇이 review-needed인가요?

답변:

> 처리 상태가 failed/blocked이거나 warning이 있는 경우, downstream artifact가 review_pending인 경우, benchmark상 locator precision이나 claim precision이 약한 경우가 review-needed입니다. Lattice는 이런 상태를 숨기지 않고 별도 상태로 남기는 것이 핵심입니다.

### Q11. Downstream artifact는 뭔가요?

답변:

> 원본 논문에서 파생되는 2차 산출물입니다. 예를 들어 meeting pack, chart pack, image evidence, method comparison, obsidian export, 발표자료, figure 설명 같은 결과입니다. 중요한 점은 이 산출물이 원본 paper_id, run_id, source checksum과 연결된다는 것입니다.

### Q12. Attach한다는 말은 page JSON에 계속 붙인다는 뜻인가요?

답변:

> 아닙니다. page artifact 자체를 계속 덮어쓰는 것이 아니라, downstream artifact를 별도 record로 등록하고 paper_id, run_id, source_pdf_sha256, candidate_ids로 원본 paper state와 연결한다는 뜻입니다.

### Q13. NAS로 바꿀 수 있나요?

답변:

> GCS가 맡는 object storage 역할은 나중에 NAS adapter로 대체할 수 있습니다. 다만 Firestore가 맡는 metadata/index/status 역할은 별도의 DB나 index store가 필요합니다. NAS를 쓰면 동시성, 권한, checksum, 백업 정책을 직접 설계해야 합니다.

### Q14. Zotero를 쓰는 의미가 있나요?

답변:

> 지금 본선 핵심에는 넣지 않는 편이 좋습니다. Zotero는 reference manager이므로 나중에 paper input이나 citation metadata source로 붙일 수 있습니다. 하지만 Lattice의 핵심은 bibliography 관리가 아니라 paper evidence state를 구조화하는 것입니다.

### Q15. 이게 그냥 요약 도구와 뭐가 다른가요?

답변:

> 요약 도구는 보통 텍스트 결과를 바로 줍니다. Lattice는 원본 PDF, evidence, uncertainty, provenance, processing status, warning, review status를 함께 보존합니다. 그래서 나중에 발표자료나 그래프를 만들 때도 원본 근거와 연결된 상태를 유지할 수 있습니다.

### Q16. 정확도는 어느 정도인가요?

답변:

> 정확도가 완전히 해결됐다고 말하지 않습니다. 대신 fixed goldset과 scorecard로 claim recall, evidence support, locator precision 같은 항목을 측정하고 있습니다. 현재 benchmark는 성능 과장이 아니라 어디를 고쳐야 하는지 보여주는 repair loop입니다.

### Q17. 현재 production-ready인가요?

답변:

> 아닙니다. 현재는 assisted alpha demo입니다. Production으로 가려면 auth, lab/device identity, role-based permission, retention/delete policy, durable audit, Cloud Run worker, Cloud Tasks dispatch, signing/notarization이 필요합니다.

### Q18. Cloud Run과 Cloud Tasks는 이미 쓰고 있나요?

답변:

> 현재 demo에서 live processing을 돌린다고 주장하지 않습니다. Cloud Run과 Cloud Tasks는 production worker 방향입니다. 현재 측정된 것은 GCS + Firestore + FastAPI + packaged macOS alpha proof입니다.

### Q19. Project/lab sharing은 이미 되나요?

답변:

> 현재는 production-grade sharing이라고 말하면 안 됩니다. 다만 GCP-backed paper state가 있기 때문에 나중에 승인된 project/lab member가 같은 paper state와 artifact를 공유하는 방향으로 확장할 수 있습니다. 그 단계에는 auth, permission, audit이 필요합니다.

### Q20. 왜 GCP가 필요한가요?

답변:

> local-only로 두면 paper state가 한 기기에 묶이고, 팀 단위 재사용이나 장기 추적이 어렵습니다. GCP를 쓰면 원본 PDF와 artifact를 GCS에, metadata와 processing state를 Firestore에 보존해서 같은 paper state를 나중에 다시 찾고 검증할 수 있습니다.

## 14. 발표에서 절대 피할 표현

아래 표현은 쓰지 않는다.

- Firestore에 PDF를 저장합니다.
- GCP가 논문을 분석합니다.
- Cloud Run과 Cloud Tasks가 현재 demo를 live로 돌립니다.
- Production SSO가 구현됐습니다.
- Project/lab sharing이 production-ready입니다.
- Paper understanding accuracy가 해결됐습니다.
- Downstream artifact가 canonical scientific truth입니다.
- Extracted protocol은 승인된 SOP입니다.
- 사용자가 만든 tool을 아무거나 바로 붙일 수 있습니다.

대신 이렇게 말한다.

- GCS에 PDF와 artifact JSON을 저장합니다.
- Firestore에 metadata/index/status를 저장합니다.
- Lattice backend가 processing과 gate check를 수행합니다.
- FastAPI가 redacted public response를 반환합니다.
- Cloud Run/Cloud Tasks는 production worker 방향입니다.
- 현재는 measured assisted alpha demo입니다.

## 15. 숫자로 외울 것

발표에서 숫자는 많지 않게, 아래만 외운다.

| 항목 | 숫자 / 상태 | 말할 의미 |
| --- | --- | --- |
| 데모 PDF | 34 pages | toy example이 아니라 실제 논문 기반 |
| 최종 gate | passed | scripted readiness gate 통과 |
| gate 시간 | 24 sec | 데모 경로가 측정됨 |
| public redaction | passed | 브라우저 응답에서 private ref 노출 방지 |
| endpoint proof | all 200 | packaged app / extracted zip smoke 통과 |
| goldset readiness | 8/8 ready | benchmark fixture 준비 완료 |

주의:

> 이 숫자는 시스템이 완성됐다는 뜻이 아니라, 무엇이 측정됐는지 말하기 위한 근거다.

## 16. 심사위원이 깊게 물으면 답할 기준

### 기술 질문이면

항상 아래 순서로 답한다.

1. 브라우저는 FastAPI만 호출한다.
2. FastAPI backend가 service layer를 호출한다.
3. service layer가 GCS/Firestore adapter를 호출한다.
4. GCS는 파일 저장, Firestore는 metadata/status 저장이다.
5. public response는 redacted schema로 내려간다.

### 연구 가치 질문이면

항상 아래 순서로 답한다.

1. 논문 요약보다 중요한 것은 근거와 불확실성을 잃지 않는 것이다.
2. Lattice는 claim/evidence/uncertainty/provenance를 구조화한다.
3. downstream artifact는 이 state에 연결된다.
4. 그래서 발표자료, figure 설명, comparison output을 만들 때 원본 근거를 추적할 수 있다.

### 한계 질문이면

숨기지 말고 이렇게 답한다.

1. 현재는 assisted alpha다.
2. production auth/sharing은 아직 아니다.
3. Cloud Run/Tasks는 production direction이다.
4. benchmark는 accuracy solved가 아니라 measurement/repair loop다.
5. 이 경계를 분리해서 보여주는 것이 오히려 시스템의 강점이다.

## 17. 마지막 더블체크 체크리스트

발표 직전에는 아래만 체크하면 된다.

- [ ] 첫 문장은 "논문 요약 도구"가 아니라 "근거와 상태를 보존하는 연구 워크스페이스"로 시작한다.
- [ ] GCS와 Firestore를 헷갈리지 않는다.
- [ ] 브라우저가 GCP에 직접 붙는다고 말하지 않는다.
- [ ] Cloud paper service layer가 GCP managed service라고 말하지 않는다.
- [ ] state는 서비스명이 아니라 schema-backed data structure라고 말한다.
- [ ] gate는 Firestore plugin이 아니라 backend validation/checkpoint라고 말한다.
- [ ] downstream artifact는 원본을 대체하지 않는 reviewable derived output이라고 말한다.
- [ ] 현재 데모의 실제 작업 실행 위치는 local Lattice backend라고 말한다.
- [ ] Cloud Run/Cloud Tasks는 현재 live demo가 아니라 production direction이라고 말한다.
- [ ] project/lab sharing은 기대 방향이며, production에는 auth/permission/audit이 필요하다고 말한다.
- [ ] benchmark는 accuracy solved가 아니라 measurement/repair loop라고 말한다.

## 18. 발표자가 바로 외울 마지막 문장

> Lattice는 논문을 한 번 요약하고 끝내는 도구가 아니라, 원본 논문에서 나온 evidence state를 구조화해서 다시 사용할 수 있게 만드는 연구 워크스페이스입니다. 이번 본선에서는 이 state를 GCP 기반 cloud-paper path로 확장했습니다. GCS는 원본 PDF와 artifact를 저장하고, Firestore는 paper metadata와 processing status를 저장합니다. 실제 처리와 검증은 Lattice FastAPI backend에서 수행하며, 브라우저에는 redacted public response만 반환합니다. 현재는 production system이 아니라 measured assisted alpha demo이고, Cloud Run/Cloud Tasks와 production sharing은 다음 단계입니다.
