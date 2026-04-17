from src.schemas import (
    ChatRequest,
    ImageEvidence,
    IntakeOverrideLog,
    MeetingPack,
    MethodComparison,
    PaperNoteListResponse,
    ProjectMemoryItem,
    SkillRunRequest,
)
from src.schemas.chat import ChatRequest as ChatRequestDirect
from src.schemas.image_evidence import ImageEvidence as ImageEvidenceDirect
from src.schemas.intake_override_log import IntakeOverrideLog as IntakeOverrideLogDirect
from src.schemas.meeting_pack import MeetingPack as MeetingPackDirect
from src.schemas.method_comparison import MethodComparison as MethodComparisonDirect
from src.schemas.paper_notes import PaperNoteListResponse as PaperNoteListResponseDirect
from src.schemas.project_memory import ProjectMemoryItem as ProjectMemoryItemDirect
from src.schemas.skills import SkillRunRequest as SkillRunRequestDirect


def test_schema_package_exports_safe_subset():
    assert ChatRequest is ChatRequestDirect
    assert PaperNoteListResponse is PaperNoteListResponseDirect
    assert IntakeOverrideLog is IntakeOverrideLogDirect
    assert ImageEvidence is ImageEvidenceDirect
    assert MeetingPack is MeetingPackDirect
    assert MethodComparison is MethodComparisonDirect
    assert ProjectMemoryItem is ProjectMemoryItemDirect
    assert SkillRunRequest is SkillRunRequestDirect
