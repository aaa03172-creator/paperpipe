# Installability Audit (2026-03-27)

Status: Active audit report
Date: 2026-03-27
Owner: Lattice runtime maintainers
Purpose: assess the current macOS-first installability path for the existing launcher-first Lattice runtime and define the minimum work needed to make it behave more like an installable local app without reopening broader platform assumptions.

Update:
- 2026-03-27 follow-up patch implemented the first installability slice:
  - `/ui` now prefers the built frontend bundle and serves built asset paths
  - `sample.pdf` and `/assets/*` are now reachable through the backend-served UI path
  - log path handling now has a centralized `logs_root()` helper
- 2026-03-27 second follow-up patch implemented the next path-normalization slice:
  - cache-like roots now have centralized helpers
  - agent defaults no longer hardcode `storage/rag`, `storage/feedback_index`, or `storage/ocr_cache`
  - config defaults for agent trace/logging now follow runtime path helpers
- 2026-03-27 third follow-up patch implemented a first runtime readiness surface:
  - `/health/ready` now exposes a narrow installability-oriented readiness report
  - `lattice self-test` now exposes the same checks through the launcher
- 2026-03-28 fourth follow-up patch implemented the config-root policy slice:
  - `config_root()` now exists in the runtime-path layer
  - `PAPERPIPE_CONFIG_DIR` is now a first-class override
  - installed-mode config layout can be opted into without breaking repo-relative dev defaults
  - `lattice self-test` now reports `config_root` writability separately from `config_file` load
- 2026-03-28 fifth follow-up patch started the first shell-to-Python replacement slice:
  - real-smoke backend launch now has a Python entry at `scripts/run_backend_for_real_smoke.py`
  - `frontend/playwright.backend.real.config.ts` now launches that Python entry directly instead of the bash wrapper
  - targeted tests and the real Playwright smoke route both passed on the new entry
- 2026-03-28 sixth follow-up patch implemented the first app-data root policy slice:
  - `storage_root()`, `state_db_path()`, `logs_root()`, and `cache_root()` now follow install-layout defaults when `PAPERPIPE_INSTALL_LAYOUT=1`
  - install-layout self-test now shows runtime DB, storage, logs, and cache under a user-scoped app-data root
  - repo-relative dev defaults and explicit env overrides remain intact
- 2026-03-28 seventh follow-up patch implemented the first source/workspace-root normalization slice:
  - install-layout now normalizes app-owned legacy path literals in config
  - `export_dir`, `watch_folder`, `library_dir`, and `pdf_storage_dir` now move under install-layout app-owned roots without touching explicit custom paths
  - external/user-managed roots such as `zotero_base_dir`, `obsidian_vault`, `downloads_watch_dir`, and explicit `upload_dir` remain unchanged
- 2026-03-28 eighth follow-up patch implemented external-root readiness diagnostics:
  - `/health/ready` and `lattice self-test` now report `obsidian_vault` and `zotero_base_dir` as configured external dependencies
  - missing external roots degrade readiness with `warn` instead of silently hiding the problem
  - `lattice doctor` now shows found/missing status for both paths

## 1. Executive summary

Current Lattice is not yet an installable local app in the end-user sense.
It is a developer-launchable local runtime with a credible single launcher, a real FastAPI backend, a real bounded UI, and partially centralized runtime paths.

The good news is that the repo does **not** need a desktop-shell rewrite to move toward installability.
The most realistic path is:

1. keep `lattice start` as the product entry
2. normalize runtime paths, config, logs, and health/self-test around it
3. fix the backend-served UI entry so `lattice start` actually opens a usable built UI
4. only then add a thin native wrapper for macOS

The most important installability blocker **was** straightforward:

- `lattice start` launched the backend and pointed users at `/ui`
- `/ui` fell back to [`frontend/index.html`](/Users/jangseongjin/paperpipe/frontend/index.html)
- that file referenced `/src/main.tsx`
- the backend did not serve `/src/main.tsx`

That first blocker is now closed.
Today the remaining installability gap is less about launcher honesty and more about path policy, logs, config/data separation, and packaging readiness.

## 2. What exists today in the repo

### Runtime and entry points

