# Cleanup Plan

## Phase 1: Lowest-risk local removals

Follow-up status:
Completed after the audit.

Items to clean up:
U1 `src/test_download.py`; U3 `log_workflow_step`; U4 `lifecycleToPaperStatus`; U5 unused paper-note ops helpers; U10 `inspect_*.py`; U11 `copy_case.py`.
Reason:
Strong no-reference evidence, no framework registration, no public API route exposure.
Expected risk:
Low, except manual developer habits.
Tests/checks to run:
`rg` for removed names, `cd frontend && npm run lint && npm run build`, `python3 scripts/check_python_import_health.py` if applicable, targeted processor/job tests.
Rollback notes:
Restore individual files/functions from git if a manual workflow surfaces.

## Phase 2: Strong-evidence module/function cleanup with compatibility checks

Follow-up status:
Mostly completed after the audit: U2, U6, U8, and L7 were cleaned. Remaining risk is external/manual compatibility rather than first-party reachability.

Items to clean up:
U2 `src/db.py` embedding helpers; U6/R5 `src/fetchers.py::fetch_arxiv`; U8 unused frontend contract types; L7 tracked MagicMock Chroma artifacts if not fixtures.
Reason:
Likely unused internally, but public import/fixture concerns exist.
Expected risk:
Low/Medium to Medium.
Tests/checks to run:
`pytest -q tests/test_db_schema_compat.py tests/test_indexer.py tests/test_downloads_watcher.py tests/test_fetch_providers.py`; frontend build; `rg` for literal MagicMock paths.
Rollback notes:
Keep removals in small commits by category so any fixture/public-import fallout can be reverted independently.

## Phase 3: Duplicate logic consolidation

Follow-up status:
D1's known frontend fallback issue-state drift was aligned with backend behavior. D2 was partially consolidated into shared backend/frontend identity helpers with parameterized and route-level alias tests. D3 now has focused backend golden tests. D4 now has stronger rollback preservation tests across the artifact stores reviewed, including Project Memory and Protocol Attachment; the first shared transaction helper extraction is now applied only to simple text bundle stores. D5 now has stronger rate-limit response/audit payload contract tests plus shared rate-limit response and audit payload helpers; broader middleware reshaping remains open because it touches security/audit behavior.

Items to clean up:
D1 note-backed paper summary synthesis; D2 paper/Zotero ID expansion; D3 ops-summary derivation; D4 artifact bundle rollback helpers; D5 API rate-limit/audit helpers.
Reason:
These are not dead code, but they create correctness and maintenance risk.
Expected risk:
Medium, with D4 and D5 higher because persistence/security behavior is sensitive.
Tests/checks to run:
Parameterized backend/frontend contract tests for note fallback and ID aliases; ops-summary golden tests; artifact failure-injection tests; middleware security/audit tests; full targeted backend smoke for touched surfaces.
Rollback notes:
Consolidate one rule/family at a time. Preserve old behavior byte-for-byte before deleting duplicate copies.

## Phase 4: High-risk legacy/public/dynamic surfaces

Follow-up status:
Not cleaned. These remain manual-verification or deprecation-policy items.

Items to clean up:
U7/R4 retraction audit path; U9/L3 `src/providers/*`; R1 global feedback/review-log routers; R2 Talk Pack API-only surface; R3/L4 `/api/chat`; L1 paper synthesis compatibility bundle route; L2 legacy trial extraction alias after 2026-06-30; L5 root legacy instructions.
Reason:
These look obsolete/disconnected but may be used externally, manually, dynamically, or by public API contracts.
Expected risk:
Medium/High to High.
Tests/checks to run:
Runtime request-audit checks, external/client search, crontab/automation review, route-specific smoke tests, `python3 scripts/check_paper_synthesis_bundle_route_removal_readiness.py --db <runtime-db>`, and the legacy trial extraction removal-readiness script after the scheduled removal date.
Rollback notes:
Prefer formal deprecation PRs before deletion. Keep compatibility redirects or stubs where external caller uncertainty remains.

## Recommended sequence

1. Land completed Phase 1/2 cleanup as one bounded cleanup lane if the existing dirty tree can be separated cleanly.
2. Treat D2 as partially closed unless future alias surfaces are changed; add broader API alias sweeps only with those changes.
3. For D4, keep `d4-store-differences.md` as the extraction gate; the simple text helper is done, while managed text and mixed/binary stores should remain separate until a focused helper stays smaller than the duplicated logic.
4. Treat any deeper D1 backend-owned contract extraction and D5 as separate PR-sized refactors with tests first.
4. Treat Phase 4 as product/API governance work, not ordinary dead-code deletion.
