from unittest.mock import MagicMock, patch

import pytest

from mcp_scholarly import arxiv_search as arxiv_search_module
from mcp_scholarly.arxiv_search import ArxivSearch, _backoff_delay, _get_max_retries


# --- _get_max_retries ---

def test_get_max_retries_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("SCHOLAR_MAX_RETRIES", raising=False)
    assert _get_max_retries() == arxiv_search_module.DEFAULT_MAX_RETRIES


def test_get_max_retries_defaults_when_env_empty(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "")
    assert _get_max_retries() == arxiv_search_module.DEFAULT_MAX_RETRIES


def test_get_max_retries_uses_valid_env_value(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "5")
    assert _get_max_retries() == 5


def test_get_max_retries_allows_zero(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "0")
    assert _get_max_retries() == 0


def test_get_max_retries_defaults_on_negative_value(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "-3")
    assert _get_max_retries() == arxiv_search_module.DEFAULT_MAX_RETRIES


def test_get_max_retries_defaults_on_non_numeric_value(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "nope")
    assert _get_max_retries() == arxiv_search_module.DEFAULT_MAX_RETRIES


# --- _backoff_delay ---

def test_backoff_delay_grows_exponentially():
    assert _backoff_delay(0) == 1
    assert _backoff_delay(1) == 2
    assert _backoff_delay(2) == 4


def test_backoff_delay_caps_at_max():
    assert _backoff_delay(10) == arxiv_search_module.MAX_BACKOFF_SEC


# --- ArxivSearch.arxiv_search ---

def test_arxiv_search_builds_search_and_returns_results():
    instance = ArxivSearch()
    fake_client = MagicMock()
    fake_client.results.return_value = iter(["result-a", "result-b"])
    instance.client = fake_client

    with patch.object(arxiv_search_module.arxiv, "Search") as search_cls:
        search_cls.return_value = "search-object"
        results = instance.arxiv_search("keyword", max_results=5)

    search_cls.assert_called_once_with(
        query="keyword",
        max_results=5,
        sort_by=arxiv_search_module.arxiv.SortCriterion.SubmittedDate,
    )
    fake_client.results.assert_called_once_with("search-object")
    assert results == ["result-a", "result-b"]


# --- ArxivSearch._parse_results ---

def test_parse_results_formats_each_field():
    fake_result = MagicMock()
    fake_result.title = "A Title"
    fake_result.summary = "A Summary"
    fake_result.pdf_url = "http://pdf"
    link_a, link_b = MagicMock(), MagicMock()
    link_a.href = "http://a"
    link_b.href = "http://b"
    fake_result.links = [link_a, link_b]

    parsed = ArxivSearch._parse_results([fake_result])

    assert parsed == [
        "Title: A Title\nSummary: A Summary\nLinks: http://a||http://b\nPDF URL: http://pdf"
    ]


# --- ArxivSearch.search ---

def test_search_succeeds_on_first_attempt():
    instance = ArxivSearch()
    fake_result = MagicMock()
    fake_result.title = "T"
    fake_result.summary = "S"
    fake_result.pdf_url = "u"
    fake_result.links = []

    with patch.object(instance, "arxiv_search", return_value=[fake_result]) as search_mock:
        articles = instance.search("keyword", max_results=3)

    search_mock.assert_called_once_with("keyword", 3)
    assert articles == ["Title: T\nSummary: S\nLinks: \nPDF URL: u"]


def test_search_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "3")
    instance = ArxivSearch()
    fake_result = MagicMock()
    fake_result.title = "T"
    fake_result.summary = "S"
    fake_result.pdf_url = "u"
    fake_result.links = []

    with patch.object(
        instance, "arxiv_search", side_effect=[RuntimeError("first failure"), [fake_result]]
    ) as search_mock, patch.object(arxiv_search_module.time, "sleep") as sleep_mock:
        articles = instance.search("keyword")

    assert articles == ["Title: T\nSummary: S\nLinks: \nPDF URL: u"]
    assert search_mock.call_count == 2
    sleep_mock.assert_called_once_with(1)


def test_search_raises_last_error_after_exhausting_retries(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "2")
    instance = ArxivSearch()
    errors = [RuntimeError("e1"), RuntimeError("e2"), RuntimeError("e3")]

    with patch.object(instance, "arxiv_search", side_effect=errors) as search_mock, \
         patch.object(arxiv_search_module.time, "sleep"):
        with pytest.raises(RuntimeError, match="e3"):
            instance.search("keyword")

    assert search_mock.call_count == 3
