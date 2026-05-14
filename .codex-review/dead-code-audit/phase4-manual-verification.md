# Phase 4 Manual Verification Checklist

Purpose:
Track high-risk cleanup candidates that must not be removed from repository evidence alone. These surfaces may be public, compatibility-preserving, runtime-registered, deployment-only, or externally called.

Reviewed on: 2026-05-14

## Summary

| ID | Item | Current status | Repo evidence | Removal stance |
|---|---|---|---|---|
| P4-1 | `/api/chat` | Intentionally stub-only compatibility surface | `backend/main.py:4808`, `docs/API_CHAT_CONTRACT.md`, `tests/test_chat_api_stub.py` | Do not remove |
| P4-2 | Paper Synthesis compatibility bundle route | First-party surfaces ready to retire, API deletion not confirmed | `backend/routers/paper_syntheses.py:91`, readiness script output | Do not remove yet |
| P4-3 | `/feedback` and `/artifact-feedback` | Active API/logging surfaces | `backend/routers/feedback.py:51`, `backend/routers/artifact_feedback.py:22`, `backend/main.py:6089` | Do not remove |
| P4-4 | `src/providers/*` wrappers | Compatibility import wrappers | `src/providers/*.py`, `src/downloader/providers/*` | Do not remove without deprecation |
| P4-5 | Retraction audit path | Mostly manual/offline path; low internal reachability | `src/audit_retractions.py:12`, `src/retraction.py:7` | Needs operator confirmation |
| P4-6 | Legacy `trial_extraction` alias | Active compatibility alias until 2026-06-30 | `src/config.py:163`, readiness script output | Do not remove before removal window |
| P4-7 | Talk Pack API/export surface | Mounted bounded API with tests/docs; no first-party frontend route found | `backend/routers/talk_packs.py:19`, `tests/test_talk_packs_api.py`, `docs/TALK_PACK.md` | Do not remove yet |

## P4-1 `/api/chat`

Status: Do not remove

Evidence:
- `backend/main.py:4808` registers `POST /api/chat`.
- `backend/main.py:4811` and `backend/main.py:4823` return HTTP 501 in both disabled and enabled flag states.
- `docs/API_CHAT_CONTRACT.md` explicitly marks the route as a stub-only compatibility surface.
- `tests/test_chat_api_stub.py` covers disabled/enabled stub behavior.
- `tests/test_browser_request_audit_api.py` covers browser write throttling for `/api/chat`.

Interpretation:
This is unused as a live chat runtime, but it is deliberately retained as a public compatibility and future-contract hook.

Required manual verification before deletion:
- Confirm no frontend, docs, API clients, or demos expect a 501 stub response.
- Confirm external API consumers do not use the route as a health/contract probe.
- Adopt a replacement contract or formal deprecation note first.

Suggested action:
Keep as `Do not remove`.

## P4-2 Paper Synthesis Compatibility Bundle Route

Status: Do not remove yet

Evidence:
- `backend/routers/paper_syntheses.py:91` registers the deprecated synthesis detail compatibility route.
- `backend/routers/paper_syntheses.py:37` emits compatibility/preferred-route headers.
- `backend/routers/paper_syntheses.py:47` best-effort logs compatibility route hits to request audit.
- `docs/PAPER_SYNTHESIS.md` documents the split manifest/markdown routes and compatibility route.
- `tests/test_paper_syntheses_api.py` and `tests/test_paper_synthesis_bundle_route_scripts.py` cover the compatibility behavior and readiness tooling.

Command results:

```sh
python3 scripts/check_paper_synthesis_bundle_route_usage.py --root .
```

Result:
`offender_count=0`; allowlisted surfaces only.

```sh
python3 scripts/check_paper_synthesis_bundle_route_removal_readiness.py
```

Result:
`active_surface_ready=true`, `ready_to_retire_bundle_route_from_first_party=true`, `ready_to_delete_api_bundle_route_now=false`.

