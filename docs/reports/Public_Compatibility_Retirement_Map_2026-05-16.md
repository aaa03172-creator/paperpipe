# Public Compatibility Retirement Map

Date: 2026-05-16

Purpose: summarize the remaining unused-looking PaperPipe surfaces that should not be deleted from repository reachability evidence alone. This is a review/gate artifact, not a canonical runtime spec or deletion authorization.

## Current Stance

| Surface | Layer | Stance | Retirement gate | Verification command |
|---|---|---|---|---|
| `POST /api/chat` | Public API compatibility stub | Keep | Formal replacement/deprecation contract, plus client/demo search showing no one depends on the 501 stub response | `.venv314/bin/python -m pytest -q tests/test_chat_api_stub.py tests/test_browser_request_audit_api.py` |
| Paper Synthesis compatibility bundle route | Public API compatibility route | Keep | Runtime/deployment request evidence shows no external callers, and first-party readiness remains clean | `paperpipe paper-synthesis-compat-usage --json`; `python3 scripts/check_paper_synthesis_bundle_route_removal_readiness.py --db <runtime-db>` |
| `src.providers.*` wrappers | Library import compatibility | Keep with deprecation warning | External/private import sweep is clean after a deprecation window | `.venv314/bin/python -m pytest -q tests/test_provider_compat_imports.py tests/test_downloader.py` |
| Retraction audit path | Explicit ops-only command | Keep | Operator confirms no runbook, notebook, schedule, or manual workflow needs it; remove wrapper separately from `src/retraction.py` | `paperpipe audit-retractions --limit 1 --json`; `.venv314/bin/python -m pytest -q tests/test_retraction_audit_service.py` |
| `/feedback` and `/artifact-feedback` | Active API/logging surfaces | Not a deletion candidate | Only revisit through product/API governance, not dead-code cleanup | Route-specific backend tests before any future route-shape change |
| Legacy `trial_extraction` alias | Config compatibility alias | Keep until at least 2026-06-30 | Removal window is open and readiness script passes on the then-current repo | `python3 scripts/check_legacy_trial_extraction_removal_readiness.py --current-root .` |
| Talk Pack API/export surface | Bounded API/export plus CLI | Keep | Product/export roadmap explicitly retires it, and API/operator script usage is clear | `.venv314/bin/python -m pytest -q tests/test_talk_packs_api.py tests/test_talk_pack_cli.py` |

## Operating Rule

Treat these as compatibility or governance surfaces, not ordinary dead code. A clean `rg` result inside the repo is useful evidence, but it is not enough to delete public routes, legacy import paths, manual ops commands, or dated compatibility aliases.

Smallest safe next step for any future removal: open a focused PR for one surface, run the listed verification, attach the external/operator evidence, and keep rollback straightforward.
