Status: Active
Date: 2026-04-13
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: `AnalysisWorkbench` artifact panel inference boundary summary (`/workbench/:paperId`)
- Goal action: Let a research operator quickly understand which inference backend was used, what payload boundary applied, and whether redaction was used, without opening raw `run_meta.json`.
- Primary persona: Research operator reviewing a saved deep-read run before trusting or reusing its outputs.
- Current friction: The backend now records inference boundary metadata, but the workbench only exposes it inside raw JSON. Users must parse implementation-facing fields to answer a basic trust question: "what left the machine and which backend handled it?"
- Success metric: The workbench shows a compact, honest inference summary card with top-level backend/payload/redaction badges plus per-lane details, and users can understand the trust boundary without opening raw artifact JSON.
- Constraints:
  - Preserve the current `ArtifactPanel` layout and dark-first `--pp-*` visual contract.
  - Keep the raw artifact JSON available for audit, but do not require it for routine trust review.
  - Do not imply stronger guarantees than the stored metadata actually provides.

## Quick Review (5 min)
- The trust question exists today, but the answer is buried in raw JSON.
- The smallest safe improvement is a read-only summary card, not a new workflow.
- The card should foreground backend, payload class, and redaction status first, then expose lanes second.
- Users should never need to infer "commercial API" or "local-only" from field names like `inference_lanes`.
- Missing summary data should fail quiet rather than inventing certainty.

## Full Review
### P0
- If the workbench cannot answer "what crossed the boundary?" at a glance, it weakens trust in saved outputs for sensitive lab workflows.
- The card must distinguish data ownership from inference placement. "Local-first" does not mean every lane stayed local.

### P1
- The summary should show backend/payload/redaction as primary badges because those are the first trust questions an operator asks.
- Per-lane detail should stay compact and readable on desktop and mobile, without forcing raw JSON expansion.

### P2
- Future runs may add more lanes or lab-server routing. The UI should accept additional lanes without redesign.
- If later UX work adds explanatory help text or drill-down, this card can remain the stable summary header.

### Full Review Coverage
- 6P storyboard context:
  - Problem: the user wants to trust or question a saved run but cannot see the inference boundary quickly.
  - Emotion: uncertainty about whether sensitive context stayed local or left the machine.
  - Action: open the workbench to review a saved run.
  - Struggle: boundary metadata exists but is hidden in raw artifact JSON.
  - Attempt: the user opens raw JSON or guesses based on model names and outcomes.
  - Happy Ending: the user reads one compact card and immediately understands the backend and payload boundary.
- BMAP:
  - Motivation is high because trust review is part of deciding whether to reuse a saved run.
  - Ability is currently low because the metadata is implementation-shaped, not operator-shaped.
  - Prompt should live near other trust surfaces such as saved checks and compiled knowledge, not in a debug-only drawer.
- B.I.A.S:
  - Block: raw JSON is too effortful for routine review.
  - Interpret: users may misread backend names or over-assume locality.
  - Act: the best next step is to scan a compact summary, not expand a blob.
  - Store: repeated exposure to a consistent trust card builds confidence in the review loop.
- Peak-End:
  - Peak is the moment the user can answer the trust-boundary question without leaving the workbench.
  - Pit is the current need to inspect raw metadata for a basic operational fact.
  - Transition is from notebook-style reading cells into a trust-oriented runtime summary.
  - End should reinforce that raw JSON remains available when deeper audit is needed.
- Ethics:
  - Regret: the card should not overstate safety or imply that "redacted" means "risk-free."
  - Black Mirror: avoid visual language that hides external routing behind soft euphemisms.
  - In Real-Life: a trustworthy research tool states what happened plainly and lets the user verify it.

## BMAP diagnosis
- Motivation: High. Operators need quick trust checks before reuse, export, or sharing.
- Ability: Previously weak because the answer required raw JSON reading.
- Prompt: Strong if the card sits alongside saved checks and compiled knowledge in the artifact panel.

