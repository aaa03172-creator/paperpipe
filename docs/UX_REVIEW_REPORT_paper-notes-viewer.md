# UX Review Report - Paper Notes Viewer

Status: Current review artifact  
Date: 2026-03-13  
Owner: Lattice runtime maintainers  
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-13
Reviewer: Codex

## Input
- Screen/Flow: `/papers` list, `/papers/:slug` detail, note -> workbench handoff
- Goal action: 사용자가 논문 노트를 빠르게 찾고, 읽고, 관련 논문을 탐색한 뒤 필요 시 Workbench로 넘어간다.
- Primary persona: Obsidian vault를 이미 쓰고 있는 연구자/대학원생
- Current friction: list/detail/workbench의 핵심 흐름, structured search, related reasoning, operational summary 정리, triage `Content Review`와 workbench `issue focus` 연결은 완료됐다. workbench의 `Content Review` clear-state는 paper detail이 준비된 뒤에만 노출되도록 정리됐고, flagged-path도 backend e2e로 검증됐다. 현재 남은 마찰은 density preset이 실제로 필요한지, 그리고 timeline/stepper까지 같은 status grammar를 넓힐 가치가 있는지 아직 사용 근거가 부족하다는 점이다.
- Decision checkpoint:
  - `issues_state`는 backend contract로 유지하되, producer가 직접 저장한 값이 있으면 그것을 1차 source-of-truth로 사용하고 legacy row에서만 heuristic fallback을 사용한다는 점을 기록한다.
  - richer taxonomy(`review_flags[]`)는 source-of-truth가 생기기 전까지 도입하지 않는다.
  - cross-surface viewer/workbench 후속 작업은 repo-wide queue와 이 UX review report의 flow-local trigger backlog에서 추적한다.
- Success metric: `/papers` 진입 후 2분 내 목표 논문 도달률, 상세 화면에서 related 클릭률, note -> workbench 전환률
- Constraints:
  - 기존 Lattice 런타임은 FastAPI + Vite + React Router 기반이다.
  - 현재 `--pp-*` 토큰 기반 테마와 dark-first 톤을 유지해야 한다.
  - vault 경로와 PDF 링크는 공개 배포보다 사설/로컬 사용성을 우선한다.

## 1) Quick Review (5 min)
- Block: 큰 플로우 단절은 없다. 남은 마찰은 density와 timeline/stepper grammar를 더 넓힐지에 대한 근거 부족이다.
- Interpret: 상세 화면, reference 정책, 목록 hierarchy, related reasoning, list/detail operational state, triage/workbench rail entry point, repair/rebuild 분리, sync/repair/rebuild notice 정렬, shared status summary primitive, note status chip visual language 정리, `/papers` contract 기반 ops_summary 공급 정리, triage `Content Review` 분리는 완료됐다.
- Act: `Open in Workbench` CTA는 명확하고 모바일 고정 버튼도 합리적이다.
- Store: Related link, markdown section, Workbench handoff는 남지만, 읽기 종료 후 "다음에 뭘 할지"가 약간 약하다.
- Ethics first pass: 과장된 CTA나 조작 패턴은 없다.
- Decision: viewer의 핵심 흐름은 현재 범위에서 닫혔다. 남은 viewer-polish는 실사용 근거가 생길 때만 다시 검토한다.

## 2) Full Review (P0/P1/P2 prioritized)
### P0
- 현재 기준 치명적 플로우 단절은 없다.
- API, markdown, related papers, references 정책은 기본 동작을 충족한다.

### P1
- list/detail/triage/workbench rail에서는 `Healthy` / `Action needed`와 `Stats report is missing or empty.` 문구가 맞춰졌다.
- Workbench의 `Repair Stats`는 missing-state 전용 CTA로 남고, overwrite semantics를 갖는 `Rebuild Stats`는 `Advanced actions` 아래로 이동했다.
- `Sync to Obsidian`도 같은 inline notice/success/error 패턴을 사용하도록 맞췄다.
- `OperationalStateSummary`로 list/detail/triage/rail/workbench body가 같은 badge + reason + action hint 세트를 읽도록 맞췄다.
- note processing status chip, note frontmatter status, operational state badge는 같은 tone/badge 계층으로 정리됐다.
- triage의 `Content Review`는 별도 header/카피/색으로 분리되어 artifact health와 다른 신호로 읽히게 됐다.
- workbench도 `Content Review` notice와 body summary를 통해 triage의 issue-focus 문맥을 유지한다.
- clear-state `Content Review` notice는 paper detail 로드 전에는 숨겨져 잘못된 초기 문구를 줄인다.
- `issues_label`은 backend contract 값을 그대로 보존해 triage/workbench의 `Content Review` detail copy에 사용한다. 지금은 taxonomy를 추측으로 늘리지 않고, source-of-truth label fidelity를 우선한다.
- workbench 상단 `Content Review` notice도 generic count만 남기지 않고, 같은 `issues_label` detail을 함께 보여줘 triage -> workbench 첫 화면의 문맥 손실을 줄인다.
- rail은 밀도를 유지해야 하므로, 선택된 flagged paper에만 `issues_label` detail 한 줄을 보여준다. count chip은 유지하되 active context만 깊게 보여주는 방식이다.
- `issues=0`이어도 `issues_label`이 `Not analyzed`처럼 availability 상태를 뜻할 수 있으므로, `Content Review`는 zero-issue를 무조건 `Clear`로 해석하지 않는다. `Unavailable` 상태를 별도로 둬 의미 과장을 막는다.
- `Unavailable`은 triage/workbench summary에만 머물지 않고, rail의 compact chip/selected detail에도 반영돼 navigation surface에서도 `Clear`와 섞이지 않는다.
- `Unavailable` 해석은 이제 프런트 regex에만 의존하지 않고, backend `/papers` contract의 `issues_state`가 1차 source-of-truth가 된다. backend는 저장된 `issues_state`가 있으면 그것을 우선 사용하고, 없을 때만 heuristic fallback을 사용한다.
- legacy batch producer와 watcher local producer는 producer-owned `processing_status`와 분석 실행 여부를 기준으로 `issues_state`를 직접 저장하므로, viewer는 이 경로들에서는 label-derived state보다 더 안정적인 explicit source를 갖게 됐다.
- backend fallback도 `issues` / `issues_label`만 보지 않고 legacy `status`를 읽으므로, `NEW` 같은 미분석 row가 `Clear`로 과잉 해석되지 않는다. Zotero sync 신규 row는 `issues_state="unavailable"`를 직접 저장한다.

