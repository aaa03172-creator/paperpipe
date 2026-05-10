# Chart Pack Backend Core Staging Prep

Status: staging manifest  
Date: 2026-03-22  
Branch: `codex/agents-smoke-ci-check`

## Intent

Freeze the backend/runtime core of the chart-pack lane without pulling in the broader frontend viewer shell.

## Included scope

- `backend/main.py`
- `backend/routers/chart_packs.py`
- `src/chart_packs/`
- `src/schemas/chart_pack.py`
- `src/services/runtime_paths.py`
- `tests/test_api_key_auth.py`
- `tests/test_chart_pack_schema.py`
- `tests/test_chart_pack_service.py`
- `tests/test_chart_pack_source_loader.py`
- `tests/test_chart_pack_store.py`
- `tests/test_chart_packs_api.py`
- `tests/test_runtime_paths_chart_packs.py`
- `docs/reports/Chart_Pack_Backend_Core_Staging_Prep_2026-03-22.md`

## Explicitly excluded

- `frontend/src/App.tsx`
- `frontend/src/app/pages/ChartPackPage.tsx`
- `frontend/e2e/chart-pack.mock.spec.ts`
- `frontend/src/app/lib/api.ts`
- `frontend/src/app/lib/mock.ts`
- `frontend/src/app/lib/types.ts`
- `storage/search_eval/`
- `storage/obsidian/`
- any visual snapshots

## Closure checks

1. `python -c 'import backend.main'`
2. targeted pytest for chart-pack schema/service/store/source-loader/API/runtime-paths/auth
3. `python3 scripts/lint_docs.py`

## Commit target

`feat(chart-pack): add backend core and storage contract`
