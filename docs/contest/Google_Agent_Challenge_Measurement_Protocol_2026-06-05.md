# Google Agent Challenge Measurement Protocol

Status: Measurement and evidence protocol
Date: 2026-06-02
Event target: Google Agent Challenge finals, 2026-06-05
Owner: PaperPipe/Lattice runtime maintainers

Related documents:

- `docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md`
- `docs/GCP_CLOUD_PAPER_CHALLENGE_DEMO_READINESS_2026-06-01.md`
- `docs/GCP_CLOUD_PAPER_DEMO_COST_GUARDRAILS_2026-06-01.md`
- `docs/GCP_CLOUD_PAPER_PRODUCTION_DECISION_GATE_2026-06-01.md`
- `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md`
- `docs/contest/Google_Agent_Challenge_Metrics_Benchmark_Brief_2026-06-05.md`
- `docs/contest/Google_Agent_Challenge_Metrics_Plan_2026-06-05.md`
- `docs/Evidence_Grounding_Performance_Roadmap_2026-05-22.md`

## Purpose

This protocol defines exactly what to measure, how to measure it, where to store the evidence, and how to turn the evidence into finals-stage presentation material.

The goal is not to create a new product spec. The goal is to make the June 5, 2026 presentation quantitatively credible without claiming more than the current code and docs support.

## Layer Classification

All outputs from this protocol are `review/gate artifacts`.

They are not:

- raw source truth
- canonical structured runtime state
- production audit logs
- evidence that paper-understanding accuracy is solved
- authorization to change runtime behavior

Allowed uses:

- final rehearsal proof
- slide-ready metric tables
- demo operator checklist
- post-event follow-up planning

Blocked uses:

- replacing `docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md`
- claiming production auth, production Cloud Run worker, or public notarized installer
- treating cloud page text as canonical scientific evidence
- treating benchmark proxy metrics as production quality guarantees

## Measurement Runs

Run three measurement passes.

### Pass 1. Baseline Evidence Capture

When:

- before slide lock
- after code/doc inspection
- before any final package rebuild

Goal:

- capture current values and detect drift

Commands:

```bash
du -sh dist/Lattice.app dist/lattice dist/release/Lattice-macos-arm64.zip
shasum -a 256 dist/release/Lattice-macos-arm64.zip
jq '.hashes.release_zip_sha256, .signing.enabled, .notarization.enabled, .gatekeeper_assessment' \
  dist/release/Lattice-macos-arm64.manifest.json
jq '.release_readiness | {item_count, ready_count, release_ready, split_summaries}' \
  goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json
```

Expected artifact:

- `storage/contest/google_agent_challenge_2026_06_05/baseline_measurement_<timestamp>.md`

Minimum fields:

- run timestamp
- current git branch and short commit if available
- dirty-worktree note
- package sizes
- release zip SHA256
- manifest SHA256
- signing/notarization/Gatekeeper fields
- goldset readiness summary
- known caveats

### Pass 2. Final Readiness Gate

When:

- after the final demo PDF and package are selected
- before stage rehearsal
- after any rebuild that changes `dist/`

Goal:

- prove the full demo path works end-to-end

Command:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  scripts/run_gcp_cloud_paper_demo_readiness_gate.sh
```

Expected artifact:

- `storage/contest/google_agent_challenge_2026_06_05/final_gate_<timestamp>.log`
- `storage/contest/google_agent_challenge_2026_06_05/final_gate_summary_<timestamp>.json`

Current limitation:

- the gate script currently emits stdout, not a full machine-readable JSON summary.
- until `--json-out` is implemented, capture stdout with `tee` and manually extract the summary.

Interim command:

```bash
mkdir -p storage/contest/google_agent_challenge_2026_06_05
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  scripts/run_gcp_cloud_paper_demo_readiness_gate.sh \
  | tee "storage/contest/google_agent_challenge_2026_06_05/final_gate_$(date -u +%Y%m%dT%H%M%SZ).log"
```

### Pass 3. Rehearsal JSON Capture

When:

- immediately after final readiness gate
- whenever the selected PDF changes

Goal:

- capture the cleanest machine-readable cloud-paper demo metrics

Command:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  uv run --extra cloud python scripts/cloud_paper_demo_rehearsal_smoke.py --json \
  > "storage/contest/google_agent_challenge_2026_06_05/rehearsal_summary_$(date -u +%Y%m%dT%H%M%SZ).json"
```

