# D4 Artifact Store Rollback Difference Review

Purpose:
Record the per-store differences behind D4 before any shared transaction helper is extracted. This is a cleanup-prep artifact only; no production code is changed by this review.

## Summary

D4 is confirmed duplicate logic, but it is not one uniform duplication. The stores share atomic write, snapshot, restore, stale-managed-file cleanup, and empty-directory cleanup mechanics, while their validation and managed-file semantics differ enough that a broad extraction would be risky.

Recommended stance:
Start with tests and documentation, then extract only a small helper or one store family at a time. Do not replace all bundle writers with a single broad abstraction in one change.

Follow-up status:
A first low-risk helper extraction now exists in `src/services/artifact_transactions.py` for shared text/byte atomic primitives and directory cleanup. It has been applied only to the simple text bundle family: Meeting Pack, Method Comparison, Paper Synthesis, and Project Memory. Managed stale-file stores and mixed/binary stores remain intentionally local for now.

## Store Families

| Family | Stores | Evidence | Shared mechanics | Store-specific behavior | Extraction risk |
|---|---|---|---|---|---|
| Simple text bundles | `src/meeting_packs/store.py:77`, `src/method_comparisons/store.py:77`, `src/paper_syntheses/store.py:60`, `src/project_memory/store.py:96` | Each saves a small fixed set of text files, snapshots existing text, restores on exception, and removes an empty bundle dir. | Shared helper now backs `_atomic_write_text`, `_optional_text`, `_restore_optional_text`, and `_remove_empty_dir`; thin store-local wrappers remain for error context and test monkeypatch compatibility. | Payload shape and path count differ; project memory writes JSON plus JSONL and validates workspace/item IDs. | Low/Medium |
| Managed text bundles with stale cleanup | `src/chart_packs/store.py:187`, `src/protocol_cards/store.py:107` | Each calculates expected paths, snapshots existing managed files, writes current bundle files, removes stale managed files, and prunes managed subdirs. | Expected-path tracking, stale managed path removal, text restore, empty-dir pruning | Chart Pack validates chart IDs and render extensions; Protocol Card validates version-summary parity. Managed subdirs differ. | Medium/High |
| Managed mixed/binary bundles | `src/image_evidence/store.py:158`, `src/talk_packs/store.py:120` | Each snapshots bytes, writes JSON/text/binary outputs, removes stale managed members, and restores previous bytes on failure. | `_atomic_write_bytes`, `_optional_bytes`, `_restore_optional_bytes`, expected-path tracking, stale managed path removal | Image Evidence derives paths from view-state/handoff/derived output refs; Talk Pack derives managed paths from generated output/review artifacts in the previous JSON payload. | High |
| Fixed binary bundle | `src/protocol_attachments/store.py:41` | Writes JSON, source bytes, optional markdown bytes, restores byte snapshots on failure, and removes empty dirs. | Binary snapshot/write/restore and empty-dir cleanup | Optional markdown may be removed when absent; source path comes from declared attachment ref. No broad managed stale sweep. | Medium |

## Confirmed Duplicate Mechanics

- Atomic text writing is reimplemented in `src/meeting_packs/store.py:102`, `src/method_comparisons/store.py:112`, `src/paper_syntheses/store.py:90`, `src/chart_packs/store.py:341`, and `src/protocol_cards/store.py:202`.
- Atomic byte writing is reimplemented in `src/image_evidence/store.py:352`, `src/talk_packs/store.py:340`, and `src/protocol_attachments/store.py:137`.
- Optional snapshot/restore helpers are repeated across text and byte stores, including `src/chart_packs/store.py:360`, `src/protocol_cards/store.py:221`, `src/image_evidence/store.py:371`, and `src/talk_packs/store.py:359`.
- Empty-directory pruning is repeated across managed stores, including `src/chart_packs/store.py:374`, `src/protocol_cards/store.py:235`, `src/image_evidence/store.py:385`, `src/talk_packs/store.py:373`, and `src/protocol_attachments/store.py:170`.

## Differences That Make Removal Or Refactor Risky

