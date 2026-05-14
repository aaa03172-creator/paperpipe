# Removal Risk Matrix

| ID | Item | Type | Status | Risk | Evidence strength | Suggested action | Verification needed |
|---|---|---|---|---|---|---|---|
| U1 | `src/test_download.py` | Script | Cleaned after audit | Low | Strong | Cleaned after audit | Search local operator refs if restoring manual probe |
| U2 | `src/db.py` embedding helpers | Functions | Cleaned after audit | Medium | Strong internal, incomplete external | Cleaned after audit | External/public import check if restoring compatibility |
| U3 | `src/db_utils.py::log_workflow_step` | Function | Cleaned after audit | Low | Strong | Cleaned after audit | DB/job tests passed in follow-up subset |
| U4 | `lifecycleToPaperStatus` | Frontend export | Cleaned after audit | Low | Strong | Cleaned after audit | Frontend build/lint passed |
| U5 | `buildPaperNoteOpsMap`, `getPaperNoteOpsClassName` | Frontend exports | Cleaned after audit | Low | Strong | Cleaned after audit | Frontend build/lint passed |
| U6 | `src/fetchers.py::fetch_arxiv` | Function | Cleaned after audit | Medium | Good internal, incomplete external | Cleaned after audit | Watcher tests passed; external script risk remains |
| U7 | Retraction audit path | Script/service | Needs operator confirmation | Medium | Internal-only evidence; no repo scheduler found | Do not delete from repo-only evidence; confirm operator status before any archive/remove proposal | Cron/automation/runbook check outside repo |
| U8 | `ChartValueKind`, `PaperSynthesisResponse` TS types | Types | Cleaned after audit | Low/Medium | Strong internal, contract risk | Cleaned after audit | Frontend build/lint passed |
| U9 | `src/providers/*` | Compatibility package | Do not remove yet | High | Strong internal, incomplete external; wrapper aliases preserved | Deprecate first; do not delete directly | External/package-user search |
| U10 | root `inspect_*.py` scripts | Scripts | Cleaned after audit | Low | Strong | Cleaned after audit | Confirm `effgen` not supported if restoring |
| U11 | `copy_case.py` | Script | Cleaned after audit | Low | Strong | Cleaned after audit | Confirm docx generation if restoring |
| R1 | Global feedback/review-log routers | Routes | Do not remove | High | Strong route/runtime evidence after Phase 4 review | Keep as active runtime/admin surfaces; document producer if needed | Runtime logs/external clients only if reducing scope |
| R2 | Talk Pack API without UI route | Route/module | Do not remove yet | High | Strong backend/API test/docs evidence; no frontend route found | Keep as bounded API/export surface; handle via roadmap/API governance | Talk Pack roadmap/smoke |
| R3 | `/api/chat` useful behavior | Route behavior | Do not remove | High | Strong | Keep as stub-only compatibility surface unless formally deprecated | API docs/tests/client review |
| R4 | Retraction audit scheduling | Job/script | Needs operator confirmation | Medium | Good internal evidence | Do not delete from repo-only evidence; confirm operator status before any archive/remove proposal | External cron/automation |
| R5 | `fetch_arxiv` legacy path | Function | Cleaned after audit | Medium | Good internal evidence | See U6 | Watcher/fetch tests |
| D1 | Note-backed paper summary synthesis | Duplicate logic | Confirmed | Medium | Strong | Frontend issue-state drift aligned after audit | Backend-owned contract/fallback tests still recommended |
| D2 | Paper/Zotero ID expansion | Duplicate logic | Confirmed | Medium/High | Strong | Partially consolidated after audit | Route-level alias tests added; broader sweep only if more surfaces change |
| D3 | Ops-summary derivation | Duplicate logic | Confirmed | Low/Medium | Strong | Golden tests added after audit | Prefer backend summary in future UI cleanup |
| D4 | Artifact bundle rollback helpers | Duplicate logic | Confirmed | Medium/High | Strong | Extract transaction helper incrementally only after reviewing per-store differences | Preservation tests added for major artifact stores reviewed |
| D5 | API rate-limit/audit responses | Duplicate logic | Confirmed | Medium | Strong | Rate-limit response and audit payload helpers extracted; keep broader middleware reshaping separate | Rate-limit response and audit payload tests strengthened |
| L1 | Paper synthesis compatibility bundle route | Legacy route | Do not remove yet | High | Strong first-party, incomplete external | Keep until runtime/external proof | Readiness script + request audit |
| L2 | Legacy trial extraction config alias | Legacy config | Do not remove yet | Do not remove yet | Strong | Remove after 2026-06-30 only if readiness passes | Readiness script |
| L3 | `src/providers/*` | Legacy import surface | Do not remove yet | High | Strong internal, incomplete external; wrapper aliases preserved | Deprecate first; do not delete directly | External import audit |
| L4 | `/api/chat` stub | Legacy/reserved route | Do not remove | High | Strong behavior evidence | Keep as stub-only compatibility surface unless formally deprecated | Docs/tests/client review |
| L5 | root legacy instructions | Docs/config-ish | Probably obsolete | Medium | Strong | Archive/mark historical | Tooling search |
| L6 | manual probe scripts | Scripts | Partially cleaned after audit | Low/Medium | Strong | Confirm any remaining manual server/probe scripts with maintainers before proposing archive/removal | Maintainer confirmation |
| L7 | tracked `<MagicMock ...>` Chroma artifacts | Generated artifacts | Cleaned after audit | Low/Medium | Strong | Cleaned after audit | RAG/indexer tests if restoring fixture-like artifacts |
