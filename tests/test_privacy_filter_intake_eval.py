from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.evaluate_privacy_filter_intake import (
    PrivacySpan,
    VALID_PRIVACY_LABELS,
    add_deterministic_predictions,
    apply_paperpipe_manual_review_gate,
    apply_paperpipe_preserve_rules,
    detect_deterministic_privacy_spans,
    detect_paperpipe_manual_review_reasons,
    evaluate_records,
    is_prediction_preserved_by_paperpipe_rules,
    load_policy_records,
    load_prediction_records,
    main,
    parse_opf_json_output,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "privacy_filter_intake" / "paperpipe_policy_fixture.jsonl"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def test_evaluate_records_tracks_hits_preserve_conflicts_and_false_negatives(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.jsonl"
    predictions_path = tmp_path / "predictions.jsonl"
    _write_jsonl(
        policy_path,
        [
            {
                "id": "paperpipe-privacy-001",
                "text": "Email clinician@example.org but preserve Park et al. and DOI 10.1000/test.",
                "expected_spans": [
                    {"label": "private_email", "text": "clinician@example.org", "policy": "redact"},
                    {"label": "private_person", "text": "Park et al.", "policy": "preserve"},
                    {"label": "secret", "text": "sk-paperpipe-secret", "policy": "redact"},
                ],
            }
        ],
    )
    _write_jsonl(
        predictions_path,
        [
            {
                "id": "paperpipe-privacy-001",
                "detected_spans": [
                    {"label": "private_email", "text": "clinician@example.org"},
                    {"label": "private_person", "text": "Park et al."},
                    {"label": "account_number", "text": "10.1000/test"},
                ],
            }
        ],
    )

    records = load_policy_records(policy_path)
    predictions = load_prediction_records(predictions_path)
    result = evaluate_records(records, predictions)

    assert result["summary"]["true_positive"] == 1
    assert result["summary"]["false_negative"] == 1
    assert result["summary"]["preserve_conflict"] == 1
    assert result["summary"]["unexpected_prediction"] == 1
    assert result["by_label"]["secret"]["false_negative"] == 1
    assert result["records"][0]["false_negatives"][0]["text"] == "sk-paperpipe-secret"


def test_parse_opf_json_output_accepts_summary_prefix() -> None:
    payload = parse_opf_json_output(
        'summary: output_mode=typed spans=1\n{"detected_spans":[{"label":"private_person","text":"Ben Morgan"}]}'
    )

    assert payload["detected_spans"][0]["label"] == "private_person"


def test_evaluate_records_treats_split_predictions_inside_one_expected_span_as_one_hit(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.jsonl"
    predictions_path = tmp_path / "predictions.jsonl"
    _write_jsonl(
        policy_path,
        [
            {
                "id": "split-address",
                "text": "Mail consent to 12 3rd St, Apt 4B, Boston, MA 02118.",
                "expected_spans": [
                    {"label": "private_address", "text": "12 3rd St, Apt 4B, Boston, MA 02118", "policy": "redact"},
                ],
            }
        ],
    )
    _write_jsonl(
        predictions_path,
        [
            {
                "id": "split-address",
                "detected_spans": [
                    {"label": "private_address", "text": "12"},
                    {"label": "private_address", "text": "3rd St"},
                    {"label": "private_address", "text": "Apt 4B, Boston"},
                    {"label": "private_address", "text": "02118"},
                ],
            }
        ],
    )

    result = evaluate_records(load_policy_records(policy_path), load_prediction_records(predictions_path))

    assert result["summary"]["true_positive"] == 1
    assert result["summary"]["false_negative"] == 0
    assert result["summary"]["unexpected_prediction"] == 0


def test_cli_writes_json_and_markdown_from_prediction_jsonl(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.jsonl"
    predictions_path = tmp_path / "predictions.jsonl"
    output_json = tmp_path / "out" / "privacy_eval.json"
    output_md = tmp_path / "out" / "privacy_eval.md"
    _write_jsonl(
        policy_path,
        [
            {
                "id": "clean-hit",
                "text": "Call +1 415 555 0100.",
                "expected_spans": [
                    {"label": "private_phone", "text": "+1 415 555 0100", "policy": "redact"},
                ],
            }
        ],
    )
    _write_jsonl(
        predictions_path,
        [
            {
                "id": "clean-hit",
                "detected_spans": [
                    {"label": "private_phone", "text": "+1 415 555 0100"},
                ],
            }
        ],
    )

    exit_code = main(
        [
            "--input-jsonl",
            str(policy_path),
            "--predictions-jsonl",
            str(predictions_path),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
            "--fail-on-findings",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["summary"]["true_positive"] == 1
    assert payload["summary"]["false_negative"] == 0
    report = output_md.read_text(encoding="utf-8")
    assert "OpenAI Privacy Filter Intake Evaluation" in report
    assert "private_phone" in report


def test_deterministic_scanner_catches_paperpipe_secret_gaps_without_trial_id_noise() -> None:
    text = (
        "Authorization: Basic beta:wrong-pass; OPENAI_API_KEY=sk-proj-paperpipe-abcdef; "
        "url=https://storage.example.org/private/paper.pdf?X-Amz-Signature=abc123secret; "
        "path=/Users/jangseongjin/paperpipe/Library/private.pdf; "
        "subject JL-042; trial NCT00000123"
    )

    spans = detect_deterministic_privacy_spans(text)
    by_text = {(span.label, span.text) for span in spans}

    assert ("secret", "Basic beta:wrong-pass") in by_text
    assert ("secret", "sk-proj-paperpipe-abcdef") in by_text
    assert ("private_url", "https://storage.example.org/private/paper.pdf?X-Amz-Signature=abc123secret") in by_text
    assert ("secret", "abc123secret") in by_text
    assert ("secret", "/Users/jangseongjin/paperpipe/Library/private.pdf") in by_text
    assert ("account_number", "JL-042") in by_text
    assert ("account_number", "NCT00000123") not in by_text


def test_deterministic_predictions_can_be_added_without_model_predictions() -> None:
    records = load_policy_records(FIXTURE_PATH)
    predictions = add_deterministic_predictions(records, {})
    result = evaluate_records(records, predictions)

    assert result["summary"]["true_positive"] >= 7
    assert result["summary"]["preserve_conflict"] == 0


def test_cli_can_run_deterministic_scanner_without_predictions_or_opf(tmp_path: Path) -> None:
    output_json = tmp_path / "privacy_eval.json"
    output_md = tmp_path / "privacy_eval.md"

    exit_code = main(
        [
            "--input-jsonl",
            str(FIXTURE_PATH),
            "--include-deterministic-scanner",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["summary"]["true_positive"] >= 7
    assert payload["summary"]["preserve_conflict"] == 0
    assert "Source: `deterministic-scanner`" in output_md.read_text(encoding="utf-8")


def test_paperpipe_preserve_rules_filter_public_metadata_without_muting_private_notes() -> None:
    records = [
        {
            "id": "public-author-email",
            "source_surface": "paper_metadata",
            "text": "Public paper metadata includes hkjin@knu.ac.kr.",
            "expected_spans": [],
        },
        {
            "id": "private-beta-email",
            "source_surface": "user_action_payload",
            "text": "Private beta user email is jordan.lee@example.org.",
            "expected_spans": [],
        },
        {
            "id": "trial-id",
            "source_surface": "clinical_metadata",
            "text": "Clinical trial registration is NCT00000123.",
            "expected_spans": [],
        },
        {
            "id": "subject-id",
            "source_surface": "note_body",
            "text": "Participant subject ID is JL-042.",
            "expected_spans": [],
        },
        {
            "id": "docs-placeholder",
            "source_surface": "docs",
            "text": "Docs placeholder email is maya.chen@example.com.",
            "expected_spans": [],
        },
    ]
    predictions = {
        "public-author-email": [PrivacySpan(label="private_email", text="hkjin@knu.ac.kr")],
        "private-beta-email": [PrivacySpan(label="private_email", text="jordan.lee@example.org")],
        "trial-id": [PrivacySpan(label="account_number", text="NCT00000123")],
        "subject-id": [PrivacySpan(label="account_number", text="JL-042")],
        "docs-placeholder": [PrivacySpan(label="private_email", text="maya.chen@example.com")],
    }

    filtered = apply_paperpipe_preserve_rules(records, predictions)

    assert filtered["public-author-email"] == []
    assert filtered["private-beta-email"] == predictions["private-beta-email"]
    assert filtered["trial-id"] == []
    assert filtered["subject-id"] == predictions["subject-id"]
    assert filtered["docs-placeholder"] == []
    assert is_prediction_preserved_by_paperpipe_rules(records[0], predictions["public-author-email"][0])
    assert not is_prediction_preserved_by_paperpipe_rules(records[1], predictions["private-beta-email"][0])


def test_cli_can_apply_paperpipe_preserve_rules_to_saved_predictions(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.jsonl"
    predictions_path = tmp_path / "predictions.jsonl"
    output_json = tmp_path / "privacy_eval.json"
    output_md = tmp_path / "privacy_eval.md"
    _write_jsonl(
        policy_path,
        [
            {
                "id": "public-author-email",
                "source_surface": "paper_metadata",
                "text": "Public paper metadata includes hkjin@knu.ac.kr.",
                "expected_spans": [
                    {"label": "private_email", "text": "hkjin@knu.ac.kr", "policy": "preserve"},
                ],
            },
            {
                "id": "private-beta-email",
                "source_surface": "user_action_payload",
                "text": "Private beta user email is jordan.lee@example.org.",
                "expected_spans": [
                    {"label": "private_email", "text": "jordan.lee@example.org", "policy": "redact"},
                ],
            },
        ],
    )
    _write_jsonl(
        predictions_path,
        [
            {
                "id": "public-author-email",
                "detected_spans": [{"label": "private_email", "text": "hkjin@knu.ac.kr"}],
            },
            {
                "id": "private-beta-email",
                "detected_spans": [{"label": "private_email", "text": "jordan.lee@example.org"}],
            },
        ],
    )

    exit_code = main(
        [
            "--input-jsonl",
            str(policy_path),
            "--predictions-jsonl",
            str(predictions_path),
            "--apply-paperpipe-preserve-rules",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
            "--fail-on-findings",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["summary"]["true_positive"] == 1
    assert payload["summary"]["preserve_conflict"] == 0
    assert "paperpipe-preserve-rules" in output_md.read_text(encoding="utf-8")


def test_manual_review_gate_flags_short_name_context_and_unresolved_findings() -> None:
    records = [
        {
            "id": "clinical-short-name",
            "source_surface": "operator_note",
            "text": "Reminder: Maya's lumbar puncture appointment is scheduled for September 18, 2026.",
            "expected_spans": [
                PrivacySpan(label="private_person", text="Maya"),
                PrivacySpan(label="private_date", text="September 18, 2026"),
            ],
        }
    ]
    predictions = {
        "clinical-short-name": [
            PrivacySpan(label="private_date", text="September 18, 2026"),
        ]
    }

    result = apply_paperpipe_manual_review_gate(records, evaluate_records(records, predictions))
    reasons = result["records"][0]["manual_review"]
    reason_names = {item["reason"] for item in reasons}

    assert result["summary"]["manual_review_records"] == 1
    assert result["summary"]["manual_review_reasons"] == 2
    assert reason_names == {"missed_expected_redaction", "short_private_name_context"}
    assert detect_paperpipe_manual_review_reasons(records[0], result["records"][0]) == reasons


def test_manual_review_gate_does_not_flag_public_citation_context() -> None:
    records = [
        {
            "id": "public-citation",
            "source_surface": "citation",
            "text": "Park et al. published the paper on January 13, 2022.",
            "expected_spans": [],
        }
    ]

    result = apply_paperpipe_manual_review_gate(records, evaluate_records(records, {}))

    assert result["summary"]["manual_review_records"] == 0
    assert result["records"][0]["manual_review"] == []


def test_cli_can_fail_on_manual_review_without_model_findings(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.jsonl"
    predictions_path = tmp_path / "predictions.jsonl"
    output_json = tmp_path / "privacy_eval.json"
    output_md = tmp_path / "privacy_eval.md"
    _write_jsonl(
        policy_path,
        [
            {
                "id": "short-name-context",
                "source_surface": "operator_note",
                "text": "Reminder: Maya's lumbar puncture appointment is scheduled for Friday.",
                "expected_spans": [],
            }
        ],
    )
    _write_jsonl(predictions_path, [{"id": "short-name-context", "detected_spans": []}])

    exit_code = main(
        [
            "--input-jsonl",
            str(policy_path),
            "--predictions-jsonl",
            str(predictions_path),
            "--apply-paperpipe-manual-review-gate",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
            "--fail-on-manual-review",
        ]
    )

    assert exit_code == 1
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["summary"]["false_negative"] == 0
    assert payload["summary"]["manual_review_records"] == 1
    report = output_md.read_text(encoding="utf-8")
    assert "paperpipe-manual-review-gate" in report
    assert "short_private_name_context" in report


def test_paperpipe_privacy_policy_fixture_covers_redact_preserve_and_all_labels() -> None:
    records = load_policy_records(FIXTURE_PATH)
    labels = {span.label for record in records for span in record["expected_spans"]}
    policies = {span.policy for record in records for span in record["expected_spans"]}
    surfaces = {str(record.get("source_surface") or "") for record in records}

    assert len(records) >= 20
    assert labels == VALID_PRIVACY_LABELS
    assert policies == {"redact", "preserve"}
    assert {"request_audit", "paper_metadata", "artifact_json", "beta_feedback", "citation"} <= surfaces


def test_paperpipe_privacy_policy_fixture_flags_unpredicted_redactions_without_preserve_conflicts() -> None:
    records = load_policy_records(FIXTURE_PATH)
    result = evaluate_records(records, {})

    assert result["summary"]["records"] == len(records)
    assert result["summary"]["expected_redact"] > 0
    assert result["summary"]["expected_preserve"] > 0
    assert result["summary"]["false_negative"] == result["summary"]["expected_redact"]
    assert result["summary"]["preserve_conflict"] == 0
