# UX Review Report: Image Evidence Viewer

Status: Active
Date: 2026-03-22
Owner: Lattice runtime maintainers
Canonical parent: `docs/ux-review.md`

## Header
- Screen/Flow: Image Evidence viewer (`/image-evidence`, `/image-evidence/:imageEvidenceId`)
- Goal action: Inspect a saved image-evidence bundle and decide whether its raw identity, derived outputs, and handoff metadata are trustworthy enough for downstream reuse.
- Primary persona: Operator reviewing microscopy or figure-adjacent image metadata before using it in notes, packs, or external viewer handoff.
- Current friction: Backend `image_evidence` registration exists, but there is no direct viewer for raw-vs-derived separation, checksum/missing-file warnings, view state, or handoff metadata.
- Success metric: Operator can open a saved image-evidence bundle, understand what the raw source is, see whether the bundle is warning-heavy, inspect derived-output lineage, and hand off to a note or external viewer without confusing metadata with validated claim truth.
- Constraints: Read-only v0 lane; no embedded image canvas, no external process launch, preserve `--pp-*` tokens and dark-first Lattice tone, keep the viewer framed as metadata QA rather than image interpretation.

## Quick Review (5 min)
- The first read needs to answer three questions quickly: what raw source this bundle points to, whether anything about it is warning-heavy, and whether derived outputs still preserve explicit lineage.
- The index should prioritize search and warning visibility over thumbnails or gallery layout.
- The detail page should keep source identity, warnings, and derived-output lineage in the main viewport, then put metadata, view state, and handoff targets in a supporting rail.

## Full Review
### P0
- Keep the viewer read-only and metadata-first. Rendering image pixels or editing overlays inside this surface would blur the raw/derived boundary that the backend contract is trying to protect.
- Surface warning state in the primary viewport. If checksum mismatch, missing local file, or representative-only notes are buried below the fold, users will over-trust the saved bundle.

### P1
- Show raw source identity, paper linkage, checksum, and content format together so the operator can orient without opening JSON files.
- Keep derived outputs grouped with their provenance fields: kind, tool, created-by, bundle path or external ref, and optional view-state linkage.
- If a paper note slug exists, provide direct handoff into `/papers/:slug` so the image-evidence lane stays connected to the current paper-note review loop.

### P2
- Put view state and handoff targets in a side rail rather than the hero position. They matter, but they are secondary to raw identity and warning status.
- Use copy that explicitly says this is a metadata review surface, not an image-analysis viewer.

### Full Review Coverage
- 6P storyboard context: Problem is that saved image metadata becomes opaque once registered; emotion is low trust in representative images without provenance; action is open an image-evidence bundle; struggle is separating raw identity from derived outputs and handoff metadata; attempt is inspect warning/source/lineage cards; happy ending is a bounded image bundle whose limits are obvious before reuse.
- BMAP: Motivation is high because image-backed artifacts are easy to over-trust; ability drops when raw source, derived outputs, and handoff metadata are split across files; prompt should bring warning state and raw-vs-derived separation into the first screen.
- B.I.A.S: Block comes from opaque metadata bundles and absent trust cues; interpret improves when source identity, warnings, and derived lineage are shown together; act improves with direct note handoff and clear external-viewer metadata; store improves when every bundle uses the same summary/detail rhythm.
- Peak-End: Peak should be immediate recognition of source kind and warning state; pit is a gallery-like surface that implies image truth; transition is from saved-bundle index to metadata-rich detail; end is a trust-boundary card that reminds the operator what this viewer does not validate.
- Ethics: The viewer must not imply that a registered image proves a claim, that representative crops are exhaustive evidence, or that external-viewer handoff means the current runtime has validated the underlying pixels.

## BMAP diagnosis
- Motivation: High. Image evidence is likely to be reused downstream, so trust calibration matters.
- Ability: Medium before this viewer. Reading `image_evidence.json` and adjacent files directly is possible but too indirect for routine review.
- Prompt: Weak before this viewer. There was no dedicated place to review bundle warnings and raw/derived separation before handoff.

## B.I.A.S diagnosis
- Block: No dedicated read surface for image-evidence QA.
- Interpret: Users need to see raw source, warning state, derived outputs, and handoff metadata together.
- Act: The next actions are usually open the note, inspect the handoff target, or decide not to reuse the bundle.
- Store: Repeated bundle-summary and derived-output cards make future inspection predictable.

## Peak-End design notes
- Peak: The first detail card should immediately show source kind, content format, and warning count.
- Pit: Avoid image-gallery styling that makes representative outputs feel like validated findings.
- Transition: Keep the index lightweight, then move into source-first detail.
- End: Finish with an explicit trust-boundary card so users leave with the correct mental model.

