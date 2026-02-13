import yaml
import os
import shutil
from pathlib import Path
from typing import List
from src.profiles.profile_schema import ProfileConfig, Profile

DEFAULT_PROFILE_PATH = Path("config/profiles.yaml")

def load_profiles(path: Path = DEFAULT_PROFILE_PATH) -> ProfileConfig:
    """Safely loads profiles from YAML."""
    if not path.exists():
        # Return empty config if file doesn't exist
        return ProfileConfig()
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            
        # Pydantic Validation
        return ProfileConfig(**data)
    except Exception as e:
        # Fallback or re-raise? For strictness, re-raise.
        raise ValueError(f"Failed to load profiles from {path}: {e}")

def save_profiles(config: ProfileConfig, path: Path = DEFAULT_PROFILE_PATH):
    """
    Atomically saves profiles to YAML.
    1. Write to temp file.
    2. Move to target path.
    """
    temp_path = path.with_suffix(".tmp")
    
    try:
        # Dump to dict using Pydantic
        data = config.model_dump(exclude_none=True)
        
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(temp_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False, allow_unicode=True)
            
        # Atomic Move
        shutil.move(temp_path, path)
        
    except Exception as e:
        if temp_path.exists():
            os.remove(temp_path)
        raise IOError(f"Failed to save profiles to {path}: {e}")
