# PaperPipe Project Knowhow

Status: dated report / project knowhow synthesis
Date: 2026-06-07
Owner: Runtime/product maintainers
Layer: compiled knowledge
Canonical status: non-canonical

Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/reports/Current_Docs_Posture_2026-04-17.md`
- `AGENTS.md`

## Purpose

이 문서는 PaperPipe/Lattice를 진행하면서 반복해서 배운 실전 노하우를 한곳에 모은다.

목표는 새 architecture spec을 만드는 것이 아니다. 목표는 다음 작업자가 PR, 리뷰, 문서 정리, 외부 도구 검토, cloud/local 경계 작업을 시작할 때 같은 판단을 다시 발명하지 않게 하는 것이다.

This note is:
- a dated synthesis of project knowhow
- a reviewable memory aid
- subordinate to the canonical docs above

This note is not:
- a runtime spec
- a DB or API contract
- permission to change product scope
- a replacement for current schema-backed state

## Short Version

PaperPipe가 잘 굴러갈 때의 공통 패턴은 이렇다.

1. 먼저 layer를 분류한다.
2. canonical truth를 넓히기 전에 schema, route, reader, writer, doc owner를 확인한다.
3. 기능을 크게 만들기보다 PR-sized contract를 하나 정한다.
4. generated output은 기본적으로 draft-like 또는 non-canonical로 둔다.
5. 사용자에게 보이는 biomedical content는 source/evidence lineage를 잃지 않게 한다.
6. 외부 AI, cloud, skill, UI component는 product fit과 payload boundary를 통과해야 한다.
7. dirty worktree에서는 좋은 코드보다 lane discipline이 먼저다.
8. viewer/display assist는 판단을 돕되 판단을 소유하지 않는다.
9. eval, quality gate, trace, readiness는 review signal이지 truth store가 아니다.
10. 운영/배포 claim은 personal-runtime 현실을 넘어 과장하지 않는다.

## 1. Product Boundary Knowhow

### What worked

- Product identity를 "paper-first, local-first, job/run/artifact-first, single-operator-first, evidence-linked, human-reviewable"로 짧게 유지한 것이 흔들림을 줄였다.
- 새로운 아이디어를 곧바로 top-level platform concept로 승격하지 않고, bounded artifact lane으로 먼저 다루는 방식이 안전했다.
- `Research DNA`, `Meeting Pack`, `Chart Pack`, `Image Evidence`, `Method Comparison` 같은 lane은 각각 real feature이지만, 전체 제품 정체성을 대체하지 않는다.

### Working habit

새 기능을 제안하거나 구현하기 전에 먼저 물어본다.

- 이것은 paper, job/run, artifact 중 어디에 붙는가?
- 이것이 source, canonical state, derived artifact, review artifact 중 무엇인가?
- 이것이 사용자의 trust를 높이는가, 아니면 polished output만 늘리는가?
- 지금 main UI에 노출해야 하는가, 아니면 API/CLI/operator lane으로 충분한가?

### Failure pattern

가장 위험한 흐름은 "좋아 보이는 기능"이 product boundary를 몰래 바꾸는 것이다. 예를 들어 cloud page artifact, project memory, external AI trace, compiled wiki가 편해 보인다는 이유만으로 canonical truth처럼 행동하면 이후 reader, export, review, API contract가 동시에 흐려진다.

## 2. Layer Taxonomy Knowhow

Layer 분류는 PaperPipe의 가장 중요한 방어선이다.

Default classification:
- Raw source: PDF, source page image, original external input.
- Raw memory: logs, traces, local working files, backend-only memory, task notes.
- Compiled knowledge: derived synthesis, wiki-like notes, fit reviews, project summaries.
- Canonical structured state: schema-backed runtime truth.
- Review/gate artifact: eval sidecar, acceptance note, readiness gate, correction log.
- User-facing artifact/export: Meeting Pack, chart bundle, markdown export, slide-ready output.

Practical rule:
- ambiguous하면 non-canonical로 둔다.
- canonical로 만들려면 schema, storage, API, readers, writers, docs, migration/backfill impact를 같이 본다.
- review/gate artifact는 trust signal이지 truth store가 아니다.

Good labels that reduced confusion:
- `derived_noncanonical`
- `review_pending`
- `background`
- `draft`
- `canonical_status=non_canonical`
- `payload_class`
- `source_pdf_sha256`
- stable page/source locators

## 3. API And Schema Knowhow

### What worked

- Core behavior를 FastAPI route 뒤에 두는 방식이 CLI-only drift를 줄였다.
- Pydantic schemas under `src/schemas/`를 contract boundary로 삼으면 frontend, tests, docs, downstream adapters가 한 방향으로 정렬된다.
- Public DTO와 internal storage artifact를 분리하면 cloud/private refs, signed URLs, local paths가 새는 위험을 줄일 수 있다.

### Before changing contracts

Check:
- current route patterns in `backend/main.py` and nearby routers
- current API-key and same-origin `/api/*` behavior
- current schema naming/versioning style under `src/schemas/`
- existing artifact path conventions and runtime path helpers
- frontend payload consumers
- failure behavior for partial writes, stale cache, orphan records, and retries

### Smallest safe shape

좋은 first slice는 보통 다음 중 하나다.

- read-only route before mutation route
- dry-run plan before canonical write path
- adapter response before downstream lane promotion
- public redacted DTO before exposing internal artifact
- schema compatibility test before reader/writer widening

## 4. Evidence And Trust Knowhow

PaperPipe의 output quality는 "멋진 문장"보다 "무엇을 근거로 말하는지 복원 가능함"에서 나온다.

Stable habits:
- source/evidence locator를 가능한 한 오래 보존한다.
- uncertainty, missing support, conflict, weak support를 숨기지 않는다.
- generated answer, summary, chart, meeting note는 evidence-linked structured state보다 강하게 보이게 하지 않는다.
- downstream artifact는 source refs, run ids, warnings, caveats를 같이 들고 간다.

Risky shortcuts:
- cloud OCR/page text를 canonical evidence처럼 쓰기
- visual/table extraction을 confidence 없이 claim support로 쓰기
- Meeting Pack이나 slide polish가 warning보다 앞서는 UI 만들기
- raw memory나 compiled summary를 source lineage 없이 biomedical answer에 넣기

## 5. Local-First And Cloud Knowhow

Local-first는 "모든 inference가 local-only여야 한다"가 아니다. 이 프로젝트에서는 주로 ownership, recovery, inspectability, portability, and privacy boundary를 뜻한다.

Useful distinction:
- canonical state remains local or locally recoverable
- cloud backend can be source/artifact processing backend when explicitly bounded
- external inference can exist only after payload classification and minimization

Cloud lane lessons:
- GCP should act as a source/artifact backend, not a new truth layer.
- Public responses must redact bucket refs, signed URLs, service account details, private storage paths, and local paths.
- Browser-owned state must not hold provider keys, GCP credentials, or long-lived signed private URLs.
- Production auth/device enrollment is a separate gate from demo header-derived policy.
- Cloud page artifacts can support navigation and downstream candidates, but should remain below evidence-linked structured state unless a canonical promotion path is explicitly adopted.

## 6. External AI And Tooling Intake Knowhow

External tools are most useful as pattern sources, not as product destiny.

Adoptable patterns:
- evaluation traces with offline sidecars
- bounded handoff files
- manager/specialist separation for agent review
- local workspace security posture
- wiki-like compiled knowledge with immutable raw sources and lint passes
- chart/presentation quality checklists

Do not adopt by default:
- GPL or unclear-license code
- broad Claude hook/plugin assumptions
- external skills that bypass `config/skills_policy.yaml`
- generic memory/workspace shells that replace paper/job/artifact scope
- cloud trace uploads of raw papers, full notes, private logs, or canonical state
- voice cloning or passive audio capture as core runtime behavior

Best review question:

What exact reliability, UX, or verification improvement does this external tool provide that PaperPipe cannot get from a smaller local pattern?

## 7. UI And UX Knowhow

The strongest UI pattern is not more decoration. It is making state, evidence, and next action visible without overstating trust.

Useful screen grammar:
- left: navigation, search, selection
- center: reading, evidence inspection, verification work
- right: metadata, related state, references, artifact readiness

Important UX habits:
- show warnings/source lineage before polished previews
- keep dark-first `--pp-*` token system
- do not introduce a second design system casually
- do not put secrets or provider keys in browser env
- use UX review artifacts for viewer-facing changes
- one timely prompt beats many generic CTAs

Trust hierarchy to preserve:

source -> evidence -> review state -> personal memory -> downstream artifact -> guarded action

## 8. Review Knowhow

Good PaperPipe review is evidence-first and failure-mode-first.

Lead with:
- structural defects
- data integrity risks
- security leaks
- stale cache or partial write bugs
- schema/API compatibility breaks
- frontend secret exposure
- generated artifact trust overstatement

Avoid:
- broad rewrites without concrete file/line evidence
- style-only findings
- treating proposal docs as runtime authorization
- accepting Codex-assisted review suggestions without checking current code

Review output should separate:
- confirmed defects
- open questions
- test gaps
- residual risks
- optional cleanup

## 9. TDD And Verification Knowhow

TDD matters most where contracts are expensive to repair later.

Strong TDD targets:
- FastAPI route behavior
- Pydantic schemas
- DB/state transitions
- artifact writers/readers
- idempotent Obsidian markdown replacement
- parser output contracts
- auth/redaction/payload-boundary behavior
- frontend flows that expose trust, secrets, or canonical state

Verification habit:
- run the smallest relevant gate
- record what was not run and why
- for docs-only work, lint/link checks may be enough
- for UI work, build and existing Playwright coverage matter
- for API/schema work, targeted pytest is the usual minimum

Common local verification note:
- Prefer the repo's resolved verification Python path when standard local Python is broken or mismatched.
- Do not treat a bad local runner as a product regression until import health is checked.

## 10. Worktree And Lane Knowhow

The current repo often contains many unrelated dirty changes. The safest work habit is lane discipline.

Rules that keep work recoverable:
- inspect `git status` before staging, branching, or committing
- do not stage generated outputs, caches, snapshots, storage artifacts, logs, or secrets
- do not bundle docs-only governance with runtime/API/schema changes unless explicitly requested
- use one branch/worktree per PR slice when the main tree is mixed
- patch-stage if a file contains mixed unrelated edits
- keep local backup cleanup opt-in

Practical smell:

If a PR description needs "also" more than twice, the lane is probably too wide.

## 11. Documentation Knowhow

Docs work is valuable when it clarifies entrypoints and status. It is risky when it creates another source of truth.

Good docs actions:
- update reading order before rewriting historical reports
- add status/current-entrypoint notes to confusing docs
- promote durable conclusions into canonical docs only when the owner is clear
- keep dated reports as evidence or posture notes
- cite canonical parents at the top of new reports

Bad docs actions:
- using fit reviews as authorization for runtime changes
- treating `.codex/work/...` as SSOT
- archiving or moving dated reports without checking entrypoint references
- rewriting canonical specs opportunistically during implementation work

## 12. First Slice Selection Knowhow

When a goal feels too big, choose the slice with the cleanest contract boundary.

Good first slices:
- read-only visibility before mutation
- dry-run before promotion
- redacted public DTO before internal storage exposure
- adapter foundation before lane-specific behavior
- one downstream artifact family before all downstream families
- reviewer/admin-only gate before broad user-facing action
- background-only context before evidence-backed claim support

Hard fail conditions:
- a derived artifact starts behaving like canonical state
- a browser route receives secrets or private refs
- a schema shape changes without reader/writer/tests/docs awareness
- a cloud or external inference path sends unclassified payloads
- a UI preview makes warnings or evidence lineage less visible
- a mixed worktree gets staged as one broad change

## 13. Documentation Authority Knowhow

PaperPipe docs are useful because they carry status. They become dangerous when status is ignored.

Before using a doc as implementation authority, classify it:
- canonical/current
- active bounded spec
- runbook
- template
- queue/staging note
- dated report
- proposal / fit review / future seam
- historical/archive

Working order:
- `AGENTS.md` controls agent workflow.
- `docs/Lattice_v3_Master_Spec.md` and bounded active specs control runtime/product contracts.
- operating notes such as `docs/PaperPipe_Minimum_Operating_Principles.md`, `docs/inference_data_boundary.md`, and `docs/PERSONA_MODE_BOUNDARY.md` control boundaries.
- dated reports inform posture only when referenced by an entrypoint or canonical doc.

Practical lesson:
- do not delete, archive, or rewrite historical reports just because they are old.
- first update reading order or status notes.
- then promote only the durable conclusion into the right canonical owner.

## 14. Bounded Artifact Lane Knowhow

The strongest artifact lanes share the same shape:

- schema-backed bundle
- file-backed storage
- explicit source refs
- deterministic rendering or rerendering
- warnings/caution notes in the artifact
- read-first viewer
- additive acceptance/quality sidecars
- no second canonical truth store

This pattern applies across `Meeting Pack`, `Chart Pack`, `Image Evidence`, `Method Comparison`, `Protocol Knowledge`, and related handoff artifacts.

Good defaults:
- persist the original generation request when regeneration matters.
- expose `markdown_sync`, drift, stale, or regenerate availability rather than silently fixing or hiding it.
- keep quality gates visible in the viewer if operators rely on them.
- prefer deterministic selectors over fuzzy hidden search.
- surface consensus and conflict separately; do not flatten divergence into a nicer story.

Bad defaults:
- letting a downstream pack invent evidence.
- letting visual polish outrank warning state.
- letting quality gates mutate canonical state.
- treating traces, source selectors, or retrieval debug data as scientific truth.

## 15. Research DNA Knowhow

`Research DNA` works because it treats search design as a reproducible asset, not as a one-off prompt.

Stable lessons:
- keep `ResearchDNA` and executable `Profile` distinct.
- use `DRAFT -> PILOT -> LOCKED` as a bounded lifecycle, not a generic approval model for the whole repo.
- keep interview responses, query versions, runs, approvals, screening logs, and guidance snapshots append-only where possible.
- make screening recommendations advisory until a separate gate upgrades their default behavior.
- preserve reason codes and operator decisions; they are more useful than generic "AI score" explanations.

Projection lesson:
- projected profiles are compatibility snapshots, not editable truth equal to the DNA owner.
- profile writes need merge-safe and revision-aware behavior because `profiles.yaml` is an operator-facing file.

Scope lesson:
- lack of a web viewer route does not mean the lane is not real.
- current exposure can be API/CLI-first when that is more honest than forcing a premature wizard.

## 16. Evaluation And Goldset Knowhow

Eval lanes are valuable when they stay bounded and repeatable.

Useful eval pattern:
- fixed manifest
- snapshot output
- baseline compare
- explicit gate mode
- optional promotion only after intentional review

Good eval artifacts:
- `summary.json`
- `details.json`
- `acceptance_contract.json`
- `quality_gate.json`
- comparison reports
- reviewer handoff packets

Rules:
- a benchmark or goldset is only as strong as its provenance and adjudication.
- provisional goldsets should stay labeled provisional.
- baseline promotion is a decision, not a side effect of a passing run.
- metric improvements do not automatically authorize product-scope expansion.
- docs-only edits usually should not force heavyweight eval gates.

When eval changes touch shared deep-read, evidence grounding, parser output, schema, or promotion behavior, use the broader manifest/gate mode rather than a single-paper continuity check.

## 17. Runtime Ops And Security Knowhow

The current operating shape is personal-runtime and close-person beta, not shared multi-tenant SaaS.

Safe operational claims:
- FastAPI backend plus Vite/React UI.
- SQLite-backed local runtime state.
- background worker for deep-read jobs.
- local roots for logs, artifacts, reports, and support artifacts.
- app-owned state can move outside the repo checkout under install-layout mode.

Security habits:
- keep backend secrets out of `VITE_*`.
- browser UI should call same-origin `/api/*`.
- path masking is the default; raw local paths are trusted-debug only.
- readiness payloads shown to browsers should be narrowed under beta gates.
- API docs exposure should tighten under hosted beta.
- cloud credentials, signed URLs, bucket refs, service accounts, and provider keys stay out of public DTOs.

Ops habits:
- use `/health` for liveness and `/health/ready` for readiness.
- diagnose stale jobs before mutation.
- capture incident snapshots before reclaiming or requeueing.
- avoid direct SQLite edits for queue recovery.
- mutation scripts should prefer dry-run, explicit `--apply`, backup-before-apply, transaction/rollback, and summary output.

## 18. Display-Assist Knowhow

Some features are valuable precisely because they stay display-only.

Examples:
- Korean reading assist
- viewer `view=learner|builder_debug`
- section navigator
- context traces
- related-paper hints
- runtime readiness page

Rules:
- English/original text remains canonical for search, screening, evidence, and final judgment.
- display assist can improve comprehension, but it must not drive inclusion/exclusion, claim acceptance, evidence strength, or final synthesis.
- debug/view modes may change density, ordering, and helper copy, not truth policy.
- translation or local-language output should keep source field pointers, provenance, and fallback behavior.
- section navigation is a reopen aid, not a section-truth registry.

## 19. Runtime Skill Policy Knowhow

PaperPipe has two different skill worlds:

- Codex-only developer workflow helpers.
- product runtime skills exposed through PaperPipe.

Do not merge them by accident.

Developer skills may help implementation, review, diagnosis, or artifact assembly. They do not become product features by folder presence under `.codex/skills/`.

Runtime-visible skills require:
- `src/skills/`
- `config/skills_policy.yaml`
- relevant Pydantic schemas
- FastAPI/API ownership if user-facing
- sandbox, network, timeout, license, and secret policy

Good skill policy habits:
- default deny.
- local-only when possible.
- explicit network allowlists.
- no arbitrary publisher scraping.
- no copied mixed-license skill bodies without file-level license review.
- source data, canonical state, and derived markdown summaries stay separate.

## 20. Release, Demo, And Packaging Honesty

PaperPipe has repeatedly benefited from honest stage labels.

Useful distinctions:
- repo-based alpha install
- personal runtime
- close-person beta
- assisted alpha launcher
- packaged installer
- notarized public macOS release
- Windows-later or from-source-only status
- demo-ready cloud path
- production cloud path

Do not collapse those into "shipped."

Good release notes say:
- what is demo-ready
- what is partial
- what is not ready
- what verification passed
- what production gate remains
- what rollback path exists

Packaging lesson:
- a native-looking launcher can be a useful assisted-alpha artifact while still not being a notarized public app.
- public macOS claims require signing/notarization/Gatekeeper acceptance, not just a zip.
- Windows support should not be implied by cross-platform Python code alone.

## 21. Memorable Project Heuristics

- If it cannot trace back to source/evidence, it is not evidence-backed.
- If it is not schema-backed, it is not canonical runtime truth.
- If it is generated, start it as draft-like.
- If it is cloud-visible, assume redaction is required.
- If it is in the browser, assume secrets will leak unless proven otherwise.
- If it touches persisted shape, test the contract.
- If it touches UX trust, write the UX review artifact.
- If it touches external AI, classify the payload first.
- If the worktree is dirty, lane discipline is part of correctness.
- If a proposal is useful, translate it into a bounded RFC or PR-sized slice before implementation.
- If it is a trace, gate, score, or readiness badge, label what it measures and what it does not.
- If it is a display assist, keep original/canonical judgment state visible.
- If it is a demo artifact, say exactly which production gates remain.

## 22. Suggested Next PR-Sized Actions

1. Add a lightweight "project knowhow" link from the docs reading-order surface if maintainers want this report discoverable.
2. Convert the most durable heuristics into a compact checklist under the appropriate canonical operating doc.
3. Create a reusable PR review template section for layer classification, payload class, trust boundary, verification run, and residual risk.
4. Add a small "artifact lane checklist" template for new bounded artifact families.
5. Add a small "demo vs production claim" checklist to packaging/release notes.

## References Reviewed

- `AGENTS.md`
- `README.md`
- `docs/working-files.md`
- `docs/reports/README.md`
- `docs/Product_Positioning_Principles.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/README.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/inference_data_boundary.md`
- `docs/runtime_security_env.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/PERSONAL_RUNTIME_INSTALL.md`
- `docs/WEB_VIEWER.md`
- `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/Korean_Reading_Assist_Policy.md`
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`
- `docs/CHART_PACK.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/SKILLS_PACKAGING_GUIDE.md`
- `config/skills_policy.yaml`
- `docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md`
- `docs/reports/Current_Docs_Posture_2026-04-17.md`
- `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`
- `docs/reports/Paper_Access_Note_Backed_Fallback_Stage_Set_2026-04-10.md`
- `docs/GCP_CLOUD_PAPER_PAGE_ROADMAP_2026-05-30.md`
- `docs/reports/GCP_Cloud_Paper_Roadmap_Implementation_Audit_2026-06-02.md`
- `docs/reports/External_AI_Tooling_Fit_Review_2026-06-06.md`
- `docs/PaperPipe_UI_GRAMMAR.md`