Expected JSON fields already emitted by the script:

- `status`
- `project_id`
- `metadata_collection`
- `pdf_name`
- `pdf_size_bytes`
- `pdf_sha256`
- `paper_id`
- `upload_mode`
- `processing_status`
- `page_schema_version`
- `page_block_count`
- `search_query`
- `search_hit_ids`
- `firestore.document_exists`
- `firestore.upload_status`
- `firestore.processing_status`
- `firestore.lab_id`
- `public_redaction`

## Metrics To Measure

### 1. Demo Gate Metrics

Purpose:

- prove the demo is repeatable and failure-isolated.

| Metric | Definition | Source | Collection method | Stage use |
| --- | --- | --- | --- | --- |
| `gate_status` | Final gate result, expected `passed` | gate stdout | parse final `status=` line | Say the controlled gate passed |
| `gate_started_at` | UTC start timestamp | gate stdout | parse `started_at=` | Evidence timestamp |
| `gate_finished_at` | UTC finish timestamp | gate stdout | parse `finished_at=` | Evidence timestamp |
| `gate_duration_seconds` | `finished_at - started_at` | derived | compute from timestamps | Show rehearsal speed |
| `cost_preflight_enabled` | Whether preflight ran | gate stdout | parse `run_cost_preflight=` | Explain scope |
| `rehearsal_enabled` | Whether real PDF smoke ran | gate stdout | parse `run_rehearsal=` | Avoid fake pass |
| `packaged_proof_enabled` | Whether built app proof ran | gate stdout | parse `run_packaged_proof=` | Package confidence |
| `zip_proof_enabled` | Whether extracted zip proof ran | gate stdout | parse `run_zip_proof=` | Release confidence |
| `fallback_mode` | Documented fallback env pair | gate stdout/docs | parse final fallback line | Stage resilience |

Good slide phrasing:

"The final gate runs cost preflight, real PDF rehearsal, hash check, packaged app proof, and extracted zip proof."

Bad slide phrasing:

"This proves production readiness."

### 2. Real Paper Metrics

Purpose:

- show the demo handles a real paper with integrity tracking.

| Metric | Definition | Source | Collection method | Stage use |
| --- | --- | --- | --- | --- |
| `pdf_size_bytes` | Byte size of selected demo PDF | rehearsal JSON | emitted directly | Real input size |
| `pdf_sha256` | SHA256 of selected demo PDF | rehearsal JSON | emitted directly | Source integrity |
| `pdf_page_count` | Number of PDF pages | readiness doc or independent PDF tool | record in measurement note | Full-paper proof |
| `doi` | DOI of selected paper | readiness doc | record in measurement note | Scientific specificity |
| `license_note` | Open-access/license posture | readiness doc | record in measurement note | Demo legitimacy |

Preferred evidence:

- use `pdf_size_bytes` and `pdf_sha256` from the rehearsal JSON because they come from the exact PDF bytes used in the smoke.
- use the page count from the readiness doc unless an independent PDF page-count command is added.

Optional page-count command:

```bash
python3 - "/path/to/demo.pdf" <<'PY'
from pathlib import Path
import sys

from pypdf import PdfReader

path = Path(sys.argv[1])
print(len(PdfReader(str(path)).pages))
PY
```

If `pypdf` is unavailable, do not block the demo; cite the documented page count and mark it as doc-sourced.

### 3. Cloud Upload And Processing Metrics

Purpose:

- prove the actual cloud-paper contract path.

| Metric | Definition | Source | Collection method | Stage use |
| --- | --- | --- | --- | --- |
| `upload_mode` | Upload route mode | rehearsal JSON | expected `backend_mediated` | Browser does not directly write GCS |
| `paper_id` | Demo paper identifier from runtime | rehearsal JSON | emitted directly | Traceability |
| `processing_status` | Completion status | rehearsal JSON | expected `ready` | Page artifact available |
| `page_schema_version` | Public page DTO schema | rehearsal JSON | expected `cloud_page_artifact_public.v1` | Stable contract |
| `page_block_count` | Count of public page blocks | rehearsal JSON | emitted directly | Page artifact substance |
| `search_query` | Query used for search smoke | rehearsal JSON | emitted directly | Reproducible UI step |
| `search_hit_ids` | Paper ids returned by search | rehearsal JSON | emitted directly | Search proof |

