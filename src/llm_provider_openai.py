from __future__ import annotations

import logging
from typing import Dict, List, Optional

from openai import OpenAI

from src.llm_provider_base import LLMProvider
from src.llm_transport import openai_chat_request

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API를 사용하는 LLM 공급자"""

    def _initialize(self):
        api_key = None
        if self.config.cloud and self.config.cloud.api_key:
            api_key = self.config.cloud.api_key

        if not api_key:
            logger.warning("OpenAI API key is not configured. OpenAI features will be disabled.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)

    def _get_model(self, task: str) -> str:
        if self.config.cloud and self.config.cloud.model:
            return self.config.cloud.model
        return super()._get_model(task)

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
        logger.info(f"Making LLM request to model '{model}' for task '{task}'.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "timeout": self.config.timeout_seconds,
        }
        if is_json or schema:
            request_params["response_format"] = {"type": "json_object"}

        return openai_chat_request(
            client=self.client,
            request_params=request_params,
            max_retries=self.config.max_retries,
            logger=logger,
        )

    def get_embedding(self, text: str) -> Optional[List[float]]:
        if not self.is_available():
            return None
        try:
            embedding_model = (
                self.config.cloud.embedding_model
                if self.config.cloud and self.config.cloud.embedding_model
                else "text-embedding-3-small"
            )
            resp = self.client.embeddings.create(input=text, model=embedding_model)
            return resp.data[0].embedding
        except Exception as exc:
            logger.error(f"OpenAI embedding failed: {exc}")
            return None
