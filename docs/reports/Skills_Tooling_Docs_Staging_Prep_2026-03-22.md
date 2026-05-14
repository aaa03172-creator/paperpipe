# Skills Tooling Docs Staging Prep (2026-03-22)

## Scope
Self-contained developer-tooling lane for local Codex helper skills, skill packaging guidance, and top-level repo instructions that document the boundary between local workflow helpers and PaperPipe runtime behavior.

## Included files
- `/Users/jangseongjin/paperpipe/.gitignore`
- `/Users/jangseongjin/paperpipe/AGENTS.md`
- `/Users/jangseongjin/paperpipe/README.md`
- `/Users/jangseongjin/paperpipe/.codex/agents/architecture_guardian.toml`
- `/Users/jangseongjin/paperpipe/.codex/agents/code_mapper.toml`
- `/Users/jangseongjin/paperpipe/.codex/agents/eval_harness_builder.toml`
- `/Users/jangseongjin/paperpipe/.codex/skills/smallest-safe-patch/SKILL.md`
- `/Users/jangseongjin/paperpipe/.codex/skills/smallest-safe-patch/references/patch-checklist.md`
- `/Users/jangseongjin/paperpipe/.codex/skills/tool-intake-review/SKILL.md`
- `/Users/jangseongjin/paperpipe/.codex/skills/tool-intake-review/references/fit-rubric.md`
- `/Users/jangseongjin/paperpipe/docs/SKILLS_PACKAGING_GUIDE.md`
- `/Users/jangseongjin/paperpipe/docs/archive/README.md`
- `/Users/jangseongjin/paperpipe/docs/archive/Frontend_Worksurface_UI_Refinement_Prompt_2026-03-22.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Skills_Tooling_Docs_Staging_Prep_2026-03-22.md`

## Explicitly excluded
- Runtime-facing `src/skills/` changes.
- Product UI routes and frontend viewer shells.
- Hidden local folders unrelated to this lane such as `.omx/` and `.serena/`.

## Verification target
- `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`
