# Obsolete or Legacy Code Candidates

## Obsolete or legacy candidate: L1 Paper synthesis compatibility bundle route

Status: Probably obsolete
File/line:
`backend/routers/paper_syntheses.py:91`
Evidence:
Route is marked `deprecated=True`; docs and headers point callers to `/manifest` and `/markdown`; frontend uses split route helpers at `frontend/src/app/lib/api.ts:1173` and `frontend/src/app/lib/api.ts:1196`.
Original purpose, if inferable:
Compatibility response bundling manifest plus markdown for older callers.
Current usage:
No first-party frontend usage found; tests/scripts explicitly guard removal readiness.
Why it appears obsolete:
First-party clients have moved to split manifest/markdown routes.
Risk if removed:
High for unknown external API callers.
Risk if kept:
API bloat and compatibility logging forever.
Suggested action:
Keep until runtime request-audit history and external-caller review confirm deletion readiness.
Suggested verification:
`python3 scripts/check_paper_synthesis_bundle_route_removal_readiness.py --db <runtime-db>`.

## Obsolete or legacy candidate: L2 legacy trial extraction feature alias

Status: Confirmed obsolete
File/line:
Legacy trial extraction constants in `src/`, plus `src/config.py:163` and `src/config.py:216`
Evidence:
Removal date is `2026-06-30`; config warns to use `specialty_trial_extraction`.
Original purpose, if inferable:
Backward-compatible config alias during feature rename.
Current usage:
Readiness script reports active surface clean but removal window not open on 2026-05-10.
Why it appears obsolete:
New name exists and old name has scheduled removal.
Risk if removed:
Medium before 2026-06-30 because supported local configs may still rely on it.
Risk if kept:
Config ambiguity and old naming propagation after the scheduled date.
Suggested action:
Do not remove before 2026-06-30; re-run readiness after that date.
Suggested verification:
Run the legacy trial extraction removal-readiness script against the current root.

## Obsolete or legacy candidate: L3 `src/providers/*` downloader compatibility package

Status: Probably obsolete
File/line:
`src/providers/base.py:1`, `src/providers/arxiv.py:1`, `src/providers/unpaywall.py:3`
Evidence:
Files simply re-export canonical `src.downloader.providers.*`; internal code imports canonical downloader providers.
Original purpose, if inferable:
Compatibility for old import path.
Current usage:
No internal runtime caller found.
Why it appears obsolete:
Canonical provider package is `src/downloader/providers`.
Risk if removed:
High if external/local scripts import `src.providers`.
Risk if kept:
Duplicate public import surface and old patch targets.
Suggested action:
Deprecate and search external/local users before deleting.
Suggested verification:
Import audit outside repo plus `pytest -q tests/test_downloader.py tests/test_cli_unpaywall_smoke.py`.

## Obsolete or legacy candidate: L4 `/api/chat` stub-only reserved route

Status: Needs verification
File/line:
`backend/main.py:4804`
Evidence:
Both enabled and disabled branches return HTTP 501.
Original purpose, if inferable:
Reserved future chat/memory/RAG contract.
Current usage:
Route exists; no implemented chat behavior.
Why it appears obsolete:
If no longer reserved, it is dead product surface.
Risk if removed:
High if docs/tests/future clients depend on a stable stub.
Risk if kept:
User/API confusion.
Suggested action:
Explicitly classify as reserved contract or start deprecation.
Suggested verification:
Search API docs/tests and planned Chat work.

## Obsolete or legacy candidate: L5 Root-level legacy agent instructions

Status: Probably obsolete
File/line:
`instructions.md:5`, `instructions.md:10`, `ticket-execution:4`
Evidence:
Repo `AGENTS.md` names `docs/Lattice_v3_Master_Spec.md` and current PaperPipe guidelines as authority; `instructions.md` names `PaperPipe_Master_Spec.md` and a missing `antigravity/rules/master-rules`.
Original purpose, if inferable:
Older agent/operator workflow notes.
Current usage:
No active tooling references found.
Why it appears obsolete:
Conflicts with current local AGENTS guidance and missing paths.
Risk if removed:
Low / Medium; historical context may be lost.
Risk if kept:
Future agents/humans may follow stale SSOT.
Suggested action:
Archive or mark historical after confirming no tooling reads it.
Suggested verification:
`rg -n "instructions.md|ticket-execution|antigravity/rules/master-rules" .`.

## Obsolete or legacy candidate: L6 Manual probe scripts

Status: Probably obsolete
File/line:
`inspect_agent.py:2`, `inspect_config.py:2`, `src/test_download.py:2`, `scripts/test_phase3_integration.py:16`
Evidence:
Probe scripts inspect old `effgen` APIs or start live manual servers; no first-party references were found for inspect scripts; `src/test_download.py` is unregistered.
Original purpose, if inferable:
One-off development diagnostics.
Current usage:
No confirmed active usage.
Why it appears obsolete:
Outside current test/CLI harness and stale dependency names.
Risk if removed:
Low / Medium if a developer still uses them manually.
Risk if kept:
Stale dependency noise and accidental execution.
Suggested action:
Archive/remove in low-risk cleanup.
Suggested verification:
Repo-wide search and ask current maintainers.

## Obsolete or legacy candidate: L7 Tracked generated `<MagicMock ...>` Chroma artifacts

Status: Probably obsolete
File/line:
Tracked paths beginning `<MagicMock name='load_config().agents.__getitem__()' ...>/chroma.sqlite3`
Evidence:
`git ls-files` reports multiple Chroma DB binary artifacts under literal MagicMock-derived directories.
Original purpose, if inferable:
Accidental test/mock runtime output.
Current usage:
No production code should reference literal MagicMock directory names.
Why it appears obsolete:
Generated/vector-store runtime artifacts are tracked under mock object string paths.
Risk if removed:
Low / Medium; could affect tests only if accidentally encoded as fixtures.
Risk if kept:
Repository noise and misleading source scans.
Suggested action:
Treat as non-code cleanup candidate, not production dead code. Remove only after confirming tests do not use them as fixtures.
Suggested verification:
`rg -n "MagicMock name='load_config" .` and targeted RAG/indexer tests.
