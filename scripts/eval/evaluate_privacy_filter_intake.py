#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

VALID_PRIVACY_LABELS = {
    "account_number",
    "private_address",
    "private_date",
    "private_email",
    "private_person",
    "private_phone",
    "private_url",
    "secret",
}
VALID_POLICIES = {"redact", "preserve"}

_SIGNED_URL_RE = re.compile(
    r"https?://[^\s,<>]+(?:X-Amz-Signature|signature|sig|token|access[_-]?key)[^\s,<>]*",
    re.IGNORECASE,
)
_QUERY_SECRET_RE = re.compile(
    r"(?:X-Amz-Signature|signature|sig|token|access[_-]?key)=([^&\s,.;]+)",
    re.IGNORECASE,
)
_BASIC_AUTH_RE = re.compile(r"\bBasic\s+[A-Za-z0-9._~+/\-:=]+")
_BEARER_AUTH_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/\-=]+")
_OPENAI_STYLE_KEY_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9][A-Za-z0-9_-]{7,}\b")
_DATABASE_URL_RE = re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s,;]+", re.IGNORECASE)
_LOCAL_PATH_RE = re.compile(r"(?<![A-Za-z0-9])(?:/Users/[^\s,;]+|/home/[^\s,;]+|[A-Za-z]:\\[^\s,;]+)")
_SUBJECT_ID_RE = re.compile(r"\b(?:subject|participant)\s+([A-Z]{1,4}-\d{2,6})\b", re.IGNORECASE)
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
_TRIAL_ID_RE = re.compile(r"\b(?:NCT\d{8}|ISRCTN\d{8}|UMIN\d{9,}|ACTRN\d{14})\b", re.IGNORECASE)
_DOCS_PLACEHOLDER_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@example\.(?:com|org|net|kr)\b", re.IGNORECASE)
_DOCS_PLACEHOLDER_SECRET_RE = re.compile(r"\bsk-(?:test|example|placeholder|demo)\b", re.IGNORECASE)
_PAPERPIPE_PAPER_ROUTE_RE = re.compile(r"^/papers/zotero%3A[-A-Z0-9_]+/pdf$", re.IGNORECASE)
_SHORT_PRIVATE_NAME_CONTEXT_RE = re.compile(
    r"\b[A-Z][a-z]{2,12}'s\b(?=[^.\n]{0,100}\b(?:appointment|birth|born|diagnosis|follow-up|procedure|visit|lumbar puncture)\b)"
)
PUBLIC_METADATA_SURFACES = {"paper_metadata", "citation"}
MANUAL_REVIEW_CONTEXT_SURFACES = {"operator_note", "note_body", "beta_feedback", "user_action_payload"}


