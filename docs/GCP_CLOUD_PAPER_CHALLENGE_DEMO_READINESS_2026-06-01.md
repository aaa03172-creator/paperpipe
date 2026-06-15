# GCP Cloud Paper/Page Challenge Demo Readiness

Status: Active demo-prep checklist
Date: 2026-06-01
Event target: Google Agent Challenge finals, 2026-06-05
Owner: PaperPipe/Lattice runtime maintainers
Cost guardrail: `docs/GCP_CLOUD_PAPER_DEMO_COST_GUARDRAILS_2026-06-01.md`
Stage operator sheet: `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md`

## Demo Goal

Show that PaperPipe can run as a lightweight installed research UI while cloud infrastructure stores PDFs, produces reusable page artifacts, and returns redacted page/search/detail data to authenticated devices.

## Selected Demo Paper

Primary paper:

- Title: Neuronal APOE4-induced early hippocampal network hyperexcitability in Alzheimer's disease pathogenesis
- Journal: Nature Aging
- DOI: `10.1038/s43587-026-01096-0`
- Article URL: `https://www.nature.com/articles/s43587-026-01096-0`
- Access/license note: Open access article under Creative Commons Attribution 4.0 International License according to the publisher page.
- Local demo source: user-provided Downloads PDF; do not commit the PDF or a personal filesystem path into the repository.
- Size: `8460622` bytes
- Pages: `34`
- SHA256: `5f9a0e674db49c1749717ac3502378518c81cef37c780258db317058d3124f40`
- Demo value: APOE4, Alzheimer's disease, hippocampal network hyperexcitability, and page-searchable scientific text make the upload -> cloud page -> installed UI loop easy to explain.

## Accepted Architecture Direction

- Storage: GCS for raw PDFs and page artifacts.
- Durable metadata: Firestore.
- Page processing worker: Cloud Run.
- Dispatch: Cloud Tasks for the first worker pilot.
- Demo auth: current same-origin/API-key plus beta lab/device headers.
- Production auth: first-class user/session/lab/device identity after the challenge.
- Retention: lab-configured policy with explicit delete semantics before production data.

## Friday Demo Scope

In scope:

- Controlled backend runtime with `PAPERPIPE_CLOUD_ADAPTER=gcs`.
- Firestore-backed demo metadata through `PAPERPIPE_CLOUD_METADATA_STORE=firestore`, with `memory` as the immediate rollback path.
- Cloud paper list, ready/processing/failed state display, normalized page preview, existing detail shell, hydration policy state, and cloud page search matches.
- One pre-verified demo PDF and one optional live upload.
- Clear verbal boundary: this is an internal pilot path, not a finished multi-tenant production deployment.

Out of scope for the stage demo:

- Real production SSO.
- Broad multi-tenant lab onboarding.
- Autonomous Cloud Run worker scaling claims unless the worker is actually deployed and smoke-tested.
- Retention/delete claims beyond the documented policy direction.
- Downstream artifact lanes treating cloud page text as canonical evidence.

## Demo Environment Variables

Minimum controlled demo path:

```bash
export LATTICE_API_KEY="set-demo-secret"
export LATTICE_CORS_ALLOW_ORIGINS="http://localhost:8000"
export PAPERPIPE_CLOUD_ADAPTER="gcs"
export PAPERPIPE_GCP_PROJECT_ID="knudc-a01068202087"
export PAPERPIPE_GCS_RAW_PDF_BUCKET="paperpipe-raw-pdf-dev-knudc-a01068202087"
export PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET="paperpipe-page-artifacts-dev-knudc-a01068202087"
export PAPERPIPE_CLOUD_METADATA_STORE="firestore"
export PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION="cloud_papers_demo"
```

Rollback:

```bash
export PAPERPIPE_CLOUD_METADATA_STORE="memory"
export PAPERPIPE_CLOUD_ADAPTER="mock"
```

Firestore status, 2026-06-01:

- Firestore API was enabled for project `knudc-a01068202087`.
- Firestore Native `(default)` database was created in `asia-northeast3`.
- Current demo collection: `cloud_papers_demo`.
- Latest cost preflight confirms billing is enabled, demo buckets are in `ASIA-NORTHEAST3`, Firestore DB exists in `asia-northeast3`, and Cloud Run/Cloud Tasks are not enabled.

