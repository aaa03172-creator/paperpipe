# Personal Runtime User Kits

Status: Active
Date: 2026-03-28
Owner: Lattice runtime maintainers
Purpose: describe the current user-facing handoff folders for macOS and Windows personal-runtime alpha delivery.

Canonical parents:
- `docs/PERSONAL_RUNTIME_INSTALL.md`
- `docs/MACOS_PERSONAL_RUNTIME_ALPHA_HANDOFF.md`
- `docs/WINDOWS_PERSONAL_RUNTIME_ALPHA.md`

## Scope

Use this runbook when you want to create user-facing folders that already contain:

- a product guide
- an install guide
- cautions and current limits
- a feedback note template
- the current OS-specific runtime payload

Do not use this runbook as if it created:

- a notarized public macOS release
- a packaged Windows installer
- a general self-serve consumer distribution channel

## Current generator

The current generator is:

- `scripts/build_personal_runtime_user_kits.py`

Run it from the repo root:

```bash
python3 scripts/build_personal_runtime_user_kits.py
```

## Current outputs

The generator writes into:

- `dist/release/user-kits/`

Current kit shapes:

- `Lattice-macos-alpha-kit`
- `Lattice-windows-source-alpha-kit`

It also writes matching zip archives for both folders.

## macOS kit

The macOS kit currently bundles:

- the current macOS alpha app zip from `dist/release/`
- the config template
- the current release manifest
- the current alpha handoff note
- user-facing `Start Here`, `Product Guide`, `Install Guide`, `Cautions`, and `Feedback Note`

Honest status:

- working alpha handoff
- not yet Gatekeeper-ready unless the separate signing/notarization path has been completed

## Windows kit

The Windows kit currently bundles:

- a source snapshot under `app/`
- PowerShell helpers for install-and-smoke and normal start
- user-facing `Start Here`, `Product Guide`, `Install Guide`, `Cautions`, and `Feedback Note`

Honest status:

- from-source alpha
- not yet a packaged `.exe` installer

## Recommended use

- send the macOS kit to trusted macOS alpha testers
- send the Windows kit only to technically comfortable testers who can run PowerShell and Python
- collect the first feedback directly in `04_FEEDBACK_NOTE.md`

## Verification bar

Before treating the generated folders as handoff-ready, confirm:

- the generator script completed successfully
- the macOS kit includes the current app zip and config template
- the Windows kit includes `app/scripts/check_windows_personal_runtime_smoke.py`
- the copied Windows snapshot can run the smoke entry on a real Windows host
