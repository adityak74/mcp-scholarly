from unittest.mock import MagicMock, patch

import pytest

from mcp_scholarly import server
from mcp_scholarly.serply_scholar import MAX_RESULTS, SerplyScholarSearch, _parse_results


# --- _parse_results ---

def test_parse_results_maps_articles():
    data = {
        "articles": [
            {
                "title": "Title A",
                "link": "http://a",
                "description": "A Author - Venue, 2020 - a.org",
                "author": {"names": "A Author - Venue, 2020 - a.org"},
                "extras": {"citations": {"count": "Cited by 42"}},
                "doc": {"link": "http://a.pdf", "type": "PDF"},
            },
            {"title": "Title B", "link": "http://b", "description": "B Author - 2021"},
        ]
    }

    parsed = _parse_results(data)

    assert parsed == [
        "Title: Title A\nAuthors: A Author - Venue, 2020 - a.org\nCitations: Cited by 42\nURL: http://a\nPDF: http://a.pdf",
        "Title: Title B\nAuthors: B Author - 2021\nURL: http://b",
    ]


def test_parse_results_defaults_missing_fields():
    data = {"articles": [{}, {"title": "T", "link": "u", "author": None, "extras": {}, "doc": None}]}

    parsed = _parse_results(data)

    assert parsed[0] == "Title: No title\nAuthors: No authors available\nURL: No URL available"
    assert parsed[1] == "Title: T\nAuthors: No authors available\nURL: u"


def test_parse_results_truncates_at_max_results():
    data = {"articles": [{"title": f"T{i}"} for i in range(MAX_RESULTS + 5)]}

    parsed = _parse_results(data)

    assert len(parsed) == MAX_RESULTS


def test_parse_results_empty_articles():
    assert _parse_results({}) == []


# --- SerplyScholarSearch.available ---

def test_available_false_without_key(monkeypatch):
    monkeypatch.delenv("SERPLY_API_KEY", raising=False)
    assert SerplyScholarSearch().available is False


def test_available_true_with_key(monkeypatch):
    monkeypatch.setenv("SERPLY_API_KEY", "test-key")
    assert SerplyScholarSearch().available is True


# --- SerplyScholarSearch.search ---

def test_search_returns_empty_list_without_key(monkeypatch):
    monkeypatch.delenv("SERPLY_API_KEY", raising=False)
    instance = SerplyScholarSearch()
    assert instance.search("keyword") == []


def test_search_gets_from_api(monkeypatch):
    monkeypatch.setenv("SERPLY_API_KEY", "test-key")
    instance = SerplyScholarSearch()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "articles": [{"title": "T", "link": "u", "description": "d"}],
    }
    fake_client = MagicMock()
    fake_client.get.return_value = fake_resp
    instance._client = fake_client

    results = instance.search("keyword")

    assert results == ["Title: T\nAuthors: d\nURL: u"]
    fake_client.get.assert_called_once()
    args, kwargs = fake_client.get.call_args
    assert args == ("https://api.serply.io/v1/scholar",)
    assert kwargs["params"] == {"q": "keyword", "num": MAX_RESULTS}
    assert kwargs["headers"] == {"X-Api-Key": "test-key", "User-Agent": "mcp-scholarly"}
    fake_resp.raise_for_status.assert_called_once()
    fake_client.close.assert_called_once()


def test_search_raises_on_http_error(monkeypatch):
    monkeypatch.setenv("SERPLY_API_KEY", "test-key")
    instance = SerplyScholarSearch()
    fake_client = MagicMock()
    fake_client.get.side_effect = RuntimeError("boom")
    instance._client = fake_client

    with pytest.raises(RuntimeError, match="boom"):
        instance.search("keyword")

    fake_client.close.assert_called_once()


# --- server.search_google_scholar_serply ---

def test_server_search_google_scholar_serply_formats_results():
    fake_engine = MagicMock()
    fake_engine.available = True
    fake_engine.search.return_value = ["Title: T\nAuthors: d\nURL: u"]
    with patch.object(server, "SerplyScholarSearch", return_value=fake_engine):
        out = server.search_google_scholar_serply("keyword")

    assert out == "Search articles for keyword:\nTitle: T\nAuthors: d\nURL: u"
    fake_engine.search.assert_called_once_with("keyword")


def test_server_search_google_scholar_serply_no_results():
    fake_engine = MagicMock()
    fake_engine.available = True
    fake_engine.search.return_value = []
    with patch.object(server, "SerplyScholarSearch", return_value=fake_engine):
        out = server.search_google_scholar_serply("keyword")

    assert out == "No results for keyword."


def test_server_search_google_scholar_serply_without_key():
    fake_engine = MagicMock()
    fake_engine.available = False
    with patch.object(server, "SerplyScholarSearch", return_value=fake_engine):
        out = server.search_google_scholar_serply("keyword")

    assert "SERPLY_API_KEY" in out
    fake_engine.search.assert_not_called()


def test_server_search_google_scholar_serply_raises_on_empty_keyword():
    with pytest.raises(ValueError, match="Missing keyword"):
        server.search_google_scholar_serply("")
