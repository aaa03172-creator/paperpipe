# Pending PR Queue

## Recently Completed (Runtime)
- `PR-BE-JobContract-Hardening`
- `PR-BE-Queue-Claim-Atomic`
- `PR-QA-JobRunner-FailurePaths`
- `PR-QA-JobCancel-Transitions`
- `PR-BE-Worker-CancelSync`
- `PR-BE-Queue-Legacy-Recovery`
- `PR-BE-JobRunner-StageSplit`
- `PR-BE-Evidence-Contract-v1`
- `PR-BE-Citation-Jump-MVP`
- `PR-BE-RunProfile-v1`
- `PR-BE-Discover-Queue-v1`
- `PR-BE-Stats-Trigger-v1`
- `PR-BE-Observability-Rollup`
- `PR-BE-V2-Identity-EventLog`
- `PR-BE-EventWriter-Buffered`
- `PR-BE-ArtifactPath-PaperKey`
- `PR-DOC-Blueprint-v2`
- `PR-BE-H2-Output-Contracts`
- `PR-BE-V2-EventLog-Taxonomy-ReplayTyping`
- `PR-BE-JobRunner-StageSplit-v2`
- `PR-BE-H0-LocalPdf-CanonicalIds`
- `PR-BE-H0-NonDb-Fallback-CanonicalIds`
- `PR-BE-H2-Obsidian-Resolved-Bridge`
- `PR-BE-JobRunner-Helper-Split`
- `PR-BE-H2-Obsidian-Artifacts-API`
- `PR-QA-Phase3-Stability-Gate`
- `PR-BE-H0-PaperId-Migration-Audit-Plan`
- `PR-BE-H0-ObsidianIndex-PaperId-Normalize`
- `PR-OPS-Orphan-PaperRef-Cleanup`
- `PR-BE-V2-EventLog-Followups`
- `PR-OPS-Backfill-Outputs`
- `PR-DOC-DoD-Milestone-Sync`
- `PR-BE-Exporter-Related-Papers`
- `PR-QA-Top3-Feedback-Injection-Regression`
- `PR-BE-Downloader-Ops-Metrics-API`
- `PR-CLI-Start-Entrypoint`
- `PR-QA-CLI-Start-Regression-Coverage`
- `PR-OPS-Summary-Quality-Normalize`

## PR-OPS-Teacher-Quality-Loop (In Progress)
- Title: `feat(quality): add teacher candidate/gate/goldset/eval promotion loop`
- Priority: High
- Purpose: Reduce ongoing manual/Codex dependency by making local quality iteration reproducible and measurable.
- Scope:
  - [done] SSOT runtime path resolver 추가 (`src/services/runtime_paths.py`) with env override + repo-relative fallback.
  - [done] 후보 추출 스크립트 추가 (`scripts/extract_teacher_candidates.py`) with reproducible `manifest.json`.
  - [done] 게이트 검증/라우팅 추가 (`src/quality/gates.py`, `scripts/verify_teacher_output.py`) with `reason_codes[]`.
  - [done] deterministic split 빌더 추가 (`scripts/build_goldset.py`) with paper_id hash rule and overlap guard.
  - [done] quality eval 모드 추가 (`scripts/eval/run_eval.py --mode quality`) for 4 core metrics.
  - [done] baseline/new 비교 + 승격 게이트 추가 (`scripts/eval/compare_eval.py`).
  - [done] 회귀 테스트 추가 (`tests/test_extract_teacher_candidates.py`, `tests/test_teacher_gate_verifier.py`, `tests/test_build_goldset.py`, `tests/test_eval_quality_compare.py`).

## PR-OPS-Summary-Quality-Normalize (Completed)
- Title: `chore(ops): normalize papers.summary quality and regenerate notes`
- Priority: High
- Purpose: Remove translation/prompt artifacts from DB summary text and keep note one-line summaries concise/consistent.
- Scope:
  - [done] 공용 정제 로직 추가 (`src/services/summary_normalizer.py`).
  - [done] 배치 스크립트 추가 (`scripts/normalize_summaries.py`, dry-run default + backup/apply + subset paper_id).
  - [done] 회귀 테스트 추가 (`tests/test_summary_normalizer.py`, `tests/test_normalize_summaries_script.py`).
  - [done] 운영 DB 적용: `updated=51`, backup 생성(`storage/backups/state_before_summary_normalize_20260224_125053.db`).
  - [done] 노트 재생성 실행(`run_export(overwrite=True)`), 사후 품질 리포트 저장(`storage/reports/note_regen_audit_post_summary_*.md`).
  - [done] merged via PR #73 (`933a27f`).

