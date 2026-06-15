# UX Review Report: Cloud Paper/Page

Status: Active implementation slice
Date: 2026-06-01
Owner: Lattice runtime maintainers

## Header
- Screen/Flow: Paper Notes index cloud PDF upload, paper detail cloud paper/page, derived artifacts, and downstream handoff read path
- Goal action: Select a real PDF from the installed UI, upload it through the backend-mediated cloud paper flow, open the resulting cloud paper detail shell, and read extracted title, abstract, and body text while understanding whether it is ready, processing, blocked, read-only, or available offline.
- Primary persona: Lab researcher using an authenticated lab device.
- Current friction: Cloud processing can feel like a separate backend job unless upload, readiness, permission, extraction, and hydration state are visible in the existing paper workspace.
- Success metric: A researcher can upload one real PDF, land on the cloud paper detail shell, see extracted title/abstract/body text rather than mock text, inspect OCR/table/figure derived artifacts, see Meeting Pack/Chart Pack/Image Evidence/Method Comparison/Obsidian handoff readiness, and understand why local hydration is available or locked without seeing cloud internals.
- Constraints: Use the existing Paper Notes UI, `--pp-*` tokens, same-origin API calls only, no browser-held GCP secrets, no raw GCS refs or absolute local paths in browser-visible payloads.

## Quick Review (5 min)
- First meaningful success: A ready cloud paper appears in the Paper Notes index and opens into the existing paper detail shell with normalized page text.
- Upload success: The Cloud paper/page section has a single PDF upload button that opens the native picker and lands directly on the processed cloud page when extraction completes.
- Extraction success: The processed page shows real title, abstract, and body snippets extracted from the uploaded PDF, not placeholder mock text.
- Derived artifact success: OCR/table/figure hints appear in the same detail shell as source-linked secondary artifacts, not as replacement evidence.
- Downstream handoff success: Meeting Pack, Chart Pack, Image Evidence, Method Comparison, and Obsidian readiness are visible as background/non-canonical routes before any export or persistence action.
- Dynamic candidate success: Chart Pack and Image Evidence cards show which downstream adapter table/figure candidate was selected for the route call, so the action feels traceable rather than hardcoded.
- Empty-state success: If no table or figure candidate is ready, Chart Pack and Image Evidence show `unavailable` instead of silently calling a downstream route with an empty id.
- Review success: Registry readback can show artifact-level `review_approved` / `review_rejected` status without implying canonical promotion.
- Review audit success: Registry readback can show a public-safe latest review event summary, including reviewer role and whether a note was recorded, without exposing reviewer note text.
- Promotion readiness success: The UI can show whether downstream artifacts are eligible for canonical promotion, or blocked by pending/rejected/missing registry state, without mutating canonical state.
- Promotion plan success: The UI can show the read-only dry-run promotion plan, item count, and `no canonical mutation` state after readiness is checked.
- Current search success: A Paper Notes search can also surface readable cloud page matches without mixing them into canonical saved-note results.

## Full Review
### P0
- Keep cloud credentials and private object refs out of browser state.
- Keep uploaded PDF bytes as raw source handled by backend-mediated same-origin API calls; only derived snippets and public bundle state return to the browser.
- Do not present cloud page output as stronger than evidence-linked structured state.
- Do not present OCR/table/figure derived artifacts as stronger than evidence-linked structured state.
- Do not present downstream handoff readiness or explicit export/register actions as canonical evidence.
- Hydration/download must remain permission-gated.

### P1
- Show ready, processing, failed, blocked, and read-only states where users already scan paper state.
- Keep upload in the existing Paper Notes cloud section and route directly to the detail shell after success.
- Use a separate cloud upload button so the existing local `Import PDF` fallback keeps its current meaning.
- Keep the page preview inline and provide a detail-shell route so the user does not leave the existing paper workspace.
- Keep derived OCR/table/figure visibility inside the same detail shell so users do not need a separate cloud operations UI.
- Keep downstream handoff visibility and permission-gated export/register actions inside the same detail shell so users can see what is possible without opening five separate tool screens.
- Show selected table/figure candidate ids for Chart Pack and Image Evidence so users can connect the visible downstream action to the adapter candidate list.
- Show no-candidate empty-states for Chart Pack and Image Evidence instead of silent failure or misleading readiness.
- Show artifact-level review statuses in registry readback while keeping top-level registry status pending until all artifacts are reviewed.
- Show latest public-safe review event summaries while keeping reviewer note text out of browser-visible registry payloads.
- Show read-only promotion readiness with approved/total counts and the first blocker.
- Show read-only promotion plan status with dry-run item counts, first blocker, and explicit no-mutation copy.
- Make failures legible with warnings instead of silent disabled buttons.
- Keep cloud page search results visually separate from saved-note search results until source/evidence lineage can be unified safely.

