# Lattice Paper Notes Viewer

## 목적
Obsidian Vault에 저장된 논문 노트(`.md + frontmatter`)를 웹에서 동일하게 조회하기 위한 뷰어입니다.

- 목록: `/papers`
- 상세: `/papers/:slug`

## 데이터 소스
- Source of truth: `config.yaml`의 `paths.obsidian_vault`
- 주로 사용하는 frontmatter 키:
  - `id`, `aliases`, `tags`, `date_processed`, `confidence`, `status`
  - 선택: `doi`, `pdf_url`, `zotero_link`/`zotero_url`/`zotero_uri`
- 노트가 paper note로 인식되는 조건:
  - 위 핵심 키 중 하나 이상 존재, 또는
  - 상대 경로에 `paperpipe` 문자열 포함

## 백엔드 API
새 라우터: `backend/routers/paper_notes.py`

- `GET /paper-notes`
  - query:
    - `q` (title/alias/slug/id 검색)
    - `tag`
    - `status`
    - `sort_by`: `date_processed | confidence`
    - `sort_order`: `asc | desc`
  - response: `PaperNoteListResponse`
  - 정렬 동작:
    - `date_processed`: 날짜(파싱 실패 시 원문 문자열) 기준
    - `confidence`: 숫자 기준 (없으면 `-1.0` 취급)

- `GET /paper-notes/{slug}`
  - query:
    - `related_limit` (기본 5, 범위 1~20)
  - response: `PaperNoteDetailResponse`
  - 포함 내용:
    - Properties(frontmatter)
    - Markdown 본문(GFM 렌더용)
    - Related Papers(공유 태그 교집합 기반)
    - References(Open PDF/DOI/Zotero 우선순위)

## API ↔ UI 매핑(현재 구현)
### `/papers` 목록 페이지
- 프론트 파일: `frontend/src/app/pages/PaperNotesListPage.tsx`
- 데이터 로드: 최초 1회 `GET /paper-notes`
- 검색/태그/상태/정렬/페이지네이션: 현재 **클라이언트 측 계산**
  - URL 쿼리 동기화 키: `q`, `tags`, `status`, `sort`, `order`, `page`, `tag_input`
  - 참고: API의 `q/tag/status/sort_by/sort_order`는 준비되어 있으나, 현재 목록 페이지는 서버 필터를 직접 사용하지 않음

### `/papers/:slug` 상세 페이지
- 프론트 파일: `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- 데이터 로드: `GET /paper-notes/{slug}`
- 렌더링 매핑:
  - Properties 패널: `note` 객체 (`id/aliases/tags/date_processed/confidence/status`)
  - 본문: `body_markdown` (GFM)
  - Related Papers: `related[]`
  - References: `references[]`
  - Workbench CTA: `note.id` 우선, 없으면 `slug`로 `/workbench/{paperId}` 링크

## 인덱싱(빌드/캐시)
- Vault 스캔 결과를 JSON으로 저장(요청 시 재생성):
  - `storage/obsidian/paper_notes_index.json`
- 인덱스 항목:
  - `slug`, `title(alias 우선)`, `tags`, `date_processed`, `confidence`, `status` 등
- 제외 규칙:
  - 디렉터리명 `.obsidian`, `_backup`
  - 숨김 경로(`.` prefix) 전반

## 렌더링 규칙
- wiki-link `[[path/to/note|label]]` → `/papers/{slug}` 링크로 변환
- 기존 노트 본문의 `Related Papers`/`References` 섹션은 상세 페이지 전용 컴포넌트에서 별도 렌더링
- Markdown 렌더링: `react-markdown + remark-gfm`

## References 우선순위/보안 규칙
- 기본 우선순위:
  1. frontmatter `pdf_url`
  2. 본문 References 섹션의 PDF 링크
  3. DOI
  4. Zotero
  5. 기타 외부 링크
- 경로 마스킹 활성 시:
  - 환경변수 `LATTICE_MASK_LOCAL_PATHS=1` 또는 `PAPERPIPE_MASK_LOCAL_PATHS=1`
  - `pdf` source 링크(`file://`, `.pdf`, `Open PDF`)는 응답에서 제외

## 프론트 구조
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
- `file://` 링크 노출이 불필요하면 path masking 설정을 활성화해 로컬 파일 링크를 숨길 수 있습니다.

## 테스트
- API 단위 테스트:
```bash
pytest -q tests/test_paper_notes_api.py
```
- 백엔드 E2E(화면+API 연동):
```bash
npm --prefix frontend run e2e:backend
```
