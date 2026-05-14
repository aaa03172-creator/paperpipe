# Biomedical Research Workspace UI Review (2026-03-29)

Status: repo-grounded design review
Scope: current FastAPI + Vite + React Router UI only
Basis:
- actual routes in `frontend/src/App.tsx`
- current page/layout/component code
- current UX review artifacts under `docs/UX_REVIEW_REPORT_*.md`

This document does **not** adopt external prompts or reference products literally. It translates them into changes that fit the current PaperPipe repo, current component vocabulary, and the current local-first biomedical research workspace story.

## 1. Executive summary

PaperPipe already has the beginnings of a real research workspace: a triage home, a note browser, a reading detail view, a workbench, and several exportable artifact lanes. The main weakness is not the absence of features. It is that the UI still surfaces too much of its route catalog and operational structure before it clearly communicates the core value loop: ingest a paper, read it, inspect evidence, review uncertainty, and hand work forward into a reusable artifact.

### Current UI in one sentence
The current UI is **closer to a working local research shell than to a generic AI SaaS**, but it still under-explains its highest-value objects and shows provenance/review strength too late in the flow.

### Biggest problems
1. The strongest differentiation of the product, evidence, provenance, review state, and structured outputs, lives deeper in the flow than the first-session surfaces.
2. Some screens still read like route inventory or operator tooling rather than one connected biomedical research workspace.
3. Reading, structure review, and artifact generation are all present, but the handoff language between them is still weaker than the underlying capability.

### First things to fix
1. Make `paper -> evidence/review -> next action` more explicit on first-contact surfaces, especially triage, paper list rows, and paper detail.
2. Reuse shared status/provenance/review blocks more aggressively instead of letting each screen explain itself differently.
3. Tighten artifact-lane framing so each lane answers “when do I use this?” in one sentence before showing controls.

### What from the reference prompts is too much for the current repo
- A full project-centered entity redesign is too large for the current codebase and unnecessary for the next UI step.
- HeroUI as a library/system migration is not warranted; the repo already has workable UI primitives and Tailwind token contracts.
- taste-skill-like visual taste is useful only as a guardrail against generic UI patterns, not as a visual system to copy.
- A new “AI research super-app” shell would be overreach. PaperPipe needs sharper information hierarchy, not a new product architecture.

## 2. Current UI reality map

### Actual top-level routes
- `/`
  - `TriageDashboard`
  - current role: first-session entry, queue scan, route hub, onboarding CTA
  - current confusion: it still has to balance onboarding and advanced artifact lanes in one place
- `/papers`
  - `PaperNotesListPage`
  - current role: canonical note index, search/filter, manual PDF import entry
  - current confusion: the list is useful, but the route still reads more as a note browser than as the front door to evidence-driven work
- `/papers/:slug`
  - `PaperNoteDetailPage`
  - current role: note reading surface, related papers, structured signal summary, workbench handoff
  - current confusion: this is one of the strongest screens, but the structured state is still secondary to the markdown body in ways that sometimes hide PaperPipe’s real advantage
- `/workbench/:paperId`
  - `AnalysisWorkbench`
  - current role: deep-read workspace, PDF/text, claims/evidence, operational actions, timeline
  - current confusion: strongest product differentiation lives here, but the screen still carries operator/debug tone in places
- `/meeting-packs`, `/method-comparisons`, `/chart-packs`, `/image-evidence`, `/protocol-cards`
  - current role: saved and now partially creatable research artifacts
  - current confusion: several lanes are more usable than they first appear, but their value proposition is still not obvious from their headers alone
- `/ready`
  - `RuntimeReadinessPage`
  - current role: machine/runtime readiness, watched-folder/import transparency
  - current confusion: helpful operationally, but should remain secondary to research work, not a primary product identity

### Existing reusable building blocks worth keeping
- `Rail`
  - compact left navigation with status, review, access, and ops hints
- `ArtifactPanel`
  - strong candidate for PaperPipe’s “evidence/review output” pattern
- `OperationalStateSummary`
  - one of the best current primitives for shared health state language
