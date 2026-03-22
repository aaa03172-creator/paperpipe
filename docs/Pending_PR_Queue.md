# Pending PR Queue

Status: Active working queue
Date: 2026-03-17
Owner: Repository maintainers
Canonical: `docs/Pending_PR_Queue.md`

## Queued

## Future RFC Follow-Ups (Not Approved)
- Title: `future/protocol-knowledge-layer`
- Priority: Low
- Purpose: Explore a bounded protocol knowledge surface without redefining the current product around a new `projects/documents` platform.
- Reference: `docs/archive/Protocol_Knowledge_Layer_RFC_2026-03-18.md`

- Title: `future/method-comparison-layer`
- Priority: Low
- Purpose: Explore a paper-centric comparison artifact layer with explicit cell-level provenance and no spreadsheet-platform scope creep.
- Reference: `docs/archive/Method_Comparison_Layer_RFC_2026-03-18.md`
- Implementation plan: `docs/archive/Method_Comparison_v0_Implementation_Plan_2026-03-18.md`

- Title: `future/project-memory-layer`
- Priority: Low
- Purpose: Explore a bounded project memory/workspace layer only after an explicit product decision that this should become first-class.
- Reference: `docs/archive/Project_Memory_Layer_RFC_2026-03-18.md`

- Title: `future/local-backup-restore-semantics`
- Priority: Low
- Purpose: Unify local-first backup-before-apply, restore-readiness, and rerender-vs-restore semantics without pretending the repo already has a first-class project backup API.
- Reference: `docs/archive/Local_Backup_and_Restore_Semantics_RFC_2026-03-18.md`

- Title: `future/research-data-visualization-layer`
- Priority: Low
- Purpose: Explore a bounded chart/figure artifact layer for structured research-data visualization without turning current Lattice into a generic dataset platform.
- Reference: `docs/archive/Research_Data_Visualization_Layer_RFC_2026-03-18.md`
- Implementation plan: `docs/archive/Research_Data_Visualization_v0_Implementation_Plan_2026-03-18.md`

- Title: `future/image-evidence-viewer-layer`
- Priority: Low
- Purpose: Explore an image-evidence sidecar layer with raw/derived separation and external-viewer handoff without turning current Lattice into a microscopy management platform.
- Reference: `docs/archive/Image_Evidence_Viewer_Layer_RFC_2026-03-18.md`
- Implementation plan: `docs/archive/Image_Evidence_Viewer_v0_Implementation_Plan_2026-03-18.md`

