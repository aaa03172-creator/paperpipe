from src.services.deepread_note_writer import upsert_deepread_section


def test_upsert_appends_when_missing():
    content = "# Title\n\n## Notes\nhello\n"
    new_section = "## 🤖 Agent Deep Read\nnew body\n"
    updated = upsert_deepread_section(content, new_section)

    assert "## 🤖 Agent Deep Read\nnew body\n" in updated
    assert updated.count("## 🤖 Agent Deep Read") == 1
    assert "## Notes\nhello" in updated


def test_upsert_replaces_single_existing_section():
    content = (
        "# Title\n\n"
        "## 🤖 Agent Deep Read\n"
        "old body\n"
        "### 🧪 Stats Verification\n"
        "old stats\n\n"
        "## Next\n"
        "keep me\n"
    )
    new_section = "## 🤖 Agent Deep Read\nnew body\n"
    updated = upsert_deepread_section(content, new_section)

    assert updated.count("## 🤖 Agent Deep Read") == 1
    assert "new body" in updated
    assert "old body" not in updated
    assert "## Next\nkeep me" in updated


def test_upsert_normalizes_duplicate_sections_to_one():
    content = (
        "# Title\n\n"
        "## 🤖 Agent Deep Read\n"
        "first old\n\n"
        "## Notes\n"
        "keep notes\n\n"
        "## 🤖 Agent Deep Read\n"
        "second old\n"
        "### 🧪 Stats Verification\n"
        "old stats\n\n"
        "## Tail\n"
        "tail content\n"
    )
    new_section = "## 🤖 Agent Deep Read\nnew canonical\n"
    updated = upsert_deepread_section(content, new_section)

    assert updated.count("## 🤖 Agent Deep Read") == 1
    assert "new canonical" in updated
    assert "first old" not in updated
    assert "second old" not in updated
    assert "## Notes\nkeep notes" in updated
    assert "## Tail\ntail content" in updated