### P2
- Keep improving hydrated-bundle reuse inside downstream local artifact readers.
- Later, unify cloud/local search only if canonical note search can preserve the cloud page source boundary.

### Full Review Coverage
- 6P storyboard context: Problem is cloud state invisibility; emotion is uncertainty; action is preview/download/search/read derived artifacts/inspect handoff readiness/inspect selected table/figure candidates/prepare export/register artifacts/review registered artifacts/read review audit summaries/check promotion readiness/check promotion dry-run plan; struggle is permission, processing, candidate selection, review state, auditability, promotion safety, and source-boundary ambiguity; attempt is a compact cloud rail plus separated cloud matches, derived artifact panels, downstream handoff panel, selected candidate labels, registry review statuses, public-safe review events, read-only promotion readiness, read-only promotion plan, and permission-gated commands; happy ending is page plus OCR/table/figure and safe downstream context from an authenticated device.
- BMAP: Motivation is high when a user has a PDF ready; Ability improves by using a native file picker and avoiding a separate cloud UI; Prompt is the cloud upload button, status/action row, `Cloud page matches` block during search, a derived artifacts panel, a downstream handoff panel, and explicit export/register buttons inside detail.
- B.I.A.S: Block is distrust of remote storage and opaque automation; Interpret is status plus provenance plus separated cloud-match/derived-artifact/handoff/selected-candidate/action/registry/review labeling; Act is preview, inspect OCR/table/figure, inspect downstream readiness and selected candidates, prepare Obsidian export, register downstream artifacts, read back review-pending or artifact-reviewed registry state, open detail, or hydrate; Store is remembered as available offline only after backend hydration succeeds, and downstream write actions remain non-canonical.
- Peak-End: Peak is the detail-shell page view with source-linked derived artifacts, visible downstream handoff readiness, selected table/figure ids, permission-gated export/register actions, or finding processed cloud text from the existing search box; pit is a failed/blocked paper, empty cloud match, missing artifact, unavailable adapter route, missing candidate, or export permission lock; transition is processing to ready; end is either readable, hydrated, stale, safely handoff-ready, honestly unavailable for a lane, prepared as review-pending, or clearly locked.
- Ethics: Cloud upload and hydration state must be explicit, reversible by policy, and not pressure users into downloading sensitive material.

## BMAP Diagnosis
- Motivation: Strong for second-device reading and lab-shared processed papers.
- Ability: Improved by showing cloud papers inside Paper Notes and using same-origin API calls.
- Prompt: The compact cloud section prompts preview/detail-view first, cloud page matches appear during search, and hydration is only offered when allowed.
- Prompt: The cloud upload button is colocated with ready/processing/needs-check counts so upload feels like part of the cloud paper flow rather than local note import.
- Prompt: Downstream handoff cards prompt inspection first, then permission-gated prepare/register actions only after the non-canonical boundary is visible.
- Prompt: Selected table/figure labels make Chart Pack and Image Evidence actions legible as adapter-selected routes instead of invisible defaults.
- Prompt: `unavailable` badges tell the user when a lane needs a derived table or figure before it can be used.
- Prompt: Registry artifact review statuses tell the user which handoff artifacts have been reviewed without changing their canonical boundary.
- Prompt: Latest review event summaries tell the user that a human review action happened without revealing private note text.
- Prompt: Promotion readiness tells the user whether canonical promotion is blocked or eligible before any write action exists.
- Prompt: Promotion plan tells the user what a future canonical promotion would prepare while clearly stating that no mutation has been applied.

## B.I.A.S Diagnosis
- Block: Users may not know whether a paper is stored remotely, locally, or both.
- Interpret: Status chips separate cloud readiness from local availability.
- Act: Ready papers can load a normalized page preview, open the existing detail shell, or be opened from separated search matches; hydration is locked unless policy allows it.
- Act: Users can choose a PDF through the cloud upload button and are routed directly to the resulting detail shell after upload and extraction.
- Act: Downstream readiness can be inspected in place; export/register actions are explicit, permission-gated, and remain review-pending.
- Act: Chart Pack and Image Evidence route calls now follow the selected downstream adapter candidate ids shown in the panel.
- Act: When no selected candidate exists, Chart Pack and Image Evidence stay as empty-states and do not call a route with an empty id.
- Act: Export-capable reviewer/admin/maintainer contexts can approve or reject registered downstream artifacts through the API; the UI readback shows artifact-level review state.
- Act: Public readback shows reviewer role, review status, timestamp-backed event presence, and whether a note was recorded, while excluding note contents.
- Act: Users can inspect promotion readiness, approved/total counts, and first blocker; no canonical mutation is performed.
- Act: Users can inspect promotion plan dry-run status and item counts; the UI says `no canonical mutation` so readiness is not mistaken for promotion.
- Store: Hydration result is reflected as `Available offline` without exposing local paths; downstream registry readback is shown as review-pending rather than canonical memory.

