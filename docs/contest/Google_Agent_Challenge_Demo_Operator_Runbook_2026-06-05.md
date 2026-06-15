# Google Agent Challenge Demo Operator Runbook

Status: Stage-demo operator sheet
Date: 2026-06-05
Use this when: running the assisted macOS alpha demo for the GCP cloud paper/page path
Canonical readiness: `docs/GCP_CLOUD_PAPER_CHALLENGE_DEMO_READINESS_2026-06-01.md`

## Goal

Show that Lattice can be installed and run as a lightweight research UI while GCP stores the source PDF, stores durable paper metadata, produces a reusable page artifact, and returns only redacted page/search/detail data to the local app.

## Demo Paper

- Title: Neuronal APOE4-induced early hippocampal network hyperexcitability in Alzheimer's disease pathogenesis
- DOI: `10.1038/s43587-026-01096-0`
- Expected demo paper id after rehearsal: `paper_mock_000001`
- Search query to use in the UI: `processed page text`

## Before Going On Stage

Run the final gate once:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  scripts/run_gcp_cloud_paper_demo_readiness_gate.sh
```

Expected end state:

- `status=passed`
- real PDF rehearsal: `upload_mode=backend_mediated`, `processing_status=ready`
- downstream registry smoke: `registry_status=available`, `review_status=review_pending`
- release zip hash check: passed
- packaged app proof: `/health`, `/ui`, cloud list, cloud search all `200`
- extracted zip proof: `/health`, `/ui`, cloud list, cloud search all `200`

If the gate fails, do not change GCP live on stage. Use the fallback section below.

## Launch App

Use the packaged app path:

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
PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE="firestore" \
PAPERPIPE_FIRESTORE_DOWNSTREAM_REGISTRY_COLLECTION="cloud_downstream_registry_demo" \
./dist/Lattice.app/Contents/MacOS/Lattice start --host 127.0.0.1 --port 8046
```

Open:

```text
http://127.0.0.1:8046/ui
```

## UI Path

1. Open the paper notes/list UI.
2. Search for `processed page text`.
3. Open the cloud paper result.
4. Show that the page view loads from the cloud page artifact path, while the browser-visible response stays redacted.
5. Mention that the same installed UI can read the authenticated cloud-backed library from another approved machine/device path once production auth is added.

## Say

- "The installed app is intentionally light; the cloud path stores PDFs and returns reusable page artifacts."
- "The browser does not directly access GCS. The backend returns a redacted public contract."
- "For the demo, GCS stores the PDF and page artifact, and Firestore stores durable paper metadata."
- "The downstream registry is stored as review-pending Firestore state, not canonical evidence."
- "Cloud Run and Cloud Tasks are the accepted production worker path, but they are not claimed as live in this stage demo."
- "This is an assisted alpha demo, not a public multi-tenant production release."

## Do Not Say

- "This is production SSO."
- "Cloud Run and Cloud Tasks are already powering the demo."
- "The browser directly reads from GCS."
- "Cloud page text is canonical evidence for every downstream artifact."
- "This zip is a notarized public installer."

## Fallback

If GCP, Firestore, GCS auth, or network access is unstable:

```bash
export PAPERPIPE_CLOUD_METADATA_STORE="memory"
export PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE="memory"
export PAPERPIPE_CLOUD_ADAPTER="mock"
```

Then say:

"The live GCP path is documented and rehearsed, but for stage reliability I am switching to the mock-backed UI contract. The production direction remains GCS + Firestore + Cloud Run worker."

## Current Alpha Artifact

- Release zip: `dist/release/Lattice-macos-arm64.zip`
- SHA256: `068c8977fa14b3f093f19040bd52b12cb7d5dc95af1a3dc1c356fcec929f4d22`
- Launcher zip: `dist/release/Lattice-macos-arm64.launcher.zip`
- Launcher zip SHA256: `5152a4c3c4d800d4e8a221a8026be69c28c49678511cd6c93d43572049313e81`
- Size: about `94M`
- Icon: custom Lattice app icon included
- Signing status: unsigned local alpha
- Notarization status: not notarized
- Security audit: `docs/reports/MacOS_Alpha_Install_Package_Security_Audit_2026-06-01.md`
- Remaining public distribution blockers: Developer ID signing, Apple notarization, stapling, and `spctl` acceptance
- Bundle slimming status: mitigated for the cloud UI demo package
