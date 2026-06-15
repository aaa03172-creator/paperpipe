#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PAPERPIPE_GCP_PROJECT_ID:-knudc-a01068202087}"
RAW_BUCKET="${PAPERPIPE_GCS_RAW_PDF_BUCKET:-paperpipe-raw-pdf-dev-knudc-a01068202087}"
PAGE_BUCKET="${PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET:-paperpipe-page-artifacts-dev-knudc-a01068202087}"

echo "== PaperPipe cloud paper demo cost preflight =="
echo "Project: ${PROJECT_ID}"
echo

echo "== Active account =="
gcloud auth list --filter=status:ACTIVE --format="value(account)" || true
echo

echo "== Billing link =="
gcloud billing projects describe "${PROJECT_ID}" --format="table(billingEnabled,billingAccountName)" || true
echo

echo "== Enabled services relevant to demo =="
gcloud services list \
  --enabled \
  --project="${PROJECT_ID}" \
  --format="value(config.name)" \
  | grep -E "^(firestore|storage|run|cloudtasks|artifactregistry|cloudbuild)\\.googleapis\\.com$" \
  || true
echo

echo "== Demo buckets =="
gcloud storage buckets list \
  --project="${PROJECT_ID}" \
  --format="table(name,location,storageClass)" \
  | grep -E "(${RAW_BUCKET}|${PAGE_BUCKET})" \
  || true
echo

echo "== Firestore databases =="
if ! gcloud firestore databases list --project="${PROJECT_ID}" --format="table(name,locationId,type)"; then
  echo "Firestore database list failed. Do not create the database until IAM and location are confirmed."
fi
echo

echo "== Recommended stage-demo defaults =="
cat <<EOF
PAPERPIPE_CLOUD_ADAPTER=gcs
PAPERPIPE_CLOUD_METADATA_STORE=firestore
PAPERPIPE_GCP_PROJECT_ID=${PROJECT_ID}
PAPERPIPE_GCS_RAW_PDF_BUCKET=${RAW_BUCKET}
PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET=${PAGE_BUCKET}
PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION=cloud_papers_demo

Cost guardrail:
- Keep Cloud Run min instances at 0 if deployed.
- Keep Cloud Tasks queue paused/unused unless worker smoke is intentional.
- Keep only demo PDFs in the dev buckets.
- Roll back to PAPERPIPE_CLOUD_METADATA_STORE=memory if Firestore read/write smoke fails.
EOF