Runtime audit interpretation:
Selected local `storage/state.db` showed `total_hit_count=2`, both `testserver` hits for `papersynth_missing`, classified as likely historical test noise. External callers remain unconfirmed.

Required manual verification before deletion:
- Check deployment/runtime request logs outside the local DB.
- Confirm downstream notebooks/scripts/API clients have moved to `/manifest` and `/markdown`.
- Run readiness script against the actual runtime DB before any removal PR.

Suggested action:
Keep route for now; first-party code is ready, but public/API deletion is not verified.

## P4-3 Feedback And Artifact Feedback Routes

Status: Do not remove

Evidence:
- `backend/main.py:6089` and `backend/main.py:6091` include `artifact_feedback.router` and `feedback.router`.
- `backend/routers/feedback.py:51` registers `POST /feedback`.
- `backend/routers/feedback.py:84` registers `GET /feedback`.
- `backend/routers/artifact_feedback.py:22` registers `POST /artifact-feedback`.
- `backend/routers/artifact_feedback.py:41` registers `GET /artifact-feedback`.
- `backend/services/job_runner.py:393` uses similar feedback retrieval for Deep Read prompt hints.
- `docs/Lattice_v3_Master_Spec.md` lists `/feedback` as part of the current runtime/API surface.
- `docs/runtime_security_env.md` documents feedback sanitization and protected-route behavior.

Interpretation:
These are not dead routes. They are active feedback/logging and review surfaces.

Required manual verification before deletion:
None currently; they should not be deletion candidates. If reducing scope later, split product route cleanup from feedback-index/runtime behavior cleanup.

Suggested action:
Reclassify from high-risk unused-looking candidate to `Do not remove`.

## P4-4 `src/providers/*`

Status: Do not remove without deprecation

Evidence:
- `src/providers/base.py`, `src/providers/arxiv.py`, `src/providers/direct.py`, `src/providers/pmc.py`, and `src/providers/unpaywall.py` are wrappers over `src/downloader/providers/*`.
- Internal production usage appears to prefer `src.downloader.providers.*`.
- Repo search found no first-party import of `src.providers.*` outside the wrapper package itself.
- `src/providers/base.py` preserves a `BaseDownloader = DownloadProvider` alias.
- `src/providers/unpaywall.py` re-exports `requests`, likely preserving older monkeypatch/import behavior.

Interpretation:
These look unused internally, but the module path is a likely legacy public import surface. Removing it could break external scripts or older notebooks.

Required manual verification before deletion:
- Search private/operator scripts outside this repo.
- Add a deprecation warning release first if this package has ever been imported externally.
- Confirm package/export expectations if PaperPipe is used as a local library.

Suggested action:
Keep as `Do not remove yet`. If cleanup is desired, use this order: add tests that pin wrapper imports, add a deprecation note/warning, search private/operator scripts, wait a deprecation window, then remove only if no external import risk remains.

## P4-5 Retraction Audit Path

Status: Needs operator confirmation

Evidence:
- `src/audit_retractions.py:12` defines a standalone audit path and `src/audit_retractions.py:75` has a direct `__main__` entry.
- `src/retraction.py:7` contains Crossref/Retraction Watch lookup logic.
- `src/config.py:32` has `check_retraction_on_ingest` defaulting to `False`.
- Repo search did not find FastAPI route, cron, package script, or first-party runtime caller for `audit_retractions`.
- `find` did not locate repo-local cron, launchd, systemd, automation, plist, or service files that schedule this script.
- `config.yaml` currently has `check_retraction_on_ingest: false`.
- `src/obsidian.py` still renders retraction details if present, so downstream presentation support is not itself dead.

Interpretation:
The audit script is probably manual/offline or legacy. The underlying `retraction.py` utility and retraction fields may still be useful if an operator workflow exists.

Required manual verification before deletion:
- Check cron/launchd/manual operator runbooks outside the repo.
- Confirm whether `check_retraction_on_ingest` is intentionally dormant or reserved.
- Confirm whether any local notebooks/scripts call `src.audit_retractions`.

