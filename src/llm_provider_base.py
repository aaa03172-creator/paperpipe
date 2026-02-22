from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.config import LLMConfig
from src.llm_prompts import (
    build_deep_read_prompt,
    build_escalation_prompt,
    build_one_liner_prompt,
    build_relevance_analysis_prompt,
    build_slot_classification_prompt,
    build_tagging_prompts,
    build_trial_extraction_prompt,
)
from src.llm_response_utils import (
    escalation_result_from_payload,
    extract_llm_json,
    relevance_result_from_payload,
    slot_prediction_from_payload,
)
from src.llm_similarity import find_related_papers_by_cosine
from src.schemas import PaperTagging, TrialExtraction

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
        """임상시험 논문에서 Pydantic 모델을 사용하여 구조화된 데이터를 추출하고 검증합니다."""
        try:
            schema_json = json.dumps(TrialExtraction.model_json_schema(), indent=2)
        except Exception:
            schema_json = "Schema definition unavailable."

        prompt = build_trial_extraction_prompt(paper, methods_snippet, schema_json)

        for i in range(2):
            response_content = self._make_request(
                "trial_extraction",
                prompt,
                is_json=True,
                schema=TrialExtraction.model_json_schema(),
            )

            if not response_content or "AI Error" in response_content:
                logger.error(f"Failed to get valid content from LLM: {response_content}")
                return None

            try:
                data = self._extract_json(response_content)
                if not data:
                    logger.warning(f"Attempt {i + 1}: Failed to extract JSON from response.")
                    continue

                if not data.get("paper_id"):
                    data["paper_id"] = paper.get("doi") or paper.get("link") or paper.get("title") or "unknown_id"

                if not data.get("citation"):
                    data["citation"] = {
                        "title": paper.get("title", ""),
                        "authors_first": str(paper.get("authors", "")).split(",")[0]
                        if paper.get("authors")
                        else "Unknown",
                        "year": int(paper.get("published", "0")[:4])
                        if paper.get("published") and paper.get("published")[:4].isdigit()
                        else 0,
                        "journal_or_server": paper.get("source", "Unknown"),
                        "doi": paper.get("doi"),
                        "url": paper.get("link"),
                    }

                validated_data = TrialExtraction(**data)
                logger.info("Successfully parsed and validated trial extraction data.")
                return validated_data
            except Exception as exc:
                logger.error(f"Schema validation failed for LLM response: {exc}")
                return None

        logger.error("Failed to get a valid and parseable JSON response after retries.")
        return None

    def generate_deep_read(self, paper: Dict[str, Any]) -> Optional[str]:
        prompt = build_deep_read_prompt(paper)
        return self._make_request("deep_read", prompt)

    def generate_one_liner(self, paper: Dict[str, Any]) -> Optional[str]:
        prompt = build_one_liner_prompt(paper)
        return self._make_request("one_liner", prompt)

    def classify_slot(self, paper: Dict[str, Any], current_slot: str) -> str:
        prompt = build_slot_classification_prompt(paper, current_slot)
        response_content = self._make_request("slot_classification", prompt, is_json=True)

        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                    predicted = slot_prediction_from_payload(data)
                    if predicted:
                        logger.info(f"   🤖 Slot Verified: {current_slot} -> {predicted}")
                        return predicted
            except Exception:
                pass

        logger.warning("   ⚠️ Classification verification failed. Keeping original slot.")
        return current_slot

    def tag_paper(self, paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        system_prompt, user_prompt = build_tagging_prompts(paper, self.entity_aliases)
        response_content = self._make_request(
            "tagging",
            user_prompt,
            is_json=True,
            schema=None,
            system_prompt=system_prompt,
        )

        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                    tagging_result = PaperTagging(**data)
                    return tagging_result.model_dump()
                logger.warning("Extracted JSON was None/Empty")
            except Exception as exc:
                logger.error(f"Error parsing tagging result: {exc}. Content: {response_content[:100]}...")
                return None

        return None

    def evaluate_escalation(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        prompt = build_escalation_prompt(paper)
        response_content = self._make_request("escalation", prompt, is_json=True)

        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                    return escalation_result_from_payload(data)
            except Exception:
                logger.warning("Failed to parse Escalation Judge response.")

        return {"approved": False, "reason": "Judge Error"}

    def analyze_relevance(self, paper: Dict[str, Any], rq: str) -> Optional[Dict[str, str]]:
        prompt = build_relevance_analysis_prompt(paper, rq)
        response_content = self._make_request("relevance_analysis", prompt, is_json=True)

        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                    return relevance_result_from_payload(data)
            except Exception:
                logger.warning("Failed to parse Relevance Analysis response.")

        return None

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
        if target_paper_id not in all_papers_vectors:
            logger.warning(f"Target paper ID '{target_paper_id}' not found in provided vectors.")
            return []

        related = find_related_papers_by_cosine(
            target_paper_id=target_paper_id,
            all_papers_vectors=all_papers_vectors,
            top_k=top_k,
        )
        if not related:
            logger.warning(
                f"Target paper '{target_paper_id}' has missing/zero vectors. Cannot compute similarity."
            )
        return related
