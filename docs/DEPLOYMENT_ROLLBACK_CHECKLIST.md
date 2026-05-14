# Deployment And Rollback Checklist

Status: Active
Date: 2026-04-26
Owner: Operations maintainers
Canonical runbook: `docs/DEPLOYMENT_ROLLBACK_CHECKLIST.md`
Canonical parent: `docs/OPERATIONS_RUNBOOK.md`

## Purpose

Use this checklist before sharing, updating, or rolling back a personal-runtime PaperPipe/Lattice instance.

This document is intentionally an operations checklist. It does not replace the install, user-kit, macOS release, or Windows alpha runbooks.

## Current Deployment Shape

Current deployment posture is personal-runtime first:

- repo-based local alpha install is the safest general path
- macOS alpha handoff exists for trusted testers
- macOS Gatekeeper-ready release requires the signing/notarization path
- Windows is currently from-source alpha unless a real Windows packaged smoke has passed
- no shared multi-tenant production deployment is the default operating target

## Canonical References

- `docs/PERSONAL_RUNTIME_INSTALL.md`
- `docs/PERSONAL_RUNTIME_USER_KITS.md`
- `docs/MACOS_PERSONAL_RUNTIME_ALPHA_HANDOFF.md`
- `docs/MACOS_PERSONAL_RUNTIME_RELEASE.md`
- `docs/WINDOWS_PERSONAL_RUNTIME_ALPHA.md`
- `docs/runtime_security_env.md`
- `docs/RESTORE_READINESS_MATRIX.md`
- `docs/MUTATION_SCRIPT_SAFETY_INVENTORY.md`

## Pre-Update Checklist

Before changing a runtime or sending a new artifact:

1. Record the current source revision or package artifact name.
2. Preserve the previous package, zip, app bundle, or source checkout until the new runtime passes smoke checks.
3. Confirm where runtime state lives:
   - repo checkout storage/logs for development
   - install-layout app data roots for personal runtime
4. Do not mix dev-checkout state with tester app-owned state unless the operator intentionally chose that path.
5. Run a current readiness check:

```bash
.venv314/bin/python scripts/check_ops_readiness.py --json
```

6. If this is a packaged/personal-runtime handoff, run the relevant self-test:

```bash
lattice self-test --json
```

or, for a built macOS app:

```bash
./dist/Lattice.app/Contents/MacOS/Lattice self-test --json
```

7. If DB maintenance was part of the release/update, confirm the mutation script printed a backup path and drill the backup:

```bash
.venv314/bin/python scripts/check_sqlite_restore_drill.py --backup storage/backups/<backup>.db
```

8. If Obsidian note filename migration is part of the update, confirm a trusted vault backup exists before using `--apply --confirm-vault-backup`.

## Rollout Checklist

For a repo-based personal runtime:

1. Update the checkout using normal git workflow.
2. Reinstall dependencies only when requirements changed.
3. Rebuild the frontend when `frontend/` changed:

```bash
cd frontend
npm install
npm run build
cd ..
```

4. Run `lattice self-test --json`.
5. Start with `lattice start` or `python3 -m src.cli start`.

For macOS alpha handoff:

1. Build or reuse the current bundle according to `docs/MACOS_PERSONAL_RUNTIME_ALPHA_HANDOFF.md`.
2. Run the local proof wrapper when possible:

```bash
bash ./scripts/run_macos_personal_runtime_local_proof.sh
```

3. Send the app zip, config template, and handoff note together.

For macOS Gatekeeper-ready release:

1. Run the prerequisite check first:

```bash
bash ./scripts/run_macos_personal_runtime_gatekeeper_prereqs.sh
```

2. Use `docs/MACOS_PERSONAL_RUNTIME_RELEASE.md` for signing, notarization, stapling, and final zip generation.
3. Do not call the artifact Gatekeeper-ready until `spctl --assess --type execute dist/Lattice.app` passes.

For Windows:

1. Treat the current path as from-source alpha.
2. Run the Windows smoke on a real Windows host:

```powershell
py -3 scripts/check_windows_personal_runtime_smoke.py --mode source
```

3. Do not describe Windows as packaged alpha until the packaged smoke path has passed on a real Windows host.

## Post-Update Checks

After updating:

1. Confirm `/health` responds.
2. Confirm `/health/ready` or `scripts/check_ops_readiness.py` reflects the expected status.
3. Confirm `/ui` loads for the intended runtime shape.
4. Confirm configured external roots are still what the operator expects.
5. Confirm the latest monitor files can be written when local scheduling is used:

```bash
.venv314/bin/python scripts/run_ops_readiness_monitor.py --skip-downloader
```

6. Keep the old artifact/checkpoint until the operator has completed at least one representative workflow.

## Rollback Matrix

Rollback should target the layer that changed.

| Changed layer | First rollback move | What not to do |
| --- | --- | --- |
| Runtime env/config | Restore previous env vars or config file; rerun self-test. | Do not patch runtime DB to compensate for config mistakes. |
| Source checkout | Return to the previous branch/revision with normal git workflow. | Do not reset unrelated dirty work. |
| Packaged artifact | Reopen/redeploy the previous known-good app/zip. | Do not overwrite app-owned state with bundled sample state. |
| SQLite mutation | Restore only from the intended script-created backup after drill/check. | Do not hand-edit `storage/state.db` rows. |
| Generated bundle artifact | Prefer rerender/regenerate when the matrix says rerenderable. | Do not byte-restore partial bundles unless all required files are consistent. |
| Raw source file/PDF/attachment | Restore original bytes from trusted backup. | Do not regenerate raw sources from derived artifacts. |
| Browser/security gate | Revert env flags such as beta password, allowed hosts, allowed IPs, or rate-limit settings. | Do not expose backend secrets through `VITE_*` variables. |

## Stop Conditions

Pause rollout and keep the old artifact/runtime when:

- self-test reports `error`
- `/health` fails
- `/ui` does not load in the intended package
- the DB backup drill fails after a mutation
- configured storage/log/cache roots unexpectedly point into the wrong user or checkout
- Windows or Gatekeeper claims are not backed by their required host checks

## Operator Note Template

Record the minimum handoff note:

```text
date:
operator:
source revision or artifact:
runtime shape: repo alpha | macOS alpha handoff | macOS Gatekeeper-ready | Windows source alpha
state root:
pre-checks:
post-checks:
rollback artifact/path:
known warnings:
decision: proceed | hold | rollback
```
