# Image Evidence Backend Core Staging Prep (2026-03-22)

## Scope
Self-contained backend lane for image evidence registration, storage, and read APIs.

## Included files
- `/Users/jangseongjin/paperpipe/backend/main.py`
- `/Users/jangseongjin/paperpipe/backend/routers/image_evidence.py`
- `/Users/jangseongjin/paperpipe/src/image_evidence/__init__.py`
- `/Users/jangseongjin/paperpipe/src/image_evidence/service.py`
- `/Users/jangseongjin/paperpipe/src/image_evidence/store.py`
- `/Users/jangseongjin/paperpipe/src/schemas/image_evidence.py`
- `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`
- `/Users/jangseongjin/paperpipe/tests/fixtures/image_evidence_case/`
- `/Users/jangseongjin/paperpipe/tests/test_api_key_auth.py`
- `/Users/jangseongjin/paperpipe/tests/test_image_evidence_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_image_evidence_fixture_hardening.py`
- `/Users/jangseongjin/paperpipe/tests/test_image_evidence_schema.py`
- `/Users/jangseongjin/paperpipe/tests/test_image_evidence_service.py`
- `/Users/jangseongjin/paperpipe/tests/test_image_evidence_store.py`
- `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_image_evidence.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Image_Evidence_Backend_Core_Staging_Prep_2026-03-22.md`

## Explicitly excluded
- `/Users/jangseongjin/paperpipe/src/schemas/__init__.py` because it also carries unrelated chart-pack/meeting-pack/method-comparison/schema exports.
- Frontend shell changes under `/Users/jangseongjin/paperpipe/frontend/`.
- Local caches like `__pycache__/`.

## Verification target
- `PAPERPIPE_CONFIG_PATH=/tmp/.../config.example.yaml python3 -c 'import backend.main'`
- `pytest -q tests/test_image_evidence_api.py tests/test_image_evidence_fixture_hardening.py tests/test_image_evidence_schema.py tests/test_image_evidence_service.py tests/test_image_evidence_store.py tests/test_runtime_paths_image_evidence.py tests/test_api_key_auth.py -k image_evidence`
- `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`
