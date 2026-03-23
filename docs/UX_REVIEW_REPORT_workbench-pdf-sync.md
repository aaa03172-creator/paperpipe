# UX Review Report: Workbench PDF Claim Sync

Status: Active
Date: 2026-03-23
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: `/workbench/:paperId` PDF panel claim switch -> page jump -> highlight/search fallback sync
- Goal action: 연구자가 claim을 바꿔도 PDF viewer가 재마운트 없이 현재 claim evidence로 안정적으로 이동한다.
- Primary persona: workbench에서 claim과 evidence span을 빠르게 넘겨보는 연구자
- Current friction: current master는 active claim/page가 바뀔 때 viewer를 remount하고 `onDocumentLoad`에 sync를 몰아 넣어서, claim switch가 잦을수록 highlight/search fallback이 불안정하게 읽힌다.
- Success metric: claim switch 후 highlight landing 안정성, risk/obsidian jump success rate, text fallback continuity
- Constraints:
  - `PdfPanel.tsx` 단일 behavioral lane
  - existing `--pp-*` token system and dark-first Lattice tone 유지
  - triage/App/image evidence/chart pack routes는 제외
  - relevant verification은 existing mock Playwright reuse

## Quick Review (5 min)
- viewer를 claim/page 변화마다 다시 만들 필요는 없다.
- document load와 claim sync를 분리하면 page jump, bbox highlight, text-match fallback이 더 예측 가능해진다.
- 구조 변경 없이 `PdfPanel` 내부 sync ownership만 정리하는 것이 가장 작은 lane이다.

## Full Review
### P0
- claim switch가 highlight/search fallback을 놓치면 workbench 핵심 행동이 끊긴다.
- PDF 렌더러 remount는 사용자가 “왜 다시 로드되지?”를 느끼게 만드는 피해야 할 pit다.

### P1
- `onDocumentLoad`는 document metadata만 맡고, active claim sync는 별도 effect가 ownership을 가져야 한다.
- bbox highlight와 text-match fallback은 같은 claim switch event에서 일관되게 반응해야 한다.

### P2
- 이 lane에서는 copy나 layout보다 jump stability가 우선이다.
- richer viewer chrome은 별도 lane으로 남기는 것이 맞다.

### Full Review Coverage
- 6P storyboard context: Problem은 claim switch 후 PDF evidence가 흔들리는 것, emotion은 “지금 선택한 claim이 맞게 보이나?”라는 불안, action은 claim list/issue focus/obsidian jump, struggle은 viewer remount와 late sync, attempt는 claim sync effect 분리, happy ending은 claim을 바꿔도 viewer가 바로 같은 document 안에서 안정적으로 이동하는 것이다.
- BMAP: Motivation은 매우 높고, Ability는 remount 제거만으로 개선되며, Prompt는 existing claim selection CTA가 이미 충분하다.
- B.I.A.S: Block은 remount가 만들어내는 불연속성, Interpret는 stable highlight/search fallback이 “현재 claim이 반영됐다”는 해석을 빠르게 만든다, Act는 claim switching을 더 주저 없이 하게 만들고, Store는 workbench가 믿을 만하다는 기억을 남긴다.
- Peak-End: Peak는 claim을 눌렀을 때 즉시 맞는 page/highlight로 가는 순간, pit는 viewer가 다시 로딩되며 컨텍스트가 끊기는 순간, transition은 claim rail -> PDF panel, end는 selected claim evidence가 바로 읽히는 상태다.
- Ethics: urgency나 조작적 copy 없이 stability만 높이는 수정이라 안전하다.

## BMAP diagnosis
- Motivation: 높음. 사용자는 현재 claim 근거를 바로 보고 싶다.
- Ability: viewer remount를 없애고 sync ownership을 분리하면 인지 비용 없이 안정성이 오른다.
- Prompt: issue focus, claim card, obsidian snapshot click이 이미 충분한 prompt다.

## B.I.A.S diagnosis
- Block: remount와 late sync가 attention을 끊는다.
- Interpret: stable page jump와 highlight가 현재 claim 반영 여부를 즉시 이해시킨다.
- Act: claim switching과 evidence inspection이 더 매끄러워진다.
- Store: workbench가 "믿고 눌러도 되는" 도구라는 기억을 강화한다.

## Peak-End design notes
- Peak: claim switch 후 원하는 page/highlight가 바로 보이는 순간
- Pit: viewer가 다시 로딩되며 claim context가 끊기는 순간
- Transition: claims rail / issue focus / obsidian stats -> PDF panel
- End: bbox 또는 text fallback이 현재 claim 기준으로 정렬된 상태

## Concrete changes
- `PdfPanel`에서 viewer key를 document URL로 좁혀 claim/page switch 시 Viewer remount를 피한다.
- `onDocumentLoad`는 metadata load만 처리하고, claim/page/highlight/search sync는 effect로 분리한다.
- plugin refs와 sync sequence guard를 추가해 overlapping async search highlight 결과가 stale state를 덮지 않게 한다.
- existing mock Playwright scenarios(`issue focus`, `obsidian stats jump`, `normalized bbox`)로 regression을 다시 확인한다.

## Ethics check results
- Regret: 통과. 더 빠르고 안정적인 evidence inspection만 제공한다.
- Black Mirror: 통과. 조급함, 압박, deceptive feedback이 없다.
- In Real-Life: 통과. 연구 도구가 페이지를 다시 여는 대신 현재 문서 안에서 조용히 맞는 위치로 안내하는 수준이다.

## Next PR-sized actions
1. text-match fallback mock fixture가 준비되면 search-highlight continuity를 별도 lane으로 검증한다.
2. `PdfPanel` 이후 workbench detail shell이 필요하면 viewer chrome/copy는 separate UX lane으로 분리한다.
3. image evidence or chart-pack viewer behavior는 이 lane에 섞지 않고 독립 reland를 유지한다.