### P2
- 목록 row-card는 vault browser 쪽으로 개선됐지만, 추후 density presets를 둘지 검토 여지가 있다.
- 상세 화면 outline은 추가됐지만, 향후 더 세밀한 section navigation까지 갈지는 실제 사용 빈도를 보고 결정하는 편이 낫다.
- 현재 단계에서는 density preset이나 timeline grammar 확장보다 현재 계약 유지가 우선이다.

## 3) BMAP diagnosis
- Motivation: 높음. 사용자는 이미 Obsidian에 축적된 논문 노트를 웹에서 재활용하고 싶어 한다.
- Ability: 높아졌다. 기본 읽기, 태그 필터, reference 이해, list 스캔, repair/rebuild 판단, sync 결과 해석, operational state 해석, note status 해석 모두 이전보다 쉬워졌다. 남은 비용은 density와 timeline/stepper visual grammar 검증이다.
- Prompt: 중간 이상. Workbench CTA와 Related list는 존재하고 references 설명도 보강됐다. normal repair와 advanced rebuild의 prompt도 분리됐고 sync feedback도 같은 패턴으로 맞춰졌다. `OperationalStateSummary`가 body/rail/list/detail에 같은 신호를 주고, `Content Review`도 triage -> workbench 사이에서 같은 문맥을 유지한다.

## 4) B.I.A.S diagnosis
- Block: 목록 밀도 최적값이 아직 실사용 기준으로 검증되지 않았고, timeline/stepper는 아직 별도 status grammar를 사용한다는 점
- Interpret: detail은 viewer답게 읽히고, references 정책과 list hierarchy도 즉시 이해되기 쉬워졌다. triage/workbench rail까지 semantics가 퍼졌고 rebuild path와 sync feedback도 explicit해졌으며, shared `OperationalStateSummary`, shared `StatusBadge`, `/papers` contract의 `ops_summary`, triage `Content Review` 분리, workbench `Content Review` summary가 status language source를 통일했다.
- Act: Workbench 이동은 쉽고 related click도 가능하다. 탐색 act는 충분히 살아 있다.
- Store: note를 읽고 related/workbench로 이어지는 기억은 남지만, "viewer 자체가 연구 허브"라는 인상은 목록 위계가 더 정리되면 강해질 수 있다.

## 5) Peak-End design notes
- Peak: 논문 상세에서 Properties와 markdown이 정확히 복원되고, related paper가 클릭 가능한 순간
- Pit: note 수가 많아질 때 현재 row density가 과하거나 부족할 가능성
- Transition: `/papers` -> `/papers/:slug`는 자연스럽지만, detail -> related -> workbench 연쇄 사용을 더 부드럽게 만들 여지가 있다
- End: 현재는 `Open in Workbench`가 종료 액션이다. 이후에는 "Review in Workbench"와 "Return to list" 사이의 맥락을 더 또렷하게 만들 수 있다.

## 6) Ethics Check
- Regret: 통과. 사용자가 나중에 봐도 "Obsidian note를 웹에서 읽기 좋게 보여주려는 설계"로 이해 가능하다.
- Black Mirror: 통과. 저작권 위험이 있는 PDF 직접 호스팅을 기본값으로 밀지 않는다.
- In Real-Life: 통과. 연구자가 실제로 쓰는 도구 흐름과 맞다.
- 대응:
  - PDF가 직접 노출되지 않는 경우 이유를 UI에 설명한다.
  - 외부 링크 우선순위는 문서와 UI 문구 양쪽에서 일치시킨다.

