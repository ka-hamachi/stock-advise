from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

from src.storage.models import RawItem
from .base import BaseCollector

logger = logging.getLogger(__name__)

NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
]


class TwitterCollector(BaseCollector):
    """Collect tweets via Nitter (public Twitter mirror, no API key needed).

    Falls back across multiple Nitter instances since they can go down.
    If all instances fail, returns an empty list gracefully.
    """

    def __init__(self, accounts: list[str], cashtags: list[str] | None = None):
        self.accounts = accounts
        self.cashtags = cashtags or []

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        for account in self.accounts:
            items.extend(self._scrape_account(account))
        for tag in self.cashtags:
            items.extend(self._scrape_search(tag))
        logger.info("Twitter collected %d items", len(items))
        return items

    def _scrape_account(self, username: str) -> list[RawItem]:
        for base_url in NITTER_INSTANCES:
            try:
                url = f"{base_url}/{username}"
                resp = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                return self._parse_nitter_page(resp.text, f"twitter:@{username}")
            except Exception:
                logger.debug("Nitter instance %s failed for @%s", base_url, username)
                continue
        logger.warning("All Nitter instances failed for @%s", username)
        return []

    def _scrape_search(self, query: str) -> list[RawItem]:
        for base_url in NITTER_INSTANCES:
            try:
                url = f"{base_url}/search?f=tweets&q={query}"
                resp = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                return self._parse_nitter_page(resp.text, f"twitter:search:{query}")
            except Exception:
                continue
        return []

    def _parse_nitter_page(self, html: str, source: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "html.parser")
        items = []
        for tweet_div in soup.select(".timeline-item .tweet-content"):
            text = tweet_div.get_text(strip=True)
            if not text:
                continue
            items.append(RawItem(
                source=source,
                title=text[:120],
                content=text[:2000],
                url=None,
                content_hash=self.make_hash(source, None, text[:200]),
            ))
        return items[:20]  # Cap per source