## B.I.A.S diagnosis
- Block: boundary metadata is present but too implementation-facing.
- Interpret: users can confuse backend quality, locality, and data exposure if the UI does not separate them.
- Act: one scan of badges plus lanes is the right minimum interaction.
- Store: repeated clear boundary summaries create a more trustworthy habit loop than forcing JSON inspection.

## Peak-End design notes
- Peak: one glance should answer "local, mixed, or external?"
- Pit: raw JSON feels like a debugging detour, not a review surface.
- Transition: introduce a compact "Inference boundary" card before the compiled knowledge / mirror lanes.
- End: keep the raw artifact viewer available so the summary feels audited, not magical.

## Concrete changes
- Add a read-only inference summary card to `ArtifactPanel` using the new `artifactBundle.inference_summary` contract.
- Show top-level badges for selected backend, payload class, and redaction status.
- Render each saved lane with a compact row showing lane name, backend, payload class, and provider/model when present.
- Add stable `data-testid` hooks for mock and backend E2E coverage.
- Seed backend E2E fixture `run_meta.json` with inference metadata so the browser path can verify the live contract.

## Ethics check results
- Regret: Low if the copy stays explicit and avoids overstating guarantees.
- Black Mirror: Low if external routing is labeled plainly instead of softened into generic "AI summary" language.
- In Real-Life: This feels like a candid lab assistant, not a marketing layer.

## Next PR-sized actions
- Add a small glossary/help affordance if users need clarification on `payload_class` semantics.
- Surface the same summary in artifact exports only if there is a clear operator need.
- Consider lane grouping if future runs grow beyond reader plus one or two adjunct lanes.

## 2026-04-14 checkpoint: Saved Section Reopen Signal
- Screen/Flow: `AnalysisWorkbench` header `Saved review state`
- Goal action: let an operator see whether note-backed section reopen cues are already present before diving into evidence cards.
- Current friction:
  - workbench can already open note-backed evidence, but section reopen quality is implicit.
  - the note viewer now exposes this distinction, while workbench still requires the operator to infer it from evidence cards or raw state.
- Quick decision:
  - keep the change inside the existing `Saved review state` card.
  - do not add a new workbench panel, CTA, or truth source.
  - reuse explicit signal first, then bounded inference from saved section summary/count and older claimset section labels.
- BMAP:
  - Motivation: high for operators checking whether saved note context is strong enough before deeper review.
  - Ability: one compact badge and one-line hint is enough.
  - Prompt: strongest next to `saved checks`, not in the artifact body.
- B.I.A.S:
  - Block: no extra navigation or dense subpanel.
  - Interpret: `Saved signal ready/thin/missing` explains support quality without pretending to own truth.
  - Act: users can keep reviewing in workbench or open the paper note with better context.
  - Store: reinforces that saved state quality is inspectable, not magical.
- Peak-End:
  - Peak is seeing saved review state and section reopen readiness together at the top of the workbench.
  - Pit is having to infer section quality from scattered evidence cards.
- Ethics:
  - Regret: pass. this exposes stored state quality more transparently.
  - Black Mirror: pass. no pressure or hidden ranking is introduced.
  - In Real-Life: pass. it behaves like a cautious collaborator explaining what support is already present.
- Concrete change:
  - Add a compact section reopen readiness row under `Saved review state`.
  - Prefer explicit note-backed signal fields, then bounded fallback from saved section summaries/counts or older claimset section labels.
  - Keep the row additive-only and separate from canonical evidence ownership.

## 2026-04-21 checkpoint: Saved Note Continuation Wording
- Screen/Flow: `AnalysisWorkbench` header `Saved review state` -> `Paper note` sub-card
- Goal action: let operators read the note handoff as a continuation of the same saved-note thread instead of a separate route-management step.
- Current friction:
  - the workbench header already exposed the right paper-note handoff, but the CTA wording split between `Open paper note` and `Add in paper note`.
  - that lagged behind the saved-note continuation language already used on home, note detail, and artifact viewers.
- Quick decision:
  - keep the current card structure and destination.
  - change only the paper-note handoff wording to `Continue in note`.
  - leave the surrounding saved-marker explanation unchanged.