Suggested action:
Keep as `Needs operator confirmation`; do not delete from repo-only evidence. If no operator workflow is found, next cleanup should archive/document `src/audit_retractions.py` separately from `src/retraction.py` and the schema/rendering support.

## P4-6 Legacy `trial_extraction` Alias

Status: Do not remove before removal window

Evidence:
- `src/config.py:163` includes `clinical_extraction`, `specialty_trial_extraction`, and legacy `trial_extraction`.
- `src/config.py:166` explicitly marks `trial_extraction` as backward-compatible.
- `src/config.py:212` warns that `llm.features.trial_extraction` is deprecated and points to the scheduled removal date.
- `docs/Lattice_v3_Master_Spec.md` records 2026-06-30 as the target first-party alias removal date.
- `tests/test_no_new_trial_extraction_alias.py` prevents spread outside the allowlist.

Command results:

```sh
python3 scripts/check_legacy_trial_extraction_alias.py --root .
```

Result:
`offender_count=0`, `removal_date=2026-06-30`.

```sh
python3 scripts/check_legacy_trial_extraction_removal_readiness.py --current-root .
```

Result:
`removal_window_open=false`, `active_surface_ready=true`, `ready_to_remove_alias_now=false`.

Generated/historical scan:
`current_repo_include_generated` found 24 preserved historical snapshot configs, which are classified as generated/historical snapshots rather than active blockers.

Required manual verification before deletion:
- Wait until the 2026-06-30 removal window opens.
- Re-run readiness script with the then-current date.
- Confirm sibling/worktree sweeps remain clean.

Suggested action:
Keep compatibility alias until the scheduled removal window.

## P4-7 Talk Pack API/Export Surface

Status: Do not remove yet

Evidence:
- `backend/main.py:6095` includes `talk_packs.router`.
- `backend/routers/talk_packs.py:19` registers a bounded `/talk-packs` API surface.
- `tests/test_talk_packs_api.py` covers list/detail/artifact/preview/render-deck behavior.
- `scripts/run_talk_pack_verify.sh` and `scripts/check_talk_pack_render_smoke.py` provide focused verification.
- `docs/TALK_PACK.md` describes Talk Pack as a bounded future/current export lane with router seams.
- No first-party frontend route was found in the current app route graph.

Interpretation:
This is not ordinary dead code. It is an API/export surface with backend coverage and docs, even though the first-party frontend route is not present.

Required manual verification before deletion:
- Confirm Talk Pack product/export roadmap.
- Confirm no API clients or operator scripts use the bounded render/export routes.
- Run the Talk Pack verification script before any route-shape change.

Suggested action:
Keep as `Do not remove yet`; treat as roadmap/API-governance work, not a dead-code deletion candidate.

## Continuation Verification On 2026-05-14

Additional read-only checks:
- `crontab -l` returned `no crontab for jangseongjin`.
- Repo-local schedule/runbook search found only `.codex/work/2026-04-24_ops_sustainability_runbook`; no repo cron, launchd, systemd, plist, or service file was found scheduling `src/audit_retractions.py`.
- Focused retraction search found `config.yaml` keeps `check_retraction_on_ingest: false`, `tests/verify_config.py` asserts it is false, and only archived docs mention `src/audit_retractions.py` structurally.
- Focused `src.providers` search found only wrapper self-references and `BaseDownloader` alias preservation.
- Focused Talk Pack search found mounted API, backend/service/store code, tests, docs, and verification scripts, but no first-party frontend route.

Paper Synthesis readiness note:
The first rerun of `python3 scripts/check_paper_synthesis_bundle_route_usage.py --root .` flagged this audit document because it quoted the bare compatibility route pattern. The audit wording was changed to avoid creating a false positive in the repository readiness gate.
After the wording change, `python3 scripts/check_paper_synthesis_bundle_route_usage.py --root .` returned `offender_count=0`, and `python3 scripts/check_paper_synthesis_bundle_route_removal_readiness.py` returned `active_surface_ready=true`, `ready_to_retire_bundle_route_from_first_party=true`, and `ready_to_delete_api_bundle_route_now=false`.

