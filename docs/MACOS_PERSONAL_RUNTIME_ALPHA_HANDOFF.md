# macOS Personal Runtime Alpha Handoff

Status: Active
Date: 2026-03-28
Owner: Lattice runtime maintainers
Purpose: define the honest close-person handoff path for the current macOS personal-runtime bundle while Gatekeeper-ready trust distribution is still deferred.

Canonical parents:
- `docs/PERSONAL_RUNTIME_INSTALL.md`
- `docs/MACOS_PERSONAL_RUNTIME_RELEASE.md`
- `docs/reports/Personal_Runtime_Packaging_Decision_2026-03-28.md`

## Scope

Use this when:

- you want to hand the current macOS app to a small number of trusted testers
- you are comfortable with operator-assisted setup
- Gatekeeper-ready signing/notarization is not yet the goal

Do not use this as if it were:

- a public distribution guide
- a mass self-serve installer flow
- proof of general consumer installability

## Current honest product state

Today the repo can produce:

- `dist/Lattice.app`
- `dist/lattice`
- `dist/release/Lattice-macos-arm64.zip`
- `dist/release/Lattice-macos-arm64.alpha-handoff.md`
- `dist/release/Lattice-macos-arm64.config.example.yaml`

Today the repo does not yet guarantee:

- Apple Gatekeeper acceptance
- notarized public web distribution
- frictionless first-run for non-technical testers

## Maintainer path

1. Build the current bundle:

```bash
uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean
```

For the Google Agent Challenge cloud paper demo, the optional slimmer build profile is:

```bash
uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py \
  --skip-frontend-build \
  --clean \
  --bundle-profile cloud-ui
```

Use that only after rebuilding and rerunning the packaged cloud proof. The default `full` profile remains the safer compatibility choice when local parsing, OCR, indexing, or ML-adjacent features must remain bundled.

2. Produce the alpha handoff package:

```bash
uv run --extra cloud --extra packaging python scripts/release_macos_personal_runtime.py
```

If producing a public-distribution candidate rather than an assisted alpha zip, add `--require-gatekeeper` together with real Developer ID and notary credentials. Without those credentials, this path is intentionally only an assisted alpha handoff.

If you want to rehearse the full local alpha proof before sending anything, use:

```bash
bash ./scripts/run_macos_personal_runtime_local_proof.sh
```

For the Google Agent Challenge cloud paper demo, run the packaged GCS + Firestore proof as well:

```bash
bash ./scripts/run_macos_personal_runtime_cloud_demo_proof.sh
```

Then verify the actual release zip, not only the local `dist/Lattice.app` tree:

```bash
bash ./scripts/run_macos_alpha_zip_cloud_demo_proof.sh
```

Preferred final pre-stage gate after the release zip already exists:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  bash ./scripts/run_gcp_cloud_paper_demo_readiness_gate.sh
```

That proof expects the controlled demo record to already exist in Firestore/GCS. Prepare it first with:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  uv run --extra cloud python scripts/cloud_paper_demo_rehearsal_smoke.py
```

3. Confirm the generated files exist:

- `dist/release/Lattice-macos-arm64.zip`
- `dist/release/Lattice-macos-arm64.alpha-handoff.md`
- `dist/release/Lattice-macos-arm64.config.example.yaml`

4. Run one final runtime check before sending:

```bash
PAPERPIPE_CONFIG_PATH="$PWD/config.example.yaml" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/Lattice.app/Contents/MacOS/Lattice self-test --json
```

5. Edit the config example or separately provide the tester with the exact values for:

- `paths.obsidian_vault`
- `paths.zotero_base_dir`

## Google Agent Challenge Assisted Demo Package

Latest local alpha package, 2026-06-04:

