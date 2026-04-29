# Windows Personal Runtime Alpha

Status: Active
Date: 2026-03-28
Owner: Lattice runtime maintainers
Purpose: define the honest Windows status and cautious alpha path for the personal-runtime shape without overstating packaged support.

Canonical parents:
- `docs/PERSONAL_RUNTIME_INSTALL.md`
- `docs/reports/Personal_Runtime_Packaging_Decision_2026-03-28.md`

## Scope

Use this when:

- you want to explain what the repo currently supports on Windows
- you want a cautious Windows alpha path for a technically comfortable operator
- you need a single reference that separates repo-proven behavior from future packaging goals

Do not use this as if it were:

- a claim of a finished Windows installer
- proof of a repo-proven packaged `.exe`
- a promise of frictionless non-technical onboarding

## Current honest status

Today the repo does support these Windows-aligned facts:

- personal runtime roots can resolve under `%APPDATA%\\Lattice`
- install-layout mode can move `config`, `storage`, `logs`, and `cache` out of the repo checkout
- the primary launcher path is Python-based, not shell-script-only
- the backend still serves the built `/ui` bundle in the same runtime shape as macOS/Linux
- repo tests already guard the Windows app-data path logic

Today the repo does not yet prove these Windows claims:

- a packaged Windows `.exe` build
- a Windows installer or signed distribution artifact
- a repo-recorded end-to-end smoke on a real Windows machine
- a SmartScreen-friendly trust-distribution path

The safest current product language is:

- `Windows-later`
- `from-source alpha only`
- `not yet officially packaged/supported`

## What is already repo-proven

The repo currently has direct guardrails for Windows runtime roots:

- `tests/test_runtime_paths_windows.py` verifies `%APPDATA%\\Lattice` resolution
- install-layout mode resolves Windows `config`, `storage`, `logs`, and `cache` roots under that same base path

The repo also already relies on runtime behavior that is not macOS-only:

- `src.cli` starts the backend through Python entrypoints
- `backend/main.py` serves the built frontend bundle at `/ui`
- `src/services/runtime_paths.py` centralizes platform path differences instead of spreading Windows branches through the codebase

That means the core runtime shape is not blocked on Windows. The missing proof is packaging and real-host smoke, not the basic product architecture.

## Repo-provided smoke entry

The repo now provides a Windows-host smoke entry at:

- `scripts/check_windows_personal_runtime_smoke.py`

Recommended first use on a real Windows machine:

```powershell
py -3 scripts/check_windows_personal_runtime_smoke.py --mode source
```

What it does:

- ensures install-layout mode is on
- creates `%APPDATA%\\Lattice\\config\\config.yaml` from `config.example.yaml` if it does not already exist
- runs `self-test --json`
- starts the local runtime without opening the browser
- checks both `/health` and `/ui`
- prints a JSON summary of the result

There is also an experimental packaged attempt:

```powershell
py -3 scripts/check_windows_personal_runtime_smoke.py --mode packaged --build-packaged --clean
```

Treat the packaged mode as a proving tool, not as public-support evidence, until it has been run successfully on a real Windows host.

## Current recommended Windows alpha path

Use this only for a technically comfortable operator.

### 1. Prerequisites

You currently need:

- a local checkout of this repo
- Python 3.13+
- Node.js and npm
- PowerShell or another Windows-native shell

Do not treat the maintainer `scripts/*.sh` files as the Windows operator contract.

### 2. Install and build from source

From PowerShell at the repo root:

```powershell
git submodule update --init --recursive
py -3 -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
```

### 3. Create the personal config

```powershell
$configDir = Join-Path $env:APPDATA "Lattice\\config"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
Copy-Item .\\config.example.yaml (Join-Path $configDir "config.yaml")
```

Then edit:

- `paths.obsidian_vault`
- `paths.zotero_base_dir`

If you leave placeholder values for a first launch check, `self-test` can still run but will likely report `warn` or `degraded`.

### 4. Enable install-layout mode

```powershell
$env:PAPERPIPE_INSTALL_LAYOUT="1"
```

This keeps app-owned state under the user-scoped app-data root instead of mixing it into the repo checkout.

### 5. Run self-test first

```powershell
py -3 -m src.cli self-test --json
```

What a reasonable alpha result looks like:

- `config_file`, `runtime_db`, `storage_root`, `logs_root`, `cache_root`: `ok`
- `ui_bundle`: `ok` if `frontend/dist` exists
- `obsidian_vault` and `zotero_base_dir`: `warn` is acceptable if you have not configured real external paths yet

### 6. Start the runtime

```powershell
py -3 -m src.cli start --no-open
```

Expected runtime shape:

- config preflight runs first
- runtime DB bootstraps
- backend starts locally
- `/health` and `/ui` should be available from the same local server

Using the direct Python entry is the safest current Windows instruction because it does not depend on shell alias or packaged-launcher assumptions.

## What not to promise yet

Do not currently promise:

- a double-click installer
- a packaged `Lattice.exe`
- Windows code-signing or SmartScreen trust
- parity with the current macOS alpha handoff flow

Those are follow-up milestones, not current repo truth.

## Exit criteria for a real Windows alpha handoff

Upgrade Windows from `from-source alpha` to `packaged alpha` only after all of these happen on a real Windows host:

1. Build a packaged launcher artifact on Windows.
2. Run `self-test --json` from that packaged path.
3. Start the runtime and confirm `/health` and `/ui` both respond successfully.
4. Prove the app-owned roots land in a user-scoped Windows app-data location.
5. Record the exact handoff steps in a Windows-specific operator note.

Only after that should the repo describe Windows as a packaged alpha target.

## One-line recommendation

Keep Windows in a cautious `from-source personal-runtime alpha` state for now, and defer any packaged-support claim until a real Windows packaged smoke pass exists.
