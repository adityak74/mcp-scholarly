import os
import sys
import time
from typing import List

import arxiv

client = arxiv.Client()

# 指数退避重试配置（与 google_scholar 共用，见该文件说明）
DEFAULT_MAX_RETRIES = 3
INITIAL_BACKOFF_SEC = 1
MAX_BACKOFF_SEC = 10


def _get_max_retries() -> int:
    raw = os.environ.get("SCHOLAR_MAX_RETRIES")
    if raw is None or raw == "":
        return DEFAULT_MAX_RETRIES
    try:
        n = int(raw, 10)
    except (TypeError, ValueError):
        return DEFAULT_MAX_RETRIES
    return n if n >= 0 else DEFAULT_MAX_RETRIES


def _backoff_delay(attempt: int) -> float:
    return min(INITIAL_BACKOFF_SEC * (2 ** attempt), MAX_BACKOFF_SEC)


class ArxivSearch:
    def __init__(self):
        self.client = arxiv.Client()

    def arxiv_search(self, keyword, max_results=10):
        search = arxiv.Search(query=keyword, max_results=max_results, sort_by=arxiv.SortCriterion.SubmittedDate)
        results = self.client.results(search)
        all_results = list(results)
        return all_results

    @staticmethod
    def _parse_results(results):
        formatted_results = []

        for result in results:
            title = result.title
            summary = result.summary
            links = "||".join([link.href for link in result.links])
            pdf_url = result.pdf_url

            article_data = "\n".join([
                f"Title: {title}",
                f"Summary: {summary}",
                f"Links: {links}",
                f"PDF URL: {pdf_url}",
            ])

            formatted_results.append(article_data)
        return formatted_results

    def search(self, keyword, max_results=10) -> List[str]:
        """
        搜索 arXiv 论文，失败时指数退避重试。
        重试上限由环境变量 SCHOLAR_MAX_RETRIES 控制（默认 3）。
        """
        max_retries = _get_max_retries()
        last_error: BaseException | None = None

        for attempt in range(max_retries + 1):
            try:
                results = self.arxiv_search(keyword, max_results)
                return self._parse_results(results)
            except Exception as error:
                last_error = error
                if attempt >= max_retries:
                    break
                delay = _backoff_delay(attempt)
                print(
                    f"[arxiv_search] attempt {attempt + 1}/{max_retries + 1} "
                    f"failed ({type(error).__name__}: {error}), "
                    f"retry in {delay}s",
                    file=sys.stderr,
                )
                time.sleep(delay)

        raise last_error  # type: ignore[misc]
