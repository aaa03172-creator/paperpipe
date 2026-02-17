import json
import re
from typing import Any, Dict


def repair_and_parse_json(dirty_string: str) -> Dict[str, Any]:
    """
    Repair common malformed JSON patterns from LLM responses and parse to dict.
    Raises json.JSONDecodeError if parsing still fails.
    """
    if not dirty_string:
        raise json.JSONDecodeError("Empty JSON content", "", 0)

    text = dirty_string.strip()

    # 1) Standard parse first.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        raise json.JSONDecodeError("JSON root is not an object", text, 0)
    except json.JSONDecodeError:
        pass

    # 2) Strip markdown fenced blocks.
    fenced_json = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced_json:
        text = fenced_json.group(1).strip()
    else:
        fenced_any = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if fenced_any:
            text = fenced_any.group(1).strip()

    # 3) Extract JSON object region.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    # 4) Common fixups.
    # Remove trailing commas before object/array close.
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Convert Python-style None/True/False literals.
    text = re.sub(r"\bNone\b", "null", text)
    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)
    # Convert single-quoted keys/strings to double-quoted JSON strings.
    text = re.sub(r"(?<!\\)'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', text)

    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("JSON root is not an object", text, 0)
    return parsed
