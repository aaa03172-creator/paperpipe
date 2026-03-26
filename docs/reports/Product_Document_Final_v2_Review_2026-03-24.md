# Product Document Final v2 Review (2026-03-24)

Status: Active
Date: 2026-03-24
Owner: Runtime/design maintainers
Scope: review `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md` against the current PaperPipe repo

## Purpose

Sort the external product document into three buckets:

1. keep as product-direction input
2. park as future-only material
3. identify what can be absorbed into current active docs without rewriting the runtime around a different model

This note is not a runtime spec.

## Overall Judgment

The document is strong as a future-facing product narrative.

It is not safe to adopt as an active PaperPipe product/runtime description because it repeatedly states a `project-first` workspace model, broad protocol/workspace ownership, meeting-record canonicalization, and future memory/UI surfaces as if they are already the current repo shape.

Current repo reality remains:
- paper-first
- local-first
- operator-reviewable
- bounded around `papers`, `jobs`, `artifacts`, note state, `Research DNA`, `Meeting Pack`, and other bounded artifact lanes

Current active anchors:
- `docs/Product_Positioning_Principles.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/API_CHAT_CONTRACT.md`

## 1. Keep

These parts are worth keeping as product-direction input and are broadly compatible with current repo principles.

### A. Natural language is interface, structured state is truth

Keep:
- product philosophy in section 2.2
- the idea that commands should land as state, logs, linkage, and artifacts

Why it fits:
- aligns with current sidecar state, file-backed artifacts, and append-only run/audit emphasis
- does not require a new top-level owner by itself

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:28`

Closest current repo anchors:
- `docs/Product_Positioning_Principles.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`

### B. Source / canonical / derived separation

Keep:
- the three-layer separation in sections 3.2 and 3.3
- the export/delivery artifact framing later in the document

Why it fits:
- matches current runtime direction across note sidecar state, file-backed artifacts, and export caution
- reinforces a distinction the repo already relies on

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:110`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:165`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1139`

Closest current repo anchors:
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/Product_Positioning_Principles.md`

### C. Zotero / Obsidian / PaperPipe ownership split

Keep:
- storage-role framing in section 4

Why it fits:
- this is directionally consistent with current runtime boundaries
- it is useful for preventing source-of-truth confusion without forcing new schemas

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:202`

Closest current repo anchors:
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`

### D. Provenance, failed runs, stale artifacts, human sign-off

Keep:
- emphasis on provenance and failed-run recording
- stale artifact detection
- human sign-off points
- ingestion quality flags

Why it fits:
- current repo already has partial or implemented support for all of these themes
- they strengthen current architecture instead of redefining it

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:575`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1055`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1944`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1963`

Closest current repo anchors:
- `src/db_utils.py`
- `src/schemas/skills.py`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/WEB_VIEWER.md`

### E. Job/run logging before UI polish

Keep:
- the ordering principle that canonical logging comes before nicer visualization

Why it fits:
- exactly matches the repo’s current runtime priority shape

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:599`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1818`

Closest current repo anchors:
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`

## 2. Future-Only / Park

These sections are useful ideas, but they should stay future-facing or parked because they would overstate the current repo.

### A. Project as the active top-level owner

Park:
- one-line definition
- “Project 중심 구조”
- any statement that `Project` is already the top-level canonical owner

Why parked:
- current repo still does not have an approved first-class project runtime surface across DB/API/UI
- promoting this language would make docs lead implementation

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:5`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:89`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:2003`

Repo anchors:
- `docs/Product_Positioning_Principles.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`

### B. Broad canonical object family under Project

Park:
- `Project`-scoped objects such as `experiment_data`, `decision`, `open_question`, `blocked_reason`, `artifact_index`, `export_manifest` when described as if they already exist as current first-class runtime objects

Why parked:
- some of these exist only as partial signals
- others exist only in a bounded file-store lane or future RFC
- current repo can audit them as `implemented/partial/missing`, but should not claim them as active canonicals

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:273`

Repo anchors:
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `src/schemas/project_memory.py`

### C. Protocol as a project-level canonical platform

Park:
- protocol language that describes a broad project-level protocol object family with experiment/deviation/workspace ownership

Why parked:
- current repo has a bounded `Protocol Knowledge` lane implemented as `ProtocolCard` and versioned protocol-reference bundles
- the active repo explicitly avoids turning that lane into a generalized protocol platform

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:621`

Repo anchors:
- `docs/PROTOCOL_KNOWLEDGE.md`
- `src/schemas/protocol_card.py`

### D. Meeting records as a canonical workspace subsystem

Park:
- the meeting-records canonical layer in section 20

Why parked:
- current repo has `Meeting Pack` as a downstream artifact family, not an approved meeting-records canonical subsystem
- some concepts appear in generated pack text or future lanes, but not as a stable cross-product system

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1411`

Repo anchors:
- `docs/MEETING_PACK.md`
- `src/schemas/meeting_pack.py`

### E. Memory core and conversational cockpit

Park:
- memory core section
- conversational cockpit wording

Why parked:
- `/api/chat` is still stub-only
- memory/conversation persistence is explicitly out of scope in the current runtime

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1917`