## PR-DOC-BE-MeetingPack-v1 (Completed in workspace)
- Title: `docs/backend: define Meeting Pack v1 as evidence-linked lab meeting draft artifact`
- Priority: High
- Purpose: Add reusable lab-meeting draft generation without introducing slide export, unsupported synthesis, or a second research-state canonical.
- Scope:
  - [done] `docs/MEETING_PACK.md`로 canonical boundary, mode structure, source priority, evidence rule, storage/API contract 고정
  - [done] `docs/archive/Meeting_Pack_Fit_Review_2026-03-13.md`와 `docs/archive/Meeting_Pack_v1_Implementation_Plan_2026-03-13.md`로 fit review와 PR sequence 기록
  - [done] `src/schemas/meeting_pack.py` + `meeting_packs_root()` + store skeleton 추가
  - [done] `state.json` first source resolver와 pack-level evidence ledger 구현
  - [done] `POST /meeting-packs/generate`, `POST /meeting-packs/{pack_id}/regenerate`, `POST /meeting-packs/{pack_id}/rerender`, `GET /meeting-packs/{pack_id}`, `GET /meeting-packs/{pack_id}/markdown` thin FastAPI surface 추가
  - [done] `storage/meeting_packs/<pack_id>/meeting_pack.json` + `.md` 저장과 `journal_club` vs `experiment_proposal` mode contrast regression coverage 추가
  - [done] saved `generation_request` snapshot + rerenderable deterministic markdown contract 추가
  - [done] note-backed selectors(`paper_note`, `project_note`, `research_note`) 추가 with linked `paper_state` resolution
  - [done] `5-8` slide draft shape와 note-backed API regression coverage 추가
  - [done] `topic` selector support 추가 with deterministic structured-signal exact matching
  - [done] `project_profile` / `research_profile` selector support 추가 with deterministic `ResearchDNA` projection-profile resolution
  - [done] generic manual profile selector guard 추가 (projection metadata가 없는 profile은 reject)
  - [done] structured `one_page_summary.consensus_points[]` + Markdown `[Consensus]` rendering 추가
  - [done] shared focus-family adjudication 추가 with root-overlap paraphrase match, limited synonym aliasing, and `increase/decrease/null/benefit/harm` wording buckets
  - [done] higher-is-better / higher-is-worse focus-family framing 추가 so strong cases can align benefit-like and signed increase/decrease wording
  - [done] `safety` family strong cases에 limited row-level valence mapping 추가 so `improved tolerability` and `reduced adverse events` can align without reopening fuzzy matching
  - [done] clear `3+` source majority lane에서 `majority_directional_alignment` partial consensus 추가 while keeping structured divergence conflict
  - [done] note/screening context를 `discussion_questions[]` / `expected_questions[]` / `next_steps[]`에 mode-specific follow-up wording으로 반영
  - [done] note/screening context를 overview, first key-point uncertainty note, opening/context slide framing까지 확장 while keeping claim text source-first
  - [done] `cross_focus_pattern`이 생성되면 top summary / limits slide에서 family-level directional consensus보다 먼저 보이도록 ordering 조정
  - [done] shared majority subset이 여러 focus family에서 반복될 때 `cross_focus_majority_pattern` partial summary 추가 with same-source-population guard
  - [done] `cross_focus*` label/evidence/source-id ordering canonicalization + partial convergence `outlier_source_item_ids[]` 추가
  - [done] curated glycemic family 확장으로 `blood sugar`와 `glycemic/glucose` strong-case alignment 추가
  - [done] `validate` now rechecks the saved selector set against the current vault before reporting regenerate availability
  - [done] bundle save now rolls back on second-write failure so partial `meeting_pack.json` / `meeting_pack.md` artifacts are not left behind
- Notes:
  - locator/evidence payload는 `docs/API_CHAT_CONTRACT.md`와 existing claim/evidence IDs를 재사용해야 한다.
  - v1 non-goals: PPTX export, Google Slides export, auto-designed slide visuals, chatbot integration.
  - current limitation: bounded legacy regenerate fallback policy, branch-required rollout / API escalation policy for the new Meeting Pack CI verify lane (currently blocked on this private repo by GitHub branch-protection `403` plan limits), broader synonym coverage beyond the small alias map, looser cross-focus majority/outlier semantics beyond the current same-source-population guard, and deeper note/context-derived tuning beyond the current framing layer는 아직 follow-up이다.

## Next Up (2026-03-18)
- Recommended next: package the already-committed backend/API stack into a PR/change-summary bundle
  - 이유: `PR-M0` baseline adoption은 이미 commit `5c09619`로 실행됐고, 그 뒤의 Meeting Pack/runtime/paper-notes/skills/obsidian/method-comparison follow-up lane도 개별 commit으로 고정됐다. 현재 남은 ambiguity는 baseline adoption 여부가 아니라, 이 committed stack을 어떤 narrative로 묶고 어떤 dirty tail을 별도 lane으로 남길지다.
- Current stack note: use `docs/reports/Committed_Backend_API_Stack_Summary_2026-03-18.md` as the current packaging summary
  - 이유: 이 note는 `5c09619` baseline anchor 이후의 additive commit stack, latest validation, remaining dirty tails(`backend/main.py`, `src/schemas/agent_artifacts.py`)를 한 곳에 모아준다.
- PR packaging note: use `docs/reports/Backend_API_PR_Packaging_2026-03-18.md` as the ready-to-paste PR title/body/review-order draft
  - 이유: 현재는 새 baseline 실행이 아니라 이미 commit된 stack을 reviewer가 이해 가능한 narrative로 묶는 단계이므로, title/body/validation/out-of-scope를 바로 재사용할 수 있는 packaging note가 필요하다.
