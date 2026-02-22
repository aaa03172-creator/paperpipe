from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.llm_provider_base import LLMProvider
from src.llm_provider_ollama import OllamaProvider
from src.llm_provider_openai import OpenAIProvider
from src.schemas import TrialExtraction

logger = logging.getLogger(__name__)


class HybridProvider(LLMProvider):
    """로컬(Ollama)과 클라우드(OpenAI) LLM을 조합하여 사용하는 공급자"""

    def _initialize(self):
        self.local = OllamaProvider(self.config, self.entity_aliases)
        self.cloud = OpenAIProvider(self.config, self.entity_aliases)
        self.client = self.local.is_available() or self.cloud.is_available()
        if not self.client:
            logger.error("Neither local nor cloud LLM providers are available in Hybrid mode.")

    def is_available(self) -> bool:
        return self.local.is_available() or self.cloud.is_available()

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        logger.warning(f"HybridProvider: Unrouted task '{task}'. Falling back to cloud if available, else local.")
        if self.cloud.is_available():
            return self.cloud._make_request(task, prompt, is_json, schema, system_prompt=system_prompt)
        if self.local.is_available():
            return self.local._make_request(task, prompt, is_json, schema, system_prompt=system_prompt)
        logger.error(f"HybridProvider: No LLM available for task '{task}'.")
        return "❌ AI Error: No LLM available."

    def get_embedding(self, text: str) -> Optional[List[float]]:
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for embedding.")
            return self.local.get_embedding(text)
        if self.cloud.is_available():
            logger.debug("HybridProvider: Using cloud for embedding.")
            return self.cloud.get_embedding(text)
        logger.error("HybridProvider: No LLM available for embedding.")
        return None

    def classify_slot(self, paper: Dict[str, Any], current_slot: str) -> str:
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for slot classification.")
            return self.local.classify_slot(paper, current_slot)
        if self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for slot classification, falling back to cloud.")
            return self.cloud.classify_slot(paper, current_slot)
        logger.error("HybridProvider: No LLM available for slot classification.")
        return current_slot

    def tag_paper(self, paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for tagging.")
            return self.local.tag_paper(paper)
        if self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for tagging, falling back to cloud.")
            return self.cloud.tag_paper(paper)
        logger.error("HybridProvider: No LLM available for tagging.")
        return None

    def generate_one_liner(self, paper: Dict[str, Any]) -> Optional[str]:
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for one-liner generation.")
            return self.local.generate_one_liner(paper)
        if self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for one-liner, falling back to cloud.")
            return self.cloud.generate_one_liner(paper)
        logger.error("HybridProvider: No LLM available for one-liner.")
        return None

    def extract_trial_data(self, paper: Dict[str, Any], methods_snippet: str = "") -> Optional[TrialExtraction]:
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for trial data extraction.")
            return self.local.extract_trial_data(paper, methods_snippet)
        if self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for trial extraction, falling back to cloud.")
            return self.cloud.extract_trial_data(paper, methods_snippet)
        logger.error("HybridProvider: No LLM available for trial data extraction.")
        return None

    def evaluate_escalation(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        if self.cloud.is_available():
            logger.info("⚡️ HybridProvider: Using Cloud (OpenAI) for Escalation Evaluation.")
            return self.cloud.evaluate_escalation(paper)

        logger.warning("HybridProvider: Cloud unavailable for escalation, falling back to local.")
        if self.local.is_available():
            return self.local.evaluate_escalation(paper)

        logger.error("HybridProvider: No LLM available for escalation evaluation.")
        return {"approved": False, "reason": "No LLM available for escalation."}

    def generate_deep_read(self, paper: Dict[str, Any]) -> Optional[str]:
        if self.cloud.is_available():
            logger.debug("HybridProvider: Using cloud for deep read generation.")
            return self.cloud.generate_deep_read(paper)
        if self.local.is_available():
            logger.warning("HybridProvider: Cloud unavailable for deep read, falling back to local.")
            return self.local.generate_deep_read(paper)
        logger.error("HybridProvider: No LLM available for deep read generation.")
        return None

    def analyze_relevance(self, paper: Dict[str, Any], rq: str) -> Optional[Dict[str, str]]:
        if self.cloud.is_available():
            logger.debug("HybridProvider: Using cloud for relevance analysis.")
            return self.cloud.analyze_relevance(paper, rq)
        if self.local.is_available():
            logger.warning("HybridProvider: Cloud unavailable for relevance analysis, falling back to local.")
            return self.local.analyze_relevance(paper, rq)
        logger.error("HybridProvider: No LLM available for relevance analysis.")
        return None
