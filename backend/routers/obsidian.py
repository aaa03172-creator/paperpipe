from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import logging
from pathlib import Path
import json
import os
import re
import tempfile
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import quote, urlparse

from src.config import load_config
from src.schemas.agent_artifacts import ClaimSet, StatsReport
from src.schemas.ops import (
    ArtifactFileEntry,
    ObsidianArtifactsResponse,
    ObsidianMirrorClaim,
    ObsidianMirrorResponse,
    ObsidianMirrorStatCheck,
)
from src.services.event_log import log_user_action
from src.services.identity import paper_id_candidate_ids
from src.services.path_masking import is_path_masking_enabled, mask_local_path
from src.services.runtime_paths import artifact_run_dir
import yaml

logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/obsidian", tags=["obsidian"])


def _best_effort_log_user_action(*, paper_id: str | None, action_type: str, source: str, payload: dict | None = None) -> None:
    try:
        log_user_action(paper_id=paper_id, action_type=action_type, source=source, payload=payload)
    except Exception:
        pass


def _paper_route_candidate_ids(paper_id: str) -> list[str]:
    return paper_id_candidate_ids(paper_id)

class SyncRequest(BaseModel):
    paper_id: str
    run_id: str

MARKER_START = "<!-- AI_AGENT_START -->"
MARKER_END = "<!-- AI_AGENT_END -->"
MARKER_BLOCK_PATTERN = re.compile(
    rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}",
    flags=re.DOTALL,
)
DEFAULT_LATTICE_PUBLIC_BASE_URL = "http://127.0.0.1:8000"

try:
    import fcntl
except Exception:  # pragma: no cover - non-POSIX fallback
    fcntl = None

def _load_artifact(paper_id: str, run_id: str, filename: str):
    for candidate_id in _paper_route_candidate_ids(paper_id):
        path = artifact_run_dir(candidate_id, run_id) / filename
        if not path.exists():
            continue
        with open(path, "r") as f:
            return json.load(f)
    return None


def _public_path(path_value: str | None) -> str | None:
    if path_value is None:
        return None
    if not is_path_masking_enabled():
        return path_value
    return mask_local_path(path_value)


def _load_claimset_for_obsidian(paper_id: str, run_id: str) -> dict | None:
    for filename in ("claimset.resolved.json", "claimset.json"):
        data = _load_artifact(paper_id, run_id, filename)
        if data:
            return data
    return None


def _display_page(page: int | None) -> int | None:
    if not isinstance(page, int) or page < 0:
        return None
    return page + 1


def _find_note_candidates(vault_path: Path, paper_id: str) -> list[Path]:
    candidate_paths: list[Path] = []
    seen: set[Path] = set()
    for candidate_id in _paper_route_candidate_ids(paper_id):
        matches = list(vault_path.rglob(f"*{candidate_id}*.md"))
        if not matches and "/" in candidate_id:
            clean_id = candidate_id.replace("/", "_")
            matches = list(vault_path.rglob(f"*{clean_id}*.md"))
        for match in sorted(matches):
            if match not in seen:
                seen.add(match)
                candidate_paths.append(match)
    return candidate_paths


def _find_existing_note_path(vault_path: Path, paper_id: str) -> Path | None:
    candidates = _find_note_candidates(vault_path, paper_id)
    if not candidates:
        candidate_ids = set(_paper_route_candidate_ids(paper_id))
        for note_path in sorted(vault_path.rglob("*.md")):
            if not note_path.is_file():
                continue
            try:
                content = note_path.read_text(encoding="utf-8")
            except Exception:
                continue
            if not content.startswith("---"):
                continue
            lines = content.splitlines()
            end_index = None
            for idx in range(1, len(lines)):
                if lines[idx].strip() == "---":
                    end_index = idx
                    break
            if end_index is None:
                continue
            try:
                frontmatter = yaml.safe_load("\n".join(lines[1:end_index])) or {}
            except Exception:
                continue
            if not isinstance(frontmatter, dict):
                continue
            if str(frontmatter.get("id") or "").strip() in candidate_ids:
                return note_path
        return None
    return candidates[0]


def _merge_agent_block(original_content: str, new_content: str) -> str:
    if MARKER_BLOCK_PATTERN.search(original_content):
        return MARKER_BLOCK_PATTERN.sub(new_content, original_content, count=1)
    stripped = original_content.rstrip()
    if not stripped:
        return f"{new_content}\n"
    return f"{stripped}\n\n{new_content}\n"


def _lattice_public_base_url() -> str:
    raw = (
        os.getenv("LATTICE_PUBLIC_BASE_URL")
        or os.getenv("PAPERPIPE_PUBLIC_BASE_URL")
        or DEFAULT_LATTICE_PUBLIC_BASE_URL
    )
    base_url = raw.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return DEFAULT_LATTICE_PUBLIC_BASE_URL
    return base_url