## PR-CLI-Start-Entrypoint (Completed)
- Title: `feat(cli): add local start command and project script entrypoints`
- Priority: Medium
- Purpose: Improve local runtime launch UX by adding a single command to preflight/start backend and open docs/UI.
- Scope:
  - [done] `src/cli.py`에 `start` 커맨드 추가 (preflight + healthcheck + browser open + graceful stop).
  - [done] `entrypoint()` 분리로 console script 진입점 안정화.
  - [done] `pyproject.toml`에 script entrypoints 추가 (`paperpipe`, `lattice`).
  - [done] 기존 CLI/API 회귀 세트 통과 (`tests/test_cli_deepread_upsert.py`, `tests/test_jobs_api_smoke.py`, `tests/test_papers_api.py`).
  - [done] merged via PR #69 (`f42d969`).

## PR-QA-CLI-Start-Regression-Coverage (Completed)
- Title: `test(cli): add start command regression coverage`
- Priority: Medium
- Purpose: Lock launcher fail-safe behavior after `start` command rollout and prevent runtime startup regressions.
- Scope:
  - [done] `tests/test_cli_start_command.py` 추가 (port in-use, healthcheck timeout, clean exit).
  - [done] CLI 회귀 세트 통과 (`tests/test_cli_start_command.py`, `tests/test_cli_smoke_db_paths.py`, `tests/test_cli_unpaywall_smoke.py`, `tests/test_cli_deepread_upsert.py`).
  - [done] merged via PR #70 (`286a2a4`).

## PR-BE-Downloader-Ops-Metrics-API (Completed)
- Title: `feat(ops): expose downloader metrics via API and shared service module`
- Priority: Medium
- Purpose: Provide runtime/API surface for downloader failure/retry metrics while keeping CLI dashboard and API on one shared metrics logic.
- Scope:
  - [done] 공용 메트릭 서비스 분리 (`src/services/downloader_ops_metrics.py`).
  - [done] API endpoint 추가: `GET /ops/downloader-metrics` (`backend/main.py`).
  - [done] Pydantic response contract 추가 (`src/schemas/ops.py` + `src/schemas/__init__.py` export).
  - [done] dashboard script가 공용 서비스 로직을 재사용하도록 정리 (`scripts/downloader_ops_dashboard.py`).
  - [done] API 회귀 테스트 추가 (`tests/test_downloader_ops_api.py`) + 관련 테스트 통과.
  - [done] merged via PR #67 (`06c9c74`).

## PR-DOC-DoD-Milestone-Sync (Completed)
- Title: `docs(spec): sync Phase DoD checkboxes with implemented runtime evidence`
- Priority: Medium
- Purpose: Align milestone checkboxes in v3 master specs with current merged behavior/tests.
- Scope:
  - [done] Phase 1 API milestones checked (`/papers`, `pdf_exists`, missing-path signaling).
  - [done] Phase 2 job/SSE/restart milestones checked.
  - [done] Phase 4/5 중 검증 근거 있는 항목만 conservative하게 체크.
  - [done] merged via PR #62 (`ab06d53`).

## PR-BE-Exporter-Related-Papers (Completed)
- Title: `feat(exporter): add related papers block using shared tags on run_export`
- Priority: Medium
- Purpose: Close Phase 5 UX gap so exported notes show immediate local navigation context.
- Scope:
  - [done] `export_paper_to_markdown`에 `## 🔗 Related Papers` 블록 생성(공유 태그 기준, 최대 5개).
  - [done] 기존 claim evidence 링크/critical review 섹션 동작 유지.
  - [done] `tests/test_exporter_obsidian_path.py` 회귀 테스트 추가(related block 렌더링 검증).
  - [done] exporter 관련 테스트 세트 통과 (`17 passed`).
  - [done] merged via PR #63 (`51df851`).

## PR-QA-Top3-Feedback-Injection-Regression (Completed)
- Title: `test(job-runner): verify Top-3 feedback injection is applied to persona context`
- Priority: Medium
- Purpose: Provide direct regression evidence for Phase 4 milestone (`Top-3` dynamic injection + log visibility).
- Scope:
  - [done] `tests/test_job_runner_persona.py`에 runtime-style regression 추가.
  - [done] ReaderAgent `persona_hint`에 `Similar feedback examples (Top-3)` 주입 확인.
  - [done] progress event 로그(`Similar feedback injected: N`)와 `bootstrap_meta`(`similar_feedback_count`, `similar_feedback_paper_ids`) 확인.
  - [done] 관련 회귀 세트 통과 (`9 passed`).
  - [done] merged via PR #65 (`c17321a`).