- release zip: `dist/release/Lattice-macos-arm64.zip`
- size: about `97M`
- app bundle size: about `194M`
- SHA256: `522e5693a20bd7f9c96383d044d9416669d5c80e4c25b77d2377194308e21b9e`
- launcher zip: `dist/release/Lattice-macos-arm64.launcher.zip`
- launcher zip SHA256: `1a6472ed64ea99b241a602a56fe20fd877554cce518a42dcca3605c47be3f196`
- manifest: `dist/release/Lattice-macos-arm64.manifest.json`
- alpha note: `dist/release/Lattice-macos-arm64.alpha-handoff.md`
- config template: `dist/release/Lattice-macos-arm64.config.example.yaml`

Verification completed for this package:

- current `dist/Lattice.app` was rebuilt from the cloud-enabled code path
- release zip was regenerated from that app bundle
- release zip SHA256 was checked against the release manifest
- release zip was extracted to a temporary folder and the extracted `Lattice.app` was launched successfully
- manifest marks `signed=false`, `notarized=false`, and `gatekeeper_assessment=null`
- packaged cloud proof passed with `/health`, `/ui`, `/api/cloud/papers`, and `/api/cloud/papers/search` all returning `200`
- extracted-zip cloud proof also passed with `/health`, `/ui`, `/api/cloud/papers`, and `/api/cloud/papers/search` all returning `200`; the same proof now also verifies the assisted launcher zip structure, executable bit, and icon resource
- `/Applications/Lattice Launcher.app` can be regenerated with `scripts/install_macos_lattice_launcher.py --sign`; it uses the same Lattice icon, stores runtime state under `~/Library/Application Support/Lattice`, writes launcher logs under `~/Library/Logs/Lattice`, detects an existing server before launching, and opens `http://127.0.0.1:8046/ui`
- native-like launcher smoke passed on 2026-06-02 KST by stopping the existing app process, opening `/Applications/Lattice Launcher.app`, and observing `/health` return `200` after 5 seconds
- cloud search included the controlled demo paper id `paper_mock_000001`
- public cloud list/search payloads did not expose GCS refs, bucket names, signed URLs, service accounts, or internal object-ref fields
- final readiness gate passed on 2026-06-02 KST from `2026-06-02T09:50:33Z` to `2026-06-02T09:50:57Z`
- targeted install-package security audit completed in `docs/reports/MacOS_Alpha_Install_Package_Security_Audit_2026-06-01.md`
- cloud UI bundle profile was rebuilt with the native AppKit shell, custom Lattice app icon, assisted launcher artifact, and extracted-zip proof passed on 2026-06-04 KST with SHA256 `522e5693a20bd7f9c96383d044d9416669d5c80e4c25b77d2377194308e21b9e`

Latest installed-app demo completeness gate, 2026-06-04:

- report: `docs/reports/Installed_App_Demo_Completeness_Gate_2026-06-04.md`
- installed app smoke: `scripts/run_macos_installed_settings_smoke.sh`
- installed app: `/Applications/Lattice.app` replaced from current `dist/Lattice.app`
- installed launcher: `/Applications/Lattice Launcher.app` regenerated with `scripts/install_macos_lattice_launcher.py --sign`
- direct app launch: opening `/Applications/Lattice.app` starts the native AppKit/WKWebView shell, detects/reuses an existing healthy server when present, and renders `http://127.0.0.1:8046/ui` inside the app window
- app bundle shape: `Contents/MacOS/Lattice` is the native WebView launcher and `Contents/MacOS/LatticeRuntime` is the packaged PyInstaller runtime
- browser boundary: the native launcher runs `LatticeRuntime start --no-open`, so the primary app path does not open the default web browser
- installed settings smoke passed with `health_status=200`, `ui_status=200`, and `settings_status=200`
- settings UI bundle contains `Google Gemini` and `Test live call`
- release zip SHA256: `522e5693a20bd7f9c96383d044d9416669d5c80e4c25b77d2377194308e21b9e`
- launcher zip SHA256: `1a6472ed64ea99b241a602a56fe20fd877554cce518a42dcca3605c47be3f196`
- extracted release zip proof passed with `/health`, `/ui`, cloud list, and cloud search all returning `200`

