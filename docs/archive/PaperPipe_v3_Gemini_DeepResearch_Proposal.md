# PaperPipe v3.0 제안서(옵션): **Gemini Deep Research** 기반 “클라우드 에스컬레이션” 모듈 도입

Status: Proposal  
Date: 2026-03-09  
Owner: Repository maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

작성 목적: PaperPipe의 **로컬-first(Ollama/effGen)** 전략을 유지하면서, 특정 상황(최신 정보 필요, 인용 포함 보고서 필요, 장시간 리서치 필요)에만 **Google Gemini Deep Research Agent**를 *선택적으로* 붙이는 업그레이드 방안을 제안합니다.

---

## 1) 왜 지금 검토할 가치가 있나

Gemini Deep Research Agent는 단순 생성 모델이 아니라 **“계획 → 검색 → 읽기 → 반복 → 종합”** 루프를 수행해, **인용(cited) 보고서** 형태로 결과를 내는 “analyst-in-a-box” 타입의 에이전트로 설명됩니다. citeturn1view0

PaperPipe 관점에서 이것이 유용한 구간은 명확합니다.

- **웹 기반 최신 정보**가 결과 품질을 결정하는 경우 (예: 신약/표적/규제/최근 임상 업데이트)
- **교수님/랩 공유용**으로 *근거 링크가 포함된 보고서*가 필요한 경우
- 로컬 RAG/검색만으로는 답이 제한되는 **시장/경쟁/동향/문헌 검토**(몇 분 단위) 작업 citeturn1view0

---

## 2) 핵심 사실(도입 전 반드시 알아야 할 제약)

### 2.1 API/호출 방식
- Deep Research Agent는 **Interactions API에서만 사용 가능**하며, `generate_content`로는 접근할 수 없습니다. citeturn1view0  
- Interactions API 자체도 **Beta**로, 스키마/기능 변경 가능성이 명시돼 있습니다. citeturn1view1turn2view2

### 2.2 장시간 작업(비동기) 전제
- Deep Research는 **몇 분이 걸릴 수 있어** `background=true`로 비동기 실행 후 폴링이 권장됩니다. citeturn1view0  
- 스트리밍(`stream=True`) + `thinking_summaries` 이벤트를 받는 패턴도 문서에 제시됩니다. citeturn2view4  
- 또한 `background=True` 실행에는 **`store=True` 요구사항**이 명시돼 있습니다. citeturn2view2  
  - (주의) PaperPipe 통합 시, SDK 호출부에서 `store` 옵션 지원 여부/기본값 확인이 필요합니다. *(이 부분은 실제 SDK 버전/샘플 코드로 확인해야 하며, 본 제안서는 설계 수준입니다.)*

### 2.3 도구/구조화 출력 관련 제한
- Deep Research Agent는 **커스텀 function calling 도구나 remote MCP 서버를 붙일 수 없습니다.** citeturn2view2  
- 또한 **structured outputs(스키마 강제)와 human-approved planning을 지원하지 않는다고 명시**돼 있습니다. citeturn2view2  
→ 즉, PaperPipe가 중요시하는 “결정론적 JSON 출력/검증”은 **Deep Research가 아니라, 로컬/일반 모델 + Action Gates에서 계속 담당**해야 합니다.

---

## 3) PaperPipe에 어떻게 붙이는 게 “맞는”가 (권장 아키텍처)

### 결론부터: **로컬-first + 클라우드(Deep Research) 옵션 에스컬레이션**
- **Daily Routine / Tagging / Action Gates**는 기존처럼 **결정론적(검증 가능) 파이프라인** 유지
- “심층 분석/보고서 생성”에서만 **선택적으로** Deep Research 호출

이렇게 하면:
- 비용/프라이버시를 지키면서도,
- “필요할 때만” 인용 기반 보고서를 뽑을 수 있습니다. citeturn1view0

---

## 4) 기능 설계(제안): PaperPipe v3.0에 추가할 “클라우드 Deep Research 모듈”

### 4.1 CLI 추가(옵션 기능)
- `paperpipe deepresearch --paper <id> --question "<질문>"`  
  - 특정 논문(또는 노트) + 질문을 입력으로 전달
- `paperpipe deepresearch --topic "<주제>" --days 90`  
  - “최근 90일 문헌 + 웹” 혼합 리서치 보고서 생성

Deep Research는 저지연 채팅이 아니라 “분 단위” 분석에 적합하다고 문서에 명시돼 있으므로, CLI가 잘 맞습니다. citeturn1view0

### 4.2 출력 포맷(권장)
Deep Research가 구조화 출력이 약하므로(제약 명시), citeturn2view2  
출력은 **Markdown 보고서 + 인용 링크** 형태를 기본으로 하고, PaperPipe는 다음만 강제합니다.

- `report.md` (본문)
- `sources.json` (추출한 출처 링크 목록/메타데이터)
- `run.json` (요청/옵션/interaction_id/status/log)

---

## 5) “내 데이터 + Deep Research”를 쓰는 방법: File Search 도입(선택)

