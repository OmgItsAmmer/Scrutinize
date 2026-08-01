import re

POISON_PATTERNS = [
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:", re.IGNORECASE),
    re.compile(r"assistant\s*:", re.IGNORECASE),
    re.compile(r"new\s+instruction", re.IGNORECASE),
    re.compile(r"you\s+are\s+(?:now\s+)?(?:an?\s+)?(?:\w+\s+)*assistant", re.IGNORECASE),
]

def check_for_injection(text: str) -> bool:
    """Check if the text chunk contains patterns indicative of prompt injection."""
    if not text:
        return False
    return any(pattern.search(text) for pattern in POISON_PATTERNS)

def wrap_untrusted(sources: list) -> str:
    """Safely format and delimit retrieved search sources inside an untrusted content envelope.
    
    Escapes tag boundaries within content to prevent escape attacks.
    """
    wrapped = []
    for i, source in enumerate(sources, start=1):
        content = source.content or ""
        
        # Escape XML-like tags used as delimiters
        safe_content = content.replace("<retrieved_source", "&lt;retrieved_source")
        safe_content = safe_content.replace("</retrieved_source>", "&lt;/retrieved_source&gt;")
        
        is_poisoned = getattr(source, "is_poisoned", False)
        poison_attr = ' is_poisoned="true"' if is_poisoned else ''
        
        wrapped.append(
            f'<retrieved_source id="{i}"{poison_attr}>\n'
            f'[Source {i}] Title: {source.title}\n'
            f'{safe_content}\n'
            f'</retrieved_source>'
        )
    return "\n\n".join(wrapped)
