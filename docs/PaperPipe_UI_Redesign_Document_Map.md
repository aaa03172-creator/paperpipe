# PaperPipe UI Redesign Document Map

Status: Proposed document map
Date: 2026-05-10
Owner: Frontend/product maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Operating note: `docs/PaperPipe_Minimum_Operating_Principles.md`

## 1. Executive Summary

The UI redesign documentation now has five working layers:

1. Product identity
2. Page architecture
3. Extracted data workflow
4. UI grammar
5. Implementation plan

This document is the entry point for reading those layers in the right order.

Current recommendation:
- proceed with a reference-informed redesign
- keep it evidence/workflow-led, not visual-refresh-led
- start implementation with `Paper Detail` only after the UI grammar and current UI audit exist, unless the audit identifies a safer first route
- do not introduce a new runtime dependency, generic graph database, broad approval system, or chat-first shell

## 2. Document Roles

| Document | Role | Owns | Does not own |
| --- | --- | --- | --- |
| `docs/PaperPipe_Design_Identity.md` | product identity | what PaperPipe should feel like; trust rules; visual personality; state language | route-level implementation scope |
| `docs/PaperPipe_Page_Architecture.md` | page structure | page families, route intent, required content, important UI elements, action hierarchy | low-level schema or data extraction contracts |
| `docs/PaperPipe_Extracted_Data_Workflow_Map.md` | extracted-data reuse | source -> extraction -> evidence -> artifact relationship rules; duplicate-use and stale-impact rules | canonical truth store or graph database |
| `docs/PaperPipe_UI_GRAMMAR.md` | implementation-facing UI grammar | layout zones, visual state system, action hierarchy, icons, color, motion, relationship summaries, mobile ordering, banned patterns | route implementation by itself |
| `docs/Reference_Driven_Redesign_Plan_2026-05-10.md` | program plan | phases, deliverables, tooling map, risk register, verification approach | product identity or page ownership by itself |
| `docs/ui_references.md` | reference-research policy | Lazyweb/reference usage boundary and artifact format | product requirements |
| `docs/reports/UI_Reference_Research_Lazyweb_Synthesis_2026-05-10.md` | reference synthesis | what reference research suggested and rejected | implementation contract |
| `docs/API_CHAT_CONTRACT.md` | chat boundary | current `/api/chat` stub-only status and future answer-generation constraints | general UI redesign |

## 3. Reading Order

Read in this order before implementation:

1. `docs/PaperPipe_Design_Identity.md`
2. `docs/PaperPipe_Page_Architecture.md`
3. `docs/PaperPipe_Extracted_Data_Workflow_Map.md`
4. `docs/PaperPipe_UI_GRAMMAR.md`
5. `docs/Reference_Driven_Redesign_Plan_2026-05-10.md`
6. `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`
7. `docs/UX_REVIEW_REPORT_paper-detail-right-rail.md`
8. Code for the target route/component

For chat or provider settings work, also read:
- `docs/API_CHAT_CONTRACT.md`
- `docs/runtime_security_env.md`

For reference-tool-assisted UI work, also read:
- `docs/ui_references.md`
- the relevant reference synthesis or pattern report

## 4. Current Decisions

Adopted:
- PaperPipe identity: local-first biomedical evidence workspace
- first implementation target: bounded `/papers/:slug` right-rail and mobile-sheet micro-spike
- UI grammar: source/evidence/state/reuse/action rules should govern route spikes before visual polish
- current audit: first spike should be Paper Detail right rail and mobile sheet ordering; fallback is Paper Notes List row state/action grammar if route risk is too high
- page families: Home/Recovery, Paper Library, Paper Detail, Evidence Workbench, Figure/Table Evidence, Artifact Detail, Research Memory/DNA, Runtime/Diagnostics, Settings/Local Secrets, Evidence-Aware Assistant
- visual style: mostly neutral, dark-first, evidence-forward, restrained color
- relationship pattern: `used by`, `derived from`, `stale impact`, and source chain summaries before any graph UI
- Settings direction: useful, but secrets must remain backend/server-side or OS-keychain-style; frontend shows redacted status only
- Lazyweb/reference tools: developer-local research tools only

Rejected or deferred:
- full UI rewrite
- visual-only redesign
- Lazyweb runtime dependency
- graph database or universal relation registry as a current requirement
- broad approval/promote/final truth language
- chat-first product shell
- browser-owned API keys
- heavy animation or visualization dependencies without explicit approval
- color per artifact family, relationship type, marker type, or graph edge

## 5. Overall Review

### Quick Review

- Choice count: the docs now point to one primary implementation path rather than many redesign branches.
- Benefit: the product is framed around evidence, provenance, state, and safe next action.
- Next action: the next concrete step should be the bounded Paper Detail right-rail and mobile-sheet micro-spike.
- Feedback: save/review/export/regenerate states are documented as visible UI events, not hidden background changes.
- Ethics: generated, extracted, assistant-produced, and downstream artifact content remain weaker than upstream evidence-linked state.

### Full Review

