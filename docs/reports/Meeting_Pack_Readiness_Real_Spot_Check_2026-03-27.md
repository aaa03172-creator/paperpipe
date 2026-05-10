# Meeting Pack Readiness Real Spot Check (2026-03-27)

Status: Complete bounded spot check
Date: 2026-03-27
Owner: Runtime maintainers
Canonical parent: `docs/MEETING_PACK.md`

Related docs:
- `docs/MEETING_PACK.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `scripts/check_meeting_pack_real_smoke.py`

## Purpose

Validate the tightened `Meeting Pack` readiness semantics against representative real sample states without widening the contract.

This spot check was intentionally narrow:
- keep `readiness=evidence_backed` when direct structured evidence refs exist
- require explicit uncertainty when direct refs exist but `grounded` / `resolution` metadata is missing or unresolved
- avoid turning this into a grounded-only readiness RFC

## Probe Setup

Vault:
- `frontend/.e2e-backend-runtime/obsidian`

Representative checks:
- standard real-input smoke on `zoteroduboisAlzheimerDiseaseClinicalBiological2024`
- focused uncertainty inspection on:
  - `zoteroduboisAlzheimerDiseaseClinicalBiological2024` in `journal_club`
  - `zoterostructuredSkillsClaimset2026` in `experiment_proposal`

Commands:

```bash
python3 scripts/check_meeting_pack_real_smoke.py --root tmp/meeting_pack_readiness_real_smoke
python3 - <<'PY'
from pathlib import Path
from src.meeting_packs.service import generate_meeting_pack
from src.schemas.meeting_pack import MeetingPackGenerateRequest, MeetingPackSourceSelector

vault = Path("frontend/.e2e-backend-runtime/obsidian").resolve()
root = Path("tmp/meeting_pack_readiness_spot_check").resolve()
root.mkdir(parents=True, exist_ok=True)
checks = [
    ("zoteroduboisAlzheimerDiseaseClinicalBiological2024", "journal_club"),
    ("zoterostructuredSkillsClaimset2026", "experiment_proposal"),
]
for slug, mode in checks:
    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode=mode,
            source_items=[MeetingPackSourceSelector(type="paper_slug", ref=slug)],
            max_slides=5,
        ),
        vault_path=vault,
        root=root,
    )
    print(
        slug,
        mode,
        response.pack.readiness,
        response.pack.one_page_summary.key_points[0].uncertainty_note,
    )
PY
```

## Findings

### 1. Standard real-input smoke still passes

For `zoteroduboisAlzheimerDiseaseClinicalBiological2024`, all four supported modes still generated successfully:
- `journal_club`
- `literature_update`
- `project_progress_update`
- `experiment_proposal`

Observed for all four:
- `readiness = evidence_backed`
- `markdown_sync = in_sync`
- direct `evidence_refs[]` present
- slide count stayed within the bounded `5-8` range

### 2. The new uncertainty note appears on real saved state

Focused inspection confirmed the new caution appears in both:
- `one_page_summary.key_points[0].uncertainty_note`
- `one_page_summary.uncertainties[]`

Observed wording:
- `Direct evidence refs exist, but citation-grounding metadata is missing; re-check citation linkage before presentation.`
- `At least one evidence-linked claim is still missing or unresolved citation-grounding metadata; re-check citation linkage before presentation.`

### 3. Current representative sample states still lack grounding metadata

The sampled e2e runtime states currently preserve direct evidence refs but do not preserve resolved grounding metadata:
- `grounded = null`
- `resolution = null`

That means the new caution is expected and truthful under the current contract. It should not be treated as a regression by itself.

## Judgment

The bounded runtime patch behaves as intended on representative real samples:
- `Meeting Pack` no longer treats bare claim presence as enough for `evidence_backed`
- packs with real direct evidence refs still stay usable
- missing grounding metadata is now visible instead of silently looking citation-verified

This spot check does **not** justify a stricter grounded-only readiness gate yet.

## Remaining Risk

- Current representative saved states still do not preserve `grounded` / `resolution`, so many real packs will carry the new uncertainty note by default.
- That is acceptable for the current bounded contract, but it means `evidence_backed` still should not be read as “citation-verified.”
- If product/release pressure later demands a stronger trust signal, the next lane should be a separate RFC about preserving grounding metadata through `MeetingPackEvidenceRef`, not another ad hoc readiness tweak.
