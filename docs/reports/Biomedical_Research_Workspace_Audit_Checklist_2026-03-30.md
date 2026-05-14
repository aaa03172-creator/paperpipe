# Biomedical Research Workspace Audit Checklist (2026-03-30)

Status: Completed
Date: 2026-03-30
Owner: Lattice runtime maintainers
Reviewer: Codex
Canonical inputs:
- `docs/UX_REVIEW_REPORT_primary-research-loop.md`
- `docs/UX_REVIEW_REPORT_artifact-family.md`
- `docs/UX_REVIEW_REPORT_cross-cutting-systems.md`

## Goal

Verify the current PaperPipe UI/UX as a connected biomedical research workspace, not as isolated route demos.

## Stopping condition

- Every checklist item below is marked `PASS`, `FIXED`, or `N/A`.
- Any `FAIL` discovered during review is either fixed and reverified or explicitly left as a blocker.
- A final double-check reruns the narrow checks supporting the closing claim.

## Checklist

### A. Primary Research Loop

| ID | Item | Verification mode | Status | Notes |
|---|---|---|---|---|
| A1 | Home `/ui` communicates start path without mock fallback | Direct current runtime | PASS | `Start here=1`, `Mock mode=0` on current `:8000`. |
| A2 | Runtime readiness `/ui/ready` renders honest readiness guidance | Direct current runtime | PASS | Body shows `RUNTIME READINESS`, `Needs attention`, `WARNINGS`; API remains honestly `degraded` because `watch_folder` is a warning on this machine. |
| A3 | Paper Notes index `/ui/papers` exposes import and pickup setup clearly | Direct current runtime | PASS | `Add your own PDF=1`, `Check automatic pickup setup=1`, `Mock mode=0`. |
| A4 | Paper detail `/ui/papers/:slug` shows review snapshot and primary handoffs | Direct current runtime | PASS | `Review snapshot=1`, `Save protocol card=2`, `Open in Workbench=3` on current note detail. |
| A5 | `Save protocol card` preserves canonical note context | Direct current runtime + seeded rail | PASS | Current runtime href is `/ui/protocol-cards?noteSlug=zoteroduboisAlzheimerDiseaseClinicalBiological2024&paperId=zotero%3AduboisAlzheimerDiseaseClinicalBiological2024`; seeded rail `backend paper note detail can start a protocol card with note context from the browser` passed. |
| A6 | Workbench `/ui/workbench/:paperId` loads without mock fallback or console noise | Direct current runtime | PASS | `Mock mode=0`, visible buttons include `Run deep read`, console errors `[]`. |
| A7 | `note -> workbench -> protocol` core journey stays connected | Seeded backend rail | PASS | `backend paper note to workbench to protocol create journey stays connected in the browser` passed. |

### B. Artifact Family

| ID | Item | Verification mode | Status | Notes |
|---|---|---|---|---|
| B1 | Protocol detail explains purpose and links back to note | Direct current runtime | PASS | `When to use=1`, `Open note=1` on saved protocol detail. |
| B2 | Meeting Pack detail explains purpose and keeps note-first continuation | Direct current runtime | PASS | `When to use=1`, `Continue from this draft=1`, `Continue in note=1` on latest saved meeting pack. |
| B3 | Meeting Pack create/rerender/regenerate keeps note-first continuation | Seeded backend rail | PASS | `backend meeting pack create keeps the continuation card and note handoff on the real route` covers create, rerender, regenerate, and note continuation. |
| B4 | Protocol create from browser works end to end | Seeded backend rail | PASS | `backend protocol knowledge index can create a new protocol card from the browser` passed. |
| B5 | Chart Pack create flow works end to end | Seeded backend rail | PASS | `backend chart pack index can create a new chart pack from the browser` passed; `backend chart pack quick-pick journey stays connected in the browser` also passed. |
| B6 | Method Comparison create flow works end to end | Seeded backend rail | PASS | `backend method comparison index can create a new comparison from the browser` passed. |
| B7 | Image Evidence detail keeps note-first handoff | Seeded backend rail + direct current runtime | PASS | Seeded rail `backend image evidence viewer loads a registered bundle and keeps note handoff on the real route` passed. During the audit run, current runtime now also contains `imageev_current_runtime_smoke_20260330`, and its saved-detail route shows `When to use`, `Derived from`, `Open note`, `Continue in note`, and `Continue after note review`. |
| B8 | Zero-data artifact indexes stay honest and actionable | Direct current runtime | PASS | The checklist began with `chart=0`, `image=0`, `method=0`; during execution current-runtime create/register flows produced one real chart pack, one real method comparison, and one real image-evidence bundle. Saved-detail direct-open coverage now exists for all three lanes. |