## 7) Concrete changes
- Component:
  - `/papers`의 태그 입력은 `Command`/chip형 선택 패턴으로 완료했다.
  - `/papers/:slug`의 desktop 3-pane + mobile sheet는 완료 상태로 유지한다.
  - References 패널에 access policy summary와 source별 설명을 추가했다.
  - `/papers` 목록은 row-card 형태로 재구성해 title/status/confidence/signals 위계를 재정렬했다.
  - `GET /paper-notes`와 `GET /paper-notes/{slug}`의 `note` payload에 operational summary를 추가해 `Healthy` / `Action needed`와 `Stats report is missing or empty.` language를 list/detail/workbench 사이에서 맞췄다.
  - 상세 Properties 패널에도 같은 operational summary를 올려 list -> detail -> workbench 흐름의 상태 언어를 통일했다.
  - triage queue와 workbench rail도 같은 operational badge를 읽도록 확장했다.
  - triage/workbench는 별도 `/paper-notes?page_size=5000` hook fetch 대신 `/papers` 응답의 `ops_summary`를 직접 사용하도록 바꿨다.
  - repair/rebuild나 artifact refresh 이후에는 `/papers`도 다시 불러와 rail/queue 상태를 함께 갱신한다.
  - `StatusBadge`와 `statusSystem` helper를 추가해 processing/completed/failed/not_started, note frontmatter status, `Healthy` / `Action needed`가 같은 badge/tone 계층을 사용하도록 맞췄다.
  - rail의 수작업 status pill을 제거하고 `StatusChip`을 재사용하도록 정리했다.
  - triage에서는 `Issues`를 `Content Review`로 재명명하고, artifact health와 다른 카피/색 계층으로 분리했다.
  - rail의 issue count는 amber warning 대신 red `QA {n}` chip으로 표기해 operational warning과 구분했다.
  - workbench notice와 body에도 `Content Review` summary를 추가해 `focus=issues` 진입 시 triage의 문맥이 유지되도록 맞췄다.
  - workbench의 clear-state `Content Review` notice는 paper detail 로드 후에만 보이도록 조정해 초기 flicker를 줄였다.
  - `issues_label`을 generic copy로 덮어쓰지 않고 보존해, `2 mapping ambiguities` 같은 source-backed `Content Review` detail이 triage/workbench에 그대로 노출되도록 맞췄다.
  - workbench 상단 notice도 같은 detail copy를 함께 보여줘, summary card까지 스크롤하기 전에도 review 이유를 유지한다.
  - rail은 `QA {n}` compact chip을 유지하되, 현재 선택된 flagged paper에는 한 줄 detail을 추가해 workbench navigation surface에서도 같은 review 이유를 유지한다.
  - `issues=0` + `issues_label=Not analyzed` 같은 availability 상태는 `Clear` 대신 `Unavailable`로 분리해, 분석되지 않은 paper를 오검출로 `review clear` 처리하지 않도록 맞췄다.
  - triage의 disabled action button도 `Unavailable`에 맞는 muted affordance를 사용하고, rail은 `QA unavailable` chip + selected detail로 같은 의미를 유지한다.
  - backend `/papers`와 `/papers/{paper_id}`는 `issues_state`를 내려주고, 프런트는 이를 우선 사용해 `Unavailable` 판단을 label regex보다 계약 기준으로 고정한다.
  - backend e2e fixture에 `issues=2` healthy artifact paper를 추가해 `Review 2 issues -> workbench` 경로를 검증했다.
  - Workbench의 `Repair Stats`는 `stats missing` 상태에서만 보이도록 유지하고, overwrite semantics가 있는 `Rebuild Stats`는 `Advanced actions` 안으로 분리했다.
  - `Rebuild Stats`는 `/ops/repair-stats`의 `skip_existing=false`를 사용하고, backend e2e 전용 stale snapshot fixture로 overwrite 경로를 검증했다.
  - `Sync to Obsidian`도 같은 inline notice/success/error 패턴과 terminal summary를 사용하도록 맞췄다.
  - sync 중에는 repair/rebuild를 막고, repair/rebuild 중에는 sync 버튼을 비활성화해 충돌을 줄였다.
- `OperationalStateSummary` 공용 컴포넌트를 추가해 list/detail/triage/rail/workbench body가 같은 badge + reason + action hint를 사용하도록 맞췄다.
- workbench body는 note index summary가 비어도 artifact state에서 같은 language를 fallback 생성하도록 맞췄다.
- note-backed workbench는 이제 stale artifact claimset보다 canonical `.pp/<slug>/state.json`를 우선 읽어 notebook highlight를 만든다.
- 이를 위해 `paper_id -> slug -> structured_state` resolver endpoint를 추가했고, note-backed bbox evidence가 artifact `text_match` fallback보다 우선되도록 source priority를 고정했다.
- Route:
  - 기존 `/papers`, `/papers/:slug`는 유지한다.
  - route 변경 없이 레이아웃만 개선한다.
- Copy:
  - References 블록에 "PDF is shown only for private/local-safe links; DOI/Zotero is preferred otherwise." 보조 문구를 추가한다.
  - Related Papers에 `shared tags`와 `structured signals` 근거를 함께 둔다.
- Default action:
  - 상세 화면 기본 보기는 markdown 본문이다.
  - related/references/properties는 보조 패널로 승격한다.
- Data/API contract:
  - 현재 `GET /paper-notes`, `GET /paper-notes/{slug}` 계약은 유지한다.
  - 추후 상세 우측 패널을 위해 `references_policy_reason` 같은 보조 필드는 확장 가능하다.

## 7.5) Claim/Evidence Verification Checkpoint (2026-03-13)
- real workspace sample `wenzelShortchainFattyAcids2020` 기준으로 `state.json -> /paper-notes/{slug} -> /papers/:slug` 레일을 다시 확인했다.
- 확인 결과:
  - structured state claim `2`, evidence `2`
  - API `structured_state.claimset[]`도 같은 개수와 같은 stable ids를 반환
  - rendered detail page도 claim card `2`, evidence card `2`를 실제로 노출
  - `?focus=evidence:evidence_e9a2060106f4` deep link는 evidence card ring focus까지 정상 동작
- real vault 전체 기준 current structured sidecar `4`건은 모두 `StructuredPaperState` validation을 통과했다.
- 현재 실데이터 evidence locator 분포:
  - `text_match=5`
  - `bbox=1`
  - `table_cell=1`
