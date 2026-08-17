from unittest.mock import AsyncMock, patch

import pytest

from mcp_scholarly import server


# --- search_arxiv ---

def test_search_arxiv_rejects_missing_keyword():
    with pytest.raises(ValueError, match="Missing keyword"):
        server.search_arxiv("")


def test_search_arxiv_returns_formatted_results():
    with patch.object(server, "ArxivSearch") as arxiv_search_cls:
        arxiv_search_cls.return_value.search.return_value = ["article-1", "article-2"]
        result = server.search_arxiv("transformers")

    arxiv_search_cls.return_value.search.assert_called_once_with("transformers")
    assert result == "Search articles for transformers:\narticle-1\n\n\narticle-2"


# --- search_google_scholar ---

def test_search_google_scholar_rejects_missing_keyword():
    with pytest.raises(ValueError, match="Missing keyword"):
        server.search_google_scholar("")


def test_search_google_scholar_returns_formatted_results():
    with patch.object(server, "GoogleScholar") as google_scholar_cls:
        google_scholar_cls.return_value.search_pubs.return_value = ["article-1", "article-2"]
        result = server.search_google_scholar("transformers")

    google_scholar_cls.return_value.search_pubs.assert_called_once_with(keyword="transformers")
    assert result == "Search articles for transformers:\narticle-1\n\n\narticle-2"


# --- main ---

async def test_main_runs_stdio_server():
    with patch.object(server.mcp, "run_stdio_async", new_callable=AsyncMock) as run_mock:
        await server.main()

    run_mock.assert_called_once_with()


def test_arxiv_tool_description_warns_that_matches_may_be_weak():
    """arXiv returns best-effort matches for any query, including nonsense.
    A caller scoring novelty must not read "results came back" as "prior work
    exists", so the tool says so where the model will read it."""
    from mcp_scholarly import server

    import inspect
    src = inspect.getsource(server)
    start = src.index('name="search-arxiv"')
    desc = src[start:start + 600]
    assert "relevance" in desc.lower()
    assert "judge" in desc.lower() or "may not" in desc.lower()
