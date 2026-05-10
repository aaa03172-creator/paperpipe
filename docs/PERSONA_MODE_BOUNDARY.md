# Persona and Output Mode Boundary

Status: Active
Date: 2026-03-17
Owner: Runtime/design maintainers
Canonical: `docs/PERSONA_MODE_BOUNDARY.md`
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Roadmap: `docs/PERSONA_MODE_ROADMAP_2026-03-17.md`

Purpose: prevent PaperPipe from turning every user-facing perspective into a separate agent or persona entry.

## Current judgment

PaperPipe should not implement every persona as a separate agent.

Instead, separate concerns into three axes:
1. core reasoning personas
2. profile context
3. output/view modes

This is narrower and cleaner than treating every audience, workflow, lab, or deliverable as a new agent.

## 1. Core reasoning personas

These are the small set of reasoning stances that affect decision criteria.

Current target set:
- `librarian`
- `researcher`
- `extractor_reviewer`

### What they change
- search and source-priority behavior
- what counts as sufficient evidence
- how conflicts, uncertainty, and missing data are surfaced
- what is treated as extraction-ready versus review-only
- how conservative the system should be when summarizing or promoting claims

### What they do not change
- UI chrome
- note layout
- template formatting
- meeting-pack slide order by itself
- reader-facing copy tone by itself

## 2. Profile context

PaperPipe already has a separate concept that should not be conflated with persona:
- `config/profiles.yaml`
- `Research DNA` projected profiles

These are not new agents.
They are domain or program context overlays:
- lab/topic focus
- query constraints
- scope filters
- scheduling and result limits

### Rule
- a profile is not a persona
- a profile should refine context inside a reasoning lane, not create a new agent family

Example:
- `researcher` reasoning persona + `coglab` profile context
- `librarian` reasoning persona + `research_dna_<dna_id>` projected profile

## 3. Output/view modes

These are presentation and delivery modes.

Current target set:
- `learner`
- `lab_meeting`
- `project_update`
- `builder_debug`

### What they change
- UI emphasis
- ordering of panels or sections
- template structure
- wording of generated outputs
- what actions or metadata are highlighted first

### What they do not change
- core evidence threshold
- core source-priority rules
- claim truth policy
- screening truth policy
- retrieval acceptance criteria

## Why this split fits PaperPipe

Current repo reality already points in this direction:
- `backend/services/job_runner.py` uses `persona_id` as a reasoning hint injected into reader behavior
- `config/profiles.yaml` stores research/query context, not distinct agent implementations
- `docs/MEETING_PACK.md` already uses `mode` to change output framing and section emphasis
- `Research DNA` uses `researcher` and `librarian` as interview rounds, which are reasoning roles, not product personas that each deserve a dedicated agent runtime

So the correct adaptation is not “more persona entries.”

The correct adaptation is:
- keep reasoning personas few
- keep profile context explicit
- keep output modes separate

## Contract implications

### Runtime reasoning
- `persona_id` should be interpreted as a reasoning-lane selector, not a generic bucket for every audience or deliverable
- do not create a separate agent/model chain for each learner/lab/project/debug surface
- if different reasoning is needed, first ask whether it is truly one of the three core reasoning personas or merely a profile/output difference

### Profiles API compatibility
- current `/personas` and `persona_id` naming can remain as a compatibility surface
- but conceptually, YAML profile entries should not be used to represent output/view modes like `learner` or `lab_meeting`
- future cleanup may rename or split these surfaces, but current runtime does not need that rename to follow the boundary

### Meeting Pack and similar generators
- meeting-pack generation should stay output-mode-driven
- mode changes can alter framing, slide structure, question style, and next-step wording
- mode changes must not silently loosen evidence truth or selector policy
- concrete `Meeting Pack` modes may map into a shared output-mode family for cross-surface consistency, but that family remains presentation-only

### Viewer and chat surfaces
- `learner` is a view/output mode
- it may simplify layout, explanation density, or glossary framing
- it should not trigger a different scientific truth policy than `researcher` or `extractor_reviewer`
- `/api/chat` may accept an additive `output_mode_family` hint, but that hint must remain presentation-oriented and must not spawn a separate chat runtime
- paper notes detail may accept an additive `view=learner|builder_debug` query param, but that switch must remain limited to panel ordering, helper copy, and UI emphasis

### Builder/debug surfaces
- `builder_debug` is an output/view mode for operational clarity
- it may expose traces, write scopes, retrieval metadata, or validation warnings
- it should not become a separate “debug agent”

## Recommended mapping for current PaperPipe surfaces

### Deep Read / job execution
- primary axis: reasoning persona
- optional overlay: profile context
- not an output-mode selector

### Research DNA intake/interview
- use `librarian` and `researcher` as reasoning roles during intake and refinement
- do not explode each interview style into a separate runtime agent

### Meeting Pack
- treat current pack `mode` values as output-mode-family variants, not personas

Practical family mapping:
- `journal_club` -> `lab_meeting`
- `literature_update` -> `lab_meeting` or `project_update` family, depending on context
- `project_progress_update` -> `project_update`
- `experiment_proposal` -> `builder_debug` family with proposal framing

This keeps current feature compatibility while making the conceptual layer cleaner.

### Paper Notes viewer
- future `learner` and `builder_debug` differences should be viewer/output-mode changes
- they should not require separate reader agents or separate profile records

## Guardrails

- Do not create a new agent just because the user wants a different audience-facing output.
- Do not encode output/view modes in `config/profiles.yaml`.
- Do not treat every lab or topic profile as a new persona family.
- Do not let output mode override evidence or screening truth.
- Do not duplicate core reasoning logic across many named personas when the difference is really a template or UI emphasis change.

## Rule of thumb

When a new “persona” request appears, classify it in this order:
1. Is this really one of the three core reasoning personas?
2. If not, is it a profile-context difference?
3. If not, is it an output/view mode?

Only if it fails all three checks should PaperPipe consider adding a new core concept.
