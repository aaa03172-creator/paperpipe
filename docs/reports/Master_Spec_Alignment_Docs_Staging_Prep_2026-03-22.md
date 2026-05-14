# Master Spec Alignment Docs Staging Prep

Status: staging manifest  
Date: 2026-03-22  
Branch: `codex/agents-smoke-ci-check`

## Intent

Freeze the documentation lane that aligns the canonical master spec, retires duplicate compatibility stubs, and adds metadata headers to directly related runbooks/contracts.

## Included scope

- `docs/Lattice_v3_Master_Spec.md`
- retired compatibility stub for the old UI/UX master path
- retired compatibility stub for the old PaperPipe master-spec path
- retired compatibility stub for the old PaperPipe final blueprint path
- `docs/UIUX_Adoption_Filter_2026-02-25.md`
- `docs/WEB_VIEWER.md`
- `docs/ClaimSet_Rendering_Guide.md`
- `docs/Stats_Verification_Agent_Spec.md`
- `docs/bootstrap_meta_schema.md`
- `docs/document_artifact_v2.md`
- `docs/downloader_monitoring.md`
- `docs/indexer.md`
- `docs/reports/Master_Spec_Alignment_Docs_Staging_Prep_2026-03-22.md`

## Explicitly excluded

- unrelated legacy docs like `docs/development_rules.md`
- any runtime/frontend code changes
- UX review artifacts already committed

## Verification

1. `python3 scripts/lint_docs.py`
2. staged diff stays docs-only

## Commit target

`docs(spec): align master spec and retire legacy stubs`
