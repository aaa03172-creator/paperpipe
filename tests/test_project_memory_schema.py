from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.project_memory import ProjectMemoryItem, ProjectMemoryWorkspace


def _sample_item(*, item_id: str = "pmitem_alpha_question", item_type: str = "question") -> ProjectMemoryItem:
    return ProjectMemoryItem(
        item_id=item_id,
        project_id="pmproj_alpha",
        item_type=item_type,
        content=" What is the strongest mechanistic explanation? ",
        confidence_status="working",
        freshness_status="current",
        linked_entities=[
            {
                "entity_type": "paper",
                "entity_id": " paper-001 ",
                "relationship_type": "references",
                "note": " primary source ",
            },
            {
                "entity_type": "paper",
                "entity_id": "paper-001",
                "relationship_type": "references",
                "note": "primary source",
            },
        ],
        created_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 23, 2, 5, tzinfo=timezone.utc),
    )


def test_project_memory_schema_normalizes_workspace_and_item_state() -> None:
    item = _sample_item()
    workspace = ProjectMemoryWorkspace(
        project_id="pmproj_alpha",
        title=" Ketone pathway project ",
        objective=" Clarify mechanism and next experiments ",
        status="active",
        notes=" Working memory only ",
        linked_paper_ids=[" paper-001 ", "paper-001", "paper-002"],
        linked_research_dna_ids=[" dna-main ", "dna-main"],
        linked_meeting_pack_ids=[" meetingpack_001 ", "meetingpack_001"],
        created_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 23, 2, 5, tzinfo=timezone.utc),
    )

    assert workspace.title == "Ketone pathway project"
    assert workspace.layer == "raw_memory"
    assert workspace.canonical_status == "non_canonical"
    assert workspace.objective == "Clarify mechanism and next experiments"
    assert workspace.notes == "Working memory only"
    assert workspace.linked_paper_ids == ["paper-001", "paper-002"]
    assert workspace.linked_research_dna_ids == ["dna-main"]
    assert workspace.linked_meeting_pack_ids == ["meetingpack_001"]

    assert item.content == "What is the strongest mechanistic explanation?"
    assert item.layer == "raw_memory"
    assert item.canonical_status == "non_canonical"
    assert len(item.linked_entities) == 1
    assert item.linked_entities[0].entity_id == "paper-001"
    assert item.linked_entities[0].note == "primary source"


def test_project_memory_item_rejects_unscoped_ids() -> None:
    with pytest.raises(ValidationError):
        ProjectMemoryItem(
            item_id="memory-1",
            project_id="project-1",
            item_type="note",
            content="Keep this around",
            created_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 23, 2, 5, tzinfo=timezone.utc),
        )


def test_project_memory_workspace_rejects_blank_link_ids() -> None:
    with pytest.raises(ValidationError):
        ProjectMemoryWorkspace(
            project_id="pmproj_alpha",
            title="Alpha",
            linked_paper_ids=["paper-001", " "],
            created_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 23, 2, 5, tzinfo=timezone.utc),
        )
