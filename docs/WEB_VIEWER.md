# Lattice Paper Notes Viewer

Status: Active
Date: 2026-03-13
Owner: Lattice runtime (`backend/` + `frontend/`)
Canonical runbook: `docs/WEB_VIEWER.md`

Related specs:
- Feature spec: `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
- UX review command: `docs/ux-review.md`
- UX review template: `docs/UX_REVIEW_TEMPLATE.md`
- Scoped queue: `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`
- Midpoint checkpoint: `docs/archive/Paper_Notes_Workbench_Midpoint_Checkpoint_2026-03-13.md`

## 목적
Obsidian Vault에 저장된 논문 노트(`.md + frontmatter`)를 웹에서 동일하게 조회하기 위한 뷰어입니다.

- 목록: `/papers`
- 상세: `/papers/:slug`
- backend-served direct entry:
  - `/ui` -> triage shell
  - `/ui/papers` -> paper notes list
  - `/ui/papers/:slug` -> paper note detail
  - `/ui/workbench/:paperId` -> workbench
  - reason: backend JSON API already owns root paths such as `/papers`, so direct browser entry must stay under `/ui/*`

현재 web viewer boundary에는 `Research DNA`가 포함되지 않습니다.
- `Research DNA`는 현재 API/CLI operator lane으로 유지한다.
- `/ui/research-dna` 같은 dedicated frontend viewer route는 현재 제품 범위가 아니다.

챗봇 자체는 현재 활성 제품 범위 밖입니다. 대신 아래 미래 대비 훅은 유지합니다.
- canonical structured state: `vault/.pp/<slug>/state.json`
- URL focus deep link:
  - `/papers/<slug>?focus=claim:<id>`
  - `/papers/<slug>?focus=evidence:<id>`
  - `/papers/<slug>?focus=run:<id>`
  - current scope decision: list/detail/actions/ClaimSet/related 흐름은 acceptance를 충족했다. 추가 search sophistication, density preset, audit-deep-link는 trigger-based backlog로만 유지한다.
  - `Section navigator` pilot is allowed only as a read-only viewer aid derived from existing note headings plus saved evidence `locator.section`.
  - it is navigation help only and must not become a second section-truth owner beside canonical state and source locators.
- verification checkpoint (2026-03-13):
  - real `state.json -> /paper-notes/{slug} -> /papers/:slug` path was rechecked against live workspace data.
  - sample note `wenzelShortchainFattyAcids2020` renders `2` claim cards and `2` evidence cards, and `?focus=evidence:<id>` correctly focuses the target evidence card.
  - all current real structured sidecars in the vault validate against `StructuredPaperState`.
  - Workbench now prefers canonical `paper-notes` structured sidecar state over stale artifact claimsets when a note-backed paper id is resolvable.
  - one live note-backed sidecar check (`zoteroduboisAlzheimerDiseaseClinicalBiological2024`) confirmed `claim_c0ffee000001 -> page 1 -> bbox(8,10,40,20) -> source=bbox` through the frontend notebook helper path.
  - that paper choice was a validation-time workspace example, not a default domain assumption for the viewer itself.
  - current viewer issue is not missing claim/evidence cards; the remaining limitation is upstream evidence-grounding coverage, because most real locators are still `text_match` rather than `bbox`.
- checkpoint decision (2026-03-13):
  - `issues_state`는 유지하되, richer taxonomy로 확장하지 않는다.
  - `review_flags[]`, density preset, timeline/stepper grammar unification은 evidence-triggered backlog로만 다룬다.
  - cross-surface viewer/workbench 후속 작업은 repo-wide queue 대신 `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`에서 별도 추적한다.
  - list/detail/actions 단위의 trigger-based micro-backlog는 해당 `docs/UX_REVIEW_REPORT_<flow>.md`에 남긴다.

## 데이터 소스
- Vault source root: `config.yaml`의 `paths.obsidian_vault`
- Current implementation intentionally uses backend runtime indexing, not a Next.js build-time filesystem pass.
- Structured sidecar source of truth for skill runs: `vault/.pp/<slug>/state.json`
- note body/frontmatter는 operator-facing mirror surface이며, canonical run/claim/evidence state를 대체하지 않는다.
- 주로 사용하는 frontmatter 키:
  - `id`, `aliases`, `tags`, `date_processed`, `confidence`, `status`
  - `pp.structured_path`, `pp.last_run`, `pp.actions_done`, `pp.signals.*`
  - 선택: `doi`, `pdf_url`, `zotero_link`/`zotero_url`/`zotero_uri`
- 노트가 paper note로 인식되는 조건:
  - 위 핵심 키 중 하나 이상 존재, 또는
  - 상대 경로에 `paperpipe` 문자열 포함

## 백엔드 API
현재 라우터: `backend/routers/paper_notes.py`

- `GET /paper-notes`
  - query:
    - `q`
      - title/alias/slug/id/tag 검색
      - structured fields도 포함: `claim_tags`, `entities`, `mesh`, `outcomes`, `pp.signals.last_appraisal`
      - quoted exact phrase 지원: `"Clinical-Biological Construct"`
      - multi-token AND 지원: `Amyloid Neurology`
    - `tag` (legacy single tag)
    - `tags` (comma-separated multi-tag, OR semantics)
    - `status`
    - `structured_only` (`ClaimSet` 또는 structured signals가 있는 note만)
    - `sort_by`: `date_processed | confidence`
    - `sort_order`: `asc | desc`
    - `page` (기본 1)
    - `page_size` (기본 30, 1~200)
  - response: `PaperNoteListResponse`
    - 주요 필드: `total`, `page`, `page_size`, `total_pages`, `available_tags`, `available_statuses`, `items`
    - 각 item은 optional `ops_summary`를 포함할 수 있음:
      - `state`: `healthy | action_needed`
      - `label`: `Healthy | Action needed`
      - `reason`: workbench와 맞춘 운영 문구 (`Stats report is missing or empty.` 등)
      - `recommended_action`: `none | repair_stats | open_workbench`
  - 정렬 동작:
    - `date_processed`: 날짜(파싱 실패 시 원문 문자열) 기준
    - `confidence`: 숫자 기준 (없으면 `-1.0` 취급)
    - `q`가 있으면 secondary sort 후 relevance-first ordering을 추가 적용

- `GET /paper-notes/{slug}`
  - query:
    - `related_limit` (기본 5, 범위 1~20)
  - response: `PaperNoteDetailResponse`
  - 포함 내용:
    - Properties(frontmatter)
    - Markdown 본문(GFM 렌더용)
    - Related Papers(공유 태그 + structured signals 기반)
    - References(Open PDF/DOI/Zotero 우선순위)
    - `section_navigator[]`
      - derived navigation aid from note headings plus saved evidence `locator.section`
      - prefers latest structured run `data.section_summary` when present, then falls back to claimset-derived reconstruction
      - read-only and non-canonical
    - optional `context_trace`
      - deterministic note-detail context assembly trace
      - expected actions:
        - `note_loaded`
        - `body_sections_filtered`
        - `references_resolved`
        - `related_computed`
        - `structured_state_loaded`
      - this is operational metadata only, not reader-facing scientific truth
    - `structured_state` (`runs[]`, `claimset[]`, `entities/mesh/outcomes`)
    - `available_actions` (`extract_markdown`, `validate_citations`, `critical_appraisal`)
      - preflight metadata 포함:
        - `enabled`
        - `disabled_reason`
        - `secrets_required`
      - `network`, `sandbox`, `license`, `source_skills`

- `GET /paper-notes/resolve-by-paper-id`
  - query:
    - `paper_id`
  - response: `PaperNoteStructuredStateLookupResponse`
  - purpose:
    - resolve a workbench `paper_id` back to the canonical note slug/frontmatter id
    - expose canonical `structured_state` for note-backed workbench rendering
  - current use:
    - Workbench prefers this sidecar state for claim/evidence highlight generation when available

- `POST /skills/run`
  - request: `{ slug, action, append_markdown_summary?, force? }`
  - writes:
    - `vault/.pp/<slug>/runs/<ts>_<action>.json`
    - `vault/.pp/<slug>/state.json`
    - note frontmatter `pp.*`
    - optional short markdown section `## 🔧 Automation Results (short)`
  - run artifact metadata:
    - `artifacts.structured_path`
    - `artifacts.write_scope.structured_state`
    - `artifacts.write_scope.frontmatter_pp`
    - `artifacts.write_scope.markdown_summary`
  - `append_markdown_summary=false`여도 structured state, raw run JSON, frontmatter `pp.*`는 계속 갱신된다.

- `POST /api/chat`
  - stub only
  - default `CHAT_ENABLED=false` => `501 Not Implemented`
  - even with `CHAT_ENABLED=true`, the current runtime still returns `501 Not Implemented`
  - no external LLM/provider call, no memory, no RAG

## Viewer Output Mode
- detail route supports additive `view` query param:
  - `/papers/<slug>?view=learner`
  - `/papers/<slug>?view=builder_debug`
- default is `learner` when omitted
- current behavior is presentation-only:
  - rail/panel ordering
  - helper copy and emphasis
- non-goals:
  - no different retrieval/runtime chain
  - no different claim/evidence truth policy
  - no profile or persona reinterpretation

## API ↔ UI 매핑(현재 구현)
### `/papers` 목록 페이지
- 프론트 파일: `frontend/src/app/pages/PaperNotesListPage.tsx`
- 데이터 로드: `GET /paper-notes` (필터/정렬/페이지네이션 파라미터 포함)
- 검색/태그/상태/정렬/페이지네이션: 현재 **서버 측 계산**
  - URL 쿼리 동기화 키: `q`, `tags`, `status`, `structured`, `sort`, `order`, `page`, `page_size`, `tag_input`
  - API 요청 파라미터 매핑:
    - `q` -> `q`
    - `tags` -> `tags` (comma-separated, OR semantics)
    - `status` -> `status`
    - `structured=1` -> `structured_only=true`
    - `sort` -> `sort_by`
    - `order` -> `sort_order`
    - `page` -> `page`
    - `page_size` -> `page_size`
  - list affordances:
    - row-level `Structured signals` chips
    - query match chip highlighting
    - `Structured only` quick toggle
    - `relevance first` cue when `q` is active
    - contextual empty-state recovery:
      - `Search without quotes`
      - `Turn off Structured only`
      - token-based fallback search buttons

### `/papers/:slug` 상세 페이지
- 프론트 파일: `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- 데이터 로드: `GET /paper-notes/{slug}`
- 렌더링 매핑:
  - Properties 패널: `note` 객체 (`id/aliases/tags/date_processed/confidence/status`)
    - `note.ops_summary`가 있으면 same-language operational summary 렌더
    - when the latest structured run carries `section_navigation_signal_status`, Properties also shows a compact section-navigator readiness row
    - older saved states may still infer the same row from run `data.section_summary` / `section_count` when explicit handoff quality-gate status is absent
    - this row is additive viewer guidance only; it does not own section truth and does not replace the separate `Section navigator` panel
  - 본문: `body_markdown` (GFM)
  - Related Papers: `related[]` with shared tags plus structured signals reasoning
  - References: `references[]` + access policy summary (`preferred source`, DOI/Zotero readiness, source role 설명)
  - Section navigator: derived read-only section map from note outline plus saved evidence `locator.section`
    - runtime preference order:
      - latest structured run `data.section_summary`
      - claimset/evidence fallback when older state files do not include runtime section summaries yet
    - frontend fallback mirrors the same preference order when `section_navigator[]` is absent from the detail response
    - purpose:
      - reopen long notes faster
      - jump from section label to note heading or saved evidence focus
    - non-goals:
      - no new retrieval backend
      - no section registry as truth owner
      - no promotion of viewer-derived grouping into canonical state
  - optional `context_trace`
    - summary of which note/index/sidecar paths contributed to the detail view
    - operational/debug contract only
    - current UI may keep it behind an optional/debug disclosure
    - but detail surfaces should not require operator narration to explain missing canonical structured state or which saved sidecar path was used
  - Actions card: `available_actions[]` -> `POST /skills/run`
    - `Add short note summary` toggle -> `append_markdown_summary`
    - toggle은 note-local state이며, 다른 note로 이동하면 기본값으로 reset된다.
    - 각 action row는 기본 정책 배지로 `network`, optional `sandbox`, optional `license`, `source_skills`, optional `secret <ENV_NAME>`를 노출한다.
    - secret-required action은 `secret <ENV_NAME>` badge를 노출하고, preflight에서 secret이 없으면 button disabled + reason copy를 같이 보여준다.
    - action 직후에는 `Signal updates` 블록으로 `pp.signals`의 새 값과 변경값을 inline badge로 보여주고, `new` vs `changed`를 구분한다.
    - `Signal updates`는 persisted output이 아니라 note-local comparison UI다. reload, action failure, 다른 note 이동 시 reset된다.
  - Automation Results cards: `structured_state.runs[]`
    - write-scope badges: `state updated`, `frontmatter updated`, `body summary/body skipped`
    - badges는 `run.artifacts.write_scope.{structured_state,frontmatter_pp,markdown_summary}`에서 직접 파생된다.
    - legacy runs without `artifacts.write_scope` keep rendering normally and simply omit these badges.
    - when `structured_state` is absent, product-ready detail surfaces should say that no canonical sidecar state was loaded instead of relying only on a generic empty run-history card.
  - ClaimSet cards: `structured_state.claimset[]`
    - empty-state copy should preserve the same distinction: missing sidecar truth vs loaded-but-empty structured claims
  - `focus` query 지원:
    - `claim:<id>`
    - `evidence:<id>`
    - `run:<id>`
  - Workbench CTA: `note.id` 우선, 없으면 `slug`로 `/workbench/{paperId}` 링크

### Triage / Workbench entry points
- 프론트 파일:
  - `frontend/src/app/pages/TriageDashboard.tsx`
  - `frontend/src/app/pages/AnalysisWorkbench.tsx`
  - `frontend/src/app/components/Rail.tsx`
- 동작:
  - `GET /papers?limit=5000` 응답이 각 `paper` row에 `ops_summary`를 포함한다.
  - triage queue와 workbench rail은 별도 note-index fetch 없이 이 `ops_summary`를 직접 사용한다.
  - repair/rebuild나 artifact refresh 이후에도 `/papers`를 다시 불러와 rail과 queue 상태를 함께 갱신한다.
  - triage는 `Content Review`와 operational state를 다른 signal로 취급한다.
    - `Content Review`: paper summary 기반 콘텐츠/품질 플래그(`issues`)를 뜻한다.
    - `issues_label`이 있으면 triage/workbench detail copy는 이 값을 그대로 보여준다. 프런트가 임의 taxonomy를 만들지 않는다.
    - `/papers`와 `/papers/{paper_id}`는 `issues_state` (`flagged | clear | unavailable`)를 함께 내려주고, 프런트는 이 값을 `Content Review` state의 1차 source-of-truth로 사용한다.
    - backend는 저장된 `issues_state`가 있으면 그 값을 우선 사용하고, 없을 때만 `issues` / `issues_label`과 legacy `status`에서 structured fallback을 만든다.
    - legacy batch producer(`src/processor.py`)와 watcher local producer(`src/watcher.py`)는 자신이 계산한 `processing_status`와 실제 분석 실행 여부를 기준으로 `issues_state`를 직접 저장한다.
    - Zotero sync 신규 row는 `issues_state="unavailable"`로 삽입되어, 미분석 paper가 `Clear`로 오인되지 않게 한다.
    - `issues=0`이어도 `issues_label`이 `Not analyzed` 같은 availability 상태를 뜻하면, UI는 이를 `Clear`가 아니라 `Unavailable`로 보여준다.
    - operational state: artifact health(`Healthy`, `Action needed`, `Stats report is missing or empty.`)를 뜻한다.
    - rail의 `QA {n}` badge와 triage의 `Content Review` column은 artifact health warning과 시각적으로 분리되어야 한다.
    - rail은 compact surface이므로 모든 row를 늘리지 않고, 현재 선택된 flagged paper에만 `issues_label` detail 한 줄을 보인다.
    - unavailable 상태는 rail에서도 `QA unavailable` muted chip으로 구분하고, 현재 선택된 paper에는 `issues_label` detail을 같이 보여준다.
  - workbench도 `focus=issues` 진입 시 같은 `Content Review` 문맥을 유지한다.
    - 상단 notice는 issue-focus 여부와 content-review 상태를 먼저 설명하고, `issues_label`이 있으면 같은 detail copy를 함께 보여준다.
    - artifact panel에는 `Content Review` summary card가 별도로 렌더된다.
  - shared UI primitive:
    - `frontend/src/app/components/OperationalStateSummary.tsx`
    - badge + reason + optional action hint를 list/detail/triage/rail/workbench body에서 공용으로 사용한다.
    - workbench body는 `/papers` 응답이 아직 없거나 선택 paper row가 비어도 현재 artifact state로 동일 language fallback summary를 만든다.
    - `frontend/src/app/components/StatusBadge.tsx`
    - `frontend/src/app/lib/statusSystem.ts`
    - processing status chip, note frontmatter status, operational state badge가 같은 tone token 계층을 사용한다.
  - Workbench actions:
    - `Repair Stats`: `claimset 있음 + stats_report 없음` 상태에서만 직접 노출
    - `Rebuild Stats`: 기존 snapshot overwrite가 필요한 경우에만 `Advanced actions` 안에서 노출
    - 두 액션 모두 `POST /ops/repair-stats`를 사용하되, `Rebuild Stats`는 `skip_existing=false`로 호출한다.
    - `Sync to Obsidian`: 같은 상단 notice/success/error 패턴을 사용하며, terminal에는 `obsidian-sync summary`를 남긴다.
    - sync 중에는 repair/rebuild를 막고, repair/rebuild 중에는 sync를 비활성화한다.

## 인덱싱(빌드/캐시)
- Vault 스캔 결과를 JSON으로 저장(요청 시 재생성):
  - `storage/obsidian/paper_notes_index.json`
- 인덱스 항목:
  - `slug`, `title(alias 우선)`, `tags`, `date_processed`, `confidence`, `status`
  - `pp.signals`
  - `claimset.tags`, `entities`, `mesh`, `outcomes`
  - `pp.signals.last_appraisal` (query/relevance support)
  - optional `ops_summary` (latest artifact health derived from the preferred run artifact directory under `storage/artifacts/<paper-segment>/<run_id>`)
- 제외 규칙:
  - 디렉터리명 `.obsidian`, `_backup`
  - 숨김 경로(`.` prefix) 전반

## 렌더링 규칙
- wiki-link `[[path/to/note|label]]` → `/papers/{slug}` 링크로 변환
- 기존 노트 본문의 `Related Papers`/`References` 섹션은 상세 페이지 전용 컴포넌트에서 별도 렌더링
- 기존 노트 본문의 automation dump는 지양하고, 짧은 `Automation Results (short)` 섹션만 유지
- Markdown 렌더링: `react-markdown + remark-gfm`
- note detail `context_trace`는 body filter, reference resolution, related derivation, structured-state load를 기록하지만, evidence truth를 새로 소유하지 않는다

## Structured State Contract
- canonical source: `vault/.pp/<slug>/state.json`
- frontmatter는 light index만 유지:
  - `pp.structured_path`
  - `pp.last_run`
  - `pp.actions_done`
  - `pp.signals`
- `state.json` 최소 필드:
  - `runs[]`
  - `signals`
  - `claimset[]`
  - `entities[]`
  - `mesh[]`
  - `outcomes[]`
- stable ids:
  - `run.id`
  - `claim.id`
  - `evidence.id`
- 상세 계약: [API_CHAT_CONTRACT.md](/Users/jangseongjin/paperpipe/docs/API_CHAT_CONTRACT.md)

## References 우선순위/보안 규칙
- 기본 우선순위:
  1. frontmatter `pdf_url`
  2. 본문 References 섹션의 PDF 링크
  3. DOI
  4. Zotero
  5. 기타 외부 링크
- 기본 경로 마스킹:
  - 로컬 파일 절대경로와 `pdf` source 링크(`file://`, `.pdf`, `Open PDF`)는 기본적으로 응답에서 제외
  - trusted local debugging이 꼭 필요할 때만 `LATTICE_MASK_LOCAL_PATHS=0` 또는 `PAPERPIPE_MASK_LOCAL_PATHS=0`으로 opt-out

## 프론트 구조
- Current frontend stack:
  - Vite + React Router + TypeScript
  - TailwindCSS
  - `react-markdown + remark-gfm`
- 라우팅:
  - `frontend/src/App.tsx`
- 페이지:
  - `frontend/src/app/pages/PaperNotesListPage.tsx`
  - `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- API:
  - `frontend/src/app/lib/api.ts`
- 타입:
  - `frontend/src/app/lib/types.ts`

## 실행 방법
1. 백엔드 실행
```bash
python3 -m uvicorn backend.main:app --reload --port 8000
```

2. 프론트 실행
```bash
cd frontend
npm install
npm run dev
```

3. 브라우저 접속
- [http://localhost:5173/papers](http://localhost:5173/papers)

## 배포 참고
- 서버는 `config.yaml`의 vault 경로에 접근 가능해야 합니다.
- 공개 배포 시에는 저작권 PDF 직접 호스팅 대신 DOI/Zotero 링크 사용이 기본 안전 경로입니다.
- 기본 동작은 path masking 활성화입니다. 로컬 파일 링크를 일부러 노출해야 하는 trusted debugging이 아니면 그대로 유지하세요.
- UI/UX 변경 전에는 `docs/UX_REVIEW_TEMPLATE.md` 기준으로 `docs/UX_REVIEW_REPORT_<flow>.md`를 생성합니다.

## 테스트
- API 단위 테스트:
```bash
pytest -q tests/test_papers_api.py tests/test_paper_notes_api.py tests/test_skills_api.py
```
- producer-level `issues_state` 저장 spot check:
```bash
pytest -q tests/test_full_pipeline.py tests/test_processor_institutional_proxy.py tests/test_db_utils_download_attempts.py
pytest -q tests/test_watcher_issue_state.py
pytest -q tests/test_db_utils_sync_zotero_issue_state.py
```
- 프론트 build:
```bash
npm --prefix frontend run build
```
- 백엔드 E2E(화면+API 연동):
```bash
npm --prefix frontend run e2e:backend
```
- content-review / operational-state focused spot check:
```bash
cd frontend && E2E_BACKEND_PORT=18207 E2E_FRONTEND_PORT=43202 \
  npx playwright test -c playwright.backend.config.ts \
  e2e/backend.spec.ts --grep "content review|workbench reuses the same operational state summary language"
```
- skills/actions / structured-state focused spot check:
```bash
cd frontend && E2E_BACKEND_PORT=18208 E2E_FRONTEND_PORT=43203 \
  npx playwright test -c playwright.backend.config.ts \
  e2e/backend.spec.ts --grep "renders structured actions, automation results, and claimset cards|persist a structured result|without appending a markdown summary|resets quiet-run controls"
```
