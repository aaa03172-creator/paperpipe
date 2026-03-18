# Committed Backend/API Stack Summary

Status: Active clean-replay PR-packaging note
Date: 2026-03-18
Branch observed: `codex/backend-api-packaging-stack`
Canonical parents:
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Current_Baseline_Recheck_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Backend_API_PR_Packaging_2026-03-18.md`

## 0. Purpose

Summarize the already-committed backend/API stack after `PR-M0` baseline adoption, so the next step can be PR packaging rather than more opportunistic slicing.

This note is not a new roadmap and does not reopen the baseline boundary.

## 1. Baseline Anchor

The Meeting Pack baseline runtime slice is already fixed in the repository:

- `5c09619` `feat(meeting-pack): adopt baseline runtime slice`

Implication:

- `PR-M0` is no longer a staged-candidate question
- it is a committed baseline anchor
- later additive slices should be described as follow-up commits, not as reasons to reopen `PR-M0`

## 2. Follow-Up Commit Stack After Baseline Adoption

### 2.1 Meeting Pack follow-up

- `cad2560` `feat(meeting-pack): add list and trace debug surfaces`
- `2a6966d` `feat(meeting-pack): align output mode family metadata`
- `a61785c` `fix(meeting-pack): add output mode family helper`
- `3c58fe7` `test(api): expand auth coverage for meeting-pack flows`

### 2.2 Runtime and platform hardening

- `bea989d` `fix(runtime): stabilize artifact path identity handling`
- `bd3d92a` `feat(jobs): add run event logging and persona split runtime`
- `f9be6a5` `feat(ops): add repair-stats fallback seeding route`
- `702dacb` `feat(personas): classify builtin and profile persona options`
- `ae6c252` `fix(api): require auth for meeting-pack and research-dna writes`
- `c46529b` `fix(runtime): honor db path override in downloader metrics`
- `b0eb1fe` `fix(runtime): prioritize db env override over cached path`

### 2.3 Research DNA / output contract surfaces

- `a0799f2` `feat(research-dna): add core service and projection flows`
- `8eef521` `feat(research-dna): add api wrappers`
- `0637dc7` `feat(chat): add stub contract and output mode support`
- `11acfce` `feat(output): add claimset bridge contract`

### 2.4 Paper notes / skills / obsidian / method comparisons

- `93d2db6` `feat(paper-notes): add structured detail and action catalog`
- `deef8f2` `feat(skills): add run api and structured note execution`
- `6150f43` `feat(paper-notes): enrich list search and operational signals`
- `2102f87` `feat(obsidian): add mirror and artifact inspection routes`
- `e3e2587` `feat(method-comparisons): add comparison generation api`
- `5decdc5` `test(api): cover method-comparison auth requirements`

## 3. Current Validation Snapshot

Confirmed green checks used during the latest recheck:

- `PR-M0` baseline verification command -> `97 passed`
- clean replay scoped backend/API suite -> `219 passed, 7 warnings`
- `python3 scripts/lint_docs.py` -> `docs lint passed`

Meaning:

- the committed stack is test-backed enough to package as a PR narrative
- the clean replay resolves the unrelated merge-history conflict that blocked PR `#108`
- one minimal replay-only follow-up was required to keep `load_config()` aligned with `PAPERPIPE_CONFIG_PATH`
- the current blocker is no longer runtime breakage inside the packaged backend/API scope

## 4. Remaining Dirty Tails That Should Stay Separate

These should not be silently folded into the committed stack summary:

- `/Users/jangseongjin/paperpipe/backend/main.py`
  - remaining diff is mostly route/import relocation cleanup
  - low value as a standalone follow-up unless it is bundled with a real feature lane
- `/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py`
  - remaining diff is a broader schema-contract hardening lane
  - includes `DocumentChunk` metadata expansion, `EvidenceSpan` validation, and `ScientificClaim.unknown*`
  - should be treated as a separate contract lane if reopened

## 5. Recommended Next Step

1. Treat the current stack as ready for PR/change-summary packaging.
2. Do not spend another slice on `backend/main.py` move-only cleanup.
3. If code work resumes, reopen a separate `agent_artifacts` contract-hardening lane instead of mixing it into this packaged stack.
