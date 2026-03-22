# Protocol Cards API Staging Prep

Status: staging-prep manifest  
Date: 2026-03-23  
Lane: `protocol-cards-api`

## Purpose

Expose the bounded Protocol Cards backend core through a thin FastAPI surface with API-key protection and focused regression coverage.

## In Scope

- `/Users/jangseongjin/paperpipe/backend/main.py`
- `/Users/jangseongjin/paperpipe/backend/routers/protocol_cards.py`
- `/Users/jangseongjin/paperpipe/tests/test_api_key_auth.py`
- `/Users/jangseongjin/paperpipe/tests/test_protocol_card_service.py`
- `/Users/jangseongjin/paperpipe/tests/test_protocol_cards_api.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Protocol_Cards_API_Staging_Prep_2026-03-23.md`

## Out Of Scope

- protocol-card schema/store/runtime-path core (already committed)
- docs queue/readme promotion work
- frontend/runtime viewer work

## Verification

Current worktree:
- `cd /Users/jangseongjin/paperpipe && PAPERPIPE_CONFIG_PATH=config.example.yaml pytest -q tests/test_protocol_card_service.py tests/test_protocol_cards_api.py tests/test_api_key_auth.py`

Temp worktree:
- apply only the in-scope files to clean `HEAD`
- `PAPERPIPE_CONFIG_PATH=config.example.yaml python3 -c "import backend.main"`
- `PAPERPIPE_CONFIG_PATH=config.example.yaml pytest -q tests/test_protocol_card_service.py tests/test_protocol_cards_api.py tests/test_api_key_auth.py`

## Safe Next Git Step

Stage only the files in scope above and commit as the thin protocol-cards API lane.
