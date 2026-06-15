# macOS Personal Runtime Release

Status: Active
Date: 2026-03-28
Owner: Lattice runtime maintainers
Purpose: provide the smallest repo-grounded release path from the current PyInstaller personal-runtime bundle to a Gatekeeper-ready macOS artifact.

Canonical parents:
- `docs/PERSONAL_RUNTIME_INSTALL.md`
- `docs/reports/Personal_Runtime_Packaging_Decision_2026-03-28.md`

If trust distribution is intentionally deferred and the goal is only close-person tester handoff, use:

- `docs/MACOS_PERSONAL_RUNTIME_ALPHA_HANDOFF.md`

## Scope

Use this runbook when you want to move from:

- `working local alpha bundle`

to:

- `Developer ID signed app bundle`
- `notarized app bundle`
- `stapled app bundle`
- `distribution zip built from the stapled app`

This runbook does not cover:

- Windows packaging
- DMG authoring
- App Store distribution

## Current release script

The current release entrypoint is:

- `scripts/release_macos_personal_runtime.py`

It wraps the already-proven bundle build from:

- `scripts/build_personal_runtime_bundle.py`

## Prerequisites

You need:

- macOS
- Xcode command line tools
- a `Developer ID Application` certificate installed in Keychain
- `xcrun notarytool`
- the packaging dependency already installed

Install the repo packaging dependency:

```bash
.venv/bin/python -m pip install ".[packaging]"
```

Repo-local repeatable proof wrapper:

```bash
bash ./scripts/run_macos_personal_runtime_local_proof.sh
```

What it does:

- packages the current local release zip into a temporary release directory
- runs packaged `self-test --json` for both `dist/lattice` and the app-bundle executable
- launches the packaged app on a local port and probes `/health` and `/ui`

GCS + Firestore demo proof wrapper:

```bash
bash ./scripts/run_macos_personal_runtime_cloud_demo_proof.sh
```

Use this after the Google Agent Challenge cloud paper rehearsal has written the controlled Firestore/GCS demo record. It launches `dist/Lattice.app/Contents/MacOS/Lattice` with the demo cloud environment and verifies `/health`, `/ui`, `/api/cloud/papers`, and cloud page search from the packaged app. It does not notarize, upload, or create Cloud Run/Cloud Tasks resources.

Installed settings smoke wrapper:

```bash
bash ./scripts/run_macos_installed_settings_smoke.sh
```

Use this after copying `dist/Lattice.app` to `/Applications/Lattice.app` and, when needed, regenerating `/Applications/Lattice Launcher.app`. It launches the installed app with provider API key environment variables unset, verifies `/health`, `/ui/settings`, and `/api/runtime-settings/llm`, and checks the installed UI bundle contains the Google Gemini provider option plus the explicit `Test live call` action. It does not invoke the live LLM provider test.

Native-like direct app launch check:

```bash
open /Applications/Lattice.app
curl -fsS http://127.0.0.1:8046/health
```

The installed bundle's `Contents/MacOS/Lattice` is a small AppKit/WKWebView launcher around `Contents/MacOS/LatticeRuntime`. No-argument app launches start `LatticeRuntime start --no-open` and render `/ui` inside the app window; explicit CLI arguments continue to pass through to the runtime so existing smoke scripts and compatibility launchers keep working.

Gatekeeper prereq wrapper:

```bash
bash ./scripts/run_macos_personal_runtime_gatekeeper_prereqs.sh
```

Optional explicit target values:

```bash
bash ./scripts/run_macos_personal_runtime_gatekeeper_prereqs.sh \
  --identity "Developer ID Application: Your Name (TEAMID1234)" \
  --notary-profile LATTICE_NOTARY \
  --output /tmp/lattice-gatekeeper-prereqs.json
```

What it does:

- resolves a healthy local Python runner
- calls `release_macos_personal_runtime.py --check-prereqs`
- prints the JSON report and saves the same report to a file

Use the manual commands below when you want to inspect or customize one step at a time.

## 1. Build the app bundle

If you need a fresh bundle first:

```bash
uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean
```

Expected macOS bundle artifacts:

- `dist/lattice`
- `dist/Lattice.app`
- `dist/Lattice-support`

For a slimmer cloud-backed stage-demo app, use the cloud UI bundle profile:

```bash
uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py \
  --skip-frontend-build \
  --clean \
  --bundle-profile cloud-ui
```

This profile is intended for the lightweight GCP paper/page demo path. It excludes local heavy ML stacks such as Torch, Transformers, OpenCV, scikit-learn, and SciPy. Use the default `full` profile when local parsing, OCR, indexing, or ML-adjacent features need to stay bundled.

## 2. Store notarization credentials once

Recommended path: create a Keychain profile for `notarytool`.

App Store Connect API key flow:

```bash
xcrun notarytool store-credentials LATTICE_NOTARY \
  --key /absolute/path/to/AuthKey_XXXXXX.p8 \
  --key-id XXXXXX \
  --issuer XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
```

Apple ID flow:

```bash
xcrun notarytool store-credentials LATTICE_NOTARY \
  --apple-id your-apple-id@example.com \
  --team-id TEAMID1234
```

The release script expects the profile name, not the raw secret values.

## 3. Run the full release path

Example:

```bash
.venv/bin/python scripts/release_macos_personal_runtime.py \
  --build \
  --clean \
  --skip-frontend-build \
  --identity "Developer ID Application: Your Name (TEAMID1234)" \
  --notary-profile LATTICE_NOTARY \
  --require-gatekeeper
```

Environment-variable equivalent:

```bash
export PAPERPIPE_MACOS_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID1234)"
export PAPERPIPE_MACOS_NOTARY_PROFILE="LATTICE_NOTARY"
.venv/bin/python scripts/release_macos_personal_runtime.py --build --clean --skip-frontend-build
```

When the release script is also building the app, it can forward the same bundle profile:

```bash
uv run --extra cloud --extra packaging python scripts/release_macos_personal_runtime.py \
  --build \
  --clean \
  --skip-frontend-build \
  --bundle-profile cloud-ui
```

For public distribution attempts, add `--require-gatekeeper`. That guard fails early unless both `--identity` and `--notary-profile` are present, which prevents accidentally treating an assisted alpha zip as a public Gatekeeper-ready release.

What the script does:

- optionally rebuilds the PyInstaller bundle
- re-signs `dist/lattice`
- re-signs `dist/Lattice.app`
- verifies the current code signature locally
- creates a zip archive from `dist/Lattice.app`
- submits that zip to Apple notary service and waits
- staples the accepted ticket to `dist/Lattice.app`
- validates the stapled ticket
- runs `spctl --assess --type execute`
- rebuilds the final distribution zip from the stapled app
- writes a release manifest JSON under `dist/release/`

## 3.5 Check prerequisites first

Before the real signed/notarized run, you can inspect the current machine state:

```bash
.venv/bin/python scripts/release_macos_personal_runtime.py --check-prereqs
```

Or use the repo-local wrapper above if you want the report written to a file as well.

What this report tells you:

- whether `dist/Lattice.app` and `dist/lattice` already exist
- whether local macOS tools like `codesign`, `xcrun`, `spctl`, and `ditto` are present
- which code-signing identities are visible in Keychain
- whether the requested `notarytool` Keychain profile exists
- whether the machine is ready only for local release packaging or also for Gatekeeper-ready release

Current repo-local honest state on this machine was:

- local release packaging: ready
- Gatekeeper-ready release: blocked by missing `Developer ID Application` identity and missing `notarytool` Keychain profile

## 4. Local verification mode without Apple credentials

If you want to exercise the script shape without signing or notarization credentials:

```bash
uv run --extra cloud --extra packaging python scripts/release_macos_personal_runtime.py
```

This mode still:

- verifies the existing local code signature state
- packages `dist/Lattice.app` into a release zip
- writes a release manifest

This mode does not:

- make the app Gatekeeper-ready
- run notarization
- run stapling
- perform a final `spctl` acceptance check

## 5. Release outputs

After a full run, expect:

- `dist/Lattice.app`
- `dist/lattice`
- `dist/release/Lattice-macos-arm64.zip`
- `dist/release/Lattice-macos-arm64.manifest.json`
- `dist/release/Lattice-macos-arm64.notary-submit.json`

If notarization fails and Apple returns a submission id, the script also tries to write:

- `dist/release/Lattice-macos-arm64.notary-log.json`

## 6. Honest acceptance bar

For a real macOS handoff, expect all of the following:

- local `codesign --verify --deep --strict dist/Lattice.app` passes
- `spctl --assess --type execute dist/Lattice.app` passes
- `dist/Lattice.app/Contents/MacOS/Lattice self-test --json` reports `ui_bundle=ok`
- launching the app bundle executable serves `/ui`

Until `spctl` passes, the artifact is still alpha-quality, not a true Gatekeeper-ready distribution.

## 7. Google Agent Challenge Cloud Demo Note

For the 2026-06-05 stage demo, the currently accepted installable path is:

```bash
cd frontend && npm run build
cd ..
uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean
scripts/run_macos_personal_runtime_cloud_demo_proof.sh
```

Current local verification on 2026-06-01:

- `dist/Lattice.app` rebuilt successfully from current code.
- PyInstaller hidden imports include `google.cloud.firestore` and `google.cloud.storage` for the current GCS + Firestore path.
- Packaged self-test is `degraded` only because `config.example.yaml` has placeholder Obsidian/Zotero/watch roots; `ui_bundle`, `backend_entrypoint`, and `cli_entrypoint` are `ok`.
- Packaged cloud proof passes with `health_status=200`, `ui_status=200`, `cloud_list_status=200`, and `cloud_search_status=200`.
- This remains an unsigned/local alpha artifact unless the Developer ID + notary flow above is completed.

Installed app verification on 2026-06-04:

- `/Applications/Lattice.app` direct launch passed through `open /Applications/Lattice.app`.
- `/health` returned `200` on port `8046`, `/ui` returned `200`, and the app log showed WebView asset requests from the native Lattice process.
- The primary app path starts the runtime with `--no-open`, so it does not open the default web browser for the app surface.
- Installed settings smoke passed with `health_status=200`, `ui_status=200`, and `settings_status=200`.
- Release zip SHA256: `522e5693a20bd7f9c96383d044d9416669d5c80e4c25b77d2377194308e21b9e`.
- Assisted launcher zip SHA256: `1a6472ed64ea99b241a602a56fe20fd877554cce518a42dcca3605c47be3f196`.
