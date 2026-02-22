from __future__ import annotations

import logging
from typing import Dict, List, Optional

import ollama

from src.llm_provider_base import LLMProvider
from src.llm_transport import ollama_chat_request

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama API를 사용하는 LLM 공급자"""

    def _initialize(self):
        self.host = self.config.local.base_url if self.config.local else "http://localhost:11434"
        self.models = self.config.local.models if self.config.local else {}

        try:
            self.ollama_client = ollama.Client(host=self.host)
            self.ollama_client.list()
            self.client = True
            logger.info(f"Ollama connected successfully at {self.host}")
        except Exception as exc:
            logger.warning(f"Ollama connection failed at {self.host}: {exc}. Ollama features will be disabled.")
            self.client = None
            self.ollama_client = None

    def _get_model(self, task: str) -> str:
        if self.models:
            if task == "trial_extraction":
                return self.models.get("extractor", "llama3:8b")
            if task == "slot_classification":
                return self.models.get("classifier", "llama3:8b")
            if task == "tagging":
                return self.models.get("tagger", "biomistral:7b")
            if task == "escalation":
                return self.models.get("judge", "openhermes-2.5-mistral")
            if task == "one_liner":
                return self.models.get("one_liner", "phi3")
            if task == "deep_read":
                return self.models.get("deep_read", "llama3:8b")
            if task == "relevance_analysis":
                return self.models.get("relevance_analyzer", "llama3:8b")

        return self.models.get("chat", "phi3")

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        if not self.is_available():
            return None

        model = self._get_model(task)
        logger.info(f"Making LLM request to Ollama model '{model}' for task '{task}'.")
        return ollama_chat_request(
            ollama_client=self.ollama_client,
            model=model,
            prompt=prompt,
            is_json=is_json,
            schema=schema,
            system_prompt=system_prompt,
            logger=logger,
        )

    def get_embedding(self, text: str) -> Optional[List[float]]:
        if not self.is_available():
            return None
        try:
            embedding_model = self.models.get("embedder", "nomic-embed-text")
            response = self.ollama_client.embeddings(model=embedding_model, prompt=text)
            return response["embedding"]
        except Exception as exc:
            logger.error(f"Ollama embedding failed for model '{embedding_model}': {exc}")
            return None