- Current-state recheck note: use `docs/reports/Current_Baseline_Recheck_2026-03-18.md` as the short "bind now vs separate lane" execution note
  - 이유: 2026-03-18 기준 repo의 실제 가치는 이미 bounded `Research DNA`, evidence-linked `Meeting Pack`, additive paper-note `context_trace`까지 포함한 biomedical core loop에 있고, 이 note는 baseline adoption 이후에도 무엇을 separate lane으로 남겨야 하는지 다시 좁혀준다.
- External reference guardrail: interpret recent external references only in a bounded `sidecar`, `fallback`, `benchmark`, `dataset`, or `reference` frame
  - 이유: `GLM-OCR`, `OpenDataLoader PDF`, `Scientific Taste`, `Ars Contexta`, `OpenAlex`, `MedCPT`, `Docling`, `PaperQA2` 등은 current repo 기준에서 architecture replacement 후보가 아니라 제한적 fit-review 입력이다. baseline-freeze work를 새 architecture hunt로 넓히면 안 된다.
- Reopen-condition guardrail: only revisit those external references if the repo-grounded recheck conditions in `docs/reports/Current_Baseline_Recheck_2026-03-18.md` are satisfied
  - 이유: 외부 레퍼런스 검토는 새 roadmap item이 아니라 조건부 재검토 대상이다. 실측 없는 재개는 queue churn만 만든다.
- Baseline adoption note: use `docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md` as the canonical include/exclude boundary
  - 이유: 이 note는 `PR-M0`가 어떤 include/exclude boundary로 실행되었는지를 설명하는 historical baseline note로 유지된다. 실행 자체는 commit `5c09619`로 끝났지만, boundary 설명은 여전히 여기서 canonical하다.
- Dry-run and staged-candidate notes remain historical validation artifacts
  - 이유: `docs/archive/PR_M0_Staging_Dry_Run_2026-03-17.md`와 `docs/archive/PR_M0_Staged_Candidate_Validation_2026-03-17.md`는 실행 전 검증 기록으로 유지하되, 현재의 실행 단계는 아니다.
- Baseline freeze guardrail: do not broaden selector semantics during `PR-M0`
  - 이유: baseline freeze의 목적은 current green slice를 고정하는 것이지, profile/topic/note semantics를 더 넓히는 것이 아니다.
- Baseline freeze guardrail: `backend/main.py`는 whole-file adoption이 아니라 `meeting_packs.router` import/include hunk만 좁게 추출
  - 이유: 현재 `backend/main.py` 작업트리 diff는 너무 넓어서, raw inclusion은 `PR-M0`를 baseline freeze가 아니라 broad product expansion으로 보이게 만든다.
- Guardrail note: recent `Research DNA` eval-report hardening and paper-note `context_trace` are additive hardening slices, not reasons to broaden `PR-R0` or `PR-M0`
  - 이유: 두 변화 모두 explainability와 reproducibility를 높이지만, 새 runtime layer나 broader UI/product scope를 열어야 하는 성질은 아니다.
- Technical next lane if coding resumes: keep `agent_artifacts` contract hardening bounded as a separate schema lane
  - 이유: `src/schemas/agent_artifacts.py` hardening은 여전히 separate lane으로 다뤄야 하지만, 현재 증적상 reader/runtime redesign으로 넓힐 이유는 없다.
  - 현재 범위: `DocumentChunk` metadata 확장, `EvidenceSpan` text-vs-table payload/bbox sanity, `ScientificClaim.unknown*` normalization
  - 현재 검증:
    - `pytest -q tests/test_claimset_policy.py tests/test_document_artifact_v2.py tests/test_indexer_agent_chunk_ids.py tests/test_job_runner_ingest_backend.py` -> `27 passed`
    - `pytest -q tests/test_citation_grounding.py tests/test_deepread_note_writer.py tests/test_worker_job_runner_chain.py tests/test_paper_notes_api.py` -> `26 passed`
  - guardrail: schema/test lane로만 유지하고 reader/runtime redesign으로 확장하지 않는다.
- Guardrail note: projection-backed profile selectors are usable only when the latest screened include set maps to existing vault `state.json`
  - 이유: query/profile text만으로 pack을 만들면 `state.json` first evidence boundary가 무너진다.
