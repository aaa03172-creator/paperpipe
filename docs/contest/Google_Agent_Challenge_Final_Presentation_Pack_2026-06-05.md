# Google Agent Challenge Final Presentation Pack

Status: Finals presentation packet
Date: 2026-06-02
Event target: Google Agent Challenge finals, 2026-06-05
Brand: Lattice

## Purpose

This is the one document to review before the finals presentation.

It combines:

- the earlier prelim submission story
- the existing architecture slides
- the verified June 2 measurement evidence
- the final demo operator runbook
- stage-safe speaker notes and Q&A boundaries

Use this as the source for final slide edits, rehearsal notes, and last-minute claim checks. It is a review/gate artifact, not a canonical product spec.

## Final Presenter Brief

Read this section first if there is not enough time to reread the full packet.

### Final Recommendation

Use the personal research-workflow pain as the opening, then quickly move to the measured cloud-paper proof.

The strongest finals story is:

> I experienced that research work breaks down when summaries, slides, protocol notes, and figures drift away from the original paper evidence. Lattice solves the first layer by preserving paper-centered evidence state, then GCP extends that state beyond one local machine through a measured cloud-paper path.

This is stronger than a pure architecture story because it explains:

- why the project exists
- why evidence/provenance matters
- why GCP is relevant
- why future project/lab sharing and downstream tools naturally fit
- why the current alpha boundaries are explicit and deliberate

### Final Stage Claim

Use this as the compact stage-safe claim:

> Lattice is an evidence-linked biomedical research workspace. For the finals, we measured a real cloud-paper path where a 34-page paper is stored through backend-mediated GCS, tracked in Firestore metadata, returned to the app through redacted FastAPI contracts, and verified by a packaged macOS alpha demo gate.

### Final Reviewer Verdict

From a judge's perspective, the story is understandable if the presentation keeps this order:

1. Real research pain: evidence gets lost after the first read.
2. Product idea: preserve paper-centered evidence state, not just summaries.
3. Agentic value: move through gated analysis/review/artifact steps.
4. GCP value: make the paper/page state durable beyond one laptop.
5. Measurement: show the 34-page, 24-second, redaction-passed gate.
6. Extension: project/lab sharing, protocol references, meeting packs, slides, graphs, and figures can attach to the same state.
7. Boundary: assisted alpha, not production SSO, not solved scientific accuracy, not shipped project-memory collaboration.

From a first-time researcher's perspective, the story is understandable if the presentation avoids internal names until after the problem is clear. Say "claim, evidence, uncertainty, and source links" before saying "schema-backed state" or "artifact bundle."

### Final Slide Decision

Use a 7-slide main deck for the live talk:

1. Personal motivation
2. Problem
3. Solution
4. Cloud paper demo
5. Measured gate
6. Extensibility
7. Roadmap and honest boundaries

Keep the detailed 11-slide notes below as expansion material or backup. If time is short, do not present separate benchmark, demo-run, and architecture slides live; fold their safest numbers into the measured-gate and roadmap slides.

### Final Non-Negotiables

- Verified numbers only: `34` pages, `8,460,622` bytes, `24` seconds, redaction passed, endpoint proofs all `200`, goldset `8/8`.
- GCP is real for the measured storage/metadata demo path; Cloud Run and Cloud Tasks are accepted production direction, not live demo infrastructure.
- Project/lab sharing is production direction, not current production-grade collaboration.
- Protocol cards are reviewable references, not SOP approval or wet-lab automation.
- Project Memory is future/support context, not an opened API, viewer, or source of truth.
- Natural language is the interface; schema-backed evidence state remains the source of truth.

## End-to-End Program Path

Use this if judges ask what the program actually does from start to finish.

### Product-Level Path

```text
Researcher pain
  -> PDF / paper input
  -> paper-centered structured state
  -> claim, evidence, uncertainty, provenance
  -> review gates
  -> downstream artifacts
  -> project/lab reuse direction
```

Stage-safe explanation:

1. A researcher starts from a real paper, not from an ungrounded chat prompt.
2. Lattice preserves the paper as structured research state: claims, evidence links, uncertainty, warnings, and provenance.
3. Gates decide what is ready, what needs review, and what must not be silently promoted.
4. Downstream artifacts such as meeting packs, comparison outputs, protocol references, slides, graphs, and figure explanations should attach to that evidence state.
5. In the production direction, approved project or lab members can reuse the same paper state and derived artifacts instead of rebuilding notes independently.

### Finals Demo Path

```text
Real 34-page PDF
  -> backend-mediated upload
  -> GCS raw PDF / page artifact storage
  -> Firestore paper metadata
  -> redacted FastAPI page/search contracts
  -> local macOS app UI
  -> cloud paper search/open/inspect
  -> final readiness gate proof
```

Stage-safe explanation:

1. The demo uses a real `34`-page PDF with checksum-tracked source identity.
2. Upload is backend-mediated; the browser does not directly access GCS.
3. GCS stores source PDF/page artifacts, while Firestore stores durable paper metadata for the controlled demo collection.
4. FastAPI returns redacted public page/search contracts to the local app UI.
5. The UI searches, opens, and inspects the cloud paper state.
6. The final gate verifies the rehearsal, redaction, package hash, packaged app proof, extracted zip proof, and core endpoint responses.

Boundary:

- Current measured path: GCS + Firestore + FastAPI + packaged macOS alpha proof.
- Accepted production direction: Cloud Run worker and Cloud Tasks dispatch.
- Not claimed live in the current gate: production SSO, deployed Cloud Run/Tasks processing, production-grade lab sharing, or automatic scientific correctness.

