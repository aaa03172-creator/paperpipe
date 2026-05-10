# Document Overlap and Conflict Map

Status: Dated review note  
Date: 2026-03-24  
Owner: Runtime/design maintainers  
Scope: active canonicals, bounded specs, and current release-scope notes

## Purpose

Map which active documents currently own product/runtime meaning, where wording still overlaps, and where scope drift would most likely re-enter the repo.

This note is not a new spec.

## Current document roles

| Document | Class | One-line purpose | What it should own |
| --- | --- | --- | --- |
| `docs/README.md` | canonical map | documentation routing and hierarchy | which doc is normative vs historical |
| `docs/Product_Positioning_Principles.md` | canonical | product identity and stable product-level principles | why the product exists, who it is for, what it is not |
| `docs/Lattice_v3_Master_Spec.md` | canonical SSOT | top-level runtime and contract source | active runtime shape, ownership, storage, API/model contract |
| `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md` | canonical workflow guide | safe audit-first architecture refocus workflow | how to review/change architecture without reopening product shape |
| `docs/PERSONA_MODE_BOUNDARY.md` | canonical bounded rule | reasoning/profile/output-mode separation | persona vs profile vs presentation boundary |
| `docs/Evidence_and_Uncertainty_Rules.md` | canonical bounded rule | evidence-first and uncertainty-visible truth policy | claim/evidence trust boundary across lanes |
| `docs/API_CHAT_CONTRACT.md` | canonical bounded contract | future chat hook and current stub boundary | `/api/chat` non-scope and chat-state contract floor |
| `docs/RESEARCH_DNA.md` | canonical bounded spec | bounded search-design lane | `ResearchDNA` lifecycle and `Profile` projection boundary |
| `docs/MEETING_PACK.md` | canonical bounded spec | bounded downstream meeting-draft lane | canonical inputs, draft output, trace/readiness/regenerate rules |
| `docs/reports/First_Shippable_Product_Bar_2026-03-24.md` | active decision note | first externally presentable product boundary | what counts as the first product promise |
| `docs/reports/Launch_Readiness_Checklist_2026-03-24.md` | active release gate note | practical go/no-go translation of the product bar | green/yellow/red release judgment |

## Stable overlap that is healthy

These ideas intentionally appear in multiple active docs and should remain repeated.

1. The product is `local-first`, `paper-centered`, `paper-first`, and `single-operator-first`.
2. Natural language may operate the system, but structured state is the source of truth.
3. Source data, canonical structured state, and derived artifacts stay separate.
4. Provenance and uncertainty remain visible.
5. `Project`, broad memory/chat, and generalized workspace/platform lanes are future-only unless explicitly adopted.

This repetition is good because these are the assertions most likely to drift under new proposals.

## Overlap and drift map

### 1. Product shape: `workspace` vs `platform` vs `paper-centered product`

Primary owners:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`

Current state:
- Active docs now align on `paper-centered`, `paper-first`, and `paper/job/artifact-first`.
- Bounded specs mostly reinforce that boundary by explicitly rejecting generalized platform interpretations.

Remaining drift:
- release-scope docs sometimes use `artifact-first` as shorthand, while the stronger current runtime wording is `paper/job/artifact-first`; this is a minor wording drift, not a competing architecture.
- `docs/Lattice_v3_Master_Spec.md` still carries some older “blueprint” tone and broader implementation sections later in the file, which can read larger than the current product shape even when the top sections are aligned.
- Historical audits and older reports still use phrases closer to “research operating surface” or “broader workspace,” and should not be cited as present-tense SSOT.

Judgment:
- no active canonical conflict
- continuing risk comes from legacy master-spec tail sections and historical reports being over-cited

### 2. `paper-centered` vs `project-centered`

Primary owners:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`

Current state:
- Active product/runtime docs consistently say current runtime is not first-class `Project`-based.
- `Meeting Pack` and related bounded lanes can mention `project_note` or `project_profile`, but those are selector/context surfaces, not top-level runtime ownership.

Remaining drift:
- external prompts and historical proposal/review notes still tend to pull toward `Project` as the natural top-level owner.
- some readers may still over-read `workspace` to mean `project-first workspace`.

Judgment:
- current active docs are aligned
- this boundary needs continuous repetition, not a new spec

### 3. `local-first` meaning

Primary owners:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`

Current state:
- both docs now explain `local-first` as operational: ownership, recovery, portability, offline survivability, limited provider dependence.

Remaining drift:
- older docs often use `local-first` as a looser style word rather than an operational constraint.

Judgment:
- active canonicals are aligned
- no new doc needed; old reports should simply not be treated as stronger than the active pair

### 4. LLM role, chat, and memory boundaries

Primary owners:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`