- Follow-up after that: only after packaging and bounded schema/test hardening, tighten mode-specific tuning from note/context inputs without letting them override structured claim/evidence truth
  - 이유: overview/key-point/slide framing까지는 반영됐지만, 더 깊은 synthesis 단계에서 context weighting은 아직 얇다.
- Operational follow-up: retry natural quarantine only if a materially different candidate pool or stricter gate configuration becomes available
  - 이유: 2026-03-13 widened probe(`limit 20`, `low-confidence-threshold 0.95`)에서도 `19 accepted / 0 quarantine`였다.
- Optional evidence upgrade: benchmark breadth review only if a materially better independent source appears
  - 이유: `Research DNA` 트랙의 bounded external benchmark는 이미 충분히 닫혀 있으므로, 더 강한 independent source가 실제로 나타날 때만 다시 여는 편이 맞다.
- Optional quality follow-up: real Deep Read output hardening after the Park 2022 browser/runtime audit
  - 이유: runtime wiring, unsupported limitation leakage, quote/raw_text/source grounding mismatch, evidence quote display cleanup, and degenerate-table fallback semantics는 fresh rerun 기준으로 닫혔다. 현재 남은 것은 residual claim fidelity/compression과 broader upstream table extraction quality다 (`docs/archive/Deep_Read_Real_Quality_Check_Park_2026-03-13.md`).

## PR-FE-Workbench-Contextual-State-Badges (Completed in workspace)
- Title: `feat(ui): add contextual state badges and inline action feedback across workbench entry points`
- Priority: Medium
- Purpose: Carry forward the next-step UX hardening after the Repair Stats flow so missing-state reasoning is visible before opening a paper.
- Scoped follow-up:
  - viewer/workbench-specific next actions now move to `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`
  - midpoint review is recorded in `docs/archive/Paper_Notes_Workbench_Midpoint_Checkpoint_2026-03-13.md`
- Scope:
  - [done] left rail and relevant list views show `stats missing` style badges where applicable
  - [done] advanced rebuild path is separated from normal repair CTA
  - [done] sync/repair result feedback patterns are aligned across workbench actions
  - [done] shared operational status summary primitive is used across list/detail/triage/rail/workbench body
  - [done] note status chip, processing status chip, and operational state now share the same badge/tone system
  - [done] `/papers` contract now carries `ops_summary`, removing the separate runtime note-ops fetch path
  - [done] triage `Content Review` cues are separated from operational artifact health cues
  - [done] workbench now preserves triage `Content Review` context in issue-focus notice and artifact summary
  - [done] backend-provided `issues_label` now stays visible across triage, workbench notice/body, and selected rail context instead of collapsing to generic copy
  - [done] zero-issue `Content Review` now distinguishes `Unavailable` states like `Not analyzed` from true `Clear` states
  - [done] `/papers` contract now carries `issues_state`, so frontend `Content Review` state no longer depends on label regex alone

## PR-OPS-Teacher-Baseline-Regression-Batch (Completed in workspace)
- Title: `ops(quality): run larger local-first teacher batch against promoted baseline`
- Priority: Medium
- Purpose: Turn the existing promoted baseline into an actual ongoing regression check instead of a one-off compare run.
- Scope:
  - [done] run a local-first teacher batch from current candidate extraction flow (`qualityloop_20260313_batch01`)
  - [done] compare resulting metrics against `baselines/quality_eval_teacher_compare_20260310`
  - [done] record that the current candidate pool capped at `8 real + 1 local unsupported`, with no natural quarantine case in this run
  - [done] write a dated runtime report with pass/fail decision and promotion outcome

## PR-OPS-Teacher-Natural-Quarantine-Probe (Completed in workspace)
- Title: `ops(quality): widen teacher candidate extraction and check for natural quarantine`
- Priority: Medium
- Purpose: Determine whether a naturally occurring quarantine case appears once the local-first candidate pool is widened beyond the initial regression batch.
- Scope:
  - [done] widen extraction to `qualityloop_20260313_batch02` with `--limit 20 --low-confidence-threshold 0.95`
  - [done] generate local-first teacher outputs for the widened bundle pool (`success=19`, `failed=1`)
  - [done] verify all completed real outputs in an isolated goldset root and record final routing result (`accepted=19`, `quarantine=0`)
  - [done] run quality eval + baseline compare for the widened batch and record no-regression result
  - [done] write a dated runtime report concluding that controlled drill remains the only canonical quarantine evidence under the current candidate pool/gates

