from __future__ import annotations

from datetime import datetime, timezone

import pytest

import src.project_memory.store as project_memory_store
from src.project_memory.store import (
    append_project_memory_item,
    list_project_memory_ids,
    load_project_memory_items,
    load_project_memory_workspace,
    project_memory_jsonl_path,
    project_workspace_json_path,
    save_project_memory_bundle,
)
from src.schemas.project_memory import ProjectMemoryItem, ProjectMemoryWorkspace


def _sample_workspace(*, title: str = "Ketone pathway project") -> ProjectMemoryWorkspace:
    return ProjectMemoryWorkspace(
        project_id="pmproj_alpha",
        title=title,
        objective="Clarify mechanism and next experiments",
        status="active",
        notes="Working memory only",
        linked_paper_ids=["paper-001", "paper-002"],
        linked_research_dna_ids=["dna-main"],
        linked_meeting_pack_ids=["meetingpack_001"],
        created_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 23, 2, 5, tzinfo=timezone.utc),
    )


def _sample_item(*, item_id: str, item_type: str, content: str) -> ProjectMemoryItem:
    return ProjectMemoryItem(
        item_id=item_id,
        project_id="pmproj_alpha",
        item_type=item_type,
        content=content,
        confidence_status="working",
        freshness_status="current",
        linked_entities=[
            {
                "entity_type": "paper",
                "entity_id": "paper-001",
                "relationship_type": "references",
            }
        ],
        created_at=datetime(2026, 3, 23, 2, 10, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 23, 2, 10, tzinfo=timezone.utc),
    )


def test_project_memory_store_roundtrip_creates_expected_layout(tmp_path) -> None:
    root = tmp_path / "project_memory"
    workspace = _sample_workspace()
    items = [
        _sample_item(item_id="pmitem_alpha_question", item_type="question", content="What is the mechanism?"),
        _sample_item(item_id="pmitem_alpha_decision", item_type="decision", content="Prioritize BHB readout."),
    ]

    result = save_project_memory_bundle(workspace, items, root=root)
    loaded_workspace = load_project_memory_workspace(workspace.project_id, root)
    loaded_items = load_project_memory_items(workspace.project_id, root)

    assert result[0] == project_workspace_json_path(workspace.project_id, root)
    assert result[1] == project_memory_jsonl_path(workspace.project_id, root)
    assert loaded_workspace.title == "Ketone pathway project"
    assert [item.item_id for item in loaded_items] == ["pmitem_alpha_question", "pmitem_alpha_decision"]
    assert list_project_memory_ids(root) == [workspace.project_id]


def test_project_memory_store_append_item_preserves_order(tmp_path) -> None:
    root = tmp_path / "project_memory"
    workspace = _sample_workspace()
    save_project_memory_bundle(workspace, [], root=root)

    first_item = _sample_item(item_id="pmitem_alpha_question", item_type="question", content="What is the mechanism?")
    second_item = _sample_item(item_id="pmitem_alpha_todo", item_type="todo", content="Check chart-pack handoff.")
    append_project_memory_item(first_item, root)
    append_project_memory_item(second_item, root)

    loaded_items = load_project_memory_items(workspace.project_id, root)
    assert [item.item_id for item in loaded_items] == ["pmitem_alpha_question", "pmitem_alpha_todo"]


def test_project_memory_store_rejects_mismatched_item_project_ids(tmp_path) -> None:
    root = tmp_path / "project_memory"
    workspace = _sample_workspace()
    foreign_item = ProjectMemoryItem(
        item_id="pmitem_other_note",
        project_id="pmproj_other",
        item_type="note",
        content="Wrong project",
        created_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="must match workspace project_id"):
        save_project_memory_bundle(workspace, [foreign_item], root=root)


def test_project_memory_store_rejects_duplicate_item_ids(tmp_path) -> None:
    root = tmp_path / "project_memory"
    workspace = _sample_workspace()
    duplicate_items = [
        _sample_item(item_id="pmitem_alpha_question", item_type="question", content="What is the mechanism?"),
        _sample_item(item_id="pmitem_alpha_question", item_type="todo", content="Duplicate item id"),
    ]

    with pytest.raises(ValueError, match="duplicate item_id"):
        save_project_memory_bundle(workspace, duplicate_items, root=root)


def test_project_memory_store_requires_workspace_before_item_writes(tmp_path) -> None:
    root = tmp_path / "project_memory"
    item = _sample_item(item_id="pmitem_alpha_question", item_type="question", content="What is the mechanism?")

    with pytest.raises(FileNotFoundError, match="workspace JSON not found"):
        append_project_memory_item(item, root)

    with pytest.raises(FileNotFoundError, match="workspace JSON not found"):
        project_memory_store.save_project_memory_items(item.project_id, [item], root)


def test_project_memory_store_list_ignores_directories_without_project_json(tmp_path) -> None:
    root = tmp_path / "project_memory"
    workspace = _sample_workspace()
    save_project_memory_bundle(workspace, [], root=root)
    stray_dir = root / "pmproj_stray"
    stray_dir.mkdir(parents=True)
    (stray_dir / "memory.jsonl").write_text("", encoding="utf-8")

    assert list_project_memory_ids(root) == ["pmproj_alpha"]


def test_project_memory_store_rolls_back_if_items_write_fails(tmp_path, monkeypatch) -> None:
    root = tmp_path / "project_memory"
    original_workspace = _sample_workspace(title="Original title")
    original_items = [_sample_item(item_id="pmitem_alpha_question", item_type="question", content="Original item")]
    save_project_memory_bundle(original_workspace, original_items, root=root)

    updated_workspace = _sample_workspace(title="Updated title")
    updated_items = [
        _sample_item(item_id="pmitem_alpha_question", item_type="question", content="Original item"),
        _sample_item(item_id="pmitem_alpha_decision", item_type="decision", content="Updated decision"),
    ]
    original_atomic_write_text = project_memory_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_second_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(project_memory_store, "_atomic_write_text", fail_on_second_write)

    with pytest.raises(OSError):
        save_project_memory_bundle(updated_workspace, updated_items, root=root)

    loaded_workspace = load_project_memory_workspace(original_workspace.project_id, root)
    loaded_items = load_project_memory_items(original_workspace.project_id, root)
    assert loaded_workspace.title == "Original title"
    assert [item.item_id for item in loaded_items] == ["pmitem_alpha_question"]
