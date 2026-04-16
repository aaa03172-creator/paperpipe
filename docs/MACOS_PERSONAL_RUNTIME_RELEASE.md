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

## 1. Build the app bundle

If you need a fresh bundle first:

```bash
.venv/bin/python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean
```

Expected macOS bundle artifacts:

- `dist/lattice`
- `dist/Lattice.app`
- `dist/Lattice-support`

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
  --notary-profile LATTICE_NOTARY
```

Environment-variable equivalent:

```bash
export PAPERPIPE_MACOS_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID1234)"
export PAPERPIPE_MACOS_NOTARY_PROFILE="LATTICE_NOTARY"
.venv/bin/python scripts/release_macos_personal_runtime.py --build --clean --skip-frontend-build
```

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
.venv/bin/python scripts/release_macos_personal_runtime.py
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