## PR-DOC-BE-ResearchDNA-v0 (Completed)
- Title: `docs/backend: define Research DNA v0 boundary and pilot loop`
- Priority: High
- Purpose: Add a reproducible search-design asset without creating a second live canonical beside `config/profiles.yaml`.
- Scope:
  - [done] `docs/RESEARCH_DNA.md` 초안 작성 with `DRAFT -> PILOT -> LOCKED` and `ResearchDNA -> Profile` projection rules
  - [done] v1 범위는 `Researcher 4 + Librarian 4` interview로 제한
  - [done] `recommended_databases`와 `available_databases`를 분리
  - [done] append-only `query_versions`, `run_log`, `approval_audit`, `screening_log` 최소 계약 정의
  - [done] `pilot -> screening -> refine` loop와 `reason_code` refinement 규칙 정의
  - [done] goldset sanity check는 optional로 유지
  - [done] `full PRESS automation`, `mandatory grey literature`, `external DOI archiving`, `OpenAlex-first`는 P1로 명시
  - [done] `src/profiles/research_dna_schema.py` / `src/profiles/research_dna_store.py` / runtime path helper(`research_dna_root`, `search_eval_root`) 구현 + 회귀 테스트 추가
  - [done] service hooks로 `create / approve_pilot / refine / submit_screening / lock / unlock` 및 append-only audit semantics 구현
  - [done] `run_pilot` + `manifest/queries/retrieved/screening_queue/metrics` artifact generation 구현
  - [done] thin FastAPI wrapper 추가 with API-key protection and regression tests
  - [done] thin CLI wrapper 추가 under `paperpipe research-dna ...`
  - [done] interview logging operator surface 추가 under service/API/CLI and `interview.jsonl`
  - [done] `scripts/evaluate_search.py`와 `storage/search_eval/<run_id>/...` artifact contract 구현
  - [done] `update_dna` path 추가 + `DRAFT` 단계 `v1` query draft 허용으로 spec mismatch 해소
  - [done] compare/promotion workflow를 fixed baseline 운영 루프로 연결
  - [done] keep/discard threshold policy(`min_labeled_count`, `min_precision_delta`, optional `goldset_recall`)와 baseline naming rule(`dna_id/current + history/run_id`) 확정
  - [done] real pilot batch 1회로 baseline seed/compare/promotion 운영 기록 남기기
  - [done] first-run baseline seed helper 추가로 수동 baseline copy 단계 제거
  - [done] optimistic revision guard 추가로 duplicate create와 stale overwrite 차단
  - [done] `pilot.goldset[]` 기반 optional recall 계산을 `scripts/evaluate_search.py`에 연결
  - [done] retrospective provisional goldset으로 real pilot recall sanity follow-up 기록 (`v1=0.125`, `v2=1.0`)
  - [done] compare provenance 보존을 위해 `baseline_snapshot.json` artifact 추가
  - [done] repeated promotion history overwrite를 막기 위해 same-`run_id` history에 append-only suffix naming 적용
  - [done] `versions/vN.yaml`을 full state가 아닌 deterministic query-only snapshot으로 정리
  - [done] `pilot.goldset_kind / goldset_sources / goldset_note` provenance fields 추가
  - [done] independent external benchmark candidate source review 기록
  - [done] strongest current candidate (`PMC11074881`)에 대한 adjudicated subset manifest 저장 (`5 include`, `1 exclude`)
  - [done] real probe run1/run2에 subset manifest 평가를 적용해 `external_benchmark_recall` 운영 증적 확보 (`0.0 -> 1.0`)
  - [done] second independent source (`PMC9947355`) adjudication + union manifest 저장 (`6 include`, `2 exclude`)
  - [done] union manifest 기준 breadth-sensitive external benchmark eval 운영 증적 확보 (`0/6 -> 6/6`)
  - [done] optional `external_benchmark_recall_delta`를 keep/discard policy에 연결해 evidence와 gate semantics를 정렬
  - [done] bounded external benchmark candidate의 최소 판단 기준을 문서로 고정
  - [done] explicit operator approval 적용으로 `pilot.goldset_kind`를 `retrospective_provisional -> external_benchmark`로 승격하고, stale baseline 위험이 있던 parallel rerun을 폐기한 뒤 순차 재평가 결과(`run1 0/6`, `run2 6/6`)만 canonical로 채택
  - [done] future goldset-kind changes가 generic `update`에 섞이지 않도록 dedicated `change_goldset_kind` audit action 추가
  - [done] `ResearchDNA -> Profile` deterministic projection helper 추가 with projected ID `research_dna_<dna_id>`, `enabled=false`, `schedule=manual`, and provenance-rich `Profile.notes`
  - [done] legacy `profiles` / `audit` CLI가 projected profile을 수정하지 못하도록 read-only guard 추가
  - [done] real workspace projection validation 완료 and fixed-temp-path write race hardening applied to `profile_store.py` / `research_dna_store.py`
  - [done] legacy `profiles` / `audit` CLI를 `PAPERPIPE_PROFILES_PATH`와 정렬하고, operator-facing `profiles.yaml` writes를 lock + merge-safe update/upsert path로 전환
  - [done] legacy `profiles` / `audit` same-profile mutation에 per-profile revision conflict guard 추가로 stale overwrite 차단
  - [done] raw `save_profiles_snapshot()` overwrite를 operator-facing profiles path에서 기본 차단하고, fixture/bootstrap snapshot만 explicit unsafe flag로 허용
  - [done] generic `rewrite_profiles_config()` bulk rewrite도 operator-facing profiles path에서 기본 차단하고, projection 같은 system-owned path만 explicit opt-in으로 허용