Good slide phrasing:

"The upload is backend-mediated, processing reaches `ready`, and the local UI reads a redacted public page contract."

Bad slide phrasing:

"The browser uploads directly to GCS."

### 4. Firestore And GCS Posture Metrics

Purpose:

- prove the controlled cloud backend exists while keeping production caveats visible.

| Metric | Definition | Source | Collection method | Stage use |
| --- | --- | --- | --- | --- |
| `project_id` | GCP project used for demo | rehearsal JSON | emitted directly | Scope clarity |
| `metadata_collection` | Firestore collection | rehearsal JSON | emitted directly | Durable metadata location |
| `firestore.document_exists` | Firestore doc check | rehearsal JSON | expected `true` | Metadata proof |
| `firestore.upload_status` | Stored upload status | rehearsal JSON | expected `ready` | Durable state |
| `firestore.processing_status` | Stored processing status | rehearsal JSON | expected `ready` | Durable state |
| `firestore.lab_id` | Lab id stored in request metadata | rehearsal JSON | expected demo lab | Access scoping |
| `enabled_services` | Relevant GCP APIs enabled | cost preflight stdout | capture in log | Cost/scope posture |
| `bucket_locations` | Demo bucket regions | cost preflight stdout or guardrail doc | capture in log | Region clarity |

Do not include bucket names in browser-visible public payload screenshots. Bucket names can appear in operator/internal docs, but the stage redaction claim is that public DTOs do not expose them.

### 5. Redaction Metrics

Purpose:

- prove sensitive cloud/internal details are not in public API responses.

| Metric | Definition | Source | Collection method | Stage use |
| --- | --- | --- | --- | --- |
| `public_redaction` | Rehearsal public payload redaction result | rehearsal JSON | expected `passed` | Trust boundary proof |
| `forbidden_terms_checked` | Count/list of forbidden terms | script source | record list | Explain redaction |
| `upload_intent_redacted` | Upload intent payload check | rehearsal script assertions | pass/fail | Route-level proof |
| `pending_bundle_redacted` | Pending bundle check | rehearsal script assertions | pass/fail | Route-level proof |
| `source_upload_redacted` | Source upload response check | rehearsal script assertions | pass/fail | Route-level proof |
| `completed_bundle_redacted` | Complete-upload response check | rehearsal script assertions | pass/fail | Route-level proof |
| `public_page_redacted` | Page payload check | rehearsal script assertions | pass/fail | Route-level proof |
| `cloud_search_redacted` | Search payload check | rehearsal script assertions | pass/fail | Route-level proof |
| `packaged_list_search_redacted` | Built app list/search payload grep | packaged proof script | pass/fail | Browser-visible route proof |

Forbidden terms currently checked by the rehearsal script:

- `gcs_pdf_object_ref`
- `gcs_page_artifact_object_ref`
- `gs://`
- `signed_url`
- `service_account`
- `/Users/`
- `storage/artifacts`
- demo raw bucket name
- demo page bucket name

Good slide phrasing:

"The public API is checked for GCS refs, signed URLs, service-account markers, bucket names, object refs, and absolute local paths."

Bad slide phrasing:

"No secrets can ever leak."

### 6. Packaged App Metrics

Purpose:

- show the installed/alpha app path is real.

| Metric | Definition | Source | Collection method | Stage use |
| --- | --- | --- | --- | --- |
| `app_bundle_size` | Size of `dist/Lattice.app` | `du -sh` | capture before final gate | Package footprint |
| `cli_binary_size` | Size of `dist/lattice` | `du -sh` | capture before final gate | Runtime footprint |
| `release_zip_size` | Size of alpha zip | `du -sh` | capture before final gate | Shareable artifact size |
| `release_zip_sha256` | SHA256 of alpha zip | manifest and `shasum` | must match | Artifact integrity |
| `cli_binary_sha256` | SHA256 of CLI binary | manifest | record | Artifact integrity |
| `signing_enabled` | Manifest signing flag | manifest | expected `false` for alpha | Honesty |
| `notarization_enabled` | Manifest notarization flag | manifest | expected `false` for alpha | Honesty |
| `gatekeeper_assessment` | Manifest Gatekeeper result | manifest | expected `null` for alpha | Public distribution caveat |

Required check:

- If `release_zip_sha256` in docs differs from the manifest or `shasum`, update the docs after the final gate.

