# PaperPipe Product Discussion Summary Fit Review

Status: completed fit review
Date: 2026-04-13
Lane: `pp`
Source input:
- `/Users/jangseongjin/Downloads/PaperPipe_product_discussion_summary_for_Codex.md`

Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/WEB_VIEWER.md`

## 1. Executive summary

The source summary is useful as a product-direction note.
It is not safe to treat as a current-runtime mirror.

Current repo-grounded judgment:
- keep the summary as a discussion-derived framing document
- preserve its strongest ideas about source/canonical/derived separation, provenance, and "model is not the truth store"
- do not promote its project/workspace, decision, next-action, or broad memory language into current product truth
- if any part of it is reused in repo docs, split it into:
  - current match
  - bounded next candidate
  - future-only / explicit adoption required

The main reason is simple:
- current Lattice/PaperPipe is still a local-first, paper-centered, paper/job/artifact-first runtime
- the repo does not yet approve a first-class project/workspace owner
- current repo-wide `Decision`, `Open Question`, `Next Action`, and broad chat/memory product surfaces are not active canonical runtime families

## 2. Current match

These parts of the source summary already fit the repo when phrased with current scope discipline.

| Summary theme | Repo-grounded judgment | Current anchors |
| --- | --- | --- |
| local-first biomedical research workspace | Fits when narrowed to the current `paper-first`, `single-operator-first` product shape rather than a broad project platform. | `docs/Product_Positioning_Principles.md`, `docs/Lattice_v3_Master_Spec.md`, `docs/PaperPipe_Minimum_Operating_Principles.md` |
| source data vs canonical structured state vs derived/export layers | Strong match. This is one of the clearest alignments with the current runtime. | `docs/Lattice_v3_Master_Spec.md`, `docs/PaperPipe_Minimum_Operating_Principles.md`, `docs/Product_Positioning_Principles.md` |
| models are important but are not the source of truth | Strong match. Current product trust is meant to live in schema-backed structured state plus evidence lineage, not in model outputs, prompts, memory files, or chat. | `docs/Lattice_v3_Master_Spec.md`, `docs/Product_Positioning_Principles.md`, `docs/API_CHAT_CONTRACT.md` |
| wiki / annotation / retrieval / workbench are support or explanatory layers, not truth owners | Strong match. Current repo explicitly blocks promoting these layers above canonical evidence-linked state. | `docs/PaperPipe_Minimum_Operating_Principles.md`, `docs/API_CHAT_CONTRACT.md`, `docs/WEB_VIEWER.md` |
| parsing, canonical state quality, and verification matter more than generic chat polish | Strong match. The current runtime is paper/job/artifact-first and `/api/chat` is still stub-only. | `docs/Lattice_v3_Master_Spec.md`, `docs/API_CHAT_CONTRACT.md`, `backend/services/job_runner.py` |
| hybrid model posture can exist beneath a local-first product | Fits as architectural posture, as long as provider choice stays subordinate to local data ownership and canonical-state rules. | `docs/Lattice_v3_Master_Spec.md`, `src/config.py`, `src/llm_provider.py` |

## 3. Bounded next candidates

These ideas are not current product truth yet, but they have a safe additive interpretation that fits the repo.

| Idea from the summary | Safe current interpretation | Current insertion points | Guardrail |
| --- | --- | --- | --- |
| project-context linking and relevance capture | Safe only as support-only `raw_memory` / `non_canonical` supervision, not as a first-class project owner. | `src/schemas/project_memory.py`, `src/schemas/project_context_link.py`, `backend/routers/project_context_links.py` | Do not let `Project Memory` or link logs become stronger truth owners than current paper-side canonical state. |
| richer context / annotation layer | Safe as retrieval, operator-resume, or review support material under the current raw-memory and compiled-knowledge boundaries. | `docs/PaperPipe_Minimum_Operating_Principles.md`, `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`, `docs/API_CHAT_CONTRACT.md` | Keep it subordinate to `StructuredPaperState` and upstream evidence/source lineage. |
| read-only navigation or TOC-aware retrieval aids | Safe as viewer/navigation help derived from note headings and saved evidence locators. | `docs/WEB_VIEWER.md`, `backend/routers/paper_notes.py` | Do not create a second section-truth owner or a new retrieval truth store. |
| beginner-facing "Start here today" guidance | Safe as an additive improvement to the current triage shell and paper-first web journey. | `frontend/src/app/pages/TriageDashboard.tsx`, `frontend/src/App.tsx`, `docs/Product_Positioning_Principles.md` | Keep the home shell honest about current paper-first routes and avoid implying a full project platform. |
| experiment-plan or next-step guidance | Safe as derived drafts, workbench prompts, or lane-owned artifacts rather than repo-wide canonical object families. | `docs/Product_Positioning_Principles.md`, `docs/PaperPipe_Minimum_Operating_Principles.md`, bounded artifact docs such as `docs/MEETING_PACK.md` | Generated outputs should default to draft-like state and must not silently become canonical truth. |
| capability-slot framing for models | Safe as internal architecture or positioning language on top of the current provider layer. | `src/config.py`, `src/llm_provider.py`, `backend/services/job_runner.py` | Do not market this as a live user-facing account-connection or provider marketplace surface until such a surface actually exists. |

## 4. Future-only / explicit adoption required

These parts of the source summary overshoot the active runtime and should stay future-only unless an explicit product-shape decision reopens them.

| Idea | Why it stays future-only now | Current blocking anchors |
| --- | --- | --- |
| first-class project/workspace owner | Current runtime still explicitly rejects a project-first DB/API/UI/storage root. | `docs/Lattice_v3_Master_Spec.md`, `docs/PaperPipe_Minimum_Operating_Principles.md`, `docs/Product_Positioning_Principles.md` |
| repo-wide canonical `Decision`, `Open Question`, or `Next Action` families | The repo has bounded decision-like traces and raw-memory notes, but not a stable cross-surface canonical object family. | `docs/PaperPipe_Minimum_Operating_Principles.md`, `docs/reports/Canonical_Objects_Scope_Cut_And_Supported_Journey_2026-03-24.md` |
| broad memory/chat lane as active product surface | `/api/chat` is stub-only and the repo explicitly blocks chat, memory persistence, and RAG orchestration as current product truth. | `docs/API_CHAT_CONTRACT.md`, `docs/PaperPipe_Minimum_Operating_Principles.md` |
| product messaging that treats the current runtime as a full research operating system or project OS | This overstates the current first-product boundary, which is still paper-centered and bounded. | `docs/Product_Positioning_Principles.md`, `docs/reports/Canonical_Objects_Scope_Cut_And_Supported_Journey_2026-03-24.md` |
| provider account-connection, marketplace, or billing-style onboarding surface | Current repo has provider configs and adapters, not a user-facing provider-auth product lane. | `src/config.py`, `src/llm_provider.py`, `docs/API_CHAT_CONTRACT.md` |
| generalized experiment or decision workspace | Current repo has adjacent bounded artifacts and operator hints, not a general experiment/workflow platform. | `docs/PaperPipe_Minimum_Operating_Principles.md`, `docs/reports/Canonical_Objects_Scope_Cut_And_Supported_Journey_2026-03-24.md` |

## 5. Section-specific read of the source summary

The source summary is most reliable when read in three passes:

### A. Keep

Keep these ideas almost as-is:
- source/canonical/derived separation
- provenance-aware posture
- "model is not the truth store"
- workbench or wiki surfaces are not canonical truth
- hybrid provider posture beneath local data ownership

### B. Rewrite before reuse

Rewrite these ideas before promoting them into repo-facing docs:
- "project-centric" language
- "operating system" language
- project-dashboard-first UX framing
- claims that imply the product already has stable meeting-note, decision, and next-action object families

Those should be translated into current literals first:
- paper-first
- job/run/artifact-first
- note-backed structured state
- bounded downstream artifact lanes

### C. Park as future-only

Keep these parked until an explicit adoption decision exists:
- first-class `Project`
- broad memory/chat
- canonical cross-paper decision workspace
- generalized experiment runtime
- provider-auth or account-link product surface

## 6. Safest use of the source summary

Use the source summary as:
- a framing note for product intent
- a prompt for bounded RFCs
- a pressure test for whether new proposals preserve source/canonical/derived boundaries

Do not use it as:
- a replacement for `docs/Lattice_v3_Master_Spec.md`
- evidence that the current repo already ships a project/workspace platform
- justification for widening canonical schema families
- justification for reopening `Project Memory` or `/api/chat` as active product surfaces by momentum

If the summary is later promoted into repo-local docs, the safest path is:
1. rename the current-product wording to `Lattice`
2. split every major claim into `now`, `bounded next`, and `future-only`
3. move project/workspace, decision, next-action, and broad memory claims into explicit future-only sections
4. keep the strongest material on truth boundaries and provenance intact

## 7. Bottom line

The source summary contains several strong ideas that already match the repo:
- local-first posture
- evidence-linked truth
- source/canonical/derived separation
- workbench and annotation surfaces as support layers
- models as subordinate reasoning tools rather than truth owners

But as a whole it is still larger than the current runtime.

The safest current interpretation is:

> useful product-direction note, not current product contract

That means the summary is best used to sharpen bounded next RFCs while keeping the active PaperPipe/Lattice runtime honest about what it already is and what still remains future-only.
