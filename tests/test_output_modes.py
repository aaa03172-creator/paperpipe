from src.output_modes import resolve_meeting_pack_output_mode_family


def test_meeting_pack_modes_map_to_shared_output_mode_families():
    assert resolve_meeting_pack_output_mode_family("journal_club") == "lab_meeting"
    assert resolve_meeting_pack_output_mode_family("literature_update") == "lab_meeting"
    assert resolve_meeting_pack_output_mode_family("project_progress_update") == "project_update"
    assert resolve_meeting_pack_output_mode_family("experiment_proposal") == "builder_debug"


def test_explicit_output_mode_family_remains_supported_for_compatibility():
    assert (
        resolve_meeting_pack_output_mode_family(
            "journal_club",
            explicit_family="lab_meeting",
        )
        == "lab_meeting"
    )
