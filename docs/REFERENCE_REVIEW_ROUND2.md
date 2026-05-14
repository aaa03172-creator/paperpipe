# Reference Review Round 2

Status: Active review note  
Date: 2026-03-18  
Owner: Repository maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Purpose
Re-review only the external references that still seem worth studying and extract the parts that are actually useful for PaperPipe.

This note is intentionally narrow:
- keep biomedical / medical literature workflows first
- keep `Research DNA`, pilot screening, refine, and lock loops first
- keep claim/evidence-linked storage and Meeting Pack generation first
- keep local-first, reproducible, evidence-linked design first
- reject anything that adds framework weight without clear ROI

## Executive Call

What is worth borrowing now:
- `anthropics/skills`: packaging structure only
- `planning-with-files`: persistent working-file discipline only

What is worth remembering for later, but not implementing now:
- `deer-flow`: config vocabulary and modular loading ideas only
- `taste-skill`: UI quality guardrails only
- `UI-Friend-MCP`: optional frontend preview workflow only

What not to do:
- no framework migration
- no Claude-specific runtime import
- no LangGraph / super-agent harness adoption
- no plugin or hook system as PaperPipe product/runtime
- no heavy frontend tooling becoming a core dependency

## 1. `anthropics/skills`

### What it actually is
An example repository for Anthropic's skill system. The useful part is not the runtime itself; it is the folder-based packaging pattern around `SKILL.md`, `spec/`, and `template/`.

### Why it is or is not relevant to PaperPipe
Relevant:
- PaperPipe already uses local skills and already needs a clean packaging rule for future biomedical workflow helpers.
- The repo reinforces the idea that one skill should stay small at the top level and move heavy detail into selective subfiles.

Not directly relevant:
- PaperPipe does not use Claude plugin/runtime assumptions as product infrastructure.
- Some bundled document skills are source-available rather than fully open source, so copying content is the wrong move.

### Extracted patterns

| Pattern | Why it matters for PaperPipe | Priority | Smallest PaperPipe adaptation |
| --- | --- | --- | --- |
| Folder-per-skill with one required `SKILL.md` | Fits future biomedical workflow skills without inventing a second runtime | P0 | docs only |
| Keep `SKILL.md` short and push depth into `references/`, `examples/`, `templates/`, `scripts/` | Good fit for selective context loading and low-noise operator guidance | P0 | docs only |
| Separate packaging spec/template from runtime policy | Helps avoid mixing authoring docs with `config/skills_policy.yaml` and Pydantic contracts | P1 | docs only |
| Minimal metadata in frontmatter (`name`, `description`) | Useful if PaperPipe later exposes skill metadata more formally | P1 | config/schema only |

### Smallest adaptation proposal
No runtime change is needed now.

The smallest useful PaperPipe-native move is:
- keep using `docs/SKILLS_PACKAGING_GUIDE.md` as the canonical translation of this pattern
- add future biomedical skills only under `.codex/skills/<skill>/` with short `SKILL.md` plus selective support folders

### What not to copy
- Claude plugin marketplace flows
- Anthropic-specific tool/runtime assumptions
- source-available document skill bodies
- Anthropic eval/benchmark orchestration as PaperPipe runtime

## 2. `planning-with-files`

### What it actually is
A skills/plugin package for AI coding tools that pushes long tasks into persistent markdown files like `task_plan.md`, `findings.md`, and `progress.md`, plus hook-based reminders and session-recovery behavior.

### Why it is or is not relevant to PaperPipe
Relevant:
- The core pattern is high ROI for long PaperPipe work because it reduces goal drift and keeps findings outside the chat window.
- PaperPipe already adopted the right subset in `docs/working-files.md`.

Not directly relevant:
- The plugin/hook ecosystem is IDE-specific and not a product/runtime concern for PaperPipe.
- Session recovery, hook automation, and cross-IDE install surface are much broader than PaperPipe needs.

### Extracted patterns

| Pattern | Why it matters for PaperPipe | Priority | Smallest PaperPipe adaptation |
| --- | --- | --- | --- |
| Task-local `plan.md`, `findings.md`, `progress.md` | Strong fit for multi-step backend/docs/reference work | P0 | small workflow rule |
| Re-read `plan.md` before major decisions or broad edits | Prevents scope drift in long PaperPipe tasks | P0 | small workflow rule |
| Log verification results and failed attempts in `progress.md` | Useful for reproducible engineering work and later resume | P1 | small workflow rule |
| Automatic hook enforcement | Adds operational complexity without helping product scope | P2 | do not apply now |
| Session recovery and IDE/plugin distribution | Outside PaperPipe's product/runtime boundary | P2 | do not apply now |

