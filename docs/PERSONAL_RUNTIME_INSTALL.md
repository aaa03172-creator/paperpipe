# Personal Runtime Install And Start Guide

Status: Active  
Date: 2026-03-28  
Owner: Lattice runtime maintainers  
Canonical runbook: `docs/PERSONAL_RUNTIME_INSTALL.md`  
Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md`
- `docs/reports/Personal_Runtime_MVP_Checklist_2026-03-28.md`

## Purpose

This runbook explains the current close-person alpha path for running Lattice as a personal runtime.

Use this when the goal is:
- one operator
- one isolated runtime
- one user-owned config/state/artifact boundary

Do not use this runbook as if it described:
- a packaged desktop installer
- a shared multi-user server
- a generalized workspace platform

Current honest status:
- this is a repo-based alpha install path
- the packaged installer path is not the default distribution path yet
- the recommended runtime shape is still personal and local-first

Windows status:
- not currently an officially packaged or repo-proven target
- not impossible at the core runtime level
- safest current claim is `Windows-later`, with cautious from-source use only if the operator is technically comfortable
- use `docs/WINDOWS_PERSONAL_RUNTIME_ALPHA.md` for the Windows-specific status and PowerShell path
- the repo-provided Windows host smoke entry is `py -3 scripts/check_windows_personal_runtime_smoke.py --mode source`

## Recommended runtime shape

For close-person alpha, prefer:

- `PAPERPIPE_INSTALL_LAYOUT=1`
- one user-specific config file
- app-owned data outside the git checkout

That keeps runtime state under a user-scoped app-data root instead of scattering it through the repo checkout.

Platform-style config root:

- macOS: `~/Library/Application Support/Lattice/config/config.yaml`
- Linux: `~/.config/Lattice/config/config.yaml`
- Windows: `%APPDATA%\\Lattice\\config\\config.yaml`

When install-layout is enabled, app-owned roots such as storage, logs, and cache also move under the same user-scoped base directory.

## 1. Prerequisites

You currently need:

- a local checkout of this repo
- Python 3.13+
- Node.js and npm for the frontend build

Optional but commonly useful:

- Ollama if you want local-model flows
- a real Obsidian vault path
- a real Zotero storage path

Windows note:

- use PowerShell or another Windows-native shell for the runtime steps
- do not assume the maintainer shell scripts under `scripts/*.sh` are part of the Windows operator path

## 2. Install dependencies

From the repo root:

```bash
git submodule update --init --recursive
python -m pip install -r requirements.txt
```

Build the frontend bundle:

```bash
cd frontend
npm install
npm run build
cd ..
```

Why the frontend build matters:

- `lattice start` can fall back to a dev entry if the built bundle is missing
- for personal-runtime alpha, prefer a real built `/ui` bundle

Windows from-source equivalent:

```powershell
git submodule update --init --recursive
py -3 -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
```

## 3. Create a personal config file

Create the platform-style config directory.

macOS:

```bash
mkdir -p "$HOME/Library/Application Support/Lattice/config"
cp config.example.yaml "$HOME/Library/Application Support/Lattice/config/config.yaml"
```

Linux:

```bash
mkdir -p "$HOME/.config/Lattice/config"
cp config.example.yaml "$HOME/.config/Lattice/config/config.yaml"
```

Windows PowerShell:

```powershell
$configDir = Join-Path $env:APPDATA "Lattice\\config"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
Copy-Item .\\config.example.yaml (Join-Path $configDir "config.yaml")
```

Then edit `config.yaml` and update at least:

- `paths.zotero_base_dir`
- `paths.obsidian_vault`

You may leave those paths intentionally unset or placeholder-shaped if you only want a first launch check, but `self-test` will warn that the external roots are missing.

## 4. Enable install-layout mode

macOS/Linux:

```bash
export PAPERPIPE_INSTALL_LAYOUT=1
```

Windows PowerShell:

```powershell
$env:PAPERPIPE_INSTALL_LAYOUT="1"
```

What this changes:

- config resolves from the user-scoped install-layout path
- app-owned storage/log/cache roots move out of the repo checkout
- the runtime behaves more like a personal app and less like a dev workspace

## 5. Run self-test first

```bash
lattice self-test --json
```

What to expect:

- `config_file`: should be `ok` if your install-layout config exists
- `config_root`, `runtime_db`, `storage_root`, `logs_root`: should be writable
- `ui_bundle`: should be `ok` if you built the frontend
- `obsidian_vault` / `zotero_base_dir`: may be `warn` if not configured yet

Interpretation:

- `error`: fix before sharing or relying on the runtime
- `warn` / `degraded`: usually means a missing external dependency or a non-ideal runtime condition, not necessarily a broken launcher

If `backend_entrypoint` reports a missing dependency such as `fastapi`, rerun:

```bash
python -m pip install -r requirements.txt
```

If `ui_bundle` warns that the built frontend bundle is missing, rerun:

```bash
cd frontend
npm run build
cd ..
```

## 6. Start the personal runtime

```bash
lattice start
```

Compatibility alias:

```bash
paperpipe start
```

If the installed command aliases are not available in the current shell yet, use the Python entry directly:

macOS/Linux:

```bash
python3 -m src.cli start
```

Windows PowerShell:

```powershell
py -3 -m src.cli start
```

Expected behavior:

- config preflight runs first
- runtime DB bootstraps
- backend starts
- healthcheck passes
- browser opens to `/ui`

Stop with `Ctrl+C`.

## 7. Recommended optional security defaults

For any runtime you plan to keep around or share over a non-trivial network, set:

```bash
export LATTICE_API_KEY="change-me"
export LATTICE_CORS_ALLOW_ORIGINS="http://localhost:8000"
export LATTICE_BETA_PASSWORD="change-me"
export LATTICE_ALLOWED_HOSTS="localhost,127.0.0.1"
export LATTICE_BETA_ALLOWED_IPS="203.0.113.7"
export LATTICE_BROWSER_WRITE_RATE_LIMIT_COUNT="30"
```

`LATTICE_MASK_LOCAL_PATHS` is already enabled by default; only set it to `"false"` for trusted local debugging that needs raw absolute paths.

`LATTICE_BETA_PASSWORD` adds a thin HTTP Basic gate in front of `/ui`, browser-facing `/api/*`, and `/health/ready`. The default username is `beta`; set `LATTICE_BETA_USERNAME` only if you need a different shared username. In a gated browser session, `/health/ready` now defaults to a browser-safe summary rather than the full internal runtime topology.

`LATTICE_ALLOWED_HOSTS` should list the hostname(s) your personal runtime will actually receive in a hosted setup. For local-only use, the default allowlist already covers `localhost` and `127.0.0.1`.

`LATTICE_BETA_ALLOWED_IPS` is optional but recommended once you move beyond localhost. It narrows `/ui`, browser-facing `/api/*`, and the same protected root routes to a small exact-IP or CIDR allowlist before the beta password or API key is evaluated.

`LATTICE_BROWSER_WRITE_RATE_LIMIT_COUNT` adds a small same-origin browser write throttle for protected `/api/*` `POST` routes in hosted beta. The default window is `60` seconds, and `LATTICE_BETA_PASSWORD` already turns this protection on with a conservative default unless you override it.

FastAPI docs stay available by default for local development, but once `LATTICE_BETA_PASSWORD` is set they are disabled unless you explicitly opt back in with `LATTICE_ENABLE_API_DOCS="true"`.

If you want one more outer layer at the reverse proxy, start from `packaging/reverse_proxy/caddy/Caddyfile.example` or `packaging/reverse_proxy/nginx/lattice-beta.conf.example`. Those templates keep `/health` open, then apply IP allowlist + Basic auth to everything else before the request reaches FastAPI.

If you need the full detailed readiness payload inside a trusted gated browser session, opt back in explicitly:

```bash
export LATTICE_BROWSER_DETAILED_RUNTIME_READINESS="true"
```

Then start again:

```bash
lattice start
```

More detail:
- `docs/runtime_security_env.md`

## 8. What lives where

With install-layout enabled, the intended shape is:

- config under the user-scoped config root
- app-owned DB/storage/log/cache under the user-scoped app-data area
- external/operator-owned roots such as Obsidian and Zotero stay external

This separation matters because Lattice is currently:

- local-first
- single-operator-first
- not a shared multi-user workspace platform

## 9. Optional macOS packaging spike

This is not yet the default operator path, but the current macOS-first packaging spike is repo-proven.

For the next release step from alpha bundle to Gatekeeper-ready notarized artifact, use:

- `docs/MACOS_PERSONAL_RUNTIME_RELEASE.md`

For close-person tester sharing before Gatekeeper-ready trust distribution, use:

- `docs/MACOS_PERSONAL_RUNTIME_ALPHA_HANDOFF.md`

Install the packaging dependency:

```bash
.venv/bin/python -m pip install ".[packaging]"
```

Build the bundle around the existing launcher:

```bash
.venv/bin/python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean
```

Current macOS spike outputs:

- `dist/lattice`
- `dist/Lattice.app`

PyInstaller currently also emits a support directory for the app-bundle build:

- `dist/Lattice-support`

Run a packaged readiness check:

```bash
PAPERPIPE_CONFIG_PATH="$PWD/config.example.yaml" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/lattice self-test --json
```

Start the packaged runtime:

```bash
PAPERPIPE_CONFIG_PATH="$PWD/config.example.yaml" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/lattice start --no-open --port 8026
```

Or launch the app-bundle executable path directly:

```bash
PAPERPIPE_CONFIG_PATH="$PWD/config.example.yaml" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/Lattice.app/Contents/MacOS/Lattice --no-open --port 8026
```

For Finder-style launch on macOS, the bundled app executable defaults to `start` when opened without an explicit subcommand.

What this currently proves:

- the packaged launcher can start the backend
- the packaged backend can serve `/ui` from bundled frontend assets
- the app-bundle executable path can reuse the same launcher-first runtime
- the app bundle passes local `codesign --verify --deep --strict`
- Finder-style no-arg launch behavior is covered by CLI tests, but Gatekeeper still rejects the app because it is not Developer ID signed/notarized yet
- install-layout paths still resolve into the user-scoped app-data roots

What this does not yet prove:

- signed or notarized installer quality
- a drag-and-drop `.app` distribution experience
- Windows packaged support

## 9. Common first-launch issues

### `config_file` error

Cause:
- install-layout is enabled, but the user-scoped `config.yaml` does not exist

Fix:
- copy `config.example.yaml` into the platform-style config root as shown above

### `ui_bundle` warning

Cause:
- frontend bundle was not built

Fix:
- run `cd frontend && npm install && npm run build`

### `obsidian_vault` or `zotero_base_dir` warning

Cause:
- external roots are missing or still set to placeholders

Fix:
- update the paths in your personal `config.yaml`

### Runtime state appears inside the repo checkout

Cause:
- install-layout mode is not enabled in the current shell

Fix:
- export `PAPERPIPE_INSTALL_LAYOUT=1`
- rerun `lattice self-test --json`

## 10. Maintainer-facing verification

For release or share readiness on the current repo path, use the smallest honest checks:

```bash
lattice self-test --json
./scripts/run_backend_api_smoke.sh
cd frontend && npm run build
cd frontend && npm run verify:frontend
```

If local verification fails before tests really start because the default Python or `pytest` runner is unhealthy, rebuild the bounded verification env first:

```bash
python3 scripts/bootstrap_verification_env.py --run-id local_verification_bootstrap
```

Current local verify wrappers resolve `PAPERPIPE_VERIFICATION_PYTHON`, then `.venv314`, before falling back to other healthy interpreters. If you need to override the chosen runner explicitly, point `PAPERPIPE_VERIFICATION_PYTHON` at the desired venv Python.

Windows note:

- the maintainer verification path is still more mature on macOS/Linux because several repo checks still use bash
- that does not mean the core runtime is impossible on Windows
- it does mean we should not advertise Windows as a fully supported packaged target yet

## 11. Current boundary

This runbook is the current close-person alpha path.

It is intentionally not yet:

- a one-click desktop installer
- a shared hosted SaaS setup
- a multi-user collaboration runbook

Those are future packaging or product-shape decisions, not assumptions hidden inside this guide.