### 7. Packaged Route Proof Metrics

Purpose:

- show the built app and extracted zip both serve the right routes.

| Metric | Definition | Source | Collection method | Stage use |
| --- | --- | --- | --- | --- |
| `health_status` | HTTP status for `/health` | packaged proof stdout | expected `200` | Runtime up |
| `ui_status` | HTTP status for `/ui` | packaged proof stdout | expected `200` | UI served |
| `cloud_list_status` | HTTP status for `/api/cloud/papers` | packaged proof stdout | expected `200` | Cloud list route |
| `cloud_search_status` | HTTP status for `/api/cloud/papers/search` | packaged proof stdout | expected `200` | Search route |
| `expected_paper_id_present` | Search response includes demo paper id | packaged proof assertions | pass/fail | Data continuity |
| `zip_extract_proof_status` | Extracted zip can run same proof | zip proof stdout | pass/fail | Release artifact confidence |

Good slide phrasing:

"Both the built app and the extracted release zip passed `/health`, `/ui`, cloud list, and cloud search checks."

Bad slide phrasing:

"This zip is a production installer."

### 8. Cost Posture Metrics

Purpose:

- show cost discipline without making unverified pricing claims.

| Metric | Definition | Source | Collection method | Stage use |
| --- | --- | --- | --- | --- |
| `billing_enabled` | Billing linked for project | cost preflight stdout | capture | Real-cost awareness |
| `storage_enabled` | Storage API enabled | cost preflight stdout | capture | Scope |
| `firestore_enabled` | Firestore API enabled | cost preflight stdout | capture | Scope |
| `cloud_run_enabled` | Cloud Run API enabled? | cost preflight stdout | should remain not enabled unless worker smoke exists | Prevent overclaim |
| `cloud_tasks_enabled` | Cloud Tasks API enabled? | cost preflight stdout | should remain not enabled unless queue smoke exists | Prevent overclaim |
| `estimated_gcs_writes` | Source PDF + page artifact writes | cost guardrail / script flow | conservative count | Cost intuition |
| `estimated_firestore_ops` | Pending/ready document reads/writes | script flow | conservative estimate | Cost intuition |

Do not put dollar amounts in slides unless current Google pricing is checked on June 5, 2026.

### 9. Goldset Metrics

Purpose:

- show that scientific quality has a fixed evaluation surface.

| Metric | Definition | Source | Collection method | Stage use |
| --- | --- | --- | --- | --- |
| `goldset_id` | Fixed paper-understanding goldset id | release package JSON | jq | Eval identity |
| `goldset_item_count` | Total ready items | release package JSON | jq | Scope |
| `seed_count` | Seed split count | release readiness JSON | jq | Split hygiene |
| `eval_count` | Eval split count | release readiness JSON | jq | Split hygiene |
| `holdout_count` | Holdout split count | release readiness JSON | jq | Split hygiene |
| `invalid_count` | Invalid records | release readiness JSON | expected 0 | Validity |
| `release_ready` | Release readiness flag | release readiness JSON | expected true | Eval artifact readiness |

Good slide phrasing:

"The paper-understanding benchmark has 8 curated fixtures split into seed, eval, and holdout, with release readiness passing."

Bad slide phrasing:

"The benchmark is large enough to prove broad scientific accuracy."

### 10. Evidence Grounding Scorecard Metrics

Purpose:

- show the system measures scientific quality and exposes failures.

| Metric | Definition | Source | Collection method | Stage use |
| --- | --- | --- | --- | --- |
| `compared_metric_count` | Number of compared metrics per split | comparison report JSON | jq | Benchmark breadth |
| `runtime_artifact_coverage_rate` | Input artifact coverage | comparison report JSON | jq | Pipeline completeness |
| `grounded_evidence_ratio` | Ratio of grounded evidence spans | comparison report JSON | jq | Grounding proxy |
| `unresolved_grounding_rate` | Unresolved grounding ratio | comparison report JSON | jq | Failure visibility |
| `evidence_backed_extraction_rate` | Evidence-backed extraction proxy | comparison report JSON | jq | Lineage proof |
| `claim_precision` | Gold-scored claim precision | comparison report JSON | jq | Quality, caveated |
| `claim_recall` | Gold-scored claim recall | comparison report JSON | jq | Quality, caveated |
| `evidence_support_precision` | Gold-scored evidence support precision | comparison report JSON | jq | Quality, caveated |
| `locator_precision` | Gold-scored locator precision | comparison report JSON | jq | Reviewability, caveated |
| `unsupported_claim_rate` | Gold-scored unsupported claim rate | comparison report JSON | jq | Overclaim risk |
| `failed_checks` | Gate failures | comparison report JSON | jq | Repair target |

