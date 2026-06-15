---
name: pp-worktree-branch-hygiene
description: Use for PaperPipe branch, worktree, staging, cleanup, main/master alignment, backup branch, or "avoid mixing work" requests.
---

# PaperPipe Worktree And Branch Hygiene

## Overview

Keep PaperPipe branch and worktree operations explicit, reversible, and scoped. This skill is for avoiding mixed-lane damage.

Default stance: inspect and propose. Only create, delete, stage, commit, or push when the user asks.

## Trigger Conditions

Use this skill when the user asks to:
- create a clean branch for docs or a bounded lane
- inspect branch/worktree status
- clean up branches or worktrees
- resolve main/master confusion
- stage only the active lane
- avoid mixing current dirty changes with new work

## Workflow

1. Inspect before touching anything:
   - `git status --short`
   - `git branch --show-current`
   - `git worktree list`
   - `git branch -vv`
2. Classify dirty changes:
   - active requested lane
   - unrelated user changes
   - generated outputs/cache/logs
   - uncertain ownership
3. If creating a branch:
   - prefer `codex/<short-purpose>` unless the user asks for a different name
   - create from the intended base only after confirming the current branch/base from local evidence
   - for mixed dirty trees, prefer a clean worktree or branch from the merged base
4. If staging:
   - stage only files or hunks that belong to the active lane
   - never stage generated outputs or local runtime files unless explicitly requested
5. If cleaning:
   - dry-run first
   - follow `docs/Local_Backup_Branch_Retention_2026-02-24.md` for backup branch cleanup
   - require explicit apply/delete instruction before destructive actions

## Output Contract

Return:

```markdown
**Current State**
- branch, dirty summary, worktree summary

**Recommended Action**
- exact branch/worktree/staging plan

**Commands Used**
- inspection commands already run

**Needs Approval**
- destructive or irreversible operations
```

## Guardrails

- Never run `git reset --hard` or `git checkout --` unless explicitly requested.
- Never delete branches/worktrees from inference alone.
- Do not stage, commit, push, or create a PR unless the user asks.
- Preserve unrelated dirty changes.
- Keep docs-only lanes separate from runtime/API/schema lanes unless explicitly requested.
