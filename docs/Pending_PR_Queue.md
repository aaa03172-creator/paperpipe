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

## PR-BE-H0-Canonical-PaperID (Next)
- Title: `feat(core): canonical paper_id issuance and normalization utilities`
- Priority: Medium
- Purpose: Close remaining `PR-H0` identity gap.
- Scope:
  - [done] `normalize_doi`, canonical `paper_id` issuance helper module(`src/core/ids.py`).
  - [done] Discovery/Zotero/PubMed entrypoints adopt shared helper without schema break.
  - [done] legacy/local PDF 진입점 canonical issuance 확대(`process_local_pdf_legacy`, `create_paper_from_pdf`).
  - [next] non-DB helper/legacy fallback 경로(`obsidian_index`, `llm_provider_tasks`)의 `paper_id` 사용을 운영 계약 관점에서 감사(audit) 후 정리.
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
