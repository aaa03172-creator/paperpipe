# Branch Unification Plan - 2026-05-15

## Status

This document records the current `main` / `master` split and the safe path to a single default integration branch.

The immediate trigger was PR #380, which attempted to merge `codex/doi-identity-inventory` into `main` after the reviewed residual-hardening stack had landed into `codex/doi-identity-inventory`.

PR #380 was closed after conflict triage because direct integration into `main` would either:

- delete or omit the active FastAPI/backend/frontend/runtime tree, or
- require a broad branch reconstruction outside the scope of a feature PR.

## Observed Branch Roles

As of 2026-05-15:

| Ref | Observed role | Tracked files | Backend files | Notes |
| --- | --- | ---: | ---: | --- |
| `origin/main` | GitHub default branch, workflow-registration and legacy Python snapshot | 22 | 0 | README explicitly says this branch is not the current integration line. |
| `origin/master` | Active PaperPipe runtime integration line | 744 | 15 | Current open runtime PRs are targeting this branch. |
| `origin/codex/doi-identity-inventory` | Reviewed residual-hardening integration stack | 1850 | 20 | Contains merged PR #375 and #376. |

Open PRs observed during triage:

- PR #381 targets `master`: NotebookLM / Obsidian meeting-pack boundary.
- PR #382 targets `master`: chart-pack table provenance.
- PR #380 targeted `main` and is now closed.

## Confirmed Constraints

- Do not force-merge `codex/doi-identity-inventory` into `main` as a normal feature PR.
- Do not treat `main` and `master` as interchangeable until the repository default branch is explicitly unified.
- Do not delete or overwrite active runtime files as a side effect of resolving feature-branch conflicts.
- Keep the reviewed residual-hardening stack safe on `codex/doi-identity-inventory` until the target branch is selected.

## Recommendation

Use `master` as the active runtime source of truth for the unification operation, then make the repository default branch point at the active runtime line.

Preferred path:

1. Freeze new feature PRs to `main`.
2. Finish or explicitly park open `master` PRs that are already in flight.
3. Create a backup marker for the current default branch state:
   - tag or branch: `backup/main-legacy-snapshot-20260515`
   - source: current `origin/main`
4. Create a backup marker for the active runtime line before default-branch change:
   - tag or branch: `backup/master-runtime-before-default-switch-20260515`
   - source: current `origin/master`
5. Re-land the reviewed residual-hardening stack against the chosen active runtime branch if it is still needed there:
   - DOI identity inventory audit
   - pipeline residual hardening
   - backend smoke readiness fixture hardening
6. Run the active runtime smoke checks on the selected branch:
   - backend API smoke when the active tree contains `scripts/run_backend_api_smoke.sh`
   - frontend build and existing frontend smoke only when the active tree includes `frontend/`
7. Change the GitHub default branch only after the selected branch has the intended runtime tree and passing checks.
8. After the default branch is changed, update docs and PR templates to stop referring to the old split.

## Non-Goals

- This plan does not merge PR #380.
- This plan does not rewrite `main` or `master`.
- This plan does not delete backup branches, worktrees, snapshots, or legacy runtime files.
- This plan does not decide the final branch name by itself; it defines the gate sequence before that decision is executed.

## Acceptance Criteria

The branch split is considered resolved only when all of the following are true:

- The GitHub default branch contains the active PaperPipe runtime tree.
- New feature PRs target the same branch used by runtime CI.
- `README.md` no longer describes `main` as a non-integration snapshot.
- Open PRs are not split between incompatible base branches without an explicit stacked-lane reason.
- A backup ref exists for the pre-unification `main` state.
- A backup ref exists for the pre-unification active runtime state.

## Rollback

If the unification causes CI, workflow-dispatch, or release disruption:

1. Restore the GitHub default branch setting to the previous default.
2. Use the backup refs above to recover the pre-change branch tips.
3. Reopen the branch-unification issue with the failing check or workflow as the blocker.
