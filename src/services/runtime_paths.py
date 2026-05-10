from __future__ import annotations

import os
from pathlib import Path
import sys

from src.services.identity import artifact_paper_segment, legacy_artifact_paper_segment


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundle_root() -> Path | None:
    override = os.getenv("PAPERPIPE_APP_BUNDLE_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root).expanduser().resolve()

    return None


def app_source_root() -> Path:
    return bundle_root() or repo_root()


def _truthy_env(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _app_name() -> str:
    value = os.getenv("PAPERPIPE_APP_NAME")
    if value and value.strip():
        return value.strip()
    return "Lattice"


def install_layout_enabled() -> bool:
    return _truthy_env("PAPERPIPE_INSTALL_LAYOUT") or bundle_root() is not None


def frontend_runtime_dir() -> Path:
    return (app_source_root() / "frontend").resolve()


def user_config_base_dir() -> Path:
    app_name = _app_name()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / app_name).resolve()
    if os.name == "nt":
        base = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
        if base:
            return (Path(base).expanduser() / app_name).resolve()
        return (Path.home() / "AppData" / "Roaming" / app_name).resolve()
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return (Path(xdg).expanduser() / app_name).resolve()
    return (Path.home() / ".config" / app_name).resolve()


def paperpipe_home() -> Path:
    value = os.getenv("PAPERPIPE_HOME")
    if value:
        return Path(value).expanduser().resolve()
    return repo_root()


def storage_root() -> Path:
    value = os.getenv("PAPERPIPE_STORAGE_DIR")
    if value:
        return Path(value).expanduser().resolve()
    if os.getenv("PAPERPIPE_HOME"):
        return (paperpipe_home() / "storage").resolve()
    if install_layout_enabled():
        return (user_config_base_dir() / "storage").resolve()
    return Path("storage").resolve()


def state_db_path() -> Path:
    value = os.getenv("PAPERPIPE_DB_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "state.db").resolve()


def config_root(config_path: str | Path = "config.yaml") -> Path:
    value = os.getenv("PAPERPIPE_CONFIG_DIR")
    if value:
        return Path(value).expanduser().resolve()
    explicit_config = os.getenv("PAPERPIPE_CONFIG_PATH")
    if explicit_config:
        explicit_path = Path(explicit_config).expanduser().resolve()
        workspace_candidate = (explicit_path.parent / "config").resolve()
        if workspace_candidate.exists():
            return workspace_candidate
        return explicit_path.parent.resolve()
    if os.getenv("PAPERPIPE_HOME"):
        return (paperpipe_home() / "config").resolve()
    if install_layout_enabled():
        return (user_config_base_dir() / "config").resolve()
    raw = Path(config_path).expanduser()
    if raw.name != "config.yaml" or raw.parent != Path("."):
        return raw.resolve().parent
    cwd_candidate = (Path.cwd() / "config").resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    return (paperpipe_home() / "config").resolve()


def config_file_path(config_path: str | Path = "config.yaml") -> Path:
    value = os.getenv("PAPERPIPE_CONFIG_PATH")
    if value:
        return Path(value).expanduser().resolve()
    config_dir_override = os.getenv("PAPERPIPE_CONFIG_DIR")
    if config_dir_override:
        return (config_root(config_path) / "config.yaml").resolve()
    if os.getenv("PAPERPIPE_HOME"):
        candidates = [
            (config_root(config_path) / "config.yaml").resolve(),
            (paperpipe_home() / "config.yaml").resolve(),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]
    if install_layout_enabled():
        install_candidate = (config_root(config_path) / "config.yaml").resolve()
        if install_candidate.exists():
            return install_candidate
        return install_candidate
    raw = config_path
    return Path(raw).expanduser().resolve()


def logs_root() -> Path:
    value = os.getenv("PAPERPIPE_LOGS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    if os.getenv("PAPERPIPE_HOME"):
        return (paperpipe_home() / "logs").resolve()
    if install_layout_enabled():
        return (user_config_base_dir() / "logs").resolve()
    return Path("logs").resolve()


def cache_root() -> Path:
    value = os.getenv("PAPERPIPE_CACHE_DIR")
    if value:
        return Path(value).expanduser().resolve()
    if os.getenv("PAPERPIPE_HOME"):
        return (paperpipe_home() / "cache").resolve()
    if install_layout_enabled():
        return (user_config_base_dir() / "cache").resolve()
    return (storage_root() / "cache").resolve()


def exports_root() -> Path:
    if os.getenv("PAPERPIPE_HOME"):
        return (paperpipe_home() / "export").resolve()
    if install_layout_enabled():
        return (storage_root() / "exports").resolve()
    return Path("export")


def library_root() -> Path:
    if os.getenv("PAPERPIPE_HOME"):
        return (paperpipe_home() / "Library").resolve()
    if install_layout_enabled():
        return (storage_root() / "library").resolve()
    return Path("Library")


def pdf_storage_root() -> Path:
    if os.getenv("PAPERPIPE_HOME"):
        return (paperpipe_home() / "storage" / "pdfs").resolve()
    if install_layout_enabled():
        return (storage_root() / "pdfs").resolve()
    return Path("storage/pdfs")


def managed_watch_folder_root() -> Path:
    if os.getenv("PAPERPIPE_HOME"):
        return (paperpipe_home() / "watch_folder").resolve()
    if install_layout_enabled():
        return (storage_root() / "watch_folder").resolve()
    return Path("Download/PaperPipe_Watch")


def rag_root() -> Path:
    value = os.getenv("PAPERPIPE_RAG_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "rag").resolve()


def feedback_index_root() -> Path:
    value = os.getenv("PAPERPIPE_FEEDBACK_INDEX_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "feedback_index").resolve()


def feedback_log_path() -> Path:
    value = os.getenv("PAPERPIPE_FEEDBACK_LOG_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "feedback.jsonl").resolve()


def artifact_review_feedback_log_path() -> Path:
    value = os.getenv("PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "artifact_review_feedback.jsonl").resolve()


def artifact_generation_outcome_log_path() -> Path:
    value = os.getenv("PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "artifact_generation_outcomes.jsonl").resolve()


def project_context_link_log_path() -> Path:
    value = os.getenv("PAPERPIPE_PROJECT_CONTEXT_LINK_LOG_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "project_context_links.jsonl").resolve()


def zotero_export_path() -> Path:
    value = os.getenv("PAPERPIPE_ZOTERO_EXPORT_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "zotero_export.json").resolve()


def ocr_cache_root() -> Path:
    value = os.getenv("PAPERPIPE_OCR_CACHE_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (cache_root() / "ocr").resolve()


def artifacts_root() -> Path:
    value = os.getenv("PAPERPIPE_ARTIFACTS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "artifacts").resolve()


def _confined_child(root: Path, *parts: str) -> Path | None:
    root_path = root.expanduser().resolve()
    candidate = root_path.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError:
        return None
    return candidate


def artifact_paper_dir_candidates(paper_id: str, root: Path | None = None) -> list[Path]:
    root_path = root.resolve() if root is not None else artifacts_root()
    candidates: list[Path] = []
    seen: set[Path] = set()
    for segment in (artifact_paper_segment(paper_id), legacy_artifact_paper_segment(paper_id)):
        candidate = _confined_child(root_path, segment)
        if candidate is None:
            continue
        if candidate not in seen:
            candidates.append(candidate)
            seen.add(candidate)
    return candidates


def preferred_artifact_paper_dir(paper_id: str, root: Path | None = None) -> Path:
    candidates = artifact_paper_dir_candidates(paper_id, root=root)
    root_path = root.resolve() if root is not None else artifacts_root()
    legacy_path = _confined_child(root_path, legacy_artifact_paper_segment(paper_id))
    canonical_path = _confined_child(root_path, artifact_paper_segment(paper_id))

    # Preserve existing raw paper_id directories for backward compatibility.
    if legacy_path is not None and canonical_path is not None and legacy_path != canonical_path and legacy_path.exists():
        return legacy_path
    if canonical_path is not None and canonical_path.exists():
        return canonical_path
    return candidates[0]


def artifact_paper_dir(paper_id: str) -> Path:
    return preferred_artifact_paper_dir(paper_id)


def artifact_run_dir_candidates(paper_id: str, run_id: str) -> list[Path]:
    root_path = artifacts_root()
    candidates: list[Path] = []
    for paper_dir in artifact_paper_dir_candidates(paper_id):
        candidate = _confined_child(root_path, str(paper_dir.relative_to(root_path)), str(run_id))
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def artifact_run_dir(paper_id: str, run_id: str) -> Path:
    preferred = preferred_artifact_paper_dir(paper_id)
    root_path = artifacts_root()
    preferred_candidate = _confined_child(root_path, str(preferred.relative_to(root_path)), str(run_id))
    if preferred_candidate is None:
        preferred_candidate = preferred / artifact_paper_segment(run_id)
    candidates = [preferred_candidate]
    for candidate in artifact_run_dir_candidates(paper_id, run_id):
        if candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def goldset_root() -> Path:
    value = os.getenv("PAPERPIPE_GOLDSET_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (paperpipe_home() / "goldset").resolve()


def research_dna_root() -> Path:
    value = os.getenv("PAPERPIPE_RESEARCH_DNA_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (paperpipe_home() / "research_dna").resolve()


def search_eval_root() -> Path:
    value = os.getenv("PAPERPIPE_SEARCH_EVAL_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "search_eval").resolve()


def protocol_cards_root() -> Path:
    value = os.getenv("PAPERPIPE_PROTOCOL_CARDS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "protocol_cards").resolve()


def protocol_attachments_root() -> Path:
    value = os.getenv("PAPERPIPE_PROTOCOL_ATTACHMENTS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "protocol_attachments").resolve()


def chart_packs_root() -> Path:
    value = os.getenv("PAPERPIPE_CHART_PACKS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "chart_packs").resolve()


def image_evidence_root() -> Path:
    value = os.getenv("PAPERPIPE_IMAGE_EVIDENCE_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "image_evidence").resolve()


def meeting_packs_root() -> Path:
    value = os.getenv("PAPERPIPE_MEETING_PACKS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "meeting_packs").resolve()


def talk_packs_root() -> Path:
    value = os.getenv("PAPERPIPE_TALK_PACKS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "talk_packs").resolve()


def method_comparisons_root() -> Path:
    value = os.getenv("PAPERPIPE_METHOD_COMPARISONS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "method_comparisons").resolve()


def paper_syntheses_root() -> Path:
    value = os.getenv("PAPERPIPE_PAPER_SYNTHESES_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "paper_syntheses").resolve()


def project_memory_root() -> Path:
    value = os.getenv("PAPERPIPE_PROJECT_MEMORY_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "project_memory").resolve()


def profiles_config_path() -> Path:
    value = os.getenv("PAPERPIPE_PROFILES_PATH")
    if value:
        return Path(value).expanduser().resolve()
    if os.getenv("PAPERPIPE_CONFIG_PATH"):
        config_path = config_file_path()
        candidates = [
            (config_root() / "profiles.yaml").resolve(),
            config_path.with_name("profiles.yaml").resolve(),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]
    if os.getenv("PAPERPIPE_CONFIG_DIR") or os.getenv("PAPERPIPE_HOME") or install_layout_enabled():
        return (config_root() / "profiles.yaml").resolve()
    cwd_candidate = (Path.cwd() / "config" / "profiles.yaml").resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    return (paperpipe_home() / "config" / "profiles.yaml").resolve()