- BMAP:
  - Motivation: high. workbench users often bounce back into the saved note while staying inside the same paper thread.
  - Ability: improves when the handoff sounds like continuation instead of route or object management.
  - Prompt: `Continue in note` is the cleanest prompt inside this loop.
- B.I.A.S:
  - Block: mixed `Open` / `Add` language created small but repeated interpretation drift.
  - Interpret: `Continue in note` better matches the actual state because the note already exists.
  - Act: users can jump back to the saved note with less translation cost.
  - Store: workbench now reinforces the same saved-note continuation language as adjacent surfaces.
- Peak-End:
  - Peak is seeing workbench describe the note handoff in the same language as the rest of the product loop.
  - Pit was the wording drift between note-first and workbench surfaces.
  - Transition is workbench review -> continue in note -> reopen reading or continue downstream work.
  - End is a more consistent paper-thread memory.
- Ethics:
  - Regret: pass. this is a clarity improvement only.
  - Black Mirror: pass. no action is hidden or deceptively reprioritized.
  - In Real-Life: pass. it sounds more like a careful teammate than a raw route label.
- Concrete change:
  - Rename the paper-note handoff CTA in `Saved review state` to `Continue in note` whether note markers already exist or not.
  - Keep explanatory note-state copy and destination unchanged.
  - Update keyboard-order and live browser expectations to match the continuation wording.

## 2026-04-21 checkpoint: Saved Checks Success Wording
- Screen/Flow: `AnalysisWorkbench` repair/rebuild success feedback for `Saved checks`
- Goal action: let operators understand the outcome of a repair or rebuild in paper-thread language instead of implementation language.
- Current friction:
  - the repair and rebuild success toasts correctly confirmed that saved checks were refreshed.
  - the trailing phrase `artifact bundle updated` exposed storage implementation details instead of telling the operator what changed for the current paper.
- Quick decision:
  - keep the current repair and rebuild actions, timing, and state transitions.
  - change only the success copy suffix to `The current paper now uses the refreshed checks.`
  - keep low-level detail in terminal logs rather than the main feedback toast.
- BMAP:
  - Motivation: high when an operator is unblocking review and wants immediate confirmation that the paper is ready again.
  - Ability: improves when the toast answers the user question directly instead of naming a storage object.
  - Prompt: the success toast should close the repair loop in user language.
- B.I.A.S:
  - Block: implementation wording makes the success state feel more technical than actionable.
  - Interpret: `The current paper now uses the refreshed checks.` maps the result back to the active review thread.
  - Act: users can continue reviewing without translating backend terms.
  - Store: the workbench feels more like a paper-first review tool and less like a storage debugger.
- Peak-End:
  - Peak is the repair toast clearly confirming that review can continue on the current paper.
  - Pit was finishing the repair and seeing backend storage language in the success state.
  - Transition is refresh/rebuild checks -> confirmation -> continue reviewing the same paper thread.
  - End is a cleaner memory that the repair action restored the paper's saved checks.
- Ethics:
  - Regret: pass. the change removes jargon without hiding what happened.
  - Black Mirror: pass. no certainty is invented beyond the actual refresh result.
  - In Real-Life: pass. this sounds more like a teammate confirming the paper is ready again.
- Concrete change:
  - Replace the `artifact bundle updated` success suffix in repair and rebuild feedback with `The current paper now uses the refreshed checks.`
  - Keep terminal logs unchanged for implementation-level debugging detail.
  - Update browser coverage to assert the paper-thread success wording on both repair and rebuild flows.

## 2026-04-26 checkpoint: Workbench Paper ID Copy
- Screen/Flow: `AnalysisWorkbench` header `Saved review state`
- Goal action: let operators copy the current `paper_id` from the workbench before using CLI/API handoff commands.
- Primary persona: first-session or repeat operators who move between workbench, terminal commands, and API/job identifiers.
- Current friction:
  - the route contains the paper id, but users had to select it from the URL or infer it from deeper API/debug context.
  - imported-note detail already exposes `Copy ID`; workbench did not yet match that handoff affordance.
