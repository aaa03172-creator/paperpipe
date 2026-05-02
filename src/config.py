import yaml
import os
import re
import warnings
from pydantic import BaseModel, Field, field_validator, model_validator
from pathlib import Path
from typing import List, Optional, Dict, Any, Literal

from src.services.runtime_paths import (
    config_file_path,
    exports_root,
    feedback_index_root,
    install_layout_enabled,
    library_root,
    logs_root,
    managed_watch_folder_root,
    pdf_storage_root,
    rag_root,
)
from src.legacy_trial_extraction_constants import (
    LEGACY_TRIAL_EXTRACTION_ALIAS_REMOVAL_DATE,
    SPECIALTY_TRIAL_EXTRACTION_FEATURE_KEY,
    LEGACY_TRIAL_EXTRACTION_FEATURE_KEY,
)

_LEGACY_TRIAL_EXTRACTION_ALIAS_WARNED = False

class SystemConfig(BaseModel):
    backfill_limit_days: int = 3
    log_level: str = "INFO"
    unpaywall_email: Optional[str] = None
    check_retraction_on_ingest: bool = False # [NEW] Default to False

class PathsConfig(BaseModel):
    zotero_base_dir: Path
    obsidian_vault: Path
    index_all: Path = Path("00_Index/paper_collection.csv")
    index_clinical: Path = Path("00_Index/clinical_trials.csv")
    upload_dir: Optional[Path] = None
    export_dir: Path = Field(default_factory=exports_root)
    watch_folder: Optional[Path] = None # [NEW]
    library_dir: Path = Field(default_factory=library_root) # [NEW]
    downloads_watch_dir: Path = Field(default_factory=lambda: Path("~/Downloads").expanduser())
    pdf_storage_dir: Path = Field(default_factory=pdf_storage_root)

    @field_validator(
        "zotero_base_dir",
        "obsidian_vault",
        "upload_dir",
        "export_dir",
        "watch_folder",
        "library_dir",
        "downloads_watch_dir",
        "pdf_storage_dir",
        mode="before",
    )

    @classmethod
    def expand_paths(cls, v):
        if v:
            return Path(v).expanduser()
        return v

    @model_validator(mode="after")
    def normalize_install_layout_owned_defaults(self):
        if not install_layout_enabled():
            messages = _path_boundary_warnings(self)
            if messages:
                raise ValueError("; ".join(messages))
            return self

        if self.export_dir == Path("export"):
            self.export_dir = exports_root()
        if self.library_dir == Path("Library"):
            self.library_dir = library_root()
        if self.pdf_storage_dir == Path("storage/pdfs"):
            self.pdf_storage_dir = pdf_storage_root()
        if self.watch_folder == Path("Download/PaperPipe_Watch"):
            self.watch_folder = managed_watch_folder_root()

        messages = _path_boundary_warnings(self)
        if messages:
            raise ValueError("; ".join(messages))
        return self


def _resolved_optional_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        return path.expanduser().resolve(strict=False)
    except Exception:
        return None


def _paths_overlap(first: Path, second: Path) -> bool:
    if first == second:
        return True
    try:
        first.relative_to(second)
        return True
    except ValueError:
        pass
    try:
        second.relative_to(first)
        return True
    except ValueError:
        return False


def _path_boundary_warnings(paths: PathsConfig) -> list[str]:
    messages: list[str] = []
    resolved_watch_folder = _resolved_optional_path(paths.watch_folder)
    resolved_upload_dir = _resolved_optional_path(paths.upload_dir)
    resolved_downloads_watch_dir = _resolved_optional_path(paths.downloads_watch_dir)
    resolved_pdf_storage_dir = _resolved_optional_path(paths.pdf_storage_dir)

    if resolved_watch_folder is not None:
        conflicts: list[str] = []
        for label, resolved in (
            ("upload_dir", resolved_upload_dir),
            ("pdf_storage_dir", resolved_pdf_storage_dir),
        ):
            if resolved is not None and _paths_overlap(resolved_watch_folder, resolved):
                conflicts.append(f"{label}={resolved}")
        if conflicts:
            messages.append(
                "paths.watch_folder overlaps managed output paths; "
                "`paperpipe watch` will fail until this is separated: "
                + ", ".join(conflicts)
            )

    if (
        resolved_downloads_watch_dir is not None
        and resolved_pdf_storage_dir is not None
        and _paths_overlap(resolved_downloads_watch_dir, resolved_pdf_storage_dir)
    ):
        messages.append(
            "paths.downloads_watch_dir overlaps paths.pdf_storage_dir; "
            "`paperpipe watch-downloads` will fail until this is separated: "
            f"pdf_storage_dir={resolved_pdf_storage_dir}"
        )

    return messages

