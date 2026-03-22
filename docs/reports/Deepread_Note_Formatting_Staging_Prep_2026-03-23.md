# Deepread Note Formatting Staging Prep (2026-03-23)

## Goal
Split a narrow note-writer lane that improves deep-read markdown readability without pulling in broader paper-notes API changes.

## Included
- `/Users/jangseongjin/paperpipe/src/services/deepread_note_writer.py`
- `/Users/jangseongjin/paperpipe/tests/test_deepread_note_writer.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Deepread_Note_Formatting_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- The runtime change is limited to deep-read markdown formatting.
- The matching tests only validate note-writer behavior: stats notes rendering and conservative evidence quote cleanup.
- No paper-notes API, frontend, or routing behavior is required for this slice.

## Explicitly Excluded
- `/Users/jangseongjin/paperpipe/tests/test_paper_notes_api.py`
- `/Users/jangseongjin/paperpipe/src/services/paper_ops_summary.py`
- `/Users/jangseongjin/paperpipe/src/obsidian.py`
- all frontend files and Playwright assets

## Verification Plan
In a temp worktree containing only this patch:
- `pytest -q tests/test_deepread_note_writer.py`
- `python3 scripts/lint_docs.py`

## Expected Outcome
Deep-read markdown displays cleaner evidence text and preserves stats repair notes in the rendered section.
