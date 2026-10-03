"""Google Scholar search via the Serply API.

Optional provider for the same Google Scholar index that `search-google-scholar`
scrapes. The scrape path routes through a free proxy pool and retries with
backoff because Google Scholar CAPTCHAs datacenter IPs; an API key removes
that failure mode. Enabled only when SERPLY_API_KEY is set; otherwise the
server starts and behaves exactly as before.
"""

import os

import httpx

API_URL = "https://api.serply.io/v1/scholar"
MAX_RESULTS = 10


def _parse_results(data: dict) -> list[str]:
    """Format the Serply `articles` payload the same way the other providers
    format theirs (Title/.../URL blocks), keeping authors and citation count
    since Scholar results carry no abstract."""
    articles = []
    for item in data.get("articles", []):
        title = item.get("title", "No title")
        link = item.get("link", "No URL available")
        authors = (item.get("author") or {}).get("names") or item.get("description") or "No authors available"
        lines = [f"Title: {title}", f"Authors: {authors}"]
        cited_by = ((item.get("extras") or {}).get("citations") or {}).get("count")
        if cited_by:
            lines.append(f"Citations: {cited_by}")
        lines.append(f"URL: {link}")
        pdf = (item.get("doc") or {}).get("link")
        if pdf:
            lines.append(f"PDF: {pdf}")
        articles.append("\n".join(lines))
        if len(articles) >= MAX_RESULTS:
            break
    return articles


class SerplyScholarSearch:
    """Search Google Scholar via the Serply REST API."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("SERPLY_API_KEY", "").strip()
        self._client = httpx.Client(timeout=30)

    @property
    def available(self) -> bool:
        """The provider is opt-in: without an API key it stays disabled."""
        return bool(self.api_key)

    def search(self, keyword: str) -> list[str]:
        if not self.available:
            return []
        try:
            resp = self._client.get(
                API_URL,
                params={"q": keyword, "num": MAX_RESULTS},
                headers={"X-Api-Key": self.api_key, "User-Agent": "mcp-scholarly"},
            )
            resp.raise_for_status()
            return _parse_results(resp.json())
        finally:
            self.close()

    def close(self) -> None:
        self._client.close()
