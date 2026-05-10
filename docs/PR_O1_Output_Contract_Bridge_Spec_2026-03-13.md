# PR-O1 Output Contract Bridge

Status: implemented narrow bridge  
Date: 2026-03-13

## Scope

This PR does not replace the legacy artifact schema.

It introduces a shared bridge for one concrete drift point:

- deepread `ClaimSet` payloads from `claimset.json` / `claimset.resolved.json`
- product-layer `StructuredPaperState.claimset`

## Added module

- `/Users/jangseongjin/paperpipe/src/contracts/output_bridge.py`

Primary functions:

- `normalize_claimset_payload(payload)`
- `claim_cards_from_claimset_payload(payload)`
- `bind_claim_cards_to_run(claim_cards, run_id)`

## Adoption

Current adopter:

- `/Users/jangseongjin/paperpipe/src/skills/runner.py`

Compatibility choice:

- keep `_load_claimset_payload`
- keep `_claim_cards_from_payload`
- keep `_bind_claim_cards_to_run`

These now delegate to the bridge so existing tests and imports do not break.

## Why this shape

The duplication hotspot was in `skills/runner`, where deepread claim/evidence payloads were converted into `SkillClaimCard` / `SkillClaimEvidence` with their own stable ids and locators.

Moving that logic into a contract bridge gives one reusable adapter without forcing a full schema migration in the same PR.

## Explicit non-goals

- no `grounded/resolution` evidence resolver yet
- no reader prompt/schema hardening yet
- no replacement of legacy `agent_artifacts`
- no paper-notes API rewrite

## Next adopters

1. citation grounding resolver work can reuse the bridge's claim/evidence mapping
2. paper-note detail or stats repair can reuse the same bridge if they need `StructuredPaperState`-compatible claim cards
