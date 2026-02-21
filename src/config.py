import yaml
import os
import re
from pydantic import BaseModel, Field, field_validator, model_validator
from pathlib import Path
from typing import List, Optional, Dict, Any, Literal

class SystemConfig(BaseModel):
    backfill_limit_days: int = 3
    log_level: str = "INFO"
    unpaywall_email: Optional[str] = None
    check_retraction_on_ingest: bool = False # [NEW] Default to False

class PathsConfig(BaseModel):
    zotero_base_dir: Path
    obsidian_vault: Path
    index_all: Path = Path("00_Index/paper_collection.csv")
    index_clinical: Path = Path("00_Index/mct_mci_trials.csv")
    upload_dir: Optional[Path] = None
    export_dir: Path = Path("export")
    watch_folder: Optional[Path] = None # [NEW]
    library_dir: Path = Path("Library") # [NEW]

    @field_validator("zotero_base_dir", "obsidian_vault", "upload_dir", "export_dir", "watch_folder", "library_dir", mode="before")

    @classmethod
    def expand_paths(cls, v):
        if v:
            return Path(v).expanduser()
        return v

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
    model: str = "gpt-4o-mini" # Default, can be overridden by specific provider config

class LLMFeatures(BaseModel):
    trial_extraction: FeatureConfig
    slot_classification: FeatureConfig
    one_liner: FeatureConfig

class LocalLLMConfig(BaseModel):
    provider: Literal["ollama"] = "ollama"
    base_url: str = "http://localhost:11434"
    models: Dict[str, str] = {
        "classifier": "llama3:8b",
        "tagger": "biomistral:7b",
        "embedder": "nomic-embed-text",
        "judge": "openhermes-2.5-mistral",
        "chat": "phi3" # Default chat model
    }
    concurrency: int = 4

class CloudLLMConfig(BaseModel):
    provider: Literal["openai"] = "openai"
    api_key: Optional[str] = None
    model: str = "gpt-4o"

class LLMConfig(BaseModel):
    mode: Literal["cloud", "local", "hybrid"] = "cloud" # Default to cloud for backward compatibility
    
    # Provider Configs
    local: LocalLLMConfig = Field(default_factory=LocalLLMConfig)
    cloud: CloudLLMConfig = Field(default_factory=CloudLLMConfig)
    
    # Common Settings
    features: LLMFeatures
    timeout_seconds: int = 15
    max_retries: int = 2

    @model_validator(mode='after')
    def resolve_api_key(self):
        # 1. ENV overrides everything for Cloud
        env_key = os.getenv("OPENAI_API_KEY")
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

# [Ticket v3.0] Agent Configuration
class AgentToolsConfig(BaseModel):
    retrieval: bool = True
    python_repl: bool = True
    web_search: bool = False

class AgentLoggingConfig(BaseModel):
    trace_file: str = "logs/agent_trace.jsonl"

class AgentConfig(BaseModel):
    enabled: bool = False
    backend: str = "ollama_adapter"
    main_model: str = "llama3:latest"
    rag_index_path: str = "./storage/rag/"
    feedback_index_path: str = "./storage/feedback_index/"
    tools: AgentToolsConfig = Field(default_factory=AgentToolsConfig)
    logging: AgentLoggingConfig = Field(default_factory=AgentLoggingConfig)

class AppConfig(BaseModel):
    system: SystemConfig
    paths: PathsConfig
    search: SearchConfig
    llm: LLMConfig
    unpaywall: UnpaywallConfig = Field(default_factory=UnpaywallConfig)
    confidence_thresholds: ConfidenceThresholds = Field(default_factory=ConfidenceThresholds)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    sources: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    entity_aliases: Dict[str, str] = Field(default_factory=dict)
    agents: Optional[AgentConfig] = None # [Ticket v3.0] 


def load_config(config_path: str = "config.yaml") -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path.absolute()}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Note: Pydantic V2 validation happens on instantiation
    config = AppConfig(**data)
    
    return config