## Final Reading Order

Read these in order on presentation day:

1. This packet: `docs/contest/Google_Agent_Challenge_Final_Presentation_Pack_2026-06-05.md`
2. Demo operator runbook: `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md`
3. Slide metrics table: `storage/contest/google_agent_challenge_2026_06_05/slide_metrics_table_20260602T095050Z.md`
4. Final gate summary: `storage/contest/google_agent_challenge_2026_06_05/final_gate_summary_20260602T095050Z.json`
5. Metrics and benchmark brief: `docs/contest/Google_Agent_Challenge_Metrics_Benchmark_Brief_2026-06-05.md`

Optional reference:

- Prelim submission pack: `docs/contest/prelim_submission_pack_2026-05-23.md`
- Existing architecture slides: `presentation_slides_3pages.html`
- Measurement protocol: `docs/contest/Google_Agent_Challenge_Measurement_Protocol_2026-06-05.md`
- Product positioning: `docs/Product_Positioning_Principles.md`
- Knowledge layer note: `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
- Artifact bundle spec: `docs/ARTIFACT_BUNDLE_SPEC.md`
- Research workspace decisions: `docs/reports/Research_Workspace_Core_Structure_Decisions_2026-04-01.md`
- Project minimum chrome: `docs/reports/Research_Workspace_Project_Minimum_Chrome_2026-04-01.md`
- Project Memory gate: `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
- First product demo FAQ/script: `docs/reports/First_Product_Demo_FAQ_2026-03-27.md`, `docs/reports/First_Product_Demo_Script_3min_2026-03-27.md`
- Talk-pack quality guidance: `docs/TALK_PACK_QUALITY_BENCHMARK.md`, `docs/TALK_PACK_STYLE_GUIDE.md`

## What Changed From The Prelim Story

The prelim story was:

> Lattice turns papers into evidence-linked research assets.

Keep that. It is still the strongest product narrative.

The finals story adds:

> The research workspace now has a measured cloud-paper demo path: a real 34-page paper goes through backend-mediated GCS storage, Firestore metadata, redacted FastAPI page/search contracts, and an installable macOS alpha package.

Do not turn the finals into a pure architecture talk. The core win is that the old workflow vision now has a controlled, measured demo path.

## Final Narrative Frame

Use this as the opening logic for the finals talk.

### Korean Opening Script

학부연구생으로 논문을 읽고 정리하면서, 그리고 주변 선배들이 랩미팅이나 과제 발표를 준비하는 과정을 보면서 반복적으로 느낀 불편함이 있었습니다.

논문을 한 번 요약하는 것은 할 수 있지만, 시간이 지나면 그 요약이 원문 어디에 근거했는지, 어떤 figure나 문장에 연결되는지, 어떤 부분은 불확실했는지 다시 찾기가 어려웠습니다. 발표자료, 표, 그래프, 미팅 자료를 만들 때도 같은 논문을 계속 다시 정리하게 되고, AI가 만든 draft도 어디까지 믿을 수 있는지 애매했습니다.

그래서 저는 단순히 논문을 요약하는 프로그램이 아니라, 원본 논문에서 나온 claim, evidence, uncertainty, provenance를 구조화된 상태로 보존하고, 그 위에서 발표자료나 미팅 자료 같은 2차 산출물을 만들 수 있는 연구 워크스페이스를 직접 만들어보고자 했습니다.

예를 들어 한 논문의 주장 하나가 어떤 페이지, 어떤 문장, 어떤 figure에 연결되는지 저장하고, 근거가 약하거나 위치가 불확실하면 그것을 숨기지 않고 `review-needed` 상태로 남기는 방식입니다. 목표는 논문을 다시 읽지 않아도, 이전에 확인한 근거와 불확실성을 기반으로 다음 발표자료나 미팅자료를 만들 수 있게 하는 것입니다.

### Why This Matters Now

요즘은 필요한 도구를 직접 만들 수도 있고, 하루가 지나면 더 좋은 AI 도구가 새로 나오는 시대입니다. 그래서 Lattice가 모든 PPT 생성기, 그래프 도구, figure 편집 도구를 직접 끝까지 만들겠다는 접근은 적절하지 않다고 보았습니다.

대신 가장 먼저 무너지면 안 되는 부분에 집중했습니다:

- 원본 PDF가 무엇인지
- 어떤 claim이 어떤 evidence에 근거했는지
- 어떤 부분이 불확실하거나 review-needed인지
- downstream artifact가 어떤 paper state에서 나왔는지

이 구조화된 evidence state가 있으면, 그 위에 PPT, 발표 스크립트, graph, figure, comparison table, meeting pack 같은 여러 도구를 붙일 수 있습니다. 어떤 도구는 Lattice 안에서 직접 만들 수 있고, 어떤 도구는 사용자가 만들거나 외부에서 공유받아 연결할 수도 있습니다.

The key claim is not:

> We will build every research tool ourselves.

The safer claim is:

> We make the original paper/evidence state reliable and usable enough that many downstream AI tools can work on it without re-reading or re-inventing the paper from scratch.

### GCP Connection

GCP is the first measured extension of that idea.

User-facing value first:

