from __future__ import annotations

import re
from dataclasses import dataclass


TRANSLATION_TAIL_RE = re.compile(r"\(\s*translation\s*:\s*.*?\)\s*$", re.IGNORECASE | re.DOTALL)
TLDR_PREFIX_RE = re.compile(r"^\s*here is a possible tl;dr.*?:\s*", re.IGNORECASE | re.DOTALL)
LEADING_LABEL_RE = re.compile(
    r"^\s*(abstract|significance|importance|objective|background|findings|conclusions?|evidence review)\s*[:\-]?\s*",
    re.IGNORECASE,
)
APOLOGY_RE = re.compile(r"^\s*i apologize, but\b", re.IGNORECASE)


@dataclass(frozen=True)
class SummaryNormalizationResult:
    text: str
    changed: bool
    reasons: list[str]


def _collapse_whitespace(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _trim_to_sentence_budget(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    pieces = re.split(r"(?<=[\.\!\?。！？])\s+", text)
    out: list[str] = []
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        candidate = " ".join(out + [piece]).strip()
        if len(candidate) <= max_chars:
            out.append(piece)
            continue
        break

    if out:
        return " ".join(out).strip()
    if max_chars <= 1:
        return text[:max_chars]
    return text[: max_chars - 1].rstrip() + "…"


def normalize_summary_text(raw: str | None, max_chars: int = 320) -> SummaryNormalizationResult:
    original = (raw or "").strip()
    if not original:
        return SummaryNormalizationResult(text=original, changed=False, reasons=[])

    reasons: list[str] = []
    text = _collapse_whitespace(original)

    cleaned = TLDR_PREFIX_RE.sub("", text).strip()
    if cleaned != text:
        reasons.append("removed_tldr_prefix")
        text = cleaned

    while True:
        cleaned = TRANSLATION_TAIL_RE.sub("", text).strip()
        if cleaned == text:
            break
        reasons.append("removed_translation_tail")
        text = cleaned

    cleaned = LEADING_LABEL_RE.sub("", text).strip()
    if cleaned != text:
        reasons.append("removed_leading_label")
        text = cleaned

    if APOLOGY_RE.match(text):
        text = "Summary unavailable."
        reasons.append("normalized_apology")

    text = _collapse_whitespace(text)

    trimmed = _trim_to_sentence_budget(text, max_chars=max_chars)
    if trimmed != text:
        reasons.append("trimmed_length")
        text = trimmed

    return SummaryNormalizationResult(text=text, changed=(text != original), reasons=reasons)
