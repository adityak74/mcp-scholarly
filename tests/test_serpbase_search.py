from unittest.mock import MagicMock, patch

import pytest

from mcp_scholarly import server
from mcp_scholarly.serpbase_search import MAX_RESULTS, SerpBaseSearch, _parse_results


# --- _parse_results ---

def test_parse_results_maps_organic_items():
    data = {
        "organic": [
            {"title": "Title A", "link": "http://a", "snippet": "Snippet A"},
            {"title": "Title B", "link": "http://b", "snippet": "Snippet B"},
        ]
    }

    parsed = _parse_results(data)

    assert parsed == [
        "Title: Title A\nSummary: Snippet A\nURL: http://a",
        "Title: Title B\nSummary: Snippet B\nURL: http://b",
    ]


def test_parse_results_defaults_missing_fields():
    data = {"organic": [{}, {"title": "T", "link": "u"}]}

    parsed = _parse_results(data)

    assert parsed[0] == "Title: No title\nSummary: No summary available\nURL: No URL available"
    assert parsed[1] == "Title: T\nSummary: No summary available\nURL: u"


def test_parse_results_truncates_at_max_results():
    data = {"organic": [{"title": f"T{i}"} for i in range(MAX_RESULTS + 5)]}

    parsed = _parse_results(data)

    assert len(parsed) == MAX_RESULTS


def test_parse_results_empty_organic():
    assert _parse_results({}) == []


# --- SerpBaseSearch.available ---

def test_available_false_without_key(monkeypatch):
    monkeypatch.delenv("SERPBASE_API_KEY", raising=False)
    assert SerpBaseSearch().available is False


def test_available_true_with_key(monkeypatch):
    monkeypatch.setenv("SERPBASE_API_KEY", "test-key")
    assert SerpBaseSearch().available is True


# --- SerpBaseSearch.search ---

def test_search_returns_empty_list_without_key(monkeypatch):
    monkeypatch.delenv("SERPBASE_API_KEY", raising=False)
    instance = SerpBaseSearch()
    assert instance.search("keyword") == []


def test_search_posts_to_api(monkeypatch):
    monkeypatch.setenv("SERPBASE_API_KEY", "test-key")
    instance = SerpBaseSearch()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "status": 0,
        "organic": [{"title": "T", "link": "u", "snippet": "s"}],
    }
    fake_client = MagicMock()
    fake_client.post.return_value = fake_resp
    instance._client = fake_client

    results = instance.search("keyword")

    assert results == ["Title: T\nSummary: s\nURL: u"]
    fake_client.post.assert_called_once()
    args, kwargs = fake_client.post.call_args
    assert kwargs["json"] == {"q": "keyword", "hl": "en", "gl": "us", "page": 1}
    assert kwargs["headers"] == {"X-API-Key": "test-key"}
    fake_client.close.assert_called_once()


def test_search_raises_on_api_error_status(monkeypatch):
    monkeypatch.setenv("SERPBASE_API_KEY", "test-key")
    instance = SerpBaseSearch()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"status": 1001, "error": "unauthorized"}
    fake_client = MagicMock()
    fake_client.post.return_value = fake_resp
    instance._client = fake_client

    with pytest.raises(RuntimeError, match="unauthorized"):
        instance.search("keyword")

    fake_client.close.assert_called_once()


def test_search_raises_on_http_error(monkeypatch):
    monkeypatch.setenv("SERPBASE_API_KEY", "test-key")
    instance = SerpBaseSearch()
    fake_client = MagicMock()
    fake_client.post.side_effect = RuntimeError("boom")
    instance._client = fake_client

    with pytest.raises(RuntimeError, match="boom"):
        instance.search("keyword")

    fake_client.close.assert_called_once()


# --- server.search_google_web ---

def test_server_search_google_web_formats_results():
    fake_engine = MagicMock()
    fake_engine.search.return_value = ["Title: T\nSummary: s\nURL: u"]
    with patch.object(server, "SerpBaseSearch", return_value=fake_engine):
        out = server.search_google_web("keyword")

    assert out == "Search articles for keyword:\nTitle: T\nSummary: s\nURL: u"
    fake_engine.search.assert_called_once_with("keyword")


def test_server_search_google_web_no_results():
    fake_engine = MagicMock()
    fake_engine.search.return_value = []
    with patch.object(server, "SerpBaseSearch", return_value=fake_engine):
        out = server.search_google_web("keyword")

    assert out == "No results for keyword."


def test_server_search_google_web_raises_on_empty_keyword():
    with pytest.raises(ValueError, match="Missing keyword"):
        server.search_google_web("")
