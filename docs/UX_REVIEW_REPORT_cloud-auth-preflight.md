# UX Review Report: Cloud Auth Preflight

Status: Active implementation slice
Date: 2026-06-04
Owner: Lattice runtime maintainers

## Header
- Screen/Flow: Paper Notes index cloud authentication preflight for teammate-installed GCP demo access
- Goal action: Help a teammate prove that their computer can use Application Default Credentials to read the shared GCS/Firestore cloud paper demo before they try to open or upload a cloud PDF.
- Primary persona: Team member installing Lattice on their own Mac with existing GCP access.
- Current friction: A teammate may be logged into Google Cloud in the CLI but not have Application Default Credentials, or may have ADC without the exact bucket/Firestore permissions.
- Success metric: A teammate can open Paper Notes, see whether cloud access is ready, run the exact ADC commands if needed, and know whether the remaining blocker is sign-in, local config, runtime packaging, GCS permission, or Firestore permission.
- Constraints: No browser-held GCP tokens, no service account keys in frontend state, no credential file paths, no signed URLs, no raw bucket refs in paper payloads, and no personal user credentials bundled into the installer.

## Quick Review (5 min)
- First meaningful success: The cloud section says `GCP auth ready` before the user relies on shared cloud papers.
- The failure state names one next action instead of presenting an opaque API error.
- When action is needed, commands are copyable and limited to ADC login plus project selection.
- The checklist separates ADC, raw PDF bucket, page artifact bucket, and Firestore metadata.
- The UI does not ask users to paste credentials into Lattice.

## Full Review
### P0
- Do not expose tokens, credential file paths, service account JSON, signed URLs, or raw GCS object refs to the browser.
- Do not imply personal credentials are bundled with the app.
- Do not silently fall back to mock data when the user is trying to validate teammate GCP access.

### P1
- Show the preflight inside the existing Cloud paper/page section before list/search results.
- Provide explicit commands for ADC setup.
- Keep the number of visible actions small: copy commands and check again.
- Distinguish auth missing from permission denied.

### P2
- Later, add a deeper admin-only IAM checklist or link once project-level permissions are formalized.

### Full Review Coverage
- 6P storyboard context: Problem is a teammate opens the app and sees no cloud papers; emotion is uncertainty about whether login, permissions, or app config is wrong; action is checking the preflight panel; struggle is ADC vs CLI login ambiguity; attempt is copyable ADC commands plus separate access checks; happy ending is `GCP auth ready` and visible real cloud papers.
- BMAP: Motivation is high because the teammate wants to view the demo; Ability improves because the command path is short and copyable; Prompt is colocated with the cloud paper list.
- B.I.A.S: Block is opaque Google auth failure; Interpret is a single status badge plus project/collection context; Act is copy commands or check again; Store is a clear ready state before reading papers.
- Peak-End: Peak is seeing `GCP auth ready`; pit is a 403 or missing ADC; transition is running ADC login and checking again; end is ready or a specific access request.
- Ethics: The flow tells users to authenticate through Google tooling and does not collect or store their private credentials.

## BMAP Diagnosis
- Motivation: The user wants shared demo data to open on their own machine.
- Ability: ADC commands reduce the setup to a familiar terminal action.
- Prompt: The panel appears where cloud paper access is needed, not in a hidden settings page.

## B.I.A.S Diagnosis
- Block: Users may confuse `gcloud auth login` with ADC.
- Interpret: Check names clarify what passed and what failed.
- Act: `Copy commands` and `Check again` keep the next step obvious.
- Store: A ready state creates confidence that the installed app can read shared cloud data.

## Peak-End Design Notes
- Peak: `GCP auth ready` appears before paper reading.
- Pit: Missing ADC and permission-denied states are named instead of becoming generic API failures.
- End: The user finishes either with ready access or a concrete access request to a project admin.

## Concrete Changes
- Add `CloudPaperAuthPreflightResponse` and check schemas.
- Add a backend cloud auth preflight service that checks ADC, GCS raw bucket, GCS page artifact bucket, and Firestore collection reachability.
- Add `/cloud/papers/auth-preflight`.
- Add frontend API/types for the preflight response.
- Add a Cloud Auth preflight panel to `PaperNotesListPage`.
- Add copyable ADC setup commands and a manual check-again action.

## Ethics Check Results
- Regret: Users are not asked to paste private credentials into the app.
- Black Mirror: No credential paths, tokens, keys, signed URLs, or GCS object refs are exposed.
- In Real-Life: The app behaves like a teammate saying, "Sign in through Google, then I will check access."

## Next PR-Sized Actions
- Add a packaged-app first-run auth checklist screen if teammate installs become a recurring workflow.
- Add admin-facing IAM role documentation after demo permissions are finalized.
- Add a shell helper that opens `gcloud auth application-default login` guidance outside the browser.

## Verification
- Backend: targeted `tests/test_cloud_paper_api.py` preflight tests.
- Frontend: `cd frontend && npm run build`.
- E2E: `cd frontend && npm run e2e:mock -- -g "cloud auth preflight"`.
- Browser: Paper Notes cloud section shows preflight status and the real cloud PDF list.
