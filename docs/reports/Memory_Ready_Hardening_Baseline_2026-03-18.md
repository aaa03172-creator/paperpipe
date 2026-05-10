# Memory-Ready Hardening Baseline

Status: Ready-to-freeze baseline slice  
Date: 2026-03-18  
Owner: Repository maintainers  
Canonical parents:
- `/Users/jangseongjin/paperpipe/docs/Audit_Driven_Roadmap_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Current_Baseline_Recheck_2026-03-18.md`

## 0. Purpose

Define the narrow hardening slice that is now green and should be treated as the current execution baseline for the memory-ready/runtime-reliability lane.

This note is not a new roadmap.

It exists to stop the next PR from dissolving back into the full dirty workspace.

## 1. What This Baseline Slice Covers

This slice covers the already-implemented hardening needed to make later memory, recall, and operator-visible evidence work feasible without reopening architecture search.

Included capability groups:

1. stable runtime identity and artifact path helpers
2. deterministic chunk ids in the active indexing path
3. additive execution event logging
4. `user_actions` write/read/timeline integration
5. output-bridge and citation-grounding hardening
6. reader-side evidence grounding improvements
7. timeline UI visibility for real backend `user_action` events
8. client-only gesture logging for meaningful frontend navigation intent
9. evidence-review gesture logging for claim and stats jumps

## 2. Included Runtime Areas

### 2.1 Identity and artifact pathing

Primary files:

- `/Users/jangseongjin/paperpipe/src/services/identity.py`
- `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`
- `/Users/jangseongjin/paperpipe/src/services/paper_ops_summary.py`
- `/Users/jangseongjin/paperpipe/src/services/stats_repair.py`

Intent:

- centralize runtime `paper_id` / `run_id` helpers
- keep legacy artifact directories readable
- allow safe artifact segments for unsafe `paper_id` values

### 2.2 Deterministic chunk ids and reader grounding

Primary files:

- `/Users/jangseongjin/paperpipe/src/agents/indexer_agent.py`
- `/Users/jangseongjin/paperpipe/src/agents/reader_agent.py`
- `/Users/jangseongjin/paperpipe/src/contracts/artifact_views.py`
- `/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py`
- `/Users/jangseongjin/paperpipe/src/services/citation_grounding.py`
- `/Users/jangseongjin/paperpipe/src/quality/teacher_review.py`

Intent:

- replace active `uuid4()` chunk ids with deterministic ids
- resolve evidence against real chunk/page context
- preserve `grounded` / `resolution` semantics through runtime output

### 2.3 Execution events and user actions

Primary files:

- `/Users/jangseongjin/paperpipe/src/services/event_log.py`
- `/Users/jangseongjin/paperpipe/src/db_utils.py`
- `/Users/jangseongjin/paperpipe/src/db.py`
- `/Users/jangseongjin/paperpipe/src/jobs/queue.py`
- `/Users/jangseongjin/paperpipe/src/jobs/worker.py`
- `/Users/jangseongjin/paperpipe/src/jobs/schemas.py`
- `/Users/jangseongjin/paperpipe/backend/main.py`
- `/Users/jangseongjin/paperpipe/backend/routers/obsidian.py`
- `/Users/jangseongjin/paperpipe/src/skills/runner.py`

Intent:

- keep `jobs` table behavior intact
- add `execution_runs`, `job_events`, and `user_actions` additively
- expose `/user-actions`
- include matching `user_actions` inside `/runs/{run_id}/timeline`

### 2.4 Output bridge and consumer surfaces

Primary files:

- `/Users/jangseongjin/paperpipe/src/contracts/output_bridge.py`
- `/Users/jangseongjin/paperpipe/src/schemas/skills.py`
- `/Users/jangseongjin/paperpipe/src/schemas/ops.py`
- `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`
- `/Users/jangseongjin/paperpipe/src/exporter.py`

Intent:

- preserve resolved claim grounding through bridge layers
- ensure `claimset.resolved.json` is produced and preferred where appropriate

### 2.5 Timeline user-action UI surface

Primary files:

