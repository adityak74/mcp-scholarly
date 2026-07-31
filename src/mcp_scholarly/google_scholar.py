import os
import sys
import time
from typing import List

from scholarly import scholarly, ProxyGenerator

MAX_RESULTS = 10

# 指数退避重试配置
# SCHOLAR_MAX_RETRIES: 最大重试次数（优先读取环境变量，未设置时默认 3）
# 退避策略：初始 1s，每次连续重试翻倍，上限 10s
#
# NOTE: kept low on purpose. MCP clients enforce their own request timeout
# (this is what surfaces as "MCP error -32001: fetch failed" in #11), so
# retrying for minutes only delays the same failure past that timeout
# instead of avoiding it.
DEFAULT_MAX_RETRIES = 3
INITIAL_BACKOFF_SEC = 1
MAX_BACKOFF_SEC = 10

# Google Scholar blocks most requests coming directly from datacenter/cloud
# IPs with a CAPTCHA, which scholarly surfaces as a generic fetch failure.
# Routing through a rotating free proxy avoids tripping that block.
FREE_PROXY_TIMEOUT_SEC = 1
FREE_PROXY_WAIT_SEC = 15


def _get_max_retries() -> int:
    """优先读取环境变量 SCHOLAR_MAX_RETRIES，未设置或非法时返回默认值 3"""
    raw = os.environ.get("SCHOLAR_MAX_RETRIES")
    if raw is None or raw == "":
        return DEFAULT_MAX_RETRIES
    try:
        n = int(raw, 10)
    except (TypeError, ValueError):
        return DEFAULT_MAX_RETRIES
    return n if n >= 0 else DEFAULT_MAX_RETRIES


def _backoff_delay(attempt: int) -> float:
    """指数退避：初始 1s，每次翻倍，上限 10s"""
    return min(INITIAL_BACKOFF_SEC * (2 ** attempt), MAX_BACKOFF_SEC)


class GoogleScholar:
    _proxy_ready = False

    def __init__(self):
        self.scholarly = scholarly
        self._ensure_proxy()

    @classmethod
    def _ensure_proxy(cls) -> None:
        """Attempt proxy setup once per process; fall back to a direct
        connection if no working free proxy can be found."""
        if cls._proxy_ready:
            return
        cls._proxy_ready = True
        try:
            proxy_generator = ProxyGenerator()
            if proxy_generator.FreeProxies(timeout=FREE_PROXY_TIMEOUT_SEC, wait_time=FREE_PROXY_WAIT_SEC):
                scholarly.use_proxy(proxy_generator)
            else:
                print("[google_scholar] no working free proxy found, continuing without proxy", file=sys.stderr)
        except Exception as error:
            print(f"[google_scholar] proxy setup failed ({error}), continuing without proxy", file=sys.stderr)

    def get_scholarly(self, keyword):
        return self.scholarly.search_pubs(keyword)

    @staticmethod
    def _parse_results(search_results):
        articles = []
        results_iter = 0
        for searched_article in search_results:
            bib = searched_article.get('bib', {})
            title = bib.get('title', 'No title')
            abstract = bib.get('abstract', 'No abstract available')
            pub_url = searched_article.get('pub_url', 'No URL available')
            
            article_string = f"Title: {title}\nAbstract: {abstract}\nURL: {pub_url}"
            articles.append(article_string)
            results_iter += 1
            if results_iter >= MAX_RESULTS:
                break
        return articles

    def search_pubs(self, keyword) -> List[str]:
        """
        搜索 Google Scholar 论文，失败时指数退避重试。
        重试上限由环境变量 SCHOLAR_MAX_RETRIES 控制（默认 3）。
        """
        max_retries = _get_max_retries()
        last_error: BaseException | None = None

        for attempt in range(max_retries + 1):
            try:
                search_results = self.scholarly.search_pubs(keyword)
                articles = self._parse_results(search_results)
                return articles
            except Exception as error:
                last_error = error
                if attempt >= max_retries:
                    break
                delay = _backoff_delay(attempt)
                print(
                    f"[google_scholar] attempt {attempt + 1}/{max_retries + 1} "
                    f"failed ({type(error).__name__}: {error}), "
                    f"retry in {delay}s",
                    file=sys.stderr,
                )
                time.sleep(delay)

        # 所有重试耗尽，抛出最后一次的异常
        raise last_error  # type: ignore[misc]
