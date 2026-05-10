# Reference Archive Docs Staging Prep

Status: staging manifest  
Date: 2026-03-22  
Branch: `codex/agents-smoke-ci-check`

## Intent

Freeze the remaining reference-review and archived prompt documents without pulling any runtime code changes.

## Included scope

- `docs/OpenViking_Reference_Fit_Review_2026-03-17.md`
- `docs/REFERENCE_REVIEW_ROUND2.md`
- `docs/archive/Claude_Code_Skills_Review_Prompt_2026-03-22.md`
- `docs/archive/LiteParse_Review_Prompt_2026-03-22.md`
- `docs/archive/OpenDataLoader_PDF_Fit_Review_2026-03-20.md`
- `docs/archive/OpenDataLoader_PDF_Hard_Doc_Manifest_Spec_2026-03-20.md`
- `docs/archive/OpenDataLoader_PDF_Hard_Doc_Pilot_Spec_2026-03-20.md`
- `docs/archive/OpenDataLoader_PDF_Review_Prompt_2026-03-22.md`
- `docs/reports/Reference_Archive_Docs_Staging_Prep_2026-03-22.md`

## Explicitly excluded

- any runtime/parser implementation changes
- any frontend viewer code
- tracked legacy spec edits

## Verification

1. `python3 scripts/lint_docs.py`
2. staged diff stays docs-only

## Commit target

`docs(reference): add archived fit reviews and prompts`