## Pre-Demo Verification

Required before the event:

- `PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" scripts/run_gcp_cloud_paper_demo_readiness_gate.sh`

The readiness gate orchestrates:

- `scripts/cloud_paper_demo_cost_preflight.sh`
- `PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" uv run --extra cloud python scripts/cloud_paper_demo_rehearsal_smoke.py`
- `scripts/run_macos_personal_runtime_cloud_demo_proof.sh`
- `scripts/run_macos_alpha_zip_cloud_demo_proof.sh`

Run these separately after code, dependency, frontend, or packaging changes:

- `uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean`
- `pytest tests/test_cloud_paper_api.py tests/test_cloud_paper_schema.py tests/test_cloud_paper_access_policy.py tests/test_cloud_paper_metadata_store.py -q`
- `cd frontend && npm run build`
- `cd frontend && npm run e2e:mock -- -g "cloud page matches|cloud paper opens"`
- Manual browser smoke against the installed/light UI after the rehearsal script has written the Firestore/GCS demo record.
- Confirm browser-visible responses contain no GCS refs, bucket names, signed URLs, credentials, service accounts, or local paths.

## Rehearsal Runbook

Run this sequence before the stage demo and after any backend/frontend change that could affect cloud paper behavior:

Fast path after the release zip has already been built:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  scripts/run_gcp_cloud_paper_demo_readiness_gate.sh
```

Use the detailed steps below when diagnosing a failed gate.

1. Confirm cost posture and that Cloud Run/Cloud Tasks are still outside this demo path:

```bash
scripts/cloud_paper_demo_cost_preflight.sh
```

2. Run the repeatable GCS + Firestore API rehearsal with the selected PDF:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  uv run --extra cloud python scripts/cloud_paper_demo_rehearsal_smoke.py
```

The script exercises the same FastAPI path used by the UI:

- create upload intent
- upload source PDF through the backend-mediated route
- complete upload and build the page artifact
- read the public page artifact
- search cloud page text
- verify the Firestore document exists and is ready
- verify public API payloads do not expose GCS object refs, bucket names, signed URLs, service accounts, credentials, or absolute local paths

Expected stable output:

- `status`: `passed`
- `upload_mode`: `backend_mediated`
- `processing_status`: `ready`
- `page_schema_version`: `cloud_page_artifact_public.v1`
- `public_redaction`: `passed`
- `paper_id`: usually `paper_mock_000001` after the script resets the in-process mock counter

3. Start the local installed/light UI path with the same environment variables from "Demo Environment Variables".

4. In the UI, use the cloud paper list/search flow and search for:

```text
processed page text
```

5. Open the uploaded demo paper and show that the page view is served from the cloud page artifact while browser-visible data stays redacted.

If the rehearsal fails during presentation prep, do not improvise GCP changes on stage. Switch immediately to:

```bash
export PAPERPIPE_CLOUD_METADATA_STORE="memory"
export PAPERPIPE_CLOUD_ADAPTER="mock"
```

Then show the same UI contract with mock storage and clearly say that the production direction remains GCS + Firestore + Cloud Run worker, but the stage fallback is local/mock for reliability.

## Installable macOS Demo Path

For the Friday stage demo, the installable-app path is an unsigned/local alpha bundle, not a notarized public installer.

Build the current app bundle after frontend build and cloud tests are green:

```bash
uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean
```

For the slimmer cloud-backed demo package, use:

```bash
uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py \
  --skip-frontend-build \
  --clean \
  --bundle-profile cloud-ui
```

Expected local artifacts:

- `dist/Lattice.app`
- `dist/lattice`
- `dist/Lattice-support`

Run the packaged cloud proof:

```bash
scripts/run_macos_personal_runtime_cloud_demo_proof.sh
```

The proof starts `dist/Lattice.app/Contents/MacOS/Lattice` with the GCS + Firestore demo environment, then checks:

