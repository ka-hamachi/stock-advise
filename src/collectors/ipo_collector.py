from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

from src.storage.models import RawItem
from .base import BaseCollector

logger = logging.getLogger(__name__)

NASDAQ_IPO_URL = "https://www.nasdaq.com/market-activity/ipos"


class IPOCollector(BaseCollector):
    """Scrape upcoming IPO data from Nasdaq's IPO calendar."""

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        try:
            resp = requests.get(
                NASDAQ_IPO_URL,
                headers={"User-Agent": "Mozilla/5.0 (compatible; StockAdvise/1.0)"},
                timeout=15,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for IPO listing tables
            rows = soup.select("table tbody tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    company = cells[0].get_text(strip=True)
                    ticker = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    price_range = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                    title = f"IPO: {company} ({ticker}) - Price Range: {price_range}"
                    items.append(RawItem(
                        source="ipo_calendar",
                        title=title,
                        content=f"Company: {company}, Ticker: {ticker}, Price Range: {price_range}",
                        url=NASDAQ_IPO_URL,
                        content_hash=self.make_hash("ipo", ticker, company),
                    ))
        except Exception:
            logger.exception("IPO calendar scrape failed")

        logger.info("IPO collector found %d items", len(items))
        return items
