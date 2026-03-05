# PaperPipe Agentic Guidelines

## 1. Architectural Rules
- **API-First:** Core logic must be exposed via FastAPI. No hardcoded CLI-only paths.
- **Pydantic Contracts:** All agent inputs/outputs must strictly follow the Pydantic schemas in `src/schemas/`.
- **Idempotency:** Obsidian markdown generation must replace sections safely, not blindly append.

## 2. MCP & Cost Control Guardrails (CRITICAL)
If you are equipped with the Google Developer Knowledge MCP (or any external search tool):
- **Limit `search_documents`:** Maximum 2 calls per session.
- **Limit `get_document`:** Maximum 1 call per session (only fetch the single most relevant doc).
- **BANNED `batch_get_documents`:** Do NOT use this tool. It causes massive token bloat. If absolutely necessary, you must ask the user for explicit permission first.
- **Save Context:** Summarize findings internally; do not repeatedly fetch the same external docs.

## 3. Product Psychology Rules (Always-on for UX)
Before proposing or implementing UI/UX, onboarding, pricing, CTA, conversion, flow, or key user journey changes, always read and apply:
- `rules/product-psychology/SKILL.md`
- `rules/product-psychology/references/review-checklist.md`
- `rules/product-psychology/references/bias-framework.md`
- `rules/product-psychology/references/ethics-checklist.md`
- `rules/product-psychology/references/prompt-templates.md`

### Trigger Conditions
Apply the product psychology rules whenever work includes:
- Landing pages
- Onboarding
- Pricing or paywall
- Key CTA design/copy
- Conversion or retention UX
- Error or empty states
- Core user flows (signup, purchase, explore, approve/export)
- "Why should I use this?" clarity problems

### Required Output Format (when UX is involved)
Every UX-involved response must include:
1. Quick Review (5 min)
2. Full Review (P0/P1/P2 prioritized)
3. Concrete changes (component/route/copy/default-action level)
4. Ethics check results (Regret / Black Mirror / In Real-Life)
5. Next PR-sized actions (1-3 items)

### Full Review Coverage (mandatory)
Inside "Full Review", explicitly cover all five frameworks:
- 6P storyboard context (Problem/Emotion/Action/Struggle/Attempt/Happy Ending)
- BMAP (Motivation / Ability / Prompt gaps)
- B.I.A.S (Block / Interpret / Act / Store)
- Peak-End (peak, pit, transition, end)
- Ethics checks (Regret / Black Mirror / In Real-Life)

### Internal Command Convention
Treat `/ux-review` as the standard review mode for UX tasks.

Input:
- target screen/flow
- user goal
- current pain points
- constraints (tech/design/business)

Output:
- Quick Review
- Full Review (P0/P1/P2)
- Concrete implementation changes
- Ethics check
- 1-3 PR-sized next actions