- `ContentReviewSummary`
  - useful review-state block that should appear earlier and more consistently
- `StatusBadge` / `StatusChip`
  - lightweight, token-consistent status primitives
- `WorkbenchLayout`
  - already a credible research shell: left rail, reading panel, artifact/timeline column

### Where users are likely to get confused
- The home page still needs to explain the research loop, not just the available routes.
- The paper detail page has strong reading support, but “why this is better than a markdown note viewer” still depends on users noticing the structured side panels.
- Artifact routes can look like separate tools rather than downstream views of the same structured research state.
- Confidence, provenance, and review are present, but not yet visually elevated enough to define the whole product.

## 3. Verified UI findings

### Verified from current code and routes
- `frontend/src/App.tsx`
  - the product is already organized around a real workspace route map, not a single chat shell
  - `TriageDashboard`, `PaperNotesListPage`, `PaperNoteDetailPage`, `AnalysisWorkbench`, artifact pages, and `RuntimeReadinessPage` are all first-class routes
- `frontend/src/app/pages/TriageDashboard.tsx`
  - the home surface is now explicitly split into `Start here` and `More tools`
  - this confirms the UI is already moving away from a flat route directory
- `frontend/src/app/pages/PaperNotesListPage.tsx`
  - the paper note list is the real ingestion/browse entry point
  - manual PDF import is already present, which means first-session improvement does not require a new ingest product
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
  - the repo already has a sophisticated note-reading surface with related papers, structured state support, focus targets, grounding badges, and explicit workbench handoff
- `frontend/src/app/pages/AnalysisWorkbench.tsx`
  - the workbench already contains the highest-value research UI primitives: claim/evidence review, timeline, parser/runtime actions, paper access, structured state, and artifact bundle access
- `frontend/src/app/layouts/WorkbenchLayout.tsx`
  - the app already has a reusable three-column research shell
  - no full layout-system rewrite is needed to make it feel like a research workspace
- `frontend/src/app/components/Rail.tsx`
  - navigation already carries meaningful research metadata: access route, review state, operational state
- `frontend/src/app/components/ArtifactPanel.tsx`
  - provenance and review semantics already exist in reusable form: grounding, verdict, content review, operational state, claim selection
- `frontend/package.json`
  - the frontend stack is intentionally small
  - there is no existing HeroUI dependency, which supports the decision to borrow system principles rather than introduce a new UI framework

### What this means
- The core problem is not missing screens.
- The core problem is that the best research-specific UI language is unevenly distributed.
- The next realistic UI step is to normalize and elevate the strongest existing patterns, not replace them.

## 4. Scorecard

| Area | Score | Why |
|---|---:|---|
| A. First-screen clarity | 3 | Better after `Start here`, but the product promise still depends on reading below-the-fold or entering deeper screens. |
| B. Evidence traceability | 4 | `ArtifactPanel`, note evidence metadata, grounding badges, and workbench structure are strong. The problem is prominence, not absence. |
| C. Information architecture consistency | 3 | Routes are coherent and share data concepts, but artifacts still feel more lane-based than project-context based. |
| D. Reading experience | 4 | Paper detail is one of the strongest surfaces. Markdown, outline, related papers, and references are already useful and reasonably dense. |
| E. Action transition speed | 3 | Manual import and better artifact quick-picks help a lot, but some action language still reads like operator UI rather than research next-step UI. |
| F. Findability and recovery | 3 | Search, filters, related links, and rails exist, but the cross-object recall story is still stronger within a route than across the whole workspace. |
| G. Density vs fatigue | 3 | The app is generally dense-but-readable, but priority is not always obvious and some surfaces still explain too much at the same visual weight. |
| H. High-speed operation | 2 | There is some fast-path behavior, but no clear command-driven shell or strong keyboard-first mental model yet. |
| I. Local-first / privacy trust | 4 | Import path, readiness page, masking rules, and runtime transparency are genuinely good. This is already a differentiator. |
| J. Artifact productivity | 3 | Meeting pack, chart pack, method comparison, and protocol card are becoming real outputs, but the “why/when use this” framing still needs work. |

