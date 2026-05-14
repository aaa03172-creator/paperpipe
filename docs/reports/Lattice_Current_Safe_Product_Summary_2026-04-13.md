# Lattice Current-Safe Product Summary

Status: active summary note
Date: 2026-04-13
Owner: Runtime/product maintainers
Source inputs:
- `/Users/jangseongjin/Downloads/PaperPipe_product_discussion_summary_for_Codex.md`
- `docs/reports/PaperPipe_Product_Discussion_Summary_Fit_Review_2026-04-13.md`

Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/WEB_VIEWER.md`
- `docs/API_CHAT_CONTRACT.md`

## Purpose

Provide a current-runtime-safe restatement of the external discussion summary.

This note is for:
- product messaging grounded in the current repo
- internal alignment when future product ideas are discussed
- avoiding overclaiming `Project`, broad memory/chat, or workspace-platform status

This note is not:
- a new runtime spec
- a replacement for the canonical docs above
- approval to widen the current product shape

## 1. Product statement

Lattice is a local-first, paper-centered biomedical research workspace for a single primary operator.

It helps an operator move from:
- source paper and PDF-backed evidence
- to saved structured paper state
- to reproducible search-design work
- to bounded downstream artifacts such as meeting-ready drafts

without hiding provenance, uncertainty, or run history.

Natural language may guide the workflow, but schema-backed structured state remains the source of truth.

## 2. Current product boundary

Current product reality is:
- paper-first
- local-first
- job/run/artifact-first
- single-operator-first
- operator-reviewable
- additive rather than fully autonomous

Current main product surfaces are:
- paper-note list/detail and workbench routes
- bounded artifact viewers such as `Meeting Pack`, `Method Comparison`, `Chart Pack`, `Image Evidence`, and `Protocol Card`

Route note:
- the frontend route family is centered on `/papers`, `/papers/:slug`, and `/workbench/:paperId`
- when the backend serves the frontend shell directly, browser entry stays under `/ui/*` per `docs/WEB_VIEWER.md`

Current active bounded operator lane:
- `Research DNA`
  - real and implemented
  - API/CLI-first today
  - not yet a main web viewer route

## 3. Source-of-truth boundary

Current evidence grounding and runtime truth should be read across these layers:

1. source data
   - PDFs, Zotero-backed metadata, imported files
2. canonical structured state
   - paper-scoped `StructuredPaperState`
   - job/run/event trail
   - bounded canonical `Research DNA`
3. derived outputs and mirrors
   - note body/frontmatter mirror
   - meeting-ready and other downstream artifacts
   - compiled knowledge and review/gate artifacts

Important rule:
- canonical runtime truth lives in schema-backed structured state plus bounded canonical runtime owners
- derived outputs may explain, package, or mirror current truth
- they must not silently replace current truth

## 4. What the product is not yet

Lattice is not currently:
- a first-class project/workspace platform
- a broad memory-first research system
- a chatbot-first copilot
- a generalized decision/task/experiment operating system
- a user-facing provider marketplace or account-link hub

The repo already has some adjacent pieces:
- backend-only `Project Memory`
- project-context relevance capture
- stub-only `/api/chat`

Those pieces do not change the current product boundary.
They remain support-only, gated, or future-facing.

## 5. Current model and provider posture

Current repo posture is:
- provider choice is an implementation layer
- local ownership of data and canonical state remains primary
- hybrid provider use can exist beneath that boundary

Current implementation already has:
- local / cloud / hybrid config posture
- provider abstraction in the runtime

Current implementation does not yet have:
- a live chat product surface
- conversation persistence
- memory-first orchestration
- a polished user-facing provider onboarding surface

So the safest current wording is:
- models are important reasoning tools
- models are not the truth store
- provider breadth is secondary to parsing quality, structured state quality, and evidence-linked reviewability

## 6. Current user journey the repo can honestly support

The current repo can honestly support this bounded journey:

1. open or ingest a paper
2. inspect saved paper state and run history
3. review claims, evidence, and uncertainty in paper detail or workbench
4. optionally refine reproducible search design through `Research DNA`
5. optionally generate bounded downstream artifacts such as `Meeting Pack`

That journey is real.
It is narrower than a full project workspace or generalized research operating system.

## 7. Safe messaging rules

Prefer:
- local-first biomedical research workspace
- paper-centered biomedical research workspace
- evidence-linked paper review and downstream artifact workflow
- schema-backed structured state
- provenance-visible, operator-reviewable workflow

Avoid:
- project dashboard
- project operating system
- generalized research workspace platform
- memory-first assistant
- chatbot/copilot as the primary current identity

## 8. Safe short copy

### Current-safe one-line version

Lattice is a local-first, paper-centered biomedical research workspace that turns paper review into evidence-linked structured state and bounded downstream artifacts.

### Current-safe short paragraph

Lattice helps a single primary operator move from papers and PDFs to saved structured paper state, reproducible search-design work, and meeting-ready artifacts without losing provenance, uncertainty, or run history.

### Current-safe "what you can do today"

Today, Lattice is best understood as a paper-first runtime:
- review saved paper state
- inspect claims and evidence
- run bounded deep-read workflows
- refine `Research DNA`
- generate downstream artifacts such as `Meeting Pack`

## 9. Practical use

Use this note when:
- rewriting product-facing internal docs
- preparing demos or walkthroughs
- checking whether a new summary sentence is safe for the current repo

If a proposed sentence depends on:
- first-class `Project`
- broad memory/chat
- canonical decision/task/experiment families
- provider onboarding/product surfaces

then that sentence should stay future-only unless an explicit product-shape decision adopts it.

## Bottom line

The safest current summary is:

> Lattice is a local-first, paper-centered biomedical research workspace with schema-backed paper state, visible provenance, bounded operator workflows, and downstream artifact lanes.

That is strong enough for the current repo.
Anything broader should remain future-facing until the runtime actually adopts it.
