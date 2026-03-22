# Skills Packaging Guide

Status: Active
Date: 2026-03-17
Owner: Skills maintainers
Canonical: `docs/SKILLS_PACKAGING_GUIDE.md`

Purpose: define how future PaperPipe-local skills should be packaged and documented, using external skill repositories as design reference only.

## Reference stance

Use external repositories such as [Anthropic skills](https://github.com/anthropics/skills) as packaging and authoring reference only.

Do not:
- add a direct runtime dependency on Anthropic skill infrastructure
- assume Claude-specific hooks, slash commands, artifacts, connectors, or subagent features exist in PaperPipe
- copy source-available skill content, examples, templates, or scripts until license boundaries are checked and the project policy explicitly allows it

Reason:
- PaperPipe already has its own runtime/action contract under `config/skills_policy.yaml` and `src/skills/`
- the Anthropic repository uses mixed per-skill licenses rather than one uniform reusable license
- some skills include client/runtime assumptions that do not map cleanly onto FastAPI-first PaperPipe

## What to borrow

These patterns are useful and should be reused in a PaperPipe-native form:
- folder-based skill packaging with one required `SKILL.md`
- minimal trigger metadata in `SKILL.md` frontmatter
- progressive disclosure: short `SKILL.md`, heavy detail in bundled files
- separation between workflow instructions, references, examples, templates, and helper scripts
- domain-specific skill folders instead of one giant all-purpose biomedical skill

## What not to borrow

Do not adopt these as-is:
- Claude-only runtime hooks or plugin systems
- tool names like `create_file`, `str_replace`, or artifact-specific assumptions
- benchmark/eval infrastructure that depends on Anthropic-specific orchestration
- large copied skill bodies from mixed-license or source-available folders

## Recommended PaperPipe layout

Future local skills should live under `.codex/skills/<skill-name>/` and use this shape when the task warrants it:

```text
.codex/skills/<skill-name>/
  SKILL.md
  references/        # optional, background docs or checklists
  examples/          # optional, example prompts, inputs, outputs, edge cases
  templates/         # optional, reusable output skeletons
  scripts/           # optional, deterministic helpers
  assets/            # optional, static local assets only when truly needed
  LICENSE.txt        # required only when copied third-party content is permitted
  NOTICE.md          # optional provenance and adaptation notes
```

Use the smallest subset that solves the problem. Many skills should remain just `SKILL.md` plus one small `references/` file.

## Codex workflow boundary

PaperPipe distinguishes between:
- Codex-only developer workflow helpers
- product runtime skills exposed through PaperPipe

Codex-only workflow helpers may live under:
- `.codex/skills/<skill-name>/` for local workflow skills
- `.codex/agents/<agent-name>.toml` for narrow custom subagents used during development

These are developer tooling only. They must not be treated as product runtime features by folder presence alone.

Current minimal developer-workflow set:
- `tool-intake-review`
- `smallest-safe-patch`
- `code_mapper`
- `architecture_guardian`

Optional next-layer helper:
- `eval_harness_builder`

Purpose:
- `tool-intake-review`: conservative fit review for external repos, libraries, parsers, and frameworks
- `smallest-safe-patch`: map-first, minimal-edit workflow for additive fixes
- `code_mapper`: read-only execution-path and ownership mapper
- `architecture_guardian`: read-only guard against rewrites, schema drift, and dependency overreach
- `eval_harness_builder`: bounded evaluation and regression harness builder that should reuse existing `goldset/`, `scripts/eval/`, `baselines/`, `snapshots/`, and targeted test paths before creating new eval surfaces

Rule:
- use these to support safe development decisions
- do not wire them into FastAPI routes, `src/skills/`, or user-facing runtime flows unless a separate product contract adopts that behavior

## `SKILL.md` guidance

Keep `SKILL.md` as the routing and workflow document, not the dump site for every detail.

Recommended frontmatter:

```yaml
---
name: example-skill
description: What the skill does and when to trigger it.
license: MIT
---
```

Rules:
- `name` and `description` are the only required metadata fields
- `license` is optional and should be included only when it clarifies bundled content provenance
- do not rely on Claude-specific frontmatter fields as runtime requirements
- keep network, sandbox, and secret policy out of `SKILL.md`; those belong in `config/skills_policy.yaml` and runtime/UI policy surfaces

Recommended body structure:
1. Overview
2. Trigger conditions
3. Inputs and expected context
4. Output contract
5. Workflow or decision tree
6. Bundled resource map
7. Guardrails and non-goals
8. Verification or handoff expectations

## Resource separation rules

### `references/`
- use for stable background material, checklists, domain rules, and longer how-to details
- keep `SKILL.md` short and point to the right reference file instead of embedding everything inline
- separate by variant when domains differ materially

### `examples/`
- use for realistic prompts, sample inputs, expected outputs, and edge cases
- examples are not the canonical spec and should not silently override contracts

### `templates/`
- use for repeatable output skeletons such as intake briefs, screening summaries, or meeting-pack section layouts
- templates should express output shape, not runtime truth

### `scripts/`
- use for deterministic transforms, validators, or report assembly helpers
- scripts are helpers, not the canonical product contract
- if a script becomes product-critical, move the core logic behind FastAPI and Pydantic contracts instead of leaving it skill-only

## Progressive disclosure rule

Apply a three-layer model:
- layer 1: `SKILL.md` for trigger and routing
- layer 2: `references/`, `examples/`, `templates/` for selective context loading
- layer 3: `scripts/` for deterministic execution

This keeps the trigger surface short while preserving depth where needed.

## Relationship to PaperPipe runtime

Folder presence alone does not create a product feature.

If a skill will be user-visible or callable through PaperPipe runtime:
- define or extend the action in `src/skills/registry.py`
- define policy gates in `config/skills_policy.yaml`
- keep the request/response/state contract in `src/schemas/skills.py` or another appropriate Pydantic schema
- store durable outputs in canonical roots such as `.pp/<slug>/state.json`, `research_dna/`, or `storage/meeting_packs/`
- keep note frontmatter and markdown summaries as derived surfaces, not the primary store

## Design patterns by skill family

### 1. Librarian / researcher intake skills

Type:
- workflow-oriented with structured document outputs

Recommended packaging:

```text
.codex/skills/librarian-intake/
  SKILL.md
  references/
    source-priority.md
    identifier-normalization.md
  templates/
    intake-brief.md
    intake-checklist.md
  examples/
    intake-prompts.md
  scripts/
    normalize_identifiers.py
```

PaperPipe rule:
- output should normalize into structured intake data or note sidecar state, not remain a free-form chat artifact
- keep DOI, PMID, Zotero, and local vault identifiers explicit

### 2. Screening / review skills

Type:
- workflow-oriented, policy-heavy

Recommended packaging:

```text
.codex/skills/screening-review/
  SKILL.md
  references/
    inclusion-exclusion.md
    evidence-thresholds.md
    review-checklists.md
  templates/
    screening-decision.md
    review-summary.md
  examples/
    accepted-vs-rejected.md
```

PaperPipe rule:
- inclusion/exclusion, evidence quality, and review outputs must remain consistent with `Research DNA`, reviewer workflows, and existing structured review state
- do not invent a second screening truth in skill-local markdown files

### 3. Meeting-pack generation skills

Type:
- document-oriented workflow wrapper over an existing canonical contract

Recommended packaging:

```text
.codex/skills/meeting-pack-generation/
  SKILL.md
  references/
    source-selection.md
    mode-guide.md
  templates/
    journal-club.md
    experiment-proposal.md
  examples/
    source-selector-examples.md
```

PaperPipe rule:
- `docs/MEETING_PACK.md` remains the canonical contract
- the skill should help choose inputs, mode, and verification steps, not redefine pack schema or storage shape
- generated packs must still land in `storage/meeting_packs/<pack_id>/`

### 4. Future biomedical workflow skills

Type:
- domain-variant workflows with shared core steps

Recommended packaging:
- keep a shared workflow in `SKILL.md`
- split domain-specific knowledge into `references/` by modality, evidence type, or data source
- avoid one monolithic “biomedical super skill”

Example:

```text
.codex/skills/biomedical-workflow/
  SKILL.md
  references/
    clinical-trials.md
    observational-studies.md
    biomarker-papers.md
```

PaperPipe rule:
- variant-specific guidance should stay additive and selective
- durable biomedical outputs still need the repo’s canonical contracts and pathing rules

## License and provenance rule

Before copying any third-party skill text, scripts, templates, or examples:
1. identify the exact file-level or skill-level license
2. confirm it is compatible with PaperPipe’s intended use
3. record provenance in `NOTICE.md` or an equivalent project doc
4. adapt the material into PaperPipe terminology and contracts instead of pasting it verbatim

If the license is unclear, restrictive, source-available, or client-bound:
- do not copy the content
- borrow only the structural idea

## Authoring rule of thumb

For PaperPipe, a good skill package should:
- trigger clearly from user intent
- stay short at the top level
- defer heavy detail to bundled resources
- point back to canonical product contracts
- avoid inventing new runtime truth
- stay license-clean and repo-portable
