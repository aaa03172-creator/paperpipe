from src.llm_prompts import (
    build_deep_read_prompt,
    build_one_liner_prompt,
    build_slot_classification_prompt,
    build_tagging_prompts,
)


def test_build_deep_read_prompt_uses_slot_variants():
    methods_prompt = build_deep_read_prompt(
        {"slot": "methods", "title": "M1", "summary": "S1"}
    )
    mechanism_prompt = build_deep_read_prompt(
        {"slot": "mechanism", "title": "M2", "summary": "S2"}
    )
    default_prompt = build_deep_read_prompt({"slot": "clinical", "title": "M3", "summary": "S3"})

    assert "METHODOLOGY paper" in methods_prompt
    assert "MECHANISTIC paper" in mechanism_prompt
    assert "Analyze this paper for a neuroscientist." in default_prompt


def test_build_one_liner_prompt_contains_title_and_summary():
    prompt = build_one_liner_prompt({"title": "Title X", "summary": "Summary Y"})
    assert "Title X" in prompt
    assert "Summary Y" in prompt


def test_build_slot_classification_prompt_truncates_summary():
    long_summary = ("A" * 1500) + "CUT_MARKER_AFTER_1500"
    prompt = build_slot_classification_prompt(
        {"title": "Paper", "summary": long_summary}, "Methods"
    )
    assert "Current Rule-based Guess: Methods" in prompt
    assert ("A" * 1500) in prompt
    assert "CUT_MARKER_AFTER_1500" not in prompt


def test_build_tagging_prompts_includes_alias_and_full_text_snippet():
    full_text = ("B" * 20000) + "TAIL_MARKER_NOT_INCLUDED"
    system_prompt, user_prompt = build_tagging_prompts(
        {
            "title": "P",
            "summary": "S",
            "full_text": full_text,
        },
        {"AD": "AlzheimerDisease"},
    )

    assert "Entity Normalization" in system_prompt
    assert "'AD' -> 'AlzheimerDisease'" in system_prompt
    assert "Full Text Content (First 20k chars)" in user_prompt
    assert ("B" * 20000) in user_prompt
    assert "TAIL_MARKER_NOT_INCLUDED" not in user_prompt
