# GCP Cloud Paper Roadmap Implementation Audit

Status: Current-state audit with assisted launcher packaging improvement
Date: 2026-06-02
Roadmap: `docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md`
Readiness: `docs/GCP_CLOUD_PAPER_CHALLENGE_DEMO_READINESS_2026-06-01.md`

## Bottom Line

The current implementation is suitable for the Google Agent Challenge assisted
alpha demo. It proves the installed/light UI path, GCS + Firestore demo storage,
redacted cloud paper APIs, page artifact search/read, and a native-like icon
launcher workflow.

It is not yet a production or public-distribution implementation. The main
remaining roadmap gaps are first-class production auth/device registration,
Cloud Run or queue-backed page processing, public macOS signing/notarization,
model-backed AI/DeepRead parity, and stronger local hydration/product parity
beyond the rehearsed demo path.

## Roadmap Coverage

| Roadmap promise | Current evidence | Status |
| --- | --- | --- |
| Installed app remains user-facing client/UI shell | `dist/Lattice.app`, `/ui` proof, assisted `Lattice Launcher.app` artifact | Demo-ready |
| PDF originals stored in GCP | GCS demo buckets and rehearsal smoke documented in readiness gate | Demo-ready |
| Server-side page artifact generation | backend-mediated demo processor writes reusable cloud page artifact | Demo-ready, production worker deferred |
| UI reads cloud PDF/page state | cloud list/search/detail APIs, draft cloud-page summary API, and frontend mock/e2e coverage | Demo-ready |
| Public responses redact cloud internals | cloud API/proof checks reject GCS refs, signed URLs, service account refs, bucket leaks | Demo-ready |
| Download/hydrate local bundle | schema/service/tests exist for hydration manifest and conflict/stale behavior | Partial |
| Authenticated device access | header-derived role/device/download policy exists; production identity/device enrollment deferred | Partial |
| Agent-ready foundations | stable ids, provenance, payload class, permissions, tool capability filtering covered by schemas/tests | Partial |
| Existing AI/summary cloud-page input bridge | `/cloud/papers/{paper_id}/summary` derives a draft summary from public page blocks with source-block provenance | First slice done |
| Public macOS distribution | ad-hoc/local signing only; `spctl` rejects | Not ready |

## Improvement Applied

The assisted alpha release path now emits a reproducible native-like launcher
artifact:

- `dist/release/Lattice Launcher.app`
- `dist/release/Lattice-macos-arm64.launcher.zip`
- launcher SHA256: `5152a4c3c4d800d4e8a221a8026be69c28c49678511cd6c93d43572049313e81`

`scripts/release_macos_personal_runtime.py` records this artifact in the release
manifest for assisted alpha releases. `scripts/run_macos_alpha_zip_cloud_demo_proof.sh`
now verifies the launcher zip hash, app structure, executable bit, and icon
resource before running the extracted app cloud proof.

Current main release zip SHA256:

`068c8977fa14b3f093f19040bd52b12cb7d5dc95af1a3dc1c356fcec929f4d22`

Double-check note:

An initial launcher release artifact pointed at the local build tree instead of
`/Applications/Lattice.app`. The release path now generates the assisted
launcher with `/Applications/Lattice.app` as the launch target and verifies that
the packaged launcher does not contain the local build path.

## Residual Risks

- The launcher is an assisted-alpha convenience wrapper, not a notarized public
  macOS app shell.
- The live GCP path is demo-controlled; Cloud Run/Cloud Tasks style production
  processing is still a production gate.
- Hydration exists as a tested contract but is not yet the dominant end-user
  path for all existing local UI features.
- The draft summary bridge proves cloud page artifacts can feed summary output,
  but full DeepRead/model-backed AI conversion is not complete.
- Role/device access is header/config driven for demo and tests; production
  enrollment and revocation are not complete.
- The app still opens the browser UI rather than embedding a native WebView.

## Recommended Next Goals

1. Production auth/device gate: replace demo headers and `demo-secret` assumptions
   with a bounded authenticated-device contract.
2. Hydration parity gate: prove one downloaded cloud PDF/page bundle can drive
   the existing local paper detail/artifact flow without stale-cache ambiguity.
3. AI/summary parity gate: route one existing DeepRead or model-backed summary
   flow through cloud page artifacts with payload-class policy and source-block
   provenance.
4. Page worker gate: move from demo processor to queue/Cloud Run style processing
   with retry, failure metadata, and orphan cleanup checks.
5. Public macOS gate: Developer ID signing, hardened runtime, notarization,
   stapling, and `spctl` acceptance.
