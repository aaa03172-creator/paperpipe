import pytest
from pydantic import ValidationError

from src.config import AppConfig


def _config_payload() -> dict:
    return {
        "system": {"backfill_limit_days": 3, "log_level": "INFO"},
        "paths": {
            "zotero_base_dir": "./zotero",
            "obsidian_vault": "./vault",
        },
        "search": {
            "constraints": {"min_pubmed": 1, "max_preprint": 1},
            "slots": {"mechanism": {"query": "test", "source": "pubmed"}},
        },
        "llm": {
            "mode": "local",
            "local": {
                "provider": "ollama",
                "base_url": "http://127.0.0.1:11434",
                "models": {
                    "classifier": "llama3:8b",
                    "tagger": "biomistral:7b",
                    "embedder": "nomic-embed-text",
                    "judge": "llama3:latest",
                    "chat": "phi3",
                },
            },
            "cloud": {"provider": "openai", "api_key": "", "model": "gpt-4o-mini"},
            "features": {
                "slot_classification": {"enabled": False, "model": "gpt-4o-mini"},
                "one_liner": {"enabled": False, "model": "gpt-4o-mini"},
            },
            "timeout_seconds": 15,
            "max_retries": 1,
        },
    }


def test_performance_config_defaults_are_safe():
    config = AppConfig(**_config_payload())

    assert config.performance.embedding_batch_size == 16
    assert config.performance.reader_max_context_chars == 16000
    assert config.performance.max_concurrent_jobs == 1
    assert config.performance.local_gpu_backend == "ollama_metal"


def test_performance_config_validates_bounds():
    payload = _config_payload()
    payload["performance"] = {
        "embedding_batch_size": 0,
        "reader_max_context_chars": 16000,
        "max_concurrent_jobs": 1,
        "local_gpu_backend": "ollama_metal",
    }

    with pytest.raises(ValidationError):
        AppConfig(**payload)
