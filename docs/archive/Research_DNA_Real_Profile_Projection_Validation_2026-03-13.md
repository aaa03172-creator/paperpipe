# Research DNA Real Profile Projection Validation (2026-03-13)

Status: Historical runtime report  
Date: 2026-03-13  
Owner: Search/runtime maintainers  
Canonical parent: `docs/RESEARCH_DNA.md`

## Goal
실제 `Research DNA` probe를 legacy `config/profiles.yaml` compatibility surface로 projection하고, duplicate 없이 deterministic upsert되는지 확인한다.

## Target DNA
- profile:
  - [/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/profile.yaml](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/profile.yaml)
- current revision:
  - `3`
- selected query version:
  - `v2`
- selected database:
  - `pubmed`

## Validation Result
- projected profile path:
  - [/Users/jangseongjin/paperpipe/config/profiles.yaml](/Users/jangseongjin/paperpipe/config/profiles.yaml)
- projected profile ID:
  - `research_dna_dna_mci_medium_chain_triglycerides_probe_20260312`
- projected profile count after sequential sync:
  - total profiles `2`
  - target projected profile entries `1`
- projected profile revision after post-hardening refresh:
  - `1`

Projected profile properties:
- `enabled=false`
- `schedule=manual`
- `limits.max_results_per_run=20`
- `query.must = ["mild cognitive impairment", "medium-chain triglycerides"]`
- `query.should = ["cognition"]`
- `query.must_not` carries the current DNA exclusions
- `Profile.notes` contains:
  - `schema_version: research_dna.profile_projection.v1`
  - `source_dna_id`
  - `source_query_version: v2`
  - `selected_database: pubmed`
  - full exact selected PubMed query

## Important Runtime Finding
An initial parallel projection probe exposed a real temp-path collision in YAML atomic writes.

Observed behavior:
- two concurrent `project-profile` writes targeted the same `config/profiles.yaml`
- the old writer used a fixed temp file path
- one write succeeded, one failed with missing temp-file during move

Resolution:
- [profile_store.py](/Users/jangseongjin/paperpipe/src/profiles/profile_store.py) now uses unique temp files + `os.replace`
- [research_dna_store.py](/Users/jangseongjin/paperpipe/src/profiles/research_dna_store.py) was hardened the same way for consistency
- operator-facing `profiles.yaml` mutation now uses lock + merge-safe update/upsert semantics so unrelated profile entries survive concurrent writes
- legacy `profiles` / `audit` CLI was aligned to the same `PAPERPIPE_PROFILES_PATH` runtime path contract
- legacy `profiles` / `audit` same-profile saves now carry expected revision checks so stale edits fail as conflicts instead of silently winning
- raw `save_profiles_snapshot()` overwrite is now blocked on the operator-facing path, so future code cannot bypass the guarded update path by accident
- generic `rewrite_profiles_config()` bulk rewrites are now also blocked on the operator-facing path unless the caller explicitly marks the write as system-owned

Accepted validation run:
- only the later sequential syncs are treated as canonical
- sequential run 1 materialized the projection
- sequential run 2 confirmed idempotent upsert with no duplicate entry
- post-hardening sequential refresh confirmed the projected profile now persists `revision=1`

## Audit Evidence
- approval audit tail:
  - `project_profile repeat projection to verify idempotent upsert`
  - `project_profile materialize compatibility profile for real probe validation (sequential run 1)`
  - `project_profile materialize compatibility profile for real probe validation (sequential run 2)`
  - `project_profile validate projected profile revision guard after profile store hardening`
- audit log:
  - [/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/logs/approval_audit.jsonl](/Users/jangseongjin/paperpipe/research_dna/dna_mci_medium_chain_triglycerides_probe_20260312/logs/approval_audit.jsonl)

## Conclusion
`ResearchDNA -> Profile` projection is now validated on real workspace data.

Current interpretation:
- `ResearchDNA` remains the editable source of truth
- projected `Profile` is a deterministic, read-only compatibility snapshot
- legacy `profiles` / `audit` CLI must not edit the projected profile directly