- PDF와 논문 상태를 한 기기 안에만 두지 않고, cloud-backed 상태로 보존할 수 있습니다.
- 로컬 앱은 가볍게 유지하면서도, 승인된 환경에서는 같은 paper state를 다시 읽고 검색할 수 있습니다.
- 앞으로는 같은 프로젝트나 랩의 팀원이 승인된 권한 안에서 같은 paper state, extracted protocol reference, meeting/comparison artifact를 열람하는 방향으로 확장할 수 있습니다.
- 이때 프로젝트는 모든 데이터를 소유하는 거대한 관리 시스템이 아니라, 연구 질문을 중심으로 논문과 산출물을 묶어 주는 context가 되어야 합니다.
- 브라우저는 cloud 내부 경로나 bucket 정보를 직접 보지 않고, redacted public contract만 받습니다.

Technical implementation:

- GCS stores source PDFs and page artifacts.
- Firestore stores durable paper metadata.
- FastAPI returns redacted public page/search contracts to the browser.
- The local app can stay lightweight while reading cloud-backed paper state.

This supports the longer-term direction: researchers should not have to leave the workspace, copy-paste evidence between tools, or rebuild context manually. They should be able to ask in natural language for a meeting pack, presentation outline, comparison table, graph-ready summary, or figure-focused explanation, while the system uses the same evidence-linked state underneath.

Keep the boundary clear:

- current demo: measured cloud-paper state and alpha app proof
- current product direction: evidence-linked downstream artifacts
- future extension: project/lab-scoped sharing, protocol-reference viewing, and user-created or shared tools that attach to Lattice state
- not yet claimed: a complete plugin ecosystem or fully automatic all-in-one research platform
- not yet claimed: production-grade multi-user lab infrastructure or a first-class project-memory API

## Current / Direction / Future Boundary

Use this table if judges ask what is real now versus future-facing.

| Layer | Status | Safe wording |
| --- | --- | --- |
| Paper/evidence state | Current product direction with implemented surfaces and schemas | "Lattice preserves paper-centered evidence state and keeps downstream artifacts subordinate to that state." |
| Cloud-paper demo | Current measured demo | "The finals gate measured a real GCS + Firestore cloud-paper path through the local app." |
| Meeting/comparison-style artifacts | Current bounded downstream artifact direction | "Some downstream artifacts already exist as bounded lanes; they are not the source of truth." |
| Protocol reference artifacts | Current bounded product direction, not wet-lab execution | "Paper- or attachment-derived protocol references can be reviewable artifacts, but they are not SOP approval or lab automation." |
| Project context | UX/product direction, not canonical object ownership | "A project can frame a research question and linked papers, but paper/evidence state remains the stronger truth owner." |
| Project Memory | Backend-only raw-memory support lane, not opened API | "Project-scoped questions and decisions are a plausible future memory layer, but not a shipped project workspace surface." |
| Project/lab member access | Future production direction | "GCP-backed paper state can support approved project/lab access after real user/session/lab identity and permissions are added." |
| PPT, graph, figure, and external tool attachment | Future extension direction | "These tools should be able to attach to Lattice state instead of reprocessing raw PDFs and scattered notes." |
| User-created/shared tool ecosystem | Not yet claimed | "This is a roadmap direction, not a shipped plugin ecosystem." |
| Natural-language operation | Product direction | "Natural language should operate the workspace, while schema-backed state remains the source of truth." |

## One-Sentence Pitch

Lattice is an evidence-linked biomedical research workspace that turns a real paper into structured, reviewable research state, then serves that state through a lightweight local app with cloud-backed PDF/page storage and measurable safety gates.

## Two-Minute Story

Researchers do not only need faster summaries. They need to know where each claim came from, what evidence supports it, what is still uncertain, and whether a generated artifact can be reviewed later.

Lattice treats the paper as the center of the workflow. A PDF becomes structured state, claims, evidence, warnings, and reusable artifacts such as meeting packs and comparison views.

The user benefit is simple: a researcher should not have to reread and reconstruct the same paper every time they need a lab meeting slide, a comparison table, or a follow-up analysis.

The longer-term strategy is not to manually rebuild every possible research tool. It is to make the original paper/evidence state reliable and structured enough that new AI tools, user-created tools, and shared downstream workflows can attach to it.

For project teams, the same principle matters: shared work should start from the same source-backed paper state rather than each member rebuilding notes independently. In the production direction, GCP-backed storage can make paper state, extracted protocol references, and downstream artifacts available to approved project or lab members with explicit permissions.

For the finals demo, the important upgrade is the cloud-paper path. The installed app stays lightweight, while GCS stores the source PDF and page artifact, Firestore stores durable paper metadata, and the browser only receives a redacted public contract.

The final gate is measured: it processed a real 34-page Nature Aging paper, passed the GCS plus Firestore rehearsal, passed public redaction checks, launched the packaged app, extracted the release zip, and verified the core UI/API routes.

This is an assisted alpha demo, not a finished public production release. That boundary is a strength: the system already separates what is measured, what is ready for a controlled demo, and what remains a production gate.

## Second-Pass Existing Docs Review

The older documents do support the project/team/protocol expansion story, but only with careful boundaries.

