# Removal Risk Matrix

| ID | Item | Type | Status | Risk | Evidence strength | Suggested action | Verification needed |
|---|---|---|---|---|---|---|---|
| U1 | `src/test_download.py` | Script | Confirmed unused | Low | Strong | Cleaned after audit | Search local operator refs if restoring manual probe |
| U2 | `src/db.py` embedding helpers | Functions | Confirmed unused | Medium | Strong internal, incomplete external | Cleaned after audit | External/public import check if restoring compatibility |
| U3 | `src/db_utils.py::log_workflow_step` | Function | Confirmed unused | Low | Strong | Cleaned after audit | DB/job tests passed in follow-up subset |
| U4 | `lifecycleToPaperStatus` | Frontend export | Confirmed unused | Low | Strong | Cleaned after audit | Frontend build/lint passed |
| U5 | `buildPaperNoteOpsMap`, `getPaperNoteOpsClassName` | Frontend exports | Confirmed unused | Low | Strong | Cleaned after audit | Frontend build/lint passed |
| U6 | `src/fetchers.py::fetch_arxiv` | Function | Probably unused | Medium | Good internal, incomplete external | Cleaned after audit | Watcher tests passed; external script risk remains |
| U7 | Retraction audit path | Script/service | Needs verification | Medium | Internal-only evidence | Decide active operator status | Cron/automation/runbook check |
| U8 | `ChartValueKind`, `PaperSynthesisResponse` TS types | Types | Probably unused | Low/Medium | Strong internal, contract risk | Cleaned after audit | Frontend build/lint passed |
| U9 | `src/providers/*` | Compatibility package | Do not remove | High | Strong internal, incomplete external | Deprecate first | External/package-user search |
| U10 | root `inspect_*.py` scripts | Scripts | Probably unused | Low | Strong | Cleaned after audit | Confirm `effgen` not supported if restoring |
| U11 | `copy_case.py` | Script | Probably unused | Low | Strong | Cleaned after audit | Confirm docx generation if restoring |
| R1 | Global feedback/review-log routers | Routes | Needs verification | Medium | Good frontend-source evidence | Document producer or add caller/tests | Runtime logs/external clients |
| R2 | Talk Pack API without UI route | Route/module | Needs verification | Medium | Strong UI route evidence | Keep as API/test-only or add UI later | Talk Pack roadmap/smoke |
| R3 | `/api/chat` useful behavior | Route behavior | Confirmed unreachable | High | Strong | Classify reserved or deprecate | API docs/tests/client review |
| R4 | Retraction audit scheduling | Job/script | Probably unreachable | Medium | Good internal evidence | Archive or schedule/document | External cron/automation |
| R5 | `fetch_arxiv` legacy path | Function | Probably unreachable | Medium | Good internal evidence | See U6 | Watcher/fetch tests |
| D1 | Note-backed paper summary synthesis | Duplicate logic | Confirmed | Medium | Strong | Frontend issue-state drift aligned after audit | Backend-owned contract/fallback tests still recommended |
| D2 | Paper/Zotero ID expansion | Duplicate logic | Confirmed | Medium/High | Strong | Partially consolidated after audit | Route-level alias tests added; broader sweep only if more surfaces change |
| D3 | Ops-summary derivation | Duplicate logic | Confirmed | Low/Medium | Strong | Golden tests added after audit | Prefer backend summary in future UI cleanup |
| D4 | Artifact bundle rollback helpers | Duplicate logic | Confirmed | Medium/High | Strong | Extract transaction helper incrementally only after reviewing per-store differences | Preservation tests added for major artifact stores reviewed |
| D5 | API rate-limit/audit responses | Duplicate logic | Confirmed | Medium | Strong | Rate-limit response and audit payload helpers extracted; keep broader middleware reshaping separate | Rate-limit response and audit payload tests strengthened |
| L1 | Paper synthesis compatibility bundle route | Legacy route | Probably obsolete | High | Strong first-party, incomplete external | Keep until runtime/external proof | Readiness script + request audit |
| L2 | Legacy trial extraction config alias | Legacy config | Confirmed obsolete | Do not remove yet | Strong | Remove after 2026-06-30 if ready | Readiness script |
| L3 | `src/providers/*` | Legacy import surface | Probably obsolete | High | Strong internal, incomplete external | Deprecate first | External import audit |
| L4 | `/api/chat` stub | Legacy/reserved route | Needs verification | High | Strong behavior evidence | Reserved-contract decision | Docs/tests/client review |
| L5 | root legacy instructions | Docs/config-ish | Probably obsolete | Medium | Strong | Archive/mark historical | Tooling search |
| L6 | manual probe scripts | Scripts | Probably obsolete | Low/Medium | Strong | Remove/archive | Maintainer confirmation |
| L7 | tracked `<MagicMock ...>` Chroma artifacts | Generated artifacts | Probably obsolete | Low/Medium | Strong | Cleaned after audit | RAG/indexer tests if restoring fixture-like artifacts |
