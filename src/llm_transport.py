from __future__ import annotations

import time
from typing import Any, Dict, Optional

from openai import APITimeoutError, APIStatusError, RateLimitError


def openai_chat_request(
    *,
    client,
    request_params: Dict[str, Any],
    max_retries: int,
    logger,
) -> Optional[str]:
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(**request_params)
            return response.choices[0].message.content
        except RateLimitError:
            wait_time = 2 ** (attempt + 1)
            logger.warning(f"LLM RateLimit hit on attempt {attempt + 1}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            if attempt >= max_retries:
                logger.error("LLM RateLimit exceeded. Please check OpenAI credit balance.")
                return "❌ AI Error: Rate Limit (Check Billing)"
        except APITimeoutError:
            logger.warning(f"LLM Timeout on attempt {attempt + 1}. Retrying...")
            if attempt >= max_retries:
                logger.error("LLM Timeout exceeded.")
                return "❌ AI Error: Timeout"
        except APIStatusError as exc:
            logger.error(f"LLM API Error: {exc.status_code} - {exc.message}")
            return f"❌ AI Error: {exc.message}"
        except Exception as exc:
            logger.exception(f"An unexpected error occurred during LLM request: {exc}")
            return "❌ AI Error: An unexpected error occurred."
    return None


def ollama_chat_request(
    *,
    ollama_client,
    model: str,
    prompt: str,
    is_json: bool = False,
    schema: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
    logger,
) -> Optional[str]:
    options = {
        "temperature": 0.3,
        "num_predict": 4096,
    }
    format_param = "json" if (schema or is_json) else None
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = ollama_client.chat(
            model=model,
            messages=messages,
            format=format_param,
            options=options,
        )
        return response["message"]["content"]
    except Exception as exc:
        logger.error(f"Ollama Request Failed for model '{model}': {exc}")
        return f"❌ AI Error: Ollama request failed ({model}). Check server logs."
