from mcp.server.mcpserver import MCPServer

from .arxiv_search import ArxivSearch
from .google_scholar import GoogleScholar
from .serpbase_search import SerpBaseSearch

mcp = MCPServer("mcp-scholarly")


@mcp.tool(
    name="search-arxiv",
    description=(
        "Search arxiv for articles related to the given keyword. Results are "
        "ranked by relevance, but arxiv returns best-effort matches for any "
        "query, so a result set may contain weak or unrelated papers. Judge "
        "each result on its own; do not treat the presence of results as "
        "proof that prior work exists."
    ),
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


@mcp.tool(
    name="search-google-web",
    description=(
        "Search Google for articles and web results related to the given keyword. "
        "Available when the SERPBASE_API_KEY environment variable is set; when it "
        "is not set, this tool is not registered."
    ),
)
def search_google_web(keyword: str) -> str:
    if not keyword:
        raise ValueError("Missing keyword")
    serpbase = SerpBaseSearch()
    results = serpbase.search(keyword)
    if not results:
        return f"No results for {keyword}."
    return f"Search articles for {keyword}:\n" + "\n\n\n".join(results)


async def main():
    await mcp.run_stdio_async()
