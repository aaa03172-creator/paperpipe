# Prompt Review 03: Fireauto Reference Extraction (2026-03-11)

Status: Historical prompt fit review  
Date: 2026-03-11  
Owner: Repository maintainers  
Canonical parent: `docs/Pending_PR_Queue.md`

## Source References
- Reference repo: [imgompanda/fireauto](https://github.com/imgompanda/fireauto)
- Reviewed source files:
  - `README.md`
  - `plugin/commands/team.md`
  - `plugin/commands/loop.md`
  - `plugin/hooks/hooks.json`
  - `plugin/hooks/stop-hook.sh`
  - `plugin/agents/team-coordinator.md`
  - `plugin/` directory layout (`agents/`, `commands/`, `hooks/`, `scripts/`, `skills/`)

## Reference Summary
`fireauto` is not a runtime architecture reference for PaperPipe. It is closer to a Claude-Code-oriented plugin pack that wraps:
- command documents as task entrypoints
- lightweight agent role files
- shell hooks/scripts for loop control
- team/worktree operating patterns for parallel execution

The useful import is not the product surface. The useful import is the packaging discipline around operator-facing commands.

The most relevant patterns are:
1. Command docs as explicit entrypoints.
   - `plugin/commands/*.md` gives each operation a narrow, documented invocation surface.
2. Role separation for coordinated work.
   - `team.md` and `team-coordinator.md` separate coordinator responsibilities from worker responsibilities.
3. File-boundary discipline in parallel work.
   - The `/team` flow explicitly instructs workers to stay inside assigned file ranges and merge in a defined order.
4. Bounded iteration contract.
   - `/loop` uses explicit max-iteration and completion conditions rather than open-ended "keep trying" behavior.
5. Minimal runtime glue.
   - Most behavior is encoded in markdown commands and a small shell hook/script layer, not a large framework.

The rest is not a fit for PaperPipe core:
- SEO/reddit/boilerplate install flows
- DaisyUI-oriented UI generation
- Claude plugin-specific team tools (`TeamCreate`, `TaskCreate`, `SendMessage`) as if they were application features

## Current PaperPipe Fit
This prompt is useful as inspiration, but not in its current form.

Current PaperPipe already has:
- skill action API/runtime:
  - `backend/routers/skills.py`
  - `src/skills/runner.py`
  - `src/skills/policy.py`
- canonical runtime state/audit:
  - `.pp/<slug>/runs/<ts>_<action>.json`
  - `.pp/<slug>/state.json`
  - `pp.signals`
- canonical backlog/work queue doc:
  - `docs/Pending_PR_Queue.md`
- document naming rules that push reference notes and fit reviews into:
  - `docs/archive/`

Also important:
- `blueprints/` does not exist yet in the repo.
- A blueprint/runtime split was only reviewed conceptually in `Prompt_Review_02`; it has not been implemented.
- Therefore `blueprints/commands` is premature unless that broader blueprint lane is intentionally started first.

## What Should Change
1. Treat `fireauto` as an operator workflow reference, not a core product dependency.
   - No plugin runtime import.
   - No attempt to mirror its full directory structure into PaperPipe.

2. Do not create `docs/PARKING_LOT.md`.
   - This repo already uses `docs/Pending_PR_Queue.md` as the working queue.
   - Fireauto-derived later ideas should be parked there, not in a parallel backlog file.

3. Be careful with `blueprints/commands`.
   - If blueprint/runtime separation is not started, prefer a dated reference note or runbook proposal.
   - If that separation is started later, `blueprints/commands/` can describe operator-facing command specs, but should not duplicate `config/skills_policy.yaml`, `AGENTS.md`, or current runbooks.

4. Reframe `/team` as engineering process guidance only.
   - The transferable part is task partitioning, file-boundary ownership, and ordered merge/verification.
   - The non-transferable part is the Claude-plugin-specific toolchain (`TeamCreate`, `TaskCreate`, `SendMessage`).

5. Reframe `/loop` as a bounded evaluation loop, not a shell-hook session trap.
   - The useful part is: fixed prompt, explicit stop condition, capped retries/iterations, preserved artifacts.
   - The non-transferable part is the stop-hook that blocks session exit and reinjects prompts.

## Adapted Prompt
Use this version instead of the original prompt:

```text
Reference repo: https://github.com/imgompanda/fireauto

Goal:
Do not adopt fireauto into PaperPipe core.
Extract only the small operator/workflow patterns that can improve PaperPipe development discipline.

Tasks:
1) Review the repository README and the `plugin/` layout (`agents/`, `commands/`, `hooks/`, `scripts/`, `skills/`).
   Summarize at most 5 patterns that are actually relevant to PaperPipe.

2) Evaluate two specific questions against the current PaperPipe architecture:
   - Could a document-driven command layer make sense later, potentially as `blueprints/commands/`, without duplicating `AGENTS.md`, `config/skills_policy.yaml`, or existing runbooks?
   - Could the `/team` and `/loop` ideas be translated into PaperPipe engineering/ops workflows as:
     - bounded parallel task partitioning
     - bounded improvement/evaluation loops
     rather than as plugin-specific runtime features?

3) Deliverables for a later implementation or documentation pass:
   - a dated reference note under `docs/archive/` summarizing "adopt no / borrow selectively"
   - 1-2 parked follow-up items added to `docs/Pending_PR_Queue.md`

Scope limits:
- skip SEO, reddit lead generation, boilerplate installers, and other non-core product flows
- skip DaisyUI-specific UI paths because PaperPipe uses shadcn-based UI standards
- do not introduce Claude-plugin-specific team/task abstractions into PaperPipe runtime
- do not create a new backlog system outside `docs/Pending_PR_Queue.md`

Acceptance:
- the extracted patterns are limited to PaperPipe-relevant engineering/ops workflows
- the output clearly separates what is transferable from what is fireauto-specific
- any future `blueprints/commands` idea is explicitly gated on a real blueprint/runtime split, not assumed to exist already
```

## Recommended Future Path
If this prompt is executed later, the clean order is:
1. write one dated reference note in `docs/archive/` describing the few adopted ideas and the rejected surface area
2. park only 1-2 concrete follow-ups in `docs/Pending_PR_Queue.md`
3. only consider `blueprints/commands/` after the broader blueprint/runtime split becomes real

This keeps `fireauto` in the right role: a reference for operator packaging patterns, not a second architecture template.
