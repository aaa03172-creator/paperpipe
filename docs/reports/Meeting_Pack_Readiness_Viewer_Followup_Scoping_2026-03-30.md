# Meeting Pack Readiness / Viewer Follow-up Scoping

Status: follow-up lane scoping
Date: 2026-03-30
Lane: `meeting-pack/readiness-viewer-followup`
Parent notes:
- [Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md)
- [Meeting_Pack_Handoff_Stage_Set_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Stage_Set_2026-03-30.md)

## Purpose

Define the next safe Meeting Pack slice after the handoff-core commit.

This note answers one narrow question:

- which remaining Meeting Pack-adjacent changes still belong together, and what is the smallest next slice if work continues?

## Current Judgment

After the handoff-core commit, the remaining Meeting Pack work is no longer one coherent patch.

It now splits into two different follow-up slices:

1. readiness and listing semantics
2. viewer continuity and first-session create flow

Those slices touch adjacent files, but they do not need to ship together.

## Slice A: Readiness / Listing Semantics

Primary owners:

- [service.py](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py)
- [fixture_visibility.py](/Users/jangseongjin/paperpipe/src/services/fixture_visibility.py)
- [test_meeting_pack_service.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py)
- [test_meeting_packs_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py)

What it contains:

- fixture filtering in saved-pack listing
- readiness semantics moving from “claim rows exist” toward “direct support exists”
- grounding-metadata uncertainty wording for evidence-linked claims
- API/listing coverage for the new listing/readiness behavior

Why it is coherent:

- it is a backend/runtime truth slice
- it changes how Meeting Pack readiness and visibility are interpreted
- it has concentrated runtime and pytest owners

What stays out of this slice:

- viewer copy changes
- browser continuity assertions
- first-draft create-flow UX

## Slice B: Viewer Continuity / First-Session Flow

Primary owners:

- [meeting-pack.mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts)
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)

Likely adjacent owners if reopened:

- [MeetingPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx)
- [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts)

What it contains:

- header context strip framing
- `Start a new draft` entry framing
- continue-in-note continuity messaging
- browser verification that create -> detail -> continue flow still reads clearly

Why it should stay separate:

- this is a user-facing framing and flow slice
- it should follow the product-psychology review path, not ride along with backend truth changes
- it is easy to widen accidentally into a broader Meeting Pack viewer redesign

## Explicit Keep-Out Item

- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py)

Current diff there is still just the unrelated config rename to `specialty_trial_extraction`.
That file should not decide the next Meeting Pack slice.

## Recommended Next Slice

If work continues now, the safest next slice is `Slice A: Readiness / Listing Semantics`.

Why:

- it is the remaining backend truth lane
- it has the clearest ownership boundary
- it can be verified with pytest first
- it avoids reopening UX scope before the runtime semantics settle

## Smallest Relevant Verification For Slice A

Start with:

```bash
python3 -m pytest \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py -q
```

If `fixture_visibility.py` becomes the explicit owner for listing behavior, add:

```bash
python3 -m pytest \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py -q
```

Only after Slice A settles should the viewer/browser follow-up reopen.

## Short Version

The handoff-core lane is closed enough to move on.

The next safe Meeting Pack work is not “all remaining meeting-pack files.”

It is:

1. first, backend readiness/listing semantics
2. later, viewer continuity and first-session create flow
