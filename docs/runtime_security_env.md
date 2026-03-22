# Lattice Runtime Security Env

Status: Active  
Date: 2026-03-09  
Owner: Runtime/security maintainers  
Canonical runbook: `docs/runtime_security_env.md`  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Recommended Local Defaults

```bash
export LATTICE_API_KEY="change-me"
export LATTICE_MASK_LOCAL_PATHS="true"
export LATTICE_CORS_ALLOW_ORIGINS="http://localhost:8000"
export LATTICE_MAX_CONCURRENT_JOBS="1"
export LATTICE_MAX_QUEUED_JOBS="20"
```

Start server:

```bash
lattice start
```

## Write API Authentication Scope

When `LATTICE_API_KEY` is set, these endpoints require `X-API-Key`:

- `POST /jobs/deepread`
- `POST /jobs/{id}/cancel`
- `POST /feedback`
- `POST /obsidian/sync`

Error contract:

```json
{
  "error_code": "UNAUTHORIZED",
  "message": "Missing or invalid X-API-Key"
}
```

## Path Masking Scope

When `LATTICE_MASK_LOCAL_PATHS=true`, API responses mask absolute local paths (for example `pdf_path`, `artifact_dir`, `log_path`, Obsidian sync file path).

## Legacy Env Aliases

- `PAPERPIPE_API_KEY`
- `PAPERPIPE_MASK_LOCAL_PATHS`
- `PAPERPIPE_CORS_ALLOW_ORIGINS`
- `PAPERPIPE_MAX_CONCURRENT_JOBS`
- `PAPERPIPE_MAX_QUEUED_JOBS`