- 해석:
  - viewer의 claim/evidence card 생성 자체는 현재 정상이다.
  - 남은 제약은 viewer 렌더링이 아니라 upstream evidence-grounding breadth다. 즉, precise PDF box quality는 아직 `bbox` coverage보다 `text_match` coverage에 더 많이 의존한다.
  - 다만 note-backed workbench source priority mismatch는 수정됐다. stale artifact가 `text_match`만 갖고 있어도 canonical sidecar에 `bbox`가 있으면 Workbench는 이제 `bbox` highlight를 사용한다.

## 7.6) Grounding Visibility Checkpoint (2026-03-17)
- Screen/Flow: `/workbench/:paperId` mirror snapshot, `/papers/:slug` structured evidence metadata
- Goal action: 사용자가 근거가 실제로 매칭됐는지 한눈에 파악하고, 실패/애매함은 과신하지 않게 한다.
- Primary persona: 근거 점프를 신뢰 기준으로 삼는 연구자/리뷰어
- Current friction:
  - resolved claimset은 `grounded/resolution`을 계산하지만, workbench와 paper-note detail은 이 상태를 거의 드러내지 않는다.
  - 사용자는 `page/chunk/source`는 보지만, "검증됨 / 재검토 필요 / 미해결"을 즉시 판단하기 어렵다.
- Quick decision:
  - 새 행동 버튼은 추가하지 않는다.
  - mirror/workbench와 paper-note detail에만 작은 상태 표면을 조건부로 추가한다.
  - 내부 코드값(`OK`, `FAILED_MATCH`)은 그대로 노출하지 않고 사용자 언어(`Grounded`, `Needs review`, `Unresolved`)로 매핑한다.
- BMAP:
  - Motivation: 높음. 사용자는 근거 점프의 신뢰도를 즉시 알고 싶어 한다.
  - Ability: 작은 badge/metadata만 추가하면 판단 비용이 거의 없다.
  - Prompt: quote/page 옆에 바로 붙는 상태 신호가 가장 적절하다.
- B.I.A.S:
  - Block: 추가 상태는 conditional 노출로 제한해 밀도를 늘리지 않는다.
  - Interpret: technical code 대신 짧은 상태 언어를 쓴다.
  - Act: `Needs review`는 클릭/검토를 유도하지만 강제하지 않는다.
  - Store: 검증 실패를 숨기지 않아 장기 신뢰를 높인다.
- Peak-End:
  - Peak는 "근거가 실제로 검증됐음"이 한 번에 읽히는 순간이다.
  - Pit는 "점프는 되지만 실제로 맞는 근거인지 알 수 없음"인데, 이 지점을 badge로 메운다.
- Ethics:
  - Regret: 통과. 근거 신뢰도를 더 투명하게 보여주는 변화다.
  - Black Mirror: 통과. 불안 조장보다 오탐 신뢰를 줄이는 방향이다.
  - In Real-Life: 통과. 친절한 리뷰어처럼 상태를 설명한다.
- Concrete change:
  - `Obsidian Mirror` claim/stat snapshot에 conditional grounding badge를 추가한다.
  - `Paper Note Detail` evidence metadata 줄에도 같은 상태를 작게 노출한다.
  - 값이 없으면 아무것도 추가하지 않아 기존 밀도를 유지한다.

## 7.7) Timeline User Action Visibility Checkpoint (2026-03-17)
- Screen/Flow: `/workbench/:paperId` run timeline panel
- Goal action: 사용자가 "시스템 진행 로그"와 "사용자 트리거"를 섞어 읽지 않고, 방금 누른 행동이 실제 run에 반영됐는지 즉시 확인한다.
- Primary persona: deep read / sync / skill 실행을 반복하면서 run 상태를 추적하는 연구자
- Current friction:
  - timeline API는 이미 `source=user_action`을 내리지만, 패널은 `status/error/done/log`만 시각화해서 사용자 의도가 로그에 묻힌다.
  - default `status` filter가 켜진 run에서는 user action이 리스트에서 바로 사라질 수 있어, "내가 방금 누른 액션이 먹혔나?"를 다시 해석해야 한다.
- Quick decision:
  - filter 구조는 유지한다.
  - 대신 `user_action`에만 source pill을 추가하고, latest user action은 pinned row로 별도 노출한다.
  - 새 컬러 시스템은 만들지 않고 기존 `--pp-*` accent 계층만 재사용한다.
- BMAP:
  - Motivation: 높음. 사용자는 자신의 액션이 run에 반영됐는지 가장 먼저 확인한다.
  - Ability: 작은 source pill + pinned row면 해석 비용이 거의 없다.
  - Prompt: timeline 내부에서 바로 보여주는 것이 가장 적절하며, 별도 drawer/tooltip은 과하다.
- B.I.A.S:
  - Block: status filter가 user action을 숨길 수 있으므로 pinned row로 보완한다.
  - Interpret: technical source명 대신 `USER` / `User action` 언어로 변환한다.
  - Act: 별도 클릭 없이 같은 타임라인 안에서 다음 판단으로 이어지게 한다.
  - Store: "내 행동이 기록되고 있다"는 감각이 남아 run 신뢰도를 높인다.
- Peak-End:
  - Peak는 deep read/sync 직후 타임라인에서 자신의 액션이 바로 보이는 순간이다.
  - Pit는 user action이 job log에 묻혀 보이지 않는 순간인데, source pill과 pinned row로 메운다.
