from __future__ import annotations

from src.schemas.privacy_preflight import (
    PRIVACY_PREFLIGHT_ROLLBACK_FLAG,
    PRIVACY_PREFLIGHT_SCHEMA_VERSION,
    PrivacyPreflightFinding,
    PrivacyPreflightManualReviewItem,
    PrivacyPreflightResponse,
    PrivacyPreflightRuntimeConfig,
    PrivacyPreflightSummary,
)
from src.services.privacy_preflight import (
    build_privacy_preflight_response,
    privacy_preflight_should_block,
    public_external_link_or_none,
    resolve_privacy_preflight_mode,
)


def test_privacy_preflight_default_contract_is_off_and_non_mutating() -> None:
    config = PrivacyPreflightRuntimeConfig()
    response = PrivacyPreflightResponse()

    assert config.schema_version == PRIVACY_PREFLIGHT_SCHEMA_VERSION
    assert config.mode == "off"
    assert config.rollback_flag == PRIVACY_PREFLIGHT_ROLLBACK_FLAG
    assert config.mutation_allowed is False
    assert response.mode == "off"
    assert response.status == "disabled"
    assert response.rollback_flag == PRIVACY_PREFLIGHT_ROLLBACK_FLAG
    assert response.payload_class == "local_only"
    assert response.redaction_applied is False
    assert response.mutation_applied is False


def test_privacy_preflight_report_only_response_serializes_review_contract() -> None:
    response = PrivacyPreflightResponse(
        mode="report_only",
        status="review_required",
        payload_class="external_allowed",
        findings=[
            PrivacyPreflightFinding(
                finding_id="finding-001",
                kind="false_negative_risk",
                severity="high",
                action="manual_review",
                label="private_person",
                source_surface="operator_note",
                detector="paperpipe-manual-review-gate",
                reason="short_private_name_context",
                text_preview="Maya",
                message="Short private name near a clinical event cue requires review.",
            )
        ],
        manual_review=[
            PrivacyPreflightManualReviewItem(
                review_id="review-001",
                severity="high",
                reason="short_private_name_context",
                source_surface="operator_note",
                finding_ids=["finding-001"],
                message="Review before export or external inference.",
            )
        ],
        summary=PrivacyPreflightSummary(false_negative_risks=1, manual_review_records=1, manual_review_reasons=1),
        input_refs=["paper:paper-a"],
        source_surfaces=["operator_note"],
    )

    payload = response.model_dump(mode="json")

    assert payload["schema_version"] == PRIVACY_PREFLIGHT_SCHEMA_VERSION
    assert payload["mode"] == "report_only"
    assert payload["status"] == "review_required"
    assert payload["mutation_applied"] is False
    assert payload["findings"][0]["action"] == "manual_review"
    assert payload["manual_review"][0]["finding_ids"] == ["finding-001"]
    assert payload["summary"]["manual_review_records"] == 1


def test_privacy_preflight_block_on_review_contract_keeps_rollback_flag_visible() -> None:
    response = PrivacyPreflightResponse(
        mode="block_on_review",
        status="blocked",
        summary=PrivacyPreflightSummary(manual_review_records=2, manual_review_reasons=3),
    )

    payload = response.model_dump(mode="json")

    assert payload["mode"] == "block_on_review"
    assert payload["status"] == "blocked"
    assert payload["rollback_flag"] == "LATTICE_PRIVACY_PREFLIGHT_MODE"
    assert payload["summary"]["manual_review_reasons"] == 3


def test_runtime_privacy_preflight_report_only_masks_sensitive_previews() -> None:
    response = build_privacy_preflight_response(
        mode="report_only",
        payload_class="external_allowed",
        scope="clinical_extraction_external_payload",
        payload_texts=[
            ("source_ref", "/Users/jangseongjin/paperpipe/Library/private.pdf"),
            ("summary", "Reminder: Maya's lumbar puncture appointment is scheduled tomorrow."),
            ("config", "OPENAI_API_KEY=sk-proj-paperpipe-abcdef"),
        ],
        input_refs=["paper:paper-a"],
        redaction_applied=True,
    )

    payload = response.model_dump(mode="json")
    previews = {finding["text_preview"] for finding in payload["findings"]}

    assert payload["status"] == "review_required"
    assert payload["summary"]["deterministic_spans"] == 2
    assert payload["summary"]["false_negative_risks"] == 1
    assert payload["summary"]["manual_review_records"] == 1
    assert "<local_path>" in previews
    assert "<api_key>" in previews
    assert "<short_private_name>" in previews
    assert "sk-proj-paperpipe-abcdef" not in str(payload)
    assert "/Users/jangseongjin" not in str(payload)


def test_runtime_privacy_preflight_block_mode_marks_review_as_blocked() -> None:
    response = build_privacy_preflight_response(
        mode="block_on_review",
        payload_class="external_allowed",
        scope="clinical_extraction_external_payload",
        payload_texts=[("summary", "Reminder: Maya's visit is scheduled tomorrow.")],
    )

    assert response.status == "blocked"
    assert response.summary.manual_review_records == 1


def test_privacy_preflight_report_only_flags_local_path_without_mutation() -> None:
    response = build_privacy_preflight_response(
        mode="report_only",
        payload_class="external_allowed",
        scope="clinical_extraction_external_payload",
        payload_texts=[("methods_snippet", "See /Users/example/private-note.md for details")],
        input_refs=["paper:paper-001"],
    )

    assert response.status == "review_required"
    assert response.payload_class == "external_allowed"
    assert response.mutation_applied is False
    assert response.manual_review[0].reason == "local_path"
    assert privacy_preflight_should_block(response) is False


def test_privacy_preflight_block_on_review_blocks_local_path_without_mutation() -> None:
    response = build_privacy_preflight_response(
        mode="block_on_review",
        payload_class="external_allowed",
        scope="clinical_extraction_external_payload",
        payload_texts=[("methods_snippet", "See /Users/example/private-note.md for details")],
        input_refs=["paper:paper-001"],
    )

    assert response.status == "blocked"
    assert response.mutation_applied is False
    assert response.manual_review[0].reason == "local_path"
    assert privacy_preflight_should_block(response) is True


def test_public_external_link_or_none_drops_local_paths() -> None:
    assert public_external_link_or_none("/Users/jangseongjin/paperpipe/private.pdf") is None
    assert public_external_link_or_none("/papers/zotero%3Aabc/pdf") is None
    assert public_external_link_or_none("https://storage.example.org/private.pdf?X-Amz-Signature=abc123") is None
    assert public_external_link_or_none("https://doi.org/10.1000/example") == "https://doi.org/10.1000/example"


def test_resolve_privacy_preflight_mode_rejects_invalid_explicit_value() -> None:
    try:
        resolve_privacy_preflight_mode({"LATTICE_PRIVACY_PREFLIGHT_MODE": "surprise"})
    except ValueError as exc:
        assert "LATTICE_PRIVACY_PREFLIGHT_MODE" in str(exc)
    else:
        raise AssertionError("invalid privacy preflight mode should fail clearly")
