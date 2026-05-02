# Personal Runtime MVP Checklist (2026-03-28)

Status: Active checklist
Date: 2026-03-28
Owner: Lattice runtime maintainers
Purpose: turn the personal-runtime deployment recommendation into a small, staged implementation checklist for close-person alpha and early beta distribution.

Canonical parents:
- `docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md`
- `docs/reports/Installability_Audit_2026-03-27.md`
- `docs/reports/Alpha_Share_QA_Audit_2026-03-27.md`
- `docs/Product_Positioning_Principles.md`

## 1. Scope of this checklist

This checklist assumes the product unit is:

- one operator
- one runtime
- one isolated config/state/artifact boundary

It is intentionally not a checklist for:

- shared multi-user SaaS
- collaboration/workspace tenancy
- broad account/project platform features

## 2. MVP target

The near-term MVP target is:

- a technically comfortable operator can install or receive Lattice as a personal runtime
- run `lattice self-test`
- run `lattice start`
- reach a working `/ui`
- keep their config, DB, storage, logs, and cache isolated from other users
- understand any missing external dependency such as Obsidian or Zotero without hidden failure

## 3. Current foundation already in place

The repo already has credible building blocks for this shape:

- launcher entry via `lattice` / `paperpipe`
- `lattice self-test` and runtime readiness checks
- `lattice start` with health-gated launch and browser open
- install-layout-aware runtime roots
- writable-root checks for config, DB, storage, logs, and cache
- external-root readiness checks for Obsidian and Zotero
- frontend build and verification commands

This means the MVP path should harden and package the current launcher-first runtime, not invent a second runtime model.

## 4. P0 checklist

These items must be true before personal-runtime distribution is treated as a repeatable product path.

### P0.1 Canonical launch path is honest

- `lattice start` remains the primary operator entry
- the command works from a non-dev context, not only from a checked-out repo with hand-managed paths
- `lattice start` opens a usable `/ui` entry, not a broken dev fallback

Repo anchors:
- `src/cli.py`
- `backend/main.py`
- `src/services/runtime_readiness.py`

### P0.2 App-owned state moves out of the checkout by default

- install-layout mode is the default distribution assumption
- app-owned roots land under a user-scoped app-data base directory
- no close-person alpha depends on users writing primary runtime state into the git checkout

Repo anchors:
- `src/services/runtime_paths.py`

### P0.3 Personal isolation boundary is explicit

- each operator gets isolated:
  - config root
  - runtime DB
  - storage/artifacts
  - logs
  - cache
  - secrets/provider config
- docs and packaging must describe this as part of the product, not as an implementation detail

Repo anchors:
- `src/services/runtime_paths.py`
- `docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md`

### P0.4 Missing external roots fail visibly, not silently

- missing `obsidian_vault` is surfaced clearly
- missing `zotero_base_dir` is surfaced clearly
- operators can distinguish `app is broken` from `external dependency is not configured`

Repo anchors:
- `src/services/runtime_readiness.py`
- `src/cli.py`

### P0.5 Minimal verification path is documented and repeatable

- operator-facing install docs use the smallest honest verification path
- minimum recommended verification is:
  - `paperpipe self-test --json`
  - `lattice start`
- maintainer release verification still uses:
  - `./scripts/run_backend_api_smoke.sh`
  - `cd frontend && npm run build`
  - `cd frontend && npm run verify:frontend`

Repo anchors:
- `README.md`
- `frontend/package.json`

## 5. P1 checklist

These items are not hard blockers for very small alpha, but they should land before wider beta.

### P1.1 Packaging path exists

- there is a documented macOS-first packaging path
- the package installs the runtime entry and required files consistently
- install/update/uninstall expectations are documented

Notes:
- this can still be a thin wrapper around the current launcher-first runtime
- this does not require a full Electron/Tauri rewrite

### P1.2 First-run setup is bounded and explicit

- the operator can answer:
  - where config lives
  - where app-owned data lives
  - what external paths must be configured
  - what is optional vs required
- first-run setup should avoid asking for platform-level concepts that the current product does not yet support

### P1.3 Recovery and backup are operator-scoped

- users can identify their personal runtime roots
- export/backup guidance covers:
  - config
  - DB
  - storage/artifacts
  - logs if needed for support
- restore expectations are documented at the personal-runtime level

### P1.4 Release verification aligns with personal runtime reality

- at least one release check should use install-layout assumptions
- release QA should confirm a fresh runtime without relying on stale localhost state
- representative paper and Meeting Pack fixtures remain available for smoke checks

## 6. P2 checklist

These items improve polish and supportability, but they can trail the first repeatable MVP.

### P2.1 Native wrapper polish

- better OS-level app naming
- icon and app bundle polish
- optional startup registration / file-open integration

### P2.2 Operator support ergonomics

- clearer error copy for missing paths and dependency failures
- one support bundle or diagnostic export path
- clearer guidance when `ui_bundle` is missing and the app falls back to dev entry

### P2.3 Managed personal instance template

- one documented template for:
  - isolated VM/container
  - isolated storage volume
  - isolated secrets/config
  - operator-specific URL/access path

This is the preferred hosted path once local install pressure becomes too high.

## 7. Recommended sequence

Implement in this order:

1. lock the personal-runtime deployment unit in docs and release language
2. make install-layout the default assumption for distributed builds
3. add or tighten operator-facing install/start/self-test documentation
4. create one macOS-first packaging path around the existing launcher
5. add one release checklist lane that verifies the packaged personal runtime
6. only after that, create a single-tenant hosted template for managed beta

## 8. Concrete next PR-sized actions

### PR 1. Personal-runtime doc alignment

- keep `docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md`
- fix stale installability wording where current repo state has moved
- add this checklist as the concrete follow-up artifact

### PR 2. Operator install/start guide

- add a concise install/start runbook for personal runtime distribution
- make install-layout and external-root expectations explicit
- point to `lattice self-test` as the first support/debug step

### PR 3. Packaged alpha path

- choose one macOS-first packaging route
- wire it to the existing launcher
- verify fresh install, first launch, self-test, and `/ui` startup

## 9. One-line acceptance test

The personal-runtime MVP is real when a close-person alpha tester can start from a packaged or installer-style distribution, keep their runtime state in their own isolated app-data roots, pass `lattice self-test`, and launch a usable `/ui` without maintainer-only repo knowledge.
