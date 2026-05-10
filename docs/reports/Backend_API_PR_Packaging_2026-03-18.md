# Backend/API PR Packaging

Status: Open PR packaging note
Date: 2026-03-18
Branch observed: `codex/backend-api-packaging-stack`
Opened PR: `#108` `https://github.com/aaa03172-creator/paperpipe/pull/108`
Canonical parents:
- `/Users/jangseongjin/paperpipe/docs/reports/Committed_Backend_API_Stack_Summary_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Current_Baseline_Recheck_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`

## 0. Purpose

Provide a ready-to-paste PR title/body/review plan for the already-committed backend/API stack on this branch.

This note is for packaging, not for reopening scope.

Current sync status:

- the packaged backend/API stack is aligned with the current branch through the supporting docs-only tail
- use this draft as the current change-summary baseline unless a new non-doc backend/API commit lands after `2e13498`

## 1. Proposed PR Title

`backend/api: package committed Meeting Pack, Research DNA, paper-notes, skills, and method-comparison slices`

## 2. Short PR Summary

This PR packages the committed backend/API slices that landed after the Meeting Pack baseline adoption anchor.

It includes:

- Meeting Pack runtime baseline and follow-up debug/list surfaces
- additive runtime hardening for identity, jobs, ops, personas, auth, and DB-path handling
- Research DNA API/service projection surfaces and output/chat bridge additions
- papers ops-summary and artifact query routes
- paper-notes structured detail and operational list enrichment
- skills run API, Obsidian inspection routes, and method-comparison generation API

It does not reopen the baseline boundary or broaden selector semantics beyond the already-committed slices.

## 3. Ready-to-Paste PR Body

```md
## Summary

This PR packages the committed backend/API slices that now define the current biomedical core loop after the Meeting Pack baseline anchor.

Included surfaces:

- Meeting Pack runtime baseline plus list/trace debug follow-ups
- Research DNA service/API projection flows
- papers ops-summary and artifact query routes
- paper-notes structured detail and operational list signals
- skills run API and structured note execution
- Obsidian mirror/artifact inspection routes
- method-comparison generation API
- runtime/auth/persona/ops hardening that these surfaces now depend on

## Why

The branch has already moved past the "staged candidate" phase.

- the Meeting Pack baseline slice was fixed by commit `5c09619`
- the related backend/API follow-up lanes were committed separately and validated
- the remaining ambiguity is repository legibility, not runtime correctness

This PR therefore packages the committed stack without reopening baseline scope.

## Included Commit Groups

### Baseline anchor

- `5c09619` `feat(meeting-pack): adopt baseline runtime slice`

### Meeting Pack follow-up

- `cad2560` `feat(meeting-pack): add list and trace debug surfaces`
- `2a6966d` `feat(meeting-pack): align output mode family metadata`
- `a61785c` `fix(meeting-pack): add output mode family helper`
- `3c58fe7` `test(api): expand auth coverage for meeting-pack flows`

### Runtime/platform hardening

- `bea989d` `fix(runtime): stabilize artifact path identity handling`
- `bd3d92a` `feat(jobs): add run event logging and persona split runtime`
- `f9be6a5` `feat(ops): add repair-stats fallback seeding route`
- `702dacb` `feat(personas): classify builtin and profile persona options`
- `ae6c252` `fix(api): require auth for meeting-pack and research-dna writes`
- `c46529b` `fix(runtime): honor db path override in downloader metrics`
- `b0eb1fe` `fix(runtime): prioritize db env override over cached path`

### Research DNA / output contract surfaces

- `a0799f2` `feat(research-dna): add core service and projection flows`
- `8eef521` `feat(research-dna): add api wrappers`
- `0637dc7` `feat(chat): add stub contract and output mode support`
- `11acfce` `feat(output): add claimset bridge contract`

### Paper notes / skills / obsidian / method comparisons

- `3881326` `feat(papers): add ops summary and artifact query routes`
- `93d2db6` `feat(paper-notes): add structured detail and action catalog`
- `deef8f2` `feat(skills): add run api and structured note execution`
- `6150f43` `feat(paper-notes): enrich list search and operational signals`
- `2102f87` `feat(obsidian): add mirror and artifact inspection routes`
- `e3e2587` `feat(method-comparisons): add comparison generation api`
- `5decdc5` `test(api): cover method-comparison auth requirements`

## Validation

- `PR-M0` baseline verification command -> `97 passed`
- targeted post-baseline backend/API suite -> `57 passed, 7 warnings`
- `python3 scripts/lint_docs.py` -> `docs lint passed`

## Out of Scope

- `backend/main.py` remaining route/import relocation cleanup
- broader `src/schemas/agent_artifacts.py` contract hardening
- reopening Meeting Pack selector semantics
- frontend preview/polish work
```

## 4. Reviewer Guidance

Recommended review order:

1. Meeting Pack baseline anchor and follow-up commits
2. Runtime/auth/persona/ops hardening commits
3. Research DNA and output bridge commits
4. paper-notes / skills / obsidian / method-comparison commits

Reason:

- this follows the actual dependency direction
- it keeps baseline boundary questions ahead of additive feature/API surfaces

## 5. Explicit Out-of-Scope Reminder

Do not silently expand this packaged PR with:

- `/Users/jangseongjin/paperpipe/backend/main.py` move-only cleanup
- `/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py` broader schema hardening
- new frontend viewer polish
- broader Meeting Pack synonym/selector work

Current branch note:

- the branch also contains supporting docs-only commits after the packaged backend/API stack
- `d05ef99` records the packaging state and `2e13498` adds external-reference guardrails
- include them only as supporting documentation context, not as reasons to broaden the backend/API scope

## 6. If Code Work Resumes After Packaging

The highest-value next code lane is:

1. `/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py` contract hardening
   - keep it bounded to schema/test hardening first
   - current bounded rechecks are green:
     - `pytest -q tests/test_claimset_policy.py tests/test_document_artifact_v2.py tests/test_indexer_agent_chunk_ids.py tests/test_job_runner_ingest_backend.py` -> `27 passed`
     - `pytest -q tests/test_citation_grounding.py tests/test_deepread_note_writer.py tests/test_worker_job_runner_chain.py tests/test_paper_notes_api.py` -> `26 passed`
   - do not reopen reader/runtime design from this lane

The low-value next code lane is:

1. `/Users/jangseongjin/paperpipe/backend/main.py` move-only cleanup

Only after the packaging step and the bounded schema/test lane should the next separate follow-up be reopened:

1. tighten mode-specific tuning from note/context inputs without letting them override structured claim/evidence truth