Assisted demo run order:

1. Confirm GCP cost posture:

```bash
scripts/cloud_paper_demo_cost_preflight.sh
```

2. Refresh the controlled GCS + Firestore demo record:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  uv run --extra cloud python scripts/cloud_paper_demo_rehearsal_smoke.py
```

3. Verify the packaged app path:

```bash
scripts/run_macos_personal_runtime_cloud_demo_proof.sh
```

4. Verify the release zip path:

```bash
scripts/run_macos_alpha_zip_cloud_demo_proof.sh
```

5. Preferred native-like local demo path: install `Lattice.app` and open it directly:

```bash
rm -rf /Applications/Lattice.app
ditto ./dist/Lattice.app /Applications/Lattice.app
open /Applications/Lattice.app
```

The app bundle renders `http://127.0.0.1:8046/ui` inside a native WebView,
stores runtime state under `~/Library/Application Support/Lattice`, writes logs
under `~/Library/Logs/Lattice`, and reuses an existing healthy server when one
is already running. The primary app path starts the runtime with `--no-open`, so
it does not hand the user to Safari, Chrome, or another default browser.

Optional compatibility launcher:

```bash
python3 scripts/install_macos_lattice_launcher.py --sign
```

Then open `/Applications/Lattice Launcher.app` only if the assisted wrapper is
more convenient for a tester. It remains a compatibility path around
`/Applications/Lattice.app`; it is ad-hoc signed for local execution but is not a
Developer ID signed or notarized public installer.

6. Launch the packaged app with the same demo environment:

```bash
PAPERPIPE_INSTALL_LAYOUT=1 \
PAPERPIPE_CONFIG_PATH="$PWD/config.example.yaml" \
LATTICE_API_KEY="demo-secret" \
PAPERPIPE_CLOUD_ADAPTER="gcs" \
PAPERPIPE_CLOUD_METADATA_STORE="firestore" \
PAPERPIPE_GCP_PROJECT_ID="knudc-a01068202087" \
PAPERPIPE_GCS_RAW_PDF_BUCKET="paperpipe-raw-pdf-dev-knudc-a01068202087" \
PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET="paperpipe-page-artifacts-dev-knudc-a01068202087" \
PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION="cloud_papers_demo" \
./dist/Lattice.app/Contents/MacOS/Lattice start --host 127.0.0.1 --port 8046
```

6. Open `/ui`, search for `processed page text`, and open the cloud paper.

Immediate fallback if GCP is unstable:

```bash
export PAPERPIPE_CLOUD_METADATA_STORE="memory"
export PAPERPIPE_CLOUD_ADAPTER="mock"
```

Then demonstrate the same UI contract in mock mode and keep the production claim bounded to the documented GCS + Firestore + Cloud Run direction.

## What to send the tester

Send these together:

- the alpha app artifact zip
- the alpha handoff note
- the config template

If the tester is not comfortable with Terminal or with manual config edits, do not send only the zip. Do an assisted setup session.

## Tester path

The intended tester flow is:

1. Unzip the app artifact.
2. Move `Lattice.app` into `/Applications` or another user-controlled folder.
3. Copy the provided config template to:
   `~/Library/Application Support/Lattice/config/config.yaml`
4. Edit the config with real local paths.
5. Launch the app.

## Expect rough edges

Because trust distribution is intentionally deferred:

- macOS may warn on first open
- the maintainer may need to help with the first launch
- placeholder external roots will degrade readiness

That is acceptable for this phase because the product goal is still:

- one operator
- one runtime
- close-person alpha feedback

## When to stop using this path

Stop using this alpha handoff path when either of these becomes true:

- you want broad self-serve web distribution
- you want testers to install without maintainer assistance

At that point, move to the Gatekeeper-ready path in:

- `docs/MACOS_PERSONAL_RUNTIME_RELEASE.md`
