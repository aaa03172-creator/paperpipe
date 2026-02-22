from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

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
    relevance_result_from_payload,
    slot_prediction_from_payload,
)
from src.llm_similarity import find_related_papers_by_cosine
from src.schemas import PaperTagging, TrialExtraction


def extract_trial_data_with_provider(
    provider: Any,
    paper: Dict[str, Any],
    methods_snippet: str,
    logger: logging.Logger,
) -> Optional[TrialExtraction]:
    try:
        schema_json = json.dumps(TrialExtraction.model_json_schema(), indent=2)
    except Exception:
        schema_json = "Schema definition unavailable."

    prompt = build_trial_extraction_prompt(paper, methods_snippet, schema_json)

    for i in range(2):
        response_content = provider._make_request(
            "trial_extraction",
            prompt,
            is_json=True,
            schema=TrialExtraction.model_json_schema(),
        )

        if not response_content or "AI Error" in response_content:
            logger.error(f"Failed to get valid content from LLM: {response_content}")
            return None

        try:
            data = provider._extract_json(response_content)
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


def generate_deep_read_with_provider(provider: Any, paper: Dict[str, Any]) -> Optional[str]:
    prompt = build_deep_read_prompt(paper)
    return provider._make_request("deep_read", prompt)


def generate_one_liner_with_provider(provider: Any, paper: Dict[str, Any]) -> Optional[str]:
    prompt = build_one_liner_prompt(paper)
    return provider._make_request("one_liner", prompt)


def classify_slot_with_provider(
    provider: Any,
    paper: Dict[str, Any],
    current_slot: str,
    logger: logging.Logger,
) -> str:
    prompt = build_slot_classification_prompt(paper, current_slot)
    response_content = provider._make_request("slot_classification", prompt, is_json=True)

    if response_content:
        try:
            data = provider._extract_json(response_content)
            if data:
                predicted = slot_prediction_from_payload(data)
                if predicted:
                    logger.info(f"   🤖 Slot Verified: {current_slot} -> {predicted}")
                    return predicted
        except Exception:
            pass

    logger.warning("   ⚠️ Classification verification failed. Keeping original slot.")
    return current_slot


def tag_paper_with_provider(provider: Any, paper: Dict[str, Any], logger: logging.Logger) -> Optional[Dict[str, Any]]:
    system_prompt, user_prompt = build_tagging_prompts(paper, provider.entity_aliases)
    response_content = provider._make_request(
        "tagging",
        user_prompt,
        is_json=True,
        schema=None,
        system_prompt=system_prompt,
    )

    if response_content:
        try:
            data = provider._extract_json(response_content)
            if data:
                tagging_result = PaperTagging(**data)
                return tagging_result.model_dump()
            logger.warning("Extracted JSON was None/Empty")
        except Exception as exc:
            logger.error(f"Error parsing tagging result: {exc}. Content: {response_content[:100]}...")
            return None

    return None


def evaluate_escalation_with_provider(
    provider: Any,
    paper: Dict[str, Any],
    logger: logging.Logger,
) -> Dict[str, Any]:
    prompt = build_escalation_prompt(paper)
    response_content = provider._make_request("escalation", prompt, is_json=True)

    if response_content:
        try:
            data = provider._extract_json(response_content)
            if data:
                return escalation_result_from_payload(data)
        except Exception:
            logger.warning("Failed to parse Escalation Judge response.")

    return {"approved": False, "reason": "Judge Error"}


def analyze_relevance_with_provider(
    provider: Any,
    paper: Dict[str, Any],
    rq: str,
    logger: logging.Logger,
) -> Optional[Dict[str, str]]:
    prompt = build_relevance_analysis_prompt(paper, rq)
    response_content = provider._make_request("relevance_analysis", prompt, is_json=True)

    if response_content:
        try:
            data = provider._extract_json(response_content)
            if data:
                return relevance_result_from_payload(data)
        except Exception:
            logger.warning("Failed to parse Relevance Analysis response.")

    return None


def find_related_papers_with_provider(
    target_paper_id: str,
    all_papers_vectors: Dict[str, List[float]],
    top_k: int,
    logger: logging.Logger,
) -> List[Any]:
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
