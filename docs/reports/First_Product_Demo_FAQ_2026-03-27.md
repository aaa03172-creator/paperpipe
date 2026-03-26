# First Product Demo FAQ

Status: Active handoff note
Date: 2026-03-27
Owner: Lattice runtime maintainers
Purpose: give the presenter short, repo-grounded answers to the most likely first-product demo questions.
Canonical parents:
- `docs/reports/First_Product_Demo_Runbook_2026-03-27.md`
- `docs/reports/First_Product_Baseline_QA_2026-03-25.md`

## 1. What is this product, in one sentence?

Lattice is a local-first, paper-centered biomedical research workspace for one primary operator, built around structured evidence state, reproducible search design, and meeting-ready downstream artifacts.

## 2. What is the source of truth here?

The source of truth is Lattice-owned structured state:

- note-side `StructuredPaperState`
- run / job / event trail
- `ResearchDNA`

The UI, summaries, and packs are not the root truth.

## 3. Is this basically a chatbot for papers?

No.
Natural language can operate the workspace, but the system is not chat-first.
The truth is schema-backed state, not the conversation.

## 4. Is this project-first?

No, not in the current runtime.
The current product slice is paper-first and paper-centered.
`Project` remains a future lane, not the live product root.

## 5. Who is the v1 user?

One researcher operating in a local biomedical research workflow.
The current product is `single-operator-first`, not multi-user-first.

## 6. What does the product do well today?

It supports one bounded loop well:

paper -> structured understanding -> evidence review -> reproducible search design -> meeting-ready artifact

## 7. What is `Research DNA`?

`ResearchDNA` is the bounded reproducible search-design asset.
It is where the current runtime keeps `DRAFT -> PILOT -> LOCKED` search-design state.

## 8. Is `Meeting Pack` the source of truth?

No.
`Meeting Pack` is a downstream draft artifact generated from saved state.
It should be traceable and evidence-backed, but it is not the canonical root.

## 9. What is not promised in v1?

Not promised:

- project-first runtime
- chat/copilot-first workflow
- broad workspace memory
- repo-wide `Decision` / `Task` / `Experiment` objects
- multi-user collaboration
- full ELN/LIMS replacement

## 10. If someone asks what is still weak, what should I say?

Say this:

- the core bounded slice is real and demo-ready
- remaining work is mostly consistency and future-lane discipline
- what is intentionally not shipped is more important than what is merely not polished

Do not say:

- “we basically already have projects/chat/memory and just need UI”

## 11. If someone asks why local-first matters, what should I say?

Because the current product is designed around:

- data ownership
- inspectable local state
- portability
- offline survivability
- lower dependence on external providers

## 12. If someone asks what the LLM is doing, what should I say?

The LLM or automation helps produce structured outputs and drafts, but those outputs must stay tied to evidence, provenance, and runtime state.
LLM output is useful, but it does not outrank the canonical state.

## 13. If someone asks whether protocol, chart, image, or method lanes are part of the product, what should I say?

Yes, they are real bounded extensions.
No, they are not the first-product identity.
The product story should still start from the paper-centered core loop.

## 14. If the demo has to skip one surface, what is the safest fallback?

Stay inside this sequence:

`/papers` -> paper detail -> `Research DNA` -> `Meeting Pack`

Do not switch the story to `Project`, chat, or generalized workspace language.

## Bottom Line

If you need the safest short answer:

> Lattice currently demonstrates a real paper-centered evidence workflow, not a generalized research platform.