class SlotConfig(BaseModel):
    query: str
    source: Literal["pubmed", "arxiv", "all"] = "pubmed"
    research_question: Optional[str] = None # [NEW] Context for analysis

class ConstraintsConfig(BaseModel):
    min_pubmed: int = 2
    max_preprint: int = 1

class SearchConfig(BaseModel):
    constraints: ConstraintsConfig = Field(default_factory=ConstraintsConfig)
    slots: Dict[str, SlotConfig]

class FeatureConfig(BaseModel):
    enabled: bool = False
    model: str = "llama3:8b" # Local-first default, can be overridden by provider config

class LLMFeatures(BaseModel):
    clinical_extraction: Optional[FeatureConfig] = None
    specialty_trial_extraction: Optional[FeatureConfig] = None
    # Backward-compatible alias for older local configs. Prefer specialty_trial_extraction.
    trial_extraction: Optional[FeatureConfig] = None
    slot_classification: FeatureConfig
    one_liner: FeatureConfig


def _coerce_feature_config(feature: Any) -> Any:
    if isinstance(feature, dict):
        return FeatureConfig(**feature)
    return feature


def resolve_clinical_extraction_feature(features: Any) -> Any:
    if features is None:
        return None
    if isinstance(features, dict):
        clinical_feature = _coerce_feature_config(features.get("clinical_extraction"))
        if clinical_feature is not None:
            return clinical_feature
        specialty_feature = _coerce_feature_config(features.get(SPECIALTY_TRIAL_EXTRACTION_FEATURE_KEY))
        if specialty_feature is not None:
            return specialty_feature
        return _coerce_feature_config(features.get(LEGACY_TRIAL_EXTRACTION_FEATURE_KEY))
    clinical_feature = _coerce_feature_config(getattr(features, "clinical_extraction", None))
    if clinical_feature is not None:
        return clinical_feature
    specialty_feature = _coerce_feature_config(getattr(features, SPECIALTY_TRIAL_EXTRACTION_FEATURE_KEY, None))
    if specialty_feature is not None:
        return specialty_feature
    return _coerce_feature_config(getattr(features, LEGACY_TRIAL_EXTRACTION_FEATURE_KEY, None))


def resolve_specialty_trial_extraction_feature(features: Any) -> Any:
    if features is None:
        return None
    if isinstance(features, dict):
        specialty_feature = _coerce_feature_config(features.get(SPECIALTY_TRIAL_EXTRACTION_FEATURE_KEY))
        if specialty_feature is not None:
            return specialty_feature
        return _coerce_feature_config(features.get(LEGACY_TRIAL_EXTRACTION_FEATURE_KEY))
    specialty_feature = _coerce_feature_config(getattr(features, SPECIALTY_TRIAL_EXTRACTION_FEATURE_KEY, None))
    if specialty_feature is not None:
        return specialty_feature
    return _coerce_feature_config(getattr(features, LEGACY_TRIAL_EXTRACTION_FEATURE_KEY, None))


def _warn_legacy_trial_extraction_alias_once() -> None:
    global _LEGACY_TRIAL_EXTRACTION_ALIAS_WARNED
    if _LEGACY_TRIAL_EXTRACTION_ALIAS_WARNED:
        return
    warnings.warn(
        "`llm.features.trial_extraction` is deprecated; use "
        "`llm.features.specialty_trial_extraction` for the specialty clinical extraction lane. "
        f"Scheduled removal date: {LEGACY_TRIAL_EXTRACTION_ALIAS_REMOVAL_DATE}.",
        DeprecationWarning,
        stacklevel=2,
    )
    _LEGACY_TRIAL_EXTRACTION_ALIAS_WARNED = True


def _uses_legacy_trial_extraction_alias(data: Dict[str, Any]) -> bool:
    llm_data = data.get("llm")
    if not isinstance(llm_data, dict):
        return False
    features_data = llm_data.get("features")
    if not isinstance(features_data, dict):
        return False
    return LEGACY_TRIAL_EXTRACTION_FEATURE_KEY in features_data

