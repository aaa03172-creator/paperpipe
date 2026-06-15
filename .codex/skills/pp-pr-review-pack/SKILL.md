---
name: pp-pr-review-pack
description: Use for PaperPipe PR, branch, or uncommitted-change reviews when the user asks for a code-review stance, PR readiness check, re-review, or integration review with findings first.
---

# PaperPipe PR Review Pack

## Overview

Run a conservative PaperPipe code review. This is a review workflow, not an implementation workflow.

Prioritize confirmed correctness, data integrity, security, schema/API contract drift, persisted artifact compatibility, failure paths, and missing tests. Do not recommend broad rewrites unless concrete evidence shows current behavior is unsafe or wrong.

## Trigger Conditions

Use this skill when the user asks to:
- review a PaperPipe PR, branch, worktree, diff, or uncommitted changes
- re-review after fixes
- check final integration readiness
- review architecture/API/schema/test/documentation risk for a bounded lane

## Inputs

Expected context may include:
- repository path or worktree path
- PR number, base branch, head branch, or current dirty diff
- scope, such as API contracts, paper pipeline, release readiness, test coverage, or docs boundary

If a PR number is provided and GitHub access is available, inspect PR metadata with `gh`. Otherwise use local git evidence.

## Workflow

1. Read `AGENTS.md` and apply the PaperPipe review rules.
2. Inspect git state before reviewing:
   - `git status --short`
   - `git branch --show-current`
   - relevant `git diff --stat`, `git diff`, or base/head diff
3. Classify the touched surfaces:
   - FastAPI route/API contract
   - Pydantic schema
   - DB/state transition
   - artifact generation or persisted artifact shape
   - paper ingestion/parsing/extraction/provenance
   - frontend viewer flow
   - tests/CI/docs only
   - Codex-only workflow files
4. Review failure paths first:
   - partial writes
   - orphan records
   - stale cache or stale status
   - frontend mock fallback masking backend errors
   - secret handling or user-visible local paths
   - docs that claim behavior not implemented
5. Check tests proportionally:
   - prefer targeted tests matching the touched surface
   - identify missing tests only when tied to a concrete failure mode
6. Return findings first.

## Output Contract

Use this shape:

```markdown
**Findings**
- `[P1] Title` - file:line. Impact, concrete failure mode, smallest plausible fix.

**Open Questions**
- Only questions that affect correctness or scope.

**Test Gaps**
- Tests missing for confirmed risk.

**Verification**
- Commands inspected or run. Say explicitly if not run.
```

If there are no findings, say so clearly and list residual risk or unrun checks.

## Guardrails

- Do not edit production code during a review unless the user explicitly switches from review to fix.
- Do not guess. Findings need file/line or command evidence.
- Do not stage, commit, push, or clean branches.
- Do not treat proposal/report/archive docs as authorization to change runtime behavior.
- Separate confirmed defects from residual risk and optional cleanup.
