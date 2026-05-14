# Chart / Figure Provenance Checklist

Use this checklist to keep visual artifact reviews narrow and honest.

## 1. Identify the artifact family

Classify the saved artifact as one of:
- `Chart Pack`
- `Image Evidence`
- `Method Comparison`
- another explicitly bounded visual artifact family

Then open the matching active spec before judging behavior.

## 2. Confirm the primary bundle-local manifest

Check which file is the primary bundle-local manifest:
- `chart_pack.json`
- `image_evidence.json`
- `comparison.json`

Confirm sibling files remain derived bundle members rather than hidden truth stores.

## 3. Check source/canonical/derived separation

Verify:
- source data is still named explicitly
- canonical structured state remains elsewhere in current runtime roots
- visual outputs remain derived artifacts

Reject any change that makes a visual artifact look like the new canonical truth.

## 4. Check warnings and uncertainty visibility

Confirm that warning-heavy, sparse, missing, or conflict states are still visible in:
- saved bundle metadata
- exports
- viewer UI

Do not allow polish to erase caution.

## 5. Check provenance and traceability

Confirm:
- source refs are visible
- transform steps or view-state provenance remain inspectable when applicable
- trace or validate metadata stays operational and additive

## 6. Choose the smallest follow-up

If there is a problem, classify it as one of:
- provenance visibility gap
- warning suppression
- bundle-local manifest drift
- source selection ambiguity
- viewer wording drift

Prefer a bounded hardening patch over any broad schema or platform expansion.
