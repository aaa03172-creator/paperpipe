# Research Workspace Home Resume Card PR Brief (2026-04-01)

Status: working implementation brief
Scope: first implementation pass for home `Continue current work` in `TriageDashboard`
Basis:
- `docs/reports/Research_Workspace_Home_IA_Draft_2026-04-01.md`
- `docs/reports/Research_Workspace_Continue_Current_Work_Copy_Rules_2026-04-01.md`
- `docs/reports/Research_Workspace_Home_Resume_Card_Spec_2026-04-01.md`
- `docs/reports/Research_Workspace_Implementation_Sequencing_2026-04-01.md`
- current implementation in `frontend/src/app/pages/TriageDashboard.tsx`
- current types in `frontend/src/app/lib/types.ts`

This brief is the first implementation-ready translation for the home resume card.
It is intentionally conservative and repo-fit.
It does not assume a new backend thread model or a project runtime.

## 1. PR objective

Replace the current top-left `Start here` emphasis on home with a single `Continue current work` card that:
- reflects one likely current paper thread
- uses current repo signals only
- preserves the product rule:
  - blocker
  - review
  - reading
  - artifact continuation

For this first PR, the card should improve action clarity without pretending the runtime already supports a full thread model.

## 2. Scope

### In scope
- one `Continue current work` card in `TriageDashboard`
- one lightweight frontend-assembled `resumeThread` view model
- state-aware primary CTA copy
- demotion of `Start here` from the top-left dominant block
- optional relabel/demotion of `More tools`
- small helper extraction inside `TriageDashboard` or a tiny local helper file if needed

### Out of scope
- new backend endpoint
- project system
- artifact draft integration
- multi-card ranking UI
- queue redesign beyond keeping current triage surfaces below
- route merge or broader shell rewrite

## 3. Critical implementation reality

### Important constraint
`TriageDashboard` currently loads `PaperSummary[]` from `getPapers()`.

That data includes:
- `paper_id`
- `title`
- `updated_at`
- `ops_summary`
- `access_summary`
- claim-review signals

It does **not** include:
- note slug
- direct paper-note route target
- project context
- artifact draft hint

### Consequence
The first PR can support:
- `Fix blocker`
- `Resume review`

It cannot fully support a true thread-specific `Resume reading` CTA to note detail without extra note-link data.

### Recommended honest behavior
Do **not** fake a note-level resume route in this PR.

Instead:
- implement blocked and review states fully
- keep reading-state language support in the spec
- but treat reading-state navigation as a follow-up that requires either:
  - note slug in `PaperSummary`
  - or a second lightweight fetch/join with note summaries

This is the most important repo-grounded constraint for the first patch.

## 4. Recommendation

### Recommended v1 behavior
- if there is a blocked paper thread:
  - show `Fix blocker`
  - CTA opens workbench for that paper
- else if there is a review-needed paper thread:
  - show `Resume review`
  - CTA opens workbench for that paper
- else:
  - show a lighter non-thread fallback block or keep a compressed `Start here / Browse Paper Notes` support block

### Why
- it avoids lying about note-level resume capability that the current home payload cannot support
- it still moves home meaningfully toward a resume-first experience
- it keeps the PR small and defensible

## 5. Candidate selection rule

The card selector should operate on:

- `papers`

not:

- `filteredPapers`

### Why
- search is a local browsing/filtering tool
- `Continue current work` should stay stable even if the user has typed a search query
- otherwise the “current thread” disappears when the user filters the table

## 6. Minimal v1 selector logic

### Step 1: classify each paper

For each `PaperSummary`, derive:
- `blocked`
  - when `paper.ops_summary?.recommended_action === "repair_stats"`
- `review`
  - when `paper.ops_summary?.recommended_action === "open_workbench"`
  - or content review state is `flagged`
- `ready`
  - all other cases

### Step 2: assign priority
- blocked = 3
- review = 2
- ready = 1

### Step 3: sort within priority
- most recent `updated_at` first
- tie-break by title

### Step 4: choose one candidate
- first item in the sorted list

### Why this is enough
- it uses existing repo signals only
- it avoids a recommendation engine
- it stays deterministic and understandable

## 7. Recommended v1 view model