P0:
- Keep `docs/Lattice_v3_Master_Spec.md` and `docs/PaperPipe_Minimum_Operating_Principles.md` above all redesign docs.
- Do not let any UI redesign doc create a new runtime truth store.
- Do not add `approved`, `verified`, `final`, graph truth, or annotation states without schema/API ownership.
- Do not store provider credentials in the browser.
- Do not make reference outputs or generated images product requirements.

P1:
- Keep `docs/PaperPipe_UI_GRAMMAR.md` as the shared route-implementation grammar and update it only when a route audit finds a concrete gap.
- Use `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md` to choose and constrain the first route spike.
- Keep Paper Detail as the likely first spike unless the audit finds a safer first route.
- Add route-level `used by` and `stale impact` summaries before building graph visualization.
- Keep color secondary to label, icon, position, density, and grouping.

P2:
- Defer typographic polish, card/elevation tuning, and motion refinement until UI grammar is stable.
- Defer cross-paper Research DNA visualization until data-layer boundaries are explicit.
- Defer assistant UI beyond boundary states until `/api/chat` changes from stub-only.

## 6. BMAP Diagnosis

Motivation:
- high, because the current UI has grown beyond its original paper-reading assumptions.

Ability:
- improved by splitting the work into identity, page architecture, extracted-data workflow, audit, grammar, and one route spike.

Prompt:
- the next prompt for implementation should cite a route, a page-family section, the extracted-data rule if relevant, and the matching UX report.

## 7. B.I.A.S Diagnosis

Block:
- risk is documentation sprawl. This map reduces it by giving each document one role.

Interpret:
- the main interpretation rule is stable: source -> evidence -> review -> artifact.

Act:
- the next action should be the Paper Detail right-rail and mobile-sheet micro-spike, not broad UI implementation.

Store:
- the durable memory should be that PaperPipe is careful, evidence-first, local-first, and provenance-preserving.

## 8. Peak-End Notes

Peak:
- user can open a claim, figure, table, or artifact and see source, state, provenance, reuse, and next safe action.

Pit:
- a polished screen, generated artifact, assistant answer, or relation graph appears more certain than upstream evidence.

Transition:
- Home -> Paper Library -> Paper Detail -> Workbench -> Artifact Detail should preserve paper identity, evidence state, and source/ref context.

End:
- export or handoff should end with provenance summary, unresolved warnings, and clear draft/reuse status.

## 9. Ethics Check

Regret:
- reduced when the UI prevents over-trust in generated or repeated extracted content.

Black Mirror:
- risk appears if a weak extraction spreads across artifacts and gains authority through repetition or polish.

In Real-Life:
- PaperPipe should behave like a careful research collaborator: clear about what it knows, where it came from, and what still needs review.

## 10. Open Gaps

| Gap | Owner document | Done when | Blocks broad UI implementation? |
| --- | --- | --- | --- |
| Shared UI grammar | `docs/PaperPipe_UI_GRAMMAR.md` | initial grammar exists and route-specific spikes cite the applicable sections | Partially; broad implementation still needs the audit |
| Current UI reality audit v2 | `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md` | current routes are scored against identity, page architecture, extracted-data workflow, and visual-state rules | Completed for first-spike selection |
| Route-by-route architecture audit | `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md` | each current route has a first-scan question, design debt score, and PR-sized recommendation | Completed at audit level; route-specific reports still required |
| Extracted-data visibility audit | `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md` | current route-level visibility of source/evidence/reuse patterns is summarized | Partially; exact `evidence_refs`, `source_items`, `review_artifacts`, and `artifact_brief` checks still need route-specific data review |
| Settings secret-storage contract | Future settings/security contract | backend-owned storage, redaction, scan coverage, and browser boundary are specified | Yes for provider key UI |
| Mobile sheet ordering | `docs/PaperPipe_UI_GRAMMAR.md` | Paper Detail and Artifact Detail mobile state/action order mirrors desktop trust hierarchy | Yes for mobile UI changes |
| Visual regression plan | `docs/UX_REVIEW_REPORT_paper-detail-right-rail.md` | target checks for Paper Detail route-local layout changes are named before the first route spike | Completed at route-report level; exact tests chosen during implementation |

## 11. Next PR-Sized Actions

1. Implement the `/papers/:slug` micro-spike.
   - reorder Paper Detail right rail and mobile sheet around source/evidence/personal/context/guarded/support sequence.

2. Verify the route-local change.
   - run frontend build and targeted Paper Detail tests if existing coverage maps to the changed surface.

3. Keep route-specific UI changes bounded to the grammar.
   - cite `docs/PaperPipe_UI_GRAMMAR.md`, the route UX report, and the relevant data layer before implementation.

## 12. Implementation Gate

Do not begin broad UI implementation until:

- UI grammar exists
- current UI audit exists
- target route has a matching UX review report
- state/provenance layer is identified
- no new runtime dependency is needed, or explicit approval exists
- color/motion/icon changes have non-color and reduced-motion fallbacks
- any reference-tool use is summarized without private PaperPipe data
