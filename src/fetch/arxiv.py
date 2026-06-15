import feedparser
import urllib.parse
import logging
import re
from datetime import datetime, timedelta
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

from src.fetch.base import BaseFetcher
from src.schemas import Paper
from src.config import AppConfig

logger = logging.getLogger(__name__)
_PUBMED_FIELD_TAG_RE = re.compile(r"\[[^\]]+\]")

# Retry Configuration
RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=10),
    "retry": retry_if_exception_type((requests.RequestException, ConnectionError, TimeoutError))
}

class ArXivFetcher(BaseFetcher):
    @property
    def source_name(self) -> str:
        return "ArXiv"

    @staticmethod
    def _entry_value(entry, key: str):
        if isinstance(entry, dict):
            return entry.get(key)
        if hasattr(entry, "get"):
            try:
                return entry.get(key)
            except Exception:
                pass
        return getattr(entry, key, None)

    @classmethod
    def _entry_doi(cls, entry) -> str | None:
        for key in ("arxiv_doi", "doi"):
            value = cls._entry_value(entry, key)
            if value:
                return str(value).strip() or None
        return None

    @staticmethod
    def _normalize_query(query: str) -> str:
        normalized = _PUBMED_FIELD_TAG_RE.sub("", str(query or ""))
        return " ".join(normalized.split())

    @retry(**RETRY_CONFIG)
    def fetch(self, query: str, max_results: int) -> List[Paper]:
        """ArXiv에서 키워드로 논문 검색"""
        papers: List[Paper] = []
        
        # ArXiv API Query Format: all:keyword
        # Since 'query' comes in as "A OR B", we might need to adjust.
        # But assuming query is "kw1 OR kw2", we can urlencode it.
        # Wait, fetchers.py logic was: " OR ".join([f'all:"{k}"' for k in keywords]) from LIST of keywords.
        # But BaseFetcher.fetch takes a STRING query. 
        # So we expect the caller to pass a pre-formatted query string?
        # Config queries are strings, e.g. '(A OR B) AND C'.
        
        # If the input query is already a complex boolean string (e.g. from PubMed slot config), 
        # passing it directly to ArXiv 'all' might not work perfectly if syntax differs.
        # But for MVP, let's assume we pass it as `search_query=all:{query}` or just `search_query={query}` if it has fields.
        
        # Let's try to just urlencode the raw query.
        encoded_query = urllib.parse.quote(self._normalize_query(query))
        
        url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
        
        logger.debug(f"Fetching ArXiv: {url}")
        feed = feedparser.parse(url)
        
        if hasattr(feed, 'bozo') and feed.bozo:
            logger.warning(f"ArXiv feed parse error: {feed.bozo_exception}")

        for entry in feed.entries:
            try:
                # 날짜 필터링 (최근 7일 이내만 & Backfill day limit check?)
                # We should use config.system.backfill_limit_days
                limit_days = self.config.system.backfill_limit_days
                published_parsed = self._entry_value(entry, "published_parsed")
                if not published_parsed:
                    logger.warning("Skipping ArXiv entry with missing published_parsed")
                    continue
                published = datetime(*published_parsed[:6])
                
                if datetime.now() - published > timedelta(days=limit_days):
                    continue
                
                arxiv_id = entry.link.split("/abs/")[-1]
                pdf_link = entry.link.replace("/abs/", "/pdf/")

                papers.append(Paper(
                    id=arxiv_id,
                    doi=self._entry_doi(entry),
                    title=entry.title.replace("\n", " "),
                    authors=[a.name for a in entry.authors],
                    link=entry.link,
                    published=published.strftime("%Y-%m-%d"),
                    source="ArXiv",
                    summary=entry.summary,
                    pdf_link=pdf_link
                ))
            except Exception as e:
                logger.error(f"Error parsing ArXiv entry: {e}")
                continue
        
        return papers