| Theme | Evidence from existing docs | How to say it on stage | Boundary |
| --- | --- | --- | --- |
| Lab-managed cloud paper state | `docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md` says the strongest promise is uploading a paper once, processing it in a lab-managed cloud, then reading and reusing the processed page from authenticated devices. | "GCP lets the same processed paper state live beyond one laptop." | Current demo proves a controlled cloud-paper path, not broad production rollout. |
| Per-action access | The GCP roadmap defines permission-derived actions such as read page, read PDF, hydrate/download, optional AI, export, share, and delete. | "The future sharing model should be permission-derived, not simply public links." | Real identity, lab membership, device trust, audit, and retention remain production gates. |
| Project as context | Research Workspace docs define project as a visible research-question context, not an owner of every claim or artifact. | "Project context helps a team resume work around a research question." | Do not imply a heavy project-management platform. |
| Project Memory | Project Memory docs preserve project-scoped questions, judgments, decisions, uncertainties, and links as raw memory. | "A future memory layer could preserve team decisions and open questions around papers and artifacts." | Current decision gate says no Project Memory API or viewer yet. |
| Protocol references | `docs/PROTOCOL_KNOWLEDGE.md` defines protocol cards as versioned, evidence-linked, read-first reference artifacts. | "Protocols extracted from papers can become reviewable references with source links." | Not SOP approval, instrument control, scheduling, or wet-lab execution. |
| Derived bundles | `docs/ARTIFACT_BUNDLE_SPEC.md` defines downstream bundles as non-canonical, lineage-visible, reviewable artifacts. | "Meeting packs, slides, graphs, and figures should be generated as traceable bundles over paper state." | Bundles do not replace upstream paper/evidence truth. |
| Knowledge layer | `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md` keeps compiled knowledge derived, reviewable, and non-canonical. | "Lattice can compile knowledge, but promoted scientific claims still jump back to upstream evidence." | Do not pitch a generic wiki or chat-memory system. |
| Research DNA / project profile | `docs/RESEARCH_DNA.md` and `docs/MEETING_PACK.md` allow deterministic project/research profile projections in bounded cases. | "Project/research context can guide what papers are selected for an artifact." | Not broad fuzzy project search or generic semantic memory. |

Best final framing:

> We are not replacing the lab's judgment, project management, or SOP process. We are making the paper/evidence state durable enough that a project team can review the same source-backed claims, protocol references, and downstream artifacts later.

## Verified Metrics

Use only these numbers on stage unless the gate is rerun and the evidence is updated.

| Claim | Verified value | Evidence |
| --- | ---: | --- |
| Final readiness gate | `passed` | `storage/contest/google_agent_challenge_2026_06_05/final_gate_20260602T095050Z.log` |
| Gate duration | `24` seconds | started `2026-06-02T09:50:33Z`, finished `2026-06-02T09:50:57Z` |
| Demo PDF | `34` pages, `8,460,622` bytes | rehearsal JSON and page-count check |
| Demo PDF SHA256 | `5f9a0e674db49c1749717ac3502378518c81cef37c780258db317058d3124f40` | rehearsal JSON |
| Upload mode | `backend_mediated` | rehearsal JSON |
| Processing status | `ready` | rehearsal JSON |
| Public page schema | `cloud_page_artifact_public.v1` | rehearsal JSON |
| Public redaction | `passed` | rehearsal JSON |
| Firestore metadata | `cloud_papers_demo/paper_mock_000001` ready | rehearsal JSON |
| Packaged app proof | `/health`, `/ui`, cloud list, cloud search all `200` | final gate log |
| Extracted zip proof | `/health`, `/ui`, cloud list, cloud search all `200` | final gate log |
| App bundle size | about `194M` | baseline measurement |
| CLI binary size | about `95M` | baseline measurement |
| Release zip size | about `94M` | baseline measurement |
| Release zip SHA256 | `068c8977fa14b3f093f19040bd52b12cb7d5dc95af1a3dc1c356fcec929f4d22` | manifest and gate hash check |
| Goldset readiness | `8/8` ready; seed `3/3`, eval `3/3`, holdout `2/2` | release package JSON |

## Recommended Slide Structure

The final live deck should be the 7-slide main path. Keep the detailed 11-slide notes below as expansion material, rehearsal notes, or backup slides.

| Main slide | Purpose |
| --- | --- |
| 1. Personal Motivation | Make the problem human and research-grounded. |
| 2. Problem | Turn the personal pain into evidence/provenance/reuse pain. |
| 3. Solution | Explain paper-centered evidence state. |
| 4. Cloud Paper Demo | Explain what GCP added in user-facing terms. |
| 5. Measured Gate | Prove that the demo path was measured. |
| 6. Extensibility | Explain why reliable evidence state enables future tools. |
| 7. Roadmap | Name production gates and next steps honestly. |

Backup slides:

- Agentic workflow and quality gate details.
- Benchmark and goldset detail.
- Demo run order.
- Q&A and boundaries.

If the session allows only a short demo talk, collapse the detailed notes this way:

| Main slide | Pull from detailed notes |
| --- | --- |
| 1. Personal Motivation | Slide 1 |
| 2. Problem | Slides 2-3 |
| 3. Solution | Slides 4-5 |
| 4. Cloud Paper Demo | Slide 6 |
| 5. Measured Gate | Slides 7 and 9 |
| 6. Extensibility | Slide 8 |
| 7. Roadmap | Slides 10-11 |

The sections below keep the original slide numbers so older slide files and rehearsal notes remain easy to map.

### Slide 1. Personal Motivation

Headline:

> I built this from a real research workflow pain.

Say:

- As an undergraduate researcher, I saw that papers were not hard only because they were long.
- The hard part was preserving evidence, uncertainty, and reusable context after the first read.
- Lab meetings, presentations, tables, and figures often forced the same paper to be reprocessed again.

Show:

- A simple pain flow: `PDF -> notes -> slides -> tables -> re-reading`
- Keep this slide human and short. Move into the product problem within 30 seconds.
- Concrete example: "This claim came from page X / figure Y, but I cannot find it again later."

### Slide 2. Lattice

Headline:

> Evidence-linked biomedical research workspace

Say:

- Lattice is not just a paper summarizer.
- It turns papers into reviewable research state and reusable artifacts.
- The finals demo focuses on a measured cloud-paper path for that workflow.

