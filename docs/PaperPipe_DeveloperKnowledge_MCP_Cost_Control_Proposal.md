# PaperPipe 옵션 제안서: Google **Developer Knowledge MCP**(Antigravity 연동) 도입 + 비용 통제 가드레일

작성 목적: Antigravity에서 **Google Developer Knowledge MCP**를 사용해 “구글 공식 개발문서”를 도구 호출로 검색/가져오게 하되, **예상치 못한 비용(쿼터/토큰/과금) 리스크를 구조적으로 제한**하는 운영 방안을 제안합니다.

---

## 1) 한 줄 요약(결론)

- **도입은 추천(옵션 기능)**: 구글 SDK/문서 기반 구현에서 “최신 공식 문서”를 근거로 코딩하게 만들어 품질을 올림  
- **비용/토큰 폭증은 충분히 방지 가능**: 프로젝트 분리 + 키 제한 + 쿼터/예산 알림 + 도구 호출 상한(특히 `batch_get_documents` 금지)로 통제

---

## 2) 무엇을 얻나(기대효과)

### 2.1 최신 공식 문서 기반 개발(환각/구버전 API 리스크↓)
Developer Knowledge MCP는 **구글 공식 개발 문서(Firebase/Google Cloud/Android/Maps 등)**를 검색하고 문서 내용을 가져올 수 있는 도구를 제공합니다.

- `search_documents` : 문서 검색/스니펫 반환  
- `get_document` : 단일 문서 전체 가져오기  
- `batch_get_documents` : 여러 문서 전체 가져오기

### 2.2 PaperPipe 개발에서 특히 유용한 상황
- Gemini API(Interactions/File Search/Deep Research 등)처럼 **문서 업데이트가 잦은 영역** 연동  
- “공식 문서 근거 링크를 남기는” 개발 프로세스(설계/리뷰/인수인계 품질↑)

---

## 3) 비용이 걱정되는 이유(리스크 분석)

### 3.1 Developer Knowledge API 요청량(쿼터/사용량)
- 프로젝트 단위로 쿼터/제한이 있으며, 사용량은 콘솔에서 확인/관리합니다.  
- 기본 쿼터(문서): 프로젝트당 **분당 100 요청**.

### 3.2 LLM 토큰 비용(컨텍스트 폭증)
문서에서 명시하듯, 문서 전문을 가져오면(특히 `batch_get_documents`) **토큰 사용량이 급격히 증가**해,
- LLM 비용 상승
- 응답 지연
- 컨텍스트 오버플로우
로 이어질 수 있습니다.

따라서 **“문서 가져오기(get/batch) 남발”**이 실제 비용 폭증의 핵심 원인입니다.

---

## 4) 비용 통제 가드레일(필수 세트)

### 4.1 GCP 레벨 통제(과금 사고 방지)

**A. 전용 GCP 프로젝트로 분리(강력 권장)**  
Developer Knowledge MCP만 사용하는 프로젝트를 별도로 만들어, 비용/사용량을 독립적으로 추적합니다.

**B. API Key 제한(필수)**  
키를 생성한 뒤 **API restrictions에서 “Developer Knowledge API만 허용”**하도록 제한합니다.  
→ 키 유출 시 피해 범위를 최소화

**C. 쿼터 모니터링(필수)**  
Console의 Quotas에서 Developer Knowledge API 사용량을 주기적으로 확인합니다.  
가능하면 “요청/분” 상한을 보수적으로 낮춰 두는 것도 고려합니다(정책/권한에 따라 다를 수 있음).

**D. 예산(Budget) 알림(강력 권장)**  
Cloud Billing에서 **낮은 예산(예: $1~$5) + 50/90/100% 알림**을 설정해 조기 감지합니다.

---

### 4.2 Antigravity 레벨 통제(도구 호출 상한)

#### (1) 표준 “도구 호출 상한”(프로젝트 규칙)
> 목표: **문서 가져오기(get/batch)** 최소화 + 컨텍스트 폭증 방지

- `search_documents`: 최대 **2회**
- `get_document`: 최대 **1회** (가장 유력한 문서 1개만)
- `batch_get_documents`: **금지**  
  - 정말 필요하면: “왜 필요한지”를 먼저 설명하고 **사용자 허락**을 받은 뒤 1회만

#### (2) 표준 출력 형식(토큰 절약)
- 문서 전문을 길게 붙이지 말고 **필요한 부분만 요약**
- 결과는 아래 형식으로 마무리:
  1) **핵심 결론(1~3줄)**  
  2) **구현 단계(체크리스트)**  
  3) **근거 링크 1~3개**

#### (3) 재검색 방지(운영 습관)
- 한 번 찾은 근거 링크/요약을 **프로젝트 문서(AGENTS.md/설계 노트/Obsidian)에 저장**  
→ 같은 질문으로 MCP를 반복 호출하는 빈도를 줄임

---

## 5) Antigravity 설정(필요 시)

Antigravity에서 MCP 서버 연결은 `mcp_config.json`에 아래 형태로 추가합니다(키는 교체).

```json
{
  "mcpServers": {
    "google-developer-knowledge": {
      "serverUrl": "https://developerknowledge.googleapis.com/mcp",
      "headers": {
        "X-Goog-Api-Key": "YOUR_API_KEY"
      }
    }
  }
}
```

설정 후 Manage MCP Servers 화면에서 **Refresh**를 수행합니다.

---

## 6) 롤아웃(작게 시작하는 단계별 도입)

### Phase 0 (오늘) — 최소 도입
- MCP 연결만 세팅
- “도구 호출 상한 규칙”을 AGENTS.md에 추가
- `batch_get_documents` 금지부터 강제

### Phase 1 (1주) — 비용 관제 켜기
- 전용 프로젝트 분리 + 키 제한 + 쿼터 모니터링
- Budget 알림 설정(낮게)

### Phase 2 (2주) — 실사용 피드백
- 어떤 질문에서 MCP가 실효성이 있는지 로그로 정리
- `search_documents` 2회 제한이 부족하면, 제한 완화 대신 “질문 스코프를 좁히는 템플릿”을 추가

---

## 7) 도입 판단 기준

**도입 추천**
- 구글 문서 기반 구현(특히 Gemini/Cloud)이 자주 발생한다
- “근거 링크 기반” 인수인계/리뷰 프로세스를 강화하고 싶다

**도입 보류**
- 완전 오프라인/로컬만이 핵심이다
- 지금 단계에서 구글 문서 참조가 거의 필요 없다(도입 대비 효용 낮음)

---

## 참고 링크(원문)

- Developer Knowledge MCP (설정/Antigravity 예시 포함):  
  https://developers.google.com/knowledge/mcp#config-api

- Quotas & limits (요청 제한/관리):  
  https://developers.google.com/knowledge/quota

- Developer Knowledge API (개요/레퍼런스):  
  https://developers.google.com/knowledge/api

- Cloud Billing Budgets(예산/알림):  
  https://docs.cloud.google.com/billing/docs/how-to/budgets
