# UX Review Report - First Paper Activation

Status: Current review artifact
Date: 2026-04-29
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: README Quick Start -> `lattice start` -> `http://127.0.0.1:8000/ui/papers#import-pdf` -> imported paper detail -> workbench/deep-read next step
- Goal action: a first-time operator can add one local PDF, see the saved note, and understand the next review/deep-read action without guessing where `paper_id` comes from.
- Primary persona: first-time single-operator biomedical researcher trying to evaluate Lattice from a repo checkout.
- Current friction: the implemented Web import path exists, but the README Quick Start stopped at server startup and the CLI reference listed `deepread <paper-id-or-doi>` before explaining how a local PDF becomes a saved paper; a missing first-run `config.yaml` could also stop `doctor` before it became useful.
- Success metric: the README gives one concrete first-paper path using `/ui/papers#import-pdf`, the CLI reference exposes `paperpipe import-pdf <path>` as the matching terminal bridge, and `paperpipe doctor --fix` can create a safe local starter config before diagnosis.
- Constraints:
  - Keep the current FastAPI + Vite/React Router runtime contract.
  - Do not invent a new canonical paper store.
  - Do not imply Research DNA has a main viewer route.
  - Keep demo/sample content marked as illustrative, not source evidence.

## Quick Review (5 min)
- The main activation problem is discoverability, not absence of ingestion.
- `/paper-notes/import-pdf` and the `/papers` Import PDF UI already provide the first local-PDF entry path.
- The README should move the user from "server is running" to "my first saved paper is visible" before introducing broader lanes.
- The CLI reference should keep Web import as the first-session front door while exposing the matching CLI bridge for terminal-first operators.

## Full Review
### P0
- Add a first-paper path immediately after Quick Start so the first useful action is visible before the long runtime/security material.
- Name `http://127.0.0.1:8000/ui/papers#import-pdf` as the recommended first local-PDF URL after `lattice start`.
- Explain that the imported note produces a `userpdf-*` paper id that can be used for review/deep-read paths.
- Add `paperpipe doctor --fix` as a safe bootstrap for missing local config and project-local runtime folders.

### P1
- Clarify that `paperpipe deepread <paper-id-or-doi>` expects an already saved paper, DOI-backed paper, or discoverable local PDF.
- Separate Web/API local PDF import from the CLI bridge without implying separate storage behavior.
- Mention `/ready` only as setup diagnosis, not as the primary first action.

### P2
- Keep sample/demo references secondary. The first path should work with the user's own PDF.
- Avoid expanding the first-run path into Research DNA or Meeting Pack until the user has seen a saved paper.

### Full Review Coverage
- 6P storyboard context:
  - Problem: the user wants to evaluate whether Lattice can turn a paper into reviewable state.
  - Emotion: they are willing to try one command sequence, but will lose trust if the next step is hidden.
  - Action: they run Quick Start and open the local UI.
  - Struggle: README/CLI mention `deepread` and `paper_id` without a plain first-PDF bridge.
  - Attempt: route the first local PDF through `/ui/papers#import-pdf`.
  - Happy Ending: the user lands on the saved note, sees source/review actions, and understands the generated paper id.
- BMAP:
  - Motivation: high because the user wants the paper-to-evidence promise.
  - Ability: improved by one URL and one import button.
  - Prompt: README Quick Start becomes the prompt for the first useful action.
- B.I.A.S:
  - Block: "Where do I get a paper id?" is removed from the first session.
  - Interpret: the user understands Import PDF as the front door for a local paper.
  - Act: the user can click Import PDF and continue from the saved detail page.
  - Store: the first remembered loop becomes paper -> saved note -> review, not setup -> uncertainty.
- Peak-End:
  - Peak: the imported paper detail page opens and confirms the note is saved.
  - Pit: server started but no obvious next action.
  - Transition: Quick Start -> `/ui/papers#import-pdf` -> detail/workbench.
  - End: the user has a concrete `paper_id` and knows what to try next.
- Ethics:
  - The flow should not hide that deep-read quality depends on runtime inference setup.
  - Sample/demo PDFs should not be described as biomedical evidence.

## BMAP diagnosis
- Motivation: high.
- Ability: currently limited by documentation order and CLI vocabulary.
- Prompt: strongest prompt is "open `/ui/papers#import-pdf` after `lattice start`."