- Ethics:
  - Regret: 통과. 숨겨진 조작이 아니라 행동-결과 연결을 더 투명하게 보여준다.
  - Black Mirror: 통과. 과도한 긴급성/행동 유도 없이 이미 발생한 이벤트만 드러낸다.
  - In Real-Life: 통과. 협업 도구의 audit trail처럼 읽힌다.
- Concrete change:
  - `TimelinePanel` event row에 `USER` source pill을 조건부로 추가한다.
  - `Pinned Events`에 latest user action을 별도 row로 추가한다.
  - mock timeline fixture와 Playwright mock coverage로 표면을 고정한다.

## 7.8) Viewer Output Mode Checkpoint (2026-03-18)
- Screen/Flow: `/papers/:slug` detail viewer
- Goal action: 같은 note detail을 읽기 중심(`learner`) 또는 inspection 중심(`builder_debug`)으로 빠르게 전환한다.
- Primary persona:
  - `learner`: note를 읽고 related/reference를 따라가며 이해하려는 사용자
  - `builder_debug`: structured state와 automation output을 먼저 확인하려는 운영자/개발자
- Current friction:
  - 현재 detail page는 하나의 static panel order만 제공해서, reading-oriented 사용자와 debug-oriented 사용자가 같은 정보 밀도를 같은 순서로 받아야 한다.
  - output/view mode boundary는 문서로는 정리됐지만 viewer surface에서는 아직 보이지 않는다.
- Quick decision:
  - new runtime or data fetch는 추가하지 않는다.
  - `view=learner|builder_debug` query param만 additive로 연다.
  - mode는 panel order, helper copy, emphasis만 바꾸고 claim/evidence truth는 절대 바꾸지 않는다.
- BMAP:
  - Motivation: 높음. 읽기와 점검은 같은 note detail에서도 완전히 다른 우선순위를 가진다.
  - Ability: small mode toggle과 rail reorder만으로 충분하다.
  - Prompt: header 바로 아래의 compact toggle이 가장 적절하다.
- B.I.A.S:
  - Block: static panel order는 목적이 다른 사용자 모두에게 절충안만 제공한다.
  - Interpret: `Learner` / `Builder / Debug`를 명시하면 현재 emphasis가 즉시 이해된다.
  - Act: mode 전환 후 필요한 panel이 위로 올라오면 다음 행동까지의 스캔 비용이 줄어든다.
  - Store: viewer도 shared output-mode axis를 가진다는 점이 기억에 남는다.
- Peak-End:
  - Peak는 “이 note를 지금 목적에 맞는 순서로 읽을 수 있다”는 순간이다.
  - Pit는 debug user가 관련 논문/레퍼런스보다 actions/claimset까지 내려가야 하는 순간, 또는 learner가 structured ops 카드부터 봐야 하는 순간이다.
- Ethics:
  - Regret: 통과. 정보 숨김이 아니라 ordering/emphasis 조정이다.
  - Black Mirror: 통과. evidence threshold나 truth policy를 바꾸지 않는다.
  - In Real-Life: 통과. 사용자의 목적을 존중해 보기 순서를 바꾸는 수준이다.
- Concrete change:
  - header에 compact `View mode` toggle을 추가한다.
  - `learner`는 related/reference를 actions/automation보다 앞세운다.
  - `builder_debug`는 actions/automation/claimset을 properties보다 먼저 노출한다.
  - mode 설명 카피를 `Reading Context`와 `Reading View` 주변에 짧게 추가한다.

## 7.9) Core Worksurface Header Copy Checkpoint (2026-03-22)
- Screen/Flow: `/` triage header, `/workbench/:paperId` header and mobile controls, global lazy-load fallback
- Goal action: 사용자가 첫 진입과 workbench handoff에서 현재 작업 표면을 즉시 이해하고, 내부 운영 문구에 방해받지 않는다.
- Primary persona: list -> workbench 이동을 반복하며 상태와 evidence를 검수하는 연구자
- Current friction:
  - triage의 `Phase 3 Control UI`와 기존 document title은 내부 단계/도구 명명에 가깝다.
  - workbench mobile summary `Run & View Controls`는 기능 묶음 이름은 말하지만 작업 의미는 약하다.
  - global `Loading...` fallback도 제품 surface보다 generic shell처럼 읽힌다.
- Quick decision:
  - route, H1 contract, workbench layout, stepper, controls 구조는 유지한다.
  - 대신 eyebrow, subtitle, mobile controls label, loading copy를 작업 중심 언어로 정리한다.
- BMAP:
  - Motivation: 높음. 사용자는 현재 무엇을 검토하고 어디로 들어가야 하는지 바로 알고 싶다.
  - Ability: header copy가 직접적일수록 triage -> workbench 전환 비용이 줄어든다.
  - Prompt: `Research queue`, `Workbench controls`, `Loading workspace...` 수준의 짧은 prompt가 충분하다.
- B.I.A.S:
  - Block: 내부 단계명은 빠른 이해를 방해한다.
  - Interpret: queue/workbench 중심 언어가 current surface를 즉시 해석하게 한다.
  - Act: triage subtitle은 review -> open workbench 흐름을 바로 가리킨다.
  - Store: calm, credible wording이 long-session usability를 높인다.
- Peak-End:
  - Peak는 첫 화면과 workbench 진입 순간에 현재 작업 책임이 바로 읽히는 순간이다.
  - Pit는 stage/control wording이 internal console처럼 읽히는 순간이다.
  - Transition은 triage queue -> workbench이며, 같은 grammar로 이어져야 한다.
