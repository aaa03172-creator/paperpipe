from src.persona_modes import normalize_persona_selection, resolve_reasoning_persona_hint


def test_normalize_persona_selection_maps_legacy_profile_alias():
    selection = normalize_persona_selection(persona_id="coglab")

    assert selection.persona_id == "coglab"
    assert selection.reasoning_persona is None
    assert selection.profile_id == "coglab"


def test_normalize_persona_selection_preserves_split_fields_without_legacy_persona():
    selection = normalize_persona_selection(
        persona_id="default",
        reasoning_persona="researcher",
        profile_id="coglab",
    )

    assert selection.persona_id == "coglab"
    assert selection.reasoning_persona == "researcher"
    assert selection.profile_id == "coglab"


def test_resolve_reasoning_persona_hint_returns_lane_specific_prompt():
    hint = resolve_reasoning_persona_hint("extractor_reviewer")

    assert hint is not None
    assert "reasoning_persona=extractor_reviewer" in hint
    assert "conservative claim promotion" in hint
