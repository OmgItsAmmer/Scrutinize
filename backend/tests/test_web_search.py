import pytest
from app.services.web_search import WebSearchService
from app.schemas.search import SearchSource
from app.models.file import FileModality

class FakeSettings:
    enable_web_search = True
    web_search_engine = "brave"
    brave_search_api_key = "fake_brave_key"
    tavily_api_key = "fake_tavily_key"
    jina_reader_token = "fake_jina_token"


@pytest.mark.anyio
async def test_web_search_brave(monkeypatch):
    service = WebSearchService(FakeSettings())
    called_with = {}

    async def mock_get(url, headers, params, **kwargs):
        called_with["url"] = url
        called_with["headers"] = headers
        called_with["params"] = params
        
        class MockResponse:
            def raise_for_status(self):
                pass
            def json(self):
                return {
                    "web": {
                        "results": [
                            {
                                "title": "Brave AI news",
                                "url": "https://example.com/brave",
                                "description": "This is a description"
                            }
                        ]
                    }
                }
        return MockResponse()

    monkeypatch.setattr(service.client, "get", mock_get)
    results = await service.search("AI news", limit=1)

    assert called_with["url"] == "https://api.search.brave.com/res/v1/web/search"
    assert called_with["headers"]["X-Subscription-Token"] == "fake_brave_key"
    assert called_with["params"]["q"] == "AI news"
    
    assert len(results) == 1
    assert results[0]["title"] == "Brave AI news"
    assert results[0]["url"] == "https://example.com/brave"
    assert results[0]["snippet"] == "This is a description"


@pytest.mark.anyio
async def test_web_search_tavily(monkeypatch):
    settings = FakeSettings()
    settings.web_search_engine = "tavily"
    service = WebSearchService(settings)
    called_with = {}

    async def mock_post(url, json, **kwargs):
        called_with["url"] = url
        called_with["json"] = json
        
        class MockResponse:
            def raise_for_status(self):
                pass
            def json(self):
                return {
                    "results": [
                        {
                            "title": "Tavily AI news",
                            "url": "https://example.com/tavily",
                            "content": "Tavily content snippet"
                        }
                    ]
                }
        return MockResponse()

    monkeypatch.setattr(service.client, "post", mock_post)
    results = await service.search("AI news", limit=1)

    assert called_with["url"] == "https://api.tavily.com/search"
    assert called_with["json"]["api_key"] == "fake_tavily_key"
    assert called_with["json"]["query"] == "AI news"
    
    assert len(results) == 1
    assert results[0]["title"] == "Tavily AI news"
    assert results[0]["url"] == "https://example.com/tavily"
    assert results[0]["snippet"] == "Tavily content snippet"


@pytest.mark.anyio
async def test_web_scrape_jina(monkeypatch):
    service = WebSearchService(FakeSettings())
    called_with = {}

    async def mock_get(url, headers, **kwargs):
        called_with["url"] = url
        called_with["headers"] = headers
        
        class MockResponse:
            text = "Clean Markdown Content from Jina Reader"
            def raise_for_status(self):
                pass
        return MockResponse()

    monkeypatch.setattr(service.client, "get", mock_get)
    content = await service.scrape_url("https://example.com/article")

    assert called_with["url"] == "https://r.jina.ai/https://example.com/article"
    assert called_with["headers"]["Authorization"] == "Bearer fake_jina_token"
    assert content == "Clean Markdown Content from Jina Reader"
