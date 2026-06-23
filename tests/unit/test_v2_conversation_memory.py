from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.schemas.v2.search import ChatMessage, ConversationState
from app.services.v2.conversation_memory import (
    ConversationMemory,
    format_conversation_context,
    format_message_line,
)


@pytest.mark.unit
@pytest.mark.v2
def test_format_message_line_includes_timestamp():
    ts = datetime(2026, 6, 22, 14, 30, 0, tzinfo=UTC)
    line = format_message_line(ChatMessage(role="user", content="Hi", timestamp=ts))
    assert line == "[2026-06-22T14:30:00Z] user: Hi"


@pytest.mark.unit
@pytest.mark.v2
def test_format_conversation_context_includes_timestamps_and_recency_note():
    ts = datetime(2026, 6, 22, 14, 30, 0, tzinfo=UTC)
    state = ConversationState(
        messages=[
            ChatMessage(role="user", content="Hi", timestamp=ts),
            ChatMessage(role="assistant", content="Hello!", timestamp=ts),
        ],
    )
    context = format_conversation_context(state)
    assert "UTC timestamp" in context
    assert "latest messages" in context
    assert "[2026-06-22T14:30:00Z] user: Hi" in context
    assert "[2026-06-22T14:30:00Z] assistant: Hello!" in context


@pytest.mark.unit
@pytest.mark.v2
def test_format_conversation_context_empty():
    assert format_conversation_context(ConversationState()) == ""


@pytest.mark.unit
@pytest.mark.v2
def test_conversation_memory_record_exchange_appends_messages_with_timestamps():
    settings = Settings(local_llm_base_url="http://llm.test", v2_conversation_window_size=10)
    memory = ConversationMemory(settings)
    state = ConversationState()

    updated = memory.record_exchange(state, "Hello", "Hi there!")

    assert len(updated.messages) == 2
    assert updated.messages[0].role == "user"
    assert updated.messages[0].timestamp is not None
    assert updated.messages[1].content == "Hi there!"
    assert updated.messages[1].timestamp is not None


@pytest.mark.unit
@pytest.mark.v2
def test_conversation_memory_trims_oldest_when_window_exceeded():
    settings = Settings(local_llm_base_url="http://llm.test", v2_conversation_window_size=2)
    memory = ConversationMemory(settings)
    state = ConversationState(
        messages=[
            ChatMessage(role="user", content="m1"),
            ChatMessage(role="assistant", content="m2"),
            ChatMessage(role="user", content="m3"),
            ChatMessage(role="assistant", content="m4"),
        ]
    )

    updated = memory.record_exchange(state, "m5", "m6")

    assert len(updated.messages) == 4
    assert [message.content for message in updated.messages] == ["m3", "m4", "m5", "m6"]


@pytest.mark.unit
@pytest.mark.v2
def test_conversation_memory_prepare_trims_oversized_state():
    settings = Settings(local_llm_base_url="http://llm.test", v2_conversation_window_size=1)
    memory = ConversationMemory(settings)
    state = ConversationState(
        messages=[
            ChatMessage(role="user", content="old user"),
            ChatMessage(role="assistant", content="old assistant"),
            ChatMessage(role="user", content="new user"),
            ChatMessage(role="assistant", content="new assistant"),
        ]
    )

    trimmed, context = memory.prepare(state)

    assert len(trimmed.messages) == 2
    assert trimmed.messages[0].content == "new user"
    assert "new user" in context
    assert "old user" not in context