## Final Local Evidence Exhaustion On 2026-05-14

Local machine checks were extended beyond the repository without modifying code or runtime state:
- macOS LaunchAgents/LaunchDaemons were searched for PaperPipe/dead-code candidate references; no matching PaperPipe scheduler was found.
- Codex automations under `/Users/jangseongjin/.codex/automations` were inspected. They cover dependency, downloader, meeting-pack, watcher, release-slice, and AGENTS.md maintenance workflows; none schedule `src/audit_retractions.py`, call `src.providers`, or depend on Paper Synthesis compatibility route deletion.
- Local PKB references mention `/feedback` as an active workflow surface and mention `audit_retractions` only as a legacy/operating-option reference, not as an active scheduler.
- Focused searches across `/Users/jangseongjin/paperpipe-projects` found many stale worktree/current-repo copies and docs, but no independent non-repo operator script proving active `src.audit_retractions` or `src.providers` use.
- LaunchAgent/LaunchDaemon scan found no `paperpipe`, `audit_retractions`, Paper Synthesis, trial alias, Talk Pack, chat, or feedback references.

Final local interpretation:
Local evidence is exhausted. Nothing found locally upgrades `src/audit_retractions.py` from `Needs operator confirmation` to active, and nothing found locally proves external `src.providers` or Paper Synthesis compatibility-route callers. Those surfaces still cannot be deleted from local evidence alone because absence of local evidence is not proof about packaged users, deployment logs, notebooks outside the searched roots, or external API clients.

## Commands Run

```sh
rg -n "api/chat|/chat|chat" backend src frontend docs scripts tests -g '!node_modules'
rg -n "paper[-_ ]synthesis.*bundle|synthesis.*bundle|compatibility|compat" backend src frontend docs scripts tests -g '!node_modules'
rg -n "feedback|review-log|review_log|review log" backend src frontend docs scripts tests -g '!node_modules'
rg -n "src\\.providers|from src.providers|import src.providers|providers\\." backend src frontend docs scripts tests -g '!node_modules'
rg -n "retraction|audit_retractions|Retraction" backend src frontend docs scripts tests -g '!node_modules'
rg -n "trial_extraction|specialty_trial_extraction|legacy.*trial|clinical_extraction|specialty.*trial" backend src frontend docs scripts tests config* -g '!node_modules'
find . -maxdepth 3 \( -name '*cron*' -o -name '*launchd*' -o -name '*systemd*' -o -name '*automation*' -o -name '*.plist' -o -name '*.service' \) -print
python3 scripts/check_paper_synthesis_bundle_route_usage.py --root .
python3 scripts/check_paper_synthesis_bundle_route_removal_readiness.py
python3 scripts/check_legacy_trial_extraction_alias.py --root .
python3 scripts/check_legacy_trial_extraction_removal_readiness.py --current-root .
```

Initial command correction:
`python3 scripts/check_legacy_trial_extraction_removal_readiness.py --root .` failed because the script accepts `--current-root`, not `--root`. It was rerun successfully with `--current-root .`.

## Cleanup Order Recommendation

1. Reclassify `/feedback` and `/artifact-feedback` as active runtime surfaces, not dead-code candidates.
2. Keep `/api/chat` as a stub-only compatibility surface unless a formal API deprecation replaces it.
3. Keep the Paper Synthesis compatibility route until deployment/runtime logs, not only local repo scans, confirm no external callers.
4. Keep `src/providers/*` until a deprecation window or external import check closes.
5. Keep retraction audit as `Needs operator confirmation` until operator/manual usage is checked.
6. Keep `trial_extraction` alias until at least 2026-06-30 and a fresh readiness check passes.
7. Keep Talk Pack as `Do not remove yet`; it is a bounded API/export surface without a first-party frontend route, not a deletion candidate.
