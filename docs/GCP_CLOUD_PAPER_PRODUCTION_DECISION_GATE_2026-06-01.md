# GCP Cloud Paper/Page Production Decision Gate

Status: Accepted direction; production still gated
Date: 2026-06-01
Owner: PaperPipe/Lattice runtime maintainers
Roadmap: `docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md`
Demo cost guardrail: `docs/GCP_CLOUD_PAPER_DEMO_COST_GUARDRAILS_2026-06-01.md`

## Decision Summary

Accepted recommendation for the June 5, 2026 Google Agent Challenge finals demo:

- Internal pilot: use the existing GCS adapter, same-origin/API-key protection, beta lab/device headers, and explicit operator oversight.
- Durable metadata direction: Firestore.
- Page worker direction: Cloud Run.
- Dispatch direction: Cloud Tasks for the first queued worker pilot.
- Auth direction: keep beta auth for the challenge demo, then replace it with first-class user/session/lab identity before production rollout.
- Retention direction: lab-configured retention with explicit delete semantics before real production data.
- Cost posture: billing is enabled; run the demo cost preflight before creating any additional resources.

Do not present the demo as an internet-facing multi-tenant production service. The challenge target is a controlled internal pilot that proves the architecture, user value, and redaction/security boundaries.

## Current Implementation State

Implemented and verified:

- GCS-backed raw PDF upload through backend-mediated multipart upload.
- Raw source object checksum metadata and completion-time object verification.
- GCS/mock page artifact storage adapter boundary.
- In-process page worker boundary with explicit `running`, `ready`, and `failed` transitions.
- Redacted public DTOs for cloud paper bundles, page artifacts, and hydration state.
- Existing Paper Notes index integration for cloud-ready, processing, failed, blocked, read-only, and offline/hydrated states.
- Backend local hydration writer with checksum-tracked manifest and stale-state detection.
- Beta read/hydrate permission policy derived from request headers.
- Best-effort `user_actions` audit rows for cloud status, page read, and hydrate/download actions.

Still not production-grade:

- Cloud paper metadata has an in-memory implementation and a Firestore store wired behind `PAPERPIPE_CLOUD_METADATA_STORE=firestore`. Firestore Native `(default)` now exists in `asia-northeast3`, and the real Firestore + GCS demo smoke passed against `cloud_papers_demo`.
- Page processing is not deployed as Cloud Run, Pub/Sub, or Cloud Tasks infrastructure.
- User/session/lab/device identity is a beta header policy, not production authentication.
- Paper detail viewer parity is partial; Paper Notes index preview is implemented first.
- Retention, deletion, and legal/license policy are not finalized.

## Accepted Decisions And Remaining Gates

| Decision | Required before | Recommended default | Why |
| --- | --- | --- | --- |
| Durable metadata store | Any production or multi-process deployment | Accepted: Firestore | Cloud paper metadata is document-shaped, status-oriented, and naturally keyed by lab/paper/run. |
| Page worker deployment | Replacing in-process processing | Accepted: Cloud Run service | Keeps heavy PDF/page processing isolated from the installed app and API process. |
| Job dispatch | Async processing at scale | Accepted: Cloud Tasks for first pilot; Pub/Sub later if fanout grows | Cloud Tasks gives simpler retries, rate limits, and per-job control for lab-scale uploads. |
| User/session/lab auth | Broad multi-device rollout | Deferred past demo: first-class app user/session + lab membership | Header-derived beta policy is not a security boundary for production. |
| Device authorization | Local hydrate/download on shared devices | Deferred past demo: registered device token or approved session | Hydration writes local PDF/page data and needs a stronger device trust signal. |
| Retention/deletion | Real lab data beyond pilot | Deferred past demo: lab-configured retention with explicit delete semantics | Raw PDFs may have licensing and institutional constraints. |
| Audit durability | Production incident review | Deferred past demo: durable structured audit in DB/Firestore plus cloud logs | Best-effort local `user_actions` is not sufficient for operational accountability. |
| Rollback/deploy path | Any cost-incurring deployment | Required before challenge smoke: written deploy and rollback checklist | Avoids accidental long-running workers, public buckets, or unbounded spend. |