### Score summary
- Highest current strengths:
  - reading detail
  - traceability foundations
  - local-first trust signals
- Lowest current strengths:
  - high-speed commandability
  - first-screen product explanation
  - cross-screen value framing

## 5. Benchmark translation

### NotebookLM
#### Worth translating
- source-grounded output framing
- notebook/project feeling around a bounded set of sources
- visible citation-linked reasoning rather than free-floating AI answers

#### Not worth copying directly
- conversational chat-first shell
- generic “ask anything about sources” framing as the main product identity

#### Repo-grounded translation
- Put evidence/review/provenance summaries earlier in note detail and workbench headers.
- Let artifact lanes describe themselves as grounded derivatives of paper/note state, not standalone generators.
- Reuse `ArtifactPanel`, grounding badges, and content review summaries as PaperPipe’s equivalent of source-grounded response UI.

### Obsidian
#### Worth translating
- local-first trust
- notes as durable canonical objects
- visible linked context and user-controlled structure

#### Not worth copying directly
- graph-as-hero
- maximal plugin-workbench feel

#### Repo-grounded translation
- Keep note detail as a first-class reading surface.
- Make related papers, structured state, and downstream artifact links feel like views over one note-centered truth source.
- Continue to treat local/runtime state as explicit and inspectable, especially around import/readiness/export.

### Notion
#### Worth translating
- one canonical entity shown through multiple views
- linked-database mindset
- strong object boundaries

#### Not worth copying directly
- generic database-table UX everywhere
- over-abstraction into pages-within-pages

#### Repo-grounded translation
- Treat `paper`, `note`, `workbench state`, and `artifact` as linked views over shared state instead of siloed routes.
- Add more explicit “derived from” and “used in” framing to artifact headers.
- Avoid creating a new project-database system unless the backend model explicitly supports it.

### Linear
#### Worth translating
- crisp action language
- triage-first hierarchy
- dense UI with clear next steps

#### Not worth copying directly
- software-issue metaphors
- overly compressed engineering workflow patterns where reading depth matters

#### Repo-grounded translation
- More imperative next-action copy on row headers and artifact pages.
- Stronger bucketed triage summaries.
- Better keyboard/command affordances later, but not as a prerequisite for the next UI patch.

### Elicit
#### Worth translating
- staged research workflow
- extraction/review/report progression
- visible evidence next to AI synthesis

#### Not worth copying directly
- questionnaire-heavy front doors
- spreadsheet-like research flow everywhere

#### Repo-grounded translation
- Clarify which screens are for reading, which are for reviewing, and which are for turning structured state into outputs.
- Make uncertainty and review state more legible on paper detail and workbench, not only in artifacts.
- Let artifact surfaces feel like “report stage” rather than generic output generators.

### HeroUI and taste-skill, translated realistically
#### Keep from HeroUI
- composable component discipline
- accessible state surfaces
- clear variant/system thinking

#### Do not do
- a new library migration
- a new visual language that competes with the current token system

#### Keep from taste-skill
- anti-card-overuse
- anti-placeholder
- anti-generic AI gradients/glow
- spacing/typography discipline

#### Do not do
- landing-page aesthetics
- showy motion
- novelty-driven asymmetry that hurts research reading

## 6. Design direction

### Visual and structural direction
- Evidence first
  - claims, evidence status, and review state should be easier to see before users commit to deeper inspection
- Provenance always visible
  - grounded, unresolved, and review-needed states should be present wherever derived outputs are shown
- Dense but readable
  - preserve the current research density, but reduce equal-weight explanation and route clutter
- Local-first trust
  - continue showing import, readiness, and source-path policy explicitly; this is already a strength
- Workflow over decoration
  - avoid marketing-style hero treatment or aesthetic-only redesign; the UI should help users move from reading to review to artifact creation

### How this should feel
- not a generic AI dashboard
- not a note-taking app with a few AI buttons
- not an internal operator panel
- instead: a deliberate research workspace where paper, evidence, review, and output feel like one chain of work

## 7. Priority fixes

### P0

