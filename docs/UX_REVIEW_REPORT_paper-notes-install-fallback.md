# UX Review Report: Paper Notes Install Fallback

Status: Active implementation slice
Date: 2026-06-04
Owner: Lattice runtime maintainers

## Header
- Screen/Flow: Installed Paper Notes index when no Obsidian vault is configured.
- Goal action: Open the installed app and continue to cloud papers, page viewing, PDF viewing, and runtime checks before local Obsidian integration is configured.
- Primary persona: First-time lab evaluator using the macOS alpha package for the Google Agent Challenge demo.
- Current friction: The packaged config can contain placeholder Obsidian paths, causing `/paper-notes` to return 404 and making the installed app look broken even when cloud paper/page APIs are healthy.
- Success metric: `/paper-notes` returns a 200 empty saved-note index while `/paper-notes/home-context` remains limited, so the UI can keep showing cloud papers and the existing detail shell.
- Constraints: Preserve the existing Paper Notes UI, FastAPI/Pydantic route contract, same-origin browser API calls, and the boundary that Obsidian notes are optional local enrichment rather than the only runtime source.

## Quick Review (5 min)
- First meaningful success: A first-time evaluator can open the installed app without seeing a hard Paper Notes API failure.
- Empty-state success: Missing Obsidian vault behaves like an empty local notes collection, not a broken backend.
- Cloud success: Cloud paper rows, cloud page data, and PDF rendering remain reachable from the same Paper Notes surface.
- Trust success: The app does not imply local notes exist when the vault is missing.
- Review success: The fallback is API-contract-level and does not add browser secrets, hidden local paths, or a parallel UI state.

## Full Review
### P0
- Treat missing or unreadable Obsidian index as limited local context, not as a fatal Paper Notes index failure.
- Keep cloud paper/page data usable when local vault setup is incomplete.
- Do not expose placeholder local paths or private filesystem paths through the browser-visible empty state.

### P1
- Preserve `PaperNoteListResponse` so existing frontend list/search consumers do not need a special error branch.
- Clamp empty results to `page=1`, `total_pages=1`, and the requested `page_size` for stable pagination.
- Keep `/paper-notes/home-context` behavior aligned with the list endpoint by preserving its limited-context semantics.

### P2
- Later add a settings affordance that lets a user select or repair the Obsidian vault path from the installed app.
- Later distinguish "no vault configured" from "vault configured but unreadable" in a safe, masked diagnostic payload if the UI needs it.

### Full Review Coverage
- 6P storyboard context: Problem is first-run uncertainty; emotion is "the app is broken"; action is opening Paper Notes; struggle is placeholder local config; attempt is a non-fatal empty saved-note index plus cloud papers; happy ending is reading a cloud-processed paper before local vault setup.
- BMAP: Motivation is high during demo setup; Ability improves because no Obsidian setup is required for cloud reading; Prompt remains the existing cloud paper list and detail route.
- B.I.A.S: Block is a hard 404; Interpret is an empty saved-note index; Act is opening cloud papers or configuring a vault later; Store is confidence that installation works even with partial local setup.
- Peak-End: Peak is successfully opening a cloud page/PDF; pit is seeing "vault not found"; transition is treating local notes as optional; end is the app remains usable.
- Ethics: The fallback must not pretend missing local notes were searched or synced; it only avoids overstating the failure as an app crash.

## BMAP Diagnosis
- Motivation: Strong because evaluators want to see cloud page/PDF behavior immediately.
- Ability: Improved by removing the need to configure Obsidian before the installed app can be used.
- Prompt: Existing Paper Notes and cloud paper rows remain the prompt; no new CTA is required in this slice.

## B.I.A.S Diagnosis
- Block: A 404 from `/paper-notes` looks like product failure.
- Interpret: A 200 empty index is understood as "no local saved notes yet."
- Act: The user can open cloud papers or later configure Obsidian without being forced into setup.
- Store: First-run memory becomes "cloud demo works; local vault is optional setup" instead of "the app failed."

## Peak-End Design Notes
- Peak: Opening a ready cloud paper in the existing detail shell.
- Pit: Placeholder vault paths causing a route failure.
- Transition: API fallback turns missing local index into stable empty state.
- End: The app remains readable and demo-safe.

## Concrete Changes
- Add a `PaperNoteListResponse` empty-index fallback for `/paper-notes` when vault resolution or index building fails.
- Preserve requested `page_size` and clamp empty pagination to page 1.
- Add regression coverage for the missing-index fallback.

## Ethics Check Results
- Regret: Users are not tricked into thinking local notes are configured; the response is simply empty.
- Black Mirror: The fallback does not expose local paths, cloud credentials, signed URLs, or hidden sync state.
- In Real-Life: The app behaves like a helpful assistant saying "no local notes are available yet" while still letting the user read cloud papers.

## Next PR-Sized Actions
- Add a masked settings/status card for configuring the Obsidian vault path.
- Add installed-app smoke coverage that checks `/paper-notes` does not hard-fail with packaged placeholder config.
- Add a small UI hint only if user testing shows the empty saved-note state is confusing.

## Verification
- Targeted backend regression: `uv run pytest tests/test_paper_notes_api.py -q -k "paper_notes_list_returns_empty_index_when_index_fails or paper_notes_home_context_marks_note_context_limited_when_index_fails"`.
- Installed-app smoke after rebuild: `/paper-notes?...` returns 200 empty list with placeholder vault config while `/cloud/papers` remains 200.
