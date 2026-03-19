from src.contracts.output_bridge import (
    bind_claim_cards_to_run,
    claim_cards_from_claimset_payload,
    normalize_claimset_payload,
)


def test_normalize_claimset_payload_accepts_nested_claimset_wrapper():
    payload = {"claimset": {"claims": [{"statement": "Nested claim."}]}}
    normalized = normalize_claimset_payload(payload)
    assert normalized is not None
    assert isinstance(normalized["claims"], list)
    assert normalized["claims"][0]["statement"] == "Nested claim."


def test_claim_cards_from_claimset_payload_preserves_locator_fields():
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
                        "chunk_id": "p03_c01",
                        "char_start": 120,
                        "char_end": 184,
                        "source_span": [120, 184],
                        "bbox_pdf": [1, 2, 3, 4],
                        "bbox_pct": {"left": 0.1, "top": 0.2, "width": 0.3, "height": 0.4},
                        "highlight_source": "text_match",
                        "grounded": True,
                        "resolution": "OK",
                    }
                ],
            }
        ]
    }

    cards = claim_cards_from_claimset_payload(payload)
    assert len(cards) == 1
    claim = cards[0]
    assert claim.source_claim_id == "CLM-001"
    assert claim.id.startswith("claim_")
    assert claim.evidence_ids and claim.evidence_ids[0].startswith("evidence_")

    evidence = claim.evidence[0]
    assert evidence.locator is not None
    assert evidence.locator.page == 3
    assert evidence.locator.section == "Results"
    assert evidence.locator.chunk_id == "p03_c01"
    assert evidence.locator.span == [120, 184]
    assert evidence.locator.bbox_pdf == [1.0, 2.0, 3.0, 4.0]
    assert evidence.locator.source == "text_match"
    assert evidence.grounded is True
    assert evidence.resolution == "OK"


def test_bind_claim_cards_to_run_assigns_run_id_to_card_and_evidence():
    cards = claim_cards_from_claimset_payload(
        {
            "claims": [
                {
                    "statement": "Fallback should still evaluate claim strength.",
                    "type": "efficacy",
                    "confidence": 0.8,
                    "evidence_spans": [{"quote": "evidence text"}],
                }
            ]
        }
    )

    bound = bind_claim_cards_to_run(cards, "skill-20260313-critical_appraisal")
    assert len(bound) == 1
    assert bound[0].run_id == "skill-20260313-critical_appraisal"
    assert bound[0].evidence[0].run_id == "skill-20260313-critical_appraisal"
    assert bound[0].evidence[0].claim_id == bound[0].id
