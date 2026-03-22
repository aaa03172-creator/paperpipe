from src.skills.runner import _claim_cards_from_payload, _run_critical_appraisal_fallback


def test_claim_cards_from_payload_generates_stable_ids_and_locators():
    payload = {
        "claims": [
            {
                "claim_id": "CLM-001",
                "type": "efficacy",
                "statement": "The intervention improved the primary endpoint.",
                "confidence": 0.93,
                "evidence_spans": [
                    {
                        "quote": "The intervention significantly improved the primary endpoint.",
                        "page": 3,
                        "section": "Results",
                        "chunk_id": "chunk_12",
                        "char_start": 120,
                        "char_end": 184,
                        "source_span": [120, 184],
                        "highlight_source": "text_match",
                    }
                ],
            }
        ]
    }

    cards = _claim_cards_from_payload(payload)
    assert len(cards) == 1

    claim = cards[0]
    assert claim.id.startswith("claim_")
    assert claim.source_claim_id == "CLM-001"
    assert claim.evidence_ids and claim.evidence_ids[0].startswith("evidence_")

    evidence = claim.evidence[0]
    assert evidence.id == claim.evidence_ids[0]
    assert evidence.claim_id == claim.id
    assert evidence.run_id is None
    assert evidence.locator is not None
    assert evidence.locator.page == 3
    assert evidence.locator.section == "Results"
    assert evidence.locator.chunk_id == "chunk_12"
    assert evidence.locator.span == [120, 184]
    assert evidence.locator.source == "text_match"


def test_critical_appraisal_fallback_handles_missing_checks_list():
    cards = _claim_cards_from_payload(
        {
            "claims": [
                {
                    "claim_id": "CLM-001",
                    "type": "efficacy",
                    "statement": "Fallback should still evaluate claim strength.",
                    "confidence": 0.8,
                    "evidence_spans": [{"quote": "evidence text"}],
                }
            ]
        }
    )
    appraisal, mode = _run_critical_appraisal_fallback(cards, {"checks": None})
    assert mode == "native-fallback"
    assert appraisal["claim_count"] == 1
    assert appraisal["evidence_count"] == 1
    assert appraisal["inconsistent_checks"] == 0
