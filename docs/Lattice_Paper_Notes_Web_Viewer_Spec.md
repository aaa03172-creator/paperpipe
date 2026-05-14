# Lattice Paper Notes Web Viewer Spec

Status: Active  
Date: 2026-03-13  
Owner: Lattice runtime (`backend/` + `frontend/`)  
Canonical feature spec: `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`  
Applies to: `/papers`, `/papers/:slug`, note-to-workbench bridge, viewer-related UX review loop

Related operating docs:
- Runbook: `docs/WEB_VIEWER.md`
- Scoped queue: `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`
- Translation boundary: `docs/Korean_Reading_Assist_Policy.md`
- Midpoint checkpoint: `docs/archive/Paper_Notes_Workbench_Midpoint_Checkpoint_2026-03-13.md`

## 1. Purpose
이 문서는 사용자가 제안한 "Paper Notes Web Viewer (Obsidian-style) + Product Psychology /ux-review Loop" 프롬프트를 현재 Lattice 코드베이스에 맞게 편집한 최종 운영 명세서다.

이 문서는 새 아이디어를 그대로 복사한 제안서가 아니다. 아래 세 문서와 현재 구현 상태를 비교해, 실제로 바로 적용 가능한 계약만 남긴 실행 명세서다.

- 상위 운영 SSOT: `docs/Lattice_v3_Master_Spec.md`
- UI/UX 가드레일: `docs/Lattice_v3_Master_Spec.md` + `docs/UIUX_Adoption_Filter_2026-02-25.md`
- UI 채택/제외 기준: `docs/UIUX_Adoption_Filter_2026-02-25.md`

## 2. Comparison Summary

| Proposed prompt item | Current Lattice state | Final decision |
| --- | --- | --- |
| Next.js App Router 고정 | 현재 운영 프론트는 Vite + React Router | 현 단계에서는 채택하지 않음. 재작성 금지. 현재 스택 유지 |
| TailwindCSS | 이미 사용 중 | 채택 |
| shadcn/ui 고정 | 아직 전면 도입 아님 | 신규 재사용 UI primitive에 한해 점진 채택 |
| Obsidian note viewer | `/papers`, `/papers/:slug` 이미 구현됨 | 유지/고도화 |
| gray-matter + remark/rehype | 백엔드는 Python parser, 프론트는 `react-markdown + remark-gfm` | 현재 구조 유지. backend parse + frontend render 방식 채택 |
| build-time index | 현재 backend runtime scan + cached JSON index | 현재 구조 유지 |
| product psychology rules pin | `rules/product-psychology` git submodule already present | 현 상태 유지, AGENTS/docs로 사용 규칙만 강화 |
| `/ux-review` 의무화 | 일부 규칙 존재, 템플릿/산출물 규격은 약함 | AGENTS + docs로 고정 |

## 3. Non-Negotiables

### 3.1 Product naming
- 사용자 노출 제품명은 `Lattice`를 사용한다.
- 코드/패키지/legacy note path의 `paperpipe` 표기는 하위 호환으로 유지한다.

### 3.2 Architecture
- Paper Notes Viewer는 기존 Lattice 런타임에 붙는 기능이다.
- 코어 데이터 접근은 FastAPI를 통해 이뤄진다.
- Vault 경로를 브라우저가 직접 읽지 않는다.
- 논문 노트 웹 뷰어 때문에 frontend stack을 Next.js로 교체하지 않는다.

### 3.3 UI rule
- 신규 viewer-facing UI는 랜덤한 bespoke 컴포넌트 증식을 금지한다.
- 새 재사용 컴포넌트가 필요하면 `frontend/src/app/components/ui/` 아래에 vendored `shadcn/ui` 스타일 primitive로 추가한다.
- 기존 Lattice `--pp-*` 토큰과 dark-first tone은 유지한다.
- glassmorphism, glow-heavy, 과한 motion은 금지한다.

### 3.4 UX review rule
- UI/UX/정보구조/검색/필터/추천/참조 정책 변경 전에는 `/ux-review`를 수행한다.
- 산출물은 아래 두 파일 규칙을 따른다:
  - `docs/UX_REVIEW_TEMPLATE.md`
  - `docs/UX_REVIEW_REPORT_<flow>.md`

### 3.5 Translation boundary
- English/original text remains canonical across search, screening, claim/evidence truth, and final judgment.
- Korean, if shown, is a display-only reading-assist layer.
- v1 translation is partial only and must not be used for inclusion/exclusion or final evidence judgment.

## 4. Fixed Stack

### 4.1 Adopted stack
- Backend: FastAPI
- Frontend: Vite + React Router + TypeScript
- Styling: TailwindCSS + existing `--pp-*` theme tokens
- Markdown render: `react-markdown + remark-gfm`
- Note parsing/indexing: backend-side parsing + cached JSON index

### 4.2 Deferred, not adopted now
- Next.js App Router rewrite
- Full framework migration solely for viewer screens
- Frontend-only filesystem parsing

## 5. Source of Truth

