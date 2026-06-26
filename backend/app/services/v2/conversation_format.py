import re

_STANDALONE_RE = re.compile(
    r"^(?:"
    r"hi|hey|hello|yo|sup|howdy|hiya|"
    r"good\s+(?:morning|afternoon|evening)|"
    r"what(?:'s|\s+is)\s+up|"
    r"how\s+are\s+you|"
    r"thanks?(?:\s+you)?|thank\s+you|thx|"
    r"ok(?:ay)?|cool|nice|great|got\s+it|"
    r"bye|goodbye|see\s+ya"
    r")[\s?!.]*$",
    re.IGNORECASE,
)


def is_standalone_message(query: str) -> bool:
    """Greeting, acknowledgment, or chitchat — not a library search question."""
    stripped = query.strip()
    if not stripped:
        return True
    return bool(_STANDALONE_RE.match(stripped))


def append_conversation_context(lines: list[str], conversation_context: str) -> None:
    stripped = conversation_context.strip()
    if stripped:
        lines.append(f"Previous conversation (oldest first, UTC timestamps):\n{stripped}")
