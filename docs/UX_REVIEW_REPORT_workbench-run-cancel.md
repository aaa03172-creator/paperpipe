Status: Active
Date: 2026-03-28
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: `AnalysisWorkbench` run controls while a deep-read job is queued or running (`/workbench/:paperId`)
- Goal action: Start a deep read, then stop it safely from the same screen if the run was launched by mistake, is taking too long, or needs to be reconfigured.
- Primary persona: Busy research operator using the workbench as the main control surface for reading and rerunning papers.
- Current friction: The backend already supports `POST /jobs/{job_id}/cancel`, but the workbench did not expose it. Once a run started, the user had no direct way to stop it from the UI.
- Success metric: When a run is active, the workbench replaces the run CTA with `Cancel run`, cancellation gives immediate feedback, and the user is not forced into CLI/API work to stop the job.
- Constraints:
  - Preserve the existing FastAPI job lifecycle contract.
  - Keep the current workbench structure and dark-first token system.
  - Do not turn cancellation into a destructive action on saved artifacts; it only stops the current run.

## Quick Review (5 min)
- The existing flow had an obvious action to start a run but no matching stop control.
- That asymmetry matters most in the workbench because this is the user's long-stay operational surface.
- The smallest safe fix is not a new workflow. It is exposing the already-existing cancel endpoint at the same level as `Run deep read`.

## Full Review
### P0
- A running deep read without a visible stop action makes the workbench feel less trustworthy than the backend actually is.
- The stop action should be available only when a job is active, and it should not imply that saved artifacts are rolled back.

### P1
- Cancellation should use the same notice language and terminal logging pattern as the other workbench actions.
- Mobile and desktop need the same behavior so the user does not learn one control model on desktop and lose it on smaller screens.

### P2
- If deep-read execution becomes slower or more asynchronous later, this lane will benefit from richer progress/cancel/retry states.
- For now, a bounded cancel affordance plus explicit success/error feedback is enough.

### Full Review Coverage
- 6P storyboard context:
  - Problem: a user can start a run but cannot stop it from the UI.
  - Emotion: the run controls feel one-way and more operator-hostile than necessary.
  - Action: open workbench, start deep read, realize it should stop.
  - Struggle: there is no visible escape hatch even though the backend supports one.
  - Attempt: user waits, refreshes, or leaves the screen instead of acting directly.
  - Happy Ending: user cancels the run in place and keeps the current saved artifacts untouched.
- BMAP:
  - Motivation is high because cancelling a bad run saves time and confusion.
  - Ability is the gap: the user cannot act on that motivation without UI exposure.
  - Prompt should be strong and local: the active run state itself should switch the CTA to cancellation.
- B.I.A.S:
  - Block: missing stop control.
  - Interpret: users may assume cancellation is unsupported, risky, or hidden behind operator-only tooling.
  - Act: the next action after a mistaken run should be `Cancel run`, not “go find the API”.
  - Store: a balanced start/stop control pair makes the workbench feel more dependable.
- Peak-End:
  - Peak is the moment the user realizes they can safely stop a run without leaving the workbench.
  - Pit is the current one-way feeling after clicking `Run deep read`.
  - Transition is from active run state to cancelled state with explicit confirmation.
  - End should reassure the user that saved artifacts remain as-is.
- Ethics:
  - Regret: cancellation should reduce wasted time, not cause silent data loss.
  - Black Mirror: avoid language that overstates what cancellation does.
  - In Real-Life: a research tool should make it easy to stop the wrong run quickly.

## BMAP diagnosis
- Motivation: High. Users need a quick correction path during long-running work.
- Ability: Previously weak because the only stop path was backend-facing.
- Prompt: The active-run state should naturally surface `Cancel run`.

## B.I.A.S diagnosis
- Block: no visible stop control in the workbench.
- Interpret: users can mistake “not exposed” for “not supported.”
- Act: stopping the run should be one click from the same control cluster.
- Store: balanced controls improve trust in repeated use.

## Peak-End design notes
- Peak: turning an active run into an understandable, cancellable state.
- Pit: start-only controls create a subtle sense of lock-in.
- Transition: switch from `Run deep read` to `Cancel run` only while the job is active.
- End: leave the user with a clear cancellation confirmation and preserved artifacts.

## Concrete changes
- Add a frontend API helper for `POST /jobs/{job_id}/cancel`.
- Replace `Run deep read` with `Cancel run` while a job is active, on both desktop and mobile.
- Add inline cancellation warning/success/error notices that match existing workbench action patterns.
- Append a terminal log line for cancellation and keep existing saved artifacts untouched.
- Add targeted mock E2E coverage for `run -> cancel`.
- Add backend-served browser coverage for `queued -> cancel -> cancelled` so the control is verified beyond mock mode.

## Ethics check results
- Regret: Low. This reduces wasted runs and does not remove existing data.
- Black Mirror: Low if the copy stays explicit that only the current run stops.
- In Real-Life: A user should feel more in control, not more trapped, after launching a run.

## Next PR-sized actions
- If real runs become long-lived, add a clearer “cancelling” progress state and optional retry guidance.
- Consider a small readiness/status surface that explains why a run is stuck before cancellation becomes necessary.
- Revisit stage/debug naming in the same control strip so the whole run cluster reads with one voice.

## Verification notes
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workbench can cancel an active deep read run from the browser"` should cover the backend-served browser path.
- This browser path should confirm the same three signals as the mock test: visible cancel CTA, success notice + terminal log, and persisted backend `cancelled` job state.
