from unittest.mock import MagicMock, patch

import pytest

from mcp_scholarly import google_scholar as gs_module
from mcp_scholarly.google_scholar import GoogleScholar, _backoff_delay, _get_max_retries


# --- _get_max_retries ---

def test_get_max_retries_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("SCHOLAR_MAX_RETRIES", raising=False)
    assert _get_max_retries() == gs_module.DEFAULT_MAX_RETRIES


def test_get_max_retries_defaults_when_env_empty(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "")
    assert _get_max_retries() == gs_module.DEFAULT_MAX_RETRIES


def test_get_max_retries_uses_valid_env_value(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "7")
    assert _get_max_retries() == 7


def test_get_max_retries_allows_zero(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "0")
    assert _get_max_retries() == 0


def test_get_max_retries_defaults_on_negative_value(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "-1")
    assert _get_max_retries() == gs_module.DEFAULT_MAX_RETRIES


def test_get_max_retries_defaults_on_non_numeric_value(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "not-a-number")
    assert _get_max_retries() == gs_module.DEFAULT_MAX_RETRIES


# --- _backoff_delay ---

def test_backoff_delay_grows_exponentially():
    assert _backoff_delay(0) == 1
    assert _backoff_delay(1) == 2
    assert _backoff_delay(2) == 4


def test_backoff_delay_caps_at_max():
    assert _backoff_delay(10) == gs_module.MAX_BACKOFF_SEC


# --- GoogleScholar._ensure_proxy ---

def test_ensure_proxy_uses_working_free_proxy():
    GoogleScholar._proxy_ready = False
    fake_proxy_generator = MagicMock()
    fake_proxy_generator.FreeProxies.return_value = True

    with patch.object(gs_module, "ProxyGenerator", return_value=fake_proxy_generator) as pg_cls, \
         patch.object(gs_module.scholarly, "use_proxy") as use_proxy:
        GoogleScholar()

    pg_cls.assert_called_once()
    fake_proxy_generator.FreeProxies.assert_called_once_with(
        timeout=gs_module.FREE_PROXY_TIMEOUT_SEC, wait_time=gs_module.FREE_PROXY_WAIT_SEC
    )
    use_proxy.assert_called_once_with(fake_proxy_generator)


def test_ensure_proxy_falls_back_when_no_proxy_found():
    GoogleScholar._proxy_ready = False
    fake_proxy_generator = MagicMock()
    fake_proxy_generator.FreeProxies.return_value = False

    with patch.object(gs_module, "ProxyGenerator", return_value=fake_proxy_generator), \
         patch.object(gs_module.scholarly, "use_proxy") as use_proxy:
        GoogleScholar()

    use_proxy.assert_not_called()


def test_ensure_proxy_falls_back_when_setup_raises():
    GoogleScholar._proxy_ready = False

    with patch.object(gs_module, "ProxyGenerator", side_effect=RuntimeError("boom")):
        GoogleScholar()  # must not raise

    assert GoogleScholar._proxy_ready is True


def test_ensure_proxy_only_runs_once_per_process():
    GoogleScholar._proxy_ready = True

    with patch.object(gs_module, "ProxyGenerator") as pg_cls:
        GoogleScholar()

    pg_cls.assert_not_called()


# --- GoogleScholar.get_scholarly ---

def test_get_scholarly_delegates_to_scholarly_search_pubs():
    GoogleScholar._proxy_ready = True
    instance = GoogleScholar()
    instance.scholarly = MagicMock()
    instance.scholarly.search_pubs.return_value = "raw-results"

    assert instance.get_scholarly("keyword") == "raw-results"
    instance.scholarly.search_pubs.assert_called_once_with("keyword")


# --- GoogleScholar._parse_results ---

def test_parse_results_uses_bib_fields_with_defaults():
    results = [
        {"bib": {"title": "Title A", "abstract": "Abstract A"}, "pub_url": "http://a"},
        {"bib": {}, "pub_url": "http://b"},
        {},
    ]

    parsed = GoogleScholar._parse_results(results)

    assert parsed[0] == "Title: Title A\nAbstract: Abstract A\nURL: http://a"
    assert parsed[1] == "Title: No title\nAbstract: No abstract available\nURL: http://b"
    assert parsed[2] == "Title: No title\nAbstract: No abstract available\nURL: No URL available"


def test_parse_results_truncates_at_max_results():
    results = [{"bib": {"title": f"T{i}"}, "pub_url": "u"} for i in range(gs_module.MAX_RESULTS + 5)]

    parsed = GoogleScholar._parse_results(results)

    assert len(parsed) == gs_module.MAX_RESULTS


# --- GoogleScholar.search_pubs ---

def test_search_pubs_succeeds_on_first_attempt():
    GoogleScholar._proxy_ready = True
    instance = GoogleScholar()
    instance.scholarly = MagicMock()
    instance.scholarly.search_pubs.return_value = [{"bib": {"title": "T"}, "pub_url": "u"}]

    articles = instance.search_pubs("keyword")

    assert articles == ["Title: T\nAbstract: No abstract available\nURL: u"]
    instance.scholarly.search_pubs.assert_called_once_with("keyword")


def test_search_pubs_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "3")
    GoogleScholar._proxy_ready = True
    instance = GoogleScholar()
    instance.scholarly = MagicMock()
    instance.scholarly.search_pubs.side_effect = [
        RuntimeError("first failure"),
        [{"bib": {"title": "T"}, "pub_url": "u"}],
    ]

    with patch.object(gs_module.time, "sleep") as sleep_mock:
        articles = instance.search_pubs("keyword")

    assert articles == ["Title: T\nAbstract: No abstract available\nURL: u"]
    assert instance.scholarly.search_pubs.call_count == 2
    sleep_mock.assert_called_once_with(1)


def test_search_pubs_raises_last_error_after_exhausting_retries(monkeypatch):
    monkeypatch.setenv("SCHOLAR_MAX_RETRIES", "2")
    GoogleScholar._proxy_ready = True
    instance = GoogleScholar()
    instance.scholarly = MagicMock()
    errors = [RuntimeError("e1"), RuntimeError("e2"), RuntimeError("e3")]
    instance.scholarly.search_pubs.side_effect = errors

    with patch.object(gs_module.time, "sleep"):
        with pytest.raises(RuntimeError, match="e3"):
            instance.search_pubs("keyword")

    assert instance.scholarly.search_pubs.call_count == 3
