from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.config import LLMConfig
from src.llm_provider_tasks import (
    analyze_relevance_with_provider,
    classify_slot_with_provider,
    evaluate_escalation_with_provider,
    extract_trial_data_with_provider,
    find_related_papers_with_provider,
    generate_deep_read_with_provider,
    generate_one_liner_with_provider,
    tag_paper_with_provider,
)
from src.llm_response_utils import extract_llm_json
from src.schemas import TrialExtraction

logger = logging.getLogger(__name__)


class LLMProvider:
    """LLM 공급자 인터페이스"""

    def __init__(self, config: LLMConfig, entity_aliases: Dict[str, str] = None):
        self.config = config
        self.entity_aliases = entity_aliases or {}
        self.client = None

        self._initialize()

    def _initialize(self):
        """Provider specific initialization"""
        pass

    def is_available(self) -> bool:
        """API 키가 설정되어 있고 클라이언트가 준비되었는지 확인"""
        return self.client is not None

    def _get_model(self, task: str) -> str:
        """작업에 적합한 모델을 반환 (override 우선)"""
        if self.config.features:
            if task == "trial_extraction" and self.config.features.trial_extraction:
                return self.config.features.trial_extraction.model
            if task == "one_liner" and self.config.features.one_liner:
                return self.config.features.one_liner.model
            if task == "slot_classification" and self.config.features.slot_classification:
                return self.config.features.slot_classification.model

        if self.config.default_model:
            return self.config.default_model

        return "gpt-4o-mini"

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        raise NotImplementedError

    def get_embedding(self, text: str) -> Optional[List[float]]:
        raise NotImplementedError

    def _extract_json(self, response_content: str) -> Optional[Dict[str, Any]]:
        if not response_content:
            return None

        try:
            return extract_llm_json(response_content)
        except json.JSONDecodeError as exc:
            logger.warning(f"Failed to extract JSON from content: {response_content[:100]}... ({exc})")
        return None

    def extract_trial_data(self, paper: Dict[str, Any], methods_snippet: str = "") -> Optional[TrialExtraction]:
        return extract_trial_data_with_provider(
            provider=self,
            paper=paper,
            methods_snippet=methods_snippet,
            logger=logger,
        )

    def generate_deep_read(self, paper: Dict[str, Any]) -> Optional[str]:
        return generate_deep_read_with_provider(self, paper)

    def generate_one_liner(self, paper: Dict[str, Any]) -> Optional[str]:
        return generate_one_liner_with_provider(self, paper)

    def classify_slot(self, paper: Dict[str, Any], current_slot: str) -> str:
        return classify_slot_with_provider(self, paper, current_slot, logger)

    def tag_paper(self, paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return tag_paper_with_provider(self, paper, logger)

    def evaluate_escalation(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        return evaluate_escalation_with_provider(self, paper, logger)

    def analyze_relevance(self, paper: Dict[str, Any], rq: str) -> Optional[Dict[str, str]]:
        return analyze_relevance_with_provider(self, paper, rq, logger)

    def find_related_papers(
        self,
        target_paper_id: str,
        all_papers_vectors: Dict[str, List[float]],
        top_k: int = 3,
    ) -> List[Any]:
        """
        Smart Linking: Finds related papers based on embedding similarity.
        Requires pre-computed embeddings for all papers.
        """
        return find_related_papers_with_provider(
            target_paper_id=target_paper_id,
            all_papers_vectors=all_papers_vectors,
            top_k=top_k,
            logger=logger,
        )
