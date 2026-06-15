# UX Review Report: Submission Demo App

Screen/Flow: contest submission app startup -> cloud paper list/detail
Goal action: Evaluator opens the submitted app window and sees the bundled real paper page without Google Cloud sign-in.
Primary persona: contest evaluator on a prepared computer
Current friction: GCP-backed demo can require local ADC setup, which is unsuitable for sealed file submission.
Success metric: `/papers/cloudpdf_lab_001_fe476330a3bd?source=cloud` loads with real title, abstract, and body excerpt from the bundled snapshot.

## Quick Review (5 min)
- Choices stay narrow: open app, read bundled paper, inspect page/derived context.
- Benefit is immediate: the actual paper page appears without credential setup.
- Next action is clear: open the bundled cloud paper snapshot.
- Feedback is explicit: auth preflight reports `Submitted demo ready`.
- Ethics check: no user credentials, service account keys, signed URLs, or source PDFs are bundled.

## Full Review
P0: The submitted app must not depend on the evaluator's GCP/ADC state. The bundled env forces `PAPERPIPE_SUBMISSION_DEMO_BUNDLE=1`, mock storage, memory metadata, and the real snapshot paper id.

P1: Avoid misleading shell/browser handoff. macOS and Windows submission packages should open an app window first; helper scripts are fallback only.

P2: Avoid misleading auth copy. Submission mode uses `Submitted demo ready` instead of `GCP auth ready`, with setup commands hidden.

P2: Keep upload out of the evaluation path. The cloud upload button is disabled in submission bundle mode because the submitted artifact is read-only.

6P storyboard context:
Problem: evaluator has a prepared machine and a submitted file, not project credentials.
Emotion: they need confidence that the demo works immediately.
Action: they launch Lattice from a desktop app icon/window.
Struggle: credential setup would derail evaluation.
Attempt: app-bundled env and snapshot remove external setup.
Happy Ending: the real Alzheimer biomarker paper page opens directly.

BMAP:
Motivation is high because the evaluator wants fast verification. Ability improves by removing GCP setup. Prompt is the visible app window, `Submitted demo ready` state, and direct cloud paper start path.

B.I.A.S:
Block is reduced by one clear ready state. Interpret is improved by avoiding GCP-specific language. Act friction is lower because no commands are needed. Store is strengthened by immediate real content.

Peak-End:
Peak is first launch showing the real extracted title/body. Pit is credential uncertainty; it is repaired by offline mode. Transition from launch to paper detail is direct. End state is a stable read-only demo.

Ethics checks:
Regret: safe; credentials are not embedded.
Black Mirror: low risk; snapshot is static and read-only.
In Real-Life: helpful assistant behavior; it does not ask evaluators to authenticate into a private cloud project.

## BMAP Diagnosis
- Motivation: evaluation urgency is enough.
- Ability: offline snapshot removes project access and CLI setup.
- Prompt: status badge and direct start path make the available action obvious.

## B.I.A.S Diagnosis
- Block: no credential checklist in submission mode.
- Interpret: `Submitted demo ready` accurately describes the mode.
- Act: upload is disabled to prevent unsupported writes.
- Store: immediate real paper content creates confidence.

## Peak-End Design Notes
- Peak: real extracted paper page loads on first open.
- Pit: GCP auth friction is removed.
- Transition: list/detail route remains the same as GCS demo.
- End: evaluator can inspect content without side effects.

## Concrete Changes
- Backend: submission snapshot loader under `src/services/cloud_paper_submission_bundle.py`.
- Backend: auth preflight status `submission_bundle`.
- Frontend: status label `Submitted demo ready` and read-only upload behavior.
- Packaging: `submission-demo.env` and `submission_demo` resources copied into the contest app.
- Windows packaging: WebView2 native launcher opens `LatticeRuntime.exe` in a desktop window; browser/PowerShell helpers remain fallback paths.

## Ethics Check Results
- Regret: pass.
- Black Mirror: pass.
- In Real-Life: pass.

## Next PR-Sized Actions
- Add a multi-paper submission snapshot when licensing/permission boundaries are confirmed.
- Add a visible read-only hint on the upload button tooltip if evaluator feedback asks for it.
- Add Windows Authenticode signing once a code-signing certificate is available.
- Add notarized macOS distribution once a Developer ID certificate is available.