@dataclass(frozen=True)
class PrivacySpan:
    label: str
    text: str
    policy: str = "redact"
    start: int | None = None
    end: int | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any], *, default_policy: str = "redact") -> "PrivacySpan":
        label = _normalize_label(payload.get("label"))
        if label not in VALID_PRIVACY_LABELS:
            raise ValueError(f"unsupported_privacy_label={label!r}")
        policy = str(payload.get("policy") or default_policy).strip().lower()
        if policy not in VALID_POLICIES:
            raise ValueError(f"unsupported_privacy_policy={policy!r}")
        text = str(payload.get("text") or "").strip()
        if not text:
            raise ValueError("privacy_span_missing_text")
        return cls(
            label=label,
            text=text,
            policy=policy,
            start=_optional_int(payload.get("start")),
            end=_optional_int(payload.get("end")),
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_label(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"\s+", " ", text)
    return text


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not re.fullmatch(r"-?\d+", text):
        return None
    return int(text)


def _span_ranges_overlap(left: PrivacySpan, right: PrivacySpan) -> bool:
    if left.start is None or left.end is None or right.start is None or right.end is None:
        return False
    return max(left.start, right.start) < min(left.end, right.end)


def _span_matches(expected: PrivacySpan, predicted: PrivacySpan) -> bool:
    if expected.label != predicted.label:
        return False
    if _span_ranges_overlap(expected, predicted):
        return True
    expected_text = _normalize_text(expected.text)
    predicted_text = _normalize_text(predicted.text)
    if not expected_text or not predicted_text:
        return False
    return expected_text == predicted_text or expected_text in predicted_text or predicted_text in expected_text


def _span_from_match(label: str, match: re.Match[str], *, group: int = 0) -> PrivacySpan:
    raw_text = match.group(group)
    text = raw_text.rstrip(".,;")
    end = match.start(group) + len(text)
    return PrivacySpan(label=label, text=text, start=match.start(group), end=end)


def detect_deterministic_privacy_spans(text: str) -> list[PrivacySpan]:
    spans: list[PrivacySpan] = []
    for pattern, label in (
        (_SIGNED_URL_RE, "private_url"),
        (_BASIC_AUTH_RE, "secret"),
        (_BEARER_AUTH_RE, "secret"),
        (_OPENAI_STYLE_KEY_RE, "secret"),
        (_DATABASE_URL_RE, "secret"),
        (_LOCAL_PATH_RE, "secret"),
    ):
        spans.extend(_span_from_match(label, match) for match in pattern.finditer(text))
    spans.extend(_span_from_match("secret", match, group=1) for match in _QUERY_SECRET_RE.finditer(text))
    spans.extend(_span_from_match("account_number", match, group=1) for match in _SUBJECT_ID_RE.finditer(text))
    return _dedupe_spans(spans)


def _dedupe_spans(spans: Sequence[PrivacySpan]) -> list[PrivacySpan]:
    seen: set[tuple[str, str, int | None, int | None]] = set()
    deduped: list[PrivacySpan] = []
    for span in spans:
        key = (span.label, _normalize_text(span.text), span.start, span.end)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(span)
    return deduped


def add_deterministic_predictions(
    records: list[dict[str, Any]],
    predictions_by_id: dict[str, list[PrivacySpan]],
) -> dict[str, list[PrivacySpan]]:
    merged: dict[str, list[PrivacySpan]] = {record_id: list(spans) for record_id, spans in predictions_by_id.items()}
    for record in records:
        record_id = str(record["id"])
        merged[record_id] = _dedupe_spans(
            [
                *merged.get(record_id, []),
                *detect_deterministic_privacy_spans(str(record.get("text") or "")),
            ]
        )
    return merged


def is_prediction_preserved_by_paperpipe_rules(record: dict[str, Any], prediction: PrivacySpan) -> bool:
    surface = str(record.get("source_surface") or "").strip().lower()
    text = prediction.text.strip()
    label = prediction.label

    if surface in PUBLIC_METADATA_SURFACES:
        if label in {"private_person", "private_date", "private_email", "private_address"}:
            return True
        if label == "account_number" and _DOI_RE.search(text):
            return True
        if label == "private_url" and text.lower().startswith("https://doi.org/"):
            return True

    if surface == "clinical_metadata" and label == "account_number" and _TRIAL_ID_RE.fullmatch(text):
        return True

    if surface == "docs":
        if label == "private_email" and _DOCS_PLACEHOLDER_EMAIL_RE.fullmatch(text):
            return True
        if label == "secret" and _DOCS_PLACEHOLDER_SECRET_RE.fullmatch(text):
            return True

    if surface == "obsidian_note":
        if label == "account_number" and text.lower().startswith("zotero:"):
            return True
        if label == "private_url" and _PAPERPIPE_PAPER_ROUTE_RE.fullmatch(text):
            return True

    return False


def apply_paperpipe_preserve_rules(
    records: list[dict[str, Any]],
    predictions_by_id: dict[str, list[PrivacySpan]],
) -> dict[str, list[PrivacySpan]]:
    records_by_id = {str(record["id"]): record for record in records}
    filtered: dict[str, list[PrivacySpan]] = {}
    for record_id, predictions in predictions_by_id.items():
        record = records_by_id.get(record_id)
        if record is None:
            filtered[record_id] = list(predictions)
            continue
        filtered[record_id] = [
            prediction for prediction in predictions if not is_prediction_preserved_by_paperpipe_rules(record, prediction)
        ]
    return filtered


def detect_paperpipe_manual_review_reasons(
    record: dict[str, Any],
    evaluated_record: dict[str, Any],
) -> list[dict[str, str]]:
    reasons: list[dict[str, str]] = []
    if evaluated_record.get("false_negatives"):
        reasons.append(
            {
                "severity": "high",
                "reason": "missed_expected_redaction",
                "message": "Expected private data was not predicted and must be reviewed before export or external inference.",
            }
        )
    if evaluated_record.get("unexpected_predictions"):
        reasons.append(
            {
                "severity": "medium",
                "reason": "unexpected_prediction",
                "message": "A detector emitted an unexpected span; review whether the scanner boundary or fixture policy is too broad.",
            }
        )

    surface = str(record.get("source_surface") or "").strip().lower()
    text = str(record.get("text") or "")
    if surface in MANUAL_REVIEW_CONTEXT_SURFACES and _SHORT_PRIVATE_NAME_CONTEXT_RE.search(text):
        reasons.append(
            {
                "severity": "high",
                "reason": "short_private_name_context",
                "message": "A short possessive name appears near a clinical or personal event cue; model-only redaction may miss it.",
            }
        )
    return reasons


def apply_paperpipe_manual_review_gate(records: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    records_by_id = {str(record["id"]): record for record in records}
    manual_review_records = 0
    manual_review_reasons = 0
    for evaluated_record in result["records"]:
        record = records_by_id.get(str(evaluated_record["id"]), {})
        reasons = detect_paperpipe_manual_review_reasons(record, evaluated_record)
        evaluated_record["manual_review"] = reasons
        if reasons:
            manual_review_records += 1
            manual_review_reasons += len(reasons)
    result["summary"]["manual_review_records"] = manual_review_records
    result["summary"]["manual_review_reasons"] = manual_review_reasons
    return result


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"jsonl_line_not_object path={path} line={line_no}")
        rows.append(payload)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_policy_records(path: Path) -> list[dict[str, Any]]:
    records = _read_jsonl(path)
    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        record_id = str(record.get("id") or "").strip()
        if not record_id:
            raise ValueError(f"policy_record_missing_id line={index}")
        if record_id in seen_ids:
            raise ValueError(f"duplicate_policy_record_id={record_id}")
        seen_ids.add(record_id)
        text = str(record.get("text") or "").strip()
        if not text:
            raise ValueError(f"policy_record_missing_text id={record_id}")
        expected = [
            PrivacySpan.from_payload(span, default_policy="redact")
            for span in (record.get("expected_spans") or [])
            if isinstance(span, dict)
        ]
        normalized.append(
            {
                "id": record_id,
                "text": text,
                "source_surface": str(record.get("source_surface") or "").strip(),
                "expected_spans": expected,
            }
        )
    return normalized


def load_prediction_records(path: Path) -> dict[str, list[PrivacySpan]]:
    rows = _read_jsonl(path)
    predictions: dict[str, list[PrivacySpan]] = {}
    for index, row in enumerate(rows, start=1):
        record_id = str(row.get("id") or "").strip()
        if not record_id:
            raise ValueError(f"prediction_record_missing_id line={index}")
        detected = row.get("detected_spans")
        if detected is None and isinstance(row.get("opf_output"), dict):
            detected = row["opf_output"].get("detected_spans")
        spans = [
            PrivacySpan.from_payload(span, default_policy="redact")
            for span in (detected or [])
            if isinstance(span, dict)
        ]
        predictions[record_id] = spans
    return predictions


def parse_opf_json_output(raw: str) -> dict[str, Any]:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("opf_output_missing_json_object")
    payload = json.loads(raw[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("opf_output_json_not_object")
    return payload


def run_opf_for_record(
    record: dict[str, Any],
    *,
    opf_command: Sequence[str],
    opf_extra_args: Sequence[str],
    timeout_seconds: int,
) -> list[PrivacySpan]:
    command = [*opf_command, *opf_extra_args, str(record["text"]), "--format", "json"]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"opf_failed id={record['id']} code={completed.returncode} stderr={stderr}")
    payload = parse_opf_json_output(completed.stdout)
    return [
        PrivacySpan.from_payload(span, default_policy="redact")
        for span in (payload.get("detected_spans") or [])
        if isinstance(span, dict)
    ]


def collect_predictions(
    records: list[dict[str, Any]],
    *,
    predictions_path: Path | None,
    use_opf: bool,
    opf_command: Sequence[str],
    opf_extra_args: Sequence[str],
    timeout_seconds: int,
) -> dict[str, list[PrivacySpan]]:
    if predictions_path is not None:
        return load_prediction_records(predictions_path)
    if not use_opf:
        raise ValueError("provide --predictions-jsonl or pass --use-opf")
    return {
        str(record["id"]): run_opf_for_record(
            record,
            opf_command=opf_command,
            opf_extra_args=opf_extra_args,
            timeout_seconds=timeout_seconds,
        )
        for record in records
    }


def evaluate_records(records: list[dict[str, Any]], predictions_by_id: dict[str, list[PrivacySpan]]) -> dict[str, Any]:
    evaluated_records: list[dict[str, Any]] = []
    summary = {
        "records": len(records),
        "expected_redact": 0,
        "expected_preserve": 0,
        "predicted_spans": 0,
        "true_positive": 0,
        "false_negative": 0,
        "unexpected_prediction": 0,
        "preserve_conflict": 0,
        "unsupported_prediction_ids": [],
    }
    by_label: dict[str, dict[str, int]] = {
        label: {
            "expected_redact": 0,
            "true_positive": 0,
            "false_negative": 0,
            "unexpected_prediction": 0,
            "preserve_conflict": 0,
        }
        for label in sorted(VALID_PRIVACY_LABELS)
    }

    known_record_ids = {str(record["id"]) for record in records}
    for prediction_id in sorted(set(predictions_by_id) - known_record_ids):
        summary["unsupported_prediction_ids"].append(prediction_id)

    for record in records:
        record_id = str(record["id"])
        expected_spans: list[PrivacySpan] = record["expected_spans"]
        expected_redact = [span for span in expected_spans if span.policy == "redact"]
        expected_preserve = [span for span in expected_spans if span.policy == "preserve"]
        predictions = predictions_by_id.get(record_id, [])
        matched_prediction_indexes: set[int] = set()

        false_negatives: list[dict[str, Any]] = []
        for expected in expected_redact:
            summary["expected_redact"] += 1
            by_label[expected.label]["expected_redact"] += 1
            matching_indexes = [
                idx for idx, prediction in enumerate(predictions) if _span_matches(expected, prediction)
            ]
            if not matching_indexes:
                summary["false_negative"] += 1
                by_label[expected.label]["false_negative"] += 1
                false_negatives.append(_span_to_payload(expected))
                continue
            matched_prediction_indexes.update(matching_indexes)
            summary["true_positive"] += 1
            by_label[expected.label]["true_positive"] += 1

        preserve_conflicts: list[dict[str, Any]] = []
        unexpected_predictions: list[dict[str, Any]] = []
        for idx, prediction in enumerate(predictions):
            summary["predicted_spans"] += 1
            if idx in matched_prediction_indexes:
                continue
            preserve_match = next((span for span in expected_preserve if _span_matches(span, prediction)), None)
            if preserve_match is not None:
                summary["preserve_conflict"] += 1
                by_label[prediction.label]["preserve_conflict"] += 1
                preserve_conflicts.append(
                    {
                        "prediction": _span_to_payload(prediction),
                        "expected_preserve": _span_to_payload(preserve_match),
                    }
                )
                continue
            summary["unexpected_prediction"] += 1
            by_label[prediction.label]["unexpected_prediction"] += 1
            unexpected_predictions.append(_span_to_payload(prediction))

        summary["expected_preserve"] += len(expected_preserve)
        evaluated_records.append(
            {
                "id": record_id,
                "source_surface": record.get("source_surface") or "",
                "expected_redact": [_span_to_payload(span) for span in expected_redact],
                "expected_preserve": [_span_to_payload(span) for span in expected_preserve],
                "predicted_spans": [_span_to_payload(span) for span in predictions],
                "false_negatives": false_negatives,
                "preserve_conflicts": preserve_conflicts,
                "unexpected_predictions": unexpected_predictions,
            }
        )

    return {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "summary": summary,
        "by_label": by_label,
        "records": evaluated_records,
    }


def _span_to_payload(span: PrivacySpan) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "label": span.label,
        "text": span.text,
        "policy": span.policy,
    }
    if span.start is not None:
        payload["start"] = span.start
    if span.end is not None:
        payload["end"] = span.end
    return payload


def render_markdown_report(result: dict[str, Any], *, source_name: str) -> str:
    summary = result["summary"]
    lines = [
        "# OpenAI Privacy Filter Intake Evaluation",
        "",
        "Status: generated eval report",
        f"Date: {result['generated_at']}",
        f"Source: `{source_name}`",
        "",
        "## Summary",
        "",
        f"- Records: `{summary['records']}`",
        f"- Expected redact spans: `{summary['expected_redact']}`",
        f"- Expected preserve spans: `{summary['expected_preserve']}`",
        f"- Predicted spans: `{summary['predicted_spans']}`",
        f"- True positives: `{summary['true_positive']}`",
        f"- False negatives: `{summary['false_negative']}`",
        f"- Unexpected predictions: `{summary['unexpected_prediction']}`",
        f"- Preserve conflicts: `{summary['preserve_conflict']}`",
    ]
    if "manual_review_records" in summary:
        lines.extend(
            [
                f"- Manual review records: `{summary['manual_review_records']}`",
                f"- Manual review reasons: `{summary['manual_review_reasons']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Label Breakdown",
            "",
            "| Label | Expected redact | True positive | False negative | Unexpected | Preserve conflict |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label, counts in result["by_label"].items():
        lines.append(
            "| "
            + " | ".join(
                [
                    label,
                    str(counts["expected_redact"]),
                    str(counts["true_positive"]),
                    str(counts["false_negative"]),
                    str(counts["unexpected_prediction"]),
                    str(counts["preserve_conflict"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Review Queue", ""])
    for record in result["records"]:
        if (
            not record["false_negatives"]
            and not record["preserve_conflicts"]
            and not record["unexpected_predictions"]
            and not record.get("manual_review")
        ):
            continue
        lines.append(f"### `{record['id']}`")
        if record.get("manual_review"):
            lines.append("")
            lines.append("Manual review:")
            for item in record["manual_review"]:
                lines.append(f"- `{item['severity']}` `{item['reason']}`: {item['message']}")
        if record["false_negatives"]:
            lines.append("")
            lines.append("False negatives:")
            for span in record["false_negatives"]:
                lines.append(f"- `{span['label']}` should redact `{span['text']}`")
        if record["preserve_conflicts"]:
            lines.append("")
            lines.append("Preserve conflicts:")
            for item in record["preserve_conflicts"]:
                prediction = item["prediction"]
                lines.append(f"- `{prediction['label']}` predicted for preserve text `{prediction['text']}`")
        if record["unexpected_predictions"]:
            lines.append("")
            lines.append("Unexpected predictions:")
            for span in record["unexpected_predictions"]:
                lines.append(f"- `{span['label']}` predicted `{span['text']}`")
        lines.append("")
    if summary["unsupported_prediction_ids"]:
        lines.extend(["## Unsupported Prediction IDs", ""])
        for prediction_id in summary["unsupported_prediction_ids"]:
            lines.append(f"- `{prediction_id}`")
        lines.append("")
    lines.extend(
        [
            "## Interpretation Guardrail",
            "",
            "This report is an intake evaluation, not a compliance or anonymization guarantee. Preserve conflicts matter in PaperPipe because public biomedical metadata, provenance, and source lineage often need to remain visible.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate OpenAI Privacy Filter predictions against PaperPipe privacy-policy fixtures."
    )
    parser.add_argument("--input-jsonl", required=True, type=Path, help="Policy fixture JSONL with id, text, and expected_spans.")
    parser.add_argument("--predictions-jsonl", type=Path, help="Optional prediction JSONL with id and detected_spans.")
    parser.add_argument("--use-opf", action="store_true", help="Call the local opf CLI instead of reading predictions JSONL.")
    parser.add_argument("--opf-command", default="opf", help="Command used when --use-opf is set. Defaults to opf.")
    parser.add_argument("--opf-extra-arg", action="append", default=[], help="Extra argument forwarded to opf. Repeatable.")
    parser.add_argument("--timeout-seconds", type=int, default=120, help="Per-record opf timeout.")
    parser.add_argument(
        "--include-deterministic-scanner",
        action="store_true",
        help="Augment model predictions with PaperPipe deterministic secret/path/signed-URL rules.",
    )
    parser.add_argument(
        "--apply-paperpipe-preserve-rules",
        action="store_true",
        help="Suppress predictions that match trusted PaperPipe public-metadata or placeholder preserve rules.",
    )
    parser.add_argument(
        "--apply-paperpipe-manual-review-gate",
        action="store_true",
        help="Add eval-only manual review routing for unresolved PaperPipe privacy risk signals.",
    )
    parser.add_argument("--output-json", type=Path, help="Path for machine-readable evaluation JSON.")
    parser.add_argument("--output-md", type=Path, help="Path for Markdown report.")
    parser.add_argument("--fail-on-findings", action="store_true", help="Exit non-zero when false negatives or preserve conflicts exist.")
    parser.add_argument("--fail-on-manual-review", action="store_true", help="Exit non-zero when the manual review gate routes any record.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = load_policy_records(args.input_jsonl)
    if args.include_deterministic_scanner and args.predictions_jsonl is None and not args.use_opf:
        predictions = {}
    else:
        predictions = collect_predictions(
            records,
            predictions_path=args.predictions_jsonl,
            use_opf=bool(args.use_opf),
            opf_command=shlex.split(args.opf_command),
            opf_extra_args=args.opf_extra_arg,
            timeout_seconds=max(int(args.timeout_seconds), 1),
        )
    if args.include_deterministic_scanner:
        predictions = add_deterministic_predictions(records, predictions)
    if args.apply_paperpipe_preserve_rules:
        predictions = apply_paperpipe_preserve_rules(records, predictions)
    result = evaluate_records(records, predictions)
    if args.apply_paperpipe_manual_review_gate:
        result = apply_paperpipe_manual_review_gate(records, result)

    if args.output_json:
        _write_json(args.output_json, result)
    if args.output_md:
        source_parts: list[str] = []
        if args.predictions_jsonl:
            source_parts.append(str(args.predictions_jsonl))
        elif args.use_opf:
            source_parts.append(str(args.opf_command))
        if args.include_deterministic_scanner:
            source_parts.append("deterministic-scanner")
        if args.apply_paperpipe_preserve_rules:
            source_parts.append("paperpipe-preserve-rules")
        if args.apply_paperpipe_manual_review_gate:
            source_parts.append("paperpipe-manual-review-gate")
        source_name = " + ".join(source_parts) or str(args.opf_command)
        _write_text(args.output_md, render_markdown_report(result, source_name=source_name))
    if not args.output_json and not args.output_md:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    summary = result["summary"]
    if args.fail_on_findings and (summary["false_negative"] > 0 or summary["preserve_conflict"] > 0):
        return 1
    if args.fail_on_manual_review and summary.get("manual_review_records", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
