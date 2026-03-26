# Frontend Backend Stale Baseline Audit (2026-03-24)

## Purpose
Record a short stale-baseline audit after the viewer-shell refinement and threshold-discipline passes.

This is a verification-only note. It does not change runtime UI contracts.

## Audit Scope

### Manually sampled desktop baselines
- `/papers` list
- `/papers/:slug` detail
- `/` triage
- `/image-evidence` index
- `/method-comparisons` index
- `/chart-packs` index
- `/meeting-packs` index
- `/protocol-cards` index

### Non-manual confirmation only
- mobile counterparts for the routes above
- detail snapshots for image evidence, method comparison, chart pack, protocol cards, meeting packs

These were not manually inspected in this audit. They rely on the latest targeted Playwright reruns staying green.

## Confirmed Corrected Incidents
- `/papers/:slug` detail:
  - older darwin snapshots previously preserved pre-refinement wording.
  - this was already corrected during the paper-note-detail wording lane.
- `/papers` desktop list:
  - the desktop baseline previously preserved older header/orientation copy.
  - this was corrected when the desktop threshold was reduced and the baseline was refreshed.

## Manual Sampling Results

### `/papers` list
- Baseline matches current wording:
  - `PAPER NOTE INDEX`
  - `Paper Notes`
  - `Search notes, filter structured signals, and open the paper detail you need.`
- Result: no current stale-baseline signal.

### `/papers/:slug` detail
- Baseline matches current wording:
  - `PAPER NOTE DETAIL`
  - review-oriented subtitle above the workbench handoff
- Result: no current stale-baseline signal.

### `/` triage
- Baseline matches current wording:
  - `RESEARCH QUEUE`
  - summary strip with `NEEDS REPAIR / NEEDS REVIEW / READY`
  - row-level `PRIMARY NEXT ACTION`
- Result: no current stale-baseline signal.

### `/image-evidence`
- Baseline matches current wording:
  - `IMAGE EVIDENCE REVIEW`
  - `Search image bundles`
  - `Saved image bundles`
- Result: no current stale-baseline signal.

### `/method-comparisons`
- Baseline matches current wording:
  - `METHOD COMPARISON REVIEW`
  - `Search comparisons`
  - `Saved comparison snapshots`
- Result: no current stale-baseline signal.

### `/chart-packs`
- Baseline matches current wording:
  - `CHART PACK REVIEW`
  - `Search chart packs`
  - `Saved chart-pack artifacts`
- Result: no current stale-baseline signal.

### `/meeting-packs`
- Baseline matches current wording:
  - `MEETING PACK REVIEW`
  - `Saved meeting packs`
  - `Open by pack ID`
- Note:
  - the right-rail/body copy still reads operational and inspector-like in places, but this matches the current route intent and is not treated as stale wording.
- Result: no current stale-baseline signal.

### `/protocol-cards`
- Baseline matches current wording:
  - `PROTOCOL KNOWLEDGE REVIEW`
  - `Search protocol cards`
  - `Open protocol card`
- Result: no current stale-baseline signal.

## Current Assessment
- Confirmed stale-baseline issues remain corrected on the two routes that previously drifted:
  - `/papers`
  - `/papers/:slug`
- No new stale wording was found in the sampled desktop viewer-shell baselines.
- Mobile and unsampled detail baselines were not manually inspected in this pass.
  - Current confidence there relies on recent route-targeted Playwright reruns rather than direct image review.

## Remaining Risk
- Low to medium:
  - sampled desktop baselines look aligned with current UI
  - unsampled mobile/detail baselines could still hide wording drift if a route keeps a looser threshold and no direct image inspection happens for a while

## Recommended Next Step
- Do not open another runtime UI lane from this audit.
- If further verification work is needed, prefer one of:
  1. stop here and treat the visual-hardening lane as complete for now
  2. only add new route-level coverage when a route still lacks a shell baseline

## Post-audit update
- 2026-03-24:
  - a backend full-page workbench shell screenshot contract was added after this audit.
  - this resolves the main open gap referenced above without reopening runtime UI.

## Verification
- Manual image review of the sampled desktop baselines listed above
- latest targeted Playwright reruns already green for:
  - `/papers` list
  - `/protocol-cards` detail/index
  - `/meeting-packs` detail/index
