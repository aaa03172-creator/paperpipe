# Meeting Pack Verification Checklist

Use this checklist to keep reviews bounded and contract-aligned.

## 1. Bundle-local files

Confirm the presence and basic shape of:
- `meeting_pack.json`
- `meeting_pack.md`
- `acceptance_contract.json` if present
- `quality_gate.json` if present

## 2. Canonical input ownership

Check that the pack is still derived from current canonical inputs:
- paper-side structured state
- explicitly named source artifacts
- `Research DNA` or bounded selector metadata

Reject wording that makes the pack look like a new canonical research state.

## 3. Trace visibility

Confirm:
- `GET /meeting-packs/{pack_id}/trace` works
- trace explains selector/load behavior
- trace remains operational metadata only

## 4. Regenerateability and validate

Confirm:
- `GET /meeting-packs/{pack_id}/validate` is available
- `can_regenerate` matches current selector resolvability
- bundle-level readiness and markdown sync are surfaced honestly

## 5. Derived artifact honesty

Confirm:
- pack wording does not overstate uncertain or unresolved evidence
- context-only inputs are not promoted into canonical scientific truth
- `meeting_pack.md` stays a deterministic rendering of saved bundle state

## 6. Smallest follow-up framing

If there is a problem, classify it as one of:
- source selection drift
- trace visibility gap
- validate/regenerate mismatch
- bundle/local markdown sync drift
- readiness wording drift

Prefer a bounded patch over a schema rewrite.
