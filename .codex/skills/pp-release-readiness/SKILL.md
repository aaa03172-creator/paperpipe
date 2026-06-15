---
name: pp-release-readiness
description: Use for PaperPipe release, deploy, smoke-slot, CI readiness, or "is this safe to ship" checks that need a bounded verification pass and risk summary.
---

# PaperPipe Release Readiness

## Overview

Run a bounded release-readiness pass for PaperPipe. The goal is to answer whether a lane looks shippable, what failed first, and what the smallest next action is.

This skill is for verification and triage. It should not turn into broad refactoring.

## Trigger Conditions

Use this skill when the user asks about:
- release readiness
- deploy readiness
- CI or smoke-slot health
- final pre-merge or pre-demo checks
- "남은건?", "다음으로 해야 할 건?", or "배포해도 돼?" after a bounded lane

## Workflow

1. Read `AGENTS.md`.
2. Inspect current state:
   - `git status --short`
   - `git branch --show-current`
   - current diff or base/head diff when relevant
3. Identify the touched release surfaces:
   - backend API/contracts/jobs
   - frontend viewer or UX-sensitive paths
   - docs/runbooks/changelog
   - parser/extraction/provenance/evidence paths
   - dependency or packaging files
4. Choose the smallest relevant verification set.

Default PaperPipe checks, when applicable:
- backend API/contracts/jobs: `./scripts/run_backend_api_smoke.sh`
- agent or skills work: `./scripts/run_agents_smoke.sh`
- docs: `python3 scripts/lint_docs.py`
- frontend build: `cd frontend && npm run build`
- frontend existing coverage: `cd frontend && npm run verify:frontend`

Use narrower targeted pytest or Playwright checks when the changed surface is narrow.

## CI Failure Triage

When CI is failing:
1. Identify the first failing job/check.
2. Pull the shortest actionable log snippet.
3. Reproduce locally only the relevant command when practical.
4. Classify:
   - real product failure
   - test fixture/setup failure
   - flaky or environment-only failure
   - docs/lint/format failure
   - dependency/install failure
5. Recommend the smallest fix or next verification.

## Output Contract

Return:

```markdown
**Readiness**
`ready`, `blocked`, or `needs one targeted follow-up`.

**Verification**
- command: pass/fail/not run

**First Blocker**
- The first concrete blocker, if any.

**Risk Notes**
- Only risks tied to touched surfaces.

**Next Action**
- 1 to 3 PR-sized actions.
```

## Guardrails

- Do not claim release readiness without saying what was verified.
- Do not run broad suites before targeted checks unless the user asks.
- Do not modify code during a readiness pass unless the user asks to fix.
- Do not stage, commit, push, or deploy unless explicitly requested.
