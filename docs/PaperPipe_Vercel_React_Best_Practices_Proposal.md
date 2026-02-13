# PaperPipe(옵션) 제안서: **Vercel React Best Practices / Agent Skills / AGENTS.md 패턴** 도입

> 목적: PaperPipe에 **React/Next.js 기반 UI(대시보드/리포트 뷰어)**를 붙이거나, 향후 프론트엔드 코드를 **코딩 에이전트(Claude Code/Cursor/Codex 등)**에게 맡길 때, **성능 회귀를 예방하고 리뷰 기준을 표준화**하기 위한 “가이드라인 패키지”를 옵션으로 도입합니다.

---

## 1) 왜 PaperPipe에 도움이 될 수 있나

Vercel은 “React/Next.js 성능 최적화 경험(10+년)”을 **규칙(rule) 저장소** 형태로 정리했고, 이 규칙들이 **AI 에이전트가 바로 참고할 수 있는 형태(AGENTS.md + Agent Skills 패키지)**로 제공된다고 설명합니다.

PaperPipe에서 유의미한 적용 시나리오는 아래 2가지입니다.

1) **PaperPipe Web UI를 만들거나(또는 만들 계획이 있는 경우)**
- 논문 리스트/필터/태그 편집/근거 확인/리포트 뷰어 같은 UI는 데이터 패칭, 렌더링, 번들 크기에서 성능 문제가 쉽게 생깁니다.
- Vercel 프레임워크는 성능 문제의 우선순위를 “미세 최적화”보다 **(1) async waterfall 제거, (2) 번들 크기 감소**로 잡는다고 밝힙니다.

2) **프론트 코드를 코딩 에이전트가 만지게 할 계획이 있는 경우**
- 사람이 성능/패턴 기준을 일일이 코멘트하지 않아도, 에이전트가 일관된 규칙을 참조하도록 “지식 패키지”를 깔아두는 개념입니다.

---

## 2) Vercel 측에서 제공하는 구성요소 요약

### A. React Best Practices 규칙 저장소(40+ rules, 8 categories)
- “40+ 규칙, 8개 카테고리, 영향도(CRITICAL~LOW) 기반 정렬”로 구성되었다고 안내합니다.
- 시작점은 **Eliminate waterfalls / Reduce bundle size**입니다.

### B. Agent Skills 패키지(설치 1줄)
- Vercel은 위 규칙을 **Agent Skills**로 패키징해 “Opencode, Codex, Claude Code, Cursor 등”에서 쓸 수 있다고 안내합니다.
- 설치 커맨드(공식 안내):

```bash
npx skills add vercel-labs/agent-skills
```

### C. AGENTS.md 패턴(에이전트 ‘상시 컨텍스트’)
- 규칙 파일들이 `AGENTS.md`로 컴파일되어 에이전트가 “항상 접근 가능한 컨텍스트”로 쓰도록 설계되었다고 설명합니다.
- 별도 글에서 Vercel은 “AGENTS.md가 skills보다 에이전트 평가에서 더 높은 성능”을 보였다는 실험/사례도 공유합니다.
- Next.js 프로젝트에 대해 `AGENTS.md`에 문서 인덱스를 주입하는 codemod 커맨드도 제시합니다:

```bash
npx @next/codemod@canary agents-md
```

---

## 3) PaperPipe에 맞춘 권장 도입 방식(현실적인 “옵션 모듈”)

> 핵심: PaperPipe 코어(논문 파이프라인)는 그대로 두고, **UI/프론트가 생길 때만** 적용하는 게 가장 효율적입니다.

### 3.1 “UI가 생기는 경우” (강력 추천)
- PaperPipe가 다음 형태로 진화할 때 유효:
  - 논문 리스트/태그/게이트 상태를 한 화면에서 보는 대시보드
  - Deep Read 결과(요약/근거/표)를 렌더링하는 리포트 뷰어
  - Obsidian 노트 링크/관련 논문(embedding) 추천을 보여주는 그래프/카드 UI

