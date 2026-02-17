import json

import pytest

from src.json_repair import repair_and_parse_json
from tests.fixtures.broken_json import (
    case_chatter_with_json,
    case_hansson_truncated,
    case_markdown,
    case_python_style,
    case_trailing_commas,
)


def test_repair_markdown_fence_json():
    data = repair_and_parse_json(case_markdown)
    assert data["hard_tags"]["species"] == "human"
    assert data["confidence"] == 0.87


def test_repair_python_style_literals_and_quotes():
    data = repair_and_parse_json(case_python_style)
    assert data["hard_tags"]["species"] is None
    assert data["hard_tags"]["model"] == "5xFAD"


def test_repair_trailing_commas():
    data = repair_and_parse_json(case_trailing_commas)
    assert data["hard_tags"]["species"] == "mouse"
    assert data["soft_tags"] == ["#Preclinical"]


def test_repair_chatter_wrapper():
    data = repair_and_parse_json(case_chatter_with_json)
    assert data["hard_tags"]["sample_size"] == 58
    assert "#Clinical/MCI" in data["soft_tags"]


def test_hansson_truncated_raises_decode_error():
    with pytest.raises(json.JSONDecodeError):
        repair_and_parse_json(case_hansson_truncated)
