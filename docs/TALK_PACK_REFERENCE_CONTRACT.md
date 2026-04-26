# Talk Pack Reference Contract

Status: Draft future seam  
Date: 2026-04-20  
Owner: Runtime/artifact maintainers  
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/TALK_PACK.md`

Related docs:
- `docs/SLIDE_MANIFEST_SCHEMA.md`
- `docs/KEY_NUMBERS_SPEC.md`
- `docs/MEETING_PACK.md`
- `docs/PAPER_SYNTHESIS.md`
- `docs/WEB_VIEWER.md`

## Purpose

Define the safest future minimum relationship between talk-pack-local ids and upstream claim/evidence refs.

This contract exists to keep future talk-pack refs:
- aligned with current PaperPipe claim/evidence identity
- paper-first
- easy to reopen from deck or script outputs
- narrow enough to avoid inventing a second locator family

without:
- creating a new claim/evidence runtime
- promoting local slide or key-number ids into stronger truth owners
- reintroducing legacy id drift as the primary reference system

## Current Judgment

At the current repo stage, this reference contract is only safe as:
- a future talk-pack-local ref-alignment seam
- a bounded bridge between talk-pack seed artifacts and current evidence-linked upstream state
- a clarification of which existing ids are primary vs additive

It is not yet safe as:
- a standalone runtime family
- a new generalized evidence schema
- a replacement for `claimset.resolved.json`, current structured state, or `ChatEvidenceRef`

Current status:
- no active `talk_pack` runtime family exists yet
- this doc is a bounded design target for future talk-pack generation and review

## Current Scope

The safe current scope is:
- one paper-scoped talk pack
- `slide_manifest.json`
- `key_numbers.md`
- selected downstream talk-pack outputs that must reopen evidence

## Non-Goals

This contract does not define:
- multi-paper cross-pack identity
- citation formatting rules
- a new evidence locator family
- deck-editor internal object ids

## 1. Upstream Identity To Reuse

The current repo already has a stable evidence-linking family that talk-pack should reuse.

Primary current upstream identity:
- `paper_slug`
- `claim.id`
- `evidence.id`
- `run_id`
- `locator`

Existing aligned downstream family:
- `docs/MEETING_PACK.md` already reuses `paper_slug`, `claim_id`, `evidence_id`, `run_id`, `locator`
- `src/schemas/chat.py` defines the current additive `ChatEvidenceRef` / `ChatLocator` surface
- `docs/WEB_VIEWER.md` marks `run.id`, `claim.id`, and `evidence.id` as stable ids

Current rule:
- future talk-pack should reuse this family rather than inventing a second evidence-ref shape

## 2. Primary Vs Additive Claim Identity

Current primary claim identity for talk-pack purposes should be:
- the normalized stable claim `id` from selected structured state
- or the normalized claim-card `id` derived from selected `claimset.resolved.json`

In practice, that means:
- if talk-pack reads raw `claimset.resolved.json`, it should treat payload `claim_id` values as source-side inputs until they are resolved into the current normalized stable claim `id`
- use current claim `id` as the primary ref target
- treat legacy `source_claim_id` as additive lineage only

Current rule:
- `source_claim_id` may be preserved in notes or metadata
- `source_claim_id` must not become the primary `claim_refs[]` payload for talk-pack artifacts
- `claim_refs[]` should be persisted only after normalization into the current stable claim `id`

If only a legacy claim identifier is available:
- resolve it to the current stable claim `id` before persisting talk-pack refs when possible
- if that resolution is not possible, the dependent talk-pack output should remain warning-heavy or background-only rather than pretending the ref is strong

## 3. Pack-Local Ids Stay Local

Pack-local ids are allowed and useful, but they are not stronger than upstream ids.

Recommended talk-pack-local ids:
- `slide_id`
- `key_number_id`

Current rule:
- these ids are local handles inside one `talk_pack.json`
- they must not replace upstream `claim.id` or `evidence.id`

## 4. Slide Manifest Ref Rules

### 4.1 `claim_refs[]`

`slide_manifest.json` should treat `claim_refs[]` as:
- a list of current stable upstream `claim.id` values
- scoped to the pack's selected `paper_slug`

Current rule:
- `claim_refs[]` should not store rendered prose
- `claim_refs[]` should not store `source_claim_id` as the primary payload

### 4.2 `key_number_refs[]`

`key_number_refs[]` should point to talk-pack-local `key_number_id` values from `key_numbers.md`.

Current rule:
- `key_number_refs[]` is local-to-pack
- each referenced key number should still be able to reopen stronger upstream claim/evidence lineage

### 4.3 Optional `evidence_refs[]`

When a slide needs span-level or locator-level reopen support, the manifest may additionally carry `evidence_refs[]`.

That field should reuse `ChatEvidenceRef` semantics:
- `paper_slug`
- `claim_id`
- `evidence_id`
- `run_id`
- `locator`

Current rule:
- reuse the existing `ChatEvidenceRef` / `ChatLocator` family
- do not introduce a second talk-pack-only evidence locator schema

### 4.4 Current Runtime-Reuse Recommendation

Based on current active lanes, the safest future runtime rule is:
- if talk-pack seed artifacts need `evidence_refs[]`, type them directly as `list[ChatEvidenceRef]`

Why this is the best current default:
- `Paper Synthesis` already uses `ChatEvidenceRef` directly
- `Method Comparison` already uses `ChatEvidenceRef` directly
- `Protocol Card` already uses `ChatEvidenceRef` directly
- `Meeting Pack` is the current exception because it needs extra lane-local fields such as local `id`, `support_type`, and `note`

Current recommendation:
- do not invent `TalkPackEvidenceRef` by default
- reuse `ChatEvidenceRef` directly for talk-pack seed artifact fields that only need reopenable evidence identity
- if a future talk-pack lane needs extra local metadata, keep that metadata in sibling fields or local maps first
- only introduce a specialized talk-pack evidence-ref type if direct `ChatEvidenceRef` reuse becomes materially insufficient

This keeps talk-pack aligned with the repo's existing additive evidence-ref reuse pattern instead of proliferating near-duplicate schemas.

### 4.5 `source_artifact_refs[]` are not a substitute

`source_artifact_refs[]` remain useful, but they are owner/artifact pointers, not claim/evidence identity.

Current rule:
- `source_artifact_refs[]` may say where the slide came from
- they must not replace claim or evidence refs when a slide makes an evidence-backed claim

## 5. Key-Number Ref Rules

Each `key_numbers.md` row should have:
- one talk-pack-local `key_number_id`
- at least one stronger upstream reopening path

Recommended current relationship:
- `key_number_id` is local
- `claim_refs[]` point to stable upstream `claim.id` values when the number supports a claim
- optional `evidence_refs[]` should directly reuse `ChatEvidenceRef` when the number needs direct locator reopening
- `upstream_owner_ref` points to the stronger saved owner artifact

Current rule:
- `key_number_id` is the local handle for scripts, decks, and quick-review output
- `key_number_id` must not be the only recoverable provenance for a scientific number

## 6. Minimal Reopen Path

The safest future reopen chain is:

1. talk-pack export member
2. `slide_id` or `key_number_id`
3. `claim_refs[]` and optional `evidence_refs[]`
4. stronger upstream owner or selected artifact
5. canonical paper-scoped evidence-linked state

Current rule:
- no polished talk output should stop at the pack-local alias if it presents itself as evidence-backed

## 7. Minimal Examples

### 7.1 Slide manifest example

```json
{
  "slide_id": "s04",
  "title": "Butyrate exposure increased regulatory T-cell markers",
  "claim_refs": ["claim_4d5f89ab12cd"],
  "key_number_refs": ["kn_02"],
  "evidence_refs": [
    {
      "paper_slug": "wenzelShortchainFattyAcids2020",
      "claim_id": "claim_4d5f89ab12cd",
      "evidence_id": "evidence_a13c09ef9201",
      "run_id": "run_20260420_090000",
      "locator": {
        "page": 5,
        "table_id": "table_2",
        "cell_id": "r4c2"
      }
    }
  ]
}
```

### 7.2 Key-number row example

```md
| key_number_id | label | display_value | exact_value | claim_refs | upstream_owner_ref | source_location |
| --- | --- | --- | --- | --- | --- | --- |
| kn_02 | Treg marker increase | 18% | 18.2 | claim_4d5f89ab12cd | analysis_run_20260420_wenzel | table_2:row_4 |
```

## 8. Conclusion

The safest future talk-pack reference contract is:
- upstream-id-first
- pack-local-alias-second
- evidence-family-reusing
- non-canonical

That is enough to keep `slide_manifest` and `key_numbers` useful without drifting away from current PaperPipe evidence identity.