이 경우 Vercel 규칙을 “성능/구조 기본값”으로 채택하면,
- 초기부터 waterfall/번들 비대화를 방지하고,
- “에이전트 PR”의 품질을 일정 수준 이상으로 끌어올리는 용도로 쓸 수 있습니다.

### 3.2 “UI가 아직 없고 CLI만 있는 경우” (보류 또는 최소 도입)
- 지금 당장 PaperPipe 코드베이스에 React/Next.js가 없다면,
  - 굳이 agent-skills를 먼저 깔 필요는 없습니다.
- 다만, **향후 UI를 만들 계획이 확실**하다면:
  - “도입 계획”만 문서화해 두고,
  - UI 착수 시점에 설치/적용하는 편이 깔끔합니다.

---

## 4) 실행 계획(도입 체크리스트)

### Phase 0 — 의사결정(10분)
- PaperPipe에 “웹 UI”를 붙일지 먼저 결정:
  - 붙인다 → Phase 1 진행
  - 아직 모름 → Phase 1 대신 “문서만 남기고 보류”

### Phase 1 — Agent Skills 설치(5분)
프로젝트 루트에서:

```bash
npx skills add vercel-labs/agent-skills
```

- 설치 후, 사용하는 코딩 에이전트(Claude Code/Cursor 등)가
  - “이 프로젝트의 agent skill을 참고해서 리뷰/리팩터링해줘”
  같은 프롬프트로 실제로 참조하는지 확인합니다.

### Phase 2 — AGENTS.md 전략 선택(15~30분)
둘 중 하나를 선택합니다.

**옵션 A) Skills만 사용**
- 가장 간단합니다.
- 단점: 에이전트가 “스스로 skills를 불러오는 결정을” 못 하면 효과가 약해질 수 있음(도구/에이전트에 따라).

**옵션 B) AGENTS.md 패턴 병행**
- PaperPipe 루트에 `AGENTS.md`를 두고
  - “PaperPipe 프로젝트 규칙(폴더 구조/네이밍/데이터 계약/스키마)” + “React 성능 규칙 요약/링크”
  를 상시 컨텍스트로 제공합니다.
- Next.js 기반이라면, Vercel이 제시한 codemod도 검토:

```bash
npx @next/codemod@canary agents-md
```

### Phase 3 — “PaperPipe UI”에서의 최소 성능 가드레일(추천)
(이 단계는 실제 UI가 생겼을 때만)

- PR 리뷰 기준에 아래 2개를 상시 포함:
  - **waterfall(순차 await/순차 fetch) 제거**
  - **번들 사이즈(무거운 import) 관리**
- 리포트/리스트 화면은 특히:
  - “필터/정렬/검색” 같은 상호작용이 많아 리렌더 비용이 커지기 쉽습니다.
  - AGENTS.md/skills를 통해 에이전트가 해당 문제를 먼저 지적하도록 세팅합니다.

---

## 5) 리스크 / 주의사항

- PaperPipe에 React/Next.js 코드가 없는 단계에서 “조기 도입”하면 체감 효과가 작을 수 있습니다.
- Skills는 에이전트마다 “자동 트리거” 품질이 다를 수 있으므로,
  - 필요 시 `AGENTS.md`(상시 컨텍스트) 방식을 병행하는 게 더 안정적일 수 있습니다(실험 글 참고).

---

## 6) 참고 링크(원문)

- Vercel Blog — Introducing: React Best Practices  
  https://vercel.com/blog/introducing-react-best-practices

- GitHub — vercel-labs/agent-skills (설치 커맨드 포함)  
  https://github.com/vercel-labs/agent-skills

- GitHub — react-best-practices skill 폴더  
  https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices

- Vercel Blog — AGENTS.md outperforms skills in our agent evals (AGENTS.md 패턴/실험)  
  https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals

- Skills 사이트(표기된 프로젝트 링크)  
  https://skills.sh/vercel-labs/agent-skills