Show:

- Product name
- One UI screenshot or product surface
- One short flow: `PDF -> Evidence -> Review -> Artifacts`

### Slide 3. Problem

Headline:

> Paper summaries are fast, but research evidence gets lost.

Say:

- Researchers need claim location, evidence, uncertainty, and reusable outputs.
- AI drafts are useful, but they should not be silently promoted into trusted research state.
- The hard problem is not only generation; it is preserving reviewability.

Reuse from prelim:

- Problem framing from `docs/contest/prelim_submission_pack_2026-05-23.md`

### Slide 4. Solution

Headline:

> Lattice keeps the paper, evidence, and artifacts connected.

Say:

- Paper-centered state
- Claim/evidence/warning separation
- Reviewable downstream artifacts
- Local-first runtime with a bounded cloud storage path

Show:

```text
Paper import -> structured state -> claims/evidence -> review -> meeting/comparison/chart artifacts
```

### Slide 5. Agentic Workflow

Headline:

> The agent loop is gated, not blind.

Say:

- The workflow moves papers through fetch, analysis, validation, and indexing.
- Gates distinguish approved, pending-review, failed, and unsupported states.
- Evidence and schema checks decide what can move forward.

Use existing slide:

- `presentation_slides_3pages.html`, especially the state machine and quality gate slides.

Boundary:

- Do not present old architecture slides as the final demo evidence. Use them as explanatory support only.

### Slide 6. Cloud Paper Demo

Headline:

> The local app stays light; GCS and Firestore hold the cloud paper state.

Say:

- User value: the same paper state can be preserved beyond one local machine while the app remains lightweight.
- Future project value: approved team members should be able to reuse the same paper state, extracted protocol references, and downstream artifacts instead of rebuilding them separately.
- Project value should be framed as shared research context: linked papers, open review work, protocol references, and artifact drafts around a research question.
- Permission value should be framed as per-action access: read page, read PDF, hydrate/download, export, share, delete, and optional AI should not all mean the same permission.
- GCS stores the source PDF and page artifact.
- Firestore stores durable paper metadata.
- FastAPI returns a redacted public page/search contract to the UI.
- The browser does not directly access GCS.

Use the measured number:

- Real PDF: `34` pages, `8,460,622` bytes, checksum-tracked.

### Slide 7. Measured Gate

Headline:

> The final demo gate passed in 24 seconds.

Say:

- The gate ran cost preflight, real PDF rehearsal, manifest/hash check, packaged app proof, and extracted zip proof.
- The packaged app and extracted zip both returned `200` for `/health`, `/ui`, cloud list, and cloud search.
- Public redaction checks passed.

Show:

| Step | Result |
| --- | --- |
| Cost preflight | passed |
| Real PDF GCS + Firestore rehearsal | passed |
| Manifest/hash check | passed |
| Packaged app proof | all `200` |
| Extracted zip proof | all `200` |

### Slide 8. Why This Can Expand

Headline:

> We are building the reliable research state that other tools can use.

Say:

- AI tools change quickly, and better generation tools appear constantly.
- The durable value is not one specific PPT or graph generator.
- The durable value is the paper/evidence state that those tools can safely consume.
- With structured evidence state, downstream tools can make meeting packs, slides, graphs, figure explanations, and comparison tables without starting from raw PDFs again.
- A project team can also reuse the same evidence-linked protocol references or meeting artifacts as reviewable bundles.
- Compiled knowledge and project memory should help retrieval and continuity, but they should not replace source-backed evidence.

Show:

| Now | Direction | Future |
| --- | --- | --- |
| measured cloud-paper state | evidence-linked downstream artifacts and protocol references | project/lab sharing and user/shared tools that attach to Lattice state |

Boundary:

- Say this is the extension direction.
- Do not claim a complete plugin ecosystem or automatic all-in-one research platform is already shipped.

### Slide 9. Benchmark And Quality

Headline:

> The quality story is measured honestly.

Say:

- There is a fixed paper-understanding goldset with `8/8` ready items.
- Splits are seed `3/3`, eval `3/3`, holdout `2/2`.
- Evidence-grounding scorecards exist, but current quality is a repair loop, not a solved accuracy claim.

Use:

- The goldset readiness number.
- The caveat from `docs/contest/Google_Agent_Challenge_Metrics_Benchmark_Brief_2026-06-05.md`.

Do not say:

- "Paper understanding accuracy is solved."
- "The benchmark proves production-grade scientific correctness."

### Slide 10. Demo Run

Headline:

> Live path: search, open, inspect redacted cloud paper state.

Say:

- Search query: `processed page text`
- Expected controlled paper id: `paper_mock_000001`
- Open the cloud paper result.
- Show the page view and explain that browser-visible payloads stay redacted.

Fallback:

```bash
export PAPERPIPE_CLOUD_METADATA_STORE="memory"
export PAPERPIPE_CLOUD_ADAPTER="mock"
```

Fallback sentence:

> The live GCP path is documented and rehearsed, but for stage reliability I am switching to the mock-backed UI contract. The production direction remains GCS + Firestore + Cloud Run worker.

### Slide 11. Roadmap

Headline:

> From assisted alpha to production-grade research infrastructure.

Say:

