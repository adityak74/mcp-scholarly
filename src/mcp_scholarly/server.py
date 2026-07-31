from mcp.server.mcpserver import MCPServer

from .arxiv_search import ArxivSearch
from .google_scholar import GoogleScholar

mcp = MCPServer("mcp-scholarly")


@mcp.tool(
    name="search-arxiv",
    description="Search arxiv for articles related to the given keyword.",
)
def search_arxiv(keyword: str) -> str:
    if not keyword:
        raise ValueError("Missing keyword")
    arxiv_search = ArxivSearch()
    results = arxiv_search.search(keyword)
    return f"Search articles for {keyword}:\n" + "\n\n\n".join(results)


@mcp.tool(
    name="search-google-scholar",
    description="Search google scholar for articles related to the given keyword.",
)
def search_google_scholar(keyword: str) -> str:
    if not keyword:
        raise ValueError("Missing keyword")
    google_scholar = GoogleScholar()
    results = google_scholar.search_pubs(keyword=keyword)
    return f"Search articles for {keyword}:\n" + "\n\n\n".join(results)


async def main():
    await mcp.run_stdio_async()