- Ethics:
  - Regret: 통과. 제품을 더 화려하게 포장하지 않고 현재 작업을 더 직접적으로 설명한다.
  - Black Mirror: 통과. urgency나 branding mood를 얹지 않는다.
  - In Real-Life: 통과. 연구 보조 도구다운 절제된 안내다.
- Concrete change:
  - triage document title을 `Triage | Lattice`로 교체
  - triage eyebrow를 `Research queue`로 교체
  - triage subtitle을 workbench 진입 목적이 보이도록 정리
  - workbench mobile controls summary를 `Workbench controls`로 교체
  - terminal button copy를 `Terminal logs`로 축약
  - suspense fallback copy를 `Loading workspace...`로 교체

## 7.10) Paper Note Detail Header Copy Checkpoint (2026-03-23)
- Screen/Flow: `/papers/:slug` detail header before markdown reading and workbench handoff
- Goal action: 사용자가 이 화면을 viewer shell이 아니라 실제 note review surface로 즉시 이해한다.
- Primary persona: note 본문을 읽고 related/reference를 확인한 뒤 필요하면 workbench로 넘어가는 연구자
- Current friction:
  - `Lattice · Paper Notes Viewer`는 브랜드/내부 viewer shell처럼 읽히고, detail route의 즉각적 작업 의미를 직접 말하지 않는다.
  - H1 아래에는 논문 title과 id는 있지만, 왜 이 surface가 존재하는지 알려주는 짧은 orientation 문구가 약하다.
- Quick decision:
  - H1, note id, back/workbench CTA, viewer mode controls, panel order는 유지한다.
  - eyebrow와 subtitle만 작업 중심 문구로 교체한다.
- BMAP:
  - Motivation: 높음. 사용자는 note를 읽기 시작하기 전에 이 surface의 책임을 바로 알고 싶다.
  - Ability: 짧은 subtitle 한 줄이면 별도 설명 panel 없이도 시작 비용이 줄어든다.
  - Prompt: detail header가 reading context와 workbench handoff를 동시에 예고하면 충분하다.
- B.I.A.S:
  - Block: viewer shell 언어는 목적 해석을 한 단계 늦춘다.
  - Interpret: `Paper note detail`과 direct subtitle이 화면 책임을 바로 설명한다.
  - Act: subtitle이 `review -> open workbench` 흐름을 부드럽게 연결한다.
  - Store: detail route도 list/triage와 같은 restrained product language로 기억된다.
- Peak-End:
  - Peak는 detail 진입 직후 “여기서 note를 읽고 관련 근거를 본다”가 바로 읽히는 순간이다.
  - Pit는 title 아래가 metadata만 남아 surface purpose가 늦게 드러나는 순간이다.
  - Transition은 list -> detail -> workbench이며, header copy가 그 handoff를 미리 설명해야 한다.
- Ethics:
  - Regret: 통과. 정보를 숨기지 않고 현재 작업 목적을 더 직접적으로 설명한다.
  - Black Mirror: 통과. urgency, persuasion, branding mood를 추가하지 않는다.
  - In Real-Life: 통과. 조용하지만 분명한 연구 도구의 안내다.
- Concrete change:
  - eyebrow를 `Paper note detail`로 교체
  - subtitle을 `Review note content, related papers, and references before opening the workbench.`로 추가

## 7.11) Mobile Detail Side Panel Naming Checkpoint (2026-03-23)
- Screen/Flow: `/papers/:slug` mobile detail side panel trigger and sheet title
- Goal action: 사용자가 mobile에서 여는 보조 패널이 단순 속성 창이 아니라 review support surface라는 점을 바로 이해한다.
- Primary persona: mobile에서 note 본문을 읽다가 metadata, outline, related papers, references, actions, claim cards를 함께 확인하는 연구자
- Current friction:
  - `Properties & Links`는 일부 내용만 설명하고, actions/claim cards/outline까지 포함하는 실제 패널 역할을 충분히 말하지 못한다.
  - 특히 mobile에서는 이 패널이 detail route의 핵심 보조 surface인데, naming이 너무 narrow하다.
- Quick decision:
  - side panel contents와 ordering은 유지한다.
  - button label, sheet title, sheet description만 더 직접적인 review language로 바꾼다.
- BMAP:
  - Motivation: 높음. mobile에서는 이 패널이 supporting context의 핵심 진입점이다.
  - Ability: broader but still direct naming만으로 패널 역할 이해가 쉬워진다.
  - Prompt: `Review details` 정도가 가장 짧고 현재 내용 범위를 무리 없이 덮는다.
- B.I.A.S:
  - Block: 기존 명칭은 properties에만 시선을 묶어 outline/actions/claim cards 존재를 약하게 만든다.
  - Interpret: `Review details`가 supporting review surface라는 해석을 더 빠르게 만든다.
  - Act: 사용자는 본문 읽기 중 필요한 supporting context를 열어볼 이유를 더 쉽게 이해한다.
  - Store: mobile detail도 task-oriented language로 정리된다는 일관성이 남는다.
- Peak-End:
  - Peak는 mobile에서 버튼을 보는 순간 “이 안에 review context가 있다”가 읽히는 순간이다.
  - Pit는 속성창처럼 느껴져 실제로는 더 많은 review support가 있는 패널을 덜 열게 되는 순간이다.
  - Transition은 reading view -> side panel -> workbench handoff이며, panel naming이 첫 전환을 돕는다.