## PR-QA-PR-Scope-Guard (Completed)
- Title: `chore(ci): enforce docs/code PR scope split guard`
- Priority: Medium
- Purpose: Reduce mixed-scope PRs by default; allow only minimal queue-sync doc file in code PRs.
- Scope:
  - [done] `scripts/check_pr_scope.py` 추가 (base/head diff 또는 explicit files 검사).
  - [done] `src/services/pr_scope_guard.py` 분류/판정 로직 추가.
  - [done] `tests/test_pr_scope_guard.py` 회귀 테스트 추가.
  - [done] `.github/workflows/pr-scope-guard.yml` PR 자동 가드 추가.
  - [done] merged via PR #60 (`22c75c3`).

## PR-QA-Jobs-Restart-Persistence (Completed)
- Title: `test(api): verify jobs status/events survive backend reload`
- Priority: Medium
- Purpose: Add regression guard for the Phase-2 DoD item "server restart preserves job status/logs".
- Scope:
  - [done] backend module reload scenario keeps `/jobs/{id}` status/progress/stage/log_path readable.
  - [done] post-reload `/jobs/{id}/events` still emits `status/log/done` for terminal jobs.
  - [done] merged via PR #58 (`81b3fbe`).

## PR-QA-Papers-API-Contract (Completed)
- Title: `test(api): expand /papers contract regression coverage`
- Priority: Medium
- Purpose: Guard list/detail contract behavior (`pdf_exists`, missing-status signaling, updated_at ordering, list limit).
- Scope:
  - [done] list/detail response keeps `pdf_exists` semantics.
  - [done] missing local pdf path is surfaced as `pdf_status='missing'`.
  - [done] list endpoint ordering (`updated_at DESC`) and `LIMIT 50` verified by regression test.
  - [done] merged via PR #56 (`e42019f`).

## PR-QA-Jobs-SSE-Boundary (Completed)
- Title: `test(api): harden /jobs/{id}/events boundary behavior`
- Priority: Medium
- Purpose: Expand SSE runtime regression guard for cancel/not-found/reconnect terminal scenarios.
- Scope:
  - [done] cancelled job stream emits terminal `done` event.
  - [done] unknown job stream emits `error` event and exits.
  - [done] terminal job stream is replayable across reconnect calls.
  - [done] merged via PR #54 (`ac4e8c8`).

## PR-QA-Jobs-Events-Persistence (Completed)
- Title: `test(api): add jobs events stream + queue persistence regression guards`
- Priority: Medium
- Purpose: Lock API runtime guarantees for `/jobs/{id}/events` terminal delivery and DB-backed queue state persistence across queue instances.
- Scope:
  - [done] `tests/test_jobs_events_persistence.py` 추가.
  - [done] SSE endpoint response includes `status/log/done` events for completed jobs.
  - [done] `JobQueue` state persistence across new queue objects (`queued -> running`) 회귀 확인.
  - [done] merged via PR #52 (`ef56dbb`).

## PR-BE-Downloader-Router-Runtime-Attach (Completed)
- Title: `feat(downloader): runtime-safe provider chain attach + CLI compatibility`
- Priority: High
- Purpose: Make downloader router defaults fully active in runtime while preserving existing CLI smoke command compatibility.
- Scope:
  - [done] default provider chain expanded to `direct_link -> arxiv -> pmc -> unpaywall`.
  - [done] provider HTTP policy defaults now include `arxiv` and `pmc`.
  - [done] compatibility helper `_fetch_oa_link` re-exposed via `src.downloader` for `src/cli.py:test_unpaywall`.
  - [done] downloader regression tests updated/expanded (provider order + compatibility helper).
  - [done] merged via PR #50 (`f874dc7`).

## PR-BE-H0-Canonical-PaperID (Completed)
- Title: `feat(core): canonical paper_id issuance and normalization utilities`
- Priority: Medium
- Purpose: Close remaining `PR-H0` identity gap.
- Scope:
  - [done] `normalize_doi`, canonical `paper_id` issuance helper module(`src/core/ids.py`).
  - [done] Discovery/Zotero/PubMed entrypoints adopt shared helper without schema break.
  - [done] legacy/local PDF 진입점 canonical issuance 확대(`process_local_pdf_legacy`, `create_paper_from_pdf`).
  - [done] non-DB helper/legacy fallback 경로(`obsidian_index`, `llm_provider_tasks`)의 `paper_id` fallback canonical 정렬.
  - [done] 기존 CSV/노트 legacy `Paper_ID` 점검/정규화 도구 추가(`scripts/audit_obsidian_index_ids.py`, `scripts/normalize_obsidian_index_ids.py`).
  - [done] 릴리즈 체크포인트(2026-02-23)에서 운영 vault CSV 재감사 완료: `canonical_ratio=1.0`, `migratable_candidates=0`, normalize dry-run `candidates=0`으로 추가 `--apply` 불필요 결정.
- Merge Gate:
  - Existing records remain readable and untouched.
  - New records follow canonical issuance policy deterministically.

