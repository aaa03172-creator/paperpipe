# Personal Runtime Packaging Decision (2026-03-28)

Status: Active decision note
Date: 2026-03-28
Owner: Lattice runtime maintainers
Purpose: choose the first packaging path for personal-runtime distribution without reopening product shape or wrapping the current runtime in a heavier shell too early.

Canonical parents:
- `docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md`
- `docs/reports/Personal_Runtime_MVP_Checklist_2026-03-28.md`
- `docs/reports/Installability_Audit_2026-03-27.md`

## 1. Decision

Choose this first packaging path:

- `existing Python launcher`
- `built frontend bundle served by backend`
- `packaged Python app bundle as the first installer/bundle direction`

Do not choose first:

- Tauri shell
- Electron shell
- shared hosted app packaging

## 2. Why this is the right first path

Current repo reality:

- the canonical entry is already `lattice start`
- the runtime is already a local FastAPI backend plus built frontend
- the launcher already performs preflight, healthcheck, and browser open
- runtime roots are already moving toward install-layout-aware personal app data

So the least risky packaging move is to package the current runtime honestly, not to introduce a second app architecture.

## 3. Packaging-shape choice

The first packaging shape should be:

- a packaged Python application bundle around `src.cli:entrypoint`
- with the frontend build output included as runtime assets
- with install-layout personal data roots as the default runtime assumption

In other words:

- package the launcher
- package the backend
- package the frontend bundle
- do not replace them

## 4. Why not Tauri or Electron first

### Tauri

Not first because:

- it adds Rust/toolchain and app-shell complexity before runtime normalization is finished
- it still leaves Python backend lifecycle supervision unsolved
- it improves desktop feel, but not the current primary risk areas of state roots, readiness, packaging honesty, and supportability

### Electron

Not first because:

- it adds a full app shell before the current runtime has a stable packaged path
- it is heavier than the repo needs right now
- it also does not remove the Python backend orchestration problem

## 5. What this decision does not yet choose

This note chooses the packaging shape, not the final tool.

Still open for a bounded implementation spike:

- PyInstaller-style bundle
- Briefcase-style app packaging
- another small Python-first bundling route

Decision constraint:

- the tool must preserve the current launcher-first runtime
- the tool must not force an architectural rewrite
- the tool must not make Windows-later support worse

## 6. Windows status

Current honest status:

- Windows is not currently a packaged, repo-proven distribution target
- Windows is not blocked at the core-runtime-path level
- Windows should be described as `not yet officially packaged/supported`, not `impossible`
- the current Windows-specific operator note lives in `docs/WINDOWS_PERSONAL_RUNTIME_ALPHA.md`

Why it is not impossible:

- runtime path helpers already account for Windows app-data roots
- launcher startup is Python-based rather than shell-only
- browser open uses the standard Python `webbrowser` adapter

Why it is not yet a real supported target:

- packaging path is still missing
- many maintainer verification flows still use bash scripts
- the current repo has not proven an end-to-end Windows alpha path

## 7. Practical recommendation

### macOS-first now

- package the existing Python launcher/runtime honestly
- keep install-layout personal roots on by default for distributed builds
- verify fresh install, `self-test`, and `/ui` startup

### Windows-later safely

- keep path logic centralized
- keep shell scripts out of the product contract
- add Windows-focused runtime-path and launcher tests as guardrails
- do not promise a Windows installer before a real packaged smoke pass exists

## 8. Acceptance bar for the first packaged path

The first packaged personal-runtime path is acceptable when:

- a tester can install or unpack the app without repo-specific knowledge
- `lattice self-test` or equivalent packaged entry works
- `lattice start` or equivalent packaged start opens a working `/ui`
- runtime DB, storage, logs, and cache live in user-scoped app-data roots
- missing external roots such as Obsidian or Zotero fail visibly

## 9. One-line recommendation

Package the current Python launcher-first runtime first, and postpone any heavier desktop shell until after the personal-runtime path is truly stable.

## 10. Current scaffold

The current repo scaffold for this direction is:

- build entry: `scripts/build_personal_runtime_bundle.py`
- macOS release entry: `scripts/release_macos_personal_runtime.py`
- PyInstaller spec: `packaging/pyinstaller/lattice.spec`
- current macOS outputs: `dist/lattice`, `dist/Lattice.app`
- app-bundle support directory: `dist/Lattice-support`

Verified macOS spike commands:

```bash
.venv/bin/python -m pip install ".[packaging]"
.venv/bin/python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean
PAPERPIPE_CONFIG_PATH=/absolute/path/to/config.example.yaml PAPERPIPE_INSTALL_LAYOUT=1 ./dist/lattice self-test --json
PAPERPIPE_CONFIG_PATH=/absolute/path/to/config.example.yaml PAPERPIPE_INSTALL_LAYOUT=1 ./dist/lattice start --no-open --port 8026
```

Observed result from the local macOS spike:

- the frozen bundle imports the backend entrypoint successfully
- the frozen bundle serves the built `/ui` bundle from packaged assets
- the frozen app-bundle executable path can default to `start` for Finder-style launches
- the current `.app` bundle passes local `codesign --verify --deep --strict`
- the current `.app` bundle is still rejected by `spctl --assess --type execute`, so this is not yet a Gatekeeper-ready distribution artifact
- `self-test` returns `degraded` only when external example paths such as Obsidian and Zotero remain placeholders
- `/health` returned `200`
- `/ui` returned `200`

Treat this as a macOS-first packaging spike around the current launcher-first runtime, not as proof of a finished installer experience.