- Ethics:
  - Regret: 통과. 내용을 과장하지 않고 실제 패널 역할에 더 가깝게 설명한다.
  - Black Mirror: 통과. 클릭 유도용 과장 문구가 아니다.
  - In Real-Life: 통과. 연구 assistant가 “자세한 검토 항목은 여기”라고 안내하는 수준이다.
- Concrete change:
  - mobile trigger button을 `Review details`로 교체
  - sheet title을 `Review details`로 교체
  - sheet description을 실제 패널 구성에 맞게 더 간결하게 정리

## 7.12) Detail Technical Label Cleanup Checkpoint (2026-03-23)
- Screen/Flow: `/papers/:slug` structured detail panels and view-mode helper copy
- Goal action: 사용자가 note detail의 structured panels를 내부 구현 용어 없이 더 빠르게 해석한다.
- Primary persona: note detail에서 actions, structured runs, claim cards를 점검한 뒤 workbench로 넘어가는 연구자
- Current friction:
  - `Builder / Debug`, `Automation Results`, `ClaimSet` 같은 wording은 기능은 맞지만 연구자 관점에서는 내부 구현어처럼 들린다.
  - detail route는 이미 route-level language가 정리됐는데, side panels 안쪽 제목만 상대적으로 technical tone이 남아 있었다.
- Quick decision:
  - panel ordering, data shape, markdown output heading은 유지한다.
  - runtime UI에서만 `Inspect`, `Run history`, `Structured claims`처럼 더 직접적인 review language로 바꾼다.
- BMAP:
  - Motivation: 높음. 이 surface는 읽기와 검수를 함께 지원해야 한다.
  - Ability: 새 구조를 만들지 않고 제목과 summary만 정리해도 scan cost가 줄어든다.
  - Prompt: 현재 rail과 sheet 안에서 짧은 task-language label이 가장 안전하다.
- B.I.A.S:
  - Block: technical labels는 structured panels를 “개발자용”으로 느끼게 만든다.
  - Interpret: `Run history`와 `Structured claims`는 패널 책임을 더 직접적으로 설명한다.
  - Act: `Inspect` mode라는 이름은 왜 이 모드에서 actions/runs/claims가 앞에 오는지 해석을 돕는다.
  - Store: detail route 전체가 같은 restrained product language를 유지하게 된다.
- Peak-End:
  - Peak는 structured note detail에서도 “무엇을 검토하는지”가 즉시 읽히는 순간이다.
  - Pit는 data truth는 같지만 label tone 때문에 내부 콘솔처럼 느껴지는 순간이다.
  - Transition은 learner reading -> inspect review -> workbench handoff이며, mode/panel naming이 그 전환을 더 부드럽게 만든다.
- Ethics:
  - Regret: 통과. 구조나 truth를 감추지 않고 label만 더 직접적으로 만든다.
  - Black Mirror: 통과. urgency, overclaim, persuasion을 추가하지 않는다.
  - In Real-Life: 통과. 조용한 연구 도구가 “실행 기록”과 “구조화된 주장”을 보여주는 수준이다.
- Concrete change:
  - `Builder / Debug` mode label을 `Inspect`로 교체
  - `Builder / Debug mode lifts ...` summary를 `Inspect mode lifts ...`로 정리
  - `Automation Results` panel title을 `Run history`로 교체
  - `ClaimSet` panel title과 properties stat label을 `Structured claims`로 교체
  - append toggle helper copy를 runtime panel language와 충돌하지 않도록 `short run summary`로 정리

## 7.13) Detail Visual Baseline Refresh Checkpoint (2026-03-23)
- Screen/Flow: `/papers/:slug` desktop/mobile visual regression baselines
- Goal action: 현재 detail UI wording과 visual baseline artifact가 같은 상태를 가리키도록 맞춘다.
- Primary persona: viewer UI regression을 screenshot diff로 검토하는 maintainers
- Current friction:
  - detail route wording은 이미 `Inspect`, `Run history`, `Structured claims`, `Review details`로 바뀌었지만, 기존 darwin snapshot 일부는 높은 diff tolerance 안에서 이전 wording을 계속 보존하고 있었다.
  - 이 상태는 테스트 pass와 baseline image가 서로 다른 UI를 가리키는 작은 운영 리스크를 만든다.
- Quick decision:
  - 새 layout refinement는 추가하지 않는다.
  - detail visual baselines 4장만 `--update-snapshots=all`로 강제 재생성해 current UI와 다시 맞춘다.
- BMAP:
  - Motivation: 중간. 사용자는 보지 않더라도 maintainer는 baseline과 실제 UI가 일치하길 원한다.
  - Ability: screenshot artifact만 갱신하면 충분하다.
  - Prompt: current UI를 다시 기준선으로 삼는 것이 가장 직접적인 해법이다.
- B.I.A.S:
  - Block: lenient diff threshold는 wording drift를 baseline refresh 없이 통과시킬 수 있다.
  - Interpret: refreshed snapshot은 current product language를 정확히 보여준다.
  - Act: 이후 regression review에서 screenshot diff 신뢰도가 올라간다.
  - Store: visual baseline도 current UI contract를 기억하는 artifact가 된다.
- Peak-End:
  - Peak는 code/test/baseline이 같은 wording을 가리키는 상태다.
  - Pit는 테스트는 green인데 baseline image는 예전 UI를 보여주는 상태다.
  - Transition은 wording pass -> baseline refresh -> stable visual review다.
