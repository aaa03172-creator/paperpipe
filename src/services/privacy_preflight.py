from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from urllib.parse import urlparse

from src.schemas.privacy_preflight import (
    PRIVACY_PREFLIGHT_ROLLBACK_FLAG,
    PrivacyPreflightFinding,
    PrivacyPreflightManualReviewItem,
    PrivacyPreflightMode,
    PrivacyPreflightPayloadClass,
    PrivacyPreflightResponse,
    PrivacyPreflightSummary,
)

_SIGNED_URL_RE = re.compile(
    r"https?://[^\s,<>]+(?:X-Amz-Signature|signature|sig|token|access[_-]?key)[^\s,<>]*",
    re.IGNORECASE,
)
_AUTH_SECRET_RE = re.compile(r"\b(?:Basic|Bearer)\s+[A-Za-z0-9._~+/\-:=]+")
_OPENAI_STYLE_KEY_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9][A-Za-z0-9_-]{7,}\b")
_DATABASE_URL_RE = re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s,;]+", re.IGNORECASE)
_LOCAL_PATH_RE = re.compile(r"(?<![A-Za-z0-9])(?:/Users/[^\s,;]+|/home/[^\s,;]+|[A-Za-z]:\\[^\s,;]+)")
_SHORT_PRIVATE_NAME_CONTEXT_RE = re.compile(
    r"\b[A-Z][a-z]{2,12}'s\b(?=[^.\n]{0,100}\b(?:appointment|birth|born|diagnosis|follow-up|procedure|visit|lumbar puncture)\b)"
)


def resolve_privacy_preflight_mode(env: Mapping[str, str] | None = None) -> PrivacyPreflightMode:
    raw = (env or os.environ).get(PRIVACY_PREFLIGHT_ROLLBACK_FLAG, "off")
    mode = str(raw or "off").strip().lower()
    if mode in {"off", "report_only", "block_on_review"}:
        return mode  # type: ignore[return-value]
    raise ValueError(
        f"invalid {PRIVACY_PREFLIGHT_ROLLBACK_FLAG}={raw!r}; "
        "expected one of: off, report_only, block_on_review"
    )


def public_external_link_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    if _SIGNED_URL_RE.search(text):
        return None
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return text
    return None


def build_privacy_preflight_response(
    *,
    mode: PrivacyPreflightMode,
    payload_class: PrivacyPreflightPayloadClass,
    scope: str,
    payload_texts: Sequence[tuple[str, str]],
    input_refs: Sequence[str] | None = None,
    redaction_applied: bool = False,
) -> PrivacyPreflightResponse:
    source_surfaces = sorted({surface for surface, text in payload_texts if str(text or "").strip()})
    if mode == "off":
        return PrivacyPreflightResponse(
            mode="off",
            status="disabled",
            payload_class=payload_class,
            scope=scope,
            redaction_applied=redaction_applied,
            input_refs=list(input_refs or []),
            source_surfaces=source_surfaces,
        )

    findings = _detect_privacy_preflight_findings(payload_texts)
    manual_review = _manual_review_items_from_findings(findings)
    summary = PrivacyPreflightSummary(
        deterministic_spans=sum(1 for finding in findings if finding.kind == "deterministic_span"),
        false_negative_risks=sum(1 for finding in findings if finding.kind == "false_negative_risk"),
        unexpected_predictions=0,
        manual_review_records=1 if manual_review else 0,
        manual_review_reasons=len(manual_review),
    )
    status = "pass"
    if manual_review:
        status = "blocked" if mode == "block_on_review" else "review_required"
    return PrivacyPreflightResponse(
        mode=mode,
        status=status,
        payload_class=payload_class,
        scope=scope,
        redaction_applied=redaction_applied,
        mutation_applied=False,
        findings=findings,
        manual_review=manual_review,
        summary=summary,
        input_refs=list(input_refs or []),
        source_surfaces=source_surfaces,
    )


def privacy_preflight_should_block(response: PrivacyPreflightResponse) -> bool:
    return response.mode == "block_on_review" and response.status == "blocked"


def _detect_privacy_preflight_findings(payload_texts: Sequence[tuple[str, str]]) -> list[PrivacyPreflightFinding]:
    findings: list[PrivacyPreflightFinding] = []
    for source_surface, text in payload_texts:
        text = str(text or "")
        for pattern, label, reason, preview, message in (
            (_SIGNED_URL_RE, "private_url", "signed_url", "<signed_url>", "Signed URLs should not leave the local runtime."),
            (_AUTH_SECRET_RE, "secret", "auth_secret", "<auth_secret>", "Authorization secrets require review before external inference."),
            (_OPENAI_STYLE_KEY_RE, "secret", "api_key", "<api_key>", "API-key-like strings require review before external inference."),
            (_DATABASE_URL_RE, "secret", "database_url", "<database_url>", "Database URLs require review before external inference."),
            (_LOCAL_PATH_RE, "secret", "local_path", "<local_path>", "Absolute local paths must be dropped before external inference."),
        ):
            for match in pattern.finditer(text):
                findings.append(
                    _finding(
                        index=len(findings) + 1,
                        label=label,
                        source_surface=source_surface,
                        reason=reason,
                        text_preview=preview,
                        start=match.start(),
                        end=match.end(),
                        message=message,
                    )
                )
        for match in _SHORT_PRIVATE_NAME_CONTEXT_RE.finditer(text):
            findings.append(
                _finding(
                    index=len(findings) + 1,
                    kind="false_negative_risk",
                    label="private_person",
                    source_surface=source_surface,
                    reason="short_private_name_context",
                    text_preview="<short_private_name>",
                    start=match.start(),
                    end=match.end(),
                    message="Short possessive names near clinical or personal event cues require review.",
                )
            )
    return findings


def _finding(
    *,
    index: int,
    label: str,
    source_surface: str,
    reason: str,
    text_preview: str,
    start: int,
    end: int,
    message: str,
    kind: str = "deterministic_span",
) -> PrivacyPreflightFinding:
    return PrivacyPreflightFinding(
        finding_id=f"privacy-preflight-{index:03d}",
        kind=kind,  # type: ignore[arg-type]
        severity="high",
        action="manual_review",
        label=label,
        source_surface=source_surface,
        detector="paperpipe-runtime-privacy-preflight",
        reason=reason,
        text_preview=text_preview,
        start=start,
        end=end,
        message=message,
    )


def _manual_review_items_from_findings(findings: Sequence[PrivacyPreflightFinding]) -> list[PrivacyPreflightManualReviewItem]:
    items: list[PrivacyPreflightManualReviewItem] = []
    for finding in findings:
        items.append(
            PrivacyPreflightManualReviewItem(
                review_id=f"privacy-review-{len(items) + 1:03d}",
                severity=finding.severity,
                reason=finding.reason or finding.kind,
                message=finding.message,
                source_surface=finding.source_surface,
                finding_ids=[finding.finding_id],
            )
        )
    return items
