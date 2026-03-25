from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import mktime

import feedparser

from src.storage.models import RawItem
from .base import BaseCollector

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    def __init__(self, feeds: list[dict]):
        self.feeds = feeds  # [{"name": ..., "url": ...}, ...]

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        for feed_cfg in self.feeds:
            try:
                items.extend(self._parse_feed(feed_cfg))
            except Exception:
                logger.exception("Failed to parse feed: %s", feed_cfg.get("name"))
        logger.info("RSS collected %d items from %d feeds", len(items), len(self.feeds))
        return items

    def _parse_feed(self, feed_cfg: dict) -> list[RawItem]:
        parsed = feedparser.parse(feed_cfg["url"])
        items = []
        for entry in parsed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime.fromtimestamp(
                    mktime(entry.published_parsed), tz=timezone.utc
                )

            items.append(RawItem(
                source=f"rss:{feed_cfg['name']}",
                title=title,
                content=summary[:2000] if summary else None,
                url=link or None,
                published_at=published,
                content_hash=self.make_hash("rss", link, title),
            ))
        return items
