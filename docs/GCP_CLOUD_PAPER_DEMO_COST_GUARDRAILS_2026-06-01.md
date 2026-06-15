# GCP Cloud Paper Demo Cost Guardrails

Status: Active demo guardrail
Date: 2026-06-01
Target event: Google Agent Challenge finals, 2026-06-05
Project: `knudc-a01068202087`

## Current Cost Posture

Billing is enabled for the project, so real usage can create real charges.

Current checked state:

- Billing link: enabled.
- Enabled demo-relevant services: `firestore.googleapis.com`, `storage.googleapis.com`.
- Not enabled in the latest preflight: Cloud Run, Cloud Tasks, Artifact Registry, Cloud Build.
- Demo GCS buckets:
  - `paperpipe-raw-pdf-dev-knudc-a01068202087`
  - `paperpipe-page-artifacts-dev-knudc-a01068202087`
- Both buckets are in `ASIA-NORTHEAST3`.
- Firestore database: `(default)`, `FIRESTORE_NATIVE`, `asia-northeast3`, free tier reported by `gcloud`.
- Firestore smoke: passed with collection `cloud_papers_demo` and demo document `paper_mock_000001`.

## Safe Demo Defaults

Use this for the Firestore-backed stage demo path:

```bash
export PAPERPIPE_CLOUD_ADAPTER="gcs"
export PAPERPIPE_CLOUD_METADATA_STORE="firestore"
export PAPERPIPE_GCP_PROJECT_ID="knudc-a01068202087"
export PAPERPIPE_GCS_RAW_PDF_BUCKET="paperpipe-raw-pdf-dev-knudc-a01068202087"
export PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET="paperpipe-page-artifacts-dev-knudc-a01068202087"
export PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION="cloud_papers_demo"
```

Use this rollback path if anything looks uncertain:

```bash
export PAPERPIPE_CLOUD_METADATA_STORE="memory"
export PAPERPIPE_CLOUD_ADAPTER="mock"
```

## Preflight Command

Run:

```bash
scripts/cloud_paper_demo_cost_preflight.sh
```

The script only inspects billing linkage, enabled services, demo bucket locations, and Firestore database list state. It does not create resources.

## Rehearsal Smoke Command

Run the real demo smoke only after the preflight output looks expected:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  uv run --extra cloud python scripts/cloud_paper_demo_rehearsal_smoke.py
```

This command does create or overwrite the controlled demo paper record and demo objects for the selected PDF. It should stay limited to the approved demo buckets and Firestore collection:

- raw PDFs: `paperpipe-raw-pdf-dev-knudc-a01068202087`
- page artifacts: `paperpipe-page-artifacts-dev-knudc-a01068202087`
- Firestore collection: `cloud_papers_demo`

Expected cost posture for the command is tiny but real: one source PDF object write, one page artifact object write/read, and a small number of Firestore document reads/writes.

## Cost Guardrails

- Keep the demo to one primary APOE4 PDF and at most one fresh upload during presentation.
- Use `PAPERPIPE_CLOUD_METADATA_STORE=firestore` for the demo only after the real smoke remains green; otherwise roll back to `memory`.
- Do not enable Cloud Run or Cloud Tasks during the stage demo unless there is a clear worker smoke plan.
- If Cloud Run is deployed later, keep minimum instances at `0`.
- If Cloud Tasks is created later, keep the queue paused or unused until worker handling is verified.
- Delete accidental non-demo objects from the dev buckets after rehearsal.
- Do not put service account keys, signed URLs, bucket refs, or GCP object names into browser-visible config or public DTOs.

## Firestore Location Decision

Approved and applied:

- Firestore Native database location: `asia-northeast3`.
- This matches the region family of the existing demo GCS buckets, `ASIA-NORTHEAST3`.

## What Can Still Cost Money

- GCS storage and object operations for uploaded PDFs and page artifacts.
- Firestore document reads/writes/storage after a database is created.
- Cloud Run CPU/memory/request usage if deployed.
- Cloud Tasks operations if queues/tasks are created.
- Network egress outside free/discounted paths.

For this week's demo, expected usage is tiny, but it is not a formal zero-cost guarantee.