## Concrete changes
- Route level: add `/image-evidence` index and `/image-evidence/:imageEvidenceId` detail routes.
- Component level: render bundle summary, warning cards, derived-output cards, linked references, view-state rail, and handoff rail.
- Copy level: frame the viewer as saved metadata review, not image interpretation.
- Default-action level: primary action on index is `Open bundle`; primary detail handoff is `Open note` when a paper slug exists.
- Runtime contract: mock mode should keep the same index/detail interaction without inventing unsupported binary rendering.
- Verification level: keep both mock Playwright coverage and backend Playwright coverage so warning-heavy local bundles and clean external bundles are exercised on real routes.
- Visual level: keep backend visual snapshots for the detail shell so the metadata-first layout does not drift into gallery-like image UI.
- Index shell: keep backend visual snapshots for the search panel and saved-bundle cards so warning badges and bundle rhythms remain stable.

## 7.1) Header Copy Refinement Checkpoint (2026-03-23)
- Screen/Flow: `/image-evidence` index header and `/image-evidence/:imageEvidenceId` detail header
- Goal action: 사용자가 이 route를 generic viewer shell이 아니라 saved image-evidence review surface로 즉시 이해한다.
- Primary persona: raw image source, warning state, derived lineage를 검토한 뒤 note나 external viewer로 handoff하려는 운영자
- Current friction:
  - `Lattice · Image Evidence Viewer`는 내부 shell 이름처럼 읽히고, route 책임을 직접적으로 말하지 않는다.
  - `Search Bundles`, `Saved Bundles`도 의미는 맞지만 image-evidence context보다 generic storage vocabulary에 가깝다.
- Quick decision:
  - route 구조, card layout, button set, trust-boundary model은 유지한다.
  - header eyebrow, subtitle, index section titles만 더 직접적인 review language로 정리한다.
- BMAP:
  - Motivation: 높음. 이 surface는 low-trust image metadata를 빠르게 검토하는 곳이다.
  - Ability: copy만 정리해도 first-read cost가 줄어든다.
  - Prompt: header와 index section title이 bundle review responsibility를 직접 말하는 게 가장 안전하다.
- B.I.A.S:
  - Block: viewer shell language는 metadata QA surface를 한 단계 더 추상적으로 느끼게 만든다.
  - Interpret: `Image evidence review`는 route 책임을 더 빠르게 해석하게 한다.
  - Act: `Search image bundles`와 `Saved image bundles`는 index의 다음 행동을 더 직접적으로 보여준다.
  - Store: image-evidence lane도 core viewer routes와 같은 restrained product language를 갖게 된다.
- Peak-End:
  - Peak는 첫 진입에서 “여기서 saved image bundle을 검토한다”가 바로 읽히는 순간이다.
  - Pit는 route가 generic viewer shell로 읽혀 metadata QA 목적이 늦게 드러나는 순간이다.
  - Transition은 index search -> bundle detail -> note/external handoff이며, header copy가 그 시작점을 분명히 해야 한다.
- Ethics:
  - Regret: 통과. 기능 과장 없이 route responsibility만 더 직접적으로 말한다.
  - Black Mirror: 통과. image interpretation이나 claim validation을 더 강하게 암시하지 않는다.
  - In Real-Life: 통과. 운영자가 “저장된 이미지 번들을 검토한다”는 수준의 조용한 안내다.
- Concrete change:
  - eyebrow를 `Image evidence review`로 교체
  - subtitle을 `Review saved image-evidence metadata before reuse in notes, packs, or external viewers.`로 정리
  - `Search Bundles`를 `Search image bundles`로 교체
  - `Saved Bundles`를 `Saved image bundles`로 교체

## Ethics check results
- Regret: Low if warnings and trust-boundary copy stay visible.
- Black Mirror: Risk appears if the viewer looks like a microscopy tool and causes users to infer pixel-level validation. Countermeasure is a metadata-first layout and explicit non-goals copy.
- In Real-Life: A reviewer should be able to explain where the raw image lives, what derived outputs were produced, and whether this bundle has any warning state without touching the filesystem.

## Next PR-sized actions
- If the shell keeps changing, consider a broader visual lane that snapshots detail plus side-rail subregions separately for tighter diffs.
- If warning taxonomy expands again, add a `LOCAL_SOURCE_NOT_FILE` real backend bundle rather than broadening the current missing-file case.
- Defer any visual image preview or viewer-launch behavior into a separate RFC lane.

## 7.2) Header Context Strip Checkpoint (2026-03-29)
- Screen/Flow: `/image-evidence` index and `/image-evidence/:imageEvidenceId` detail header
- Goal action: 사용자가 image-evidence lane를 generic bundle viewer가 아니라 provenance-first review surface로 이해하고, raw source/derived outputs 관계를 header에서 바로 읽는다.
- Primary persona: raw image source, warning state, derived lineage를 검토한 뒤 note나 external viewer로 handoff하려는 운영자
- Current friction:
  - existing header는 review 목적은 말하지만, `언제 쓰는지`와 `무엇에서 파생됐는지`를 한 번에 말하지 않았다.
  - raw source identity와 derived outputs 관계는 body에서만 읽혔다.
