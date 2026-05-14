from src.services.summary_normalizer import normalize_summary_text


def test_normalize_removes_translation_tail():
    raw = (
        "이 논문은 인지 기능 저하를 설명한다. "
        "(Translation: This paper explains cognitive decline and prognosis.)"
    )
    result = normalize_summary_text(raw, max_chars=320)

    assert result.changed is True
    assert "Translation:" not in result.text
    assert result.text.endswith("설명한다.")
    assert "removed_translation_tail" in result.reasons


def test_normalize_removes_tldr_prefix():
    raw = (
        "Here is a possible TL;DR in one single Korean sentence: "
        "\"이 연구는 장내 미생물과 인지 기능의 상관을 제시한다.\""
    )
    result = normalize_summary_text(raw, max_chars=320)

    assert result.changed is True
    assert "Here is a possible TL;DR" not in result.text
    assert "removed_tldr_prefix" in result.reasons


def test_normalize_trims_long_text():
    raw = "A" * 500
    result = normalize_summary_text(raw, max_chars=120)

    assert result.changed is True
    assert len(result.text) <= 120
    assert "trimmed_length" in result.reasons


def test_normalize_apology_to_unavailable():
    raw = (
        "I apologize, but since there is no title or abstract provided, "
        "I cannot summarize the core contribution."
    )
    result = normalize_summary_text(raw, max_chars=320)

    assert result.changed is True
    assert result.text == "Summary unavailable."
    assert "normalized_apology" in result.reasons


def test_normalize_keeps_clean_summary():
    raw = "이 연구는 경도인지장애 환자군에서 바이오마커의 예측 성능을 비교했다."
    result = normalize_summary_text(raw, max_chars=320)

    assert result.changed is False
    assert result.text == raw
    assert result.reasons == []
