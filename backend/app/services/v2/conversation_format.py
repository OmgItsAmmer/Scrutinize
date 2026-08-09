import re

_STANDALONE_RE = re.compile(
    r"^(?:"
    r"hi|hey|hello|yo|sup|howdy|hiya|"
    r"good\s+(?:morning|afternoon|evening)|"
    r"what(?:'s|\s+is)\s+up|"
    r"how\s+are\s+you|"
    r"hello[!.]*\s*how\s+can\s+i\s+(?:help|assist)(?:\s+you)?(?:\s+today)?|"
    r"how\s+can\s+i\s+(?:help|assist)(?:\s+you)?(?:\s+today)?|"
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


def filter_substantive_context(conversation_context: str) -> str:
    """Filter out pure greetings and greeting replies from conversation context."""
    stripped = conversation_context.strip()
    if not stripped:
        return ""
    
    substantive_lines: list[str] = []
    for line in stripped.splitlines():
        match = re.match(r"^\[.*?\]\s*(user|assistant):\s*(.*)$", line.strip(), re.IGNORECASE)
        if match:
            text = match.group(2).strip()
            if not is_standalone_message(text):
                substantive_lines.append(line)
        else:
            if not is_standalone_message(line):
                substantive_lines.append(line)
            
    return "\n".join(substantive_lines).strip()


def append_conversation_context(lines: list[str], conversation_context: str) -> None:
    cleaned = filter_substantive_context(conversation_context)
    if cleaned:
        lines.append(f"Previous conversation (oldest first, UTC timestamps):\n{cleaned}")