- Quick decision:
  - existing bundle review layout과 trust boundary는 유지한다.
  - header 바로 아래에 reusable context strip을 추가해 `When to use`와 `Derived from`을 먼저 보여준다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend image evidence viewer loads a registered bundle and keeps note handoff on the real route"`

## 7.3) Continue In Note Handoff Checkpoint (2026-03-29)
- Screen/Flow: `/image-evidence/:imageEvidenceId` `Handoff Targets` card
- Goal action: 사용자가 saved viewer target보다 먼저 linked paper note review를 떠올리게 한다.
- Primary persona: image metadata를 검토한 뒤 note와 external viewer 사이에서 다음 행동을 정하려는 운영자
- Current friction:
  - `Open note` action은 있었지만, 왜 note review가 먼저인지에 대한 설명은 없었다.
  - saved handoff targets는 note review와 같은 레벨의 다음 행동처럼 읽힐 수 있었다.
- Quick decision:
  - existing `Open note` action과 saved target list는 유지한다.
  - `Handoff Targets` card 안에 `Continue in note`와 note-first guidance를 추가한다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend image evidence viewer loads a registered bundle and keeps note handoff on the real route"`

## 7.4) Continue After Note Review Checkpoint (2026-03-29)
- Screen/Flow: `/image-evidence/:imageEvidenceId` right-rail `Handoff Targets` card
- Goal action: 사용자가 note review 다음의 downstream artifact lane도 바로 떠올릴 수 있다.
- Primary persona: image metadata를 note에서 다시 검토한 뒤, 비교/팩/후속 artifact lane으로 이어가려는 연구자
- Current friction:
  - note-first guidance는 좋아졌지만, note를 본 뒤 다음에 어떤 artifact lane을 다시 열어야 하는지는 여전히 사용자가 추론해야 했다.
  - `linked_artifact_refs`는 저장돼 있었지만, main body의 `Linked References` 안쪽에 있어 next-step cue로는 약했다.
- Quick decision:
  - 새 route나 새 계약은 만들지 않는다.
  - existing `linked_artifact_refs`를 right rail로 끌어와 `Continue after note review` 블록으로 보여주고, detail ids 대신 lane-level reopen path만 제공한다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend image evidence viewer loads a registered bundle and keeps note handoff on the real route"`

## 7.5) Lane Hint Follow-Up Checkpoint (2026-03-29)
- Screen/Flow: `/image-evidence/:imageEvidenceId` `Continue after note review` follow-up links
- Goal action: 사용자가 lane 이름만 보는 수준을 넘어서, 왜 그 lane을 다시 열어야 하는지도 즉시 이해한다.
- Primary persona: note review 뒤 meeting/chart/comparison/protocol 중 어느 lane으로 이어갈지 빨리 판단하려는 연구자
- Current friction:
  - lane label만 있으면 사용자는 여전히 “왜 이걸 열지?”를 한 번 더 해석해야 했다.
  - `linked_artifact_refs`는 downstream 연결은 말해주지만, lane purpose까지는 말해주지 않았다.
- Quick decision:
  - 새 route나 richer artifact payload는 만들지 않는다.
  - follow-up link마다 lane-specific one-line hint만 붙여 note 이후 next action을 더 직접적으로 말한다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend image evidence viewer loads a registered bundle and keeps note handoff on the real route"`

## 7.6) Keyboard Focus Drift Checkpoint (2026-03-30)
- Screen/Flow: `/image-evidence/:imageEvidenceId` detail keyboard navigation
- Goal action: keyboard-only user가 header actions와 note/follow-up handoff를 순서대로 밟고, 비대화형 metadata text block에서 focus가 멈추지 않는다.
- Primary persona: dense review surface를 마우스 없이 훑는 반복 사용자
- Current friction:
  - Chromium에서는 `overflow-x-auto`가 걸린 `<pre>`가 탭 순서에 들어올 수 있다.
  - `ImageEvidencePage` detail의 raw source ref와 handoff `openable_ref`는 정보 전달용 static text인데도 focus를 먹어, `Open note`와 downstream follow-up 뒤 흐름을 끊었다.
- Quick decision:
  - layout, copy, provenance contract는 유지한다.
  - non-interactive scrollable `<pre>`에 `tabIndex={-1}`만 추가해 keyboard focus drift를 막는다.
- Verification:
  - `cd frontend && npm run build`
  - current runtime keyboard tab audit on `/ui/image-evidence/imageev_current_runtime_smoke_20260330`
  - confirm `Open note`, downstream follow-up links stay in the tab order while raw source / handoff `<pre>` blocks do not
