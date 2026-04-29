# UX Review Report - Paper Annotation / Marking

Status: Current review artifact
Date: 2026-04-10
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-04-10
Reviewer: Codex

## Header
- Screen/Flow: `/papers` -> `/papers/:slug` -> `/workbench/:paperId`
- Goal action: 사용자가 논문을 읽는 중 생긴 판단을 paper-scoped 상태로 저장하고, 나중에 list/filter/review 흐름에서 다시 찾는다.
- Primary persona: single-operator local-first 연구자/대학원생
- Current friction: 현재 note detail은 reading + review bridge이고, workbench는 evidence review surface다. 그러나 사용자의 paper-level 판단을 남기는 durable, retrieval-ready lane은 없다. 기존 `status`, `tags`, generated markdown body, `user_actions`는 이 역할에 그대로 쓰기 어렵다.
- Success metric: note detail에서 남긴 판단이 `/papers` 목록과 filter에서 다시 보이고, note -> revisit -> workbench 재진입 cost가 줄어든다.
- Constraints:
  - current runtime remains paper-first, artifact-first, local-first, single-operator-first
  - canonical truth must stay in schema-backed structured state
  - note body/frontmatter are already managed by generated/runtime flows
  - workbench remains the primary evidence-review surface
  - current product is not yet a first-class project/workspace platform

## Quick Review (5 min)
- Block: 지금 필요한 것은 decorative annotation이 아니라, operator judgment를 구조적으로 저장하는 최소 lane이다.
- Interpret: `paper-level note + small typed triage + optional star`는 의미가 즉시 읽힌다. sticker-like system은 연구 도구의 메시지를 흐린다.
- Act: detail에서 빠르게 저장하고, list에서 바로 다시 보이게 하는 것이 핵심이다.
- Store: 이 정보가 list/filter/review에서 회수되지 않으면 기능 가치는 급감한다.
- Ethics first pass: attention-seeking sticker UI나 감성형 marking은 피해야 한다.

## Full Review
### P0
- generated paper note markdown body에 사용자 메모를 직접 섞지 않는다.
  - current note body is rewritten through `compose_note(...)` and bounded body upsert helpers.
  - arbitrary inline note insertion risks overwrite, merge ambiguity, and future migration pain.
- existing frontmatter `status` and `tags`를 user triage source-of-truth로 재사용하지 않는다.
  - current `status` already powers list/detail filters and is interpreted as processing/readiness-like state.
  - current `tags` already affect list retrieval and related-paper derivation.
- `user_actions`를 bookmark/note/status의 durable store로 쓰지 않는다.
  - it is an audit/event log, not a retrieval-grade state contract.
- note detail markdown DOM selection 기반 passage annotation을 v1로 열지 않는다.
  - current detail surface renders generated `body_markdown`, not the source PDF as the primary evidence surface.
  - passage-anchored annotation here would overlap awkwardly with workbench evidence anchors.

### P1
- v1 should add one paper-scoped operator judgment lane only:
  - `paper note text`
  - `starred`
  - small closed-set `triage_labels[]`
- `triage_labels[]` must be separate from both:
  - machine/runtime processing status
  - broad topical tags
- list/detail/workbench should not all become editors.
  - detail can be the write surface
  - list should be retrieval/filter surface
  - workbench should initially be read-only carryover
- paper-scoped note and project-scoped judgment must stay distinct in the data model and UI copy.

### P2
- future anchored annotation can be reopened later if it uses a first-class anchor contract:
  - `anchor_type`
  - `anchor_target`
  - optional evidence locator
  - clear distinction from claim/evidence validation anchors
- future project linkage can be added later through explicit promotion or linkage, not by smuggling project ownership into v1 paper state.

### Full Review Coverage
- 6P storyboard context:
  - Problem: 읽는 중 생긴 판단이 현재 루프에 남지 않는다.
  - Emotion: 중요한 논문인지, 다시 볼 논문인지, 검증이 필요한지 잊고 싶지 않다.
  - Action: 사용자는 `/papers/:slug`에서 note를 읽고 workbench로 간다.
  - Struggle: 판단을 저장해도 later retrieval path가 없다.
  - Attempt: detail에서 paper-scoped operator state를 남기고 list/workbench에서 다시 보이게 한다.
  - Happy Ending: 논문을 다시 열지 않아도 list에서 지금 무엇을 다시 봐야 하는지 안다.
