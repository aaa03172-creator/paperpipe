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

class PathsConfig(BaseModel):
    zotero_base_dir: Path
    obsidian_vault: Path
    index_all: Path = Path("00_Index/paper_collection.csv")
    index_clinical: Path = Path("00_Index/mct_mci_trials.csv")
    upload_dir: Optional[Path] = None
    export_dir: Path = Path("export")

    @field_validator("zotero_base_dir", "obsidian_vault", "upload_dir", "export_dir", mode="before")
    @classmethod
    def expand_paths(cls, v):
        if v:
            return Path(v).expanduser()
        return v

class SlotConfig(BaseModel):
    query: str
    source: Literal["pubmed", "arxiv", "all"] = "pubmed"

class ConstraintsConfig(BaseModel):
    min_pubmed: int = 2
    max_preprint: int = 1

class SearchConfig(BaseModel):
    constraints: ConstraintsConfig = Field(default_factory=ConstraintsConfig)
    slots: Dict[str, SlotConfig]

class FeatureConfig(BaseModel):
    enabled: bool = False
    model: str = "gpt-4o-mini"

class LLMFeatures(BaseModel):
    trial_extraction: FeatureConfig
    slot_classification: FeatureConfig
    one_liner: FeatureConfig

class LLMConfig(BaseModel):
    provider: str = "openai"
    api_key: Optional[str] = None
    default_model: str = "gpt-4o-mini"
    features: LLMFeatures
    timeout_seconds: int = 15
    max_retries: int = 2

    @model_validator(mode='after')
    def resolve_api_key(self):
        # 1. ENV overrides everything
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            self.api_key = env_key
        
        # 2. Clean the key if it exists
        if self.api_key:
             self.api_key = re.sub(r'\s+', '', self.api_key)
             
        return self

class UnpaywallConfig(BaseModel):
    email: Optional[str] = None

class ConfidenceThresholds(BaseModel):
    high: float = 0.85
    low: float = 0.60

class AppConfig(BaseModel):
    system: SystemConfig
    paths: PathsConfig
    search: SearchConfig
    llm: LLMConfig
    unpaywall: UnpaywallConfig = Field(default_factory=UnpaywallConfig)
    confidence_thresholds: ConfidenceThresholds = Field(default_factory=ConfidenceThresholds)

def load_config(config_path: str = "config.yaml") -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path.absolute()}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Note: Pydantic V2 validation happens on instantiation
    config = AppConfig(**data)
    
    return config
