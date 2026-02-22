from __future__ import annotations

import logging
from typing import Dict, Optional

from src.config import LLMConfig
from src.llm_provider_base import LLMProvider
from src.llm_provider_hybrid import HybridProvider
from src.llm_provider_ollama import OllamaProvider
from src.llm_provider_openai import OpenAIProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_llm_provider(config: LLMConfig, entity_aliases: Dict[str, str] = None) -> Optional[LLMProvider]:
    """설정에 맞는 LLM 공급자 인스턴스를 반환"""
    if config.mode == "hybrid":
        logger.info("Initializing Hybrid LLM Provider.")
        return HybridProvider(config, entity_aliases)
    if config.mode == "local":
        if config.local and config.local.provider == "ollama":
            logger.info("Initializing Local Ollama LLM Provider.")
            return OllamaProvider(config, entity_aliases)
        logger.error(
            "Local mode specified, but no valid local provider configured: %s",
            config.local.provider if config.local else "None",
        )
        return None
    if config.mode == "cloud":
        if config.cloud and config.cloud.provider == "openai":
            logger.info("Initializing Cloud OpenAI LLM Provider.")
            return OpenAIProvider(config, entity_aliases)
        logger.error(
            "Cloud mode specified, but no valid cloud provider configured: %s",
            config.cloud.provider if config.cloud else "None",
        )
        return None

    logger.error(f"Invalid LLM mode specified: {config.mode}. No LLM provider initialized.")
    return None


__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "HybridProvider",
    "get_llm_provider",
]