### Smallest adaptation proposal
This pattern is already mostly absorbed.

The smallest further PaperPipe adaptation is:
- keep using `docs/working-files.md`
- apply it consistently for long reference reviews, Research DNA changes, and multi-phase backend work

### What not to copy
- hook systems
- plugin command/autocomplete surface
- session-recovery machinery
- benchmark marketing framing

## 3. `bytedance/deer-flow`

### What it actually is
A broad open-source "super agent harness" with sub-agents, skills, memory, sandboxing, channels, and a large configuration surface.

### Why it is or is not relevant to PaperPipe
Relevant:
- It contains a few useful configuration and packaging ideas.
- It is a good negative example for scope control: useful concepts exist, but the full system is far too broad for PaperPipe.

Not directly relevant:
- PaperPipe should not migrate to DeerFlow, LangGraph, or a general super-agent runtime.
- Memory platform work, messaging channels, and commercial search/crawling integrations are off-scope for current biomedical priorities.

### Extracted patterns

| Pattern | Why it matters for PaperPipe | Priority | Smallest PaperPipe adaptation |
| --- | --- | --- | --- |
| Progressive skill modularization/loading | Useful vocabulary for future PaperPipe-local skill packaging | P1 | docs only |
| Config-driven execution mode flags and budgets | Could later help name bounded modes for search/eval or pack generation | P1 | config/schema only |
| Sandbox abstraction vocabulary | Relevant only if current `native` vs `docker` action policy becomes insufficient | P2 | optional tooling |
| Memory thresholds and injection budgets | Not worth reopening until chat/memory becomes an explicit product lane | P2 | do not apply now |
| Sub-agent harness, messaging channels, commercial integrations | High complexity, low current ROI | P2 | do not apply now |

### Smallest adaptation proposal
Do not change runtime now.

The smallest valid adaptation would be one later doc/config change only:
- if PaperPipe needs explicit bounded execution modes later, add them to the existing policy/schema lane rather than importing DeerFlow concepts wholesale

### What not to copy
- DeerFlow runtime or framework
- LangGraph-centered architecture
- long-term conversational memory as a default platform feature
- InfoQuest or other external/commercial integrations
- messaging-channel scope

## 4. `Leonxlnx/taste-skill`

### What it actually is
A set of prompt/skill files that pushes AI-generated frontend work away from generic template output and toward more intentional visual design.

### Why it is or is not relevant to PaperPipe
Relevant:
- Only for viewer-facing surfaces, where generic AI UI would weaken the product.
- Its best value is as a reminder to set a clear visual bar before editing an existing screen.

Not directly relevant:
- PaperPipe is not a marketing-site project.
- Biomedical workflow clarity matters more than "premium" visual styling.

### Extracted patterns

| Pattern | Why it matters for PaperPipe | Priority | Smallest PaperPipe adaptation |
| --- | --- | --- | --- |
| Ban generic, interchangeable UI output | Good guardrail for `/papers`, workbench, and Meeting Pack viewer surfaces | P1 | UI guideline |
| Explicit variance / motion / density budget | Useful for keeping UI reviews concrete instead of subjective | P1 | UI guideline |
| Redesign existing screens before rebuilding from scratch | Fits PaperPipe's incremental UI evolution | P1 | UI guideline |
| "Premium" visual language and heavy animation defaults | Risks distracting from evidence-reading workflows | P2 | do not apply now |

### Smallest adaptation proposal
No dependency or copied skill is needed.

The smallest useful PaperPipe adaptation is:
- when a viewer/workbench screen is changed, state intended density and motion budget in the matching UX review artifact

### What not to copy
- landing-page aesthetics as a default UI direction
- heavy animation libraries or motion-first design
- any second theme/token system
- taste-skill files copied directly into runtime

## 5. `beyondworks/UI-Friend-MCP`

### What it actually is
An MCP server for frontend iteration that provides live preview, viewport switching, element inspection, screenshots, and export to multiple frameworks.