### C. Cross-Cutting Systems

| ID | Item | Verification mode | Status | Notes |
|---|---|---|---|---|
| C1 | Global `Home` does not overlap primary CTA on key dense routes | Direct current runtime + seeded rail | PASS | Current runtime geometry checks show `overlap=false` on paper detail, workbench, protocol detail, and meeting detail; seeded backend rails for note/workbench/protocol/meeting/image remained green. |
| C2 | Import PDF from Paper Notes works from the browser | Seeded backend rail | PASS | `backend paper notes index can import a local PDF from the browser` passed. |
| C3 | `/ui/*` direct-open routes stay healthy on the current runtime | Direct current runtime | PASS | Direct-open confirmed for `/ui`, `/ui/ready`, `/ui/papers`, note detail, workbench, protocol detail, meeting detail, chart index, method index, and image index. |
| C4 | Current runtime inventory is transparent about zero-data lanes | API + direct current runtime | PASS | Inventory was initially explicit as `paper-notes=121`, `meeting-packs=18`, `protocol-cards=1`, `chart-packs=0`, `image-evidence=0`, `method-comparisons=0`. During the audit run, current-runtime create/register flows raised `chart-packs`, `image-evidence`, and `method-comparisons` to `1`. |
| C5 | Runtime readiness browser flow still passes under backend coverage | Seeded backend rail | PASS | `backend runtime readiness page surfaces live runtime checks in the browser` passed. |

## Final double-check

- Direct current runtime recheck completed for:
  - `/ui`
  - `/ui/ready`
  - `/ui/papers`
  - `/ui/papers/zoteroduboisAlzheimerDiseaseClinicalBiological2024`
  - `/ui/workbench/zotero%3AduboisAlzheimerDiseaseClinicalBiological2024`
  - `/ui/protocol-cards/protocol_20260328T040041Z_6a4e5eec`
  - `/ui/meeting-packs/meetingpack_20260329T163621240532Z_journal_club_06874005`
  - `/ui/chart-packs`
  - `/ui/chart-packs/chartpack_20260330T081753Z_e439dbd9`
  - `/ui/method-comparisons`
  - `/ui/method-comparisons/methodcmp_20260330T081753Z_46782046`
  - `/ui/image-evidence`
  - `/ui/image-evidence/imageev_current_runtime_smoke_20260330`
- Seeded backend rail rerun summary:
  - 9 passed in the grouped rerun
  - plus `backend chart pack index can create a new chart pack from the browser` rerun passed
- Narrow closing rerun completed after the checklist doc was updated:
  - `GET /health` => `ok`
  - current runtime `/ui` => `Start here=1`, `Mock mode=0`
  - current runtime note detail => `Review snapshot=1`, `Save protocol card=2`, `Open in Workbench=3`
  - current runtime workbench => `Mock mode=0`, `Run deep read=true`, `consoleErrors=0`
  - current runtime chart detail => `heading=1`, `When to use=1`, `Export CSV=1`, `Home overlap=false`
  - current runtime method detail => `heading=1`, `When to use=1`, `Export CSV=1`, `Home overlap=false`
  - current runtime image-evidence detail => `heading=1`, `When to use=1`, `Derived from=1`, `Open note=1`, `Continue in note=1`, `Continue after note review=1`, `Home overlap=false`
  - seeded backend rail => `3 passed`
    - `backend meeting pack create keeps the continuation card and note handoff on the real route`
    - `backend paper note detail can start a protocol card with note context from the browser`
    - `backend paper note to workbench to protocol create journey stays connected in the browser`
- Final result:
  - No product blockers found in this checklist round.
  - No code changes were required during execution.
  - Current-runtime direct coverage now includes one saved chart-pack detail, one saved method-comparison detail, and one saved image-evidence detail created or registered during the audit run.
