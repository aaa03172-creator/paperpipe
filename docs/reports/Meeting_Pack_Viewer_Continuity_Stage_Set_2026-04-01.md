# Meeting Pack Viewer Continuity Stage Set

Status: exact stage boundary
Date: 2026-04-01
Lane: `meeting-pack/viewer-continuity`
Parent notes:
- [Meeting_Pack_Readiness_Viewer_Followup_Scoping_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Viewer_Followup_Scoping_2026-03-30.md)
- [Meeting_Pack_Viewer_Continuity_Closure_Signoff_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Viewer_Continuity_Closure_Signoff_2026-04-01.md)

## Purpose

Freeze the smallest exact git-stage boundary for the remaining Meeting Pack viewer continuity lane.

This note does not stage or commit anything.
It answers one narrower question:

- if we close the Meeting Pack viewer continuity lane next, which files are whole-file safe and which ones need hunk-splitting?

## Diff Re-check Summary

The current remaining diffs were re-read directly for:

- [MeetingPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx)
- [meeting-pack.mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts)
- [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts)
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)
- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py)

Current judgment:

- the Meeting Pack page and mock spec are whole-file safe for this lane
- the UX review report is whole-file safe for this lane
- the real backend Meeting Pack browser journey inside [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts) is coherent, but the file is mixed with unrelated artifact-viewer additions and must be hunk-split
- the unrelated config rename in [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py) still stays out

## Whole-File Safe For This Lane

These files can be staged as whole files for Meeting Pack viewer continuity:

- [MeetingPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx)
- [meeting-pack.mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts)
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)
- [Meeting_Pack_Viewer_Continuity_Closure_Signoff_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Viewer_Continuity_Closure_Signoff_2026-04-01.md)
- [Meeting_Pack_Viewer_Continuity_Stage_Set_2026-04-01.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Viewer_Continuity_Stage_Set_2026-04-01.md)

Why these are safe together:

- they all serve the same create/review/continue Meeting Pack journey
- they are covered by the same UX review framing
- none of them currently carry non-Meeting-Pack artifact work

## Split-Required File

- [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts)

Only the Meeting Pack journey support hunks belong in this lane:

- the local `boxesOverlap(...)` / `expectNoUiOverlap(...)` helper addition
- `test("backend meeting pack create keeps the continuation card and note handoff on the real route", ...)`

Why it must be split:

- the same file currently contains unrelated method-comparison, chart-pack, protocol-card, and image-evidence browser additions
- whole-file staging would widen this patch past the intended Meeting Pack boundary

## Keep-Out Files

Do not include these in the same patch:

- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py)
- unrelated non-Meeting-Pack hunks in [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts)
- any already-committed readiness/listing backend truth files from `a666514`

Why they stay out:

- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py) is still only the unrelated `trial_extraction` to `specialty_trial_extraction` config rename
- unrelated browser hunks in [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts) belong to other artifact lanes
- reopening the readiness/listing files would mix backend truth and viewer continuity again

## Manual Stage Recipe

If this lane is staged next, the safe sequence is:

```bash
git add \
  /Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx \
  /Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts \
  /Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Viewer_Continuity_Closure_Signoff_2026-04-01.md \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Viewer_Continuity_Stage_Set_2026-04-01.md
git add -p /Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts
```

When hunk-staging [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts), include only:

- the Meeting Pack-specific overlap helper hunk
- the Meeting Pack create/continue journey test

Leave every other artifact test addition unstaged.

## Smallest Relevant Verification Before Staging

Run:

```bash
cd /Users/jangseongjin/paperpipe/frontend && npm run build
cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts
cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"
```

Current result at re-check time:

- build passed
- mock Meeting Pack spec passed: `2 passed`
- backend Meeting Pack journey passed: `1 passed`

Then run:

```bash
python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py
git diff --check
```

## Short Version

The Meeting Pack viewer continuity lane is stageable next, but not as a whole-file browser patch.

The safe boundary is:

- whole-file stage the Meeting Pack page, Meeting Pack mock spec, and viewer docs
- hunk-stage only the single Meeting Pack journey test from [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts)
- keep unrelated browser journeys and the config rename out
