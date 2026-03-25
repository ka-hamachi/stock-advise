from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests

from src.storage.models import RawItem
from .base import BaseCollector

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"


class NewsAPICollector(BaseCollector):
    def __init__(self, api_key: str, queries: list[str], page_size: int = 20):
        self.api_key = api_key
        self.queries = queries
        self.page_size = page_size

    def collect(self) -> list[RawItem]:
        if not self.api_key:
            logger.warning("NewsAPI key not configured, skipping")
            return []

        items: list[RawItem] = []
        from_date = (datetime.now(timezone.utc) - timedelta(hours=15)).strftime("%Y-%m-%dT%H:%M:%S")

        for query in self.queries:
            try:
                resp = requests.get(
                    NEWSAPI_URL,
                    params={
                        "q": query,
                        "from": from_date,
                        "sortBy": "publishedAt",
                        "pageSize": self.page_size,
                        "language": "en",
                        "apiKey": self.api_key,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()

                for article in data.get("articles", []):
                    title = article.get("title", "")
                    url = article.get("url", "")
                    content = article.get("description", "") or ""
                    if article.get("content"):
                        content += "\n" + article["content"]

                    published = None
                    if article.get("publishedAt"):
                        published = datetime.fromisoformat(
                            article["publishedAt"].replace("Z", "+00:00")
                        )

                    items.append(RawItem(
                        source="newsapi",
                        title=title,
                        content=content[:2000] if content else None,
                        url=url or None,
                        published_at=published,
                        content_hash=self.make_hash("newsapi", url, title),
                    ))
            except Exception:
                logger.exception("NewsAPI query failed: %s", query)

        logger.info("NewsAPI collected %d items", len(items))
        return items