- Quick Review:
  - P0: surface the current Paper ID inside the existing saved-state context, not as a new card.
  - P1: use a small `Copy ID` action with the same pattern as imported notes.
  - P2: avoid adding a second workflow prompt; this is a utility affordance only.
- Full Review:
  - 6P: user has a current paper open, needs an id for a terminal/API command, struggles with URL selection, copies the id from the saved-state row, and continues review/deep-read work.
  - BMAP: motivation is high during handoff; ability improves by making the id selectable with one action; prompt belongs next to saved review state.
  - B.I.A.S: the row reduces hidden identifier lookup, interprets the current route as the active paper thread, enables copy, and stores confidence that workbench and CLI share the same id.
  - Peak-End: peak is copying the id without leaving workbench; pit is manual URL selection; transition is workbench -> CLI/API handoff; end is a clearer paper-thread memory.
  - Ethics: no hidden tracking, urgency, or data movement; copy is user-initiated.
- Concrete change:
  - Add a compact `Paper ID` row and `Copy ID` button to `Saved review state`.
  - Reset copied state when the workbench paper id changes.
  - Update backend E2E coverage for the saved-state header context.

## 2026-05-14 checkpoint: Compiled Markdown Handoff Emphasis
- Screen/Flow: `AnalysisWorkbench` artifact panel `Compiled knowledge` card
- Goal action: let operators open the saved compiled markdown when needed without reading it as a primary trust action ahead of source refs, evidence refs, warnings, and lineage.
- Primary persona: operator reviewing compiled paper synthesis before using the prose downstream.
- Current friction:
  - The card already labels the lane `Non-canonical`, shows source/evidence/warning counts, and provides a `Trust reopen path` plus `Inspect source refs`.
  - The final `Open markdown` link still used accent treatment, so the raw compiled note could visually compete with upstream lineage review.
- Quick decision:
  - Keep the markdown URL, audit log action, and popup behavior unchanged.
  - Lower only the visual treatment from accent to secondary outline and add a title reminding users to inspect source refs and trust reopen path first.
- Quick Review:
  - P0: do not hide raw markdown access; it remains an audit/handoff path.
  - P1: compiled prose should not be visually stronger than lineage and source-ref review.
  - P2: title copy is supportive only; the card structure remains the main trust boundary.
- Full Review:
  - 6P storyboard context: researcher sees compiled prose exists, worries whether it can be reused, checks source/evidence/warning counts and lineage, then opens markdown only when they need the derived note itself.
  - BMAP: motivation is high for downstream reuse; ability remains high because the link stays visible; prompt shifts from “open this now” to “review lineage first, then open if needed.”
  - B.I.A.S: Block is an accent handoff competing with trust signals; Interpret improves when the link reads as secondary audit access; Act remains one click; Store reinforces compiled knowledge as non-canonical.
  - Peak-End: peak is seeing the trust reopen path before compiled prose; pit is treating markdown polish as reviewed truth; end is an opened markdown artifact with provenance context already in mind.
  - Ethics: Regret pass because users are less likely to reuse prose without context. Black Mirror pass because polished derived text does not outrank uncertainty. In Real-Life pass because a careful teammate would point to sources before handing over the prose.
- Concrete change:
  - Change `Open markdown` from accent treatment to secondary outline treatment.
  - Add title copy: `Inspect source refs and trust reopen path before relying on compiled markdown.`
  - Preserve `workbench_open_paper_synthesis_markdown` audit logging and `/api/paper-syntheses/:id/markdown` URL.

## Verification
- `python3 scripts/lint_docs.py docs/UX_REVIEW_REPORT_workbench-inference-summary.md`
- `cd frontend && npm run build`
- `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "workbench surfaces inference summary in mock mode"`
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workbench shows inference boundary summary"`
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend meeting pack create keeps the continuation card and note handoff on the real route"`
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend repair stats action appears only when stats artifact is missing and hides after repair|backend rebuild stats action stays under advanced controls and overwrites the current snapshot"`
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workbench surfaces saved section reopen signal in the header context"`
