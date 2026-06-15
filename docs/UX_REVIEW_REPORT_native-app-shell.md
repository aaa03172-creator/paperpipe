# UX Review Report - Native App Shell

Screen/Flow: macOS installed app launch
Goal action: Open `Lattice.app` and read/use papers inside an app window
Primary persona: Researcher or demo reviewer using the local Lattice runtime
Current friction: The app icon starts a local server and opens a separate web browser, which feels less like a native installed product
Success metric: `Lattice.app` opens a macOS window, serves `/ui` internally, and does not launch the default browser for the primary app surface

## Quick Review

- Choice count: one primary launch target, `Lattice.app`.
- Benefit first: the user sees the Lattice product window, not server/browser mechanics.
- Next action: app opens directly to the paper UI.
- Feedback: loading/error states belong inside the app window.
- Ethics: no hidden external calls; local runtime and localhost UI remain transparent in docs.

## Full Review

P0:
- Replace browser launch as the primary installed-app surface with a native macOS WebView window.
- Keep explicit CLI/smoke paths working by forwarding arguments to the packaged runtime.

P1:
- Show an in-app loading state while the local runtime starts.
- Reuse an existing healthy localhost runtime instead of failing or spawning duplicates.

P2:
- Keep the assisted launcher as compatibility only.
- Keep Gatekeeper/notarization caveat explicit.

Framework coverage:
- 6P: researcher wants to open the installed product, not reason about localhost; the happy ending is a familiar app window with the paper library ready.
- BMAP: motivation is high before a demo; ability improves when browser choice disappears; the app icon is the prompt.
- B.I.A.S: the launch flow blocks less noise, interprets as a real app, removes action friction, and stores a more polished memory.
- Peak-End: the first window is the peak; clean shutdown and no orphan browser tab improve the end.
- Ethics: local runtime behavior is documented; no coercive prompt, tracking, or surprise network surface is added.

## BMAP Diagnosis

- Motivation: stage-demo confidence and day-to-day researcher trust.
- Ability: reduce cognitive effort by removing the browser handoff.
- Prompt: direct app icon launch.

## B.I.A.S Diagnosis

- Block: browser/server details are no longer the first visual signal.
- Interpret: installed app reads as a product, not a developer tool.
- Act: double-click once, then use.
- Store: native window and local logs create a more predictable support model.

## Peak-End Design Notes

- Peak: Lattice window appears quickly with an in-app loading state.
- Pit: startup failure should show a clear in-app error pointing to the log.
- Transition: runtime start moves into WebView load without opening Safari/Chrome.
- End: closing the app should stop the runtime it started.

## Concrete Changes

- Add a small AppKit/WKWebView launcher for `Lattice.app`.
- Start `LatticeRuntime start --no-open` inside the app.
- Render `http://127.0.0.1:8046/ui` inside the app window.
- Forward explicit CLI arguments to `LatticeRuntime` for existing smoke scripts.

## Ethics Check Results

- Regret: acceptable; the app behaves closer to the user's expectation.
- Black Mirror: no added surveillance, lock-in, or external inference path.
- In Real-Life: a helpful assistant opens the workspace directly instead of handing the user to another app.

## Next PR-Sized Actions

1. Add and compile the native app shell.
2. Rebuild and install the app, then verify `open /Applications/Lattice.app` creates a Lattice window.
3. Update release/readiness docs to state that browser-wrapper launch is deprecated as the primary flow.
