# Everything Claude Code Review Prompt

Status: Historical review prompt  
Date: 2026-03-22  
Owner: Repository maintainers  
Canonical parent: `AGENTS.md`

## Purpose

Capture a PaperPipe-grounded prompt for reviewing `everything-claude-code` as an operating-pattern reference only.

This is a reusable review prompt, not an adoption plan, not a migration plan, and not a runtime spec.

## Local Environment Anchors

Any future review using this prompt should anchor to these current local contracts first:

- `AGENTS.md`
- `docs/working-files.md`
- `docs/SKILLS_PACKAGING_GUIDE.md`
- `config/skills_policy.yaml`

The reviewer should also inspect the current local `.codex/` state before recommending anything:

- whether `.codex/config.toml` exists
- whether `.codex/AGENTS.md` exists
- whether `.codex/agents/` exists
- which skills currently exist under `.codex/skills/`
- whether `.codex/work/` is already in use

Local facts the prompt is designed to preserve:

- PaperPipe already has a root `AGENTS.md`.
- PaperPipe already has a lightweight `.codex/work/<date>_<slug>/` workflow for long multi-step work.
- PaperPipe already has local skill packaging guidance and skills policy gates.
- Current priorities are stability, bottleneck identification, safe repeat-work standardization, and verification discipline.
- `.codex/config.toml`, `.codex/AGENTS.md`, and `.codex/agents/` are not guaranteed to exist and must not be assumed.

## Official Target Facts Already Verified

As of 2026-03-22, the target repository publicly shows these baseline facts:

- it presents itself as a large complete-system style repository for agent harnesses
- it includes skills, hooks, commands, rules, memory-related material, MCP configs, and other supporting surfaces
- it includes Codex-oriented material such as a reference `.codex/config.toml`, a Codex-specific AGENTS supplement, shared skills, and project-local agent role files
- the Codex section shown in the README is already substantially larger than what PaperPipe likely needs
- the repository is useful as an operating-pattern reference, but importing its overall system shape into PaperPipe would be high-risk overreach

## Prompt

