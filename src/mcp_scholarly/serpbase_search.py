"""Google web search via the SerpBase API.

Optional provider used when the free scholarly scrape path is blocked
(Google Scholar rate-limits datacenter IPs hard, and the README already
recommends an API fallback for reliable results). Enabled only when
SERPBASE_API_KEY is set; otherwise the server starts and behaves exactly
as before, and this tool is simply not registered.
"""

import os

import httpx

API_URL = "https://api.serpbase.dev/google/search"
MAX_RESULTS = 10


def _parse_results(data: dict) -> list[str]:
    """Format the SerpBase organic results payload the same way the other
    providers format theirs (Title/Summary/URL blocks)."""
    articles = []
    for item in data.get("organic", []):
        title = item.get("title", "No title")
        link = item.get("link", "No URL available")
        snippet = item.get("snippet", "No summary available")
        articles.append(f"Title: {title}\nSummary: {snippet}\nURL: {link}")
        if len(articles) >= MAX_RESULTS:
            break
    return articles


class SerpBaseSearch:
    """Search Google for scholarly material via the SerpBase REST API."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("SERPBASE_API_KEY", "").strip()
        self._client = httpx.Client(timeout=30)

    @property
    def available(self) -> bool:
        """The provider is opt-in: without an API key it stays disabled."""
        return bool(self.api_key)

    def search(self, keyword: str) -> list[str]:
        if not self.available:
            return []
        try:
            resp = self._client.post(
                API_URL,
                json={"q": keyword, "hl": "en", "gl": "us", "page": 1},
                headers={"X-API-Key": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != 0:
                raise RuntimeError(data.get("error") or f"SerpBase error status={data.get('status')}")
            return _parse_results(data)
        finally:
            self.close()

    def close(self) -> None:
        self._client.close()
