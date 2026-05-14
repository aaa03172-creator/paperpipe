# Protocol Cards Backend Core Staging Prep

Status: staging-prep manifest  
Date: 2026-03-23  
Lane: `protocol-cards-backend-core`

## Purpose

Capture the file-backed Protocol Cards backend core as a bounded artifact lane without mixing it with queue/docs promotion work.

## In Scope

- `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`
- `/Users/jangseongjin/paperpipe/src/schemas/__init__.py`
- `/Users/jangseongjin/paperpipe/src/schemas/protocol_card.py`
- `/Users/jangseongjin/paperpipe/src/protocol_cards/__init__.py`
- `/Users/jangseongjin/paperpipe/src/protocol_cards/renderer.py`
- `/Users/jangseongjin/paperpipe/src/protocol_cards/service.py`
- `/Users/jangseongjin/paperpipe/src/protocol_cards/store.py`
- `/Users/jangseongjin/paperpipe/tests/test_protocol_card_schema.py`
- `/Users/jangseongjin/paperpipe/tests/test_protocol_card_store.py`
- `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_protocol_cards.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Protocol_Cards_Backend_Core_Staging_Prep_2026-03-23.md`

## Out Of Scope

- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`
- `/Users/jangseongjin/paperpipe/docs/README.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/backend/routers/protocol_cards.py` (already clean in the branch)
- `/Users/jangseongjin/paperpipe/backend/main.py` (already clean in the branch)

## Verification

Current worktree:
- `cd /Users/jangseongjin/paperpipe && pytest -q tests/test_protocol_card_schema.py tests/test_protocol_card_store.py tests/test_runtime_paths_protocol_cards.py`

Temp worktree:
- copy only the in-scope files onto clean `HEAD`
- `PAPERPIPE_CONFIG_PATH=config.example.yaml python3 -c "import backend.main"`
- `python3 -c "import src.protocol_cards.service"`
- `pytest -q tests/test_protocol_card_schema.py tests/test_protocol_card_store.py tests/test_runtime_paths_protocol_cards.py`

## Safe Next Git Step

Stage only the files in scope above and commit as the protocol-cards backend core lane.
