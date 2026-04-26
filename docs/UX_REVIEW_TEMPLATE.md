# UX Review Template

Status: Active template
Date: 2026-03-13
Owner: Lattice runtime maintainers
Canonical parent: `docs/ux-review.md`

## Header
- Screen/Flow:
- Goal action:
- Primary persona:
- Current friction:
- Success metric:
- Constraints:

## Quick Review (5 min)
- First meaningful success:

## Full Review
### P0
### P1
### P2

### Full Review Coverage
- 6P storyboard context:
- BMAP:
- B.I.A.S:
- Peak-End:
- Ethics:

## BMAP diagnosis

## B.I.A.S diagnosis

## Peak-End design notes

## Concrete changes

## Ethics check results

## Next PR-sized actions

## Verification
- Backend/API contract checks for additive review-gate artifacts when the surface depends on them.
- Frontend viewer changes should include `cd frontend && npm run build` plus the relevant Playwright or visual coverage for the touched surface when that route already has tests.