- Add production auth and lab/device identity.
- Deploy and smoke-test Cloud Run plus Cloud Tasks worker path.
- Add signing, notarization, stapling, and Gatekeeper acceptance for public macOS distribution.
- Continue evidence-grounding repair loop until quality gates are strong enough for accuracy claims.
- Add project/lab-scoped access so approved team members can view shared paper state, extracted protocol references, and downstream artifacts.
- Keep project scope lightweight at first: research question, linked papers, pending review, blocked work, and recent artifacts.
- Reopen Project Memory only after there is a clear product decision for project-scoped API/viewer access.
- Make downstream tool attachment easier: presentation, graph, figure, and comparison tools should consume Lattice state instead of reprocessing raw notes.
- Keep natural language as an interface over structured state, not as the source of truth.

## Demo Run Order

Before going on stage:

```bash
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" \
  scripts/run_gcp_cloud_paper_demo_readiness_gate.sh
```

Expected:

- `status=passed`
- release zip SHA256 is `068c8977fa14b3f093f19040bd52b12cb7d5dc95af1a3dc1c356fcec929f4d22`
- packaged and extracted proof endpoints all return `200`

Launch:

```bash
PAPERPIPE_INSTALL_LAYOUT=1 \
PAPERPIPE_CONFIG_PATH="$PWD/config.example.yaml" \
LATTICE_API_KEY="demo-secret" \
PAPERPIPE_CLOUD_ADAPTER="gcs" \
PAPERPIPE_CLOUD_METADATA_STORE="firestore" \
PAPERPIPE_GCP_PROJECT_ID="knudc-a01068202087" \
PAPERPIPE_GCS_RAW_PDF_BUCKET="paperpipe-raw-pdf-dev-knudc-a01068202087" \
PAPERPIPE_GCS_PAGE_ARTIFACT_BUCKET="paperpipe-page-artifacts-dev-knudc-a01068202087" \
PAPERPIPE_FIRESTORE_CLOUD_PAPER_COLLECTION="cloud_papers_demo" \
./dist/Lattice.app/Contents/MacOS/Lattice start --host 127.0.0.1 --port 8046
```

Open:

```text
http://127.0.0.1:8046/ui
```

Demo:

1. Open cloud paper list/search.
2. Search `processed page text`.
3. Open `paper_mock_000001`.
4. Show page artifact view.
5. Mention redaction boundary.

## Say / Do Not Say

### Say

- "The installed app is intentionally light; the cloud path stores PDFs and returns reusable page artifacts."
- "The browser does not directly access GCS. The backend returns a redacted public contract."
- "The final scripted gate passed in 24 seconds on the verified demo artifact."
- "This is an assisted alpha demo with measured readiness gates."
- "Cloud Run and Cloud Tasks are the accepted production worker direction, not claimed as live in this stage demo."
- "The benchmark work shows a fixed measurement system and repair loop."
- "We are not trying to hand-build every possible research output tool; we are building the reliable paper/evidence state those tools need."
- "Natural language is the way the researcher can operate the workspace, but schema-backed state remains the source of truth."
- "GCP makes the project/lab sharing direction more realistic, but production sharing still needs real identity, permissions, and retention policy."
- "Protocol references can be extracted and reviewed as bounded artifacts; they are not SOP approval or wet-lab automation."
- "Project is a research context around papers and artifacts, not the canonical owner of every claim."
- "Project Memory is a future/support lane today; it is not an opened API or shipped collaboration surface."

### Do Not Say

- "This is production SSO."
- "Cloud Run and Cloud Tasks are already powering the demo."
- "The browser directly reads from GCS."
- "This zip is a notarized public installer."
- "Paper-understanding accuracy is solved."
- "The cloud page text is canonical scientific evidence for every downstream artifact."
- "All research work is already fully automated inside Lattice."
- "Any user-created tool can already be plugged in without additional integration work."
- "Project teams can already use this as production-grade shared lab infrastructure."
- "Extracted protocols are automatically approved lab SOPs."
- "Project Memory is already the source of truth for team decisions."
- "Projects own every paper, claim, protocol, and artifact in the runtime."

## Expected Judge Questions

### What makes this agentic?

Answer:

The system is not a single prompt. It is a gated workflow that moves papers through fetch, analysis, validation, review state, and artifact generation. The agentic part is the controlled progression from paper input to structured evidence and reusable outputs, with gates preventing unsupported outputs from being silently promoted.

### Where does GCP fit?

Answer:

In the finals demo, GCP is used for the cloud-paper storage path: GCS for raw PDFs and page artifacts, and Firestore for durable paper metadata. The UI receives redacted FastAPI responses rather than direct GCS access.

### Is this production?

Answer:

No. It is an assisted alpha demo with measured gates. Production requires first-class auth, lab/device identity, Cloud Run plus Cloud Tasks worker deployment, retention/delete semantics, and public macOS signing/notarization.

### Why is the benchmark story still useful if some quality metrics are weak?

Answer:

Because the benchmark separates measurement from claims. The current evidence proves we have fixed goldset splits and scorecard outputs, and it shows exactly where repair is needed. That is safer and more useful than claiming unsupported accuracy.

### Why local app plus cloud storage?

Answer:

Researchers need a fast local workspace and durable, shareable paper state. The local app keeps the research UI lightweight; cloud storage handles PDF/page artifacts and cross-device metadata once production auth is added.

### Can this support project or lab-team sharing?

Answer:

That is the production direction, not the current stage claim. GCP-backed paper state makes this direction realistic because source PDFs, page artifacts, and metadata can live outside one laptop. But actual project/lab sharing requires first-class user/session/lab identity, role-based permissions, device trust, retention/delete policy, and audit durability. The safe claim is that the current demo proves the cloud-paper foundation; team sharing is the next production layer.

### How would project sharing work without becoming a generic workspace?

Answer:

The current product boundary treats project as context, not the canonical owner of all research truth. A project can carry a research question, linked papers, pending review state, blocked work, and recent artifacts. The claim/evidence truth still lives in paper-centered structured state and bounded artifacts. That means the project helps a team resume and coordinate work, while source-backed evidence remains reopenable.

### Did you already implement Project Memory?

Answer:

There is a backend-only file-store slice and a decision note for Project Memory, but the API and viewer are intentionally not opened yet. It is useful as a future support layer for project-scoped questions, decisions, uncertainties, and links across papers, protocol cards, meeting packs, and Research DNA assets. It should not be described as a shipped collaboration surface or as the source of scientific truth.

### What about protocols extracted from papers?

Answer:

Protocol references are a good downstream use case for Lattice state. A paper- or attachment-derived protocol reference can preserve source links, versions, and review state so project members can inspect it later. The boundary is important: this is a reviewable protocol-reference artifact, not automatic SOP approval, instrument control, scheduling, or wet-lab execution.

### Can the same project team view protocol references and meeting artifacts?

Answer:

That is the intended production direction once identity and permissions are implemented. The safe model is that approved members can view shared paper state and derived artifacts with lineage, warning, and review status preserved. Meeting packs, protocol references, slide drafts, graphs, and figures should be treated as derived bundles over upstream evidence, not as separate truth stores.

### What is the source of truth?

Answer:

The source of truth is schema-backed paper/job/artifact state, not the slide deck, not a chat transcript, and not a downstream generated pack. The presentation, meeting packs, and cloud page views are useful outputs or projections, but they stay subordinate to saved state, evidence lineage, and the measured gate artifacts.

### Is this a chatbot for papers?

Answer:

No. Natural language can operate or explain the workspace, but Lattice is not chat-first. The product identity is paper-first: import a paper, preserve structured state, keep evidence and uncertainty visible, and generate reviewable downstream artifacts.

### What could cost money in the demo?

Answer:

Billing is enabled, so the cloud path is real and can create small real charges. The measured demo uses controlled GCS buckets and a Firestore collection for one primary PDF/page path. Cloud Run and Cloud Tasks were deliberately not enabled in the latest gate, and the fallback is memory plus mock storage.

### Why should judges trust the numbers?

Answer:

The numbers come from the final gate log, rehearsal JSON, release manifest/hash check, and goldset release package. They are reopenable artifacts, not hand-entered slide claims. If the package is rebuilt, the rule is to rerun the gate and update the evidence before changing the slide.

### Are you trying to build every downstream tool yourselves?

Answer:

No. The strategy is to make the upstream paper/evidence state reliable, structured, and reusable. Some downstream tools can be built directly in Lattice, such as meeting packs or comparison artifacts. Others may come from future user-created or shared tools. The important part is that those tools should attach to evidence-linked state rather than starting from scattered PDFs, notes, and slides.

### How does natural language fit into this?

Answer:

Natural language is the operating interface. A researcher should be able to ask for a meeting pack, presentation outline, figure-focused explanation, or comparison table in ordinary language. But the answer should be generated from structured paper state and evidence lineage, not from an ungrounded chat transcript.

## Existing Material Review

| Existing material | Keep / update | How to use |
| --- | --- | --- |
| `docs/contest/prelim_submission_pack_2026-05-23.md` | Keep the product story | Use problem, solution, and workflow language. Replace old submission logistics with finals evidence. |
| `presentation_slide.html` | Reference only | Single architecture slide; too narrow for finals. |
| `presentation_slides_2pages.html` | Reference only | Good state-machine and validation explanation. |
| `presentation_slides_3pages.html` | Best existing architecture supplement | Use as backup architecture appendix, not the main finals deck. |
| `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md` | Use live | Operator sheet for commands and fallback. |
| `docs/contest/Google_Agent_Challenge_Metrics_Benchmark_Brief_2026-06-05.md` | Use live | Source for stage-safe metrics and benchmark caveats. |
| `storage/contest/google_agent_challenge_2026_06_05/slide_metrics_table_20260602T095050Z.md` | Use live | Copy into metrics slide. |

## Additional Material Worth Pulling In

