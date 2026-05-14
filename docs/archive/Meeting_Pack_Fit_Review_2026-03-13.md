# Meeting Pack Fit Review (2026-03-13)

Status: Historical fit review
Date: 2026-03-13
Owner: Repository maintainers
Canonical parent: `docs/MEETING_PACK.md`

## Compared Inputs
- `docs/Lattice_v3_Master_Spec.md`
- `docs/WEB_VIEWER.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/RESEARCH_DNA.md`
- `docs/Pending_PR_Queue.md`
- `src/schemas/skills.py`
- `src/skills/storage.py`
- `backend/routers/paper_notes.py`

## Purpose
사용자 feature brief를 현재 repo의 canonical contracts와 비교해서, 어디를 그대로 수용하고 어디를 repo 상황에 맞게 수정해야 하는지 고정한다.

## Consolidated Judgment

### 1. `Meeting Pack`은 새로운 research state가 아니라 downstream presentation draft다
이 판단은 현재 문서들과 가장 잘 맞는다.

근거:
- `docs/WEB_VIEWER.md`는 `.pp/<slug>/state.json`를 structured paper state의 canonical source로 둔다.
- `docs/API_CHAT_CONTRACT.md`도 같은 state를 chat-readiness source로 재사용한다.
- `docs/RESEARCH_DNA.md`는 상위 design/audit asset과 executable projection의 경계를 이미 강조한다.

따라서 `Meeting Pack`이 claim/evidence truth를 다시 소유하면 안 된다.

### 2. pack 저장 경로는 `storage/meeting_packs/`가 더 적합하다
사용자 초안의 `meeting_packs/<pack_id>/...` 의도는 유지하되, repo 상황에 맞게 generated runtime storage로 옮기는 편이 낫다.

채택:
- `storage/meeting_packs/<pack_id>/meeting_pack.json`
- `storage/meeting_packs/<pack_id>/meeting_pack.md`

기각:
- `.pp/<slug>/meeting_packs/...`
  - 이유: literature update / project progress / topic pack은 single slug scope를 넘을 수 있다.
- `storage/artifacts/...`
  - 이유: 기존 artifact tree는 ingest/read/verify run output용이다.

### 3. evidence ref contract는 새로 만들지 말고 existing locator semantics를 재사용해야 한다
`docs/API_CHAT_CONTRACT.md`와 `src/schemas/skills.py`가 이미 `paper_slug`, `claim_id`, `evidence_id`, `run_id`, `locator` 조합을 갖고 있다.

따라서 `Meeting Pack`은:
- top-level pack-local evidence ledger만 추가하고
- locator payload 자체는 기존 contract를 재사용하는 편이 맞다.

이 선택으로 얻는 효과:
- claim/evidence deep link와 alignment 유지
- future viewer/chat/workbench reuse 가능
- evidence jump semantics duplication 방지

### 4. v1은 `/skills/run` 확장보다 별도 service/endpoint가 더 적합하다
현재 `/skills/run`은 note-local action wrapper에 가깝다.

`Meeting Pack`은 성격이 다르다.
- output type이 더 크다
- input이 multi-source일 수 있다
- one-page summary + slide outline + notes/questions/next steps라는 composite artifact를 쓴다
- future consumer가 viewer, project dashboard, export layer로 넓어질 수 있다

따라서 thin FastAPI wrapper를 별도 route로 두는 쪽이 더 명확하다.

### 5. user brief의 `draft-first, evidence-linked` 방향은 그대로 유지해야 한다
이 부분은 기존 repo 가치와 정확히 맞는다.

정렬되는 existing rules:
- API-first
- Pydantic contract
- idempotent writes
- evidence-linked claims
- no silent unsupported synthesis

## Adaptations Made For This Repo

### storage adaptation
- from: generic `meeting_packs/<pack_id>/...`
- to: `storage/meeting_packs/<pack_id>/...`

### source adaptation
- from: feature brief의 broad source list
- to: explicit priority rooted in `state.json` first, notes/profiles second

### evidence adaptation
- from: ad hoc evidence refs
- to: `API_CHAT_CONTRACT` aligned evidence ledger + pack-local IDs

### endpoint adaptation
- from: unspecified generation surface
- to: `POST /meeting-packs/generate` 중심

## Risks If Implemented Incorrectly

1. If pack generation writes unsupported synthesis:
- feature는 slide draft가 아니라 hallucinated narrative generator가 된다.

2. If pack is stored under one note slug:
- literature/topic/project mode가 즉시 어색해진다.

3. If new evidence schema is invented:
- existing claim/evidence deep-link contract가 중복된다.

4. If output only exists as free text:
- later slide export or reviewer diff가 어려워진다.

5. If v1 includes slide rendering:
- correctness lane와 presentation lane가 섞여 scope가 급격히 커진다.

## Durable Conclusion
현재 PaperPipe 상황에서 `Meeting Pack`은 아래 정의로 여는 것이 가장 적절하다.

- downstream draft artifact
- `state.json` first
- evidence-linked sections required
- stored as structured JSON + deterministic Markdown
- separate backend service/endpoint
- no slide export in v1

이 결론을 active canonical로 고정한 문서는 `docs/MEETING_PACK.md`다.
