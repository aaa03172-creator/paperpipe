# Duplicate Logic Findings

## Duplicate logic: D1 Note-backed paper summary synthesis diverges between backend and frontend

Status: Confirmed
Files involved:
`backend/main.py:3784`, `backend/main.py:3841`, `frontend/src/app/lib/api.ts:531`, `frontend/src/app/lib/api.ts:886`
Logic duplicated:
Synthesize a paper detail/list item from a paper note or structured lookup.
Evidence:
Backend sets `status = "completed"` when structured state exists or note status is `INDEXED`, and sets `issues_state = "clear"` for completed notes. Frontend fallback can synthesize a completed paper detail from lookup but uses its own fixed review/issue values.
Differences between copies:
Backend completed note-backed items report clear/no critical issues. Frontend fallback can mark the same note completed while presenting review-unavailable state.
Risk of divergence:
Medium. Same note can display different operational/review state depending on whether `/papers/{id}` resolves first.
Current behavior difference, if any:
Confirmed potential divergence from code path.
Suggested consolidation approach:
Make backend own note-backed paper detail synthesis or expose one API endpoint/contract used by both list/detail fallback.
Suggested tests before consolidation:
Backend route test and frontend contract test for structured/indexed note fallback.
Cleanup risk: Medium

## Duplicate logic: D2 Paper/Zotero identity candidate expansion

Status: Confirmed
Files involved:
`backend/main.py:258`, `backend/main.py:3539`, `backend/routers/paper_notes.py:1644`, `frontend/src/app/lib/api.ts:476`, `frontend/src/app/lib/paperNoteOps.ts:4`
Logic duplicated:
Generate equivalent IDs for plain, colon-prefixed, `zotero:`-prefixed, and stripped paper IDs.
Evidence:
Backend candidate helpers add/strip different variants than frontend helpers. Frontend `buildPaperIdCandidates` only strips `zotero:`; `paperNoteToPaperIdCandidates` has an extra `zotero` without colon case.
Differences between copies:
Candidate set and ordering differ by API path.
Risk of divergence:
High for data integrity and artifact/run matching because candidate identity selects evidence/artifact state.
Current behavior difference, if any:
Potential misses in frontend fallback paths compared with backend lookup paths.
Suggested consolidation approach:
Centralize ID expansion server-side and return aliases/canonical IDs in API payloads, or generate frontend helper from a schema-backed rule.
Suggested tests before consolidation:
Parameterized tests for plain id, `zotero:ID`, `zoteroID`, and colon-containing IDs across `/papers`, `/paper-notes/resolve-by-paper-id`, ops summary, and frontend helpers.
Cleanup risk: Medium

## Duplicate logic: D3 Ops-summary state/action rules in Python and TypeScript

Status: Confirmed
Files involved:
`src/services/paper_ops_summary.py:88`, `frontend/src/app/lib/paperNoteOps.ts:92`, `frontend/src/app/pages/AnalysisWorkbench.tsx:571`
Logic duplicated:
Derive Paper Note ops summary state/action from claimset/stats artifact presence.
Evidence:
Backend maps `has_claimset`, `has_stats_report`, and `stats_check_count` into `healthy`, `repair_stats`, or `open_workbench`; frontend repeats equivalent derivation for workbench fallback.
Differences between copies:
No semantic drift found yet, but copy text and rule boundaries can diverge.
Risk of divergence:
Medium. This is user-facing next-action logic.
Current behavior difference, if any:
None confirmed.
Suggested consolidation approach:
Prefer backend-supplied `ops_summary` everywhere; if client derivation must remain, add golden cross-contract tests.
Suggested tests before consolidation:
All combinations of claimset/stats/check-count presence.
Cleanup risk: Low / Medium

## Duplicate logic: D4 Artifact bundle atomic write/rollback helpers

Status: Confirmed
Files involved:
`src/meeting_packs/store.py:71`, `src/method_comparisons/store.py:73`, `src/paper_syntheses/store.py:56`, `src/chart_packs/store.py:177`, `src/protocol_cards/store.py:102`, `src/image_evidence/store.py:158`, `src/talk_packs/store.py:116`
Logic duplicated:
Persist artifact bundles atomically, track previous files, roll back on failure, remove stale managed files, and clean empty dirs.
Evidence:
Multiple stores define similar `_atomic_write_text`, `_optional_text/_bytes`, `_restore_optional_*`, `_remove_empty_dir(s)`, and save-bundle transaction blocks.
Differences between copies:
Some stores track only JSON/markdown; others handle stale managed members and bytes. Error messages and cleanup semantics vary.
Risk of divergence:
High. Partial write/rollback defects fixed in one store can remain in another.
Current behavior difference, if any:
Confirmed structural variation; no current failure reproduced.
Suggested consolidation approach:
Extract a small internal artifact transaction helper with explicit text/bytes operations and managed-path cleanup. Migrate one feature family at a time. See `d4-store-differences.md` for the current per-store risk split.
Suggested tests before consolidation:
Failure-injection tests for rollback, stale cleanup, binary/text restoration, and unrelated-file preservation.
Cleanup risk: Medium / High

## Duplicate logic: D5 API rate-limit/audit response construction

Status: Confirmed
Files involved:
`backend/main.py:1159`, `backend/main.py:1203`, `backend/main.py:1248`, `backend/main.py:1291`, `backend/main.py:1395`, `backend/main.py:1410`, `backend/main.py:1438`
Logic duplicated:
Rate-limit decisions, request audit payloads, retry headers, and protected/browser API response construction.
Evidence:
Browser read/write and protected read/write blocks repeat limiter lookup, audit payload shape, `Retry-After`, and response bodies; success audit logging is repeated too.
Differences between copies:
Scope/source/error code differences are legitimate; mechanics are duplicated.
Risk of divergence:
Medium / High because this is security-sensitive middleware.
Current behavior difference, if any:
No incorrect behavior confirmed.
Suggested consolidation approach:
Extract narrow helpers for rate-limit response and browser/protected audit logging with explicit per-scope config.
Suggested tests before consolidation:
API-key/beta/browser audit tests asserting status, retry headers, error codes, and audit payload per scope.
Cleanup risk: Medium
