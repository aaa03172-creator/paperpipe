# GCP Cloud Paper/Page Roadmap

Status: Priority implementation roadmap
Date: 2026-05-30
Owner: Runtime/product maintainers

Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/runtime_security_env.md`
- `docs/inference_data_boundary.md`
- `docs/PaperPipe_UI_GRAMMAR.md`

Related surfaces:
- `backend/`
- `frontend/`
- `src/schemas/`
- `storage/artifacts/`
- `docs/API_CHAT_CONTRACT.md`
- `docs/WEB_VIEWER.md`
- `docs/UX_REVIEW_TEMPLATE.md`
- `docs/INDEPENDENT_REVIEW_TEMPLATE.md`
- `docs/working-files.md`

## Purpose

Make cloud-backed PDF storage and server-side page processing the top priority lane.

The target product shape is:

1. The installed PaperPipe/Lattice program remains the user-facing client, local cache, and existing UI shell.
2. PDF originals are uploaded to GCP.
3. GCP processes uploaded PDFs into reusable page artifacts and supporting metadata.
4. The installed program reads cloud PDF/page state and shows it through the existing paper UI.
5. When the user needs local access, the program downloads a complete PDF/page bundle and hydrates it into the existing local artifact shape so current UI features continue to work.

This note is a roadmap, not a replacement master spec. Persisted schemas, API routes, auth flows, and storage changes still need bounded implementation PRs with tests.

## Product Thesis

The installed app should feel like the same research workspace, but its heavy PDF storage and page-building work should be cloud-backed.

In plain terms:

- local app: authenticated client, viewer, local cache, local integrations
- GCP: PDF source storage, page processing backend, cloud page/artifact store
- existing UI: consumes the same paper/page/artifact contract whether data came from local storage or cloud hydration

The strongest user promise is:

> Upload a paper once, let the lab-managed cloud process it, then read and reuse the processed page from any authenticated device.

## Hybrid AI Responsibility Model

Use a hybrid responsibility model for AI and inference features.

The operator-provided baseline should cover the core product promise:

- PDF cloud storage
- page generation
- OCR/text extraction
- basic metadata
- read/search access for processed papers
- permission and device policy

The operator may provide optional AI plans for:

- summaries
- claim/evidence extraction
- paper comparison
- artifact generation
- recommendations or question-answering

Users or labs may connect their own AI backends for:

- user-owned API keys
- lab-managed inference servers
- lab-owned GCP projects
- local models or external analysis tools

Rules:

- page generation is part of the core product promise and should not require each user to configure their own AI backend.
- advanced AI should be optional, policy-gated, and separately priced or configured.
- BYO-AI must not bypass payload classification, auth, redaction, provenance, or evidence-linking rules.
- Provider credentials must remain server-side or in approved local secret storage, never in browser-owned state.
- Output/view modes must not loosen scientific truth policy or create separate agent runtimes.

## Agent-Ready Foundations

This roadmap should lay agent-ready foundations without shipping live autonomous agents in the first MVP.

Future agent features should be optional workflow layers over cloud paper/page state:

- read-only evidence-routed assistant
- draft summary or claim/evidence helper
- draft downstream artifact generator
- policy-gated action helper for export, comparison, or external tools

The first MVP should not require:

- live `/api/chat`
- autonomous agents
- automatic canonical-state edits by agents
- full PDF transfer to public commercial inference providers
- an AI tool marketplace

However, the cloud paper/page contracts should preserve the data needed for safe future agents:

- stable ids: `paper_id`, `cloud_source_id`, `run_id`, `page_id`, `block_id`, `table_id`, `figure_id`
- source locators: page number, text span, bbox, table/figure locator, source PDF checksum
- provenance: upload actor, processor name/version, model/version where applicable, created time, source checksum
- payload class: `local_only`, `lab_allowed`, or `external_allowed`
- permission-derived allowed actions: read page, read PDF, hydrate/download, run optional AI, export, share, delete
- warnings and uncertainty signals
- deterministic block ordering
- audit hooks for read, optional AI run, export, hydrate/download, and generated artifact creation

Raw PDF/page storage and page processing may use lab-managed GCP only when that backend is explicitly approved as inside the lab trust boundary. Full PDF text, raw page images, full structured state, and future agent/inference payloads must still default to the stricter applicable class, usually `local_only`, unless a bounded payload is explicitly minimized and reclassified under `docs/inference_data_boundary.md`.

`run optional AI` permission allows execution, but payload class and redaction policy decide what data may leave the current trust boundary.

Agent audit hooks should use existing event/user-action logging where available. Do not embed append-only histories inside page artifact payloads.

Agent outputs must remain draft-like unless promoted through an explicit lane-owned review contract. A future agent may suggest summaries, claims, evidence links, comparisons, or artifacts, but it must not silently outrank source data, page provenance, or evidence-linked structured state.

## Non-Goals For The First Lane

- Do not build a general workspace platform or generic object registry.
- Do not make browser-owned state hold GCP credentials, provider API keys, or signed private URLs long term.
- Do not replace evidence-linked structured state with a polished cloud page artifact.
- Do not make `/api/chat` live as part of this lane.
- Do not ship autonomous agents in the first MVP.
- Do not add a broad AI tool marketplace in the first implementation.
- Do not make every advanced AI feature operator-provided in the first MVP.
- Do not require every downstream artifact lane to be cloud-native on day one.

## Current Boundary Shift

The current runtime is local-first, paper/job/artifact-first, and single-operator-first. This roadmap intentionally introduces a lab-managed cloud backend for PDF/page storage and processing.

To keep this compatible with current architecture:

- Treat GCP as a source/artifact backend, not a new truth layer for every object in the product.
- Keep FastAPI as the only app-facing API boundary.
- Keep Pydantic schemas in `src/schemas/` as the contract boundary.
- Keep cloud page artifacts traceable back to raw PDF source and processing run metadata.
- Keep downloaded bundles compatible with existing `storage/artifacts/{paper_segment}/{run_id}/` readers.

## Implementation Operating Protocol

Read this section before writing code. It translates the repository rules and prior implementation-plan style into the working loop for this lane.

### Goal-Based Execution Model

Execute this roadmap as a sequence of PR-sized goals, not as one broad MVP goal.

Reason:

- schema, cloud auth, GCS storage, worker processing, local hydration, UI, and device access have different failure modes
- security and data-integrity defects are easier to catch when each goal has one contract boundary
- a completed goal should leave the next goal safer and clearer, not merely larger

Operating loop:

1. Create one narrow goal for the next PR-sized slice.
2. Re-read this roadmap section and the slice-specific starter contract.
3. Do the current-state audit for only that slice.
4. Use TDD for contract-sensitive behavior.
5. Run the smallest relevant verification.
6. Attach a Codex-assisted reviewer when the slice touches schema, auth, cloud refs, storage, hydration, or viewer trust.
7. Fix confirmed findings or record residual risks.
8. Mark the goal complete only when its exit criteria are met.
9. Create the next goal from the updated implementation evidence.

Do not keep a single active goal for the whole MVP. The full MVP should remain the roadmap destination, while active goals stay small enough to review, verify, and roll back.

Recommended goal completion rule:

```text
targeted tests pass + diff check passes + route/security/data-integrity risks are reviewed + residual risks are documented + next goal is scoped from current evidence
```

### Required References Before Implementation

Before opening the first implementation PR, read:

- `AGENTS.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/runtime_security_env.md`
- `docs/inference_data_boundary.md`
- `docs/PaperPipe_UI_GRAMMAR.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/working-files.md`
- the relevant existing route/schema/store files for the PR slice

When a PR touches viewer UX, also read:

- `rules/product-psychology/SKILL.md`
- `rules/product-psychology/references/review-checklist.md`
- `rules/product-psychology/references/bias-framework.md`
- `rules/product-psychology/references/ethics-checklist.md`
- `docs/UX_REVIEW_TEMPLATE.md`

### Current-State Audit Before Each PR

Every PR in this lane should start by checking the current implementation surface instead of assuming the roadmap is complete truth.

For each slice, inspect and record:

- existing route patterns in `backend/main.py` and nearby routers
- existing API-key and same-origin `/api/*` protection behavior
- current Pydantic schema style under `src/schemas/`
- current runtime path helpers and artifact writers
- existing paper note/detail payload shapes consumed by the frontend
- existing tests covering the touched API, schema, auth, or viewer surface
- whether the touched file already has unrelated dirty changes

If implementation evidence conflicts with this roadmap, do not silently follow the roadmap. Patch the roadmap or add a bounded follow-up note before changing runtime behavior.

### Worktree And Branch Hygiene

This is a mixed-risk lane: it touches docs, schemas, backend routes, security, storage, and frontend. Keep PRs narrow.

Rules:

- Use one branch/worktree per PR slice when the main worktree is dirty.
- Stage only files that belong to the current slice.
- Do not stage `storage/`, logs, generated outputs, snapshots, local secrets, or temporary GCP credentials.
- Keep docs-only adoption changes separate from schema/API/runtime changes unless the PR is explicitly a contract PR.
- If a file is already dirty from unrelated work, either hunk-stage only the lane changes or move the slice to a clean worktree.

For long-running implementation, create task-local files under `.codex/work/<YYYY-MM-DD>_gcp_cloud_paper_page/`:

```text
plan.md
findings.md
progress.md
```

These working files are not repo truth and should not be staged.

### Test-First Policy

Use TDD strongly for this lane. The first implementation should prove behavior with failing tests before runtime code wherever practical.

Must be test-first:

- Pydantic schemas and public/private DTO redaction
- FastAPI route request/response contracts
- API-key and same-origin `/api/*` auth behavior
- upload completion checksum validation
- state transitions: `pending -> running -> ready`, `pending/running -> failed`, blocked download states
- local hydration write shape and stale-cache detection
- partial-write and failure cleanup behavior
- permission matrix behavior for read, PDF read, download, upload, delete

May use documented verification instead of a new test:

- docs-only wording changes
- UX review report copy
- non-behavioral planning edits

TDD loop:

1. Add the smallest failing test for the contract or failure mode.
2. Implement the narrowest code path behind FastAPI/schema/service boundaries.
3. Run the targeted test.
4. Add a regression test for the most likely security or partial-write failure.
5. Run the smallest relevant smoke/build command before calling the PR ready.

### Review Protocol

Use code-review posture for every non-trivial PR in this lane.

Review must check:

- no browser-owned GCP credentials, provider keys, long-lived signed URLs, or raw local paths
- `/cloud/*` and same-origin `/api/cloud/*` routes are protected consistently
- internal GCS object refs are separated from public response DTOs
- generated page artifacts do not appear stronger than evidence-linked state
- local hydration does not silently overwrite or outrank newer source/checksum state
- failure paths do not leave orphan metadata, partial local bundles, or `ready` status on broken artifacts
- schema changes include compatibility impact and migration/backfill expectations

Use `docs/INDEPENDENT_REVIEW_TEMPLATE.md` for a compact signoff when a PR touches schema, security, storage, hydration, or cloud auth. Use `docs/UX_REVIEW_TEMPLATE.md` and a matching `docs/UX_REVIEW_REPORT_<flow>.md` before UI/flow work is called done.

### Codex-Assisted Reviewer Option

For non-trivial slices, attach a separate Codex review pass when useful. This is recommended, not a replacement for maintainer judgment.

Use a Codex reviewer especially when the PR touches:

- Pydantic schemas or public/private DTO separation
- FastAPI auth, same-origin `/api/*` protection, or route wiring
- GCP object refs, signed URL handling, credential boundaries, or dependency additions
- upload/process/download/hydration failure paths
- local cache writes, stale-cache behavior, or partial-write cleanup
- viewer trust hierarchy, warning display, or user-facing cloud status
- feature parity claims against the matrix in this document

Reviewer prompt shape:

```text
Review this PaperPipe GCP cloud paper/page PR against docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md, AGENTS.md, docs/runtime_security_env.md, docs/inference_data_boundary.md, and docs/PaperPipe_Minimum_Operating_Principles.md.

Findings first, ordered by severity. Focus on security, data integrity, route auth, public/private DTO leakage, partial writes, stale cache, schema compatibility, and whether generated page artifacts are kept below evidence-linked structured state.

Do not propose broad rewrites unless tied to a concrete correctness, security, data-integrity, or maintainability risk with file/line evidence. Separate confirmed defects from open questions, test gaps, residual risks, and optional cleanup.
```

Expected reviewer output:

- P0/P1/P2 findings with file/line evidence
- open questions and assumptions
- missing tests or verification gaps
- residual risk
- smallest plausible fix direction

Do not accept a Codex reviewer suggestion automatically. Apply only suggestions that are grounded in current code evidence and this roadmap's contracts.

### Situation Rules

Use these rules when the implementation path forks:

| Situation | Required action |
| --- | --- |
| New persisted response shape is needed | Add/update Pydantic schema first, then tests, then route/service code |
| New cloud object reference is needed | Store an opaque internal object ref; expose a public DTO without signed URLs |
| Browser needs upload/download | Prefer backend-mediated access; if signed URLs are used, make them short-lived and never persisted |
| A PDF/page bundle is downloaded locally | Write through a compatibility adapter, record checksum, and mark stale if cloud source changes |
| Processing fails after source upload | Keep source record, mark processing `failed`, store warning/error metadata, and expose retry action |
| Hydration fails midway | Do not mark local cache ready; clean temp files or record a recoverable partial state |
| Existing local artifact and cloud artifact disagree | Prefer explicit stale/conflict status over silent overwrite |
| A user can read a page but not download the PDF | Return page/read payload and hide or disable hydrate/download actions with a policy reason |
| A UI change changes navigation, CTA, empty/error state, or paper detail layout | Create/update the UX review artifact before finishing |
| A GCP SDK or new runtime dependency is proposed | Keep it behind an adapter/config flag and review dependency/security impact before keeping it |

## Layer Classification

| Item | Layer | Canonical posture |
| --- | --- | --- |
| Uploaded PDF in GCS | raw source | source object owned by lab-managed cloud storage |
| PDF checksum, size, content type, upload actor | canonical structured state candidate | must be schema-backed before it becomes runtime truth |
| GCP page artifact | derived artifact | reusable, reviewable, not scientific truth by itself |
| Page manifest | review/gate plus derived artifact metadata | required for hydration and provenance |
| Local downloaded PDF/page bundle | local cache / mirrored source plus derived artifact | must not silently outrank cloud source metadata |
| Existing ClaimSet/evidence state | canonical structured state when promoted through existing contracts | still stronger than generated page display |
| UI rendered page | user-facing artifact/view | presentation only |

## Target Architecture

```text
Installed app / browser UI
  -> same-origin FastAPI backend
    -> Cloud paper API adapter
      -> GCP auth and signed upload/download URLs
      -> GCS raw PDF bucket
      -> GCP page processing job
      -> GCS page artifact bucket
      -> Cloud metadata store
    -> local hydration/cache adapter
      -> storage/artifacts/{paper_segment}/{run_id}/
      -> existing paper/page/artifact readers
```

Frontend must call the local/same-origin backend only. It must not hold GCP service-account credentials or long-lived cloud secrets.

## Core User Flows

### Flow 1. Upload PDF To Cloud

1. User selects a PDF in the installed app.
2. Backend creates a cloud paper upload intent.
3. Backend validates local policy and lab/user permissions.
4. Backend uploads directly or returns a short-lived signed upload URL.
5. GCP stores the PDF and records checksum, actor, lab, paper identity, and upload event.
6. Backend starts a cloud page processing job.

Required first-screen user state:

- `Uploading`
- `Uploaded`
- `Processing page`
- `Ready to open`
- `Action needed`

### Flow 2. Process PDF Into Page On GCP

1. GCP worker reads the uploaded PDF.
2. Worker generates page artifacts.
3. Worker writes page JSON, thumbnails or render assets if adopted, and manifest metadata.
4. Worker records processing warnings, parser version, source checksum, and artifact schema version.
5. Backend exposes the result through existing paper-oriented APIs.

The page artifact must preserve:

- source PDF object id
- source PDF checksum
- run id
- processing version
- page count
- extraction/render warnings
- stable page ids
- artifact schema version

### Flow 3. Return Page To User

1. UI opens the paper detail route.
2. Backend checks auth and paper permission.
3. Backend returns a UI-compatible paper/page payload.
4. Existing viewer surfaces show the processed page without exposing cloud internals.

The user should not need to know bucket names, job ids, or signed URL mechanics during normal reading.

### Flow 4. Download PDF/Page Bundle For Local Use

1. User selects `Download for local use` or opens a paper that needs local hydration.
2. Backend checks whether the user and device can download source PDFs.
3. Backend downloads the cloud PDF, page artifacts, and manifest.
4. Backend writes a local hydrated bundle in a compatibility path.
5. Existing local UI features use the hydrated bundle as if it were locally produced.

Download permissions should be stricter than read permissions when licensing or lab policy requires it.

## Required Contract: CloudPaperBundle

The first schema should be additive and narrow. Suggested Pydantic model name:

- `CloudPaperBundleInternal`
- `CloudPaperBundlePublic`

The internal model may hold cloud object references. The public model must not expose raw signed URLs, service account paths, bucket names when avoidable, or absolute local paths.

Suggested internal fields:

```python
class CloudPaperBundleInternal(BaseModel):
    schema_version: Literal["cloud_paper_bundle.v1"]
    paper_id: str
    lab_id: str
    cloud_source_id: str
    gcs_pdf_object_ref: str
    source_pdf_sha256: str
    source_pdf_size_bytes: int
    source_pdf_content_type: str
    gcs_page_artifact_object_ref: str
    page_artifact_sha256: str
    page_schema_version: str
    run_id: str
    processing_status: Literal["pending", "running", "ready", "failed", "blocked"]
    payload_class: Literal["local_only", "lab_allowed", "external_allowed"]
    created_at: datetime
    updated_at: datetime
    provenance: CloudPaperProvenance
    local_hydration: CloudPaperHydrationState | None = None
```

`payload_class` must be assigned per bundle or per derived payload. Do not hardcode `lab_allowed`; full source-derived payloads should remain `local_only` unless an approved lab-managed backend and minimization rule justify a wider class.

Do not persist actor-specific permissions directly in `CloudPaperBundleInternal`. Derive `CloudPaperBundlePublic` from internal bundle state plus the current actor/session permissions so one cloud bundle can safely serve different roles, devices, and labs without schema drift.

Suggested public fields:

```python
class CloudPaperBundlePublic(BaseModel):
    schema_version: Literal["cloud_paper_bundle_public.v1"]
    paper_id: str
    lab_id: str
    processing_status: Literal["pending", "running", "ready", "failed", "blocked"]
    page_schema_version: str | None = None
    run_id: str | None = None
    source_pdf_sha256: str | None = None
    warnings: list[CloudPaperWarning] = []
    permissions: CloudPaperPermissions
    provenance_summary: CloudPaperProvenanceSummary
    local_hydration: CloudPaperHydrationState | None = None
    allowed_actions: list[CloudPaperAction]
```

Important constraint:

- internal GCS refs must stay server-side.
- Browser-visible responses should use opaque ids or short-lived backend-mediated download links.
- any signed URL must be response-only, short-lived, purpose-scoped, and excluded from persisted frontend state.

## Required Contract: Page Artifact

The cloud page artifact should be stable enough for the existing viewer to consume and for downstream features to reuse.

Minimum page artifact fields:

- `schema_version`
- `paper_id`
- `run_id`
- `source_pdf_sha256`
- `pages`
- `warnings`
- `created_at`
- `processor`

Each page should include:

- `page_id`
- `page_number`
- `text`
- `blocks`
- `tables`
- `figures`
- optional render asset refs
- source locators
- payload class
- warnings and uncertainty signals
- deterministic block ids and block order

PR 1 must choose one of these two implementation paths:

1. extend existing `DocumentArtifact` with cloud source/provenance fields; or
2. introduce `CloudPageArtifact` and a tested adapter that normalizes it into the existing viewer payload.

Do not leave both paths half-implemented.

Minimum locator requirements:

- page numbers are 1-based when user-facing
- bbox units must be named explicitly, for example `bbox_pct` or `bbox_pdf`
- table and figure ids must be stable within a paper/run
- block order must be deterministic
- warnings must survive into the viewer payload
- page and block locators must be stable enough for future evidence-routed assistants
- any model-generated page enrichment must remain marked as generated/draft-like unless reviewed by a lane-owned contract

If page artifacts later support claim/evidence linking, that must extend the existing evidence contracts rather than inventing a separate truth policy.

## API Roadmap

All routes should live behind FastAPI and follow existing auth/CORS rules.

Every route PR must update or explicitly verify:

- `backend/main.py` auth path matching for `/cloud/*` and same-origin `/api/cloud/*`
- `docs/runtime_security_env.md` protected route documentation
- `tests/test_api_key_auth.py` or a focused cloud-auth test file
- redaction tests proving public responses do not expose internal GCS refs, signed URLs, raw local paths, or credentials

### PR 1. Cloud Paper Contracts

Add schemas only:

- `src/schemas/cloud_paper.py`
- unit tests for validation and redaction behavior
- tests for internal vs public DTO separation
- tests for allowed action derivation from status and permissions

No GCP calls yet.

### PR 2. Mock Cloud FastAPI API

Add backend routes with a fake/local adapter and fixture-backed page payloads. This proves route auth, redaction, and viewer-compatible response shape before adding real GCP storage.

Routes may include:

- `POST /cloud/papers/upload-intents`
- `POST /cloud/papers/{paper_id}/complete-upload`
- `GET /cloud/papers/{paper_id}`
- `GET /cloud/papers/{paper_id}/page`

Behavior:

- validates API auth for root `/cloud/*` and same-origin `/api/cloud/*`
- returns redacted public DTOs backed by the PR1 schemas
- records fake/local event metadata where useful
- exercises processing states such as `pending`, `running`, `ready`, `failed`, and `blocked`
- does not import GCP SDKs or require production credentials
- proves existing UI payload compatibility at the API boundary or records the exact deferred adapter work

The PR2 fake adapter may keep process-local mock state for tests and local smoke checks only. It must not be treated as a durable metadata store, and PR3 must replace it with a config-gated storage adapter before real upload behavior is claimed.

### PR 3A. Storage Adapter Prep Without Real GCP

If production GCP is not available yet, add the storage adapter boundary before implementing real upload behavior.

Behavior:

- keep `PAPERPIPE_CLOUD_ADAPTER=mock` as the default local/test mode
- allow `PAPERPIPE_CLOUD_ADAPTER=gcs` only when required GCP config is present
- keep the GCS SDK as a lazy optional dependency, not a hard runtime dependency
- return a schema-backed `503 CLOUD_PAPER_STORAGE_UNAVAILABLE` when GCS is selected but the local runtime is not ready
- keep browser responses free of GCS object refs, signed URLs, credentials, and raw local paths

This prep slice may select a GCS adapter and validate configuration, but it must not claim real upload, checksum verification against GCS, signed URL issuance, or processing-job enqueueing until the production adapter is implemented and tested.

### PR 3B. Metadata Store And Upload Lifecycle Prep Without Real GCS

Before real GCS writes are available, move mock upload state behind a metadata-store contract and tighten lifecycle transitions.

Behavior:

- keep the metadata store schema-backed and replaceable
- keep the default implementation in-memory for local tests and smoke checks only
- record upload intent metadata separately from public cloud paper DTOs
- model upload lifecycle state separately from viewer-facing processing state
- make upload completion idempotent once a paper is ready
- persist blocked state for checksum mismatch in the metadata layer
- avoid treating process-local mock state as a durable production metadata store

This prep slice may validate state transitions with the mock API, but it must not claim real object existence checks, durable cross-process persistence, queue dispatch, or GCS checksum verification until the production metadata/storage backend is implemented.

### PR 3C. Page Artifact Adapter Prep Without Real GCS

Before a real GCP page worker exists, define the worker-style page artifact contract and normalize it into the existing viewer-compatible public page payload.

Behavior:

- keep internal page artifacts schema-backed
- require opaque cloud object refs only on internal artifacts
- preserve public viewer fields such as block id, page number, text, bbox, warnings, and provenance summary
- redact GCS refs, signed URLs, service-account values, raw local paths, and worker-only metadata from public page responses
- route mock page payloads through the same adapter that future worker output must use
- avoid claiming real worker execution, object reads, durable artifact storage, or page-quality guarantees

This prep slice may use mock internal artifacts to verify the adapter contract, but it must not treat fixture page text as a real processed result.

### PR 3. GCS Upload Intent And Completion

Replace or extend the fake adapter with a config-gated GCS adapter for source PDF upload.

Add backend routes:

- `POST /cloud/papers/upload-intents`
- `POST /cloud/papers/{paper_id}/complete-upload`

Behavior:

- validates API auth
- accepts filename, content type, checksum, lab id or active lab context
- returns upload intent id and either direct backend-upload instructions or short-lived signed upload instructions
- records event metadata
- does not persist signed URLs in public bundle records
- rate-limit and size-limit behavior is decided or explicitly deferred
- verifies object exists before marking upload complete
- verifies checksum
- creates `CloudPaperBundle` draft record
- starts or queues page processing if the processing worker is available; otherwise records a mock/deferred processing status
- leaves an auditable failed/blocked state if checksum verification fails

Suggested response:

```json
{
  "upload_intent_id": "upl_...",
  "paper_id": "paper_...",
  "upload_mode": "signed_url",
  "expires_at": "2026-05-30T00:00:00Z"
}
```

Current backend-mediated first slice:

- `POST /cloud/papers/upload-intents` may return `upload_mode: "backend_mediated"` when `PAPERPIPE_CLOUD_ADAPTER=gcs`.
- `POST /cloud/papers/{paper_id}/source-pdf` accepts multipart `source_pdf` bytes and writes them to the raw PDF bucket.
- The raw object path is server-owned: `{lab_id}/{paper_id}/source.pdf`.
- The backend stores server-computed source PDF metadata on the GCS object: `paper_id`, `lab_id`, and `source_pdf_sha256`.
- `POST /cloud/papers/{paper_id}/complete-upload` verifies that the raw object exists and that the object metadata checksum matches the upload intent before marking the paper ready.
- A missing raw object or checksum mismatch leaves the upload in a blocked state with public bundle warnings, not with leaked GCS refs.
- Public upload responses include `paper_id`, `upload_status`, `source_pdf_sha256`, `source_pdf_size_bytes`, and `content_type` only.
- GCS refs, bucket names, credentials, signed URLs, service-account values, and local paths remain out of public DTOs.
- The cloud dependency is installed with `python -m pip install ".[cloud]"`.

### PR 4. Cloud Page Status And Read API

Add routes:

- `GET /cloud/papers/{paper_id}`
- `GET /cloud/papers/{paper_id}/page`

Behavior:

- returns cloud bundle status
- returns page artifact in viewer-compatible shape
- redacts cloud internals
- includes warnings and provenance summary
- enforces read permission separately from source PDF download permission

Current page-artifact storage slice:

- storage adapters can write and read `CloudPaperPageArtifactInternal` JSON through mock storage or the configured GCS page artifact bucket.
- GCS page artifact objects use the server-owned path `{lab_id}/{paper_id}/{run_id}/page.json`.
- page artifact object metadata records `paper_id`, `lab_id`, `run_id`, and server-computed `page_artifact_sha256`.
- `complete-upload` writes the current mock page-worker artifact through the same adapter boundary before marking a stored paper ready.
- `GET /cloud/papers/{paper_id}/page` reads stored artifacts for upload-intent-backed papers and normalizes them into the public page DTO.
- public page responses and storage results still omit GCS refs, bucket names, credentials, signed URLs, service-account values, local paths, and worker-only metadata.

### PR 5. Local Hydration API

Add route:

- `POST /cloud/papers/{paper_id}/hydrate-local`

Behavior:

- checks download permission and device authorization
- downloads PDF/page/manifest
- writes compatibility files under `storage/artifacts/{paper_segment}/{run_id}/`
- records local hydration state
- makes existing UI route able to open the local bundle
- writes through a temp directory and promotes atomically when possible
- records stale/conflict state instead of silently overwriting a newer local bundle

Current backend hydration slice:

- `POST /cloud/papers/{paper_id}/hydrate-local` reads source PDF bytes and page artifact JSON through the storage adapter.
- hydration writes a compatibility bundle under the configured artifacts root using the existing paper/run directory helpers.
- bundle files are:
  - `source/source.pdf`
  - `page/page.json`
  - `cloud_hydration_manifest.json`
- the manifest records relative paths and source/page checksums.
- the public route response returns only redacted hydration state; it does not expose device id, local bundle refs, GCS refs, bucket names, credentials, signed URLs, service-account values, or local paths.
- existing bundles with matching checksums are idempotent; conflicting existing manifests are treated as stale and are not overwritten.

### PR 5A. Local Hydration Contract Prep Without Real GCS

Before real download/hydration exists, define the local hydration manifest that a backend-mediated download must eventually write.

Behavior:

- manifest uses relative bundle paths only
- manifest records source PDF and page artifact checksums
- public hydration state redacts device id and local bundle refs
- no actual cloud object download is claimed
- no local files are written by this prep slice

### PR 5B. Device Access Policy Prep Without Real Auth

Before production authentication exists, define the policy inputs that separate page read, PDF read, and hydrate/download permissions.

Behavior:

- access context includes actor, lab, paper lab, role, authentication state, device/session trust, and download policy
- cross-lab actors receive no paper permissions
- unregistered devices without approved sessions receive no paper permissions
- readers can read pages by default but cannot hydrate/download by default
- maintainers/admins can hydrate only when download policy allows it

### PR 5C. Agent/Tool Capability Prep Without Live Agents

Before shipping optional AI or external tool execution, define capability filtering over the existing cloud paper state.

Behavior:

- capabilities declare the action they need, allowed payload classes, and whether a hydrated local bundle is required
- action availability is derived from permissions and paper status
- external or hydrated-only tools are hidden until payload class and hydration state allow them
- this prep slice does not execute tools, call models, or create autonomous agents

### PR 5D. Installer/Client Runtime Config Prep Without Cloud Secrets

Before installer/client changes, define a browser-safe runtime config contract.

Behavior:

- client config reports only safe booleans and enabled contract names
- bucket names, project ids, credentials, and signed URLs are never exposed
- default mode is mock
- GCS readiness is reported without requiring a GCS SDK import

### PR 6. Existing UI Integration

Update paper list/detail flows:

- show cloud-backed papers in the same paper list
- show compact cloud status in the state/provenance rail
- add `Open processed page`
- add `Download for local use` only when permitted
- keep GCP details hidden by default
- update `docs/UX_REVIEW_REPORT_cloud-paper-page.md` before finishing the UI slice

### PR 7. Authenticated Device Access

Add device/session policy:

- authenticated user
- registered device or approved session
- lab membership
- paper read permission
- optional download permission

This can start as a hosted-beta gate plus lab/device token, but production needs first-class user auth.

## GCP Resource Plan

Minimum GCP resources:

- GCS bucket for raw PDFs
- GCS bucket or prefix for page artifacts
- Cloud Run service or worker for page processing
- Pub/Sub or Cloud Tasks queue for processing jobs
- metadata store: Firestore, Cloud SQL, or existing backend DB with cloud object refs
- Secret Manager for GCP/service credentials where needed
- Cloud Logging for upload/process/download events

Recommended bucket split:

- `lattice-raw-pdf-{env}`
- `lattice-page-artifacts-{env}`
- `lattice-download-bundles-{env}` only if prebuilt bundles are needed

Bucket access:

- private by default
- no public object ACLs
- short-lived signed URLs only when direct browser upload/download is adopted
- service-to-service access preferred for sensitive downloads

## Permission Model

Start with a minimal role set:

| Role | Read page | Read PDF | Download bundle | Upload | Delete | Admin |
| --- | --- | --- | --- | --- | --- | --- |
| lab_admin | yes | yes | yes | yes | yes | yes |
| maintainer | yes | yes | yes | yes | no | no |
| reviewer | yes | yes | policy-based | no | no | no |
| reader | yes | policy-based | no by default | no | no | no |

Device policy:

- first implementation may allow account/session auth only
- production should support registered device state
- local hydration should be recorded per device
- cached PDF removal should be available for shared machines

## Security And Privacy Rules

Payload classification:

- raw PDF storage and page processing may be treated as inside a `lab_allowed` boundary only when the GCP project is lab-managed and explicitly approved
- uploaded PDFs, full PDF text, raw page images, and complete page text must not be treated as `external_allowed`
- source-derived inference payloads default to `local_only` unless minimized and explicitly reclassified under the inference boundary policy
- full PDFs, raw page images, and complete page text remain too sensitive for public commercial inference by default

Required security rules:

- no GCP service account keys in frontend code
- no long-lived signed URLs persisted in frontend state
- no raw local paths in cloud metadata
- checksum verification before processing
- audit events for upload, process, read, download, hydrate, delete
- cloud object ids should be opaque in UI
- deletion and retention policy must be explicit before production

## Existing UI Compatibility

The existing UI should not fork into a separate cloud UI.

Instead, add a compatibility adapter that lets a paper resolve from:

1. local artifact state
2. cloud page state
3. hydrated local cache

The viewer should receive a normalized paper/page payload:

```text
PaperViewModel
  paper identity
  source state
  page artifact state
  evidence/structured state if available
  warnings
  provenance summary
  allowed actions
```

The UI may show:

- `Cloud processed`
- `Available offline`
- `Download disabled by lab policy`
- `Processing failed`
- `Source changed; local cache stale`

The UI should not show:

- bucket names
- service account details
- raw signed URLs
- internal worker traces by default

## Existing Feature Parity Matrix

The business goal says cloud PDF/page state should support existing service behavior. For implementation, treat that as staged parity rather than a vague all-at-once promise.

| Surface | MVP expectation | Later parity expectation | Verification |
| --- | --- | --- | --- |
| Paper list | cloud-backed papers appear with processing/readiness state | filters/search include cloud/local consistently | backend route test plus UI smoke |
| Paper detail viewer | processed page opens in the existing viewer shell | local/cloud/hydrated payloads preserve the same trust order | targeted frontend test when route coverage exists |
| PDF source access | permitted users can read or hydrate source PDF | policy-specific read/download separation | auth/permission matrix tests |
| Local hydration | hydrated bundle opens in paper detail | hydrated state powers downstream artifact reuse where contracts allow | hydration tests plus existing viewer tests |
| Evidence/ClaimSet panels | show existing structured state if available; do not invent missing evidence | cloud page locators can link into evidence contracts | schema/adapter tests |
| Search | cloud page text is discoverable through a separate redacted `/cloud/papers/search` contract and Paper Notes affordance | canonical note search and cloud page search can be unified only if source/evidence lineage is preserved | backend search contract tests plus mock UI search test |
| Downstream artifacts | not required to be cloud-native in MVP; cloud page matches remain non-canonical derived page text | Meeting Pack, Chart Pack, Image Evidence, Method Comparison consume hydrated or normalized state through lane-specific adapters | lane-specific tests later |
| Obsidian export/sync | not required in first MVP | export preserves cloud provenance and avoids raw signed URLs | exporter tests later |
| Offline mode | hydrated bundle can be opened locally when permitted | stale/conflict status survives reconnect | hydration/stale-cache tests |

If a PR claims "existing UI works," it must name which row(s) of this matrix it satisfies.

## Product Psychology Review

### Quick Review

- Choice count: first screen should expose one primary action, `Upload PDF`, and one ready-state action, `Open processed page`.
- Benefit: the first value is not "GCP"; it is "read the processed paper from any authenticated device."
- Next action: every status should map to one obvious action.
- Feedback: upload, process, ready, failed, and downloaded states need quiet visible feedback.
- Ethics: cloud upload must be explicit and reversible within retention policy.

### Full Review

P0:

- Do not hide that PDFs leave the local machine.
- Do not let generated page artifacts look stronger than evidence-linked structured state.
- Do not allow download by default for every read-authorized user.
- Do not store cloud credentials or provider keys in browser-owned state.

P1:

- Preserve the current paper list/detail rhythm.
- Put cloud status in the state/provenance rail, not in a loud banner.
- Make page processing warnings visible before downstream reuse.
- Keep local hydration a clear action with a clear result.

P2:

- Add richer sync controls only after upload, open, and hydrate are reliable.
- Add admin quota/storage screens after the core reader flow works.

6P storyboard context:

- Problem: a researcher wants to read the same processed paper away from the lab machine.
- Emotion: they want continuity and confidence, not another server admin surface.
- Action: they upload a PDF or open a cloud-processed paper.
- Struggle: upload, processing, permissions, and local cache can feel invisible or risky.
- Attempt: show a small set of state-driven actions and provenance.
- Happy Ending: the paper opens with processed pages, warnings, and source lineage on any authenticated device.

BMAP:

- Motivation: high because access across devices solves a real lab workflow problem.
- Ability: depends on hiding cloud mechanics and preserving the existing UI.
- Prompt: status-driven prompts should say `Open`, `Download`, `Retry`, or `Request access`.

B.I.A.S:

- Block: avoid GCP jargon in user-facing labels.
- Interpret: frame the value as processed paper access, not remote infrastructure.
- Act: reduce steps from upload to ready page.
- Store: end each flow with a visible ready/offline/provenance state.

Peak-End:

- Peak: a cloud-processed paper opens in the existing UI from a second authenticated device.
- Pit: the user cannot tell whether the PDF was uploaded, processed, or cached.
- Transition: local upload -> cloud processing -> existing viewer -> local hydration.
- End: local cache state and download policy are explicit.

Ethics:

- Regret: users should not discover after the fact that a private PDF was uploaded.
- Black Mirror: weak device/download policy can leak lab literature outside intended users.
- In Real-Life: the product should behave like a careful lab librarian that explains access and provenance.

## Implementation Phases

### Phase 0. Adoption Decision

Output:

- confirm this roadmap as a top-priority lane
- decide whether GCP is lab-managed production infrastructure or an internal pilot backend
- choose metadata store
- choose direct signed upload vs backend-mediated upload

Hard fail conditions:

- no accepted cloud trust boundary
- no decision on PDF retention and deletion
- no auth story for read/download separation

### Phase 1. Contract And Local Mock

Output:

- `CloudPaperBundle` schema
- page artifact schema or adapter contract
- fake cloud adapter backed by local fixtures
- tests for redaction and status transitions

Verification:

- targeted schema tests
- backend route tests with fake adapter
- `python -m pytest -q tests/test_cloud_paper_schema.py tests/test_cloud_paper_api.py` or equivalent focused targets
- `git diff --check -- <touched files>`

### Phase 2. GCS Upload And Metadata

Output:

- upload intent route
- upload completion route
- checksum verification
- raw PDF object storage
- metadata record

Verification:

- integration test with GCP emulator or mocked storage adapter
- manual staging smoke with a small PDF
- auth tests for `/cloud/papers/upload-intents`, `/api/cloud/papers/upload-intents`, and upload completion routes
- checksum mismatch test

### Phase 3. GCP Page Processing Worker

Output:

- processing job queue
- worker service
- page artifact write
- processing status updates
- failure/warning propagation

Verification:

- worker unit tests
- end-to-end processing smoke on one PDF
- artifact schema validation
- failed processing test that proves status is not `ready`

Current processing-worker boundary slice:

- processing now runs through `src/services/cloud_paper_processing.py` instead of being embedded directly in upload completion.
- upload completion verifies the raw source object, marks processing `running`, builds the current schema-backed mock page artifact, writes it through the storage adapter, then marks the record `ready`.
- worker failures are represented as `failed` upload/processing state with public warnings; failed processing does not create a ready state.
- this is still an in-process mock worker boundary, not a deployed Cloud Run worker, Pub/Sub topic, or Cloud Tasks queue.
- replacing the mock processor with a deployed worker must preserve the same metadata transitions and page artifact storage contract.

### Phase 4. Viewer Read Path

Output:

- backend read routes for cloud paper/page state
- normalized viewer payload
- paper list/detail UI integration

Verification:

- backend API smoke
- frontend build
- Playwright coverage for cloud-ready and processing states when route coverage exists
- UX review artifact update for cloud paper/page flow
- route redaction tests for public payloads

Current existing-UI integration slice:

- `GET /cloud/papers` returns a schema-backed `cloud_paper_list.v1` response for the installed UI.
- the list response derives actor/lab/device permissions per paper and omits papers the current context cannot read.
- `frontend/src/app/pages/PaperNotesListPage.tsx` now shows cloud-backed papers in the existing Paper Notes index instead of creating a separate cloud-only UI.
- ready, processing, failed, blocked, read-only, and offline/hydration states are visible with compact status affordances.
- ready cloud papers can load the normalized public page artifact as an inline page preview; the browser still never receives GCS refs, signed URLs, service-account data, or absolute local paths.
- local hydration remains backend-mediated and permission-gated; the UI shows the action as locked unless `hydrate_download` is allowed.
- this slice satisfies the Phase 4 paper-list/read-path MVP row only. Full paper-detail viewer parity and cloud/local search parity remain staged follow-up work.

### Phase 5. Local Hydration

Output:

- download/hydrate route
- compatibility writer under existing artifact paths
- stale-cache detection
- UI state for `Available offline`

Verification:

- hydration tests
- existing paper viewer tests against hydrated bundle
- partial hydrate failure test
- stale-cache detection test

Current local-hydration compatibility slice:

- local hydration manifests are now readable after the original hydrate call, so refreshed cloud paper status can report `hydrated` instead of reverting to `not_hydrated`.
- manifest-derived public hydration state still redacts device ids and local bundle paths before reaching the UI.
- source checksum drift is represented as `stale` rather than silently treating the local bundle as current.
- `CloudPaperBundlePublic.local_hydration` is derived from the manifest plus current cloud source checksum for stored mock/GCS-backed upload-intent papers.
- full paper-detail viewer parity is still staged; this slice only makes hydration state discoverable through the existing cloud paper status/list read path.

### Phase 6. Authenticated Multi-Device Beta

Output:

- user/session or beta auth policy
- device registration or device-token pilot
- lab membership and paper role checks
- audit log for reads/downloads

Verification:

- auth tests
- permission matrix tests
- manual second-device smoke
- audit event tests for read/download/hydrate where event logging exists

## Definition Of Done For MVP

The MVP is done only when all of the following are true:

1. A user can upload one PDF from the installed app.
2. The PDF is stored in GCP with checksum and provenance.
3. GCP processes the PDF into a page artifact.
4. The user can open the processed page in the existing UI.
5. A second authenticated device can open the same processed page.
6. A permitted user can hydrate the PDF/page bundle locally.
7. The hydrated bundle works with the existing paper detail viewer.
8. Browser-visible state contains no long-lived cloud secrets or raw signed URLs.
9. Upload/process/read/download events are auditable.
10. Processing warnings remain visible before downstream reuse.
11. `/cloud/*` and same-origin `/api/cloud/*` route protections are documented and tested.
12. Public response DTOs are separated from internal cloud object refs.
13. The MVP rows of the feature parity matrix are explicitly checked.
14. A UX review report exists for the cloud paper/page flow before frontend changes are called done.

Current MVP status after the goal-driven implementation pass:

| DoD item | Status | Evidence / next boundary |
| --- | --- | --- |
| 1. Installed app upload | Partial | Backend-mediated upload routes exist; Paper Notes still has local import and cloud upload is not yet a polished user upload flow. |
| 2. GCP source storage | Done for configured pilot | Real GCS raw PDF upload and source-object verification are implemented behind `PAPERPIPE_CLOUD_ADAPTER=gcs`. |
| 3. Page processing | MVP mock boundary | Processing runs through `src/services/cloud_paper_processing.py`; Cloud Run/PubSub/Cloud Tasks deployment remains a production-infra goal. |
| 4. Existing UI opens processed page | Detail-viewer MVP done | Paper Notes shows cloud papers, inline normalized page preview, and `/papers/{paper_id}?source=cloud` opens the existing detail shell for ready cloud pages. |
| 5. Second authenticated device | Beta policy boundary | Header-derived lab/device/session policy supports same-origin/API-key beta reads; production identity is deferred. |
| 6. Permitted local hydration | Backend MVP done | `hydrate-local` writes checksum-tracked local bundles and is permission-gated. |
| 7. Hydrated bundle works in paper detail viewer | Partial | Hydration status is discoverable after refresh; full detail-viewer bundle opening is a follow-up parity goal. |
| 8. Browser-visible secrets | Done for current routes | Public DTOs and UI state are redacted; frontend calls same-origin backend only. |
| 9. Auditability | Partial | Read/page/hydrate audit events exist where event logging is configured; upload/process durable audit strategy remains tied to production metadata. |
| 10. Processing warnings visible | Done for current routes | Failed/blocked warnings survive public bundle and UI rows. |
| 11. Route protection | Done for beta | `/cloud/*` and `/api/cloud/*` auth/same-origin behavior has focused tests. |
| 12. Internal/public DTO separation | Done | Internal cloud refs stay in internal schemas/storage adapters; public DTOs are redacted. |
| 13. MVP parity matrix checked | Partial | Paper list/read-path, detail-viewer, hydration status, separate redacted cloud search, and draft cloud-page summary bridge rows are checked; deeper downstream artifact lanes remain deferred. |
| 14. UX report | Done | `docs/UX_REVIEW_REPORT_cloud-paper-page.md` exists and covers the current UI slice. |

Do not mark the whole roadmap production-complete until the `Partial` and `MVP mock boundary` rows are intentionally closed or accepted as pilot scope.

## PR Readiness Checklist

Before marking a PR ready, confirm:

- the slice has one clear owner: contract, upload, processing, read path, hydration, UI, or auth
- new contracts live under `src/schemas/`
- route code is thin and delegates to service/adapter code
- tests were added before or alongside implementation for contract-sensitive behavior
- auth, redaction, and failure-path tests are present when the slice touches cloud data
- verification commands are listed in the PR description
- residual risks and deferred parity rows are named
- no generated runtime artifacts, credentials, logs, or local storage files are staged
- docs updated: roadmap, `runtime_security_env.md`, UX report, or independent review note as applicable

## Open Decisions

1. GCP metadata store:
   - Firestore
   - Cloud SQL
   - current backend DB plus GCS refs

2. Upload mode:
   - backend-mediated upload
   - signed URL direct upload

3. Page artifact shape:
   - extend existing `DocumentArtifact`
   - introduce `CloudPageArtifact` with adapter to existing viewer

4. User auth:
   - current API key/beta gate for internal pilot
   - first-class user accounts
   - institution SSO

5. Device auth:
   - session only
   - registered device token
   - admin-approved device enrollment

6. Retention:
   - keep raw PDFs indefinitely
   - lab-configured retention
   - delete source after page artifact generation for selected policies

7. Licensing:
   - read-only page access for most users
   - PDF download only for permitted roles
   - institution-specific restrictions

8. AI packaging:
   - operator-provided optional AI plan
   - BYO-AI with user/lab credentials
   - lab-managed inference server integration
   - local model integration

## First Three PRs

1. Contract PR
   - add `CloudPaperBundleInternal`, `CloudPaperBundlePublic`, permission, provenance, hydration schemas
   - add schema tests
   - no GCP dependency yet

2. Mock Cloud API PR
   - add FastAPI routes with fake cloud adapter
   - return redacted status and page fixture
   - prove existing UI can consume normalized payload

3. GCS Upload PR
   - add real GCS adapter behind config flag
   - implement upload intent and completion
   - verify checksum and record upload event

3A. Storage Adapter Prep PR
   - add `mock`/`gcs` adapter selection behind env config
   - keep GCS dependency lazy and optional
   - fail closed with a public 503 contract when GCS runtime config is incomplete

3B. Metadata Store And Upload Lifecycle Prep PR
   - add schema-backed upload metadata records
   - move process-local mock state behind a replaceable metadata-store contract
   - test intent-created, ready, blocked, and idempotent completion transitions

3C. Page Artifact Adapter Prep PR
   - add internal page artifact and block schemas for worker-style output
   - add adapter to the existing public viewer page payload
   - test public redaction and block/provenance/warning preservation

## Goal Sequence

Use these as the default goal prompts. Adjust only after the previous goal's implementation evidence or review findings justify a change.

### Goal 1. Cloud Paper Schema Contract

```text
Implement PR1 of the GCP Cloud Paper/Page roadmap: add cloud paper Pydantic schemas and focused tests for internal/public DTO separation, permissions, allowed actions, and redaction, without adding real GCP dependencies.
```

Exit:

- schema tests pass
- public DTO cannot expose private cloud refs
- no GCP SDK dependency
- PR2 can build fake routes without changing the schema shape

### Goal 2. Mock Cloud FastAPI API

```text
Implement PR2 of the GCP Cloud Paper/Page roadmap: add fake cloud paper FastAPI routes and adapter-backed responses using the PR1 schemas, with auth and redaction tests for /cloud/* and same-origin /api/cloud/* paths.
```

Exit:

- fake adapter can return upload/status/page payloads
- auth tests cover protected read/write paths
- public responses remain redacted
- existing paper UI payload compatibility is proven at the API boundary or explicitly deferred

### Goal 3A. Storage Adapter Prep Without Real GCP

```text
Implement a no-credentials preparation slice for PR3: add a cloud storage adapter contract and config-gated mock/GCS-ready adapter selection, keep mock as the default, avoid hard GCP runtime dependencies, and return schema-backed storage-unavailable errors when GCS is selected but not ready.
```

Exit:

- `mock` remains the default and requires no GCP SDK or credentials
- `gcs` selection validates `PAPERPIPE_GCP_PROJECT_ID`, `PAPERPIPE_GCS_RAW_PDF_BUCKET`, and `PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET`
- GCS SDK import is lazy and only attempted inside the GCS adapter operation path
- upload-intent API declares and returns `503 CLOUD_PAPER_STORAGE_UNAVAILABLE` for missing GCS runtime readiness
- public responses remain redacted
- runtime/security docs list the cloud storage adapter env vars

### Goal 3B. Metadata Store And Upload Lifecycle Prep Without Real GCS

```text
Implement the next no-real-GCS preparation goal: introduce a schema-backed cloud paper metadata store abstraction and strengthen upload lifecycle state transitions around the mock cloud paper API, with focused tests and documentation updates, without requiring real GCS credentials or hard GCP dependencies.
```

Exit:

- upload intent records are represented by a Pydantic metadata record
- process-local mock state is accessed through a replaceable metadata-store contract
- lifecycle transitions cover `intent_created`, `ready`, and `blocked`
- public `processing_status` remains derived and redacted
- checksum mismatch creates a persisted blocked state in mock metadata
- repeated upload completion after ready is idempotent
- no GCP SDK dependency or production credentials are required

### Goal 3C. Page Artifact Adapter Prep Without Real GCS

```text
Implement the next no-real-GCS preparation goal: introduce a cloud page artifact adapter contract that normalizes worker-style internal page artifacts into the existing viewer-compatible public page payload, with schema tests, mock API tests, and documentation updates, without requiring real GCS or GCP worker infrastructure.
```

Exit:

- internal page artifacts are represented by Pydantic schemas
- internal artifacts require opaque `gs://` page artifact refs
- adapter returns the existing `CloudPaperPageArtifactPublic` response shape
- block id, page, text, bbox, allowed public metadata, warnings, and provenance summary are preserved
- GCS refs, signed URLs, service-account values, raw local paths, and worker-only metadata are redacted from public payloads
- mock `/cloud/papers/{paper_id}/page` responses pass through the adapter
- no GCP SDK, worker infrastructure, or production credentials are required

### Goal 3. GCS Upload Intent And Completion

```text
Implement PR3 of the GCP Cloud Paper/Page roadmap: add a config-gated GCS adapter for upload intent and upload completion, verify checksum handling, and keep signed URLs short-lived and out of persisted public state.
```

Exit:

- tests use mocked GCS or emulator-style adapter, not required production credentials
- checksum mismatch creates failed/blocked state
- no credential or signed URL leaks into public DTOs
- runtime security docs are updated for touched routes

### Goal 4A. Real GCS Raw PDF Upload

```text
Implement real GCS raw PDF upload support through the existing cloud paper API: keep upload intent responses redacted, support backend-mediated multipart source PDF upload into the configured raw bucket, verify checksum before storage writes, and preserve mock/no-GCS behavior.
```

Exit:

- `PAPERPIPE_CLOUD_ADAPTER=gcs` selects the GCS adapter and returns `upload_mode: backend_mediated`
- `POST /cloud/papers/{paper_id}/source-pdf` writes source PDF bytes to the configured raw PDF bucket
- checksum mismatch blocks before any GCS write
- public source upload response contains no GCS refs, bucket names, credentials, signed URLs, or local paths
- `.[cloud]` optional dependency documents `google-cloud-storage`
- focused tests and a real bucket smoke pass

### Goal 4B. GCS Source Object Verification On Upload Completion

```text
Implement GCS source object verification during upload completion: persist server-owned checksum metadata on raw PDF objects, verify object existence and metadata checksum before ready state, and keep mock/no-GCS behavior plus public redaction unchanged.
```

Exit:

- GCS source uploads write object metadata for `paper_id`, `lab_id`, and server-computed `source_pdf_sha256`
- storage adapter exposes a redacted verification result with object existence, checksum match, checksum, and size only
- `complete-upload` blocks missing GCS source objects with `SOURCE_PDF_MISSING`
- `complete-upload` blocks GCS metadata checksum mismatch with `CHECKSUM_MISMATCH`
- public API responses still omit GCS refs, bucket names, credentials, signed URLs, service-account values, and local paths
- focused tests and a real bucket upload/verify/delete smoke pass

### Goal 3D. Remaining No-GCS Contract Prep

```text
Prepare all remaining no-real-GCS cloud paper groundwork: implement contract-level local hydration manifests, device access policy derivation, agent/tool capability filtering, and safe installer/client runtime config without real GCS credentials, worker infrastructure, autonomous agents, or hard GCP dependencies.
```

Exit:

- local hydration manifest rejects absolute, cloud, or parent-traversal paths
- public hydration state redacts device id and local bundle refs
- device policy separates page read from PDF read and hydrate/download
- cross-lab and untrusted-device contexts receive no paper permissions
- tool capabilities filter by permission, payload class, and hydration state
- client runtime config reports adapter readiness without leaking project ids, bucket names, credentials, or signed URLs
- no GCP SDK dependency or production credentials are required

### Goal 4. Cloud Page Read Path

```text
Implement the cloud page read path: expose processed cloud page status and viewer-compatible page payloads through FastAPI, preserving warnings, provenance, route auth, and generated-artifact trust boundaries.
```

Exit:

- viewer-compatible payload is normalized
- processing warnings and provenance survive
- read permission is separate from PDF download permission
- UX review artifact is started if frontend flow changes

### Goal 4C. Page Artifact Storage Boundary

```text
Implement the page artifact storage boundary for the cloud page read path: write and read schema-backed page artifact JSON through mock or GCS storage, keep stored artifacts internal, and expose only normalized/redacted public page payloads through the existing FastAPI route.
```

Exit:

- mock and GCS adapters can write and read page artifacts by lab, paper, and run id
- GCS page artifact writes include server-computed checksum metadata
- stored page artifacts are normalized through `derive_cloud_page_artifact_public`
- `complete-upload` creates the current mock-worker page artifact through the storage boundary before ready state
- `GET /cloud/papers/{paper_id}/page` reads stored artifacts for upload-intent-backed papers
- public responses and storage result DTOs do not leak GCS refs, bucket names, signed URLs, credentials, service-account values, local paths, or worker metadata
- focused tests and a real page-bucket write/read/delete smoke pass

### Goal 5. Local Hydration

```text
Implement local hydration for cloud PDF/page bundles: download permitted PDF/page/manifest data through the backend, write a compatibility bundle under existing artifact paths, and detect partial writes and stale cache states.
```

Exit:

- hydration tests cover success, partial failure, and stale-cache behavior
- hydrated bundle opens in the existing paper detail viewer
- no silent overwrite of newer local/cloud state
- local cache state is recorded per policy

### Goal 5A. Backend Local Hydration Boundary

```text
Implement the backend local hydration boundary: read cloud source PDF and page artifact data through storage adapters, write a checksum-tracked compatibility bundle under the existing artifact path convention, and expose only redacted hydration state through FastAPI.
```

Exit:

- `POST /cloud/papers/{paper_id}/hydrate-local` is auth-covered with the other cloud routes
- source PDF and page artifact data are read through the storage adapter
- local bundle writer uses relative manifest paths and checksum fields
- existing matching bundles are idempotent
- conflicting existing manifests return stale state instead of overwriting local files
- public hydration responses redact device id, local bundle refs, GCS refs, bucket names, signed URLs, credentials, service-account values, and local paths
- focused tests and real GCS upload/page/hydrate smoke pass

### Goal 6. Authenticated Multi-Device Beta

```text
Implement the authenticated multi-device beta path: enforce user/session or beta/device policy, lab membership, paper read permission, optional download permission, and audit events for read/download/hydrate actions.
```

Exit:

- permission matrix tests pass
- second-device manual smoke is documented
- read/download/hydrate audit events are recorded where event logging exists
- production auth gaps are explicitly listed if beta auth remains temporary

Current beta access slice:

- cloud read/page/hydrate routes derive beta access context from request headers:
  - `X-PaperPipe-Actor-Id`
  - `X-PaperPipe-Lab-Id`
  - `X-PaperPipe-Role`
  - `X-PaperPipe-Device-Registered`
  - `X-PaperPipe-Session-Approved`
  - `X-PaperPipe-Download-Allowed`
- missing headers default to local beta reader compatibility: authenticated, same-lab, registered device, page-read only, no download/hydrate.
- cross-lab, unauthenticated, or untrusted-device access gets no actions.
- `hydrate-local` requires download/hydrate permission and returns `403 CLOUD_PAPER_FORBIDDEN` when policy denies it.
- `GET /cloud/papers/{paper_id}`, `GET /cloud/papers/{paper_id}/page`, and `POST /cloud/papers/{paper_id}/hydrate-local` write best-effort `user_actions` audit rows with redacted payloads.
- this is not production user authentication. It is a beta policy boundary behind the existing API-key/same-origin protection, and must be replaced or backed by real user/session/lab identity before internet-facing multi-tenant use.

### Goal 7. Production Infrastructure Decision Gate

Decision artifact: `docs/GCP_CLOUD_PAPER_PRODUCTION_DECISION_GATE_2026-06-01.md`

```text
Prepare the production-infrastructure decision gate for the GCP Cloud Paper/Page roadmap: choose or explicitly defer the durable metadata store, page worker deployment model, queueing mechanism, production auth source, and retention policy before deploying internet-facing multi-tenant cloud processing.
```

Exit:

- Firestore, Cloud SQL, or existing backend DB is selected for durable cloud metadata, or the pilot remains explicitly process-local/non-production.
- Cloud Run, Pub/Sub, Cloud Tasks, or another worker dispatch strategy is selected before replacing the in-process mock worker.
- production user/session/lab identity source is selected before broad multi-device rollout.
- retention/deletion policy for raw PDFs and page artifacts is documented before real lab data is treated as production.
- deployment commands, service-account scopes, and rollback steps are reviewed before any cost-incurring deployment.

This goal requires an explicit operator decision and should not be auto-executed by Codex without confirmation.

Current decision-gate prep slice:

- Internal pilot is allowed with current GCS adapter plus same-origin/API-key protection and beta lab/device headers.
- For the June 5, 2026 Google Agent Challenge finals demo, the accepted architecture direction is Firestore metadata, Cloud Run page processing, Cloud Tasks dispatch, beta auth for the controlled demo, and lab-configured retention before production.
- A Firestore `CloudPaperMetadataStore` exists, is wired behind `PAPERPIPE_CLOUD_METADATA_STORE=firestore`, and is covered by fake-client API/runtime tests. Firestore Native `(default)` was created in `asia-northeast3`, and the real Firestore + GCS demo smoke passed against `cloud_papers_demo`.
- Production conversion remains blocked until deployed Cloud Run worker, real auth/session/lab identity, durable audit, retention/delete policy, and deploy/rollback commands are completed.
- The decision gate records the exact remaining gates before any cost-incurring production deployment.

### Goal 8. Full Existing Viewer Parity

```text
Implement full existing-viewer parity for cloud paper/page state: route normalized cloud page payloads and hydrated bundles into the paper detail viewer shell, preserve trust/provenance ordering, and add route coverage for ready, processing, stale, and locked hydration states.
```

Exit:

- cloud page payloads open in the existing paper detail viewer shell, not only the Paper Notes index preview.
- hydrated bundle lookup feeds existing local artifact readers where contracts allow it.
- stale hydrated bundles are visible and never silently outrank newer cloud source metadata.
- Playwright or equivalent route coverage verifies ready, processing, stale, and locked hydration states.
- the feature parity matrix rows for paper detail viewer and local hydration are explicitly checked.

Current full-viewer parity slice:

- `PaperNoteDetailPage` now accepts `/papers/{paper_id}?source=cloud` and renders cloud paper/page state inside the existing detail shell instead of a separate cloud viewer app.
- Paper Notes cloud rows link to the detail shell through `Open viewer`.
- The cloud detail shell shows cloud source, normalized page artifact, local hydration state, trust ordering, and public provenance.
- Ready cloud pages auto-load normalized page blocks; refresh and hydrate actions remain backend-mediated and permission-gated.
- This closes the first paper-detail viewer parity step for ready cloud page payloads. Full hydrated-bundle reuse by every downstream local artifact reader remains staged under Goal 9/downstream parity.

### Goal 9. Search And Downstream Parity

```text
Extend cloud page/page-hydration parity into search and downstream artifact lanes only after viewer parity is stable: index cloud page text through existing search paths and let downstream features consume hydrated or normalized state without inventing unsupported evidence.
```

Exit:

- cloud page text participates in existing search/filter behavior with focused tests.
- downstream lanes consume hydrated or normalized cloud page state through existing contracts.
- no evidence, ClaimSet, Obsidian export, or meeting/chart/image artifact treats cloud page text as canonical evidence unless upstream canonical state supports it.
- each downstream lane names whether it is cloud-native, hydrated-only, or deferred.

Current search/downstream parity slice:

- Added a redacted `GET /cloud/papers/search?q=...` FastAPI contract for processed cloud page text.
- Search hits return public `CloudPaperBundlePublic` plus matched page-block snippets only; raw GCS refs, signed URLs, service-account metadata, and local paths remain server-private.
- Added a redacted `GET /cloud/papers/{paper_id}/summary` FastAPI contract that builds a draft extractive summary from `CloudPaperPageArtifactPublic.blocks`.
- The summary bridge declares `input_source: cloud_page_artifact`, includes source block ids/pages/payload class/provenance, and uses page-read permission rather than local PDF access.
- This closes only the first summary-input conversion slice. Full DeepRead/AI/model-backed summary parity remains a follow-up lane and must keep payload classification, redaction, provenance, and audit hooks.
- The existing `/paper-notes` canonical note search is not widened yet. Paper Notes instead displays `Cloud page matches` as a separate search affordance so cloud page text does not become canonical evidence by accident.
- Current downstream lane status:
  - Paper list/search affordance: cloud-native via redacted search contract.
  - Paper detail viewer: cloud-native for ready normalized page blocks.
  - Draft summary bridge: cloud-native for deterministic extractive summaries over public page blocks.
  - Local hydration: hydrated-only for local reuse; stale/cache conflict remains governed by hydration manifest.
  - DeepRead/model-backed AI summaries, Evidence/ClaimSet, Obsidian export, Meeting Pack, Chart Pack, Image Evidence, Method Comparison: deferred until each lane has an adapter that preserves source/evidence lineage and does not treat cloud page text as canonical structured state.
- Focused verification now covers backend search/redaction, cloud-page summary bridge, lab access filtering, frontend build, and mock Playwright search/detail paths.

### Goal 10. Raw-PDF Derived Artifact Parity Queue

Raw PDF/image-dependent work such as OCR reprocessing, figure image analysis, and table reconstruction must stay server-side. The installed app should request redacted derived artifacts, not raw GCS object refs, raw signed URLs, or local worker paths.

Execute this as five sequential goals:

1. **Derived Artifact Schema/API Contract**: define internal/public DTOs for OCR blocks, reconstructed tables, figure crops, and figure analyses; expose a mock `GET /cloud/papers/{paper_id}/derived-artifacts` contract; prove public responses retain source locators/provenance while redacting GCS refs, signed URLs, service accounts, and local paths.
2. **Worker Processing Contract**: add a worker-facing service contract that reads raw PDF/page images only inside the server/GCP boundary and emits idempotent derived artifact payloads keyed by `paper_id`, `run_id`, `source_pdf_sha256`, processor name/version, and stable artifact ids.
3. **Derived Artifact Storage Boundary**: persist internal derived artifact JSON through mock/GCS storage, compute server-side checksums, and read only through normalized public DTOs.
4. **OCR/Table/Figure APIs And Image Proxy**: split read APIs for OCR, tables, figures, and figure analyses as needed; serve figure images through an authenticated backend-mediated image route or short-lived server-generated access path without exposing durable cloud refs.
5. **Existing UI Integration**: connect the paper detail viewer and downstream panels to cloud-derived OCR/table/figure artifacts while keeping cloud page text non-canonical unless upstream structured state supports it.

Current status:

- Goal 10.1 first slice is implemented as a mock/read contract: public `cloud_paper_derived_artifacts.v1` responses include OCR/table/figure/figure-analysis records with source PDF checksum, page locators, payload class, warnings, and provenance summary.
- Goal 10.2 first slice is implemented as a worker-facing contract: `process_cloud_paper_derived_artifacts` reads raw PDF bytes through the storage adapter, verifies the bytes against upload metadata checksum, passes bytes only to the server-side processor protocol, and emits deterministic internal derived artifacts keyed by `paper_id`, `run_id`, and `source_pdf_sha256`.
- Goal 10.3 first slice is implemented as a storage boundary: mock/GCS adapters write and read internal derived artifact JSON, return checksum/size-only storage results, and public read routes normalize stored artifacts through redacted public DTOs.
- Goal 10.4 first slice is implemented as split read APIs plus image proxy: `/ocr`, `/tables`, `/figures`, `/figures/{figure_id}/analysis`, and `/figures/{figure_id}/image` read from the derived artifact boundary while preserving auth, not-ready handling, redaction, and backend-mediated image bytes.
- Goal 10.5 first slice is implemented in the existing detail shell: the installed UI loads the cloud-derived artifact bundle after the cloud page is readable, shows OCR/table/figure/figure-analysis previews as secondary derived context, preserves same-origin API access, and keeps cloud page/derived text below evidence-linked structured state.
- Remaining follow-up work is downstream adapter parity: Meeting Pack, Chart Pack, Image Evidence, Method Comparison, Obsidian export, and richer figure-image affordances must each preserve payload classification, auth, redaction, provenance, auditability, and raw/source/canonical boundaries before using these artifacts.

### Goal 11. Downstream Adapter Parity Queue

Goal 11 handles the deferred lanes that need to consume cloud page or cloud-derived artifacts without treating them as canonical evidence.

Execution order:

1. **Adapter Foundation**: create a common public adapter response that converts `cloud_paper_derived_artifacts.v1` into downstream-safe candidates while preserving payload class, source PDF checksum, page/source locators, provenance, and `derived_noncanonical` status.
2. **Meeting Pack Adapter**: allow Meeting Pack planning to cite cloud-derived candidates as secondary context only when evidence-linked structured state is absent or explicitly marked as background.
3. **Chart Pack Adapter**: allow reconstructed cloud tables to become chart snapshot inputs only as derived table sources, with warnings when numeric fields are inferred from OCR/table reconstruction.
4. **Image Evidence Adapter**: allow figure candidates to point to the authenticated image proxy route, not raw GCS objects or local paths.
5. **Method Comparison Adapter**: allow method comparison to read cloud-derived OCR/table candidates as background/inferred support, never as `claimset.resolved.json` replacement.
6. **Obsidian Export Adapter**: export cloud-derived context with provenance and source boundary labels; do not embed raw signed URLs or private storage refs.

Current status:

- Goal 11.1 first slice is implemented as a common adapter foundation: `build_cloud_paper_downstream_adapter_response` converts OCR, table, figure, and figure-analysis artifacts into downstream candidates for Meeting Pack, Chart Pack, Image Evidence, Method Comparison, and Obsidian export while preserving `derived_noncanonical` status and redacting private refs.
- Goal 11.2 first slice is implemented for Meeting Pack: `build_meeting_pack_cloud_derived_context` filters common downstream candidates to the `meeting_pack` lane and emits `meeting_pack_cloud_derived_context.v1` background-only context items with empty evidence refs, `support_type=background`, and `derived_noncanonical` status.
- Goal 11.3 first slice is implemented for Chart Pack: `cloud_derived_table` is an explicit chart source kind for table chart templates, and `build_cloud_derived_table_chart_snapshot` converts cloud-derived table candidates into `ChartDataSnapshot` with a `cloud_derived_noncanonical` warning and source checksum note.
- Goal 11.4 first slice is implemented for Image Evidence: `build_cloud_derived_figure_image_evidence_request` converts cloud-derived figure candidates into `ImageEvidenceRequest` objects that use the same-origin image proxy route as `external_image_ref`, add a representative-crop derived output, and carry a `cloud_derived_noncanonical` warning.
- Goal 11.5 first slice is implemented for Method Comparison: `build_method_comparison_cloud_derived_context` converts cloud-derived OCR/table candidates into `method_comparison_cloud_derived_context.v1` background-only items with `comparison_cell_status=missing`, empty evidence refs, and `derived_noncanonical` status.
- Goal 11.6 first slice is implemented for Obsidian export: `render_cloud_derived_obsidian_section` renders a marker-bounded, provenance-labeled markdown section for cloud-derived OCR/table/figure/figure-analysis candidates without raw signed URLs, GCS refs, or local paths.
- Goal 12.1 first slice is implemented as production-facing API wiring: cloud paper routes now expose downstream adapter output, Meeting Pack background context, Chart Pack cloud-derived table snapshots, Image Evidence request payloads, Method Comparison background context, and marker-bounded Obsidian markdown sections while reusing cloud paper read permission, not-ready handling, API key protection, and redaction checks.
- Goal 12.2 first slice is implemented as frontend affordance wiring: the cloud paper detail shell now loads downstream handoff readiness from the new route group and displays Meeting Pack, Chart Pack, Image Evidence, Method Comparison, and Obsidian readiness as non-canonical/background status cards beside the page and derived artifacts.
- Goal 12.3 first slice is implemented as explicit downstream action wiring: maintainer/reviewer/admin export permission can prepare an idempotent marker-bounded Obsidian section replacement and register downstream artifact manifests, while reader sessions see the same UI actions as locked and all outputs remain `derived_noncanonical` / `review_pending`.
- Goal 12.4 first slice is implemented as review-pending registry readback: downstream registration responses are stored in a process-local registry keyed by paper, run, and source checksum, exposed through `GET /cloud/papers/{paper_id}/downstream-artifacts/registry`, and surfaced in the detail shell as registry readback without canonical promotion.
- Goal 12.5 first slice is implemented as Firestore-backed registry persistence: the downstream registry now has memory and Firestore store implementations behind `PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE`, with `PAPERPIPE_FIRESTORE_DOWNSTREAM_REGISTRY_COLLECTION` selecting the collection, fake-client API coverage proving cross-reset readback, and memory remaining the rollback/default path.
- Goal 12.6 first slice is implemented as a real GCP Firestore registry smoke: `scripts/cloud_downstream_registry_firestore_smoke.py` writes and reads a review-pending downstream registry document in project `knudc-a01068202087`, collection `cloud_downstream_registry_demo`, passes redaction checks, and is included in the demo readiness gate.
- Goal 12.7 first slice is implemented as dynamic downstream action selection: the installed frontend reads `/cloud/papers/{paper_id}/downstream-adapter`, selects the first Chart Pack-ready table candidate and Image Evidence-ready figure candidate, calls the downstream routes with those candidate ids instead of hardcoded `table_001` / `figure_001`, and surfaces the selected ids in the detail shell. The first slice still assumes a usable candidate exists for the demo paper; a graceful no-candidate empty-state remains a follow-up.
- Goal 12.8 first slice is implemented as no-candidate downstream hardening: the frontend no longer calls Chart Pack/Image Evidence routes with empty candidate ids when the adapter has no ready table/figure candidates, and the detail shell shows `unavailable` empty-states instead.
- Goal 13.1 first slice is implemented as reviewed downstream artifact approval: `POST /cloud/papers/{paper_id}/downstream-artifacts/{artifact_id}/review` lets export-capable reviewer/admin/maintainer contexts set a registered artifact to `review_approved` or `review_rejected`, keeps registry/canonical status `derived_noncanonical`, persists the artifact-level review status through memory/Firestore registry stores, and surfaces artifact review statuses in the detail shell registry readback.
- Goal 13.2 first slice is implemented as a public-safe review audit trail: reviewed downstream artifacts now carry `review_events` with event id, artifact id, review status, reviewer role, timestamp, and a `reviewer_note_recorded` boolean, while reviewer note text remains out of public registry payloads. The detail shell shows the latest review event summary beside artifact review status.
- Goal 13.3 first slice is implemented as a read-only canonical promotion readiness gate: `GET /cloud/papers/{paper_id}/downstream-artifacts/promotion-readiness` reports `blocked` when the registry is empty or any registered artifact is pending/rejected, reports `eligible` only when every registered artifact is `review_approved`, and does not mutate canonical state. The detail shell shows `Promotion readiness` with approval counts and the first blocker.
- Goal 13.4 first slice is implemented as a read-only canonical promotion dry-run plan: `GET /cloud/papers/{paper_id}/downstream-artifacts/promotion-plan` returns `cloud_paper_downstream_promotion_plan.v1`, keeps `dry_run=true`, `mutation_applied=false`, and `canonical_status=derived_noncanonical`, blocks empty/pending/rejected registries with the same blocker contract as readiness, and emits promotion items only when every registered artifact is review-approved. This creates the handoff artifact for a future canonical write path without changing canonical state.
- Goal 13.5 first slice is implemented as promotion plan UI wiring: the cloud paper detail shell now fetches `promotion-plan` after registry/readiness reads and after downstream registration refreshes, displays `Promotion plan: blocked/ready dry-run`, item counts, first blocker, and `no canonical mutation`, and keeps the plan in the same downstream action panel as registry/readiness rather than presenting it as an executed promotion.
- Remaining follow-up work is deeper promotion wiring: actual canonical-state promotion after the dry-run plan is ready, private/internal reviewer note storage if needed, and richer candidate ranking beyond first-ready table/figure selection.

## Immediate PR1 Starter Contract

Start here when beginning implementation.

Goal:

- create the schema and local mock contract that future GCP work must satisfy
- prove public responses cannot leak private cloud refs

Files likely affected:

- `src/schemas/cloud_paper.py`
- `src/schemas/__init__.py` if package exports are needed
- `tests/test_cloud_paper_schema.py`
- `docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md` only if the implementation discovers a contract mismatch

Expected outputs:

- `CloudPaperBundleInternal`
- `CloudPaperBundlePublic`
- `CloudPaperPermissions`
- `CloudPaperProvenance`
- `CloudPaperProvenanceSummary`
- `CloudPaperHydrationState`
- `CloudPaperWarning`
- `CloudPaperAction`
- helper or method that derives `CloudPaperBundlePublic` from internal state plus current actor permissions

Tests to write first:

- internal model accepts opaque GCS object refs and checksum metadata
- public model does not include `gcs_pdf_object_ref`, `gcs_page_artifact_object_ref`, signed URL fields, local absolute paths, or credential-like fields
- status and permissions derive allowed actions deterministically
- `reader` can read page but cannot hydrate by default
- checksum fields reject empty or malformed values if validators are adopted

Suggested focused verification:

```bash
python -m pytest -q tests/test_cloud_paper_schema.py
git diff --check -- src/schemas/cloud_paper.py tests/test_cloud_paper_schema.py docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md
```

Hard fail conditions:

- a public DTO exposes internal GCS refs or signed URLs
- schema fields imply cloud page output is stronger than evidence-linked structured state
- contract code imports GCP SDKs in PR1
- schema changes are implemented outside `src/schemas/`
- tests require real GCP credentials

Exit criteria:

- PR1 can be reviewed without cloud infrastructure
- PR2 can build fake FastAPI routes against the schema without changing the schema shape
- residual open decisions are listed in the PR description

## Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Cloud upload violates user expectation | trust loss | explicit upload state, lab policy copy, audit trail |
| Page artifact becomes fake truth | scientific overtrust | keep provenance, warnings, and evidence hierarchy visible |
| Browser leaks signed URLs | data leak | backend-mediated access and short-lived URLs only |
| Existing UI forks into cloud/local modes | maintenance cost | normalized viewer payload and adapter layer |
| Download policy too broad | licensing/security issue | separate read permission from source download permission |
| GCP worker failures hide partial artifacts | stale or broken UI | explicit failed/blocked status and no silent ready state |
| Local cache outranks cloud source | stale data | source checksum and stale-cache detection |
