import pytest
import asyncio
import httpx
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.user import User
from app.models.conversation import ChatConversation
from app.core.deps import get_current_user

def mock_generate_stream(*args, **kwargs):
    for i in range(5):
        yield f"chunk {i} "

def mock_search_stream(*args, **kwargs):
    yield "event: status\ndata: {\"step\": \"retrieval_end\", \"sources\": []}\n\n"
    for i in range(3):
        yield f'event: chunk\ndata: {{"text": "block {i} "}}\n\n'
    yield "event: result\ndata: {\"answer\": \"final answer\", \"sources\": []}\n\n"

@pytest.mark.asyncio
async def test_concurrent_streams_concurrency(client: TestClient, session: Session):
    app = client.app
    
    user = User(
        id=uuid4(),
        email="concurrent_user@example.com",
        hashed_password="...",
        role="member",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    conversation = ChatConversation(
        id=uuid4(),
        title="Concurrent Stream Test",
        owner_user_id=user.id,
        scope="general",
        retrieval_policy="web_only",
    )
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    
    # Register dependency overrides
    app.dependency_overrides[get_current_user] = lambda: user
    
    def override_session():
        yield session
        
    from app.core.database import get_session
    from app.core.deps import get_db_session
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_db_session] = override_session
    
    async def run_client_request(async_client: httpx.AsyncClient):
        payload = {
            "content": "Hello, this is a test query.",
            "client_message_id": str(uuid4()),
        }
        url = f"/v3/conversations/{conversation.id}/messages/stream"
        response = await async_client.post(url, json=payload, timeout=30.0)
        assert response.status_code == 200
        
        content = ""
        async for line in response.aiter_lines():
            content += line
        return content

    async def mock_web_search(*args, **kwargs):
        return [{"title": "Mock Search", "url": "http://mock", "snippet": "Mock Snippet"}]

    async def mock_is_disconnected(*args, **kwargs):
        return False

    # Use patch to mock LLM clients, Burr orchestrator, web search, and request disconnection
    with (
        patch("app.services.v2.llm_clients.local.LocalLlmClient.generate_stream", side_effect=mock_generate_stream),
        patch("app.services.v2.llm_clients.cloud.CloudLlmClient.generate_stream", side_effect=mock_generate_stream),
        patch("app.services.v4.burr_orchestrator.BurrOrchestrator.search_stream", side_effect=mock_search_stream),
        patch("app.services.web_search.WebSearchService.search", side_effect=mock_web_search),
        patch("starlette.requests.Request.is_disconnected", side_effect=mock_is_disconnected)
    ):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as async_client:
            tasks = [run_client_request(async_client) for _ in range(5)]
            results = await asyncio.gather(*tasks)
            
            for r in results:
                assert "message.completed" in r
                assert "final answer" in r
                
    # Clean up overrides
    app.dependency_overrides.clear()