- Stale managed file ownership is store-specific. Chart Pack uses known data/spec/render directories; Protocol Card uses version JSON files; Image Evidence uses derivative files; Talk Pack derives generated/review artifacts from the previous JSON payload.
- Text-only stores can restore with string snapshots, but Image Evidence, Talk Pack, and Protocol Attachment require byte snapshots to preserve binary outputs exactly.
- Some bundle writers validate declared members before writing. Moving this into a generic helper would blur schema-specific invariants.
- Unrelated operator files inside bundle directories must be preserved. Tests now cover this behavior for the major artifact stores reviewed.
- Empty-directory cleanup has different stop points. A generic cleanup loop must preserve the root boundary and not delete user-created sibling content.

## Current Verification Coverage

Added or strengthened failure-injection preservation tests for:

- `tests/test_meeting_pack_store.py`
- `tests/test_protocol_card_store.py`
- `tests/test_chart_pack_store.py`
- `tests/test_image_evidence_store.py`
- `tests/test_talk_pack_store.py`
- `tests/test_method_comparison_store.py`
- `tests/test_paper_synthesis_store.py`
- `tests/test_project_memory_store.py`
- `tests/test_protocol_attachment_store.py`

Last focused verification:

```sh
.venv/bin/python -m pytest -q tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_image_evidence_store.py tests/test_talk_pack_store.py tests/test_chart_pack_store.py tests/test_meeting_pack_store.py tests/test_protocol_card_store.py tests/test_project_memory_store.py tests/test_protocol_attachment_store.py
```

Result: `64 passed`.

## Safest Extraction Order

1. Completed first step: centralize low-level primitives in `src/services/artifact_transactions.py`, with store-local wrappers preserving domain-specific error context.
2. Completed first application: simple text bundles for Meeting Pack, Paper Synthesis, Method Comparison, and Project Memory.
3. After simple stores are stable, consider a narrow managed-text helper for Chart Pack and Protocol Card expected-path/stale-path handling.
4. Defer Image Evidence and Talk Pack until byte snapshots, nested paths, declared artifact validation, and previous-payload managed path discovery are covered by dedicated tests.
5. Treat Protocol Attachment as a separate small binary transaction, not a natural fit for the full managed-stale bundle helper.

## Suggested Helper Boundary

Potentially safe:

- `atomic_write_text(path, content)`
- `atomic_write_bytes(path, content)`
- `snapshot_text(paths)` / `snapshot_bytes(paths)`
- `restore_text(snapshot)` / `restore_bytes(snapshot)`
- `remove_empty_dirs(path, stop_at=...)`

Riskier:

- A generic `save_bundle(...)` that owns expected path construction.
- A helper that infers managed paths without each store's schema-aware logic.
- A helper that combines text and bytes unless all caller tests assert exact rollback behavior.

## Suggested Next Check Before Production Refactor

Focused tests now cover `src/project_memory/store.py` and `src/protocol_attachments/store.py` as well as the seven major artifact stores reviewed earlier.

Recommended command after any D4 production refactor:

```sh
.venv/bin/python -m pytest -q tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_image_evidence_store.py tests/test_talk_pack_store.py tests/test_chart_pack_store.py tests/test_meeting_pack_store.py tests/test_protocol_card_store.py tests/test_project_memory_store.py tests/test_protocol_attachment_store.py
```

Keep this full D4 command as the minimum verification gate after extracting shared text or binary helpers.

Latest helper-extraction verification:

```sh
python3 -m py_compile src/services/artifact_transactions.py src/meeting_packs/store.py src/method_comparisons/store.py src/paper_syntheses/store.py src/project_memory/store.py
.venv/bin/python -m pytest -q tests/test_meeting_pack_store.py tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_project_memory_store.py
.venv/bin/python -m pytest -q tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_image_evidence_store.py tests/test_talk_pack_store.py tests/test_chart_pack_store.py tests/test_meeting_pack_store.py tests/test_protocol_card_store.py tests/test_project_memory_store.py tests/test_protocol_attachment_store.py
```

Results: `py_compile` passed; simple text bundle tests passed with `28 passed`; full reviewed-store D4 gate passed with `64 passed`.