- `/health` returns `200`
- `/ui` returns `200`
- `/api/cloud/papers` returns `200`
- `/api/cloud/papers/search?q=processed page text` returns `200`
- search includes `paper_mock_000001`
- public list/search responses do not expose GCS refs, bucket names, signed URLs, service accounts, or internal object-ref fields

Latest packaged proof, 2026-06-02 KST:

- Build command: `uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean --bundle-profile cloud-ui`
- `dist/Lattice.app`: built successfully from current code.
- Packaged cloud proof: passed with `health_status=200`, `ui_status=200`, `cloud_list_status=200`, and `cloud_search_status=200`.
- Current local artifact size: `dist/Lattice.app` about `194M`, `dist/lattice` about `95M`.
- Alpha release zip: `dist/release/Lattice-macos-arm64.zip`, about `97M`.
- Alpha release zip SHA256: `522e5693a20bd7f9c96383d044d9416669d5c80e4c25b77d2377194308e21b9e`.
- Assisted launcher zip: `dist/release/Lattice-macos-arm64.launcher.zip`.
- Assisted launcher zip SHA256: `1a6472ed64ea99b241a602a56fe20fd877554cce518a42dcca3605c47be3f196`.
- Release manifest: `dist/release/Lattice-macos-arm64.manifest.json`, with `signed=false`, `notarized=false`, and `gatekeeper_assessment=null`.
- App icon: custom Lattice macOS icon included as `lattice.icns`.
- Extracted release zip proof: passed after checking the zip SHA256 against the release manifest, extracting the zip to `/tmp`, verifying the assisted launcher zip structure/icon/executable, launching the extracted `Lattice.app`, and verifying `/health`, `/ui`, cloud list, and cloud search all returned `200`.
- Cloud UI bundle profile removed the previous heavy ML directories for `torch`, `transformers`, `cv2`, `sklearn`, `scipy`, and `PIL` from the app bundle.
- Assisted handoff runbook: `docs/MACOS_PERSONAL_RUNTIME_ALPHA_HANDOFF.md`.

Latest installed-app demo completeness gate, 2026-06-04 KST:

- Report: `docs/reports/Installed_App_Demo_Completeness_Gate_2026-06-04.md`.
- Installed app: `/Applications/Lattice.app` replaced with the current cloud UI bundle.
- Installed launcher: `/Applications/Lattice Launcher.app` regenerated and ad-hoc signed.
- Native app direct launch: `open /Applications/Lattice.app` starts the AppKit/WKWebView shell, returns `/health=200`, and renders `/ui` inside the app window.
- Bundle shape: `Contents/MacOS/Lattice` is the native WebView launcher; `Contents/MacOS/LatticeRuntime` is the PyInstaller runtime used by both the app shell and compatibility launcher.
- Browser boundary: the native launcher starts `LatticeRuntime start --no-open`, so the primary installed-app path no longer opens Safari/Chrome/Whale for the app surface.
- Installed settings smoke: `scripts/run_macos_installed_settings_smoke.sh` passed with `health_status=200`, `ui_status=200`, and `settings_status=200`.
- Settings UI bundle check confirmed `Google Gemini` and `Test live call`.
- The installed settings smoke unsets provider API key env vars and does not invoke `/runtime-settings/llm/test`; live provider calls remain explicit user actions only.
- Release zip was regenerated at `dist/release/Lattice-macos-arm64.zip`, about `95M`.
- Release zip SHA256: `522e5693a20bd7f9c96383d044d9416669d5c80e4c25b77d2377194308e21b9e`.
- Assisted launcher zip SHA256: `1a6472ed64ea99b241a602a56fe20fd877554cce518a42dcca3605c47be3f196`.
- Extracted release zip proof passed with `/health`, `/ui`, cloud list, and cloud search all returning `200`.

Latest final readiness gate, 2026-06-02 KST / 2026-06-02 UTC:

