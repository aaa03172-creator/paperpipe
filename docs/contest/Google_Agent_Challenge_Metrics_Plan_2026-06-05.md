# Google Agent Challenge Metrics Plan

Status: Planning brief
Date: 2026-06-02
Event target: Google Agent Challenge finals, 2026-06-05
Companion brief: `docs/contest/Google_Agent_Challenge_Metrics_Benchmark_Brief_2026-06-05.md`
Roadmap: `docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md`
Readiness: `docs/GCP_CLOUD_PAPER_CHALLENGE_DEMO_READINESS_2026-06-01.md`
Operator runbook: `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md`

## Goal

Prepare a quantitative story that is strong enough for the finals stage without overstating production readiness or paper-understanding accuracy.

The metrics should prove four things:

1. A real paper can travel through the cloud-paper demo path.
2. The installed app can read cloud-backed paper/page state through redacted FastAPI contracts.
3. The alpha package can be launched and smoke-tested from both built app and release zip.
4. Paper-understanding quality is measured with fixed goldsets and scorecards, even where current quality still fails.

## Metric Buckets

### Bucket A. Demo Reliability

Use these to show that the demo path is repeatable.

| Metric | Why it matters | Current source | Status |
| --- | --- | --- | --- |
| readiness gate status | One top-level stage-safe proof | `scripts/run_gcp_cloud_paper_demo_readiness_gate.sh` stdout | available |
| readiness gate duration | Shows rehearsal is fast and scriptable | derived from gate `started_at` / `finished_at` | available manually; automate JSON later |
| step pass/fail: cost preflight, rehearsal, hash, packaged proof, zip proof | Shows failure isolation | gate script | available as stdout; automate JSON later |
| rollback mode | Shows stage resilience | gate/runbook docs | available |
| fallback adapter pair | Gives operator a safe switch | `PAPERPIPE_CLOUD_METADATA_STORE=memory`, `PAPERPIPE_CLOUD_ADAPTER=mock` | available |

Recommended stage claim:

"The whole controlled gate is scripted: cost preflight, real PDF rehearsal, manifest/hash check, packaged app proof, and extracted zip proof."

### Bucket B. Real Paper / Cloud Processing

Use these to show this is not a toy input.

| Metric | Why it matters | Current source | Status |
| --- | --- | --- | --- |
| PDF pages | Full-paper credibility | readiness doc | available: 34 |
| PDF size | Real upload size | rehearsal JSON and readiness doc | available: 8,460,622 bytes in readiness doc |
| PDF SHA256 | Source integrity | rehearsal JSON and readiness doc | available |
| upload mode | Browser does not directly write to GCS | rehearsal JSON | available: `backend_mediated` |
| processing status | End state | rehearsal JSON | available: `ready` |
| page schema version | Contract stability | rehearsal JSON | available: `cloud_page_artifact_public.v1` |
| page block count | Minimal page artifact substance | rehearsal JSON | available from script; should record final value |
| search hit ids | Search proof | rehearsal JSON | available |
| Firestore document status | Durable metadata proof | rehearsal JSON | available |

Recommended stage claim:

"The demo rehearses a 34-page Nature Aging paper with checksum-tracked upload, backend-mediated storage, a public page artifact contract, and Firestore-backed ready metadata."

### Bucket C. Redaction And Security Boundary

Use these to show that the architecture is not leaking cloud internals.

| Metric | Why it matters | Current source | Status |
| --- | --- | --- | --- |
| public redaction result | Trust boundary proof | rehearsal JSON | available: `passed` |
| forbidden terms checked | Explains what redaction means | `scripts/cloud_paper_demo_rehearsal_smoke.py` | available |
| list/search redaction proof | Browser-visible route proof | packaged proof script | available as pass/fail |
| API status codes | Route health | packaged/zip proof scripts | available |
| auth boundary | Browser/API-key same-origin posture | tests and production gate | available as contract, not production SSO |

Current forbidden terms in rehearsal:

- `gcs_pdf_object_ref`
- `gcs_page_artifact_object_ref`
- `gs://`
- `signed_url`
- `service_account`
- `/Users/`
- `storage/artifacts`
- raw/page bucket names as extra terms

Recommended stage claim:

"The browser-visible payloads are checked for GCS refs, signed URLs, service-account markers, credentials, bucket names, and local paths."

### Bucket D. Package And Distribution Honesty

Use these to show installability without pretending public distribution is done.

| Metric | Why it matters | Current source | Status |
| --- | --- | --- | --- |
| app bundle size | Packaging footprint | `du -sh dist/Lattice.app` | available |
| CLI binary size | Runtime footprint | `du -sh dist/lattice` | available |
| release zip size | Shareable artifact footprint | `du -sh dist/release/Lattice-macos-arm64.zip` | available |
| release zip SHA256 | Artifact integrity | manifest + `shasum` | available; current verified hash is `068c8977fa14b3f093f19040bd52b12cb7d5dc95af1a3dc1c356fcec929f4d22` |
| signed/notarized flags | Honesty boundary | manifest | available: disabled |
| Gatekeeper assessment | Public install blocker | manifest | available: null |
| packaged app proof HTTP statuses | Launch proof | packaged proof script | available |
| extracted zip proof HTTP statuses | Release artifact proof | zip proof script | available |

Recommended stage claim:

"This is an assisted macOS alpha package with hash-checked release zip proof, not a notarized public installer."

### Bucket E. Cost And Cloud Posture

Use these to show disciplined cloud use.

| Metric | Why it matters | Current source | Status |
| --- | --- | --- | --- |
| billing linked | Cost awareness | cost preflight doc/script | available |
| enabled services | Scope control | cost preflight stdout | available |
| bucket region | Data locality and setup clarity | cost guardrail | available |
| Firestore location/type | Metadata durability | cost guardrail | available |
| Cloud Run/Cloud Tasks enabled? | Prevents overclaim | cost guardrail/preflight | available: not enabled in latest preflight |
| object/write count estimate | Cost intuition | cost guardrail | approximate only |

Recommended stage claim:

"The demo uses controlled GCS and Firestore resources; Cloud Run and Cloud Tasks remain the accepted production worker path, not a live stage claim."

### Bucket F. Paper-Understanding Benchmark

Use these to show seriousness about scientific quality.

| Metric | Why it matters | Current source | Status |
| --- | --- | --- | --- |
| fixed goldset item count | Evaluation scope | release readiness JSON | available: 8 |
| split counts | Eval hygiene | release readiness JSON | available: seed 3, eval 3, holdout 2 |
| release readiness | Goldset validity | release readiness JSON | available: pass/release_ready |
| compared metric count | Benchmark breadth | comparison reports | available: 78 per split |
| runtime artifact coverage | Pipeline completeness proxy | comparison reports | available |
| grounded evidence ratio | Grounding proxy | comparison reports | available |
| evidence-backed extraction rate | Extraction lineage proxy | comparison reports | available |
| gold claim precision/recall | Actual quality signal | comparison reports | available but weak |
| locator precision | Reviewability signal | comparison reports | available but weak |
| failure taxonomy counts | Repair direction | comparison reports | available |

Recommended stage claim:

"We already measure paper-understanding against fixed goldsets. Current metrics are honest: the harness exposes grounding and locator failures rather than hiding them."

Do not claim:

- high paper-understanding accuracy
- production-ready gold-scored metrics
- solved claim extraction

## Gaps To Close Before The Presentation

### P0. Final Artifact Hash Consistency

Problem:

- A prior `dist/release/Lattice-macos-arm64.zip` SHA256 drift was found and corrected in the current docs.
- The remaining risk is future drift after any package rebuild.

Plan:

1. Rerun the final gate with the selected demo PDF.
2. Read `dist/release/Lattice-macos-arm64.manifest.json`.
3. Update the operator runbook and metrics brief to the final manifest hash.
4. Do not cite an old SHA on stage.

### P1. Single Machine-Readable Final Gate Summary

Problem:

- The rehearsal script can emit JSON, but the top-level gate and packaged proofs mainly emit stdout.

Plan:

1. Add optional `--json-out <path>` to `scripts/run_gcp_cloud_paper_demo_readiness_gate.sh`.
2. Capture:
   - started_at / finished_at / duration_seconds
   - each step status
   - rehearsal summary JSON
   - release zip hash/signing/notarization fields
   - packaged proof statuses
   - zip proof statuses
   - fallback settings
