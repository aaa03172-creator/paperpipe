# Canonical Owner Drift Review

Status: Active review note  
Date: 2026-03-24  
Owner: Runtime/design maintainers  
Scope: canonical owner wording across active docs and runtime anchors

## Purpose

Check whether current active docs and runtime anchors agree on who owns:
- source data
- canonical structured state
- note/mirror surfaces
- bounded derived artifacts

This note is not a new spec.

## Executive Call

Current repo is mostly aligned on canonical ownership.

Strong current center:
- Zotero owns imported source metadata and attachment origin
- PaperPipe/Lattice runtime owns canonical structured state
- Obsidian is a note and export mirror, not the canonical runtime store
- bounded artifact families remain derived bundles, not second truth stores

Main drift was wording, not implementation.

## 1. What Is Aligned

### A. PaperPipe runtime owns canonical structured state

Repo anchors:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `src/db_utils.py`
- `src/services/runtime_paths.py`

Why this is aligned:
- active docs now describe PaperPipe/Lattice runtime as the canonical structured-state layer
- runtime storage and DB helpers are centered on `jobs`, `execution_runs`, `job_events`, `user_actions`, paper-sidecar state, and file-backed artifact roots

### B. Research DNA owns search-design truth and Profile stays projection-only

Repo anchors:
- `docs/RESEARCH_DNA.md`
- `src/profiles/research_dna_projection.py`
- `src/profiles/profile_store.py`

Why this is aligned:
- the spec explicitly says `ResearchDNA` is the editable source of truth and `Profile` is an executable compatibility projection
- projection code writes provenance into `Profile.notes`, uses deterministic ids, and protects the operator-facing profile path with guarded rewrite/upsert rules

### C. Bounded artifacts are derived outputs, not canonicals

Repo anchors:
- `docs/MEETING_PACK.md`
- `docs/METHOD_COMPARISON.md`
- `docs/CHART_PACK.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `src/meeting_packs/store.py`

Why this is aligned:
- each bounded lane already says it is file-backed, read-first, and not a second truth store
- store code persists separate bundle files under dedicated roots rather than mutating canonical paper-side state into artifact-owned truth

### D. Obsidian is mirror/export, not runtime truth

Repo anchors:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/WEB_VIEWER.md`
- `backend/routers/obsidian.py`
- `docs/API_CHAT_CONTRACT.md`

Why this is aligned:
- current docs and routes treat note body/frontmatter as operator-facing mirror context while `vault/.pp/<slug>/state.json` and runtime artifacts carry structured run state
- the Obsidian router reads artifacts and syncs note blocks; it does not redefine canonical run ownership

## 2. Wording Drift Found

### A. Master spec still used older layer labels

Repo evidence:
- `docs/Lattice_v3_Master_Spec.md:72`
- `docs/Lattice_v3_Master_Spec.md:92`

Issue:
- `DB Layer: Zotero` and `Knowledge Layer: Obsidian` could be read as stronger ownership claims than the newer ownership section supports.

Action taken:
- renamed them to `Source Data Layer: Zotero-backed imports` and `Knowledge Mirror Layer: Obsidian`

### B. Viewer doc treated vault path like a source-of-truth statement

Repo evidence:
- `docs/WEB_VIEWER.md:42`
- `docs/WEB_VIEWER.md:44`

Issue:
- `Source of truth: paths.obsidian_vault` blurred filesystem root selection with canonical data ownership.

Action taken:
- changed the wording to `Vault source root`
- added an explicit note that note body/frontmatter is a mirror surface and does not replace canonical run/claim/evidence state

### C. Research DNA doc used “canonical executable lane” wording

Repo evidence:
- `docs/RESEARCH_DNA.md:122`
- `src/profiles/research_dna_projection.py`

Issue:
- that phrase could be misread as if `config/profiles.yaml` and projection-backed execution surfaces were canonical owners, which conflicts with the DNA/projection boundary.

Action taken:
- changed the wording to `compatibility-safe executable lane`

## 3. Remaining Low-Risk Tension

### A. Master spec still keeps historical layer names and tool examples

Repo evidence:
- `docs/Lattice_v3_Master_Spec.md`

Current judgment:
- acceptable for now because ownership is clarified above them
- still worth keeping an eye on if those historical labels begin to override current runtime reading habits

### B. Viewer docs still consume note body and frontmatter heavily

Repo evidence:
- `docs/WEB_VIEWER.md`
- `backend/routers/paper_notes.py`

Current judgment:
- this is intended, not a contradiction
- the important boundary is that note context can enrich review surfaces but must not replace structured sidecar truth for runs, claims, and evidence

## 4. Current Owner Map

### Source data owner

- Zotero export metadata
- PDF/attachment origin
- raw external library identity

### Canonical structured-state owner

- `vault/.pp/<slug>/state.json`
- runtime DB state
- run artifacts under `storage/artifacts/<paper-segment>/<run_id>/`
- `Research DNA`
- append-only audit/provenance signals

### Mirror/export owner

- Obsidian note body/frontmatter
- rendered markdown mirrors
- note organization and operator-facing navigation context

### Derived artifact owners

- `storage/meeting_packs/<pack_id>/`
- `storage/chart_packs/<chart_pack_id>/`
- `storage/method_comparisons/<comparison_id>/`
- `storage/image_evidence/<image_evidence_id>/`
- `storage/protocol_cards/<protocol_id>/`

These remain derived bundles, not canonical research-state roots.

## 5. Recommended Guardrail Going Forward

When new docs or features use “workspace”, “note”, “profile”, or “artifact” language:

1. say who owns the structured truth
2. separate mirror/export surfaces from canonical state
3. treat projection profiles as execution surfaces, not editable canonicals
4. treat bounded artifacts as derived outputs unless a separate spec explicitly promotes ownership
