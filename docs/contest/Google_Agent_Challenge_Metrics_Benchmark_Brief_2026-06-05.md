# Google Agent Challenge Metrics And Benchmark Brief

Status: Presentation-prep brief
Date: 2026-06-02
Event target: Google Agent Challenge finals, 2026-06-05
Roadmap: `docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md`
Demo readiness: `docs/GCP_CLOUD_PAPER_CHALLENGE_DEMO_READINESS_2026-06-01.md`
Operator runbook: `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md`

## Bottom Line

For the finals presentation, the safest quantitative story is:

1. Demo infrastructure and redaction readiness are strongly evidenced.
2. Installable macOS alpha packaging is evidenced, but not public-distribution ready.
3. Paper-understanding benchmark infrastructure exists with real goldset splits and scorecard comparison outputs.
4. The quality benchmark should be framed as a measurement system and active repair loop, not as a solved accuracy claim.

Do not present this as production multi-tenant auth, a notarized public installer, or a Cloud Run/Cloud Tasks powered demo unless those paths are separately deployed and smoke-tested before the event.

## Stage-Safe Quantitative Claims

| Area | Number / result | Source | Safe phrasing |
| --- | ---: | --- | --- |
| Event target | 2026-06-05 | `docs/GCP_CLOUD_PAPER_CHALLENGE_DEMO_READINESS_2026-06-01.md` | "This is the June 5 finals demo scope." |
| Demo PDF size | 8,460,622 bytes | readiness doc | "The demo is rehearsed on a real 34-page open-access Nature Aging paper." |
| Demo PDF pages | 34 | readiness doc | "The pipeline handles a full paper, not just a toy page." |
| Demo PDF checksum | `5f9a0e674db49c1749717ac3502378518c81cef37c780258db317058d3124f40` | readiness doc | "The source PDF is checksum-tracked." |
| Final readiness gate | passed | `storage/contest/google_agent_challenge_2026_06_05/final_gate_20260602T095050Z.log` | "The controlled demo gate passed on 2026-06-02 KST / 2026-06-02 UTC." |
| Gate duration | 24 seconds | gate log, start `09:50:33Z`, finish `09:50:57Z` | "The final scripted gate completed in about 24 seconds." |
| GCP smoke | passed | readiness doc | "GCS plus Firestore upload, completion, page artifact read, and search passed." |
| Public redaction | passed | readiness doc | "Public responses were checked against GCS refs, signed URLs, service accounts, credentials, object refs, and absolute local paths." |
| Packaged proof endpoints | `/health`, `/ui`, cloud list, cloud search all `200` | readiness doc | "The packaged app proof hit the core backend and UI routes successfully." |
| Extracted zip proof endpoints | `/health`, `/ui`, cloud list, cloud search all `200` | readiness doc | "The release zip was also extracted and smoke-tested." |
| Current app bundle size | about `194M` | `du -sh dist/Lattice.app` | "The cloud UI alpha app bundle is about 194 MB locally." |
| Current CLI binary size | about `95M` | `du -sh dist/lattice` | "The packaged CLI binary is about 95 MB." |
| Current release zip size | about `95M` | `du -sh dist/release/Lattice-macos-arm64.zip` | "The alpha zip is about 95 MB." |
| Current release zip SHA256 | `522e5693a20bd7f9c96383d044d9416669d5c80e4c25b77d2377194308e21b9e` | `shasum -a 256 dist/release/Lattice-macos-arm64.zip` and manifest | "Use the manifest hash from the latest full readiness gate." |
| Current launcher zip SHA256 | `1a6472ed64ea99b241a602a56fe20fd877554cce518a42dcca3605c47be3f196` | `shasum -a 256 dist/release/Lattice-macos-arm64.launcher.zip` and manifest | "The assisted icon launcher is packaged separately from the main app zip." |
| Current CLI SHA256 | `4fd400baa7b2130c6e1e13e930c212a07fd11fcd07ae5fd7ca7f28d7d688dbfc` | manifest and `shasum` | "The packaged binary is hash-addressable." |
| Signing/notarization | signing disabled, notarization disabled, Gatekeeper assessment null | manifest | "This is an assisted alpha, not a notarized public installer." |
| Cost posture | billing enabled; Storage and Firestore enabled; Cloud Run/Cloud Tasks not enabled in latest preflight | cost guardrail | "The demo uses controlled GCS and Firestore resources; worker infrastructure remains a production gate." |

