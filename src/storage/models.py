from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawItem:
    source: str
    title: str
    content: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    collected_at: datetime | None = None
    content_hash: str = ""
    processed: bool = False
    id: int | None = None


@dataclass
class Alert:
    ticker: str | None
    alert_type: str
    confidence: float
    urgency: str
    reasoning: str
    source_urls: list[str] = field(default_factory=list)
    raw_item_ids: list[int] = field(default_factory=list)
    alert_hash: str = ""
    created_at: datetime | None = None
    sent_to_slack: bool = False
    id: int | None = None