#### 1) Make evidence/review/provenance visible earlier on note-centered screens
- Problem:
  - The strongest PaperPipe differentiators show up after the user has already committed to deeper reading.
- Why it matters:
  - Without this, the app can still feel like a better markdown/PDF browser instead of a grounded research workspace.
- User loss:
  - Users may miss the reason to keep using PaperPipe instead of a vault viewer plus ad hoc ChatGPT use.
- Improvement direction:
  - Pull content review, grounding, and “used in artifact” summaries closer to the paper detail header and upper-right rail.
- Likely implementation units:
  - `frontend/src/app/pages/PaperNoteDetailPage.tsx`
  - `frontend/src/app/components/ContentReviewSummary.tsx`
  - `frontend/src/app/components/OperationalStateSummary.tsx`

#### 2) Tighten artifact lane framing into “when to use this”
- Problem:
  - Artifact routes are functional but still require interpretation.
- Why it matters:
  - If artifact pages do not answer “why am I here?” immediately, they feel like optional side tools.
- User loss:
  - Users underuse built features that actually save time.
- Improvement direction:
  - Each artifact page header should explain its role in the research workflow in one sentence.
- Likely implementation units:
  - `frontend/src/app/pages/MeetingPackPage.tsx`
  - `frontend/src/app/pages/MethodComparisonPage.tsx`
  - `frontend/src/app/pages/ChartPackPage.tsx`
  - `frontend/src/app/pages/ProtocolCardPage.tsx`

#### 3) Reduce operator language that still leaks into core workflow
- Problem:
  - Some surfaces still carry runtime/debug vocabulary more strongly than researcher-facing action language.
- Why it matters:
  - It weakens trust and makes the tool feel like an internal system rather than a research workspace.
- User loss:
  - Users slow down because they translate interface language before acting.
- Improvement direction:
  - Keep precise operational detail, but subordinate it under human-readable next-step copy.
- Likely implementation units:
  - `frontend/src/app/pages/AnalysisWorkbench.tsx`
  - `frontend/src/app/layouts/WorkbenchLayout.tsx`
  - `frontend/src/app/pages/TriageDashboard.tsx`

### P1

#### 4) Make cross-object relationships more explicit
- Problem:
  - The product wants to connect paper, note, evidence, artifact, and decision, but that graph is still implicit.
- Why it matters:
  - PaperPipe’s long-term value is not just per-screen utility; it is state reuse across screens.
- User loss:
  - Returning to prior work is slower than it should be.
- Improvement direction:
  - Add lightweight “derived from”, “used by”, and “continue in” links in headers and side inspectors.
- Likely implementation units:
  - `PaperNoteDetailPage.tsx`
  - `AnalysisWorkbench.tsx`
  - artifact page headers

#### 5) Normalize screen-level hierarchy across dense views
- Problem:
  - Several pages still let primary and secondary information compete at similar visual weight.
- Why it matters:
  - Dense research UI only works when hierarchy is explicit.
- User loss:
  - Fatigue rises even if capability is present.
- Improvement direction:
  - Standardize header > primary action > status summary > supporting detail ordering.
- Likely implementation units:
  - `WorkbenchLayout.tsx`
  - artifact page shared sections
  - notes/detail shell headers

#### 6) Tighten the “import -> read -> inspect -> export” story on home
- Problem:
  - Home is better now, but it still introduces routes more than the actual research loop.
- Why it matters:
  - The first screen should explain not just where to click, but what this workspace lets you accomplish.
- User loss:
  - Differentiation remains muted.
- Improvement direction:
  - Add a short workflow strip that shows the main loop using existing routes.
- Likely implementation units:
  - `frontend/src/app/pages/TriageDashboard.tsx`

### P2

#### 7) Add keyboard/command acceleration where repetition is real
- Problem:
  - High-speed operation is underdeveloped.
- Why it matters:
  - Repeated research work should get faster over time.
- User loss:
  - Power users stay mouse-heavy.
- Improvement direction:
  - Start with route jump/search actions, not a full command system rewrite.
- Likely implementation units:
  - app shell
  - papers/workbench/artifact navigation