class LocalLLMConfig(BaseModel):
    provider: Literal["ollama"] = "ollama"
    base_url: str = "http://localhost:11434"
    models: Dict[str, str] = {
        "classifier": "llama3:8b",
        "tagger": "biomistral:7b",
        "embedder": "nomic-embed-text",
        "judge": "llama3:latest",
        "chat": "phi3" # Default chat model
    }
    concurrency: int = 4

class CloudLLMConfig(BaseModel):
    provider: Literal["openai", "anthropic"] = "openai"
    api_key: Optional[str] = None
    model: str = "gpt-4o"
    embedding_model: Optional[str] = None

class LLMConfig(BaseModel):
    mode: Literal["cloud", "local", "hybrid"] = "local" # Default local-first runtime
    
    # Provider Configs
    local: LocalLLMConfig = Field(default_factory=LocalLLMConfig)
    cloud: CloudLLMConfig = Field(default_factory=CloudLLMConfig)
    
    # Common Settings
    features: LLMFeatures
    timeout_seconds: int = 15
    max_retries: int = 2
    reader_attempt_order: Literal["current", "focused_first"] = "current"

    @model_validator(mode='after')
    def resolve_api_key(self):
        # 1. ENV overrides everything for Cloud, keyed by provider
        provider = str(self.cloud.provider or "openai").strip().lower()
        env_var_name = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
        env_key = os.getenv(env_var_name)
        if env_key:
            self.cloud.api_key = env_key
        
        # 2. Clean the key if it exists
        if self.cloud.api_key:
             self.cloud.api_key = re.sub(r'\s+', '', self.cloud.api_key)
             
        return self

class UnpaywallConfig(BaseModel):
    email: Optional[str] = None

class ConfidenceThresholds(BaseModel):
    high: float = 0.90 # [UPDATED]
    low: float = 0.70  # [UPDATED] 

class BibliometricConfig(BaseModel): # [NEW]
    enabled: bool = False
    weights: Dict[str, float] = {"novelty": 0.4, "impact": 0.4, "venue": 0.2}
    thresholds: Dict[str, float] = {"min_citations": 0.0, "min_h_index": 0.0}

class RankingConfig(BaseModel): # [NEW]
    bibliometrics: BibliometricConfig = Field(default_factory=BibliometricConfig)


class IngestConfig(BaseModel):
    parser_backend: Literal["fitz_pdfplumber", "docling"] = "fitz_pdfplumber"
    enable_docling: bool = False
    enable_ocr_fallback: bool = False
    ocr_lang: str = "eng"
    ocr_min_text_chars: int = 200
    enable_table_pass2_ocr: bool = False
    enable_cloud_table_fallback: bool = False
    cloud_table_page_budget: int = 1
    cloud_table_model: str = "gpt-4o-mini"
    cloud_table_base_url: Optional[str] = None
    cloud_table_api_key: Optional[str] = None
    cloud_table_timeout_seconds: int = 30

# [Ticket v3.0] Agent Configuration
class AgentToolsConfig(BaseModel):
    retrieval: bool = True
    python_repl: bool = True
    web_search: bool = False

class AgentLoggingConfig(BaseModel):
    trace_file: str = Field(default_factory=lambda: str(logs_root() / "agent_trace.jsonl"))

class AgentConfig(BaseModel):
    enabled: bool = False
    backend: str = "ollama_adapter"
    main_model: str = "llama3:latest"
    rag_index_path: str = Field(default_factory=lambda: str(rag_root()))
    feedback_index_path: str = Field(default_factory=lambda: str(feedback_index_root()))
    tools: AgentToolsConfig = Field(default_factory=AgentToolsConfig)
    logging: AgentLoggingConfig = Field(default_factory=AgentLoggingConfig)

class AppConfig(BaseModel):
    system: SystemConfig
    paths: PathsConfig
    search: SearchConfig
    llm: LLMConfig
    ingest: IngestConfig = Field(default_factory=IngestConfig)
    unpaywall: UnpaywallConfig = Field(default_factory=UnpaywallConfig)
    confidence_thresholds: ConfidenceThresholds = Field(default_factory=ConfidenceThresholds)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    sources: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    entity_aliases: Dict[str, str] = Field(default_factory=dict)
    agents: Optional[AgentConfig] = None # [Ticket v3.0] 


def load_config(config_path: str = "config.yaml") -> AppConfig:
    path = config_file_path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path.absolute()}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if isinstance(data, dict) and _uses_legacy_trial_extraction_alias(data):
        _warn_legacy_trial_extraction_alias_once()

    # Note: Pydantic V2 validation happens on instantiation
    config = AppConfig(**data)

    return config
