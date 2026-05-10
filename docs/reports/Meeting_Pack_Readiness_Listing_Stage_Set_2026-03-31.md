# Meeting Pack Readiness / Listing Stage Set

Status: exact stage boundary
Date: 2026-03-31
Lane: `meeting-pack/readiness-listing`
Parent notes:
- [Meeting_Pack_Readiness_Viewer_Followup_Scoping_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Viewer_Followup_Scoping_2026-03-30.md)
- [Meeting_Pack_Readiness_Listing_Closure_Signoff_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Listing_Closure_Signoff_2026-03-30.md)

## Purpose

Freeze the smallest exact git-stage boundary for the remaining backend-side Meeting Pack readiness/listing lane.

This note does not stage or commit anything.
It answers one narrower question:

- if we close `Slice A` next, which files can be staged together without reopening viewer continuity or unrelated config churn?

## Diff Re-check Summary

The current remaining diffs were re-read directly for:

- [service.py](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py)
- [fixture_visibility.py](/Users/jangseongjin/paperpipe/src/services/fixture_visibility.py)
- [test_meeting_pack_service.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py)
- [test_meeting_packs_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py)
- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py)
- [meeting-pack.mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts)
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)

Current judgment:

- the backend truth owners for `Slice A` are now whole-file safe
- the viewer/browser continuity files remain clearly outside this slice
- the unrelated config rename in [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py) still does not belong to this lane

## Whole-File Safe For Slice A

These files can be staged as whole files for the readiness/listing follow-up:

- [service.py](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py)
- [fixture_visibility.py](/Users/jangseongjin/paperpipe/src/services/fixture_visibility.py)
- [test_meeting_pack_service.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py)
- [test_meeting_packs_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py)

Why these are safe together:

- they all belong to the same backend truth decision
- they are verified by the same focused pytest set
- none of the current remaining diffs in those files depend on viewer copy, browser-only continuity, or the unrelated config rename lane

### Companion Docs Safe To Include With This Slice

If this slice is committed, these notes can ride with it:

- [Meeting_Pack_Readiness_Viewer_Followup_Scoping_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Viewer_Followup_Scoping_2026-03-30.md)
- [Meeting_Pack_Readiness_Listing_Closure_Signoff_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Listing_Closure_Signoff_2026-03-30.md)
- [Meeting_Pack_Readiness_Listing_Stage_Set_2026-03-31.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Listing_Stage_Set_2026-03-31.md)

## Keep-Out Files

Do not include these in the same patch:

- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py)
- [meeting-pack.mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts)
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)

Why they stay out:

- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py) is still only the unrelated `trial_extraction` to `specialty_trial_extraction` config rename
- [meeting-pack.mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts) belongs to the later viewer continuity slice
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md) records user-facing Meeting Pack viewer work, not backend readiness truth

## Manual Stage Recipe

If this slice is staged next, the safe sequence is:

```bash
git add \
  /Users/jangseongjin/paperpipe/src/meeting_packs/service.py \
  /Users/jangseongjin/paperpipe/src/services/fixture_visibility.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Viewer_Followup_Scoping_2026-03-30.md \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Listing_Closure_Signoff_2026-03-30.md \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Listing_Stage_Set_2026-03-31.md
```

This lane does not currently require hunk-splitting.

## Smallest Relevant Verification Before Staging

Run:

```bash
python3 -m pytest \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py -q
```

Current result at re-check time:

- `51 passed`

Then run:

```bash
python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py
git diff --check
```

## Short Version

Unlike the earlier handoff-core lane, the remaining `Slice A` Meeting Pack readiness/listing work is now simple enough to stage as whole files.

The safe next closure boundary is:

- stage the four backend truth owners together
- optionally include the three readiness/listing notes
- keep out viewer continuity and the unrelated config rename
