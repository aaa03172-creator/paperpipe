# Installed App E2E Checklist

Date: 2026-06-04
Scope: `/Applications/Lattice.app`, `dist/Lattice.app`, and `dist/release/Lattice-macos-arm64.zip`

## Purpose

This checklist is the operator-facing gate for the native Lattice alpha app. It verifies that a teammate can open the app, configure an LLM provider key, use the paper workflow, and receive a package whose hash matches the release manifest.

## P0 Gates

- Direct launch: open `/Applications/Lattice.app`.
- Browser boundary: the app opens the Lattice window and does not open the default browser for the primary UI path.
- Runtime readiness: `/health` returns `200`.
- Settings route: `/ui/settings` returns `200`.
- API key entry: the API key field accepts normal typing, `Command+V`, and the `Paste key` button.
- Clipboard ethics: clipboard content is read only after an explicit paste action.
- Save boundary: pasted keys are not saved until the user presses `Save settings`.
- Secret boundary: raw provider keys are not echoed in API responses, logs, docs, or bundled frontend assets.
- App termination: closing or quitting the app stops the runtime process it started.

## P1 Gates

- Native menu: `Edit` menu exposes `Undo`, `Redo`, `Cut`, `Copy`, `Paste`, and `Select All`.
- Settings provider list includes OpenAI, Anthropic, and Google Gemini.
- Settings UI includes `Test live call`, but live calls remain explicit user actions only.
- Installed app smoke passes with `/health`, `/ui/settings`, and `/api/runtime-settings/llm` returning `200`.
- `dist/Lattice.app` and `/Applications/Lattice.app` executable hashes match after installation.
- `codesign --verify --deep --strict` passes for `/Applications/Lattice.app` and `/Applications/Lattice Launcher.app`.

## P2 Gates

- Mock frontend E2E passes.
- Backend E2E passes or skipped lanes are explicitly gated by environment variables.
- Release zip proof passes after extracting the zip to a temporary directory.
- Manifest `release_zip_sha256` and `launcher_zip_sha256` match `shasum -a 256`.
- Release docs reference the current manifest hashes.

## Automated Commands

```bash
cd frontend
npm run build
npm run e2e:mock
npm run e2e:backend
```

```bash
uv run pytest tests/test_build_personal_runtime_bundle.py tests/test_release_macos_personal_runtime.py tests/test_runtime_settings_api.py -q
```

```bash
swiftc packaging/macos/LatticeNativeLauncher.swift -o /tmp/LatticeNativeLauncher-check
```

```bash
uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean --bundle-profile cloud-ui
rm -rf /Applications/Lattice.app "/Applications/Lattice Launcher.app"
ditto ./dist/Lattice.app /Applications/Lattice.app
python3 scripts/install_macos_lattice_launcher.py --sign
codesign --verify --deep --strict /Applications/Lattice.app
codesign --verify --deep --strict "/Applications/Lattice Launcher.app"
PAPERPIPE_INSTALLED_SETTINGS_SMOKE_PORT=8056 scripts/run_macos_installed_settings_smoke.sh
```

```bash
uv run --extra cloud --extra packaging python scripts/release_macos_personal_runtime.py --skip-frontend-build --include-launcher
PAPERPIPE_MACOS_ALPHA_ZIP_PROOF_PORT=8057 scripts/run_macos_alpha_zip_cloud_demo_proof.sh
python3 - <<'PY'
import hashlib, json, pathlib
manifest = json.loads(pathlib.Path("dist/release/Lattice-macos-arm64.manifest.json").read_text())
for key, rel in [
    ("release_zip_sha256", "dist/release/Lattice-macos-arm64.zip"),
    ("launcher_zip_sha256", "dist/release/Lattice-macos-arm64.launcher.zip"),
]:
    actual = hashlib.sha256(pathlib.Path(rel).read_bytes()).hexdigest()
    assert actual == manifest["hashes"][key], (key, actual, manifest["hashes"][key])
    print(key, actual)
PY
```

## Manual App Checks

1. Open `/Applications/Lattice.app`.
2. Open Settings from Home.
3. Click the API key field and use `Command+V`.
4. Clear the field, copy a test string, and use `Paste key`.
5. Confirm the key remains hidden in the password field.
6. Press `Save settings` only with a non-secret test key in non-production checks.
7. Confirm `Test live call` is user-triggered and not invoked by loading the page.
8. Quit Lattice and confirm no `LatticeRuntime start`, `serve-backend`, or `serve-worker` process remains.

## Current Coverage Map

- `frontend/e2e/mock.spec.ts`: mock Settings paste coverage.
- `frontend/e2e/backend.spec.ts`: live backend Settings paste coverage.
- `scripts/run_macos_installed_settings_smoke.sh`: installed Settings route/API/bundle text coverage.
- `scripts/run_macos_alpha_zip_cloud_demo_proof.sh`: extracted zip proof for app runtime and cloud demo endpoints.

## Known Gated Lanes

- Real paper smoke requires `PAPERPIPE_REAL_SMOKE=1`.
- Parser worker lane requires `PAPERPIPE_E2E_ENABLE_PARSER_WORKER=1`.
- Intentional canary requires `PAPERPIPE_E2E_CANARY=1` and should remain skipped in normal readiness runs.

## Pass Criteria

The app is demo-shareable when P0 and P1 gates pass, release proof passes, and any skipped lanes are intentional gated lanes listed above.