```md
Task: produce a bounded fit review of operating patterns from `everything-claude-code` for PaperPipe's Codex working environment. This is an operating-pattern review, not an adoption or migration plan.

Target:
https://github.com/affaan-m/everything-claude-code

Before answering, inspect these local PaperPipe sources first and treat them as canonical:
- AGENTS.md
- docs/working-files.md
- docs/SKILLS_PACKAGING_GUIDE.md
- config/skills_policy.yaml

Also inspect the current local `.codex/` state before making suggestions:
- whether `.codex/config.toml` exists
- whether `.codex/AGENTS.md` exists
- whether `.codex/agents/` exists
- which skills currently exist under `.codex/skills/`
- whether `.codex/work/` is already used

If you find related files in `docs/archive/`, use them only as historical context, not as source of truth.

Role:
You are a senior systems architect preserving and improving a local-first biomedical research agent and its Codex working environment.

Objective:
Extract only the smallest useful operating patterns from `everything-claude-code` that could improve Codex usage in PaperPipe.
Do not treat this as a prompt to recreate the external system or to redesign PaperPipe around it.

Current local architecture facts you must anchor to:
- PaperPipe already has a root `AGENTS.md`.
- PaperPipe already has a lightweight `.codex/work/<date>_<slug>/` workflow for long multi-step work.
- PaperPipe already has local skill packaging guidance and skills policy gates.
- Current priority is stability, bottleneck identification, safe repeat-work standardization, and verification discipline.
- Current repo does not necessarily have `.codex/config.toml`, `.codex/AGENTS.md`, or `.codex/agents/`; do not assume those are already present unless local inspection confirms it.

Hard constraints:
1. Do not propose changing the project structure around `everything-claude-code`.
2. Do not propose installing, copying, or cloning the whole external repo.
3. Do not propose a full rewrite, workflow migration, config overhaul, or large multi-agent operating system.
4. Do not assume Claude-style hook execution parity exists in Codex.
5. Treat all ideas as additive, local, minimal operating patterns only.
6. Prefer the principle: small `AGENTS.md` + small `.codex` + few skills + few agents.
7. Do not make role/skill count growth a goal.
8. Mark each non-certain claim as one of:
   - `Confirmed from local repo`
   - `Confirmed from everything-claude-code`
   - `Inference`
   - `Unknown`
9. If something is not supported by local inspection or by the target repo's README/docs, say so explicitly.

Known target-repo facts you may rely on if confirmed in the target repo:
- it is a large complete-system style repository with skills, memory optimization, commands, hooks, rules, and MCP configs
- it includes Codex-oriented files such as root `AGENTS.md`, `.codex/config.toml`, `.codex/agents/*.toml`, and shared skills
- it presents Codex support as a reference configuration, not just a single config file
- the Codex portion is already much larger than what PaperPipe likely needs
- Codex should not be assumed to have Claude-style hook parity

Evaluate only these questions:

A. What to borrow
Extract only genuinely useful operating patterns for PaperPipe's Codex environment, such as:
- root `AGENTS.md` plus optional Codex-specific supplement separation
- project-local `.codex/config.toml`
- project-local `.codex/agents/*.toml`
- small skill folders for repeated procedures
- a very small number of read-only or bounded roles
- verification-first workflow
- conservative defaults
- explicit project-local over global-default preference

For each borrowed pattern, explain why it helps PaperPipe specifically.

B. What to adapt
Explain how those patterns would need to be adapted for biomedical research agent development.
Examples are acceptable only as minimal, bounded roles or skills, such as:
- `code_mapper`
- `implementation_worker`
- `architecture_guardian`
- `dependency_skeptic`
- `eval_harness_builder`
- `tool-intake-review`
- `parser-pilot-check`
- `extraction-regression-check`
- `smallest-safe-patch`

Important:
- do not present these as a required multi-agent system
- keep the set intentionally small
- prefer explicit invocation, AGENTS docs, and skill docs over hook-heavy automation
- prefer reviewer/explorer/verifier roles over role proliferation

C. What to reject
Be explicit about what does not fit PaperPipe:
- large install-script based adoption
- copying 28 agents / 116 skills / 59 commands style scale
- hook-parity assumptions for Codex
- multi-agent-by-default operation
- importing memory / continuous-learning / security system layers before current bottlenecks justify them
- treating coding meta-system optimization as more important than the biomedical product workflow

D. Current-system-safe integration
Propose only low-risk additions that preserve the current system, such as:
- tightening root `AGENTS.md`
- optionally adding a minimal project-local `.codex/config.toml`
- optionally adding a very small `.codex/agents/` set only if local evidence shows repeated need
- adding one narrow `dependency_skeptic` or `tool-review` role for external-tool fit reviews
- adding a few repeatable skill docs for recurring investigation/check patterns
- standardizing explicit verification checklists
- keeping `.codex/work` as the main persistent task-memory surface

Also assess whether the safest near-term improvement is:
1. clearer AGENTS guidance
2. one small project-local Codex config
3. one or two narrow helper roles
4. a few repeatable skills
rather than any broader systemization

E. Must-avoid mistakes
You must explicitly warn about:
- assuming a bigger operating system is automatically better
- expecting hook-driven automation despite Codex limitations
- attaching excessive multi-agent orchestration to a repo that does not need it
- optimizing coding meta-system complexity before solving actual biomedical workflow bottlenecks
- increasing role/skill count instead of improving repeatability and verification
- creating a second source of truth beside root `AGENTS.md`, `docs/working-files.md`, `docs/SKILLS_PACKAGING_GUIDE.md`, and `config/skills_policy.yaml`

Output format:
1. Executive summary
2. Current environment anchors
3. Why we should NOT adopt the full system
4. What operating patterns are genuinely useful
5. What needs adaptation for our Codex workflow
6. What should be rejected
7. Safest low-risk integrations
8. Dangerous overreach to avoid
9. Recommendation
10. Evidence and unknowns
11. Do not rewrite these parts
12. Safest next 3 experiments

Additional output requirements:
- cite local files where relevant
- separate local-repo-confirmed facts from target-repo-confirmed facts
- prefer language like `small local addition`, `optional role`, `skill doc`, `bounded helper`, `verification pattern`, `conservative default`
- avoid language implying PaperPipe should become an agent meta-framework
- if recommending `.codex/config.toml` or `.codex/agents/*.toml`, treat them as optional additions to evaluate, not assumed baseline
```

## Why This Prompt Shape Is Safer

Compared with a generic external operating-system review prompt, this version adds:

- explicit local environment anchors before any judgment
- a hard boundary around PaperPipe's existing `AGENTS.md`, `.codex/work`, skills packaging, and skills policy rails
- a warning against assuming `.codex/config.toml` or `.codex/agents/` already exist locally
- priority on minimal repeatability and verification patterns over role/skill proliferation
- a required evidence/unknown split so the target repo does not get over-interpreted as a migration template

## Sources

- https://github.com/affaan-m/everything-claude-code
