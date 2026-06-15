# Installed App Demo Completeness Gate - 2026-06-04

Purpose: record the installed-app and release-zip checks for the Google Agent Challenge demo path after adding LLM provider settings, Google Gemini selection, explicit live-call testing, and native `Lattice.app` WebView launch support.

## Result

Status: passed for assisted alpha demo readiness. `/Applications/Lattice.app` is now the primary native AppKit/WKWebView entry point; `/Applications/Lattice Launcher.app` remains an optional compatibility launcher.

## Commands

```bash
uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean --bundle-profile cloud-ui
PAPERPIPE_CONFIG_PATH="$PWD/config.example.yaml" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/Lattice.app/Contents/MacOS/Lattice self-test --json
python3 scripts/install_macos_lattice_launcher.py --sign
PAPERPIPE_CONFIG_PATH="$PWD/config.example.yaml" PAPERPIPE_INSTALL_LAYOUT=1 /Applications/Lattice.app/Contents/MacOS/Lattice self-test --json
open /Applications/Lattice.app
scripts/run_macos_installed_settings_smoke.sh
uv run --extra cloud --extra packaging python scripts/release_macos_personal_runtime.py --skip-frontend-build --include-launcher
PAPERPIPE_MACOS_ALPHA_ZIP_PROOF_PORT=8057 scripts/run_macos_alpha_zip_cloud_demo_proof.sh
```

## Installed App Checks

- `/Applications/Lattice.app` was replaced with the current `dist/Lattice.app`.
- `/Applications/Lattice Launcher.app` was regenerated and ad-hoc signed.
- `codesign --verify --deep --strict` passed for both app bundles.
- `open /Applications/Lattice.app` started the native app shell, returned `/health` status `200`, and rendered `/ui` inside the app WebView.
- The bundle executable is now a small AppKit/WKWebView launcher at `Contents/MacOS/Lattice`; the PyInstaller runtime lives at `Contents/MacOS/LatticeRuntime`.
- The native launcher starts `LatticeRuntime start --no-open`, so the primary installed-app path no longer opens the default web browser.
- Installed app self-test loaded the installed frontend bundle from `/Applications/Lattice.app/Contents/Resources/frontend/dist/index.html`.
- Launcher smoke returned `/health` status `200` on port `8046`.
- `/ui/settings` returned `200`.
- Installed settings smoke returned `health_status=200`, `ui_status=200`, and `settings_status=200`.
- The installed UI bundle contains `Google Gemini` and `Test live call`.
- Provider API key env vars were unset during installed settings smoke, and `/api/runtime-settings/llm` returned `api_key_source=none`.
- The smoke did not invoke `/runtime-settings/llm/test`; live provider calls remain explicit user actions only.

## Release Artifacts

- Release zip: `dist/release/Lattice-macos-arm64.zip`
- Release zip size: about `95M`
- Release zip SHA256: `522e5693a20bd7f9c96383d044d9416669d5c80e4c25b77d2377194308e21b9e`
- Launcher zip: `dist/release/Lattice-macos-arm64.launcher.zip`
- Launcher zip size: about `140K`
- Launcher zip SHA256: `1a6472ed64ea99b241a602a56fe20fd877554cce518a42dcca3605c47be3f196`
- App bundle size: about `194M`
- CLI binary size: about `95M`
- Manifest: `dist/release/Lattice-macos-arm64.manifest.json`
- Manifest marks `signing.enabled=false`, `notarization.enabled=false`, and `gatekeeper_assessment=null`.

## Extracted Zip Proof

`scripts/run_macos_alpha_zip_cloud_demo_proof.sh` passed after extracting the release zip and assisted launcher zip:

- `/health` returned `200`
- `/ui` returned `200`
- `/api/cloud/papers` returned `200`
- `/api/cloud/papers/search?q=processed page text` returned `200`
- Search included `paper_mock_000001`
- Public cloud list/search responses did not expose raw GCS refs, bucket names, signed URLs, service accounts, or internal object-ref fields.

## Boundary

This is still an assisted alpha package. It is suitable for a controlled local demo, but it is not a Gatekeeper-ready public installer until Developer ID signing, notarization, stapling, and `spctl` acceptance pass.
