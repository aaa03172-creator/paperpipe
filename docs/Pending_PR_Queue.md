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

## PR-BE-H0-Canonical-PaperID (Next)
- Title: `feat(core): canonical paper_id issuance and normalization utilities`
- Priority: Medium
- Purpose: Close remaining `PR-H0` identity gap.
- Scope:
  - [done] `normalize_doi`, canonical `paper_id` issuance helper module(`src/core/ids.py`).
  - [done] Discovery/Zotero/PubMed entrypoints adopt shared helper without schema break.
  - [done] legacy/local PDF 진입점 canonical issuance 확대(`process_local_pdf_legacy`, `create_paper_from_pdf`).
  - [done] non-DB helper/legacy fallback 경로(`obsidian_index`, `llm_provider_tasks`)의 `paper_id` fallback canonical 정렬.
  - [done] 기존 CSV/노트 legacy `Paper_ID` 점검/정규화 도구 추가(`scripts/audit_obsidian_index_ids.py`, `scripts/normalize_obsidian_index_ids.py`).
  - [next] 운영 vault CSV/노트에 대한 `--apply` 실행 여부를 릴리즈 체크포인트에서 결정.
- Merge Gate:
  - Existing records remain readable and untouched.
  - New records follow canonical issuance policy deterministically.

## PR-BE-V2-EventLog-Followups (Deferred)
- Title: `chore(event-log): harden taxonomy/replay and ops observability`
- Priority: Medium
- Purpose: Close residual hardening after baseline event-log rollout.
- Merge Gate:
  - [done] Replay/read models for `runs -> jobs -> events` are query-ready for UI/ops (`/runs/{run_id}`, `/runs/{run_id}/timeline`).
  - [done] Error taxonomy mapping is standardized across worker/job_runner failure paths.
  - [done] `pytest -q -k "not docker_sandbox"` + phase3 integration green.

## PR-BE-H2-ReadModel-Expansion (Next)
- Title: `feat(contracts): expand resolved/chunks read-model across API/UI paths`
- Priority: Medium
- Purpose: Reduce legacy `claimset.json` dependency and make contract-first reads the default.
- Merge Gate:
  - [done] Obsidian sync prefers `claimset.resolved.json` with legacy bridge fallback.
  - [done] Obsidian artifact API added: `GET /obsidian/artifacts?paper_id=...&run_id=...` (resolved/chunks/stats bundle).
  - [done] Remaining runtime consumers(`backend/routers/obsidian.py`, `src/exporter_claimset.py`) contract-first path adopted.
  - [done] Contract-first path regression tests expanded for API endpoints.

## PR-BE-H0-PaperId-Migration-Apply (Next)
- Title: `chore(ids): apply paper_id canonical migration with fallback-safe mapping`
- Priority: Medium
- Purpose: Move DB `papers.paper_id` from legacy values to canonical IDs using dry-run output.
- Merge Gate:
  - [done] `scripts/apply_paper_id_migration.py` 추가 (default dry-run, `--apply` 시 backup+transaction).
  - [done] `scripts/plan_paper_id_migration.py` 기반 apply 수행(52 mappings) + backup 생성.
  - [done] apply 전후 count/샘플/SQL 검증 문서화 (`docs/PaperId_Migration_Apply_2026-02-23.md`).
  - [done] rollback 리허설(backup vs current copy 검증) 1회 실행.

## PR-OPS-Orphan-PaperRef-Cleanup (Next)
- Title: `chore(ops): audit and cleanup orphan jobs/runs paper_id references`
- Priority: Medium
- Purpose: 운영 DB에서 `papers` 미존재 `paper_id`를 참조하는 `jobs/runs` test 흔적을 통제한다.
- Merge Gate:
  - [done] audit 스크립트 추가(`scripts/audit_orphan_paper_refs.py`).
  - [done] cleanup 스크립트 추가(`scripts/cleanup_orphan_paper_refs.py`, dry-run default).
  - [done] apply 시 backup + transaction + `orphan_cleanup_log` snapshot 기록.
  - [done] 단위테스트 추가(`tests/test_orphan_paper_refs.py`).
