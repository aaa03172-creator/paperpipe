# Inference Backend Strategy Review (Repo-Grounded)

Date: 2026-04-10
Scope: Review the inference backend strategy for a desktop-first paper agent against the current PaperPipe/Lattice repo, then recommend the smallest realistic adoption path under average lab hardware constraints.
Status: Analysis record. Canonical runtime ownership remains unchanged; this note is a dated review, not a new runtime spec.

Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
- `docs/runtime_security_env.md`
- `docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md`

Reference sources:
- [OpenAI Codex use cases](https://developers.openai.com/codex/use-cases)
- [OpenAI Codex customization](https://developers.openai.com/codex/concepts/customization/)
- [OpenAI Codex AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md/)
- [OpenAI Codex skills](https://developers.openai.com/codex/skills/)
- [OpenAI Codex MCP](https://developers.openai.com/codex/mcp)
- [OpenAI API data controls](https://platform.openai.com/docs/guides/your-data)
- [OpenAI business data privacy, security, and compliance](https://openai.com/business-data/)
- [OpenAI API key safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety)
- [Gemma 3 developer guide](https://developers.googleblog.com/en/introducing-gemma3/)
- [Gemma docs overview](https://ai.google.dev/gemma/docs/core)
- [Qwen3 blog](https://qwenlm.github.io/blog/qwen3/)
- [Qwen function calling](https://qwen.readthedocs.io/en/latest/framework/function_call.html)
- [Qwen-Agent](https://github.com/QwenLM/Qwen-Agent)
- [vLLM quickstart](https://docs.vllm.ai/en/stable/getting_started/quickstart/)
- [vLLM OpenAI-compatible server](https://docs.vllm.ai/en/stable/serving/openai_compatible_server/)
- [Anthropic harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Karpathy LLM wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

## Executive Verdict

현재 repo와 가장 잘 맞는 방향은 `C. 하이브리드 1`이다.

정리하면:

- `데이터와 정본 상태는 로컬 personal runtime에 남긴다`
- `검색/인덱스/근거/인용/노트는 로컬이 기본 owner다`
- `어려운 reasoning, final synthesis, evaluator/judge만 외부 추론으로 보낸다`
- `평균 연구실 PC를 기준으로, per-user local-only inference를 기본 제품 전략으로 두지 않는다`
- `v1은 hybrid 1을 채택하되, 내부 포트는 pluggable backend로 좁게 열어둔다`

즉, 현재 repo 기준 가장 현실적인 선택은:

`local-first data ownership + optional commercial inference + future lab-server slot`

이다.

## 1. Current Repo Fit

### 1.1 현재 repo의 중심

현재 PaperPipe/Lattice는 다음에 가깝다:

- paper-first
- job/run/artifact-first
- local-first
- single-operator-first
- evidence-linked
- human-reviewable

이 repo는 아직 다음이 아니다:

- broad chat runtime
- generalized memory platform
- shared multi-tenant workspace product

근거:

- `docs/Lattice_v3_Master_Spec.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/reports/Agent_Layer_Current_State_And_Implementation_Plan_2026-04-08.md`

### 1.2 이미 있는 추론 경계

현재 repo에는 이미 다음이 존재한다:

- `llm.mode = local | cloud | hybrid`
- `local/cloud/hybrid provider abstraction`
- same-origin `/api/*` browser path
- backend-side `X-API-Key` injection
- local-first runtime path abstraction

구현 anchor:

- `src/config.py`
- `src/llm_provider.py`
- `backend/main.py`

중요한 현재 사실:

- `/api/chat`은 live chat runtime이 아니라 stub-only다.
- 따라서 현재 제품의 AI 사용 중심은 generic conversation이 아니라 `deep-read pipeline`과 `paper/job/artifact` 흐름이다.

### 1.3 현재 구조와 충돌 여부

다음 제안은 현재 repo와 충돌하지 않는다:

- local data ownership 유지
- desktop/personal runtime 유지
- inference backend만 policy-based로 분리
- 로컬 모델을 “옵션/우선 fallback”으로 두고, 외부 모델을 “선별적 escalation”으로 쓰는 구조

다음 제안은 현재 repo와 충돌한다:

- 상용-only로 canonical state까지 중앙화하는 구조
- broad chat/memory runtime을 먼저 여는 구조
- shared multi-user backend를 기본 제품 unit으로 삼는 구조
- 클라이언트에 vendor API key를 두는 구조

## 2. Option Judgments

### A. 완전 로컬-only

판정: `기각`

이유:

- 로컬 오픈모델 성능은 크게 좋아졌지만, 그 사실이 곧 “평균 연구실 PC에서 모든 사용자에게 안정 배포 가능”을 뜻하지는 않는다.
- Gemma 3와 Qwen3는 강력한 open-weight 옵션을 제공하지만, 공식 문서도 모델 크기/정밀도/배포 프레임워크에 따라 자원 요구 차이가 크다는 전제를 깔고 있다.
- 평균 연구실 PC는 고사양 GPU 머신이 아닐 가능성이 높다.
- per-user local inference를 기본값으로 삼으면 설치, 지원, 성능 편차, 재현성, 사용자 체감 속도, 모델 다운로드/업데이트 관리가 제품 리스크가 된다.

언제만 허용할지:

- 파워 유저
- GPU가 있는 개인 연구자
- 에어갭 또는 강한 데이터 반출 제한 환경
- offline fallback path

### B. 상용-only

판정: `기각`

이유:

- 현재 repo의 local-first personal-runtime 방향과 맞지 않는다.
- canonical state와 검색 인덱스를 외부 종속적으로 느끼게 만들 위험이 크다.
- 민감 자료를 많이 다루는 연구 툴 특성과 어긋난다.
- 클라이언트 키를 원하지 않으므로, 결국 중앙 inference relay/backend가 필요해진다.
- 그러면서도 데이터 경계와 비용 통제의 긴장만 커진다.

### C. 하이브리드 1

판정: `채택`

정의:

- 로컬에 데이터/검색/노트/인덱스 저장
- 상용 LLM은 chat/final reasoning/judge에 사용

왜 맞는가:

- current repo의 local-first data ownership과 가장 잘 맞는다
- 상용 reasoning의 품질 이점을 활용할 수 있다
- 평균 연구실 PC 성능에 덜 의존한다
- UI와 canonical data 계층을 유지하면서 inference routing만 조정하면 된다
- 현재 `HybridProvider` 코드/문서와도 가장 자연스럽게 맞닿아 있다

단, 현재 repo 기준으로는 wording을 이렇게 바로잡는 것이 좋다:

- `local-first`는 data ownership과 runtime shape를 의미한다
- `local-only inference`를 기본 의미로 승격하지 않는다

### D. 하이브리드 2

판정: `보류`

정의:

- 로컬 앱 + 연구실 내부 공용 추론 서버(vLLM 등) + 필요시 상용 fallback

왜 보류인가:

- 아키텍처적으로는 매우 좋다
- Qwen3 + vLLM OpenAI-compatible server는 이 옵션과 잘 맞는다
- 하지만 모든 연구실이 GPU 서버를 갖고 있거나, 모델 운영/모니터링/업데이트/접근통제를 감당하진 않는다
- 기본 제품 경로로 두기엔 운영 전제가 무겁다

현재 단계에서의 적절한 위치:

- 기관/연구실 옵션
- managed beta 이후의 deployment template
- pluggable backend의 두 번째 slot

### E. pluggable backend

판정: `보류`

정의:

- UI와 데이터 계층은 고정
- 추론 backend만 local / lab server / commercial API로 교체

왜 보류인가:

- 내부 구현 원칙으로는 맞다
- 실제로 현재 repo는 이미 좁은 의미의 provider abstraction을 가지고 있다
- 하지만 v1에서 이것을 사용자-facing 옵션 매트릭스로 크게 열면 QA/문서/지원 복잡도가 급증한다

현재 단계의 안전한 해석:

- 외부 공개 제품 약속으로는 아직 보류
- 내부 port boundary로는 유지
- v1 product choice는 하나로 강하게 고르되, adapter shape만 pluggable하게 남긴다

## 3. Final Recommendation

가장 강하게 추천하는 선택은 `C. 하이브리드 1`이다.

제품 shape:

- desktop-first personal runtime
- local canonical data
- local retrieval and indexing
- thin commercial inference relay
- optional future lab inference server

이 선택이 지금 가장 현실적인 이유:

1. 현재 repo 방향과 충돌이 없다.
2. 평균 연구실 PC 성능에 덜 의존한다.
3. 상용 모델의 reasoning quality를 바로 활용할 수 있다.
4. API 키를 클라이언트에 두지 않을 수 있다.
5. 정본 데이터와 사용자 자산은 로컬에 남길 수 있다.
6. 나중에 lab server나 local model을 꽂을 길도 남긴다.

짧게 말하면:

`v1은 hybrid 1, v2 옵션으로 lab server, 내부 포트는 좁게 pluggable`

이 가장 안전하다.

## 4. Product Layer Split

### 4.1 Desktop App (UI)

역할:

- 사용자 인터페이스
- same-origin local runtime access
- local shell / packaged personal runtime entry

하지 말아야 할 것:

- vendor API key 보관
- canonical state owner 역할
- 외부 LLM 직접 호출

### 4.2 Local Data Layer

역할:

- `state.db`
- structured paper state
- local artifacts
- local notes / export mirrors
- project-local config
- logs/cache/runtime metadata

원칙:

- 정본 데이터는 여기에 남긴다
- source data / canonical state / compiled knowledge / export를 섞지 않는다

### 4.3 Search / Index Layer

역할:

- chunking
- embedding index
- retrieval
- citation grounding
- paper ranking / `Research DNA`

원칙:

- 제품의 핵심 자산은 이 계층과 canonical state다
- 가능한 한 로컬 유지
- inference backend가 바뀌어도 이 계층의 owner는 바뀌지 않아야 한다

### 4.4 Inference Backend Layer

권장 역할 분담:

- local model:
  - slot classification
  - tagging
  - one-liner
  - local embeddings when feasible
  - offline fallback
- commercial API:
  - hard reasoning
  - final synthesis
  - evaluator/judge
  - difficult chat-like answer composition
- lab server:
  - 기관 운영이 가능할 때의 open-model serving
  - commercial cost/privacy tension이 큰 기관용 middle layer

### 4.5 Why Search / Evidence / State must stay separate from Chat

논문 에이전트에서 진짜 제품 자산은:

- 논문 DB
- 메타데이터
- 검색 인덱스
- 근거와 인용
- 노트
- 위키/compiled knowledge
- project/runtime state

챗봇은 이 위에서 작동하는 인터페이스일 뿐이다.

따라서:

- search / evidence / canonical state는 durable system layer
- natural language chat / summary / reasoning은 replaceable inference layer

로 분리하는 것이 맞다.

## 5. Hardware Reality Check

### 5.1 평균 연구실 PC에서 무리인 것

다음은 기본값으로 두기 어렵다:

- 각 사용자 PC에서 큰 로컬 LLM 상시 실행
- 사용자마다 Ollama/vLLM/모델 파일/양자화 variant를 직접 관리
- per-user GPU 가정
- 긴 reasoning workload를 모두 local-only로 처리

이유:

- 메모리/VRAM 편차
- 설치와 모델 배포 부담
- 속도와 실패율 편차
- 지원 비용 증가
- 연구실 공용 PC나 노트북 환경의 불균질성

### 5.2 현실적인 것

현실적인 기본 경로:

- local runtime은 데이터와 검색을 책임진다
- inference는 외부 relay가 기본
- local model은 선택적 fallback
- lab server는 기관 옵션

이 구조가 중요한 이유:

- 사용자 PC 성능에 덜 의존한다
- 제품 경험이 균일해진다
- 지원이 쉬워진다
- 추론 실패를 infra 옵션으로 흡수할 수 있다

### 5.3 로컬 모델 성능 향상과 배포 현실은 다르다

핵심 경고:

- “좋은 로컬 오픈모델이 나왔다”
- “그래서 제품 배포 전략도 local-only로 가야 한다”

는 같은 명제가 아니다.

전자는 사실일 수 있다.
후자는 평균 사용자 하드웨어, 설치/지원 비용, 속도 편차, 운영 복잡도까지 봐야 성립한다.

현재 제품 단계에서는 후자가 성립하지 않는다.

## 6. Where Local Models Fit, and Where Commercial APIs Still Win

### 6.1 Gemma / Qwen이 잘 맞는 곳

- lightweight classification
- tagging
- simple extraction
- local fallback
- 기관 서버형 inference
- tool-calling or OpenAI-compatible serving experiments

Qwen3는 특히:

- tool use / MCP 쪽 공식 포지셔닝이 강하고
- local usage와 vLLM/SGLang deployment가 모두 잘 정리되어 있다

그래서:

- `lab server`
- `power-user local`

옵션으로 매우 유망하다.

### 6.2 아직 상용 API가 유리한 곳

- hardest reasoning
- high-quality final answer composition
- evaluator / judge
- ambiguous, open-ended, high-context synthesis
- 빠른 v1 품질 확보

현재 repo 기준으로는 특히:

- `escalation evaluation`
- future bounded answer synthesis
- difficult final writeups

같은 곳에서 commercial path가 유리하다.

## 7. Security and Cost

### 7.1 절대 외부로 보내지 말아야 할 것

- 비공개 PDF 원문 전체
- 전체 note vault
- 전체 wiki / compiled knowledge corpus
- full structured state dump
- backend-only raw memory
- user logs / traces
- local absolute paths
- provider keys / lab secrets

### 7.2 외부 전송이 가능한 것

원칙:

- full document가 아니라 minimal excerpt bundle만 보낸다

예:

- title
- abstract
- selected evidence spans
- de-identified methods snippet
- short claim bundle
- question-specific top-k excerpts
- source refs needed for answer grounding

현재 repo도 이 방향과 잘 맞는다:

- `generate_deep_read()`는 title + abstract 중심
- `extract_biomedical_clinical_data()`는 title + abstract + methods snippet 중심

즉, 외부 전송 최소화 정책을 바로 걸 수 있다.

### 7.3 API Key and Backend Rule

강한 규칙:

- vendor API key는 브라우저/클라이언트에 두지 않는다
- same-origin local runtime 또는 thin relay backend를 통해서만 외부 모델을 호출한다
- UI는 오직 own backend만 호출한다

OpenAI 공식 key safety 문서도:

- 브라우저/모바일 client-side 배포 금지
- own backend routing 권장

을 명시한다.

### 7.4 Commercial API cost traps

주의할 것:

- 긴 context를 매번 full-send 하는 것
- retrieval 없이 full note / full state를 넣는 것
- evaluator와 generator를 모두 상용으로 돌리며 캐시 없이 반복하는 것
- user별 hard budget 없이 background loops를 여는 것
- “chat UX 좋게 만들자”는 이유로 canonical data까지 중앙화하는 것

권장:

- local retrieval first
- top-k excerpt only
- prompt hash cache
- run-level token accounting
- user/project budget cap
- payload class별 external-allow policy

### 7.5 Data controls nuance

OpenAI business/API data는 기본적으로 학습에 쓰이지 않는다고 안내한다.

하지만 운영상 안전한 해석은 더 보수적이어야 한다:

- “not used for training by default”와 “아무 데이터도 남지 않는다”는 다르다
- abuse monitoring / application state / third-party MCP/tool 경계는 별도다
- 민감 데이터를 보낼 때는 항상 최소 전송 + explicit policy가 필요하다

## 8. Minimum Backend Shape for Desktop Distribution

### 8.1 Recommended minimum shape

데스크톱 배포를 전제로 할 때 필요한 최소 구조:

1. local personal runtime
2. local DB + artifact roots + retrieval/index
3. same-origin backend API
4. thin inference relay for commercial models

이 relay는 다음만 담당한다:

- vendor auth
- request signing
- rate limit / budget
- model routing
- audit metadata
- optional response cache

이 relay가 하지 말아야 할 것:

- canonical data store 소유
- user note/wiki owner 역할
- shared workspace state owner 역할
- product primary runtime 역할

### 8.2 Why this is still desktop-first

이 구조는 web SaaS-first가 아니다.

왜냐하면:

- 제품 unit은 여전히 personal runtime
- canonical state는 여전히 사용자 runtime에 존재
- relay는 단지 “외부 추론 호출용 infra sidecar”이기 때문이다

## 9. Repo-Addable Docs And Rules

현재 repo에 실제로 추가해도 안전한 문서 후보:

- `docs/inference_strategy.md`
  - local-first data ownership vs inference placement 분리
- `docs/inference_data_boundary.md`
  - external payload classification
- `docs/commercial_inference_relay.md`
  - thin relay contract
- `docs/lab_inference_server.md`
  - vLLM-based institution option
- `docs/inference_routing_policy.md`
  - task -> backend mapping table

AGENTS rule 후보:

- every new inference path must classify payload as:
  - `local_only`
  - `lab_allowed`
  - `external_allowed`
- canonical structured state, full notes, and raw memory must not be sent to external inference by default
- future answer generation must route through evidence-linked state before any compiled or memory layer
- do not store vendor API keys in frontend env or UI-managed settings

## 10. Smallest Executable Plan

### 10.1 1-week realistic slice

1주 내 가장 작은 실행안:

1. 문서 확정
   - `local-first data != local-only inference`
2. routing policy 추가
   - local preferred / commercial allowed lanes 명시
3. run metadata 추가
   - `selected_backend`
   - `payload_class`
   - `token_estimate`
   - `redaction_applied`
4. thin commercial relay stub 설계
   - no canonical storage
   - request-budget and audit only

### 10.2 Suggested v1 routing

v1 권장:

- local preferred:
  - slot classification
  - tagging
  - one-liner
  - embedding
  - simple extraction
- commercial allowed:
  - escalation judge
  - difficult final synthesis
  - future bounded answer composition
  - high-ambiguity reasoning
- lab server later:
  - institutional deployment
  - cost-sensitive teams
  - data boundary stricter than commercial, less strict than local-only

### 10.3 What not to do in v1

- do not open a broad chat memory runtime
- do not treat local-only inference as the product identity
- do not expose pluggable backend choice as a large end-user matrix
- do not centralize canonical state into a shared backend
- do not ship client-side vendor keys

## 11. Decision Summary

### A. 현재 repo와의 적합성 판단

- 현재 구조와 충돌하지 않는 방향:
  - `hybrid 1`
  - local data ownership
  - thin commercial relay
  - future lab server option
- 현재 구조와 충돌하는 방향:
  - commercial-only centralization
  - broad chat-first runtime
  - shared backend as default product unit
  - client-side key

### B. 선택지별 판정

- A. 완전 로컬-only: `기각`
- B. 상용-only: `기각`
- C. 하이브리드 1: `채택`
- D. 하이브리드 2: `보류`
- E. pluggable backend: `보류`

### C. 최종 권장안

하나를 가장 강하게 추천하면:

`C. 하이브리드 1`

단, 내부 포트 설계는 향후 `E`로 갈 수 있게 좁게 유지한다.

## 12. Required Closing Summary

### 1. 내 의도를 한 문장으로 요약하면

로컬 퍼스트 연구용 데스크톱 에이전트를 만들되, 평균 연구실 PC 현실과 보안 제약을 감안해 어떤 추론 백엔드 전략이 지금 실제로 채택 가능한지 repo 기준으로 판정하려는 것이다.

### 2. 가장 작은 성공 조건

정본 데이터와 검색 인덱스는 로컬 personal runtime에 남기고, 어려운 reasoning만 thin commercial relay로 보내며, 어떤 경우에도 vendor key를 클라이언트에 두지 않는 것이다.

### 3. 지금 당장 추가할 파일 5개

- `docs/inference_strategy.md`
- `docs/inference_data_boundary.md`
- `docs/commercial_inference_relay.md`
- `docs/lab_inference_server.md`
- `docs/inference_routing_policy.md`

### 4. 지금 단계에서 가장 위험한 오판 3개

- 로컬 모델 품질 향상을 곧바로 “모든 사용자 PC에서 로컬 추론 가능”으로 착각하는 것
- commercial API를 붙이면서 canonical data까지 중앙화하는 것
- v1부터 full pluggable backend를 사용자 옵션으로 열어 제품/운영 복잡도를 불필요하게 키우는 것