- `/Users/jangseongjin/paperpipe/frontend/src/app/components/TimelinePanel.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/types.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/mock.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/mock.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_e2e.sh`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_TEMPLATE.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_paper-notes-viewer.md`

Intent:

- show `user_action` distinctly in the workbench timeline
- protect both mock and real backend timeline rendering

### 2.6 Client-only gesture logging

Primary files:

- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/api.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `/Users/jangseongjin/paperpipe/backend/main.py`
- `/Users/jangseongjin/paperpipe/src/schemas/ops.py`
- `/Users/jangseongjin/paperpipe/src/services/event_log.py`

Intent:

- persist meaningful client-only navigation intent without blocking UI flows
- keep logging best-effort and append-only
- ensure `user_actions` captures both server-triggered work and direct viewer/workbench intent

### 2.7 Evidence-review gesture logging

Primary files:

- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ArtifactPanel.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx`
- `/Users/jangseongjin/paperpipe/backend/main.py`
- `/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts`

Intent:

- capture claim selection and mirror/stats jump intent as `user_actions`
- attach `run_id` so those actions can join the run timeline on reload
- keep the gesture surface bounded to evidence review, not every incidental click

## 3. Explicitly Out Of This Baseline Slice

These areas must stay outside this freeze, even though they may also be modified in the workspace:

1. broad Meeting Pack product expansion beyond its already-established baseline lane
2. broader Research DNA semantic/product changes
3. method-comparison follow-up work
4. frontend page/layout churn unrelated to timeline/user-action visibility
5. broad docs/archive cleanup
6. speculative memory-platform or framework migration work

Reason:

The point of this slice is to freeze the already-verified hardening path, not to absorb the whole repository.

## 4. Verification For This Slice

Confirmed on 2026-03-18:

### Full Python baseline

```bash
pytest -q
```

Result:

- `645 passed, 1 skipped`

### Frontend build

```bash
cd /Users/jangseongjin/paperpipe/frontend
npm run build
```

Result:

- success

### Mock timeline and grounding UI coverage

```bash
cd /Users/jangseongjin/paperpipe/frontend
npx playwright test -c /Users/jangseongjin/paperpipe/frontend/playwright.mock.config.ts /Users/jangseongjin/paperpipe/frontend/e2e/mock.spec.ts -g "timeline surfaces user-triggered actions distinctly|mirror grounding badges surface resolved and review-needed evidence states"
```

Result:

- `2 passed`

### Real backend timeline user-action coverage

```bash
cd /Users/jangseongjin/paperpipe/frontend
npx playwright test -c /Users/jangseongjin/paperpipe/frontend/playwright.backend.config.ts /Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts -g "backend timeline surfaces user-triggered actions distinctly"
```

Result:

- `1 passed`

### Real backend evidence-review gesture logging

```bash
cd /Users/jangseongjin/paperpipe/frontend
npx playwright test -c /Users/jangseongjin/paperpipe/frontend/playwright.backend.config.ts /Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts -g "backend evidence review gestures append user actions|backend stats snapshot disambiguates claim target by text signal|backend timeline surfaces user-triggered actions distinctly"
```

Result:

- `3 passed`

### Docs lint

```bash
python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py
```

Result:

- `docs lint passed`

## 5. Acceptance Criteria

This hardening slice should be treated as frozen only if all are true:

1. the runtime/helper/event/grounding/timeline files listed above are treated as one bounded lane
2. full Python tests remain green
3. frontend build remains green
4. both mock and backend timeline user-action Playwright checks remain green
5. no unrelated product-expansion files are pulled into the same change summary by accident

## 6. Recommended Next Step After Freeze

After this baseline is treated as frozen, there is no mandatory immediate follow-up inside this lane.

Optional next lane:

1. extend `user_actions` beyond navigation and evidence-review into explicit reviewer intent (`remember`, `important`, future pin/bookmark surfaces)

Still not recommended immediately after freeze:

1. reopening artifact contract redesign
2. widening timeline UI into a larger operator dashboard
3. using the baseline freeze as cover for unrelated frontend cleanup