## PR-BE-V2-EventLog-Followups (Completed)
- Title: `chore(event-log): harden taxonomy/replay and ops observability`
- Priority: Medium
- Purpose: Close residual hardening after baseline event-log rollout.
- Merge Gate:
  - [done] Replay/read models for `runs -> jobs -> events` are query-ready for UI/ops (`/runs/{run_id}`, `/runs/{run_id}/timeline`).
  - [done] Error taxonomy mapping is standardized across worker/job_runner failure paths.
  - [done] `pytest -q -k "not docker_sandbox"` + phase3 integration green.

## PR-BE-H2-ReadModel-Expansion (Completed)
- Title: `feat(contracts): expand resolved/chunks read-model across API/UI paths`
- Priority: Medium
- Purpose: Reduce legacy `claimset.json` dependency and make contract-first reads the default.
- Merge Gate:
  - [done] Obsidian sync prefers `claimset.resolved.json` with legacy bridge fallback.
  - [done] Obsidian artifact API added: `GET /obsidian/artifacts?paper_id=...&run_id=...` (resolved/chunks/stats bundle).
  - [done] Remaining runtime consumers(`backend/routers/obsidian.py`, `src/exporter_claimset.py`) contract-first path adopted.
  - [done] Contract-first path regression tests expanded for API endpoints.

## PR-BE-H0-PaperId-Migration-Apply (Completed)
- Title: `chore(ids): apply paper_id canonical migration with fallback-safe mapping`
- Priority: Medium
- Purpose: Move DB `papers.paper_id` from legacy values to canonical IDs using dry-run output.
- Merge Gate:
  - [done] `scripts/apply_paper_id_migration.py` 추가 (default dry-run, `--apply` 시 backup+transaction).
  - [done] `scripts/plan_paper_id_migration.py` 기반 apply 수행(52 mappings) + backup 생성.
  - [done] apply 전후 count/샘플/SQL 검증 문서화 (`docs/PaperId_Migration_Apply_2026-02-23.md`).
  - [done] rollback 리허설(backup vs current copy 검증) 1회 실행.

## PR-OPS-Orphan-PaperRef-Cleanup (Completed)
- Title: `chore(ops): audit and cleanup orphan jobs/runs paper_id references`
- Priority: Medium
- Purpose: 운영 DB에서 `papers` 미존재 `paper_id`를 참조하는 `jobs/runs` test 흔적을 통제한다.
- Merge Gate:
  - [done] audit 스크립트 추가(`scripts/audit_orphan_paper_refs.py`).
  - [done] cleanup 스크립트 추가(`scripts/cleanup_orphan_paper_refs.py`, dry-run default).
  - [done] apply 시 backup + transaction + `orphan_cleanup_log` snapshot 기록.
  - [done] 단위테스트 추가(`tests/test_orphan_paper_refs.py`).

## PR-OPS-Backfill-Outputs (Completed)
- Title: `chore(ops): backfill markdown outputs and seed claimset recovery queue`
- Priority: High
- Purpose: 운영 backlog에서 markdown 누락을 제거하고 claimset 누락을 배치 처리 경로로 전환.
- Merge Gate:
  - [done] `scripts/qa_report.py` direct run 안정화 + claimset 출력 개선.
  - [done] `scripts/backfill_operational_outputs.py` 추가 (dry-run default).
  - [done] markdown 누락 backfill 실행 (`Missing Markdown Files: 52 -> 0`).
  - [done] claimset recovery queue seed(`+10`) 및 실패 원인 확인(`PDF not found`).
  - [done] backfill enqueue guard 강화(`pdf_ready` default required, `--allow-missing-pdf` opt-in).
  - [done] `job_runner` DB pdf_path 우선 탐색 hotfix로 canonical ID 경로 실패 해소.
  - [done] claimset backfill batch 처리(`52 -> 0`, 총 52건 처리 완료).
  - [done] queued drain 완료(`queued: 0`, `running: 0` at checkpoint).
  - [done] 운영 QA 기준 clean 상태(`Missing Markdown Files=0`, `Missing/Invalid ClaimSet=0`).

## PR-OPS-LegacyFailedJobs-Archive (Completed)
- Title: `chore(ops): archive legacy failed jobs after recovery`
- Priority: Medium
- Purpose: pre-fix 실패 이력을 `jobs` 운영 뷰에서 분리하고 보존 테이블로 아카이브.
- Merge Gate:
  - [done] `scripts/archive_legacy_failed_jobs.py` 추가 (dry-run default, backup + apply).
  - [done] 아카이브 테이블 생성(`job_failures_archive`) + 원본 row_json 보존.
  - [done] 운영 DB 적용: `failed 12 -> 0`, archive rows `12`.
  - [done] 회귀 테스트 추가(`tests/test_archive_legacy_failed_jobs.py`).
