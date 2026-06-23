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

_FOLLOW_UP_RE = re.compile(
    r"(?:"
    r"\b(?:that|this|it|those|them|same|above|earlier|previous|last|there)\b|"
    r"\b(?:what|how)\s+about\b|"
    r"^(?:and|but|also)\b|"
    r"\b(?:instead\s+of|rather\s+than|the\s+same)\b|"
    r"\b(?:how\s+long|how\s+much|how\s+many|what\s+temperature|what\s+temp|which\s+one)\b"
    r")",
    re.IGNORECASE,
)


def is_standalone_message(query: str) -> bool:
    """Greeting, acknowledgment, or chitchat — not a library search question."""
    stripped = query.strip()
    if not stripped:
        return True
    return bool(_STANDALONE_RE.match(stripped))


def is_contextual_follow_up(query: str) -> bool:
    """True when the query refers to prior conversation and needs that context."""
    stripped = query.strip()
    if not stripped or is_standalone_message(stripped):
        return False
    return bool(_FOLLOW_UP_RE.search(stripped))


def append_conversation_context(lines: list[str], conversation_context: str) -> None:
    stripped = conversation_context.strip()
    if stripped:
        lines.append(f"Conversation context:\n{stripped}")
