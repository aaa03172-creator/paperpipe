# UX Review Report - Skills Actions Flow

Status: Current review artifact  
Date: 2026-03-13  
Owner: Lattice runtime maintainers  
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-13
Reviewer: Codex

## Input
- Screen/Flow: `/papers/:slug` right-panel actions -> structured results -> claim cards
- Goal action: 연구자가 note detail에서 안전한 액션을 실행하고, 결과를 markdown dump가 아닌 카드 UI로 바로 이해한다.
- Primary persona: Obsidian + Zotero를 쓰면서 논문 노트를 웹에서 검토하는 연구자
- Current friction: core action/result flow는 보이고 structured sidecar도 canonical source로 정리됐다. blocked/disabled action의 정책 거절 이유와 secret requirement는 액션 카드에서 바로 읽히게 됐다. 남은 마찰은 크게 줄었고, run 직후 `pp.*` signal diff도 `new` vs `changed`로 나뉘어 Actions 카드에서 바로 확인 가능해졌다.
- Success metric: action click-through rate, structured run re-open rate, related paper exploration rate
- Constraints:
  - FastAPI + Vite + React Router + TailwindCSS 유지
  - `--pp-*` 토큰과 dark-first Lattice tone 유지
  - `rules/product-psychology/SKILL.md`
  - `rules/product-psychology/references/review-checklist.md`
  - `rules/product-psychology/references/bias-framework.md`
  - `rules/product-psychology/references/ethics-checklist.md`
  - `rules/product-psychology/references/prompt-templates.md`

## 1) Quick Review (5 min)
- Block: 핵심 block은 풀렸다. 지금은 결과 변화량도 직접 보인다. 남은 일은 이 diff를 더 길게 가져갈지, 더 압축할지에 대한 운영 판단이다.
- Interpret: Actions card, Automation Results cards, ClaimSet cards로 해석 비용은 많이 낮아졌다.
- Act: note detail 우측 패널이 기본 실행 경로로 충분히 기능한다.
- Store: structured runs가 누적되는 현재 모델은 유지할 가치가 있다.
- Ethics first pass: network/secrets/license 정보를 버튼 옆 정책 배지로 노출해 숨은 자동화를 피한다.
- Decision: acceptance gap은 없다. 남은 항목은 trigger-based backlog로만 유지한다.

## 2) Full Review (P0/P1/P2 prioritized)
### P0
- 6P storyboard context:
  - Problem: 연구자는 note를 읽다가 “지금 바로 검증/요약을 돌리고 싶다”.
  - Emotion: storage/artifacts를 뒤지기 싫고, 결과를 빠르게 믿고 싶다.
  - Action: detail page 우측 패널에서 버튼을 본다.
  - Struggle: 결과가 본문 dump 또는 숨은 JSON이면 맥락이 끊긴다.
  - Attempt: button -> sidecar write -> cards render 흐름으로 해결했다.
  - Happy Ending: note detail 하나로 실행/결과/관련 논문 탐색까지 이어진다.
- BMAP:
  - Motivation: 높다. note를 이미 보고 있으므로 문맥 동기가 강하다.
  - Ability: 지금은 충분하다. 기능 위치와 결과 source of truth가 정리됐다.
  - Prompt: 우측 패널 버튼이 가장 적합한 prompt로 자리 잡았다.
- B.I.A.S:
  - Block: 핵심 실행 진입점은 해결됨
  - Interpret: markdown dump 대신 카드 UI가 중심이 됨
  - Act: 버튼 한 번 + 카드 확인 경로가 정착됨
  - Store: structured history가 재사용 기억을 만든다
- Peak-End:
  - peak는 실행 직후 결과 카드가 생기는 순간이다.
  - pit는 raw json/markdown을 직접 찾아가야 하는 순간이다.
  - transition은 본문 읽기 -> 우측 패널 실행으로 짧아졌다.
  - end는 related paper의 shared tags plus structured signals 탐색으로 이어져야 한다.
- Ethics:
  - Regret: 허용. 정책이 드러난다.
  - Black Mirror: allowlist 없는 network 실행은 위험.
  - In Real-Life: 조심스러운 연구 보조자처럼 동작해야 한다.

### P1
- Actions card는 버튼 외에도 `network`, `sandbox`, `license`, `source_skills`, optional `secret <ENV_NAME>`를 같이 보여주고 있다.
- secret-required action은 secret badge와 disabled reason을 preflight 단계에서 함께 보여준다.
- Automation Results는 ts/action/status/summary 중심으로 읽히고, Claim cards는 evidence와 confidence를 바로 보여준다.
- `Signal updates`가 이미 결과 변화량을 바로 보여주므로, 남은 개선은 diff 길이 제어와 grouping 정도다.

