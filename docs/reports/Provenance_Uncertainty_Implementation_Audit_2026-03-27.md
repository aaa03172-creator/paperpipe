# Provenance and Uncertainty Implementation Audit (2026-03-27)

Status: Active release evidence note with refreshed representative pack addendum
Date: 2026-03-27
Owner: Runtime/product maintainers
Canonical parents:
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/Evidence_and_Uncertainty_Rules.md`

## Purpose

Run one bounded implementation-strength audit on the current release slice and answer a narrower question:

- do the current representative runtime outputs keep weak support visible?

This note is not:
- a new truth-policy proposal
- a grounded-only readiness RFC
- a request to reopen broad UI or architecture lanes

## Representative Targets

Paper note detail:
- `paper_id = zotero:coricTargetingProdromalAlzheimer2015`
- `slug = zoterocoricTargetingProdromalAlzheimer2015`

Representative saved Meeting Pack:
- `meetingpack_20260325T062516207912Z_journal_club_0409564f`

Fresh comparison pack generated during this pass:
- `meetingpack_20260327T034836959925Z_journal_club_0409564f`

Status update (2026-03-28):
- refreshed active representative Meeting Pack:
  - `meetingpack_20260328T003221552910Z_journal_club_0409564f`

## Audit Criteria

Check whether the current release-facing slice visibly preserves:
- canonical state source path
- per-claim grounding signals such as `grounded` / `resolution`
- downstream caution when evidence is present but grounding is weak, missing, or unresolved

## Findings

### 1. Representative paper note detail is strong enough

`GET /paper-notes/zoterocoricTargetingProdromalAlzheimer2015` currently surfaces:
- canonical sidecar load trace:
  - `.pp/zoterocoricTargetingProdromalAlzheimer2015/state.json`
- `structured_state.claimset[*].evidence[*].grounded`
- `structured_state.claimset[*].evidence[*].resolution`
- evidence locator/source context

Representative claim-level examples from the live payload:
- `AMBIGUOUS_MATCH` with `grounded = false`
- `FAILED_MATCH` with `grounded = false`
- `NORMALIZED_MATCH` with `grounded = true`

Interpretation:
- the representative paper detail does not silently pretend that all support is citation-verified
- the runtime-managed canonical state and the ambiguity signals are both visible

### 2. The older saved representative Meeting Pack was weaker

`GET /meeting-packs/meetingpack_20260325T062516207912Z_journal_club_0409564f` currently returns:
- `readiness = evidence_backed`
- only the generic uncertainty:
  - `Numeric effect sizes and figure choices should still be re-verified from source text before presenting.`
- no key-point uncertainty note about missing or unresolved grounding metadata

Interpretation:
- this older saved pack remained usable
- but it understated the current grounding weakness compared with the representative note detail

### 3. Current fresh Meeting Pack generation is stronger than the older saved representative pack

A fresh pack generated during this pass from the same representative paper returned:
- `readiness = evidence_backed`
- explicit top-level uncertainty:
  - `At least one evidence-linked claim is still missing or unresolved citation-grounding metadata; re-check citation linkage before presentation.`
- explicit key-point uncertainty note:
  - `Direct evidence refs exist, but citation-grounding metadata is unresolved; re-check citation linkage before presentation.`

Interpretation:
- the current runtime does now surface the caution correctly for fresh packs
- the gap is not primarily a current generation/runtime blindness
- the gap is that older saved pack artifacts may predate the tighter uncertainty surfacing

### 4. The active representative Meeting Pack has now been refreshed

The refreshed active representative pack:
- `meetingpack_20260328T003221552910Z_journal_club_0409564f`

currently carries:
- `readiness = evidence_backed`
- top-level uncertainties including:
  - `At least one evidence-linked claim is still missing or unresolved citation-grounding metadata; re-check citation linkage before presentation.`
- key-point uncertainty notes including:
  - `Direct evidence refs exist, but citation-grounding metadata is unresolved; re-check citation linkage before presentation.`

Interpretation:
- the saved-artifact freshness gap for the active representative demo pack is now closed
- the remaining caution is semantic:
  - `evidence_backed` is still not full citation verification

## Judgment

Current best reading:
- representative paper detail is already honest enough for the bounded release slice
- current fresh Meeting Pack generation is also honest enough
- the active representative saved pack has now been refreshed to match the newer uncertainty surfacing
- the remaining weakness is narrower:
  - `evidence_backed` still is not equivalent to full citation verification

So the remaining launch `yellow` should stay `yellow`, but for a narrower reason than before:
- not because the current runtime generally hides provenance/uncertainty
- not because the active representative saved pack is stale
- but because `readiness=evidence_backed` is still not equivalent to full citation verification

## Practical Consequence

Safe current recommendation:
1. keep the launch row `yellow`
2. treat the current runtime note detail and the refreshed representative pack as strong enough
3. explain `evidence_backed` honestly as evidence-linked but not fully citation-verified

## Verification Used

- FastAPI `TestClient` requests against:
  - `/paper-notes/resolve-by-paper-id`
  - `/paper-notes/{slug}`
  - `/meeting-packs/{pack_id}`
  - `/meeting-packs/{pack_id}/validate`
- one fresh local pack generation using `generate_meeting_pack(...)` against the representative paper
- one refreshed active representative pack generation on 2026-03-28

## Conclusion

The remaining provenance/uncertainty launch caution is now narrower than the current checklist text suggests.

It is no longer:
- a broad runtime visibility problem

It is now:
- primarily a semantics problem around what `evidence_backed` means, plus the still-true fact that direct evidence presence is not the same thing as citation verification.