- Notes:
  - current reference set:
    - `docs/archive/Deep_Research_Report5_Fit_Review_2026-03-11.md`
    - `docs/archive/Prompt_Review_Integrated_Priority_2026-03-11.md`
    - `docs/archive/Prompt_Review_01_Autoresearch_Search_2026-03-11.md`
    - `docs/archive/Prompt_Review_05_Research_DNA_2026-03-11.md`
    - `docs/archive/Research_DNA_v0_Implementation_Plan_2026-03-11.md`
    - `docs/archive/Research_DNA_Real_Pilot_Probe_2026-03-12.md`
  - this item does not supersede the current frontend `Recommended next`; it is the next coherent search/profile lane once that work is reopened

## PR-FE-PaperNotes-Operational-State-Summary (Completed in workspace)
- Title: `feat(paper-notes): add operational health summary to list and detail`
- Priority: Medium
- Purpose: Surface `Healthy` / `Action needed` note state before opening Workbench and keep the wording aligned with the Repair Stats flow.
- Scope:
  - [done] backend `paper-notes` index derives latest artifact health from `storage/artifacts`
  - [done] `/papers` list shows action-needed and healthy badges using the same stats-missing vocabulary as Workbench
  - [done] detail `Properties` panel mirrors the same operational summary
  - [done] API regression, frontend build, backend e2e all pass

## PR-FE-PaperNotes-Viewer-Obsidian-Layout (Completed in workspace)
- Title: `feat(paper-notes): move detail page toward Obsidian-style 3-pane layout`
- Priority: High
- Purpose: Align the paper notes viewer with the final feature spec without rewriting the current runtime stack.
- Scope:
  - [done] desktop detail page adopts left/context + center/body + right/meta layout
  - [done] mobile detail page moves meta/related/references into sheet-style UI
  - [done] `/ux-review` report generated before implementation per `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`

## PR-FE-PaperNotes-TagFilter-Command (Completed in workspace)
- Title: `feat(paper-notes): replace add-tag filter with command-style chip selection`
- Priority: Medium
- Purpose: Reduce search/filter friction on `/papers` so tag discovery feels like browsing a vault, not operating a form.
- Scope:
  - [done] remove `Add`-dependent tag entry flow
  - [done] use shadcn-style command/chip interaction for tag selection
  - [done] run `/ux-review` before implementation and refresh `UX_REVIEW_REPORT_paper-notes-viewer.md`

