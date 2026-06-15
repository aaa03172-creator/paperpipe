#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

PDF_PATH="${PAPERPIPE_DEMO_PDF_PATH:-}"
RUN_REHEARSAL=1
RUN_REGISTRY_SMOKE=1
RUN_COST_PREFLIGHT=1
RUN_PACKAGED_PROOF=1
RUN_ZIP_PROOF=1

usage() {
  cat <<'EOF'
Usage:
  scripts/run_gcp_cloud_paper_demo_readiness_gate.sh [--pdf-path /path/to/demo.pdf] [options]

Runs the final Google Agent Challenge demo readiness gate:
  1. GCP cost/resource preflight
  2. real PDF GCS+Firestore FastAPI rehearsal
  3. packaged Lattice.app cloud proof
  4. extracted alpha release zip cloud proof
  5. release manifest and zip hash checks

Options:
  --pdf-path PATH         Demo PDF path. Defaults to PAPERPIPE_DEMO_PDF_PATH.
  --skip-cost-preflight   Skip the gcloud inspection step.
  --skip-rehearsal        Skip the real PDF upload/page rehearsal.
  --skip-registry-smoke   Skip the Firestore downstream registry smoke.
  --skip-packaged-proof   Skip dist/Lattice.app cloud proof.
  --skip-zip-proof        Skip release zip extraction cloud proof.
  -h, --help              Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pdf-path)
      PDF_PATH="$2"
      shift 2
      ;;
    --skip-cost-preflight)
      RUN_COST_PREFLIGHT=0
      shift
      ;;
    --skip-rehearsal)
      RUN_REHEARSAL=0
      shift
      ;;
    --skip-registry-smoke)
      RUN_REGISTRY_SMOKE=0
      shift
      ;;
    --skip-packaged-proof)
      RUN_PACKAGED_PROOF=0
      shift
      ;;
    --skip-zip-proof)
      RUN_ZIP_PROOF=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "${RUN_REHEARSAL}" == "1" && -z "${PDF_PATH}" ]]; then
  echo "Provide --pdf-path or set PAPERPIPE_DEMO_PDF_PATH, or pass --skip-rehearsal." >&2
  exit 2
fi

if [[ "${RUN_REHEARSAL}" == "1" && ! -f "${PDF_PATH}" ]]; then
  echo "Demo PDF not found: ${PDF_PATH}" >&2
  exit 1
fi

step() {
  echo
  echo "==> $1"
}

STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

step "Google Agent Challenge demo readiness gate"
cat <<EOF
started_at=${STARTED_AT}
run_cost_preflight=${RUN_COST_PREFLIGHT}
run_rehearsal=${RUN_REHEARSAL}
run_registry_smoke=${RUN_REGISTRY_SMOKE}
run_packaged_proof=${RUN_PACKAGED_PROOF}
run_zip_proof=${RUN_ZIP_PROOF}
EOF

if [[ "${RUN_COST_PREFLIGHT}" == "1" ]]; then
  step "GCP cost/resource preflight"
  scripts/cloud_paper_demo_cost_preflight.sh
fi

if [[ "${RUN_REHEARSAL}" == "1" ]]; then
  step "Real PDF GCS+Firestore rehearsal"
  PAPERPIPE_DEMO_PDF_PATH="${PDF_PATH}" \
    uv run --extra cloud python scripts/cloud_paper_demo_rehearsal_smoke.py
fi

if [[ "${RUN_REGISTRY_SMOKE}" == "1" ]]; then
  step "Firestore downstream registry smoke"
  uv run --extra cloud python scripts/cloud_downstream_registry_firestore_smoke.py
fi

step "Release manifest and zip hash"
python3 - <<'PY'
from __future__ import annotations

import hashlib
import json
from pathlib import Path

manifest_path = Path("dist/release/Lattice-macos-arm64.manifest.json")
zip_path = Path("dist/release/Lattice-macos-arm64.zip")

if not manifest_path.is_file():
    raise SystemExit(f"missing manifest: {manifest_path}")
if not zip_path.is_file():
    raise SystemExit(f"missing release zip: {zip_path}")

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
expected = manifest.get("hashes", {}).get("release_zip_sha256")
if not expected:
    raise SystemExit("manifest is missing hashes.release_zip_sha256")

digest = hashlib.sha256()
with zip_path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
actual = digest.hexdigest()
if actual != expected:
    raise SystemExit(f"release zip SHA256 mismatch: expected={expected} actual={actual}")

print(f"manifest={manifest_path}")
print(f"release_zip={zip_path}")
print(f"release_zip_sha256={actual}")
print(f"signed={manifest.get('signing', {}).get('enabled')}")
print(f"notarized={manifest.get('notarization', {}).get('enabled')}")
print(f"gatekeeper_assessment={manifest.get('gatekeeper_assessment')}")
PY

if [[ "${RUN_PACKAGED_PROOF}" == "1" ]]; then
  step "Packaged Lattice.app cloud proof"
  scripts/run_macos_personal_runtime_cloud_demo_proof.sh
fi

if [[ "${RUN_ZIP_PROOF}" == "1" ]]; then
  step "Extracted alpha release zip cloud proof"
  scripts/run_macos_alpha_zip_cloud_demo_proof.sh
fi

FINISHED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
step "Demo readiness gate passed"
cat <<EOF
started_at=${STARTED_AT}
finished_at=${FINISHED_AT}
status=passed
fallback=PAPERPIPE_CLOUD_METADATA_STORE=memory PAPERPIPE_CLOUD_ADAPTER=mock
EOF