- Ethics:
  - Regret: 통과. 사용자-facing behavior를 바꾸지 않고 verification artifact만 바로잡는다.
  - Black Mirror: 통과. 결과를 좋게 보이게 꾸미는 것이 아니라 current UI를 정확히 기록한다.
  - In Real-Life: 통과. 스냅샷 goldens를 실제 화면과 일치시키는 유지보수 수준이다.
- Concrete change:
  - desktop/mobile detail visual baselines 4장을 `--update-snapshots=all`로 재생성
  - current wording(`Inspect`, `Review details`, `Current focus`)이 이미지 artifact에도 그대로 반영되도록 정렬
  - spacing audit은 별도 layout patch 없이 종료

## 7.14) Missing Structured State Truth-Visibility Checkpoint (2026-03-28)
- Screen/Flow: `/papers/:slug` detail, especially notes with no canonical `.pp/<slug>/state.json`
- Goal action: 사용자가 note detail을 열었을 때 "지금 읽는 note는 열렸지만 canonical structured sidecar는 로드되지 않았다"는 사실을 바로 이해한다.
- Primary persona: note detail에서 읽기와 검수를 섞어 쓰는 단일 연구자/operator
- Current friction:
  - backend는 `context_trace`와 `structured_state_loaded -> missing`을 이미 내려주지만, frontend detail은 이를 소비하지 않아 generic empty copy만 보인다.
  - 그래서 사용자는 `No structured runs recorded yet.`를 보고 "아직 실행 안 했나?", "sidecar가 비었나?", "sidecar가 아예 없나?"를 구분하기 어렵다.
- Truth/provenance gap:
  - canonical structured truth의 부재는 runtime이 이미 알고 있지만, detail UI가 plain-language truth로 드러내지 않는다.
  - 이는 storage/schema 문제가 아니라 visibility 문제다.
- Quick decision:
  - layout/order는 유지한다.
  - missing structured state일 때만 작은 notice를 추가한다.
  - `context_trace`는 full debug panel로 승격하지 않고, compact summary/source-path disclosure로만 쓴다.
- 6P storyboard context:
  - Problem: 사용자는 note detail을 열었는데 structured review가 비어 있고, 왜 비었는지 바로 알 수 없다.
  - Emotion: "이 note가 아직 준비 안 된 건가, 내가 뭘 놓친 건가?"라는 불확실성이 생긴다.
  - Action: detail route를 열고 structured review/claims 패널을 본다.
  - Struggle: generic empty state가 canonical sidecar 부재와 단순 빈 데이터 상태를 섞어버린다.
  - Attempt: backend가 이미 주는 `context_trace`와 expected sidecar path를 compact하게 드러낸다.
  - Happy Ending: 사용자는 note는 읽을 수 있지만 structured sidecar가 없어서 run history/claims가 비어 있다는 점을 한 번에 이해한다.
- BMAP:
  - Motivation: 높음. 사용자는 structured review 가능 여부를 빠르게 알고 싶다.
  - Ability: 작은 notice와 source-path disclosure만으로 해석 비용을 크게 줄일 수 있다.
  - Prompt: empty-state 바로 위에서 보여주는 것이 가장 자연스럽다.
- B.I.A.S:
  - Block: generic empty copy는 canonical truth를 흐린다.
  - Interpret: `No saved structured state was loaded` 같은 plain-language notice가 의미를 즉시 고정한다.
  - Act: 사용자는 Workbench handoff나 later repair action을 더 정확히 판단할 수 있다.
  - Store: detail route가 숨기지 않고 말해준다는 신뢰가 남는다.
- Peak-End:
  - Peak는 missing state가 "실행 전/비어 있음/없음" 중 무엇인지 즉시 읽히는 순간이다.
  - Pit는 generic empty cards만 보여서 operator가 상태를 추측해야 하는 순간이다.
  - Transition은 note reading -> structured review -> workbench handoff이며, notice가 이 전환을 더 정직하게 만든다.
- Ethics:
  - Regret: 통과. 이미 알고 있는 runtime truth를 더 명확하게 보여주는 변화다.
  - Black Mirror: 통과. 불안을 과장하지 않고, 존재하는 결손만 설명한다.
  - In Real-Life: 통과. 좋은 연구 assistant가 "파일은 열렸지만 structured sidecar는 아직 없어요"라고 말해주는 수준이다.
- Concrete change:
  - `PaperNoteDetailResponse` frontend type에 `context_trace`를 반영한다.
  - `structured_state == null`이면서 backend trace가 `structured_state_loaded -> missing`인 경우, detail route에 compact notice를 노출한다.
  - notice에는 expected sidecar path와 compact trace summary만 담고, 별도 debug panel은 만들지 않는다.
  - existing paper-note detail backend/visual coverage에 새 truth-visibility assertion을 추가한다.

## 8) Next PR-sized actions
이 섹션은 cross-surface viewer/workbench backlog의 요약이며, scoped source of truth는 이 UX review report와 repo-wide queue에 남긴 bounded follow-up들이다.

1. batch producer와 watcher local producer 외의 producer/artifact level source가 준비되면 `issues_state`를 추가 승격할지 검토하기
2. 실제 note volume과 사용 패턴을 본 뒤에만 list density preset을 검토하기
3. `issues_label`만으로 설명이 부족한 시점에만 `review_flags[]` 같은 구조화 계약 필요성을 검토하기
