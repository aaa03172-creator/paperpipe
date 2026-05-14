Status: Historical runtime report  
Date: 2026-03-13  
Owner: Paper notes/runtime maintainers  
Canonical parent: `docs/MEETING_PACK.md`

## Goal
`Meeting Pack` v1 minimal slice가 실제 vault의 structured paper state 하나를 읽어 JSON + Markdown draft artifact를 생성하는지 확인한다.

## Probe Definition
- source slug:
  - `zoteroduboisAlzheimerDiseaseClinicalBiological2024`
- mode:
  - `journal_club`
- request:
  - `paper_slug` only
  - `max_slides=5`

## Result
- generated pack id:
  - `meetingpack_20260313T095828534763Z_journal_club_06874005`
- json artifact:
  - [/Users/jangseongjin/paperpipe/storage/meeting_packs/meetingpack_20260313T095828534763Z_journal_club_06874005/meeting_pack.json](/Users/jangseongjin/paperpipe/storage/meeting_packs/meetingpack_20260313T095828534763Z_journal_club_06874005/meeting_pack.json)
- markdown artifact:
  - [/Users/jangseongjin/paperpipe/storage/meeting_packs/meetingpack_20260313T095828534763Z_journal_club_06874005/meeting_pack.md](/Users/jangseongjin/paperpipe/storage/meeting_packs/meetingpack_20260313T095828534763Z_journal_club_06874005/meeting_pack.md)

Probe summary:
- `evidence_refs=2`
- `slides=5`
- `source_items=1`

## What Was Verified
- actual vault `.pp/<slug>/state.json` was readable
- pack-local evidence ledger IDs were generated (`evref_01`, `evref_02`)
- deterministic markdown was rendered from the saved JSON contract
- output stayed draft-first and evidence-linked
- the same probe shape can now be rerun via `python3 scripts/check_meeting_pack_real_smoke.py`

## Notes
- current probe only covers the implemented minimal slice:
  - `paper_slug` selector
  - `state.json` first
  - single-paper draft
- broader typed source selectors and richer multi-source merge/conflict handling are covered elsewhere, but this probe remains the narrowest real-input acceptance artifact.