- Main launcher: [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py)
- Installed command aliases exist in this environment: `lattice`, `paperpipe`
- Backend runtime: [`backend/main.py`](/Users/jangseongjin/paperpipe/backend/main.py)
- Frontend runtime/build scripts: [`frontend/package.json`](/Users/jangseongjin/paperpipe/frontend/package.json)

### What the launcher already does

The `start` command in [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py):
- loads config
- bootstraps the DB
- checks port availability
- launches `uvicorn backend.main:app`
- waits for [`/health`](/Users/jangseongjin/paperpipe/backend/main.py#L689)
- opens `/ui` unless `--no-open`
- shuts down cleanly on `Ctrl+C`

This is already a credible thin launcher. That matters because installability work can start from launcher hardening instead of inventing a second runtime entry.

### Current UI serving shape

Backend UI route:
- [`backend/main.py`](/Users/jangseongjin/paperpipe/backend/main.py#L955)

Current behavior:
- if `frontend/ui-shell.html` exists, serve it
- else serve [`frontend/index.html`](/Users/jangseongjin/paperpipe/frontend/index.html)

Current state after the follow-up patch:
- `frontend/ui-shell.html` still does not exist
- `/ui` now prefers [`frontend/dist/index.html`](/Users/jangseongjin/paperpipe/frontend/dist/index.html)
- built assets are served from `/assets`
- `sample.pdf` is reachable through the backend-served UI path

So the single-entry UI path is now materially more installable than the rest of the runtime.

### Runtime path and storage policy

Partially centralized runtime roots already exist:
- [`src/services/runtime_paths.py`](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py)

Current roots include:
- `PAPERPIPE_HOME`
- `PAPERPIPE_STORAGE_DIR`
- `PAPERPIPE_DB_PATH`
- `PAPERPIPE_CONFIG_PATH`
- `PAPERPIPE_CONFIG_DIR`
- artifact family roots such as meeting packs / chart packs / protocol cards

Current defaults still lean repo-relative:
- storage root defaults to [`storage/`](/Users/jangseongjin/paperpipe/storage)
- DB defaults to [`storage/state.db`](/Users/jangseongjin/paperpipe/storage/state.db)
- logs default to [`logs/`](/Users/jangseongjin/paperpipe/logs)
- config defaults to [`config.yaml`](/Users/jangseongjin/paperpipe/config.yaml)
- `config_root()` defaults to [`config/`](/Users/jangseongjin/paperpipe/config) in dev mode, while `config_file_path()` still defaults to [`config.yaml`](/Users/jangseongjin/paperpipe/config.yaml)

### Config

Current config loader:
- [`src/config.py`](/Users/jangseongjin/paperpipe/src/config.py)

Current config still assumes:
- `zotero_base_dir`
- `obsidian_vault`
- `downloads_watch_dir`
- app-owned workspace defaults still appear as legacy literals in `config.yaml`

Config path policy is now narrower and more installability-aware:
- `PAPERPIPE_CONFIG_DIR` can force a config directory root
- `PAPERPIPE_HOME` prefers `<home>/config/config.yaml` and still falls back to `<home>/config.yaml`
- `PAPERPIPE_INSTALL_LAYOUT=1` can opt into a platform-style user config root
- install-layout also normalizes app-owned legacy literals for:
  - `export_dir`
  - `watch_folder`
  - `library_dir`
  - `pdf_storage_dir`

That is workable for development and better for installability. The main remaining policy gap is now external/user-managed roots like Zotero and Obsidian rather than app-owned defaults.

### Logs and diagnostics

Current log roots are now partially normalized:
- [`src/services/runtime_paths.py`](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py) defines `logs_root()`
- [`src/logger.py`](/Users/jangseongjin/paperpipe/src/logger.py) now uses that helper
- [`src/jobs/worker.py`](/Users/jangseongjin/paperpipe/src/jobs/worker.py) now uses that helper
- agent trace logging now also follows runtime path helpers through [`src/config.py`](/Users/jangseongjin/paperpipe/src/config.py)
- some config and other runtime-adjacent paths still remain repo-relative

Current cache/data-like roots are now partially normalized:
- [`src/services/runtime_paths.py`](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py) defines:
  - `cache_root()`
  - `rag_root()`
  - `feedback_index_root()`
  - `ocr_cache_root()`
- [`src/config.py`](/Users/jangseongjin/paperpipe/src/config.py) now uses runtime-path defaults for:
  - agent trace file
  - RAG index path
  - feedback index path
- [`src/agents/indexer_agent.py`](/Users/jangseongjin/paperpipe/src/agents/indexer_agent.py) no longer hardcodes `storage/rag`
- [`src/agents/feedback_retriever.py`](/Users/jangseongjin/paperpipe/src/agents/feedback_retriever.py) no longer hardcodes `storage/feedback_index`
- [`src/agents/ingest_agent.py`](/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py) no longer hardcodes `storage/ocr_cache`

Current health/diagnostics anchors:
- `/health` in [`backend/main.py`](/Users/jangseongjin/paperpipe/backend/main.py#L689)
- `doctor` command in [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py#L112)
- `/health/ready` in [`backend/main.py`](/Users/jangseongjin/paperpipe/backend/main.py#L698)
- `self-test` command in [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py#L208)
- `self-test` now surfaces `config_root` writability in addition to `config_file` readability
- readiness now also surfaces configured external dependencies:
  - `obsidian_vault`
  - `zotero_base_dir`

### Shell dependence

There are many shell-based helpers, including:
- [`scripts/run_backend_api_smoke.sh`](/Users/jangseongjin/paperpipe/scripts/run_backend_api_smoke.sh)
- [`scripts/run_meeting_pack_verify.sh`](/Users/jangseongjin/paperpipe/scripts/run_meeting_pack_verify.sh)
- [`frontend/scripts/run_backend_for_real_smoke.sh`](/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_real_smoke.sh)
- [`frontend/scripts/run_backend_for_e2e.sh`](/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_e2e.sh)

These are fine for developer verification, but they are not the right long-term contract for an installed product.

## 3. Why current setup is / is not installable

### Why it is partly installability-ready

- There is already a single launcher entry in [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py)
- Backend startup is real and health-gated
- Shutdown works cleanly
- Runtime paths are partially centralized
- SQLite DB already uses WAL in [`src/db_utils.py`](/Users/jangseongjin/paperpipe/src/db_utils.py)
- The backend serves a unified API and bounded UI slice

### Why it is not installable yet

- The built `/ui` entry is now usable, but installability still depends on whether a built frontend bundle is actually present at runtime
- Installed mode can now move runtime DB, storage, logs, and cache out of repo-relative defaults
- Config still assumes developer-managed local filesystem setup
- There is still no complete installed-mode policy for explicit external roots such as Zotero and Obsidian vault locations
- There is no packaging/install/update path in the repo today
- There is no OS adapter layer yet for browser-open, startup registration, file-open, or notifications
- Shell scripts still carry meaningful runtime-adjacent verification duties

### Installability judgment by category

- `app entry`: already acceptable
- `local service lifecycle`: needs cleanup
- `config management`: needs cleanup
- `data directory policy`: needs cleanup
- `logs / diagnostics`: needs cleanup
- `startup / shutdown`: already acceptable
- `recovery / resilience`: needs cleanup
- `cache / temp management`: needs cleanup
- `healthcheck / self-diagnosis`: already acceptable
- `packaging readiness`: missing
- `installer readiness`: missing
- `auto-start readiness`: missing
- `macOS friendliness`: needs cleanup
- `Windows portability`: risky

### Installability judgment by narrower capability

- `single entry point`: already acceptable
- `local service startup`: already acceptable
- `graceful shutdown`: already acceptable
- `config directory policy`: needs cleanup
- `app data directory policy`: needs cleanup
- `logs and diagnostics`: needs cleanup
- `cache/temp management`: needs cleanup
- `healthcheck`: already acceptable
- `installer readiness`: missing
- `auto-start readiness`: missing
- `macOS packaging readiness`: missing
- `Windows portability`: risky

## 4. Recommended target architecture

### A. Recommended product form

Keep the current product form and strengthen it:

- local FastAPI backend service
- built React frontend served by the backend
- thin launcher as the single product entry
- app-data/config/log/cache directories separated from source checkout
- healthcheck and self-test as first-class operational surfaces
- future thin native wrapper only after runtime normalization

This keeps the current biomedical workspace and structured-state architecture intact.

### B. Process structure

Recommended process flow:

1. user launches `lattice start`
2. launcher resolves installed-mode paths
3. launcher preflights config and storage
4. launcher starts backend
5. launcher waits for `/health`
6. launcher opens the backend-served built UI entry
7. on exit, launcher terminates backend cleanly
8. on restart, runtime reuses persistent app data and logs

### C. Data structure

Recommended separation for installed mode:

- `config/`
  - runtime config, profile config, user overrides
- `data/`
  - canonical DB, Research DNA, source-derived state
- `artifacts/`
  - derived packs and bounded artifact families
- `logs/`
  - app log, uvicorn log, job logs
- `cache/`
  - OCR cache, vector cache, temp downloads, transient parser output

Current repo conceptually already separates source / canonical / derived.
The installability task is to move the roots out of repo-relative defaults and make them stable across restart/update.

### D. OS adapter strategy

Keep OS-specific behaviors out of the core runtime:

- browser open
- reveal file/folder in Finder or Explorer
- startup registration
- notifications
- future menubar / tray integration

Recommended shape:
- core runtime remains Python/FastAPI/React
- OS adapters live in a narrow launcher/wrapper layer
- path selection should be abstracted in one runtime-path service

### E. Installability operations layer

Add a clearer operations layer around the current launcher:

- single entry point: keep `lattice start`
- service orchestration: launcher owns backend start/stop
- diagnostics: expand `doctor` and add machine-readable self-test
- healthcheck: keep `/health`, add deeper readiness check
- recovery: add storage/config validation before launch
- update-safe layout: app data outside app bundle and outside repo root

## 5. Phase-by-phase implementation plan

### Phase 0: audit / no behavior change

- Goal: document current launcher/runtime/installability state
- Touch:
  - [`docs/reports/Installability_Audit_Execution_Prompt_2026-03-27.md`](/Users/jangseongjin/paperpipe/docs/reports/Installability_Audit_Execution_Prompt_2026-03-27.md)
  - this audit report
- Benefit: clear installability baseline
- Risk: none
- What not to do: no packaging work yet

### Phase 1: launcher/runtime normalization

- Goal: make `lattice start` the reliable product entry
- Touch:
  - [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py)
  - [`backend/main.py`](/Users/jangseongjin/paperpipe/backend/main.py)
- Benefit: single entry point becomes honest for end users
- Risk: accidentally breaking current dev UI assumptions
- What not to do: do not add a desktop shell yet

### Phase 2: path/config/log cleanup

- Goal: separate installed-mode app data from repo-relative dev defaults
- Touch:
  - [`src/services/runtime_paths.py`](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py)
  - [`src/config.py`](/Users/jangseongjin/paperpipe/src/config.py)
  - [`src/logger.py`](/Users/jangseongjin/paperpipe/src/logger.py)
  - [`src/jobs/worker.py`](/Users/jangseongjin/paperpipe/src/jobs/worker.py)
- Benefit: restart/update safety and Windows readiness
- Risk: path migration edge cases
- What not to do: do not silently rewrite existing user data without migration/alias rules

### Phase 3: local service lifecycle hardening

- Goal: make startup/shutdown/restart more product-like
- Touch:
  - [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py)
  - maybe a new runtime supervision helper under `src/services/`
- Benefit: fewer stale servers, clearer failure modes
- Risk: overbuilding supervision before needed
- What not to do: no daemon/service manager abstraction yet

### Phase 4: healthcheck / diagnostics / self-test

- Goal: move from simple liveness to meaningful readiness
- Touch:
  - [`backend/main.py`](/Users/jangseongjin/paperpipe/backend/main.py)
  - [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py)
  - new self-test helper under `src/services/` or `scripts/`
- Benefit: easier support and alpha distribution
- Risk: turning self-test into another giant QA framework
- What not to do: do not couple self-test to external services unnecessarily

### Phase 5: thin desktop shell or native wrapper decision

- Goal: decide whether a wrapper is now justified
- Touch:
  - packaging scaffolding only after runtime normalization
- Benefit: natural app-like launch on macOS
- Risk: introducing packaging complexity too early
- What not to do: no Tauri/Electron adoption before phases 1-4

### Phase 6: packaging / installer prep

- Goal: make macOS distribution realistic
- Touch:
  - packaging metadata
  - launcher entry
  - path defaults for installed mode
- Benefit: can share outside the dev repo
- Risk: code signing/notarization surprises
- What not to do: no full cross-platform promise yet

### Phase 7: Windows-safe cleanup

- Goal: make current architecture safe to port later
- Touch:
  - path handling
  - shell dependencies
  - OS-specific side effects
- Benefit: avoids future rewrite
- Risk: over-abstracting too soon
- What not to do: no fake Windows support claim before runtime proof exists

## 6. Minimal code changes to start now

1. Fix backend-served UI entry
- Update [`backend/main.py`](/Users/jangseongjin/paperpipe/backend/main.py) so `/ui` serves [`frontend/dist/index.html`](/Users/jangseongjin/paperpipe/frontend/dist/index.html) when present.
- Keep current `frontend/index.html` fallback only for explicit dev mode.

Status:
- implemented on 2026-03-27

2. Introduce installed-mode app directories
- Extend [`src/services/runtime_paths.py`](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py) with explicit:
  - app data root
  - config root
  - logs root
  - cache root
- Preserve current env override behavior.
- Keep repo-relative defaults only as dev fallback.

Status:
- partially implemented on 2026-03-28 for config roots and install-layout-aware config resolution

3. Move logs onto runtime paths
- Update [`src/logger.py`](/Users/jangseongjin/paperpipe/src/logger.py)
- Update [`src/jobs/worker.py`](/Users/jangseongjin/paperpipe/src/jobs/worker.py)
- Stop hardcoding `logs/...`

Status:
- partially implemented on 2026-03-27 via `logs_root()`

4. Normalize cache-like runtime roots
- Extend [`src/services/runtime_paths.py`](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py)
- Rewire agent/config defaults away from direct `storage/...` cache literals

Status:
- partially implemented on 2026-03-27 via `cache_root()`, `rag_root()`, `feedback_index_root()`, and `ocr_cache_root()`

5. Add readiness/self-test entry
- Expand `doctor` in [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py) or add a narrow `self-test` command
- Add a deeper backend readiness endpoint or CLI self-test that checks:
  - config readable
  - DB writable
  - storage roots writable
  - built UI available for installed mode

Status:
- implemented on 2026-03-27 via `/health/ready` and `lattice self-test`

6. Start replacing runtime-adjacent shell glue
- First replacement target:
  - [`frontend/scripts/run_backend_for_real_smoke.sh`](/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_real_smoke.sh)
- Move its backend launch preflight into Python so the installed product path does not depend on shell scripts

Status:
- partially implemented on 2026-03-28 via [`scripts/run_backend_for_real_smoke.py`](/Users/jangseongjin/paperpipe/scripts/run_backend_for_real_smoke.py) and direct Playwright integration

Reopen condition for the seeded E2E backend launcher:
- reopen the same Python-launcher migration for [`frontend/scripts/run_backend_for_e2e.sh`](/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_e2e.sh) only if one of these becomes true:
  - seeded `e2e:backend` or `e2e:backend:parser-worker` becomes a release-signoff gate instead of a developer-only harness
  - shell dependence becomes a real cross-machine/CI blocker
  - backend launch logic starts drifting between shell and Python paths enough to create duplicated maintenance
- when reopened, start from:
  - [`frontend/scripts/run_backend_for_e2e.sh`](/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_e2e.sh)
  - [`frontend/playwright.backend.config.ts`](/Users/jangseongjin/paperpipe/frontend/playwright.backend.config.ts)
  - [`frontend/playwright.backend.parser.config.ts`](/Users/jangseongjin/paperpipe/frontend/playwright.backend.parser.config.ts)
  - a new Python launcher under [`scripts/`](/Users/jangseongjin/paperpipe/scripts/)

## 7. Packaging recommendation

### Option comparison

#### Tauri

- Fit with current repo: medium
- Complexity: medium-high
- Pros:
  - native feel
  - low runtime overhead
  - good macOS/Windows story eventually
- Cons:
  - still needs Python backend supervision
  - adds Rust/toolchain/packaging complexity before runtime normalization is complete

#### Electron

- Fit with current repo: medium
- Complexity: medium
- Pros:
  - familiar wrapper model for local web UI
  - easier windowing and updater ecosystem
- Cons:
  - heavier runtime
  - same backend orchestration problem remains
  - more app-shell complexity than the repo needs right now

#### CLI + local web UI + thin native wrapper

- Fit with current repo: high
- Complexity: low-medium
- Pros:
  - preserves current architecture
  - starts from existing launcher
  - can become installable incrementally
  - easiest path to macOS-first without blocking Windows later
- Cons:
  - less polished initially
  - wrapper choice can be deferred but not avoided forever

### Final recommendation

Choose:

> CLI + local web UI + thin native wrapper

That is the most realistic current-repo choice.

Do **not** adopt Tauri or Electron first.
Normalize launcher/runtime/data paths first, then decide whether the thin wrapper should be:
- a small native app launcher
- a packaged Python app bundle
- or a later Tauri shell once runtime normalization is complete

## 8. macOS-first / Windows-later strategy

macOS-first now:
- make `lattice start` the honest product entry
- serve built UI from backend
- move runtime data/logs/config out of repo-relative defaults
- keep browser-open as an adapter behavior, not a core assumption
- make local restart/recovery predictable

Windows-later safely:
- keep path logic centralized
- avoid shell-first runtime flows
- avoid Finder/macOS-specific assumptions in core logic
- prefer env/config-driven locations over hardcoded repo paths
- do not let launch/startup behavior depend on `zsh`, `bash`, or macOS-only file semantics

## 9. Risks and tradeoffs

- If runtime normalization is skipped and a desktop shell is added first, the repo will gain packaging complexity without solving data durability or lifecycle clarity.
- If repo-relative paths remain the default install path, updates and user support will stay fragile.
- If `/ui` keeps serving the dev index fallback, `lattice start` will remain a misleading entry point for non-developers.
- If shell scripts remain part of the runtime-adjacent contract, Windows-safe progress will stay slower than necessary.

## 10. Concrete next actions

1. Fix `/ui` to serve built frontend output in installed/runtime mode.
2. Keep the new config-root policy stable and move on to broader app-data/source path cleanup only when needed.
3. Keep the new Python real-smoke launcher stable and only then decide whether the seeded E2E backend launcher needs the same treatment.
4. Only after that, evaluate a thin macOS wrapper.

## A. Minimum viable installability workset

This is the smallest concrete set of changes worth starting now.

### 1. Honest single-entry UI

Files:
- [`backend/main.py`](/Users/jangseongjin/paperpipe/backend/main.py)
- [`frontend/dist/index.html`](/Users/jangseongjin/paperpipe/frontend/dist/index.html)

Change:
- Make `/ui` prefer `frontend/dist/index.html`
- Keep `frontend/index.html` only as an explicit dev fallback

Why first:
- today `lattice start` points users at an entry that is not installable-quality

### 2. Installed-mode path layer

Files:
- [`src/services/runtime_paths.py`](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py)
- [`src/config.py`](/Users/jangseongjin/paperpipe/src/config.py)

Change:
- add app data root / config root / logs root / cache root helpers
- preserve env overrides
- keep repo-relative dev fallback

Why first:
- installability is impossible to stabilize while state/logs/config still default into the checkout

Status:
- materially implemented on 2026-03-28 for config-root, install-layout-aware runtime DB/storage/logs/cache defaults, and app-owned workspace defaults
- still open for explicit external source/workspace policy (`obsidian_vault`, `zotero_base_dir`) and any migration guidance around them

### 3. Log root normalization

Files:
- [`src/logger.py`](/Users/jangseongjin/paperpipe/src/logger.py)
- [`src/jobs/worker.py`](/Users/jangseongjin/paperpipe/src/jobs/worker.py)
- any direct `logs/...` writers in [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py)

Change:
- replace direct `logs/...` literals with runtime-path helpers

Why first:
- product support and recovery need stable diagnostics outside the repo root

### 4. Launcher self-test

Files:
- [`src/cli.py`](/Users/jangseongjin/paperpipe/src/cli.py)
- [`backend/main.py`](/Users/jangseongjin/paperpipe/backend/main.py)
- optional new helper under `src/services/`

Change:
- add a narrow self-test/readiness contract that checks config, DB, storage roots, and UI asset availability

Why first:
- installed apps need a supportable “what is broken?” path

### 5. First shell-to-Python replacement

Files:
- [`scripts/run_backend_for_real_smoke.py`](/Users/jangseongjin/paperpipe/scripts/run_backend_for_real_smoke.py)
- [`frontend/playwright.backend.real.config.ts`](/Users/jangseongjin/paperpipe/frontend/playwright.backend.real.config.ts)

Change:
- move backend preflight/start logic into Python
- keep the old shell script out of the active real-smoke runtime path

Why first:
- reduces shell coupling and improves future Windows portability

Status:
- implemented on 2026-03-28 for the real-smoke backend launch path

## B. Windows-safe guardrails

- Do not hardcode runtime paths under the repo root for installed mode.
- Keep all path resolution in one helper layer; do not scatter `storage/...`, `logs/...`, or `config.yaml` literals across runtime code.
- Keep shell scripts out of the product runtime contract.
- Do not put macOS-only behavior such as browser-open or future launch-agent logic inside core data/runtime services.
- Treat file open, folder reveal, startup registration, and notifications as OS adapters.
- Prefer default behavior that works without administrator rights.
- Assume user paths may include Korean characters, spaces, or synced/managed directories.
- Assume case-insensitive filesystems are common on macOS and Windows.
- Keep source data, canonical structured state, and derived artifacts separated regardless of OS.
- Preserve env overrides and migration-safe aliases when changing runtime roots.
- Do not let packaging work redefine the current paper-centered first-product boundary.

## Verification run for this audit

Directly verified in the current environment:

- `which lattice`
- `python3 -m src.cli --help`
- `python3 -m src.cli start --no-open --port 8013`
- `python3 -m src.cli start --no-open --port 8014`
- `curl http://127.0.0.1:8013/health`
- `curl http://127.0.0.1:8013/ui`
- `curl http://127.0.0.1:8013/src/main.tsx`
- `curl http://127.0.0.1:8014/ui`
- `curl http://127.0.0.1:8014/assets/index-BEYQXwhS.js`
- `curl http://127.0.0.1:8014/sample.pdf`
- `pytest -q tests/test_runtime_paths_logs.py tests/test_ui_shell_api.py tests/test_cli_start_command.py`
- `pytest -q tests/test_runtime_paths_cache.py tests/test_config_agent_path_defaults.py tests/test_runtime_paths_logs.py tests/test_config_env_override.py tests/test_runtime_paths_research_dna.py`
- `pytest -q tests/test_runtime_readiness_api.py tests/test_cli_self_test_command.py tests/test_ui_shell_api.py tests/test_cli_start_command.py`
- `pytest -q tests/test_runtime_paths_config.py tests/test_config_env_override.py tests/test_runtime_paths_research_dna.py tests/test_runtime_readiness_api.py tests/test_cli_self_test_command.py`
- `pytest -q tests/test_frontend_real_smoke_backend_launcher.py tests/test_frontend_real_smoke_preflight.py`
- `python3 -m src.cli doctor`
- `python3 -m src.cli self-test`
- `python3 -m src.cli self-test --json`
- `python3 scripts/run_backend_for_real_smoke.py --check-only`
- `cd frontend && env PAPERPIPE_REAL_SMOKE=1 PAPERPIPE_REAL_SMOKE_REQUIRE_CANDIDATES=1 node node_modules/@playwright/test/cli.js test -c playwright.backend.real.config.ts e2e/backend.spec.ts -g 'backend real-paper smoke' --reporter=line`
- graceful shutdown via `Ctrl+C`

Observed results:

- launcher startup succeeded
- health wait succeeded
- backend shutdown was clean
- `/ui` now returns the built frontend HTML
- `/assets/index-BEYQXwhS.js` returns `200`
- `/sample.pdf` returns a PDF payload
- `/src/main.tsx` still returns `404`, which is now expected because `/ui` no longer depends on that dev path
- `self-test --json` now reports both `config_file` and `config_root`
- the real-smoke Playwright path now starts backend through the Python launcher instead of the bash wrapper