```ts
type HomeResumeCardModel = {
  paperId: string;
  paperTitle: string;
  primaryState: "blocked" | "review";
  nextActionLabel: string;
  nextActionHint?: string | null;
  ctaLabel: "Fix blocker" | "Resume review";
  accessLabel?: string | null;
  accessTone?: import("../lib/statusSystem").StatusTone | null;
  accessHref?: string | null;
  accessLinkLabel?: string | null;
  updatedAt?: string | null;
  focusIssues?: boolean;
};
```

### Notes
- `primaryState` does not include `reading` in v1
- `focusIssues` can be true when content review is flagged and workbench should open with `?focus=issues`

## 8. Recommended helper functions

Keep the first pass local to `TriageDashboard` unless the logic proves reusable.

### Suggested helpers

```ts
function deriveResumePriority(paper: PaperSummary): 3 | 2 | 1
function buildHomeResumeCardModel(papers: PaperSummary[]): HomeResumeCardModel | null
```

### Behavior
- `deriveResumePriority` should compose current `ops_summary` and `deriveContentReviewSummary`
- `buildHomeResumeCardModel` should:
  - use `papers`
  - sort deterministically
  - return one card model or `null`

## 9. Rendering changes in `TriageDashboard`

### Recommended structure

Current:
- top-left `Start here`
- top-right `More tools`

Recommended v1:
- top-left `Continue current work`
- top-right compressed `Start here`
- move `More tools` lower or visually soften it

### Resume card rendering rules
- use existing raised card styling
- use one block label:
  - `Continue current work`
- show paper title as the strongest text
- show one `Next:` sentence
- show one short hint line
- show at most 2 compact tokens
- show one CTA

### CTA behavior
- blocked:
  - button label `Fix blocker`
  - navigate to `/workbench/:paperId`
- review:
  - button label `Resume review`
  - navigate to `/workbench/:paperId`
  - use `?focus=issues` when flagged content review is the deciding reason

## 10. Logging and test IDs

Keep logging consistent with current home behavior.

### Recommended action origins
- `home_resume_card_blocked`
- `home_resume_card_review`

### Recommended test IDs
- `home-resume-card`
- `home-resume-title`
- `home-resume-next-action`
- `home-resume-hint`
- `home-resume-cta`

## 11. Copy rules for v1

### Blocked
- title:
  - paper title
- next sentence:
  - `Next: Fix the blocker before continuing review.`
- hint:
  - derived blocker reason
- CTA:
  - `Fix blocker`

### Review
- title:
  - paper title
- next sentence:
  - `Next: Review flagged claims and evidence.`
  - or:
  - `Next: Continue evidence review for this paper.`
- hint:
  - issue-count sentence if flagged
  - otherwise review guidance sentence
- CTA:
  - `Resume review`

### Ready fallback
For this first PR, do not force a false thread resume card for ready-only papers.

Preferred behavior:
- return `null` from `buildHomeResumeCardModel`
- let the smaller `Start here / Browse Paper Notes` support block handle the no-action-needed case

This is more honest than inventing a `Resume reading` target the current payload cannot support.

## 12. What should not happen in this PR

Do not:
- join in project context with placeholder data
- show artifact draft hints without real source data
- create 3 to 5 “recommended threads”
- make the card sensitive to current search filtering
- add a fake `Resume reading` CTA that still goes to workbench

The last point matters most.
If the CTA says `Resume reading`, it should eventually go to the paper workspace in reading context, not to evidence review.

## 13. Follow-up after this PR

The next small follow-up should unlock true reading resume.

### Smallest clean options
1. add note slug/link data to the home paper payload
2. or join `PaperSummary` with note summary data on the frontend

Only after that should the home card gain:
- `Resume reading`
- `No project assigned`
- project context line
- artifact draft hint

## 14. Verification target

When implemented, verify with:
- `cd frontend && npm run build`

If a home/triage Playwright path already exists later, extend that coverage instead of inventing a large new test harness.

## 15. Recommendation summary

- implement the home resume card now
- keep the selector deterministic and frontend-only
- base it on `papers`, not `filteredPapers`
- support blocked and review states fully
- do not fake reading resume until note-link data exists
