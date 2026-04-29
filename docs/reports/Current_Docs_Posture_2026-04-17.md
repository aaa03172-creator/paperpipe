# Current Docs Posture

Status: active posture note
Date: 2026-04-17
Owner: Runtime/product maintainers
Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`

## Purpose

Provide one current reading-order note for the repo as it exists now.

This note is intentionally narrow.
It is not:
- a new master spec
- a replacement for canonical runtime docs
- permission to widen the current product into a first-class project/workspace platform

It exists to answer a smaller question:
- which docs should someone read first to understand the current repo posture without mixing the 2026-03 first-product baseline with the later 2026-04 lane-triage and runtime-readiness work?

## Current judgment

The repo still has one stable product boundary:
- paper-first
- local-first
- job/run/artifact-first
- single-operator-first
- evidence-linked
- human-reviewable

That boundary is already well-described in:
- `docs/Product_Positioning_Principles.md`
- `docs/reports/Lattice_Current_Safe_Product_Summary_2026-04-13.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`

The main source of confusion is no longer product identity.

The main source of confusion is that the current docs tree contains:
- the 2026-03 first-product and release-closeout baseline
- the 2026-04 worktree lane triage and runtime-readiness split
- newer support-only/internal-data notes

Those layers are all useful, but they should not be read as if they are one flat "current next action" surface.

## How To Read The Repo Now

### 1. Product identity and safe wording

Read these first when the question is "what is Lattice right now?":

1. `docs/Product_Positioning_Principles.md`
2. `docs/reports/Lattice_Current_Safe_Product_Summary_2026-04-13.md`
3. `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`

Interpretation:
- these define the current paper-first product shape
- they remain the safest anchor for demos, summaries, and product wording

### 2. Current worktree and lane posture

Read these next when the question is "what should we touch next from the current mixed tree?":

1. `docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md`
2. `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`

Interpretation:
- the current dirty tree is not one coherent lane
- the safest active implementation lanes are viewer/runtime-readiness and personal-runtime packaging
- extraction/eval work should stay frozen unless it is explicitly the selected task

### 3. Support-only and internal-data boundaries

Read these only when the question is about project-context, artifact-history, or support data:

1. `docs/PaperPipe_Minimum_Operating_Principles.md`
2. `docs/reports/Internal_Data_Readiness_For_Biomedical_Workspace_2026-04-13.md`
3. `docs/reports/Artifact_History_Promotion_Posture_Decision_2026-04-14.md`

Interpretation:
- raw memory, project-context capture, artifact review feedback, and artifact generation outcomes are support layers
- they are useful for supervision, audit, and later policy discussion
- they are not a second canonical truth store

### 4. Local verification posture

Read this when local verification behaves strangely:

1. `docs/reports/Python313_Import_Health_2026-04-14.md`

Interpretation:
- use `.venv314` or the resolved verification Python path for local checks
- do not treat the broken Python 3.13 import path as a repo regression by default

## How To Interpret The Older 2026-03 "Current State" Notes

These notes remain useful:
- `docs/reports/Current_State_Update_2026-03-24.md`
- `docs/reports/Current_Concrete_Next_Actions_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

But use them carefully.

They still describe the first-product baseline and the release-closeout posture well.
They should not be the only current guidance when deciding how to split or stage the present 2026-04 mixed tree.

Practical rule:
- use the 2026-03 notes for first-product identity and release-baseline meaning
- use the 2026-04 notes for current lane selection and current docs posture

## Current recommended action order

If the goal is "clean up docs before more implementation", the safest order is:

1. docs-only entrypoint and wording cleanup
2. choose exactly one implementation lane after that:
   - viewer/runtime-readiness, or
   - personal-runtime packaging
3. keep extraction/eval frozen unless that lane is explicitly chosen
4. keep project-context and artifact-history work support-only unless a separate RFC changes that posture

## Not current priorities

Do not treat the current repo state as a reason to:
- reopen a broad architecture reset
- open a first-class `Project` runtime lane
- promote broad memory/chat as an active product surface
- bundle the whole dirty tree into one cleanup branch
- let support-only internal data become stronger truth than paper-scoped canonical state

## Short version

The current repo is not blocked on product definition.

It is blocked on document clarity and lane discipline.

Read the paper-first product docs first, then the 2026-04 lane-triage notes, and only then the support-only/internal-data notes if your task actually needs them.