Current state:
- active docs agree that `/api/chat` is stub-only and that memory/chat is not an active product lane.
- persona/profile/output mode separation remains explicit.

Remaining drift:
- the later sections of `docs/Lattice_v3_Master_Spec.md` still include older concrete model-routing assumptions and runtime examples (`Ollama`, `ChromaDB`, specific model names, chat model slots) that are larger and older than the current release-shape story.
- these sections do not reopen chat/memory by themselves, but they do make the file feel more like an expansive blueprint than a narrow runtime SSOT.

Judgment:
- no immediate contract conflict
- strongest remaining canonical cleanup candidate is narrowing or reclassifying old master-spec implementation assumptions

### 5. `source` / `canonical` / `derived artifact` ownership

Primary owners:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- bounded artifact specs

Current state:
- this is now one of the strongest aligned concepts in the repo.
- bounded specs consistently describe themselves as derived bundles, not second truth stores.

Remaining drift:
- some older viewer or audit notes still speak about vault paths or bundle-local JSON with wording that could sound more canonical than intended, but the active docs have already been narrowed.

Judgment:
- healthy overlap
- no new canonical needed

### 6. `v1` scope vs future vision

Primary owners:
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/Product_Positioning_Principles.md`
- bounded specs with explicit non-goals

Current state:
- release-scope docs now separate launch-defining core from bounded extensions and gated surfaces.
- `Research DNA` and `Meeting Pack` both explicitly document what v1 does not include.

Remaining drift:
- the master spec still contains older blueprint breadth beyond what the release-bar docs promise.
- historical implementation/audit notes can be mistaken for current roadmap commitments if cited without the newer release-bar notes.

Judgment:
- active release-scope docs are aligned
- main risk is readers defaulting to the older broader master-spec tail or old audits

## Strongest conflict candidates

These are the areas most likely to cause confusion if left unattended.

### Candidate A: old implementation assumptions inside the master spec

Why it matters:
- the top of `docs/Lattice_v3_Master_Spec.md` now matches the current product/runtime shape, but later sections still contain older blueprint-era model/runtime assumptions.
- this is the most plausible place where a future contributor could re-inflate scope by quoting a still-active canonical file.

Recommended action:
- future narrow patch candidate
- keep the master spec as SSOT, but trim or clearly label older model-routing/runtime-specific sections as historical implementation examples rather than active runtime commitments

### Candidate B: historical audits being cited like current canonicals

Why it matters:
- several 2026-03-13 audit and baseline notes still contain now-outdated breadth or older assumptions.
- they remain useful as history, but not as current scope-setting documents.

Recommended action:
- no deletion required now
- keep steering new references toward `docs/Product_Positioning_Principles.md`, `docs/Lattice_v3_Master_Spec.md`, and the 2026-03-24 release-bar/checklist pair

## Delete / merge / promote candidates

### Delete

- none recommended right now
- the current problem is citation discipline, not file-count pressure

### Merge

- do not merge `docs/Product_Positioning_Principles.md` and `docs/Lattice_v3_Master_Spec.md`
- do not merge release-bar/checklist notes into the master spec
- each currently serves a distinct layer cleanly enough

### Promote

- no new top-level active doc is justified by this review
- if a future `core assertions` list is needed, promote it as a short section inside `docs/Product_Positioning_Principles.md`, not as another standalone SSOT

## Practical citation rule after this review

When a future task needs one document per layer, prefer this stack:

1. Product identity: `docs/Product_Positioning_Principles.md`
2. Runtime truth: `docs/Lattice_v3_Master_Spec.md`
3. Architecture refocus workflow: `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
4. Persona/profile/output-mode boundary: `docs/PERSONA_MODE_BOUNDARY.md`
5. Evidence/trust policy: `docs/Evidence_and_Uncertainty_Rules.md`
6. Chat stub boundary when relevant: `docs/API_CHAT_CONTRACT.md`
7. Release scope and go/no-go: `docs/reports/First_Shippable_Product_Bar_2026-03-24.md` and `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
8. Bounded lane details: `docs/RESEARCH_DNA.md`, `docs/MEETING_PACK.md`, and the specific bounded spec family

## Bottom line

The current repo does not have a broad active canonical conflict problem.

It has a priority/citation problem:
- active canonicals are mostly aligned
- release-scope notes are aligned
- bounded specs are aligned
- the main remaining risk is that older blueprint-era sections or historical audits get read as equal-strength SSOT

The most valuable next cleanup is not a new architecture doc.
It is a narrow pass on the remaining legacy breadth inside `docs/Lattice_v3_Master_Spec.md`, followed by disciplined reuse of the current active document stack.