### 5.1 Vault source
- Source of truth is the Obsidian vault configured by `config.yaml` `paths.obsidian_vault`.
- Primary note path pattern is typically `Inbox/PaperPipe/*.md`, but detection is metadata-first, not path-only.

### 5.2 Expected frontmatter
- Required or commonly expected:
  - `id`
  - `aliases`
  - `tags[]`
  - `date_processed`
  - `confidence`
  - `status`
  - `pp.structured_path`
  - `pp.last_run`
  - `pp.actions_done`
  - `pp.signals.*`
- Optional:
  - `pdf_url`
  - `doi`
  - `doi_url`
  - `zotero_link`
  - `zotero_url`
  - `zotero_uri`

### 5.3 Expected body sections
- One-Line Summary
- Critical Analysis
- Key Findings & Evidence
- Critical Review (ClaimSet)
- Related Papers
- References

본문은 섹션이 일부 없더라도 렌더링되어야 한다. 다만 `Related Papers`, `References`는 detail page 전용 구조로 승격할 수 있다.

## 6. Routes and UX Contracts

### 6.1 `/papers`
Purpose:
- 노트 검색, 상태/태그 필터, 날짜/신뢰도 정렬, 결과 스캔

Required behaviors:
- title + aliases + slug + id 기반 검색
- structured fields(`claim_tags`, `entities`, `mesh`, `outcomes`, `pp.signals.last_appraisal`) 검색
- quoted exact phrase and multi-token AND query 지원
- tag filter
- status filter
- `Structured only` quick filter
- sorting by `date_processed`, `confidence`
- pagination
- current filters reflected in URL query

UI contract:
- 현재 운영본은 row-card 중심 목록 구조를 사용한다.
- 향후 개선 시 shadcn-style `Input`, `Select`, `Badge`, `Command`, `Card` 조합을 우선한다.
- 결과 행/카드는 최소 아래 정보를 노출한다:
  - title
  - tags
  - status
  - date
  - confidence
  - operational summary / structured signals when available

### 6.2 `/papers/:slug`
Purpose:
- Obsidian note를 읽기 모드로 보여주고, related/reference/workbench로 이어지는 허브 역할

Current contract:
- Properties panel
- Operational summary in Properties when available
- Markdown body render
- Related Papers
- References
- Actions card backed by `available_actions`
- Structured state rendering (`runs`, `claimset`, `entities/mesh/outcomes`, signals)
- Automation Results write-scope badges
- note-local `Signal updates` comparison UI
- Workbench CTA

Layout contract:
- Desktop:
  - left: note context/navigation
  - center: markdown body
  - right: properties, related papers, references
- Mobile:
  - center-first reading
  - right panel content moves into Sheet/Drawer

Implementation note:
- 현재 운영본은 desktop 3-pane + mobile Sheet/Drawer 구조를 채택했다.
- 이후 변경도 route/API 유지 하에서 이 레이아웃 계약을 보존해야 한다.

## 7. API Contracts

### 7.1 `GET /paper-notes`
Query contract:
- `q`
- `tag` legacy single tag
- `tags` comma-separated multi-tag
- `status`
- `structured_only`
- `sort_by=date_processed|confidence`
- `sort_order=asc|desc`
- `page`
- `page_size`

Response contract:
- `total`
- `page`
- `page_size`
- `total_pages`
- `available_tags`
- `available_statuses`
- `items[]`
  - optional `ops_summary`

### 7.2 `GET /paper-notes/{slug}`
Query contract:
- `related_limit`

Response contract:
- `note`
- `frontmatter`
- `body_markdown`
- `related[]`
- `references[]`
- `structured_state`
- `available_actions[]`
  - includes preflight metadata (`enabled`, `disabled_reason`, `secrets_required`, `network`, `sandbox`, `license`, `source_skills`)

### 7.3 `POST /skills/run`
Request contract:
- `slug`
- `action`
- `append_markdown_summary`
- `force`

Behavior contract:
- writes raw run JSON to `vault/.pp/<slug>/runs/<ts>_<action>.json`
- writes merged structured state to `vault/.pp/<slug>/state.json`
- updates frontmatter `pp.*`
- optionally appends short markdown summary section
- exposes run artifact metadata:
  - `artifacts.structured_path`
  - `artifacts.write_scope.structured_state`
  - `artifacts.write_scope.frontmatter_pp`
  - `artifacts.write_scope.markdown_summary`

### 7.4 Workbench bridge
- Detail page CTA uses `note.id` first.
- Fallback may derive workbench id from slug only when mapping is deterministic.

### 7.5 Content review state contract
- `issues_state` is the current viewer-facing state contract for content-review availability:
  - `flagged`
  - `clear`
  - `unavailable`
- Current accepted implementation:
  - backend prefers stored `issues_state` when present and otherwise falls back to deriving it from `issues` / `issues_label` plus legacy `status`
  - legacy batch producer (`src/processor.py`) and watcher local producer (`src/watcher.py`) now write explicit `issues_state` from producer-owned `processing_status` when they own the analysis/gating result
  - Zotero sync inserts new paper rows with `issues_state="unavailable"`
  - frontend treats `issues_state` as the primary signal and `issues_label` as supporting detail copy