## Hash Drift Status

Resolved on 2026-06-04 KST after rebuilding the cloud UI alpha with the native
AppKit shell, custom Lattice app icon, and rerunning extracted-zip proof.

- Current manifest and `shasum` zip SHA256: `522e5693a20bd7f9c96383d044d9416669d5c80e4c25b77d2377194308e21b9e`
- Current assisted launcher zip SHA256: `1a6472ed64ea99b241a602a56fe20fd877554cce518a42dcca3605c47be3f196`
- The readiness doc, operator runbook, alpha handoff, and security audit now
  reference this same release hash.
- Latest evidence summary: `storage/contest/google_agent_challenge_2026_06_05/final_gate_summary_20260602T095050Z.json`

After any future app rebuild, rerun:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  scripts/run_gcp_cloud_paper_demo_readiness_gate.sh
```

Then update this brief, the operator runbook, and the alpha handoff to the
resulting manifest hash from `dist/release/Lattice-macos-arm64.manifest.json`.

## Benchmark Evidence

### Goldset Release Readiness

The paper-understanding gold release package exists and is release-ready as an eval/reference artifact:

| Split | Items | Ready | Warnings | Failures | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| seed | 3 | 3 | 0 | 0 | pass |
| eval | 3 | 3 | 0 | 0 | pass |
| holdout | 2 | 2 | 0 | 0 | pass |
| total | 8 | 8 | 0 | 0 | release_ready=true |

Safe phrasing:

"We have a fixed paper-understanding evaluation set with 8 curated paper fixtures split into seed, eval, and holdout. The release-readiness gate passes with no invalid records."

### Evidence Grounding Comparison

The evidence-grounding comparison suite exists and produces 78 compared metrics per split. It should be presented as a measurement and repair loop.

| Split | Items | Runtime artifact coverage | Grounded evidence ratio | Evidence-backed extraction rate | Gold claim precision | Gold claim recall | Locator precision | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| seed | 3 | 1.0 | 1.0 | 0.8889 | 0.3333 | 0.25 | 0.1667 | pass |
| eval | 3 | 1.0 | 1.0 | 1.0 | 0.0 | 0.15 | 0.0 | fail |
| holdout | 2 | 1.0 | 0.8334 | 1.0 | 0.0 | 0.5 | 0.0 | pass |

Safe phrasing:

"We do not only demo a UI. We already have a benchmark harness that scores evidence grounding against fixed paper fixtures, including claim recall, evidence support, locator precision, and failure taxonomy. The current results also show where the system still fails, especially grounding and locator quality on the eval split."

Do not say:

- "The paper-understanding benchmark proves high accuracy."
- "Claim extraction is solved."
- "The gold-scored evidence metrics are production-ready."

### External Contract Readiness

The evidence-grounding external contract compatibility audit reports:

- artifact_count: 65
- pass_count: 65
- warn_count: 0
- fail_count: 0
- external_contract_ready: false

The separate readiness gate still has 2 blockers:

- missing explicit reviewer approval reference
- missing explicit external contract opt-in

Safe phrasing:

"The scorecard artifacts are schema-compatible across 65 checked artifacts, but we intentionally block external-contract promotion until explicit human approval and opt-in."

## Slide-Ready Claims

- "Local app, cloud papers: the installed UI stays light while GCS stores PDFs and page artifacts and Firestore stores durable demo metadata."
- "Backend-mediated upload: the browser never needs service-account keys, bucket refs, signed URLs, or direct GCS access."
- "The demo gate checks the full path: upload intent, backend upload, checksum completion, page artifact write/read, search, redaction, packaged app routes, and extracted zip routes."
- "Quality is measured, not hand-waved: an 8-paper fixed goldset and scorecard comparison suite already expose claim/evidence/locator failures."
- "This is a controlled internal pilot. Production gates remain Cloud Run worker deployment, Cloud Tasks dispatch, first-class auth, retention/delete, durable audit, and public installer signing/notarization."

## Final Prep Actions

1. Rerun the final readiness gate with the selected demo PDF and update the runbook hash to the resulting manifest.
2. Keep the stage script centered on infrastructure proof and redaction proof, not quality-overclaim.
3. If benchmark metrics appear in slides, use the benchmark table above with the caveat that current gold-scored quality is an active repair loop.