def _lattice_review_url(paper_id: str) -> str:
    encoded_paper_id = quote(paper_id, safe="")
    return f"{_lattice_public_base_url()}/ui/workbench/{encoded_paper_id}"


def _lattice_return_links_markdown(paper_id: str | None) -> str:
    if not paper_id:
        return ""
    return (
        "### Lattice Return Path\n"
        f"- [Review in Lattice]({_lattice_review_url(paper_id)})\n"
        "- Boundary: this Obsidian note is a mirror; Lattice owns the canonical paper state.\n\n"
    )


def _atomic_write_text(target_file: Path, content: str) -> None:
    target_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{target_file.name}.",
        suffix=".tmp",
        dir=str(target_file.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target_file)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@contextmanager
def _note_file_lock(target_file: Path) -> Iterator[None]:
    lock_path = target_file.with_name(f".{target_file.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as lock_handle:
        if fcntl is not None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _artifact_entry(path: Path) -> ArtifactFileEntry:
    if not path.exists():
        return ArtifactFileEntry(exists=False, path=None, data=None)
    data = None
    if path.suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            data = {"_parse_error": str(exc)}
    return ArtifactFileEntry(exists=True, path=_public_path(str(path)), data=data)


def _chunks_entry(path: Path) -> ArtifactFileEntry:
    if not path.exists():
        return ArtifactFileEntry(exists=False, path=None, data=None)
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    preview: list[dict | str] = []
    for raw in lines[:5]:
        try:
            preview.append(json.loads(raw))
        except Exception:
            preview.append(raw)
    return ArtifactFileEntry(
        exists=True,
        path=_public_path(str(path)),
        data={"line_count": len(lines), "preview": preview},
    )


@router.get("/artifacts", response_model=ObsidianArtifactsResponse)
async def get_obsidian_artifacts(
    paper_id: str = Query(..., min_length=1),
    run_id: str = Query(..., min_length=1),
):
    run_dir: Path | None = None
    for candidate_id in _paper_route_candidate_ids(paper_id):
        candidate_run_dir = artifact_run_dir(candidate_id, run_id)
        if candidate_run_dir.exists():
            run_dir = candidate_run_dir
            break
    if run_dir is None:
        raise HTTPException(status_code=404, detail=f"Artifacts not found for paper_id={paper_id}, run_id={run_id}")

    resolved_path = run_dir / "claimset.resolved.json"
    legacy_path = run_dir / "claimset.json"
    claimset_path = resolved_path if resolved_path.exists() else legacy_path
    claimset_source = claimset_path.name if claimset_path.exists() else None

    return ObsidianArtifactsResponse(
        paper_id=paper_id,
        run_id=run_id,
        claimset_source=claimset_source,
        claimset=_artifact_entry(claimset_path),
        chunks=_chunks_entry(run_dir / "chunks.jsonl"),
        stats_report=_artifact_entry(run_dir / "stats_report.json"),
    )

def _format_markdown(
    claim_set_data: dict | None,
    stats_report_data: dict | None,
    *,
    paper_id: str | None = None,
) -> str:
    """Format Agent Output into verified Markdown."""
    md = []
    md.append(f"{MARKER_START}\n")
    md.append("## 🤖 PaperPipe AI Analysis\n")
    md.append(_lattice_return_links_markdown(paper_id))
    
    # 1. Claims
    if claim_set_data:
        try:
            claims = ClaimSet(**claim_set_data)
            md.append(f"### 🧪 Scientific Claims ({len(claims.claims)})\n")
            for c in claims.claims:
                icon = "🟢" if c.confidence > 0.8 else "🟡" if c.confidence > 0.5 else "🔴"
                md.append(f"#### {icon} {c.type.title()}: {c.statement}\n")
                if c.evidence_spans:
                    primary = c.evidence_spans[0]
                    quote = primary.quote or primary.raw_text
                    page = _display_page(primary.page)
                    if page is not None:
                        md.append(f"> \"*{quote}*\" (Page {page})\n")
                    else:
                        md.append(f"> \"*{quote}*\"\n")
                if c.limitations:
                    md.append(f"**Limitations**: {', '.join(c.limitations)}\n")
                md.append("\n")
        except Exception as e:
            md.append(f"⚠️ Error formatting claims: {e}\n")

    # 2. Stats
    if stats_report_data:
        try:
            stats = StatsReport(**stats_report_data)
            if stats.checks:
                md.append(f"### 📊 Statistical Verification ({len(stats.checks)})\n")
                for check in stats.checks:
                    icon = "✅" if check.verdict == "verified" else "❌" if check.verdict == "inconsistent" else "⚠️"
                    md.append(f"- {icon} **{check.test_type}**: {check.verdict.upper()}\n")
                    if check.notes:
                        md.append(f"  - Note: {check.notes}\n")
        except Exception as e:
            md.append(f"⚠️ Error formatting stats: {e}\n")
            
    md.append(f"\n{MARKER_END}")
    return "".join(md)


def _build_mirror_claims(claim_set_data: dict | None) -> list[ObsidianMirrorClaim]:
    if not claim_set_data:
        return []
    try:
        parsed = ClaimSet(**claim_set_data)
    except Exception:
        return []

    items: list[ObsidianMirrorClaim] = []
    for claim in parsed.claims:
        primary = claim.evidence_spans[0] if claim.evidence_spans else None
        items.append(
            ObsidianMirrorClaim(
                claim_id=claim.claim_id,
                claim_type=claim.type,
                statement=claim.statement,
                confidence=claim.confidence,
                evidence_quote=(
                    primary.quote if primary and primary.quote else (primary.raw_text if primary else None)
                ),
                evidence_page=(_display_page(primary.page) if primary else None),
                evidence_chunk_id=(primary.chunk_id if primary else None),
                evidence_grounded=(getattr(primary, "grounded", None) if primary else None),
                evidence_resolution=(getattr(primary, "resolution", None) if primary else None),
                limitations=list(claim.limitations or []),
            )
        )
    return items


def _build_mirror_stats(stats_report_data: dict | None) -> list[ObsidianMirrorStatCheck]:
    if not stats_report_data:
        return []
    try:
        parsed = StatsReport(**stats_report_data)
    except Exception:
        return []

    items: list[ObsidianMirrorStatCheck] = []
    for check in parsed.checks:
        primary_evidence = check.evidence[0] if check.evidence else None
        items.append(
            ObsidianMirrorStatCheck(
                check_id=check.check_id,
                test_type=check.test_type,
                verdict=(check.verdict.value if hasattr(check.verdict, "value") else str(check.verdict)),
                claim_id=check.check_id,
                evidence_page=(_display_page(primary_evidence.page) if primary_evidence else None),
                evidence_chunk_id=(primary_evidence.chunk_id if primary_evidence else None),
                evidence_grounded=(getattr(primary_evidence, "grounded", None) if primary_evidence else None),
                evidence_resolution=(getattr(primary_evidence, "resolution", None) if primary_evidence else None),
                hypothesis=check.hypothesis,
                notes=check.notes,
                decision_error=bool(check.decision_error),
            )
        )
    return items


@router.get("/mirror", response_model=ObsidianMirrorResponse)
async def get_obsidian_mirror(
    paper_id: str = Query(..., min_length=1),
    run_id: str = Query(..., min_length=1),
):
    claim_set = _load_claimset_for_obsidian(paper_id, run_id)
    stats_report = _load_artifact(paper_id, run_id, "stats_report.json")
    if not claim_set and not stats_report:
        raise HTTPException(status_code=404, detail="No artifacts found for this run.")
    claims = _build_mirror_claims(claim_set)
    stats_checks = _build_mirror_stats(stats_report)

    return ObsidianMirrorResponse(
        paper_id=paper_id,
        run_id=run_id,
        generated_markdown=_format_markdown(claim_set, stats_report, paper_id=paper_id),
        has_claimset=bool(claim_set),
        has_stats_report=bool(stats_report),
        claims=claims,
        stats_checks=stats_checks,
    )

@router.post("/sync")
async def sync_to_obsidian(req: SyncRequest):
    config = load_config()
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    vault_path.mkdir(parents=True, exist_ok=True)
    
    # 1. Load Artifacts
    claim_set = _load_claimset_for_obsidian(req.paper_id, req.run_id)
    stats_report = _load_artifact(req.paper_id, req.run_id, "stats_report.json")
    
    if not claim_set and not stats_report:
        raise HTTPException(status_code=404, detail="No artifacts found for this run.")
        
    # 2. Generate Content
    new_content = _format_markdown(claim_set, stats_report, paper_id=req.paper_id)
    
    # 3. Find Note
    target_file = _find_existing_note_path(vault_path, req.paper_id)
    if not target_file:
        # Create a new note in Inbox if no matching note is found.
        inbox_dir = vault_path / "Inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        target_file = inbox_dir / f"{req.paper_id}.md"
        with _note_file_lock(target_file):
            if not target_file.exists():
                _atomic_write_text(target_file, f"# {req.paper_id}\n\nCreated by Lattice.\n\n")
        
    # 4. Inject Content
    try:
        with _note_file_lock(target_file):
            original_content = ""
            if target_file.exists():
                original_content = target_file.read_text(encoding="utf-8")
            final_content = _merge_agent_block(original_content, new_content)
            _atomic_write_text(target_file, final_content)

        _best_effort_log_user_action(
            paper_id=req.paper_id,
            action_type="obsidian_sync",
            source="obsidian",
            payload={
                "run_id": req.run_id,
                "note_path": _public_path(str(target_file)),
                "has_claimset": bool(claim_set),
                "has_stats_report": bool(stats_report),
            },
        )
        return {"status": "synced", "file": _public_path(str(target_file)), "message": "Obsidian note updated."}
        
    except Exception as e:
        logger.error(f"Failed to write markdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))