Required caveat:

- These are eval/reference artifacts, not runtime truth.
- Current gold-scored quality is not strong enough for an accuracy claim.
- The eval split failure should be shown honestly if scorecard numbers are shown.

Recommended stage claim:

"The current scorecard is useful because it tells us where the system fails: grounding, evidence support, and locator precision."

## Material Creation Workflow

### Artifact Folder

Use:

```text
storage/contest/google_agent_challenge_2026_06_05/
```

Suggested files:

```text
baseline_measurement_<timestamp>.md
final_gate_<timestamp>.log
final_gate_summary_<timestamp>.json
rehearsal_summary_<timestamp>.json
package_measurement_<timestamp>.json
benchmark_summary_<timestamp>.json
slide_metrics_table_<timestamp>.md
stage_claims_<timestamp>.md
```

Do not stage this folder unless explicitly requested as part of a validation artifact. It may contain local runtime evidence.

### Final Metrics Table

Create a final table with exactly these columns:

| Claim | Metric | Value | Evidence file | Caveat |
| --- | --- | --- | --- | --- |

Example rows:

| Claim | Metric | Value | Evidence file | Caveat |
| --- | --- | --- | --- | --- |
| Real paper demo | PDF pages | 34 | readiness doc | Doc-sourced unless independently re-counted |
| Redacted cloud route | public redaction | passed | rehearsal summary JSON | Covers configured forbidden terms |
| Alpha package | release zip SHA256 | final manifest hash | manifest + shasum | Must match latest gate |
| Benchmark harness | fixed goldset items | 8 | release package JSON | Eval/reference artifact |
| Quality repair loop | eval split decision | fail | comparison report JSON | Use as honesty/repair signal |

### Slide Assets

Prepare four metric slides.

#### Slide 1. "Real Paper, Cloud Page"

Include:

- PDF pages
- PDF size
- PDF SHA256 short prefix
- upload mode
- processing status
- page schema version
- Firestore ready state

Visual:

```text
PDF -> backend-mediated upload -> GCS source/page artifact -> Firestore metadata -> redacted FastAPI -> installed UI
```

#### Slide 2. "Redaction Gate"

Include:

- public redaction: passed
- forbidden term categories
- endpoint statuses
- search hit includes demo paper id

Visual:

```text
Internal: GCS refs / object refs / bucket names
Public: paper id / status / page blocks / snippets
```

#### Slide 3. "Assisted Alpha Package"

Include:

- app bundle size
- release zip size
- release zip SHA256 short prefix
- signed: false
- notarized: false
- packaged and extracted route proof statuses

Visual:

```text
Built app proof + extracted zip proof
```

#### Slide 4. "Measured Quality, Honest Failures"

Include:

- 8 fixed goldset fixtures
- seed/eval/holdout split
- 78 compared metrics per split
- one good proxy metric
- one weak gold-scored metric
- next repair target

Visual:

```text
Goldset -> scorecard -> failure taxonomy -> repair queue
```

## Draft Slide Copy

### Safe Metric Copy

- "A 34-page real paper is uploaded once and served back as a redacted cloud page artifact."
- "The public API is checked for cloud refs, signed URLs, service-account markers, bucket names, object refs, and local paths."
- "The alpha app and extracted release zip both pass health, UI, cloud list, and cloud search checks."
- "The benchmark is intentionally honest: it exposes grounding and locator failures instead of hiding them behind a fluent summary."

### Forbidden Or Risky Copy

- "Production-ready multi-tenant platform."
- "Cloud Run and Cloud Tasks power the demo."
- "The browser reads directly from GCS."
- "The app is notarized and publicly installable."
- "Paper-understanding accuracy is solved."
- "Cloud page text is canonical scientific evidence."

## Implementation Plan For Better Measurement

### PR 1. JSON Summary For Readiness Gate

Scope:

- `scripts/run_gcp_cloud_paper_demo_readiness_gate.sh`

Change:

- add `--json-out PATH`
- record top-level status and per-step status
- preserve existing stdout behavior

Output schema draft:

```json
{
  "schema_version": "google_agent_challenge_demo_gate.v1",
  "started_at": "2026-06-02T00:00:00Z",
  "finished_at": "2026-06-02T00:00:31Z",
  "duration_seconds": 31.0,
  "status": "passed",
  "steps": [
    {"name": "cost_preflight", "status": "passed", "duration_seconds": 1.2},
    {"name": "real_pdf_rehearsal", "status": "passed", "duration_seconds": 8.4},
    {"name": "release_hash", "status": "passed", "duration_seconds": 0.3},
    {"name": "packaged_proof", "status": "passed", "duration_seconds": 10.1},
    {"name": "zip_proof", "status": "passed", "duration_seconds": 11.0}
  ],
  "release": {
    "zip_path": "dist/release/Lattice-macos-arm64.zip",
    "release_zip_sha256": "...",
    "signed": false,
    "notarized": false,
    "gatekeeper_assessment": null
  },
  "fallback": {
    "PAPERPIPE_CLOUD_METADATA_STORE": "memory",
    "PAPERPIPE_CLOUD_ADAPTER": "mock"
  }
}
```

Verification after this PR is implemented:

```bash
scripts/run_gcp_cloud_paper_demo_readiness_gate.sh --skip-rehearsal --json-out /tmp/gate.json
jq '.schema_version, .status, .steps' /tmp/gate.json
```

### PR 2. JSON Summary For Packaged Proof Scripts

Scope:

- `scripts/run_macos_personal_runtime_cloud_demo_proof.sh`
- `scripts/run_macos_alpha_zip_cloud_demo_proof.sh`

Change:

- add optional `PAPERPIPE_MACOS_CLOUD_DEMO_JSON_OUT`
- write route statuses and redaction result to JSON
- keep stdout summary unchanged

Metrics:

- `health_status`
- `ui_status`
- `cloud_list_status`
- `cloud_search_status`
- `expected_paper_id_present`
- `public_redaction`
- `duration_seconds`

### PR 3. Stage-Safe Benchmark Summary Exporter

Scope:

- new script under `scripts/eval/`

Change:

- read release package JSON and scorecard comparison reports
- output only stage-safe benchmark metrics with caveats

Output:

```json
{
  "schema_version": "google_agent_challenge_benchmark_summary.v1",
  "goldset": {
    "item_count": 8,
    "seed_count": 3,
    "eval_count": 3,
    "holdout_count": 2,
    "release_ready": true
  },
  "scorecard": {
    "compared_metric_count_per_split": 78,
    "splits": [
      {
        "split": "eval",
        "decision": "fail",
        "claim_precision": 0.0,
        "claim_recall": 0.15,
        "locator_precision": 0.0,
        "caveat": "Use as repair signal, not accuracy claim."
      }
    ]
  }
}
```

Verification:

```bash
uv run python scripts/eval/export_google_agent_challenge_benchmark_summary.py \
  --out /tmp/google-agent-benchmark-summary.json
jq '.goldset, .scorecard.splits[] | select(.split=="eval")' /tmp/google-agent-benchmark-summary.json
```

## Final Review Checklist

Before using a number on stage, verify:

- The value comes from the final run, not an older doc.
- The evidence file exists.
- The evidence file does not expose secrets or private local paths in slide material.
- The claim is stage-safe.
- Any benchmark quality number includes the caveat that it is an eval/reference artifact.
- Any production-direction claim says "accepted direction" or "remaining gate" unless deployed and smoke-tested.
- The zip hash in the runbook matches the final manifest.
- Cloud Run/Cloud Tasks are not described as live unless verified live.

## Final Output Package

At slide lock, produce:

```text
docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md
docs/contest/Google_Agent_Challenge_Metrics_Benchmark_Brief_2026-06-05.md
docs/contest/Google_Agent_Challenge_Metrics_Plan_2026-06-05.md
storage/contest/google_agent_challenge_2026_06_05/final_gate_<timestamp>.log
storage/contest/google_agent_challenge_2026_06_05/rehearsal_summary_<timestamp>.json
storage/contest/google_agent_challenge_2026_06_05/slide_metrics_table_<timestamp>.md
```

Only the docs should be considered for normal source control. Storage evidence should remain local unless explicitly requested for a validation package.