#### 8) Consider stronger project-level grouping later
- Problem:
  - The product story wants project-scoped research context, but current routes are mostly paper/artifact scoped.
- Why it matters:
  - This could become a real strength, but it is not the next patch.
- User loss:
  - Mild today, larger later as scale grows.
- Improvement direction:
  - Keep as a later structural review, not an immediate redesign.

## 8. Proposed UX structure

### Information structure
- Primary objects
  - paper
  - note
  - claim/evidence/review state
  - artifact
- Secondary objects
  - runtime/setup state
  - sync/export mechanics
  - low-level operational actions

### Screen-to-screen structure
- Home
  - explain the loop
  - expose import and browse
  - keep advanced tools discoverable but secondary
- Paper list
  - canonical note index
  - fast filtering and import
  - clear row-level state signals
- Paper detail
  - reading first
  - structured review always visible
  - clear handoff to workbench and downstream artifacts
- Workbench
  - evidence/debug/review first
  - actions and provenance explicit
  - timeline secondary but available
- Artifact views
  - downstream outputs
  - always identify source note/paper/run context
  - show why the artifact exists

### Three core user flows

#### Flow 1: First-session ingestion
- Home
- Add your PDF
- Paper Notes
- Paper detail
- Open in Workbench

#### Flow 2: Review and validation
- Paper detail
- Workbench
- claim/evidence inspection
- content review / ops summary
- repair or deep-read rerun if needed

#### Flow 3: Downstream artifact production
- Workbench or note context
- choose artifact lane
- create or open artifact
- inspect trace/source
- export or reuse in meeting/protocol/report work

## 9. Proposed component/system plan

### Keep and strengthen existing shared blocks
- `Rail`
  - keep as the compact navigation/state surface
  - strengthen as the canonical “research queue in miniature”
- `ArtifactPanel`
  - keep as the primary evidence/review/output block
  - extend as the shared derived-output language, not just a workbench detail
- `OperationalStateSummary`
  - keep as the shared health-state translator
- `ContentReviewSummary`
  - use more aggressively on note detail and workbench headers
- `WorkbenchLayout`
  - keep as the app’s strongest shell pattern

### New shared blocks worth adding, but only as light wrappers
- `ResearchObjectHeader`
  - for note detail, workbench, and artifact detail headers
  - should combine title, source context, confidence/review summary, and next action
- `DerivedFromStrip`
  - a compact line for `derived from note`, `derived from run`, `continue in workbench`, `used in artifact`
- `WorkflowHint`
  - one-sentence explanation of why a route exists
  - especially useful for artifact pages
- `ProvenanceBadgeGroup`
  - a consistent grouping for grounded / needs review / unresolved / unavailable

### How HeroUI-style composability translates here
- not via new dependencies
- through small shared wrappers built from current Tailwind and current UI primitives
- through consistent component APIs and consistent slot order across note/workbench/artifact surfaces

## 10. Concrete implementation suggestions

### Files/components to touch first
- `frontend/src/app/pages/TriageDashboard.tsx`
  - add a compact “research loop” strip under `Start here`
  - keep `More tools`, but add one-sentence purpose copy for each lane
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
  - move review/provenance summary blocks higher in the right-side hierarchy
  - add compact “continue with” links for workbench and relevant artifact surfaces
- `frontend/src/app/pages/AnalysisWorkbench.tsx`
  - simplify top-level control copy
  - make evidence/review summary feel primary, timeline/logging feel secondary
- `frontend/src/app/layouts/WorkbenchLayout.tsx`
  - make the top bar feel less like a tooling header and more like a paper-review state header
- `frontend/src/app/components/ArtifactPanel.tsx`
  - elevate “grounded / needs review / unresolved” further
  - make source relation to paper/note/run more visible
- artifact pages
  - add “when to use this” copy and “derived from” context at the top

### Shared UI blocks worth creating or formalizing
- `ResearchObjectHeader`
  - title
  - source context
  - confidence/review badges
  - primary next action
- `DerivedFromStrip`
  - note/paper/run linkage
  - used by / derived from / continue in
