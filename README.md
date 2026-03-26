# Lattice Runtime Guide

Lattice is a local-first, paper-centered biomedical research workspace for a single primary operator.
It helps you move from paper ingestion and deep read to evidence-linked structured state, reproducible search-design refinement, and meeting-ready downstream artifacts without hiding provenance or uncertainty.

Current runtime shape:
- paper-first
- job/run/artifact-first
- human-reviewable
- additive rather than fully autonomous

This repo is not currently:
- a generic research agent
- a chatbot-first copilot
- a first-class project/workspace platform
- a broad memory-first research system

## What You Can Do Today

- Run a deep read
  - enqueue a paper, inspect run state, and review saved paper state
- Inspect saved paper state
  - use paper notes and workbench to review evidence, uncertainty, and operational status
- Refine reproducible search design
  - create, pilot, screen, refine, and lock `Research DNA`
- Generate a meeting-ready artifact
  - produce and reopen `Meeting Pack` drafts from saved structured state
- Inspect bounded artifact viewers
  - review saved method comparisons, chart packs, image evidence, and protocol cards

## Workflow Surfaces

Implemented runtime commands:
- `lattice start`
- `paperpipe start`

Implemented CLI workflows:
- `paperpipe deepread`
- `paperpipe read`
- `paperpipe repair-stats`
- `paperpipe export`
- `paperpipe research-dna ...`

Short command reference:
- [docs/CLI_WORKFLOW_REFERENCE.md](/Users/jangseongjin/paperpipe/docs/CLI_WORKFLOW_REFERENCE.md)

Current main UI/API surfaces:
- `/papers`
- `/papers/:slug`
- `/workbench/:paperId`
- `/meeting-packs`
- `/method-comparisons`
- `/chart-packs`
- `/image-evidence`
- `/protocol-cards`

## Quick Start

```bash
git submodule update --init --recursive
lattice start
```

Compatibility alias:

```bash
paperpipe start
```

For the current first-product boundary and product identity:
- [docs/Product_Positioning_Principles.md](/Users/jangseongjin/paperpipe/docs/Product_Positioning_Principles.md)
- [docs/reports/First_Shippable_Product_Bar_2026-03-24.md](/Users/jangseongjin/paperpipe/docs/reports/First_Shippable_Product_Bar_2026-03-24.md)
- [docs/reports/First_Product_Baseline_QA_2026-03-25.md](/Users/jangseongjin/paperpipe/docs/reports/First_Product_Baseline_QA_2026-03-25.md)

## Runtime Security

```bash
export LATTICE_API_KEY="change-me"
export LATTICE_MASK_LOCAL_PATHS="true"
export LATTICE_CORS_ALLOW_ORIGINS="http://localhost:8000"
export LATTICE_MAX_CONCURRENT_JOBS="1"
export LATTICE_MAX_QUEUED_JOBS="20"

lattice start
```

Key runtime controls:
- `LATTICE_API_KEY`
- `LATTICE_MASK_LOCAL_PATHS`
- `LATTICE_CORS_ALLOW_ORIGINS`
- `LATTICE_MAX_CONCURRENT_JOBS`
- `LATTICE_MAX_QUEUED_JOBS`

Legacy `PAPERPIPE_*` aliases are still supported.

Full runbook:
- [docs/runtime_security_env.md](/Users/jangseongjin/paperpipe/docs/runtime_security_env.md)

Example authenticated write:

```bash
curl -X POST "http://127.0.0.1:8000/jobs/deepread" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${LATTICE_API_KEY}" \
  -d '{"paper_id":"paper_001","persona_id":"default","clean_reindex":false,"run_verify":true}'
```

## CI Verification Gates

Use the smallest gate that matches the surface you changed.

Agent/runtime smoke:

```bash
./scripts/run_agents_smoke.sh
```

Frontend verification:

```bash
cd frontend
npm run verify:frontend
```

Opt-in real-paper smoke:

```bash
cd frontend
npm run e2e:backend:real-smoke
```

Current workflow entry points:
- `.github/workflows/agents-smoke.yml`
- `.github/workflows/frontend-e2e.yml`
- `.github/workflows/frontend-real-smoke.yml`
- `.github/workflows/soft-gate-master.yml`

Branch note:
- repository default branch is `main`
- current PR checks still target `master`
- keep that split explicit until the integration branch strategy is unified

If repository plan limits prevent branch protection/rulesets on a private repo, required checks can still be enabled later:

```bash
./scripts/enable_required_checks.sh master
```

## Soft Gate (No Branch Protection Plan)

If branch protection is unavailable, the repo can use:
- workflow: `.github/workflows/soft-gate-master.yml`
- trigger: push to `master`
- behavior: auto-revert a failing head commit after frontend checks fail

This is a recovery mechanism, not a pre-merge hard block.

## Ops Monitoring

Generate downloader dashboard and threshold alerts:

```bash
python scripts/downloader_ops_dashboard.py --db storage/state.db --out storage/reports/downloader_ops_dashboard.md
```

- Exit `0`: healthy (no threshold crossed)
- Exit `2`: alert condition (wire to Slack/email/webhook)

Runbooks:
- [docs/runtime_security_env.md](/Users/jangseongjin/paperpipe/docs/runtime_security_env.md)
- [docs/downloader_monitoring.md](/Users/jangseongjin/paperpipe/docs/downloader_monitoring.md)
- [docs/README.md](/Users/jangseongjin/paperpipe/docs/README.md)
- [docs/Lattice_v3_Master_Spec.md](/Users/jangseongjin/paperpipe/docs/Lattice_v3_Master_Spec.md)
