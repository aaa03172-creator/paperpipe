# Paper Synthesis CLI Stage Set

Status: exact patch-stage boundary
Date: 2026-04-10
Lane: `cli/paper-synthesis`
Parent notes:
- [DeepRead_State_Projection_Clinical_Handoff_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_State_Projection_Clinical_Handoff_Stage_Set_2026-04-10.md)
- [CLI_Runtime_Hygiene_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/CLI_Runtime_Hygiene_Stage_Set_2026-04-10.md)

## Purpose

Freeze the remaining CLI follow-up that exposes paper-synthesis generate/show/list commands on top of the already-committed paper-synthesis service and storage layers.

This note does not stage or commit anything.
It answers one narrower question:

- which remaining `src/cli.py` hunks form one safe patch-stage lane for paper synthesis?

## Diff Re-check Summary

Current re-read result:

- the remaining `src/cli.py` diff is small
- one coherent subset adds three paper-synthesis commands
- existing CLI tests already exercise those commands end to end

Current judgment:

- this is one bounded patch-stage lane
- it is additive and operator-facing
- it should not be mixed with the unrelated `clinical_data` print tweak or repair-stats copy edit

## Files In Scope

These files belong to this lane:

- [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- [Paper_Synthesis_CLI_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Paper_Synthesis_CLI_Stage_Set_2026-04-10.md)

Only the note is whole-file safe.
`cli.py` requires hunk-splitting.

## What Belongs In This Lane

Keep from [cli.py](/Users/jangseongjin/paperpipe/src/cli.py):

- `paper-synthesis-generate`
- `paper-synthesis-show`
- `paper-synthesis-list`

## Out Of Scope

Do not include these in the same stage set:

- `_print_results()` `clinical_data` display tweaks
- `repair_stats()` help-text wording change
- any remaining `backend/main.py` tails

Why these stay out:

- they belong to separate lanes
- they do not materially affect the paper-synthesis CLI surface

## Architecture Check

Why this split is safe:

- it builds on the already-present paper-synthesis service and store
- it does not change canonical truth ownership
- it provides a bounded CLI operator surface for compiled paper-synthesis artifacts

## Verification Re-check

Run these commands for this lane:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q tests/test_paper_synthesis_cli.py
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
```

## Manual Stage Recipe

If this lane is staged next, patch-stage only:

```bash
git add -p /Users/jangseongjin/paperpipe/src/cli.py
git add /Users/jangseongjin/paperpipe/docs/reports/Paper_Synthesis_CLI_Stage_Set_2026-04-10.md
```

Accept only the hunks listed in `What Belongs In This Lane`.

## Short Version

The remaining safe `cli.py` tail is a small paper-synthesis lane:

- generate a paper-synthesis bundle
- load an existing bundle
- list saved bundles
