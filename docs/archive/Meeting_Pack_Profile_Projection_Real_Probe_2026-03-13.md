# Meeting Pack Profile Projection Real Probe (2026-03-13)

Status: Recorded runtime probe
Date: 2026-03-13
Owner: Paper notes/runtime maintainers
Canonical parent: `docs/MEETING_PACK.md`

## Goal
Verify that the reopened `project_profile` / `research_profile` selector path works against the current workspace using the real projected profile:
- `research_dna_dna_mci_medium_chain_triglycerides_probe_20260312`

## Probe Command
- service path: `generate_meeting_pack(...)`
- mode: `literature_update`
- selector:
  - `type=research_profile`
  - `ref=research_dna_dna_mci_medium_chain_triglycerides_probe_20260312`

## Observed Result
- generation rejected with:
  - `No structured paper states resolved from research_profile=research_dna_dna_mci_medium_chain_triglycerides_probe_20260312`

## Root Cause Review
The reopened profile selector logic is deterministic and does resolve the projected profile metadata correctly:
- `source_dna_id`
- `source_query_version`
- latest screened include set for that query version

However, the include-set candidates for this DNA do not currently map to existing structured paper states inside the active vault.

Implication:
- profile-backed Meeting Pack generation remains evidence-first
- it does not fall back to screening-only or query-term-only synthesis when the underlying `state.json` entries are absent

## Decision
Keep the current guard.

Why:
- relaxing to screening-only or query-term-driven generation would break the `state.json`-first truth boundary
- a clear rejection is more correct than silently inventing a pack from incomplete downstream evidence

## Follow-up
- code now raises a more specific error for this case:
  - `No structured paper states matched the included screening decisions for profile-backed selector ...`
- current support statement should therefore be read as:
  - projection-backed profile selectors are supported
  - but only when the selected include-set already exists as structured paper state in the vault