- BMAP:
  - Motivation is high.
  - Ability is currently low because no proper state lane exists.
  - Prompt is weak because the system does not invite or recover operator judgment.
- B.I.A.S:
  - Block: extra decorative UI would increase already-known density costs.
  - Interpret: a small judgment module reads clearly; stickers do not.
  - Act: one write surface plus retrieval surfaces minimizes friction.
  - Store: recovered judgment in list/filter is the real memory benefit.
- Peak-End:
  - Peak should be “I saved my judgment without breaking reading flow.”
  - Pit is “I had a thought but the product gave me nowhere trustworthy to keep it.”
  - End should be “I can see that judgment again before reopening the paper.”
- Ethics:
  - avoid attention-taxing decorative systems
  - avoid overstating certainty
  - respect the user’s time by keeping the interaction compact and retrieval-oriented

## BMAP diagnosis
- Motivation:
  - strong; users already read note detail and workbench with a judgment-heavy task mindset
- Ability:
  - weak today; there is no obvious durable place to save “why this matters to me now”
  - would improve sharply with one compact paper-level editor and list filters
- Prompt:
  - strongest prompt is inside note detail near the existing read -> review handoff
  - secondary prompt is recovery in `/papers` via chips/filters, not extra dashboard chrome

## B.I.A.S diagnosis
- Block:
  - papers list already has meaningful filter density
  - workbench already has known control density
  - annotation UI must not add visual noise to the center reading body by default
- Interpret:
  - users can quickly understand `My note`, `Starred`, and a few typed triage labels
  - users will not reliably interpret stickers as research-action semantics
- Act:
  - write once in detail, recover everywhere else
  - do not require users to choose among many label systems
- Store:
  - the memory value comes from retrieval, not from expressive decoration

## Peak-End design notes
- Peak:
  - saving a paper-level judgment without leaving the reading loop
- Pit:
  - note detail currently lets the user read, but not preserve their own paper-scoped interpretation
- Transition:
  - judgment should survive `detail -> list -> detail` and optionally `detail -> workbench`
- End:
  - list row and filters should make revisit paths obvious before the next deep read

## Concrete changes
- Add a dedicated paper-scoped operator state contract separate from:
  - canonical structured state
  - frontmatter processing status
  - topical tags
  - project memory ownership
- v1 surface:
  - note detail editable `My note`
  - `starred`
  - closed-set `triage_labels[]`
- retrieval surface:
  - list row badges for star / note-present / triage labels
  - list filters for star and triage labels
- workbench:
  - show read-only carryover only
  - no inline editing and no passage annotation in v1
- home dashboard:
  - show read-only paper marker aggregation inside `Workspace context`
  - reuse the home-context summary contract rather than loading the full note index on the dashboard
  - deep-link `Starred` and triage counts back into `/papers` filters instead of adding another edit surface

## Ethics check results
- Regret Test:
  - pass for compact paper-level judgment capture
  - fail risk for decorative sticker system because it wastes attention without strong research value
- Black Mirror Test:
  - avoid letting visual badges imply evidence confidence or scientific truth
- In Real-Life Test:
  - the product should feel like a disciplined research assistant, not a scrapbook

## Implementation Update (2026-04-13)
- Added read-only marker carryover in `/workbench/:paperId` so saved paper judgment remains visible during evidence review without creating a second editor.
- Added read-only marker aggregation in the home `Workspace context` card so `starred` and typed triage states become rediscoverable before re-opening an individual note.
- Kept retrieval centered on existing list/detail routes:
  - detail remains the write surface
  - `/papers` remains the filter/retrieval surface
  - home/workbench remain read-only context surfaces

## Next PR-sized actions
1. Decide whether project-level views need project-scoped judgment separate from the new paper-scoped operator state.
2. If retrieval demand grows, add a dedicated `has_operator_note` filter before expanding the vocabulary or adding more badges.
3. Reopen anchored annotations only after a separate anchor contract is written against the workbench/PDF evidence model.