- Command: `PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" scripts/run_gcp_cloud_paper_demo_readiness_gate.sh`
- Result: passed.
- Started at: `2026-06-02T09:50:33Z`.
- Finished at: `2026-06-02T09:50:57Z`.
- Duration: `24` seconds.
- Evidence log: `storage/contest/google_agent_challenge_2026_06_05/final_gate_20260602T095050Z.log`.
- Evidence summary: `storage/contest/google_agent_challenge_2026_06_05/final_gate_summary_20260602T095050Z.json`.
- Cost preflight: billing enabled, Storage + Firestore enabled, Cloud Run/Cloud Tasks not enabled.
- Real PDF rehearsal: passed with `paper_mock_000001`, `upload_mode=backend_mediated`, `processing_status=ready`, and `public_redaction=passed`.
- Release manifest/hash: passed for `dist/release/Lattice-macos-arm64.zip`.
- Packaged app proof: `/health`, `/ui`, cloud list, and cloud search returned `200`.
- Extracted release zip proof: `/health`, `/ui`, cloud list, and cloud search returned `200`.
- Fallback remains: `PAPERPIPE_CLOUD_METADATA_STORE=memory` and `PAPERPIPE_CLOUD_ADAPTER=mock`.

Installer honesty boundary:

- This is suitable for an assisted local demo on the maintainer machine.
- It is not a Gatekeeper-ready public installer until Developer ID signing, notarization, stapling, and `spctl` acceptance pass.
- Bundle size and native dependency surface are now demo-appropriate for the cloud UI package; broader public distribution still requires the Gatekeeper path above.

Latest controlled Firestore + GCS smoke, 2026-06-01:

- Runtime: `PAPERPIPE_CLOUD_ADAPTER=gcs`, `PAPERPIPE_CLOUD_METADATA_STORE=firestore`, project `knudc-a01068202087`, demo buckets configured, collection `cloud_papers_demo`.
- Flow: upload intent -> Firestore pending metadata -> backend-mediated source PDF upload -> completion/source checksum verification -> page artifact write/read -> cloud page search.
- Result: passed.
- Upload mode: `backend_mediated`.
- Demo paper id in the smoke process: `paper_mock_000001`.
- Processing status after completion: `ready`.
- Public page schema: `cloud_page_artifact_public.v1`.
- Search query smoke: `processed page text`.
- Firestore document check: `cloud_papers_demo/paper_mock_000001` exists with `upload_status=ready`, `processing_status=ready`, and `lab_id=lab_001`.
- Redaction check: passed for public response text against GCS refs, signed URLs, service accounts, credentials, absolute local paths, and internal object-ref fields.
- Caveat: keep `PAPERPIPE_CLOUD_METADATA_STORE=memory` and `PAPERPIPE_CLOUD_ADAPTER=mock` as fallback switches for the stage demo.

Optional if time remains:

- Cloud Tasks dispatch DTO and local enqueue stub.
- Cloud Run worker deployment dry-run checklist.

## What Is Still Possible Without Cloud Run/Cloud Tasks

This is the current implementation lane for the Friday demo:

- Keep the installed program lightweight by using cloud metadata/page APIs from the existing UI.
- Store the demo PDF and page artifact in GCS.
- Store durable demo metadata in Firestore.
- Build the page artifact through the current backend-mediated processing path.
- Prove redaction at the public FastAPI boundary.
- Rehearse the same flow repeatedly with `scripts/cloud_paper_demo_rehearsal_smoke.py`.
- Use Cloud Run/Cloud Tasks only as the named next production gate, not as a stage-demo claim unless separately deployed and smoke-tested.

## Presentation Script Boundary

Use the one-page stage operator sheet for the live run:

- `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md`

Say:

- "The installed UI is light; cloud storage and processing produce reusable page artifacts."
- "The page artifact is redacted before it reaches the browser."
- "Search can find processed cloud page text without promoting it to canonical evidence."
- "Firestore, Cloud Run, and Cloud Tasks are the accepted production path; today we are showing the controlled pilot path."

Do not say:

- "This is production multi-tenant auth."
- "Every downstream artifact is cloud-native."
- "Cloud page text is canonical evidence."
- "The browser directly accesses GCS."

## Remaining Production Gates

- Deploy and verify Cloud Run page worker.
- Add Cloud Tasks dispatch and retry/dead-letter policy.
- Replace beta headers with real user/session/lab/device identity.
- Add durable audit and retention/delete APIs.