## B.I.A.S diagnosis
- Block: `paper_id` appears before the creation path.
- Interpret: Import PDF must be described as the first local-paper path, not a fallback detail.
- Act: one visible URL and one button are enough for the first action.
- Store: successful import should teach the product's paper-centered loop.

## Peak-End design notes
- Peak: saved note opens with PDF/review affordances.
- Pit: dependency or API-key confusion before any paper is visible.
- Transition: runtime checks are support, not the first destination.
- End: next commands/URLs are explicit and bounded.

## Concrete changes
- README: add `First Paper in 5 Minutes` after Quick Start.
- README: explain `/ui/papers#import-pdf`, generated `userpdf-*` paper id, workbench route, CLI alternative, and optional deep-read enqueue route.
- CLI reference: add `paperpipe import-pdf <path>` and clarify that it uses the same local-PDF import contract.
- CLI/runtime: add `paperpipe import-pdf <path>` by reusing the existing Paper Notes import contract.
- CLI/runtime: add `paperpipe demo-first-paper` as a zero-choice sample import that still uses the same Paper Notes import contract.
- CLI/runtime: make `paperpipe doctor` name the first-paper web and CLI import paths, and tell users to use manual import first when automatic pickup has boundary warnings.
- Paper note detail: show the generated Paper ID and a `Copy ID` affordance in the manual-import guidance banner.
- Paper note detail: add a `Queue deep read` affordance for imported notes, using the existing deep-read job API and pointing users back to review for progress.
- Paper note detail: after queueing, show the latest queued job status, run id, and job id inline so the user can confirm the action before opening review.
- Paper note detail: poll the queued job while the imported note remains open, keeping the detail page as a lightweight status confirmation surface and the workbench as the full progress surface.
- Paper note detail: add status-specific deep-read guidance so queued/running/failed states tell the first-time user whether to open review, wait, or check `/ready`.
- Doctor CLI: add `paperpipe doctor --fix` to create a starter `config.yaml` and only create missing first-run directories that are project-local or relative; external absolute paths are reported and skipped.
- E2E: click `Queue deep read` in the imported-note browser flow and assert the queued feedback plus inline queued status.
- Docs smoke: add a README first-paper smoke test that checks the documented import URL and CLI commands still match the implemented Typer command surface.
- Smoke wrapper: add `./scripts/run_first_paper_smoke.sh` so the first-paper docs, CLI import, doctor guidance, and API import checks can be run together.
- Paper Notes UX report: add a checkpoint linking this activation artifact to the existing `/papers` import surface.

## Ethics check results
- Regret: improved; users do not waste time looking for a hidden ingestion command.
- Black Mirror: low risk; the copy explicitly says the sample/demo import is an onboarding check, not biomedical evidence.
- In Real-Life: a helpful teammate would say "start here, import one PDF, then open review."

## Next PR-sized actions
1. Consider adding the same copy affordance to other paper-id-heavy surfaces if terminal/API handoff remains common.
2. Consider adding an optional frontend entry point for the same sample demo only if first-run users still need it outside the CLI.
3. Consider adding first-run failure copy for missing cloud keys or unreachable local inference after a deep-read job is queued.

## Verification
- `.venv/bin/python -m pytest -q tests/test_cli_import_pdf.py tests/test_paper_notes_api.py -k 'import_pdf'`
- `.venv/bin/python -m src.cli import-pdf --help`
- `.venv/bin/python -m src.cli demo-first-paper --help`
- `.venv/bin/python -m src.cli doctor`
- `.venv/bin/python -m src.cli doctor --fix`
- `.venv/bin/python -m pytest -q tests/test_cli_watch_commands.py -k 'doctor_fix'`
- `.venv/bin/python -m pytest -q tests/test_readme_first_paper_smoke.py`
- `./scripts/run_first_paper_smoke.sh`
- `.github/workflows/first-paper-smoke.yml`
- `git diff --check -- backend/routers/paper_notes.py src/cli.py tests/test_cli_import_pdf.py README.md docs/CLI_WORKFLOW_REFERENCE.md docs/UX_REVIEW_REPORT_first-paper-activation.md docs/UX_REVIEW_REPORT_paper-notes-viewer.md`
- `cd frontend && npm run build`
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend paper notes index can import a local PDF from the browser|mobile imported paper note keeps sticky actions aligned with the import bridge"`