| Source | Pull into finals? | What to add |
| --- | --- | --- |
| `docs/Product_Positioning_Principles.md` | Yes | Use the product principle that natural language is interface, while schema-backed structured state is source of truth. This strengthens the trust story. |
| `docs/PaperPipe_Minimum_Operating_Principles.md` | Yes | Use the boundary that raw memory, logs, compiled artifacts, and presentation outputs are support layers, not canonical truth. |
| `docs/reports/First_Product_Demo_Script_3min_2026-03-27.md` | Yes, selectively | Reuse the spoken line: paper -> structured evidence state -> downstream artifact, without losing provenance. Replace the older local-only route with the cloud-paper route. |
| `docs/reports/First_Product_Demo_FAQ_2026-03-27.md` | Yes | Add Q&A for source of truth, chatbot boundary, v1 user, and local-first value. |
| `docs/reports/First_Product_Demo_Runbook_2026-03-27.md` | Reference only | Good fallback discipline: do not invent a broader story if one surface fails. The current live runbook is the contest operator sheet. |
| `docs/TALK_PACK_QUALITY_BENCHMARK.md` | Yes | Add final slide-quality rules: time fit, evidence traceability, slide-specific numbers, presenter usability, and Q&A realism. |
| `docs/TALK_PACK_STYLE_GUIDE.md` | Yes | Add hard rules: verified numbers only, no overclaiming, title-content alignment, and one primary message per slide. |
| `docs/PRESENTATION_REVIEW_SCHEMA.md` | Reference only | Useful future structure for presenter-view/evaluator-view review, but do not introduce a new runtime artifact for the finals. |
| `docs/Personal_Assistant_Integration_Review_Packet_2026-05-10.md` | Small Q&A only | Use the boundary that assistants or external interfaces should be thin, non-canonical projections over PaperPipe truth. Do not pitch assistant integration as part of the demo. |
| `docs/GCP_CLOUD_PAPER_DEMO_COST_GUARDRAILS_2026-06-01.md` | Yes | Use the cost answer: billing is enabled, expected demo usage is tiny but not guaranteed zero-cost, and Cloud Run/Tasks stay disabled unless intentionally smoke-tested. |
| `docs/GCP_CLOUD_PAPER_PRODUCTION_DECISION_GATE_2026-06-01.md` | Yes | Use the production boundary and roadmap gates: auth, Cloud Run worker, Cloud Tasks dispatch, retention/delete, and durable audit. |
| `docs/PROTOCOL_KNOWLEDGE.md` | Yes, with boundary | Use protocol references as a downstream extension example. Do not claim SOP approval, protocol execution, or lab automation. |
| `docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md` | Yes, with boundary | Use the lab-managed cloud promise and permission-derived action model. Do not claim production multi-device rollout. |
| `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md` | Yes | Use derived/reviewable/non-canonical language for compiled knowledge and future project continuity. |
| `docs/ARTIFACT_BUNDLE_SPEC.md` | Yes | Use the bundle contract to explain why PPT, graph, figure, and meeting outputs should remain lineage-visible downstream artifacts. |
| `docs/RESEARCH_DNA.md` | Small Q&A only | Use deterministic project/research profile projection as a bounded context-selection example. Do not pitch broad semantic project memory. |
| `docs/MEETING_PACK.md` | Yes | Use meeting pack as proof that downstream artifacts can be JSON/Markdown bundles with evidence and regeneration boundaries. |
| `docs/reports/Research_Workspace_Core_Structure_Decisions_2026-04-01.md` | Yes | Use the "project as context, paper workspace as execution center" boundary. |
| `docs/reports/Research_Workspace_Project_Minimum_Chrome_2026-04-01.md` | Yes | Use the lightweight project chrome concept: research question, linked papers, review/blocked counts, recent artifact. |
| `docs/reports/Project_Memory_API_Gate_2026-03-23.md` | Q&A boundary only | Mention Project Memory as a backend-only/future support lane. Do not describe it as an opened product surface. |
| `docs/PaperPipe_v3_Master_Spec_Final_Blueprint_v1_2.md` | No | It is a retired compatibility stub and should not be cited for finals claims. |

## Final Talk Spine

Use this order if the deck needs to be rewritten quickly:

1. I saw this pain in real research workflows: papers get reread because evidence and downstream context are not preserved.
2. Lattice solves the first layer: paper -> structured evidence state -> reviewable downstream artifacts.
3. The system is agentic because it uses gated progression, not blind generation.
4. GCP extends the workflow: source PDF/page artifact/metadata can live in a measured cloud-backed path.
5. The demo is measured: 34-page paper, 24-second gate, redaction passed, packaged and extracted app proof all `200`.
6. The future is extensibility: project/lab sharing, protocol references, PPT, graph, figure, and comparison tools can attach to reliable Lattice state.
7. The boundary is honest: alpha demo, not production SSO, not public notarized installer, not solved scientific accuracy, not a shipped project-memory collaboration platform.

## Final Slide Quality Rules

Borrowed from the talk-pack quality/style docs:

- Every number on a slide must trace to the final gate summary, rehearsal JSON, manifest/hash check, or release package JSON.
- Each slide should have one primary message.
- Slide titles must not overstate what the body evidence supports.
- Put quantitative evidence only on slides that actually use it.
- Keep the main path time-fit; move extra architecture details to backup.
- Prepare at least the high-risk objections, not only easy clarifications.
- Treat polished slides as presentation outputs, not truth owners.

## Final Claim Checklist

Before presenting, confirm:

- [ ] Final gate still passes if rerun after any rebuild.
- [ ] Release zip SHA is still `068c8977fa14b3f093f19040bd52b12cb7d5dc95af1a3dc1c356fcec929f4d22`, or all docs are updated to a new gate summary.
- [ ] Demo PDF still matches SHA `5f9a0e674db49c1749717ac3502378518c81cef37c780258db317058d3124f40`.
- [ ] No slide says production SSO.
- [ ] No slide says Cloud Run/Cloud Tasks are live.
- [ ] No slide says public notarized installer.
- [ ] No slide says benchmark accuracy is solved.
- [ ] No slide uses a number that is not traceable to the final gate, rehearsal JSON, manifest, or goldset release package.
- [ ] Every slide has one primary message.
- [ ] Source-of-truth language stays schema-backed state first, downstream artifacts second.
- [ ] Cost language says small controlled usage, not zero-cost guarantee.
- [ ] Expansion language says future direction, not already-shipped plugin ecosystem.
- [ ] Natural-language framing says interface, not source of truth.
- [ ] Project/lab sharing language says production direction, not current production-grade collaboration.
- [ ] Protocol language says reviewable reference artifact, not approved SOP or lab automation.
- [ ] Fallback env pair is memorized.

## PR-Sized Follow-Ups

1. Add `--json-out PATH` and step-level timing to `scripts/run_gcp_cloud_paper_demo_readiness_gate.sh`.
2. Convert this packet into final slide copy with one visual per slide.
3. Run one last gate on June 5 before presentation and update only the evidence timestamp/hash fields if the package changes.
