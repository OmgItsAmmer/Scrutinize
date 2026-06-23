from datetime import UTC, datetime

from app.core.config import Settings
from app.schemas.v2.search import ChatMessage, ConversationState

RECENCY_PREAMBLE = (
    "Previous conversation (chronological, oldest first). "
    "Each line includes a UTC timestamp. Prefer the latest messages when "
    "resolving follow-ups, pronouns, or ambiguous references."
)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_message_line(message: ChatMessage) -> str:
    content = message.content.strip()
    if message.timestamp is not None:
        return f"[{format_timestamp(message.timestamp)}] {message.role}: {content}"
    return f"{message.role}: {content}"


def format_conversation_context(state: ConversationState) -> str:
    if not state.messages:
        return ""
    lines = [RECENCY_PREAMBLE]
    for message in state.messages:
        lines.append(format_message_line(message))
    return "\n".join(lines)


def _trim_messages(messages: list[ChatMessage], max_messages: int) -> list[ChatMessage]:
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]


class ConversationMemory:
    """Rolling snapshot of the most recent chat turns (no LLM summarization)."""

    def __init__(self, settings: Settings) -> None:
        # Each exchange is one user + one assistant message.
        self._max_messages = settings.v2_conversation_window_size * 2

    def prepare(self, conversation: ConversationState | None) -> tuple[ConversationState, str]:
        state = conversation or ConversationState()
        trimmed = _trim_messages(state.messages, self._max_messages)
        if len(trimmed) != len(state.messages):
            state = ConversationState(messages=trimmed)
        return state, format_conversation_context(state)

    def record_exchange(
        self,
        state: ConversationState,
        user_query: str,
        assistant_answer: str,
    ) -> ConversationState:
        now = datetime.now(UTC)
        messages = [
            *state.messages,
            ChatMessage(role="user", content=user_query.strip(), timestamp=now),
            ChatMessage(role="assistant", content=assistant_answer.strip(), timestamp=now),
        ]
        return ConversationState(messages=_trim_messages(messages, self._max_messages))
