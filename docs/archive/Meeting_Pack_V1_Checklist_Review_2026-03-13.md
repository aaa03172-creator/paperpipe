Status: Active review note
Date: 2026-03-13
Owner: Paper notes/runtime maintainers
Canonical parent: `docs/MEETING_PACK.md`

## Goal
Review `Meeting Pack` v1 against a practical launch checklist that matches the current PaperPipe runtime instead of a generic slide-generator rubric.

Checklist used:
1. generation works from real inputs
2. modes are meaningfully different
3. major slides are evidence-linked
4. outputs are saved as reusable structured artifacts
5. packs are editable/regenerable
6. weak/conflicting evidence is surfaced honestly
7. no fabricated numeric claims

## Evidence Reviewed
- runtime code:
  - `backend/routers/meeting_packs.py`
  - `src/schemas/meeting_pack.py`
  - `src/meeting_packs/service.py`
  - `src/meeting_packs/store.py`
  - `src/meeting_packs/renderer.py`
- regression coverage:
  - `tests/test_meeting_pack_service.py`
  - `tests/test_meeting_pack_store.py`
  - `tests/test_meeting_pack_api.py`
  - `tests/test_meeting_packs_api.py`
- real runtime probe:
  - `frontend/.e2e-backend-runtime/obsidian/.pp/zoteroduboisAlzheimerDiseaseClinicalBiological2024/state.json`
  - generated locally on 2026-03-13 for all four modes with `max_slides=5`
  - repeatable smoke command: `python3 scripts/check_meeting_pack_real_smoke.py`
  - standard local verify lane: `./scripts/run_meeting_pack_verify.sh`
  - stored-bundle drift/regenerate enforcement: `python3 scripts/check_meeting_pack_storage_sync.py --root tmp/meeting_pack_real_smoke --vault-path frontend/.e2e-backend-runtime/obsidian --require-regenerable`
- historical runtime note checked for drift:
  - `docs/archive/Meeting_Pack_Real_Probe_2026-03-13.md`

## Checklist Verdict
| Item | Verdict | Notes |
| --- | --- | --- |
| generation works from real inputs | Pass | Current service generated packs from actual runtime `state.json` in `frontend/.e2e-backend-runtime/obsidian/.pp/...`, not only from synthetic test fixtures. |
| modes are meaningfully different | Pass | `journal_club`, `literature_update`, `project_progress_update`, and `experiment_proposal` produced different overview text, opening/context slide titles, discussion prompts, expected questions, and next steps. |
| major slides are evidence-linked | Pass | For evidence-bearing packs, opening/context/claim/limits/closing slides all carried `evidence_refs[]`. When no structured evidence existed, the pack explicitly degraded to background-only with visible cautions instead of inventing support. |
| outputs are saved as reusable structured artifacts | Pass | `meeting_pack.json` and `meeting_pack.md` are saved under `storage/meeting_packs/<pack_id>/`, loadable again via store/service/API, and bundle save now rolls back on second-write failure so partial artifacts are not left behind. |
| packs are editable/regenerable | Pass | New packs persist `generation_request`, can rerender deterministic markdown from saved JSON, and can regenerate from saved intent when the current vault can still resolve the saved selector set. |
| weak/conflicting evidence is surfaced honestly | Pass | Empty-state packs degrade to background-only, context-only sources stay in caution framing, and structured `consensus_points[]` / `conflicts[]` are rendered into summary and slide caution layers. |
| no fabricated numeric claims | Pass | Current generation uses source/claim counts and caution copy, but does not synthesize study result numbers, effect sizes, or statistical claims from thin air. |

## Real Runtime Checkpoint
Observed against `zoteroduboisAlzheimerDiseaseClinicalBiological2024` in the bundled runtime vault:
- all four modes produced `5` slides with distinct framing
- `journal_club` opening/context/limits/closing slides carried `evref_01` / `evref_02`
- first discussion question, expected PI question, and next step changed by mode

Observed against `zoteroliveValidateCitations2026`:
- pack stayed draft-first and background-only
- no `evidence_refs[]` were invented
- uncertainty/caution wording explicitly said structured claims were missing

## Top 5 V1 Gaps
1. Legacy pack regenerate is now bounded rather than fully unavailable, but the policy is still narrow.
   - Old packs can rerender markdown, and regenerate is allowed only when `source_items` can be reconstructed deterministically and the current vault can still resolve them.
2. CI workflow now exists, but branch-required rollout is still operational rather than enforced by this repo alone.
   - `.github/workflows/meeting-pack-verify.yml` runs `./scripts/run_meeting_pack_verify.sh`, but on the current private repo `scripts/enable_required_checks.sh` still hits `403 Upgrade to GitHub Pro or make this repository public`, so branch-required rollout is blocked on plan/visibility rather than missing code.
3. Drift enforcement is now verify/CI scoped, not API-scoped.
   - `./scripts/run_meeting_pack_verify.sh` and `.github/workflows/meeting-pack-verify.yml` fail if freshly generated saved bundles drift or lose regenerate availability, but read endpoints still surface drift as status/warning rather than block or auto-remediate.
4. Background-only packs are now marked structurally, but downstream consumers may still ignore the field.
   - `readiness=background_only` is present, yet there is no stronger consumer-side guard that blocks accidental presentation use.
5. Regenerate lineage is recorded one step deep only.
   - `regenerated_from_pack_id` records the immediate parent pack, but not a fuller lineage chain or operator reason.

## V1 Hardening Only
Recommended order before any broader semantics or V2 work:
1. Decide whether the CI lane should be made branch-required.
   - Minimum acceptable slice: either keep `.github/workflows/meeting-pack-verify.yml` as informative CI, or roll it into required status checks explicitly.
2. Decide whether verify/CI-only drift enforcement is sufficient.
   - Minimum acceptable slice: either keep `./scripts/run_meeting_pack_verify.sh` and `.github/workflows/meeting-pack-verify.yml` as the enforcement point, or escalate drift handling in API/operator surfaces explicitly.
3. Add regenerate provenance.
   - Minimum acceptable slice: keep immediate parent lineage and decide whether full chain/operator reason is necessary for v1.
4. Add a stronger background-only readiness marker.
   - Minimum acceptable slice: keep `readiness` in the contract and ensure downstream surfaces respect it.
5. Decide whether bounded legacy regenerate fallback should remain narrow.
   - Minimum acceptable slice: either keep the current deterministic `source_items` fallback policy, or tighten/expand it explicitly.

## Judgment
`Meeting Pack` v1 is already useful as an evidence-linked draft generator and clears `7/7` checklist items in its current shape.

The remaining work is still lifecycle hardening, but no longer a blocking gap for basic v1 usefulness:
- decide whether the CI verify lane should be made branch-required
- decide whether verify-lane-only drift enforcement is sufficient
- decide how much regenerate lineage/history v1 actually needs

Those are still v1-hardening tasks and should land before reopening broader synonym expansion or looser cross-focus semantics.
