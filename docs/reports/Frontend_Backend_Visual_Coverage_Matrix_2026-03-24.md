# Frontend Backend Visual Coverage Matrix (2026-03-24)

## Purpose
Summarize the current backend-driven Playwright visual coverage for PaperPipe's main viewer and work-surface routes, including threshold discipline, mask strategy, and remaining gaps.

## Scope
- Source of truth for this matrix:
  - `/Users/jangseongjin/paperpipe/frontend/e2e/visual-backend.backend.spec.ts`
  - matching darwin snapshot files under `/Users/jangseongjin/paperpipe/frontend/e2e/visual-backend.backend.spec.ts-snapshots/`
- This report is verification-only.
- It does not redefine runtime UX specs or route ownership.

## Coverage Matrix

| Route / Surface | Coverage shape | Desktop threshold | Mobile threshold | Dynamic mask strategy | Current note |
| --- | --- | ---: | ---: | --- | --- |
| `/papers` list | full-page | `12000` | `2800` | none | Desktop baseline was refreshed after copy drift was discovered. |
| `/` triage | full-page | `6200` | `4200` | mask row `Updated:` labels | Summary strip and primary-action copy are now part of the baseline. |
| `/papers/:slug` detail | full-page | `3200` | `3500` | none | Base detail shell is stable. |
| `/papers/:slug` structured detail | full-page | `4500` | `4200` | none | Structured cards and review terminology are part of the baseline. |
| `/workbench/:paperId` shell | full-page | `7600` | `6200` | mask timeline time labels | Route-level shell coverage now complements the existing rail/PDF subregion baselines. |
| `/workbench/:paperId` rail | subregion only | `4000` | none | none | Desktop rail snapshot retained for tighter navigation-rail drift detection. |
| `/workbench/:paperId` claim highlight | subregion only | `1600` | `1200` | none | PDF highlight rendering covered, not the full workbench shell. |
| `/image-evidence` detail | full-page | `4200` | `4200` | mask `Created` field | Stable after header-copy refinement. |
| `/image-evidence` index | full-page | `5200` | `5200` | mask card `Created:` labels | Stable after index-copy refinement. |
| `/method-comparisons` detail | full-page | `5200` | `5200` | mask `Created` and `Generated` | Verification lane is balanced. |
| `/method-comparisons` index | full-page | `6200` | `6200` | mask card `Created:` and `Generated:` labels | Verification lane is balanced. |
| `/chart-packs` detail | full-page | `6200` | `6200` | mask `Created` and `Generated` | Verification lane is balanced. |
| `/chart-packs` index | full-page | `6200` | `6200` | mask card `Created:` and `Generated:` labels | Verification lane is balanced. |
| `/protocol-cards` detail | full-page | `6200` | `6200` | none | Threshold reduced from `7200` without baseline refresh. |
| `/protocol-cards` index | full-page | `6800` | `6800` | none | Threshold reduced from `7600` without baseline refresh. |
| `/meeting-packs` detail | full-page | `7200` | `7200` | mask `Created`, visible `meetingpack_*`, and pack-id input | Threshold reduced from `8200` without baseline refresh. |
| `/meeting-packs` index | full-page | `7200` | `7200` | mask card `Created:` labels and visible `meetingpack_*` ids | Threshold reduced from `8200` without baseline refresh. |

## Stale Baseline Watch

### Confirmed stale-baseline incidents already corrected
- `/papers/:slug` detail:
  - older darwin snapshots preserved pre-refinement wording under a lenient threshold.
  - refreshed during the detail wording lane.
- `/papers` desktop list:
  - previous desktop baseline still showed older header/orientation copy.
  - refreshed when the threshold was reduced from `25000` to `12000`.

### Routes that did not require baseline refresh during threshold audit
- `/protocol-cards`
- `/meeting-packs`

## Current Gaps
- No single matrix doc previously existed:
  - coverage status lived across route UX reports and `visual-backend` alone.
- Snapshot inventory in the worktree is still noisy:
  - multiple darwin snapshots remain modified or untracked as part of this bounded frontend lane.

## Current Threshold Posture
- Tightest:
  - claim highlight subregions (`1200` mobile, `1600` desktop)
  - paper-note detail shells (`3200` to `4500`)
- Mid-range and now reasonably aligned:
  - triage, image evidence, method comparison, chart pack, protocol knowledge
- Still the loosest full-page routes:
  - meeting-pack detail/index at `7200`

## Recommended Next Step
- Do not reopen runtime UI from this matrix alone.
- If another verification-only pass is needed, prefer:
  1. closing the visual-hardening lane unless a new route regresses
  2. a short stale-baseline spot check only when a baseline refresh or wording pass lands
  3. targeted threshold tuning only for new outlier routes, not another broad audit

## Suggested Verification When This Report Changes
- `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`
