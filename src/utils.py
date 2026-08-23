import json
import logging
import re

logger = logging.getLogger(__name__)


def extract_json_from_llm(raw_text: str) -> dict:
    """Safely extract JSON from LLM response, handling markdown fences and preamble text.
    
    Handles these common LLM output patterns:
    1. Clean JSON: {"key": "value"}
    2. Markdown fenced: ```json\n{"key": "value"}\n```
    3. Preamble text: "Here is the JSON:\n```json\n{"key": "value"}\n```"
    4. Newline before fence: "\n```json\n{"key": "value"}\n```"
    """
    text = raw_text.strip()
    
    # 1. Try direct parse first (fastest path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 2. Remove markdown fences
    cleaned = re.sub(r'^```(?:json)?\s*', '', text)
    cleaned = re.sub(r'\s*```\s*$', '', cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # 3. Regex fallback: find first JSON object or array
    match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"No valid JSON found in LLM response: {text[:200]}")