Deep Research는 기본적으로 `google_search` + `url_context` 도구로 웹 접근이 켜져 있고, citeturn1view0  
내 데이터를 붙이려면 **`file_search` 도구를 추가**해야 합니다. 단, **Deep Research에서 file_search는 실험(Experimental)** 이라고 명시돼 있어요. citeturn1view0

### 5.1 File Search의 장점(설계 관점)
- 파일 업로드 시 자동으로 **청킹 → 임베딩 → 색인**이 되고, 청킹 전략도 설정 가능합니다. citeturn2view0  
- 검색은 semantic search 기반(임베딩 유사도)로 동작합니다. citeturn2view0

### 5.2 File Search의 현실적 제약(운영 관점)
- 파일 크기 제한(문서당 100MB) 및 프로젝트 스토어 용량 제한(티어별)이 존재합니다. citeturn1view2  
- 저장 용량은 무료, 인덱싱 시 임베딩 비용이 발생하고, 쿼리 시 임베딩은 무료라는 과금 안내가 있습니다. citeturn1view2  
  - 정확한 총 비용은 *사용 데이터 토큰량 + 모델 토큰량*에 따라 달라져, 실제 파일 크기/텍스트 길이 기준으로 추정이 필요합니다.

---

## 6) 통합 구현 로드맵(작게 시작하기)

### Phase 0 — “API POC” (1~2일)
- Interactions API로 Deep Research 실행/폴링 동작 확인 (Python SDK 기준 예시 제공) citeturn1view0  
- 스트리밍 + thinking summaries 동작 확인(선택) citeturn2view4  
- 결과를 `reports/deepresearch/<timestamp>/`에 저장

### Phase 1 — “PaperPipe 옵션 커맨드로 편입” (2~4일)
- `paperpipe deepresearch` 커맨드 추가
- config.yaml에 gemini 설정 추가(기본 OFF)
- logs에 interaction_id, status, 사용 옵션 저장

### Phase 2 — “File Search(내 데이터) 결합” (4~7일)
- `storage/rag/`의 텍스트(또는 PDF) 중 일부를 File Search store로 업로드
- 청킹 파라미터(토큰/오버랩) 튜닝 citeturn2view0  
- Deep Research에 tools로 `file_search` store를 전달 citeturn1view0  
- (중요) **Experimental**이므로, “핵심 Daily”가 아니라 “옵션 deepresearch”에서만 사용 권장 citeturn1view0

---

## 7) config.yaml 제안(초안)

```yaml
deepresearch:
  enabled: false          # 기본 OFF (옵션 기능)
  provider: gemini
  agent: deep-research-pro-preview-12-2025
  background: true
  stream: false
  thinking_summaries: auto   # stream=true일 때만 의미 있음
  store: true                # background 요구사항(문서 기준)

  tools:
    google_search: true      # 기본 활성(문서 기준)
    url_context: true
    file_search:
      enabled: false         # Experimental → 기본 OFF
      store_names: []        # 예: ["fileSearchStores/my-store-name"]

  output:
    dir: "reports/deepresearch"
    save_sources_json: true
    save_trace_jsonl: true

  safety:
    redact_inputs: true      # 논문 전문/개인정보가 프롬프트에 그대로 나가지 않게 최소화
    max_minutes: 20          # 문서상 60분 한도, 운영은 20분 추천
```

---

## 8) 기대효과 vs 리스크 (PaperPipe 관점)

### 기대효과
- **인용 포함 보고서**: 교수/랩 공유에 바로 쓰기 좋음 citeturn1view0  
- **장시간 리서치 자동화**: background + polling/stream 패턴이 공식 제공 citeturn1view0turn2view4  
- **웹+내 데이터 혼합**: File Search를 통해 RAG 유사 패턴 가능(Experimental) citeturn1view0turn2view0

### 리스크/주의
- Preview/Beta: 스키마 변경 가능 citeturn1view0turn1view1turn2view2  
- 커스텀 도구/구조화 출력 부재: PaperPipe의 “정밀 태깅/게이트”를 대체하면 안 됨 citeturn2view2  
- 웹검색 기본 ON: 프라이버시/재현성 이슈 → “옵션 기능 + 로그/인용 저장” 필수 citeturn1view0  
- 비용: “한 번 요청”이 루프를 돌며 다수 호출/검색을 유발할 수 있음(문서가 agentic workflow임을 명시) citeturn1view0

---

## 9) 추천 결론(도입 판단 기준)

**도입 추천 조건**
- “최신 웹 근거 + 인용 포함 결과물”이 실제로 자주 필요하다
- PaperPipe 결과물을 교수님/랩/포트폴리오 형태로 **보고서화**하는 니즈가 있다

**도입 보류 조건**
- 완전 로컬(프라이버시/오프라인) 운영이 핵심이다
- 구조화 JSON 출력/결정론적 파이프라인이 핵심이다 (Deep Research는 구조화 출력 미지원) citeturn2view2

---

## 참고 링크(원문)

아래는 원문 링크입니다(복사/공유용).

```text
Deep Research 문서:
https://ai.google.dev/gemini-api/docs/deep-research?hl=ko

Interactions API 문서:
https://ai.google.dev/gemini-api/docs/interactions

File Search 문서:
https://ai.google.dev/gemini-api/docs/file-search
```
