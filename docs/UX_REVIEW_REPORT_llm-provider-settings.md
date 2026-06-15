# UX Review Report: LLM Provider Settings

Status: Active implementation slice
Date: 2026-06-04
Owner: Lattice runtime maintainers

## Header
- Screen/Flow: `/settings` LLM provider and API key configuration.
- Goal action: Let a user connect their existing OpenAI, Anthropic, or Google Gemini API key so this machine can use cloud or hybrid LLM inference.
- Primary persona: Lab evaluator or researcher installing Lattice on an authenticated device.
- Current friction: Users must edit `config.yaml` or set environment variables manually before cloud-model features can work; in the native shell, users also expect long API keys to paste with standard macOS shortcuts.
- Success metric: A user can select provider, mode, model, paste an API key, and run an explicit live provider test from the UI; the backend stores secrets locally and returns only masked status.
- Constraints: Same-origin API only, no browser-held app API key, no API key echo in responses, and no automatic remote validation call.

## Quick Review (5 min)
- First meaningful success: User sees whether an API key is configured without seeing the secret.
- Action success: User can save provider, model, runtime mode, and key from one settings page.
- Paste success: User can paste long API keys with `Command+V` or the explicit `Paste key` action.
- Test success: User can run a deliberate minimal live provider call after saving credentials.
- Safety success: Input clears after save and status uses masked key only.
- Recovery success: User can remove the saved key.
- Trust success: Environment override is visible when provider env vars take precedence.

## Full Review
### P0
- Never return the raw provider API key in API responses.
- Keep writes behind the protected same-origin `/api/*` browser bridge.
- Store the key in the user config path, not in frontend state, bundle assets, docs, or logs.
- Keep the live test prompt minimal and unrelated to papers, notes, raw memory, or canonical state.

### P1
- Keep the setup flow familiar: mode, provider, model, API key, save. Provider choices currently include OpenAI, Anthropic, and Google Gemini.
- Keep standard macOS editing affordances available in the native app, including Paste and Select All.
- Use valid defaults for common OpenAI and Anthropic models.
- Make env override visible so users understand why a saved key may not be the active key.

### P2
- Keep the live provider test explicit, visibly user-triggered, and status-only.
- Add provider-specific model suggestions once production model policy is stable; the current Gemini default is `gemini-2.5-flash`.

### Full Review Coverage
- 6P storyboard context: Problem is manual config editing; emotion is uncertainty about where the key goes; action is opening Settings; struggle is secret handling; attempt is a single protected form with masked status; happy ending is cloud/hybrid inference configured without exposing credentials.
- BMAP: Motivation is high when AI features are unavailable; Ability improves by avoiding CLI/config editing and supporting paste for long keys; Prompt is the Settings link on Home.
- B.I.A.S: Block is secret/config complexity plus paste failure; Interpret is masked credential status; Act is Paste key, Save, or Remove saved key; Store is a clear pasted/saved/removed message.
- Peak-End: Peak is seeing `Saved locally (...last4)` after save; pit is fear of leaking a key or being forced to type it manually; transition is the input clearing; end is a clear configured status.
- Ethics: The screen must be honest about storage and avoid testing or sending keys to providers without an explicit user action.

## BMAP Diagnosis
- Motivation: Users want existing LLM accounts to power model features.
- Ability: The UI removes manual YAML editing.
- Prompt: Home exposes a Settings entry and the settings page gives direct save/remove actions.

## B.I.A.S Diagnosis
- Block: Secret fields and config paths can feel risky.
- Interpret: Masked key source and env override text clarify active state.
- Act: Save, Remove saved key, and Test live call are the core actions.
- Store: Confirmation messages and a cleared password input reduce anxiety.

## Peak-End Design Notes
- Peak: Successful save with masked local credential state.
- Pit: Raw key exposure or uncertainty about active source.
- Transition: Input clears immediately after save.
- End: User leaves with a stable configured/not-configured state.

## Concrete Changes
- Add protected runtime LLM settings API.
- Add `/settings` route and LLM provider form, including Google Gemini as a selectable cloud provider.
- Add Home Settings entry.
- Add native app Edit menu support for Cut, Copy, Paste, and Select All.
- Add explicit `Paste key` action for the API key field.
- Add masked credential status, env override state, and remove-key action.
- Add explicit `Test live call` action that reports status, model, latency, and sanitized detail only.

## Ethics Check Results
- Regret: User intent is explicit; no hidden provider validation call happens. The live provider call happens only after pressing `Test live call`.
- Black Mirror: Raw keys are not returned to the browser and are not stored in frontend assets.
- In Real-Life: The product behaves like a careful local setup assistant, not a credential collector, and respects expected macOS paste behavior.

## Next PR-Sized Actions
- Add model capability notes after provider/model policy is finalized.
- Add installed-app smoke coverage for `/settings` save/remove key.
- Add installed-app smoke coverage for `/settings` live provider test with mocked provider.

## Verification
- Backend: `uv run pytest tests/test_runtime_settings_api.py -q`.
- Frontend: `cd frontend && npm run build`.
- E2E: `cd frontend && npm run e2e:mock -- e2e/mock.spec.ts -g "settings API key field supports clipboard paste"` and `cd frontend && npm run e2e:backend -- e2e/backend.spec.ts -g "backend settings API key field supports clipboard paste"`.
- Installed app: `PAPERPIPE_INSTALLED_SETTINGS_SMOKE_PORT=8056 scripts/run_macos_installed_settings_smoke.sh`.
