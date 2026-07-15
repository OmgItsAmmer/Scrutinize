import logging
import asyncio
import re
from typing import Any
from html.parser import HTMLParser
import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class HTMLStripper(HTMLParser):
    """Simple built-in HTML parser to strip tags and extract text as a fallback."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, d):
        self.text.append(d)

    def get_data(self):
        return "".join(self.text)


def strip_tags(html: str) -> str:
    s = HTMLStripper()
    s.feed(html)
    text = s.get_data()
    # Clean up excess whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class WebSearchService:
    """Service to handle querying web search APIs (Brave/Tavily) and scraping contents using Jina Reader or fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Query the search engine and return a list of dicts with title, url, snippet."""
        if not self.settings.enable_web_search:
            logger.info("Web search is disabled in settings.")
            return []

        query = query.strip()
        if not query:
            return []

        engine = self.settings.web_search_engine.lower()
        if engine == "tavily" and self.settings.tavily_api_key:
            return await self._search_tavily(query, limit)
        elif self.settings.brave_search_api_key:
            return await self._search_brave(query, limit)
        else:
            logger.warning("No Web Search API keys configured. Web search skipped.")
            return []

    async def _search_brave(self, query: str, limit: int) -> list[dict[str, Any]]:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.settings.brave_search_api_key,
        }
        params = {"q": query, "count": limit}
        try:
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            results = []
            web_results = data.get("web", {}).get("results", [])
            for res in web_results:
                results.append({
                    "title": res.get("title", ""),
                    "url": res.get("url", ""),
                    "snippet": res.get("description", ""),
                })
            return results
        except Exception as e:
            logger.exception("Brave Search failed: %s", e)
            return []

    async def _search_tavily(self, query: str, limit: int) -> list[dict[str, Any]]:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.settings.tavily_api_key,
            "query": query,
            "max_results": limit,
        }
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            results = []
            for res in data.get("results", []):
                results.append({
                    "title": res.get("title", ""),
                    "url": res.get("url", ""),
                    "snippet": res.get("content", ""),
                })
            return results
        except Exception as e:
            logger.exception("Tavily Search failed: %s", e)
            return []

    async def scrape_url(self, url: str) -> str:
        """Fetch content from a URL, preferring Jina Reader for clean Markdown, falling back to raw HTTP GET."""
        # 1. Try Jina Reader
        jina_url = f"https://r.jina.ai/{url}"
        headers = {}
        if self.settings.jina_reader_token:
            headers["Authorization"] = f"Bearer {self.settings.jina_reader_token}"

        try:
            response = await self.client.get(jina_url, headers=headers, timeout=10.0)
            response.raise_for_status()
            content = response.text
            if content.strip():
                return content.strip()
        except Exception as e:
            logger.warning("Jina Reader failed for %s, falling back to direct GET: %s", url, e)

        # 2. Fallback to direct GET + HTML stripping
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = await self.client.get(url, headers=headers, timeout=5.0)
            response.raise_for_status()
            return strip_tags(response.text)
        except Exception as e:
            logger.warning("Direct scrape failed for %s: %s", url, e)
            return ""

    async def _scrape_url_safe(self, url: str) -> str:
        try:
            return await self.scrape_url(url)
        except Exception as e:
            logger.warning("scrape_url raised exception for %s: %s", url, e)
            return ""

    async def scrape_urls_parallel(self, urls: list[str]) -> list[str]:
        """Fetch multiple URLs concurrently with a total timeout budget."""
        tasks = [self._scrape_url_safe(url) for url in urls]
        try:
            return await asyncio.wait_for(asyncio.gather(*tasks), timeout=12.0)
        except asyncio.TimeoutError:
            logger.warning("scrape_urls_parallel timed out after 12.0 seconds.")
            return [""] * len(urls)

    async def close(self):
        await self.client.aclose()