3. Keep it as a review/gate artifact under `storage/` or a temporary operator path, not canonical runtime state.

### P1. Step-Level Timing

Problem:

- "24 seconds" can be derived from the latest gate, but per-step time is not recorded.

Plan:

1. Wrap each gate step with a small timing helper.
2. Record `duration_seconds` for cost preflight, rehearsal, hash check, packaged proof, and zip proof.
3. Use medians only if the gate is run at least 3 times under similar conditions.

### P1. Rehearsal Payload Size And Page Substance

Problem:

- The rehearsal emits PDF size and page block count, but the final docs should cite the latest run value.

Plan:

1. Run `uv run --extra cloud python scripts/cloud_paper_demo_rehearsal_smoke.py --json`.
2. Capture:
   - `pdf_size_bytes`
   - `pdf_sha256`
   - `page_block_count`
   - `search_hit_ids`
   - `firestore.upload_status`
   - `firestore.processing_status`
3. Add those values to the final metrics brief after the last rehearsal.

### P2. Cost Estimate

Problem:

- Current cost language is "tiny but real"; it does not quantify operations.

Plan:

1. Add a conservative operation-count table:
   - one source PDF object write
   - one page artifact object write
   - at least one page artifact read
   - small Firestore reads/writes for pending/ready status
2. Avoid dollar claims unless current Google pricing is checked on the day of presentation.
3. Keep the core stage claim as cost-bounded posture, not formal cost guarantee.

### P2. Quality Benchmark Caveat Slide

Problem:

- The goldset/scorecard numbers can impress, but they can also expose weak quality if framed badly.

Plan:

1. Use goldset size/splits as the main benchmark claim.
2. Use scorecard metrics as "measurement maturity" rather than "accuracy win."
3. If showing the table, include the eval split failure honestly.
4. Emphasize next repair target: grounding checker and locator precision.

## Command Plan

Run before final slide lock:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  scripts/run_gcp_cloud_paper_demo_readiness_gate.sh
```

Run to capture rehearsal JSON only:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  uv run --extra cloud python scripts/cloud_paper_demo_rehearsal_smoke.py --json
```

Run to verify current release hash:

```bash
shasum -a 256 dist/release/Lattice-macos-arm64.zip
jq '.hashes.release_zip_sha256, .signing.enabled, .notarization.enabled, .gatekeeper_assessment' \
  dist/release/Lattice-macos-arm64.manifest.json
```

Run to verify current package sizes:

```bash
du -sh dist/Lattice.app dist/lattice dist/release/Lattice-macos-arm64.zip
```

Run to summarize goldset readiness:

```bash
jq '.release_readiness | {item_count, ready_count, release_ready, split_summaries}' \
  goldset/reviews/paper_understanding_gold_reviewer_handoff_release_prep/release_package.json
```

## Slide Plan

### Slide 1. Real Demo Path

Metrics:

- 34-page PDF
- PDF SHA256
- backend-mediated upload
- processing status ready
- Firestore document ready
- public page schema version

Message:

"Installed UI, cloud-backed papers, redacted FastAPI contract."

### Slide 2. Redaction And Reliability Gate

Metrics:

- gate pass
- gate duration
- route status `200`
- public redaction pass
- forbidden terms checked

Message:

"We can rehearse the whole path and prove browser-visible payloads do not leak cloud internals."

### Slide 3. Alpha Package Honesty

Metrics:

- app/CLI/zip size
- zip SHA256
- signing disabled
- notarization disabled
- packaged and extracted proof statuses

Message:

"Assisted alpha package works; public installer gates remain explicit."

### Slide 4. Benchmark And Repair Loop

Metrics:

- 8 fixed goldset items
- seed/eval/holdout split
- 78 compared metrics per split
- example proxy metrics
- explicit weak gold-scored metrics

Message:

"Quality is measured with goldsets and scorecards; current failures guide the next repair sprint."

## PR-Sized Follow-Ups

1. Add `--json-out` and step-level timing to the final readiness gate.
2. Add a generated final metrics summary artifact after each gate run.
3. Add a small benchmark-summary exporter that prints only stage-safe goldset/scorecard metrics with caveats.