## PR-FE-PaperNotes-References-Policy (Completed in workspace)
- Title: `feat(paper-notes): explain reference access policy in detail sidebar`
- Priority: Medium
- Purpose: Make DOI/Zotero/PDF priority legible so the References panel explains why a given link is preferred.
- Scope:
  - [done] add access policy summary card to the References panel
  - [done] label the preferred link and source role for each reference
  - [done] keep API contract unchanged and verify via backend e2e

## PR-FE-PaperNotes-List-Hierarchy (Completed in workspace)
- Title: `feat(paper-notes): restructure list rows into vault-browser hierarchy`
- Priority: Medium
- Purpose: Make `/papers` easier to scan by elevating title, status, confidence, and structured signals before raw metadata.
- Scope:
  - [done] replace table/card split with shared responsive row-card layout
  - [done] surface status/confidence/source/structured badges near the title
  - [done] verify via backend e2e and visual snapshot update

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
- `PR-QA-Local-Pytest-Stability-20260225`
- `PR-DOC-ReleaseNotes-2026-02-25-UI-Mock-Test-Stability`

## PR-QA-Local-Pytest-Stability-20260225 (Completed)
- Title: `test/docs: stabilize local pytest and document forced mock mode`
- Priority: Medium
- Purpose: Keep local full-suite test runs deterministic after UI/mock changes and reduce environment-specific false failures.
- Scope:
  - [done] `tests/test_api_key_auth.py` DB_PATH cleanup leak fixed (`finally` restore).
  - [done] `tests/test_docker_sandbox.py` now skips when Docker daemon is unavailable.
  - [done] frontend forced mock mode docs added (`frontend/README.md`).
  - [done] local full test recheck at merge: `pytest -q -> 254 passed, 5 skipped`.
  - [done] merged via PR #85 (`bd9582d`).

## PR-OPS-Teacher-Quality-Loop (Completed)
- Title: `feat(quality): add teacher candidate/gate/goldset/eval promotion loop`
- Priority: High
- Purpose: Reduce ongoing manual/Codex dependency by making local quality iteration reproducible and measurable.
- Scope:
  - [done] SSOT runtime path resolver 추가 (`src/services/runtime_paths.py`) with env override + repo-relative fallback.
  - [done] 후보 추출 스크립트 추가 (`scripts/extract_teacher_candidates.py`) with reproducible `manifest.json`.
  - [done] 게이트 검증/라우팅 추가 (`src/quality/gates.py`, `scripts/verify_teacher_output.py`) with `reason_codes[]`.
  - [done] quarantine review CLI + runbook 추가 (`scripts/review_teacher_quarantine.py`, `docs/teacher_quality_loop.md`)
  - [done] deterministic split 빌더 추가 (`scripts/build_goldset.py`) with paper_id hash rule and overlap guard.
  - [done] quality eval 모드 추가 (`scripts/eval/run_eval.py --mode quality`) for 4 core metrics.
  - [done] baseline/new 비교 + 승격 게이트 추가 (`scripts/eval/compare_eval.py`).
  - [done] 회귀 테스트 추가 (`tests/test_extract_teacher_candidates.py`, `tests/test_teacher_gate_verifier.py`, `tests/test_build_goldset.py`, `tests/test_eval_quality_compare.py`).
  - [done] local-first teacher generation 추가 (`src/quality/teacher_review.py`, `scripts/generate_teacher_outputs.py`) with evidence location remap.
  - [done] real teacher outputs 기준 운영 검증 1회 완료 (`docs/archive/Teacher_Quality_Loop_Real_Output_Probe_2026-03-09.md`).
  - [done] quarantine review workflow drill 완료 (`docs/archive/Teacher_Quality_Loop_Quarantine_Review_Drill_2026-03-09.md`).
- Notes:
  - 2026-03-09 local-first teacher probes produced `8/8 accepted` and no natural quarantine record.
  - reviewer-workflow evidence was therefore captured with a controlled drill on a real bundle in an isolated goldset root.
  - 2026-03-10 baseline compare/promotion cycle completed successfully (`docs/archive/Teacher_Quality_Loop_Baseline_Compare_2026-03-10.md`).

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