Repo anchors:
- `docs/API_CHAT_CONTRACT.md`
- `backend/main.py`

### F. Project-level UI surfaces and project-aware retrieval

Park:
- project screen
- project-level recent jobs
- project-aware retrieval as current-lane product description

Why parked:
- current frontend routes are still paper/artifact/bounded-viewer-first
- retrieval expansion should follow schema/log/linkage hardening rather than frontload project UX

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1720`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1851`

Repo anchors:
- `frontend/src/App.tsx`

## 3. Active Absorption Candidates

These ideas can be absorbed into current active docs, but only in repo-grounded wording.

### A. Product positioning language about “workspace”

Absorb as:
- product direction for small lab/project contexts
- not as proof of a current project-first runtime

Target doc:
- `docs/Product_Positioning_Principles.md`

Action:
- optional future patch only if wording is needed
- use it to sharpen product-direction language, not runtime structure

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:12`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:80`

### B. Ownership and source-of-truth policy

Absorb as:
- clearer operator guidance about who owns bibliographic, narrative, and workflow truth

Target doc:
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`

Action:
- already partially covered in the current guide
- no immediate patch required from this review

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:202`

### C. Operational record checklist

Absorb as:
- audit checklist for stale artifacts
- negative results
- sign-off markers
- ingestion quality

Target doc:
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`

Action:
- already substantially covered
- future patch only if a specific missing checklist item emerges from repo audit

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:605`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1944`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:1963`

### D. Meeting Pack product framing

Absorb as:
- “presentation draft, not detached truth”
- “important but upstream state first”

Target doc:
- `docs/MEETING_PACK.md`

Action:
- mostly already covered
- no immediate patch required

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:942`

### E. Protocol direction as future product pressure

Absorb as:
- future product pressure toward richer procedure/protocol reuse
- not as a replacement for bounded `ProtocolCard` semantics

Target docs:
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/archive/Prompt_Review_Parked_Useful_Items_2026-03-23.md`

Action:
- keep as future input only
- do not widen the active protocol spec during this pass

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:621`

## 4. Rewrite Required Before Any Promotion

These parts would need rewriting before they could move into any active doc.

### A. Research DNA vs Search Profile

Problem:
- the document repeatedly treats `Research DNA / Search Profile` as a co-equal canonical pair

Current repo truth:
- `ResearchDNA` is the editable search-design source
- `Profile` is the projected executable compatibility surface

Rewrite rule:
- if promoted, rename this concept to `Research DNA + projected Profile compatibility surface`

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:95`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:430`

Repo anchors:
- `docs/RESEARCH_DNA.md`
- `src/profiles/research_dna_projection.py`

### B. Lifecycle enums

Problem:
- several status sets in the document do not match current live schemas

Examples:
- `Research DNA` adds `SUPERSEDED`
- screening lifecycle is presented as object-state flow rather than current decision-centered records
- `Meeting Pack` adds approval/stale/archive statuses not present in the live schema
- protocol statuses/source types exceed current `ProtocolCard` enums

Rewrite rule:
- if promoted, active docs must use current literals first and mark larger state sets as future-only

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:421`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:446`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:995`
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:705`

Repo anchors:
- `src/profiles/research_dna_schema.py`
- `src/schemas/meeting_pack.py`
- `src/schemas/protocol_card.py`

### C. Thin-link taxonomy

Problem:
- the proposed taxonomy includes relation types that presume first-class project/decision/experiment/protocol ownership

Rewrite rule:
- keep current taxonomy centered on existing IDs and live artifact/run/paper relations
- move `belongs_to_project`, `triggered_by_decision`, `linked_to_experiment`, `uses_protocol`, `protocol_discussed_in_meeting` to future-only unless code proves them

Source:
- `/Users/jangseongjin/Downloads/PaperPipe_product_document_final_v2.md:297`

Repo anchors:
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`

## 5. Recommended Handling

### Safe now

- keep this document outside active SSOT
- use it as product-direction input and future-RFC seed material
- cite it when discussing future `project` / `protocol` / `meeting memory` / `visibility` directions

### Not safe now

- replacing `docs/Product_Positioning_Principles.md`
- replacing `docs/Lattice_v3_Master_Spec.md`
- using it as the current runtime architecture document
- copying its P0/P1/P2 list into the active roadmap without repo-grounded re-triage

## 6. Smallest Next Moves

1. Do not promote this external document into `docs/` as an active spec.
2. Reuse it as future input when a bounded RFC is reopened:
   - project/workspace
   - richer protocol lane
   - meeting-record ingestion
   - delivery/export manifests
3. If a follow-up patch is needed, prefer a tiny wording patch in an existing canonical doc rather than creating a new master document.
