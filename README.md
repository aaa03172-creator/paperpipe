# Lattice Runtime Guide

## Quick Start

```bash
git submodule update --init --recursive
lattice start
```

Compatibility alias:

```bash
paperpipe start
```

## Runtime Security Environment Variables

| Variable | Purpose | Default |
| :--- | :--- | :--- |
| `LATTICE_API_KEY` | Enable `X-API-Key` auth for write APIs (`POST /jobs/deepread`, `POST /jobs/{id}/cancel`, `POST /feedback`, `POST /obsidian/sync`) | disabled |
| `LATTICE_MASK_LOCAL_PATHS` | Mask absolute local paths in API responses (`true/false`) | `false` |
| `LATTICE_CORS_ALLOW_ORIGINS` | Comma-separated allowed origins | `http://127.0.0.1:8000,http://localhost:8000` |
| `LATTICE_MAX_CONCURRENT_JOBS` | Max simultaneously running jobs | `1` |
| `LATTICE_MAX_QUEUED_JOBS` | Max queued jobs before `429 QUEUE_FULL` | unlimited (`0`) |

Legacy env aliases are still supported: `PAPERPIPE_API_KEY`, `PAPERPIPE_MASK_LOCAL_PATHS`, `PAPERPIPE_CORS_ALLOW_ORIGINS`, `PAPERPIPE_MAX_CONCURRENT_JOBS`, `PAPERPIPE_MAX_QUEUED_JOBS`.

## Example: Secure Local Run

```bash
export LATTICE_API_KEY="change-me"
export LATTICE_MASK_LOCAL_PATHS="true"
export LATTICE_CORS_ALLOW_ORIGINS="http://localhost:8000"
export LATTICE_MAX_CONCURRENT_JOBS="1"
export LATTICE_MAX_QUEUED_JOBS="20"

lattice start
```

## Example: Authenticated Write Request

```bash
curl -X POST "http://127.0.0.1:8000/jobs/deepread" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${LATTICE_API_KEY}" \
  -d '{"paper_id":"paper_001","persona_id":"default","clean_reindex":false,"run_verify":true}'
```

## CI Verification Gates

Run the agent smoke gate locally:

```bash
./scripts/run_agents_smoke.sh
```

This runs the targeted Ruff + pytest smoke set for the currently supported agent surface.

GitHub Actions entry point:
- `.github/workflows/agents-smoke.yml`

Run the full frontend verification gate locally:

```bash
cd frontend
npm run verify:frontend
```

This runs build + mock E2E + backend E2E in order.

Run the opt-in real-paper smoke only on a runner that has access to local PaperPipe config/storage:

```bash
cd frontend
npm run e2e:backend:real-smoke
```

Notes:
- This path uses the current `PAPERPIPE_CONFIG_PATH` / `PAPERPIPE_STORAGE_DIR` / `PAPERPIPE_DB_PATH` / `PAPERPIPE_ARTIFACTS_DIR` values.
- It does not start the seeded E2E backend harness.
- GitHub Actions entry point: `.github/workflows/frontend-real-smoke.yml` (manual, self-hosted only).
- GitHub can dispatch this workflow by filename only after the file exists on the repository default branch. The repository default branch is currently `main`, so the workflow is registered on `main` even when the actual implementation ref lives on `master` or a feature branch.
- Manual dispatch should point `--ref` at the implementation branch you want to test. Example: `gh workflow run frontend-real-smoke.yml --ref codex/<your-branch> -f config_path=config.yaml`.
- If the repository has no matching `self-hosted`, `paperpipe-real-smoke` runner online, the run will stay `queued` until a runner comes online.
- The dedicated self-hosted runner path expects `python3`, `node`, and `npm` to already exist on the runner machine. It uses runner-local Python instead of `actions/setup-python`.

Branch note:
- The repository default branch is `main`.
- The current PR workflows `.github/workflows/pr-scope-guard.yml`, `.github/workflows/agents-smoke.yml`, and `.github/workflows/frontend-e2e.yml` are scoped to `pull_request` events targeting `master`.
- Keep that split explicit until the repo's integration branch strategy is unified.

Repository plan limitations can block branch protection/ruleset APIs on private repos.
After enabling GitHub Pro/Team (or making the repo public), enforce PR required checks:

```bash
./scripts/enable_required_checks.sh master
```

This applies the following required contexts on `master`:
- `guard`
- `agents-smoke`
- `e2e-mock`
- `e2e-backend`

## Soft Gate (No Branch Protection Plan)

If branch protection is unavailable due to plan limits on a private repository, a soft gate workflow is enabled:

- Workflow: `.github/workflows/soft-gate-master.yml`
- Trigger: push to `master`
- Checks: `frontend` mock/backend E2E
- Action on failure: auto-revert the failing head commit on `master`

Notes:
- Revert commits are prefixed with `revert(soft-gate):` and are excluded from recursive auto-revert.
- This is a recovery mechanism, not a pre-merge hard block.

## Ops Monitoring

Generate downloader dashboard and threshold alerts:

```bash
python scripts/downloader_ops_dashboard.py --db storage/state.db --out storage/reports/downloader_ops_dashboard.md
```

- Exit `0`: healthy (no threshold crossed)
- Exit `2`: alert condition (wire to Slack/email/webhook)

Runbook:
- [downloader_monitoring.md](/Users/jangseongjin/paperpipe/docs/downloader_monitoring.md)
- [docs/README.md](/Users/jangseongjin/paperpipe/docs/README.md)
- [Lattice_v3_Master_Spec.md](/Users/jangseongjin/paperpipe/docs/Lattice_v3_Master_Spec.md)