### P2
- list page에 `ClaimSet`, citation count, appraisal 신호는 이미 노출되고 있다. 추가 작업은 운영 모드나 audit depth 쪽으로 넘어간다.
- 현재 범위에서 추가 UI 변경은 필요하지 않다. blocked action 빈도나 audit 요구가 실제로 커질 때만 다시 연다.

## 3) BMAP diagnosis
- Motivation: note를 읽는 시점 자체가 행동 동기다.
- Ability: 버튼과 카드 덕분에 핵심 실행 경로의 능력 장벽은 이미 낮아졌다.
- Prompt: 우측 패널이 가장 적절한 실행 prompt로 자리 잡았다.

## 4) B.I.A.S diagnosis
- Block: 남은 block은 실행 위치가 아니라, diff가 길어질 때 읽기 밀도가 올라갈 가능성이다.
- Interpret: 결과는 이미 짧은 summary + badge + evidence bullets 중심으로 읽힌다.
- Act: 정책이 명확하고 action entrypoint도 보여 실행 불안이 많이 줄었다.
- Store: structured runs는 이미 신뢰 가능한 기억 장치로 기능한다.

## 5) Peak-End design notes
- Peak: 실행 직후 새 result card가 상단에 뜨는 순간
- Pit: 큰 markdown append가 본문을 오염시키는 순간
- Transition: reading -> action -> cards -> related papers
- End: shared tags plus structured signals가 다음 탐색 행동을 만든다

## 6) Ethics Check
- Regret: 통과. 나중에 봐도 숨은 자동화처럼 보이지 않는다.
- Black Mirror: network/secrets가 기본 허용이면 실패. 정책 allowlist 필수.
- In Real-Life: 친절한 연구 조수에 가깝다. 무단 외부 호출 세일즈맨처럼 보이면 안 된다.
- 대응:
  - allowlist network만 허용
  - secret-required action은 정책과 UI에 둘 다 노출
  - note 본문에는 짧은 summary만 남김

## 7) Concrete changes
- Component:
  - `ActionsPanel`
  - `AutomationResultsPanel`
  - `ClaimSetPanel`
  - `ActionsPanel` 내 `Add short note summary` toggle로 quiet run을 지원한다.
  - quiet-run toggle은 note-local UI state로 취급하고, 다른 note로 이동하면 기본값으로 reset한다.
  - secret-required action은 `secret <ENV_NAME>` badge와 disabled reason copy를 같은 카드 안에서 보여준다.
  - action 직후 `Signal updates` 블록으로 `pp.signals` 변화량을 inline badge로 보여주고, 새 값과 변경값을 구분한다.
  - `Signal updates`는 persisted artifact가 아니라 note-local UI state다. reload, action failure, 다른 note 이동 시 reset된다.
  - `AutomationResultsPanel`은 `state updated`, `frontmatter updated`, `body summary/body skipped` write-scope badges를 보여준다.
- Route:
  - `POST /skills/run`
  - `GET /paper-notes/:slug` response extends with `structured_state`, `available_actions`
- Copy:
  - “Safe skill actions gated by license, network, and secret policy.”
  - “Structured runs read from the note sidecar state.”
- Default action:
  - 본문 읽기는 유지
  - 실행/결과는 우측 패널 우선
- Data/API contract:
  - canonical source is `.pp/<slug>/state.json`
  - frontmatter `pp.*`는 summary-only
  - `available_actions`는 preflight policy state(`enabled`, `disabled_reason`, `secrets_required`)와 display metadata(`network`, `sandbox`, `license`, `source_skills`)를 함께 내려준다.
  - quiet run도 `state.json`, raw run JSON, frontmatter `pp.*`는 계속 갱신하고 markdown body append만 건너뛴다.
  - `run.artifacts.write_scope`는 `{ structured_state, frontmatter_pp, markdown_summary }` booleans를 담고, Automation Results badges는 이 값을 그대로 읽는다.
  - legacy runs without `artifacts.write_scope` are not backfilled; their cards render without write-scope badges.

## 8) Next PR-sized actions
이 섹션은 flow-local trigger backlog다. cross-surface concern으로 커지기 전까지 `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`로 승격하지 않는다.

1. disabled reason 유형이 secret 외에도 더 다양해지면 policy note와 user-facing copy를 분리할지 검토하기
2. signal diff가 길어질 경우 noisy key suppression이나 grouping 규칙을 더 강화할지 검토하기
3. write-scope badge의 deep link는 운영 디버깅 수요가 확인될 때만 검토하기
