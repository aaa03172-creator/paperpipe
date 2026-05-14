# CLI Runtime Hygiene Stage Set

Status: exact patch-stage boundary
Date: 2026-04-10
Lane: `cli/runtime-hygiene`
Parent notes:
- [Project_Memory_Raw_Memory_Boundary_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Project_Memory_Raw_Memory_Boundary_Stage_Set_2026-04-10.md)
- [DeepRead_State_Projection_Clinical_Handoff_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_State_Projection_Clinical_Handoff_Stage_Set_2026-04-10.md)

## Purpose

Freeze the remaining CLI operator-hygiene follow-up around missing watcher dependencies, hidden fixture structured states, and runtime log-path handling.

This note does not stage or commit anything.
It answers one narrower question:

- which remaining `src/cli.py` hunks form one safe patch-stage lane?

## Diff Re-check Summary

Current re-read result:

- `src/cli.py` still contains multiple unrelated tails
- one coherent subset improves operator hygiene without changing core pipeline logic
- the subset adds watchdog dependency guards, fixture quarantine tooling, doctor visibility, and stable runtime log paths
- existing CLI watch-command tests already target this behavior

Current judgment:

- this is one bounded patch-stage lane
- it is operator-facing and additive
- it should not be staged as the whole file from the current dirty tree

## Files In Scope

These files belong to this lane:

- [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- [CLI_Runtime_Hygiene_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/CLI_Runtime_Hygiene_Stage_Set_2026-04-10.md)

Only the note is whole-file safe.
`cli.py` requires hunk-splitting.

## What Belongs In This Lane

Keep from [cli.py](/Users/jangseongjin/paperpipe/src/cli.py):

- `importlib.util` import
- `logs_root` import
- `collect_structured_state_hygiene_check` import
- `quarantine_hidden_fixture_structured_states` import
- `_optional_dependency_installed(...)`
- `_ensure_watchdog_available(...)`
- `doctor()` additions for:
  - Zotero and vault existence status
  - watchdog availability
  - structured state hygiene
  - readiness-dependent closing status message
- `quarantine-fixture-states` command
- `clear_logs()` using `logs_root()`
- `reset()` using `logs_root()`
- `watch()` watchdog preflight
- `watch_downloads()` watchdog preflight

## Out Of Scope

Do not include these in the same stage set:

- `paper-synthesis-generate`, `paper-synthesis-show`, and `paper-synthesis-list`
- `_print_results()` `clinical_data` display tweaks
- `repair_stats()` help-text wording change
- any remaining `Research DNA` or other CLI tails

Why these stay out:

- they belong to separate product or operator lanes
- mixing them would broaden the commit past the watch/hygiene boundary

## Architecture Check

Why this split is safe:

- it does not change canonical runtime ownership
- it keeps CLI operator tooling aligned with runtime hygiene checks already present elsewhere
- it fails fast when optional watcher dependencies are missing instead of crashing later
- it provides a bounded cleanup path for hidden fixture structured states

## Verification Re-check

Run these commands for this lane:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q tests/test_cli_watch_commands.py
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
```

## Manual Stage Recipe

If this lane is staged next, patch-stage only:

```bash
git add -p /Users/jangseongjin/paperpipe/src/cli.py
git add /Users/jangseongjin/paperpipe/docs/reports/CLI_Runtime_Hygiene_Stage_Set_2026-04-10.md
```

Accept only the hunks listed in `What Belongs In This Lane`.

## Short Version

The remaining safe CLI tail is a runtime-hygiene patch lane:

- guard `watch` and `watch-downloads` when `watchdog` is missing
- surface watchdog and hidden fixture hygiene in `doctor`
- add `quarantine-fixture-states`
- normalize log cleanup paths through `logs_root()`
