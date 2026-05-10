# Lattice Runtime Guide

Lattice is a local-first, paper-centered biomedical research workspace for a single primary operator.
It helps you move from paper ingestion and deep read to evidence-linked structured state, reproducible search-design refinement, and meeting-ready downstream artifacts without hiding provenance or uncertainty.

For the current repo posture and doc reading order:
- [docs/reports/Current_Docs_Posture_2026-04-17.md](/Users/jangseongjin/paperpipe/docs/reports/Current_Docs_Posture_2026-04-17.md)
- [docs/README.md](/Users/jangseongjin/paperpipe/docs/README.md)

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
  - current boundary: this is an API/CLI operator lane today, not a main web viewer route
- Generate a meeting-ready artifact
  - produce and reopen `Meeting Pack` drafts from saved structured state
- Inspect bounded artifact viewers
  - review saved method comparisons, chart packs, image evidence, and protocol cards

## Workflow Surfaces

Implemented runtime commands:
- `lattice start`
- `paperpipe start`

Current `start` behavior:
- boots the FastAPI backend
- starts the background job worker by default
- use `--no-worker` only when you intentionally want a backend-only shell

Implemented CLI workflows:
- `paperpipe import-pdf`
- `paperpipe deepread`
- `paperpipe read`
- `paperpipe repair-stats`
- `paperpipe export`
- `paperpipe research-dna ...`

Short command reference:
- [docs/CLI_WORKFLOW_REFERENCE.md](/Users/jangseongjin/paperpipe/docs/CLI_WORKFLOW_REFERENCE.md)

Current main UI surfaces:
- `/papers`
- `/papers/:slug`
- `/workbench/:paperId`
- `/meeting-packs`
- `/method-comparisons`
- `/chart-packs`
- `/image-evidence`
- `/protocol-cards`

Research DNA note:
- `Research DNA` is implemented today as an API/CLI operator lane.
- It is intentionally not part of the current main web viewer route set.
- Use [docs/CLI_WORKFLOW_REFERENCE.md](/Users/jangseongjin/paperpipe/docs/CLI_WORKFLOW_REFERENCE.md) for the supported `paperpipe research-dna ...` workflows.

Representative API examples:
- `POST /jobs/deepread`
- `GET /papers`
- `GET /papers/{paper_id}`
- `GET /research-dna/{dna_id}` (`Research DNA` API/CLI lane)
- `GET /meeting-packs`

## Quick Start

```bash
git submodule update --init --recursive
python -m pip install -r requirements.txt
python -m pip install -e .
paperpipe self-test --json
lattice start
```

If setup looks ambiguous, run `paperpipe doctor` for a human-readable diagnosis and the same first-paper import path. On a fresh checkout with no local config yet, `paperpipe doctor --fix` creates a starter `config.yaml` plus safe project-local runtime folders, then runs the same diagnosis.

## First Paper in 5 Minutes

After `lattice start` opens the local UI, start with one PDF before exploring the broader artifact lanes:

1. Open `http://127.0.0.1:8000/ui/papers#import-pdf`.
2. Click `Import PDF` and choose a local PDF from this computer.
3. Lattice saves the PDF, creates a paper note, and opens `/papers/<note-slug>`.
4. Use `Open saved PDF` to confirm the saved source, or `Open review` to continue in `/workbench/<paper_id>`.

Imported local PDFs receive a generated `paper_id` such as `userpdf-...`. Use that id when you need an API/job identifier, for example when enqueueing `POST /jobs/deepread`.

CLI alternative:

```bash
paperpipe import-pdf path/to/paper.pdf
```

The command prints the generated `paper_id`, note slug, note path, saved PDF URL, and next routes.

Zero-choice demo import:

```bash
paperpipe demo-first-paper
```

This imports the bundled sample PDF through the same Paper Notes path. Treat it as an onboarding check, not biomedical evidence.

If the UI says automatic pickup is not ready, keep using `Import PDF` for the first run. Run `paperpipe doctor`, `paperpipe doctor --fix`, or open `/ready` when you want the machine-level setup checklist.

First-paper smoke check:

```bash
./scripts/run_first_paper_smoke.sh
```

For the current close-person alpha personal-runtime path, including `PAPERPIPE_INSTALL_LAYOUT=1`, frontend bundle build, and user-scoped config setup, use:

- [docs/PERSONAL_RUNTIME_INSTALL.md](/Users/jangseongjin/paperpipe/docs/PERSONAL_RUNTIME_INSTALL.md)

Compatibility alias:

```bash
paperpipe start
```

If `paperpipe self-test --json` reports a missing backend dependency such as `fastapi`, rerun:

```bash
python -m pip install -r requirements.txt
```

If local verification hits a broken `pytest` runner, bootstrap the bounded verification env once and use its Python directly:

```bash
python3 scripts/bootstrap_verification_env.py --run-id local_verification_bootstrap
.venv314/bin/python -m pytest -q tests/test_python_import_health.py
```

Current repo verify scripts prefer `PAPERPIPE_VERIFICATION_PYTHON`, then `.venv314`, before falling back to other healthy interpreters.

If you want user-owned runtime state outside the repo checkout, prefer the personal-runtime install guide above instead of relying on repo-relative defaults.

For the current first-product boundary and product identity:
- [docs/Product_Positioning_Principles.md](/Users/jangseongjin/paperpipe/docs/Product_Positioning_Principles.md)
- [docs/reports/Lattice_Current_Safe_Product_Summary_2026-04-13.md](/Users/jangseongjin/paperpipe/docs/reports/Lattice_Current_Safe_Product_Summary_2026-04-13.md)
- [docs/reports/First_Shippable_Product_Bar_2026-03-24.md](/Users/jangseongjin/paperpipe/docs/reports/First_Shippable_Product_Bar_2026-03-24.md)
- [docs/reports/First_Product_Baseline_QA_2026-03-25.md](/Users/jangseongjin/paperpipe/docs/reports/First_Product_Baseline_QA_2026-03-25.md)

For the current mixed-worktree posture and safest next-lane selection:
- [docs/reports/Current_Docs_Posture_2026-04-17.md](/Users/jangseongjin/paperpipe/docs/reports/Current_Docs_Posture_2026-04-17.md)
- [docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md](/Users/jangseongjin/paperpipe/docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md)
- [docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md](/Users/jangseongjin/paperpipe/docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md)

## Runtime Security

```bash
export LATTICE_API_KEY="change-me"
export LATTICE_CORS_ALLOW_ORIGINS="http://localhost:8000"
export LATTICE_MAX_CONCURRENT_JOBS="1"
export LATTICE_MAX_QUEUED_JOBS="20"

lattice start
```

Optional cloud LLM provider note:

- `llm.cloud.provider: "openai"` uses `OPENAI_API_KEY`
- `llm.cloud.provider: "anthropic"` uses `ANTHROPIC_API_KEY`
- current runtime keeps embeddings OpenAI-only, so Anthropic is for text/chat tasks today

Key runtime controls:
- `LATTICE_API_KEY`
- `LATTICE_MASK_LOCAL_PATHS`
- `LATTICE_CORS_ALLOW_ORIGINS`
- `LATTICE_MAX_CONCURRENT_JOBS`
- `LATTICE_MAX_QUEUED_JOBS`

Local secret guard:

```bash
python scripts/check_no_live_secrets.py
```

The guard scans tracked files plus local `.env` for live-looking provider keys. Keep real provider secrets in your shell, OS secret store, or deployment secret manager, and keep `.env.example` placeholder-only.

Browser/runtime boundary:
- backend-served `/ui` and the dev frontend both call same-origin `/api/*`
- if `LATTICE_API_KEY` is enabled, the server injects `X-API-Key` when bridging `/api/*` to protected backend routes
- do not put backend secrets in `VITE_*` browser env vars

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
- `.github/workflows/first-paper-smoke.yml`
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
- [docs/OPERATIONS_RUNBOOK.md](/Users/jangseongjin/paperpipe/docs/OPERATIONS_RUNBOOK.md)
- [docs/runtime_security_env.md](/Users/jangseongjin/paperpipe/docs/runtime_security_env.md)
- [docs/downloader_monitoring.md](/Users/jangseongjin/paperpipe/docs/downloader_monitoring.md)
- [docs/README.md](/Users/jangseongjin/paperpipe/docs/README.md)
- [docs/Lattice_v3_Master_Spec.md](/Users/jangseongjin/paperpipe/docs/Lattice_v3_Master_Spec.md)
