# Skills Policy Staging Prep

Status: staging-prep manifest  
Date: 2026-03-22  
Lane: `skills-and-policy`

## Purpose

Define the self-contained skills-and-policy lane: policy file, packaging/audit docs, sync/audit scripts, and the vendored project-scoped skills copied into `.codex/skills/`.

## In Scope

- `/Users/jangseongjin/paperpipe/config/skills_policy.yaml`
- `/Users/jangseongjin/paperpipe/docs/SKILLS_AUDIT.md`
- `/Users/jangseongjin/paperpipe/docs/SKILLS_PACKAGING_GUIDE.md`
- `/Users/jangseongjin/paperpipe/docs/SKILLS_RECOMMENDATIONS.md`
- `/Users/jangseongjin/paperpipe/scripts/skills_audit.py`
- `/Users/jangseongjin/paperpipe/scripts/sync_scientific_skills.sh`
- `/Users/jangseongjin/paperpipe/.codex/skills/citation-management/`
- `/Users/jangseongjin/paperpipe/.codex/skills/markitdown/`
- `/Users/jangseongjin/paperpipe/.codex/skills/peer-review/`
- `/Users/jangseongjin/paperpipe/.codex/skills/pyzotero/`
- `/Users/jangseongjin/paperpipe/docs/reports/Skills_Policy_Staging_Prep_2026-03-22.md`

## Out Of Scope

- `/Users/jangseongjin/paperpipe/.codex/work/`
- `/Users/jangseongjin/paperpipe/.codex/skills/ui-ux-pro-max/`
- any runtime integration under `/Users/jangseongjin/paperpipe/src/skills/`
- unrelated docs lanes

## Verification Performed

1. `bash -n /Users/jangseongjin/paperpipe/scripts/sync_scientific_skills.sh`
2. `python3 /Users/jangseongjin/paperpipe/scripts/skills_audit.py`
3. `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`
4. policy-vs-vendored skills check
   - expected project-scoped skills: `markitdown`, `citation-management`, `pyzotero`, `peer-review`
   - `.codex/skills/ui-ux-pro-max` contains only ignored `.pyc` files and is excluded from this lane

## Safe Next Git Step

Stage only the files and directories listed in scope above and inspect `git diff --cached --name-only` before commit.