## Peak-End Design Notes
- Peak: Seeing processed text in the existing detail shell confirms the server-made page is reusable without switching workspaces.
- Peak: Seeing the uploaded PDF immediately become title, abstract, and body snippets confirms real extraction worked.
- Peak: Seeing downstream handoff readiness next to the page confirms the cloud processing result can feed lab workflows while staying non-canonical.
- Peak: Seeing selected table/figure candidate ids confirms the table or figure handoff is attached to an actual adapter candidate.
- Peak: Seeing `unavailable` for a missing table or figure preserves trust because the UI names the missing prerequisite.
- Peak: Seeing an individual artifact move to `review_approved` confirms human review without over-claiming canonical promotion.
- Peak: Seeing `maintainer review event / note recorded` makes the review action feel auditable without exposing private note text.
- Peak: Seeing `eligible / 5/5 approved` confirms the gate is satisfied without actually promoting the artifacts yet.
- Peak: Seeing `ready dry-run / 5 items / no canonical mutation` confirms the next write path is prepared but still not executed.
- Peak: Preparing an Obsidian section or registering downstream artifacts gives a concrete next step while still showing `review_pending`.
- Peak: Seeing registry readback after registration confirms the action was recorded without implying canonical promotion.
- Pit: Failed and blocked states can feel like dead ends; warning text gives the next diagnostic handle.
- End: The row should end in a clear state: preview loaded, processing still running, or download locked by policy.

## Concrete Changes
- Add cloud paper list API contract for the Paper Notes UI.
- Add browser API helper for cloud PDF upload: create upload intent, upload source PDF, complete processing, and return the ready bundle.
- Add a cloud PDF upload button and hidden PDF input to `frontend/src/app/pages/PaperNotesListPage.tsx`.
- Route successful cloud uploads to `/papers/{paper_id}?source=cloud`.
- Replace the completed-upload default page processor with real PyMuPDF text extraction for title, abstract, and body snippets.
- Preserve existing local `Import PDF` behavior as the manual local note fallback.
- Add backend tests proving uploaded real PDF text appears in cloud page blocks.
- Add backend Playwright E2E proving the upload button selects a real PDF and opens the cloud detail page with extracted text.
- Add cloud-backed paper rows to `frontend/src/app/pages/PaperNotesListPage.tsx`.
- Add inline normalized page preview for ready cloud papers.
- Add `/papers/{paper_id}?source=cloud` detail-shell rendering in `frontend/src/app/pages/PaperNoteDetailPage.tsx`.
- Add cloud-derived OCR/table/figure panel in `frontend/src/app/pages/PaperNoteDetailPage.tsx`.
- Add cloud-derived downstream handoff panel in `frontend/src/app/pages/PaperNoteDetailPage.tsx`.
- Add selected table/figure candidate labels to the Chart Pack and Image Evidence handoff cards.
- Add no-candidate empty-states to Chart Pack and Image Evidence handoff cards.
- Add artifact-level review status readback to the downstream registry display.
- Add public-safe latest review event summaries to the downstream registry display.
- Add read-only promotion readiness to the downstream registry display.
- Add read-only promotion plan display with dry-run item count and no-mutation state.
- Add permission-gated downstream export/register actions in `frontend/src/app/pages/PaperNoteDetailPage.tsx`.
- Add review-pending downstream registry readback in `frontend/src/app/pages/PaperNoteDetailPage.tsx`.
- Add redacted cloud page search contract and Paper Notes `Cloud page matches` affordance.
- Add locked hydration affordance when `hydrate_download` is absent.
- Add local hydration state display as `Available offline`, backed by manifest readback after refresh.