- `ProvenanceBadgeGroup`
  - grounded
  - needs review
  - unresolved
  - source route present
- `WorkflowHint`
  - one sentence: why this page exists in the research workflow

### Things to reduce or remove
- low-value header clutter where multiple navigation choices have equal weight
- repeated operational explanation when a shared summary block already exists
- pages that open with controls before explaining object identity and workflow purpose

### Things to emphasize
- evidence and review state
- note-centered canonical truth
- local-first control
- source context of artifacts
- next best action

## 11. Patch plan

### PR 1: Surface the research loop on home
- Purpose:
  - make the first screen explain the workflow, not just the routes
- Scope:
  - `TriageDashboard.tsx`
  - `docs/UX_REVIEW_REPORT_triage-dashboard.md`
- Expected effect:
  - first-session users understand PaperPipe as a workspace, not a route menu
- Risk:
  - low; copy and hierarchy only

### PR 2: Lift review/provenance higher on paper detail
- Purpose:
  - make PaperPipe’s unique value visible before users reach deep workbench interactions
- Scope:
  - `PaperNoteDetailPage.tsx`
  - reuse `ContentReviewSummary`, grounding badges, and `OperationalStateSummary`
- Expected effect:
  - stronger differentiation on the best reading screen
- Risk:
  - moderate; dense layout changes can hurt reading if overdone

### PR 3: Reframe workbench header around review state, not tooling
- Purpose:
  - make the workbench feel like a research-review surface first
- Scope:
  - `WorkbenchLayout.tsx`
  - `AnalysisWorkbench.tsx`
- Expected effect:
  - less internal-tool feel, clearer primary action hierarchy
- Risk:
  - moderate; control discoverability must remain intact

### PR 4: Add workflow-purpose headers to artifact lanes
- Purpose:
  - convert artifact routes from “advanced tools” to “named stages in the research loop”
- Scope:
  - meeting pack / method comparison / chart pack / protocol card page headers
- Expected effect:
  - artifact value becomes easier to understand without training
- Risk:
  - low; mostly header/copy and light layout work

### PR 5: Formalize reusable research-shell blocks
- Purpose:
  - reduce screen-by-screen drift
- Scope:
  - shared header/provenance/workflow hint blocks
- Expected effect:
  - more coherent UI without a rewrite
- Risk:
  - moderate; only worth doing after the smaller hierarchy patches are proven

## 12. Follow-up plan

### After the first hierarchy/provenance patch wave
- formalize shared header composition between note detail, workbench, and artifact detail
- standardize page-top information order:
  - identity
  - review/provenance
  - next action
  - supporting operational detail
- review whether a lightweight command/search jump layer is worth adding for frequent users
- revisit project-level grouping only after note/workbench/artifact handoffs feel fully coherent

## 13. Risks / tradeoffs

### Over-design risk
- A more ambitious visual redesign could make the app look newer while making it less trustworthy as a research tool.
- The repo already has meaningful research UI patterns; replacing them too early would create churn without improving clarity.

### Density risk
- Pulling more review/provenance UI upward can hurt reading if it becomes visually noisy.
- The right move is selective elevation, not turning every header into a dashboard.

### System risk
- Adding too many new shared wrappers too early can create another abstraction layer before the patterns are stable.
- Shared components should follow proven screen-level wins, not lead them.

### Reference-product mismatch risk
- NotebookLM, Notion, Linear, and Elicit solve adjacent problems, not this exact one.
- Treating them as direct templates would distort the repo toward other product categories.

## 14. 지금 가장 적은 수정으로 가장 큰 체감 개선을 만드는 5개 변경

1. Home에 “이 앱으로 무엇을 하게 되는가”를 한 줄 루프로 붙이기
2. Paper detail 상단 rail에 review/provenance summary를 더 먼저 보이게 하기
3. Workbench header를 tooling header보다 paper-review header처럼 재정렬하기
4. Artifact page마다 “언제 쓰는지 / 어디서 파생됐는지”를 한 줄로 명시하기
5. Shared provenance/review/status blocks를 더 많은 화면에서 같은 방식으로 재사용하기