### Why it is or is not relevant to PaperPipe
Relevant:
- It could speed up frontend iteration when PaperPipe is actively working on viewer surfaces.
- The inspector and screenshot loop can help produce faster UX review evidence.

Not directly relevant:
- It should never become a dependency of the PaperPipe product pipeline.
- Export-to-many-frameworks is the wrong direction for a repo with an already-set stack.

### Extracted patterns

| Pattern | Why it matters for PaperPipe | Priority | Smallest PaperPipe adaptation |
| --- | --- | --- | --- |
| Live preview with quick file-update loop | Useful only as optional local productivity tooling | P1 | optional tooling |
| Responsive viewport switching and screenshots | Helpful for faster UX review evidence | P1 | optional tooling |
| Element inspector with source location | Can reduce frontend debugging time on complex surfaces | P1 | optional tooling |
| Multi-framework export | Conflicts with PaperPipe's fixed runtime stack | P2 | do not apply now |
| Session-level design token injection | Not needed because PaperPipe already has `--pp-*` tokens | P2 | do not apply now |

### Smallest adaptation proposal
If frontend iteration becomes the bottleneck later, run a tiny local spike only:
- use it as an external preview helper
- do not wire it into backend/runtime/product dependencies
- do not use export features

### What not to copy
- framework export workflow
- a parallel theme/token layer
- MCP dependency inside the PaperPipe runtime
- preview tooling as a prerequisite for normal development

## 6. Earlier Reference Recheck

These were already reviewed in the repo. They are still worth classifying again against today's priorities.

| Earlier reference | Current PaperPipe judgment | Keep / skip now | Smallest adaptation if reopened |
| --- | --- | --- | --- |
| `karpathy/autoresearch` | Still useful for fixed eval harness + keep/discard discipline | Keep the pattern | config/schema only around search evaluation |
| `Auton` | Blueprint/runtime split is still later-only | Skip now | docs only if `/skills/run` hardening reopens |
| `fireauto` | Only bounded loop and file-boundary ownership still matter | Keep narrow | small workflow rule |
| `DeerFlow` | Same as above: reference only, no migration | Keep narrow | docs only |
| `OpenViking` | Observable retrieval trace still has real value for note/pack/source loading | Keep for later | config/schema only |
| `Research DNA` prompt lane / deep research fit reviews | Already absorbed into active `docs/RESEARCH_DNA.md` and runtime | Already active | do not reopen as separate framework lane |

### Net conclusion from earlier references
The only previous external ideas that still look materially helpful are:
- fixed search evaluation + keep/discard discipline
- explicit source trace / retrieval trajectory
- bounded engineering loops and persistent working files

Everything else should stay reference-only or already-absorbed.

## 7. Cross-Reference Synthesis

Across all references, the highest-ROI PaperPipe-native patterns are:

### P0 worth applying now
- Keep skill packaging folder-based and minimal, using the existing `docs/SKILLS_PACKAGING_GUIDE.md` rules.
- Keep using the working-files triad for long tasks and re-read `plan.md` before major edits.
- Continue treating `Research DNA` plus fixed search evaluation as the real product lane, not any external framework.

### P1 worth documenting for later
- Add explicit source-trace / retrieval-trajectory contracts for Meeting Pack and paper-note context assembly.
- Add bounded execution-mode vocabulary only if existing actions need it.
- Add UI-review density/motion intent when viewer-facing screens are changed.
- Keep optional local preview tooling available as a productivity experiment, not as product architecture.

### P2 do not apply now
- framework/runtime migration of any kind
- chat memory platform work
- sub-agent orchestration platform work
- hook/plugin systems
- framework export / parallel frontend stack ideas

## 8. Short Execution Suggestion

### Top 3 things to actually do next
1. Tighten the `Research DNA` and search-eval lane further with clearer keep/discard evidence and pilot refinement reporting.
2. Define a lightweight source-trace contract for Meeting Pack and paper-note context assembly so evidence loading is inspectable.
3. When future local biomedical skills are added, keep them inside the current folder-based packaging rule and do not let them create a second runtime contract.

### Top 3 things to explicitly skip
1. Skip DeerFlow-, Anthropic-, or plugin-style runtime adoption.
2. Skip frontend-tooling or UI-polish work that outruns biomedical search, screening, evidence storage, and meeting-pack reliability.
3. Skip any new dependency or abstraction that does not clearly improve local-first reproducibility or evidence linkage.