## Pilot Path

Allowed without more user decisions:

1. Keep `PAPERPIPE_CLOUD_ADAPTER=gcs` only on the controlled backend runtime.
2. Keep upload and hydrate backend-mediated.
3. Keep browser calls same-origin only.
4. Keep beta headers behind API-key/same-origin protection.
5. Use only manually supervised lab/internal data.
6. Treat processing as an in-process pilot worker, not production Cloud Run.
7. Record any production-like claim as blocked until durable metadata and auth are implemented.

Challenge demo scope:

- Show cloud PDF upload/read/page artifact/search/detail-viewer flow on controlled demo data.
- Describe Firestore, Cloud Run, and Cloud Tasks as the accepted production direction, not as fully production-complete unless deployed and verified before the event.
- Keep a local/mock fallback route ready for the stage demo.
- Use one pre-verified PDF and one freshly uploaded PDF at most; avoid live debugging with unknown documents during the presentation.

Pilot exit checks:

- Focused cloud API tests pass.
- Frontend build passes.
- Manual upload/read/page/hydrate smoke uses a test PDF.
- No public response contains GCS refs, bucket names, signed URLs, credentials, service-account values, or absolute local paths.

## Production Path

Required implementation sequence:

1. Keep the Firestore-backed `PAPERPIPE_CLOUD_METADATA_STORE=firestore` runtime path green through rehearsal.
2. Move any remaining production metadata/audit state off process-local state.
3. Add a queued page-processing dispatch layer.
4. Deploy worker behind least-privilege service account access.
5. Replace beta headers with real user/session/lab/device authorization.
6. Add durable audit events for upload, process, page read, PDF read, hydrate, delete, and retention actions.
7. Add retention/delete APIs and operator docs.
8. Run independent review for schema, storage, auth, redaction, and failure paths.

## Recommended Defaults

Metadata:

- Choose Firestore first.
- Store one cloud paper document per lab/paper.
- Store processing attempts as subcollection or child records keyed by `run_id`.
- Keep GCS object refs internal only.

Worker:

- Choose Cloud Run first.
- Worker input should include `paper_id`, `lab_id`, `run_id`, source checksum, and internal source object ref.
- Worker output should be `CloudPaperPageArtifactInternal`.
- Worker must not write public DTOs directly; public shape is derived by the API.

Dispatch:

- Choose Cloud Tasks for the first deployment.
- Use one task per paper/run.
- Configure bounded retries and dead-letter handling before real lab data.

Auth:

- Keep current beta headers only for internal pilot.
- Production should derive actor, lab, role, and device trust from a real auth/session layer.

Retention:

- Start with lab-configured retention.
- No automatic deletion until source/page/audit lineage and user-facing delete semantics are implemented.

## Decisions Needed From Operator

Already accepted for the challenge direction:

- Firestore as the first durable metadata store.
- Cloud Run as the first page-worker target.
- Cloud Tasks as the first dispatch mechanism.
- Internal pilot/beta auth for the June 5, 2026 challenge demo.

Not needed immediately for this demo-prep goal:

- Final production Firestore collection names beyond the demo `cloud_papers_demo` collection.
- Exact Cloud Run service name.
- Exact retention duration.
- Institution SSO provider.

Still needed before production conversion:

1. What user/lab identity source will production use?
2. What retention rule applies to raw PDFs?
3. What exact production Firestore collection names and Cloud Run service names will be used?
4. What deploy/rollback commands are approved for cost-incurring infrastructure?

## Hard Stops

Stop and do not deploy if any of these are true:

- Public GCS bucket/object ACLs are required for normal reading.
- Browser state needs service-account keys, bucket names, GCS refs, or long-lived signed URLs.
- Metadata remains process-local while more than one backend process is expected.
- Page processing can mark a paper ready without source checksum verification.
- Hydration can occur without an explicit download permission.
- Retention/delete policy is unknown for real lab PDFs.

## Verification For This Gate

- `git diff --check` for this decision document and the roadmap.
- Focused backend/frontend tests remain the verification for implementation slices; this gate itself is a decision artifact, not a runtime behavior change.