- Explicitly deferred:
  - `review_flags[]`
  - richer content-review taxonomy
- Reopen condition:
  - only when additional producer or artifact payloads emit structured content-review fields directly beyond the current batch-producer path

## 8. Indexing Contract

### 8.1 Chosen strategy
- Backend runtime scans vault and stores cached JSON index at:
  - `storage/obsidian/paper_notes_index.json`

### 8.2 Required index fields
- `slug`
- `title`
- `aliases`
- `tags`
- `date_processed`
- `confidence`
- `status`
- `id`
- `note_path`
- `pp.signals`
- `claimset.tags`
- `entities`
- `mesh`
- `outcomes`
- optional `ops_summary`

### 8.3 Why runtime index was chosen
- Vault path is server-local and privacy-sensitive.
- Backend already owns the vault config and masking policy.
- Next.js-style build-time indexing is unnecessary for the current runtime.

## 9. Markdown and Obsidian Link Rules

### 9.1 Markdown
- GFM must render correctly.
- Headings, lists, tables, links, blockquotes are first-class.

### 9.2 Wiki-links
- `[[Some Note]]` -> `/papers/<resolved-slug>`
- `[[Note|Label]]` -> label text with viewer route
- Legacy vault path links such as `[[Inbox/PaperPipe/foo|Label]]` must resolve to the matching slug where possible.

### 9.3 Section handling
- If the backend extracts `Related Papers` or `References` into structured fields, the viewer may omit duplicate raw markdown sections from the center content.
- Avoid rendering the same section twice.

## 10. Related Papers Logic
- Related papers are computed by shared tags plus structured-signal overlap.
- Top N defaults to backend limit.
- Each related item must show:
  - clickable title
  - shared tags
  - shared structured signals when present
- Current scoring stays lightweight and backend-owned:
  - shared tags
  - shared `entities` / `mesh` / `outcomes`
  - shared `claimset.tags`

## 11. References and PDF Policy

### 11.1 Default priority
1. private-safe PDF link
2. DOI
3. Zotero link
4. other external references

### 11.2 Safety and copyright
- Public viewer mode must not prefer direct copyrighted PDF hosting.
- If link masking is enabled, local `file://` or direct filesystem PDF links must be suppressed.
- Viewer/UI copy should explain when DOI/Zotero is preferred over PDF.

## 12. UX Review Loop

### 12.1 Mandatory trigger
Run `/ux-review` before changing:
- Paper Notes list search/filter/sort flow
- detail page layout
- related ranking or presentation
- references policy or CTA copy
- workbench handoff CTA
- empty/error states

### 12.2 Mandatory report header
- `Screen/Flow`
- `Goal action`
- `Primary persona`
- `Current friction`
- `Success metric`
- `Constraints`

### 12.3 Current defer decisions
- Do not add list density presets without observed scan-speed problems or materially larger note volume.
- Do not unify timeline/stepper grammar with operational state unless real user confusion is observed.
- Do not promote verification/gate `reason_codes` into viewer taxonomy without an explicit mapping contract.

### 12.4 Mandatory report sections
1. Quick Review (5 min)
2. Full Review (P0/P1/P2)
3. BMAP diagnosis
4. B.I.A.S diagnosis
5. Peak-End design notes
6. Ethics Check
7. Concrete changes
8. Next PR-sized actions

## 13. Acceptance Criteria

### 13.1 Functional
- `/papers` shows notes with working search/filter/sort/pagination
- `/papers/:slug` shows properties, markdown, related papers, references, actions, automation results, ClaimSet
- `/skills/run` writes structured state, run JSON, frontmatter `pp.*`, and optional short markdown summary
- related papers are clickable and show shared tags / structured signals when available
- workbench bridge resolves for mapped notes

### 13.2 Policy
- viewer changes create a matching `docs/UX_REVIEW_REPORT_<flow>.md`
- new reusable UI primitives do not bypass the shadcn-style component rule
- public-safe references policy is documented and reflected in UI behavior

### 13.3 Current evidence
- backend/API tests:
  - `tests/test_paper_notes_api.py`
  - `tests/test_papers_api.py`
  - `tests/test_skills_api.py`
  - `tests/test_full_pipeline.py`
  - `tests/test_processor_institutional_proxy.py`
  - `tests/test_db_utils_download_attempts.py`
  - `tests/test_watcher_issue_state.py`
  - `tests/test_db_utils_sync_zotero_issue_state.py`
- frontend build:
  - `cd frontend && npm run build`
- backend e2e viewer coverage: `frontend/e2e/backend.spec.ts`
- ops guide: `docs/WEB_VIEWER.md`

## 14. Out of Scope
- standalone Next.js rewrite
- public PDF hosting service
- replacing Obsidian as the authoring source of truth
- reworking the Workbench under this viewer spec

## 15. Current Next Actions
1. Reopen content-review state work only if producer/artifact payloads can emit a direct structured source beyond label-derived `issues_state`.
2. Revisit list density controls only if observed note volume or scan-speed evidence justifies them.
3. Revisit timeline/stepper grammar only if real user confusion appears between progress, event, and operational-state signals.
