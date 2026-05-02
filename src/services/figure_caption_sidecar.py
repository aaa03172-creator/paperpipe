from __future__ import annotations

from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Any

from src.contracts.artifact_views import iter_text_sections
from src.schemas.figure_captions import FigureCaptionEntry, FigureCaptionMetrics, FigureCaptionSidecar
from src.skills.storage import atomic_write_text

_FIGURE_START_RE = re.compile(r"(?im)^\s*(Fig(?:ure)?\.?\s+(?P<number>\d+[A-Za-z]?)\.)\s+(?P<body>.+)$")
_STOP_LINE_RE = re.compile(
    r"(?i)^\s*(Fig(?:ure)?\.?\s+\d+[A-Za-z]?\.|References|Acknowledg|Supplementary|Table\s+\d+\.|Funding:)"
)


def build_figure_caption_sidecar(*, paper_id: str, run_id: str, document_artifact: Any) -> FigureCaptionSidecar:
    figures: list[FigureCaptionEntry] = []
    seen: set[tuple[str, int | None]] = set()
    for section in iter_text_sections(document_artifact):
        figures.extend(_extract_section_captions(section.name, section.text, section.page_hint, seen))

    return FigureCaptionSidecar(
        paper_id=paper_id,
        run_id=run_id,
        generated_at=datetime.now(timezone.utc),
        metrics=FigureCaptionMetrics(
            figure_count=len(figures),
            page_count=len({figure.page for figure in figures if figure.page is not None}),
        ),
        figures=figures,
    )


def write_figure_caption_sidecar(sidecar: FigureCaptionSidecar, artifact_dir: Path) -> Path:
    path = artifact_dir / "figure_captions.json"
    atomic_write_text(path, sidecar.model_dump_json(indent=2))
    return path


def _extract_section_captions(
    section_name: str,
    text: str,
    page_hint: int | None,
    seen: set[tuple[str, int | None]] | None = None,
) -> list[FigureCaptionEntry]:
    lines = [line.strip() for line in str(text or "").splitlines()]
    captions: list[FigureCaptionEntry] = []
    seen = seen if seen is not None else set()
    for idx, line in enumerate(lines):
        match = _FIGURE_START_RE.match(line)
        if not match:
            continue
        label = " ".join(match.group(1).split())
        key = (label.lower(), page_hint)
        if key in seen:
            continue
        seen.add(key)
        body = match.group("body").strip()
        if page_hint is not None:
            body = re.sub(rf"^{re.escape(str(page_hint))}\s+", "", body).strip()
            if body == str(page_hint):
                body = ""
        parts = [body]
        for follow in lines[idx + 1 : idx + 12]:
            if not follow:
                break
            if page_hint is not None and not parts[-1] and follow == str(page_hint):
                continue
            if _STOP_LINE_RE.match(follow):
                break
            parts.append(follow)
            if follow.endswith(".") and len(" ".join(parts)) >= 180:
                break
        caption = " ".join(" ".join(parts).split()).strip()
        captions.append(
            FigureCaptionEntry(
                figure_id=label.lower().replace(" ", "_").replace(".", ""),
                label=label,
                page=page_hint,
                section=section_name,
                caption=caption[:2000],
            )
        )
    return captions
