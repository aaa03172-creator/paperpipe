# Lattice Runtime Guide

## Quick Start

```bash
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

## Ops Monitoring

Generate downloader dashboard and threshold alerts:

```bash
python scripts/downloader_ops_dashboard.py --db storage/state.db --out storage/reports/downloader_ops_dashboard.md
```

- Exit `0`: healthy (no threshold crossed)
- Exit `2`: alert condition (wire to Slack/email/webhook)

Runbook:
- [downloader_monitoring.md](/Users/jangseongjin/paperpipe/docs/downloader_monitoring.md)
- [Lattice_v3_UIUX_MASTER.md](/Users/jangseongjin/paperpipe/docs/Lattice_v3_UIUX_MASTER.md)