## Ethics Check Results
- Regret: The UI does not trick users into uploading or downloading; it shows read-only status when policy blocks local hydration.
- Regret: The local import fallback and cloud upload action are separate buttons, so users are not surprised by where a selected PDF goes.
- Black Mirror: Browser-visible state does not include cloud credentials, signed URLs, bucket refs, service accounts, absolute local paths, or durable raw image object refs.
- Black Mirror: Raw PDF bytes are not displayed back to the browser; browser-visible page data is derived snippet text with public provenance.
- Black Mirror: Handoff readiness, export/register actions, and registry readback do not imply evidence-backed export, claimset replacement, canonical promotion, or hidden local download.
- Black Mirror: Selected downstream candidate ids are adapter artifact ids only; they do not expose raw storage refs or durable image URLs.
- Black Mirror: Missing candidates remain missing; the UI does not fabricate table/figure readiness from page text.
- Black Mirror: Review approval is not canonical promotion and does not create claim/evidence truth.
- Black Mirror: Reviewer notes are not exposed in public registry payloads; only note presence is surfaced.
- Black Mirror: Promotion readiness is not promotion; it does not write canonical structured state.
- Black Mirror: Promotion plan is still dry-run-only; the UI explicitly states that no canonical mutation has been applied.
- In Real-Life: A lab member can explain the flow as "server processed, local app displays, local download only if permitted."
- In Real-Life: A lab member can explain upload as "I selected a PDF, the server extracted text, and the viewer opened the processed page."

## Next PR-Sized Actions
- Extend detail-shell route coverage beyond ready state into processing, stale, and locked hydration states.
- Add progress/polling UI if cloud page extraction becomes asynchronous instead of current request-complete behavior.
- Connect export/register results into actual canonical promotion write flows only after the dry-run plan has review, audit, rollback, and migration coverage.
- Add richer candidate ranking before treating dynamic table/figure selection as production-complete.
- Add richer figure-image affordances or split OCR/table/figure tabs only after each route preserves provenance and canonical-state boundaries in the visible UI.

## Verification
- Backend API contract: `tests/test_cloud_paper_api.py` list/read/hydration-state redaction coverage.
- Hydration contract: manifest readback returns redacted hydrated state and stale status on checksum drift.
- Frontend: `cd frontend && npm run build`.
- Real PDF extraction backend: `/Users/jangseongjin/paperpipe-projects/main/.venv314/bin/python -m pytest tests/test_cloud_paper_processing_worker.py tests/test_cloud_paper_api.py -q`.
- Real PDF upload E2E: `cd frontend && npm run e2e:backend -- --grep "backend cloud PDF upload opens a cloud paper page with extracted title abstract and body text"`.
- Playwright: `cd frontend && npm run e2e:mock -- -g "cloud paper opens"`.
- Downstream actions: `uv run pytest tests/test_cloud_paper_api.py::test_cloud_api_prefixed_routes_bridge_same_origin_browser_calls -q`.
- Registry readback: `uv run pytest tests/test_cloud_paper_api.py::test_cloud_api_prefixed_routes_bridge_same_origin_browser_calls tests/test_cloud_paper_schema.py -q`.
- Firestore registry persistence: `uv run pytest tests/test_cloud_paper_downstream_registry_store.py tests/test_cloud_paper_api.py::test_cloud_downstream_registry_uses_firestore_store_when_configured -q`.
- Real GCP registry smoke: `uv run --extra cloud python scripts/cloud_downstream_registry_firestore_smoke.py --project-id knudc-a01068202087 --registry-collection cloud_downstream_registry_demo --json`.
- Dynamic downstream candidate selection: `cd frontend && npm run e2e:mock -- -g "cloud paper opens"` checks `Selected table table_001` and `Selected figure figure_001`.
- No-candidate downstream empty-state: `cd frontend && npm run e2e:mock -- -g "downstream handoff shows empty states"`.
- Reviewed artifact registry readback: `cd frontend && npm run e2e:mock -- -g "registry readback shows reviewed"`.
- Review event browser smoke: `paper_mock_reviewed` shows `maintainer review event / note recorded`.
- Promotion readiness: `cd frontend && npm run e2e:mock -- -g "promotion readiness becomes eligible"`; browser smoke checks blocked and eligible states.
- Promotion plan: `cd frontend && npm run e2e:mock -- -g "promotion readiness becomes eligible|registry readback shows reviewed"` checks blocked/ready dry-run plan state and no-mutation copy.
- Search parity: `pytest tests/test_cloud_paper_api.py tests/test_cloud_paper_schema.py tests/test_cloud_paper_access_policy.py -q`; `cd frontend && npm run e2e:mock -- -g "cloud page matches|cloud paper opens"`.
