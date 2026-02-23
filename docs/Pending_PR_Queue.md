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

## PR-BE-H2-Output-Contracts (Next)
- Title: `feat(contracts): split chunk/claim artifacts and add bridge adapters`
- Priority: High
- Purpose: Close remaining `PR-H2` contract gap after v2 blueprint promotion.
- Scope (runtime + tests):
  - Introduce `chunks.json`, `claimset.raw.json`, `claimset.resolved.json` write path.
  - Bridge adapters for existing renderer/consumer compatibility.
  - Resolver test expansion for exact/normalized/failed matching.
- Merge Gate:
  - Existing API/Obsidian consumer behavior remains backward-compatible.
  - `pytest -q -k "not docker_sandbox"` green.

## PR-BE-H0-Canonical-PaperID (After H2)
- Title: `feat(core): canonical paper_id issuance and normalization utilities`
- Priority: Medium
- Purpose: Close remaining `PR-H0` identity gap.
- Scope:
  - `normalize_doi`, canonical `paper_id` issuance (`zotero:/doi:/pdfsha256`) policy module.
  - Ingestion/discovery entrypoints adopt shared helper without schema break.
- Merge Gate:
  - Existing records remain readable and untouched.
  - New records follow canonical issuance policy deterministically.

## PR-BE-V2-EventLog-Followups (Deferred)
- Title: `chore(event-log): harden taxonomy/replay and ops observability`
- Priority: Medium
- Purpose: Close residual hardening after baseline event-log rollout.
- Merge Gate:
  - Error taxonomy mapping is standardized across failure paths.
  - Replay/read models for `runs -> jobs -> events` are query-ready for UI/ops.
  - `pytest -q` full suite green.
