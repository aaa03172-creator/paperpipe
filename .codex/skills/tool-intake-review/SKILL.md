---
name: tool-intake-review
description: Conservative fit review for external repositories, parsers, libraries, and agent tooling before PaperPipe integration. Use when evaluating a GitHub link, package, parser, or framework and deciding whether it is a direct candidate, reference only, dataset only, or defer.
---

# Tool Intake Review

## Overview

This skill evaluates whether an external tool fits PaperPipe without assuming adoption.
Treat this as a fit review, not a rewrite proposal.

## Trigger Conditions

Use this skill when:
- a user shares a GitHub repository, library, parser, OCR tool, or agent framework
- the task is to judge fit against the current PaperPipe architecture
- the safest insertion point matters more than feature novelty

## Inputs And Expected Context

Gather or infer:
- the current bottleneck being discussed
- the candidate tool's likely capability
- the current subsystem that already owns the behavior

If the bottleneck is not explicit, infer it from local docs and code and label it as an inference.

## Output Contract

Return these sections:
1. `Current bottleneck`
2. `Classification`
3. `Safest insertion point`
4. `Do not rewrite these parts`
5. `Main risks`
6. `Smallest pilot`

Use exactly one classification:
- `direct candidate`
- `reference only`
- `dataset only`
- `defer`

## Workflow

1. Map the current owner first.
   If the real execution path is unclear, ask for `code_mapper` or perform equivalent read-only mapping.
2. Check the candidate against PaperPipe contracts.
   Focus on FastAPI-first core logic, Pydantic schemas, current parser/retrieval/extraction/grounding flows, and runtime skill policy boundaries.
3. Classify conservatively.
   Prefer `reference only` or `defer` when the tool duplicates a working subsystem or pushes the repo toward a rewrite.
4. Find the safest insertion point.
   Prefer optional modules, sidecar artifacts, admin-only utilities, or evaluation-only harnesses before runtime adoption.
5. State protected areas explicitly.
   Name the runtime surfaces that should not be rewritten as a first move.
6. End with the smallest pilot.
   The pilot should be bounded, measurable, and reversible.

Read [references/fit-rubric.md](references/fit-rubric.md) when the candidate touches parser, retrieval, extraction, grounding, note/export, or skills/runtime boundaries.

## Guardrails And Non-Goals

- Do not recommend replacing parsers, storage, orchestration, or note-writing flows as a first step.
- Do not confuse Codex workflow skills with PaperPipe runtime skills under `src/skills/`.
- Do not treat a broad external agent framework as a reason to redesign the repo.
- Do not skip license, operations, or schema-fit concerns just because the demo looks strong.

## Verification Or Handoff

Before any integration proposal is considered done, state:
- what was inspected
- what remains unverified
- what evidence would be needed for adoption
