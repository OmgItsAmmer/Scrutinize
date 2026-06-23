import json
import re
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from raw LLM output (handles fenced code blocks)."""
    stripped = text.strip()
    if not stripped:
        msg = "empty JSON payload"
        raise ValueError(msg)

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped, re.IGNORECASE)
    if fence_match:
        stripped = fence_match.group(1).strip()

    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        msg = "expected JSON object"
        raise ValueError(msg)
    return parsed
