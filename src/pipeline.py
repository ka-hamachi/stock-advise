from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.analysis.claude_analyzer import ClaudeAnalyzer
from src.collectors.base import BaseCollector
from src.collectors.ipo_collector import IPOCollector
from src.collectors.newsapi_collector import NewsAPICollector
from src.collectors.rss_collector import RSSCollector
from src.collectors.twitter_collector import TwitterCollector
from src.notifications.slack_notifier import SlackNotifier, build_alert
from src.storage.database import Database

logger = logging.getLogger(__name__)


@dataclass
class RunStats:
    collected: int = 0
    analyzed: int = 0
    alerted: int = 0


def get_collectors(config: dict) -> list[BaseCollector]:
    collectors: list[BaseCollector] = []
    cc = config.get("collectors", {})

    if cc.get("rss", {}).get("enabled"):
        collectors.append(RSSCollector(cc["rss"].get("feeds", [])))

    if cc.get("newsapi", {}).get("enabled"):
        collectors.append(NewsAPICollector(
            api_key=config["secrets"]["newsapi_key"],
            queries=cc["newsapi"].get("queries", []),
            page_size=cc["newsapi"].get("page_size", 20),
        ))

    if cc.get("sec", {}).get("enabled"):
        collectors.append(IPOCollector())

    if cc.get("twitter", {}).get("enabled"):
        collectors.append(TwitterCollector(
            accounts=cc["twitter"].get("accounts", []),
            cashtags=cc["twitter"].get("cashtags", []),
        ))

    return collectors


def run_pipeline(db: Database, config: dict) -> RunStats:
    started_at = datetime.now(timezone.utc)
    stats = RunStats()

    # 鮮度フィルタ: lookback_hours以内のニュースのみ
    lookback_hours = config.get("schedule", {}).get("lookback_hours", 15)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    # 1. Collect
    collectors = get_collectors(config)
    all_items = []
    for collector in collectors:
        try:
            all_items.extend(collector.collect())
        except Exception:
            logger.exception("Collector %s failed", type(collector).__name__)

    # Filter: published_at が cutoff 以降のもの、または published_at が不明なもの(念のため含む)
    fresh_items = []
    for item in all_items:
        if item.published_at is None or item.published_at >= cutoff:
            fresh_items.append(item)

    logger.info("Collected %d items total, %d fresh (within %dh)",
                len(all_items), len(fresh_items), lookback_hours)

    for item in fresh_items:
        if db.insert_raw_item(item):
            stats.collected += 1

    logger.info("Stored %d new items", stats.collected)

    # 2. Analyze
    unprocessed = db.get_unprocessed_items(
        limit=config.get("analysis", {}).get("max_items_per_batch", 50)
    )
    if not unprocessed:
        logger.info("No unprocessed items, skipping analysis")
        db.log_run(started_at, stats.collected, 0, 0)
        return stats

    analyzer = ClaudeAnalyzer(
        api_key=config["secrets"]["anthropic_api_key"],
        model=config.get("analysis", {}).get("claude_model", "claude-sonnet-4-20250514"),
    )
    result = analyzer.analyze(unprocessed, config.get("watchlist"))
    db.mark_processed([item.id for item in unprocessed if item.id])
    stats.analyzed = len(unprocessed)

    logger.info(
        "Analysis complete: %d opportunities found. Market: %s",
        len(result.opportunities),
        result.market_summary,
    )

    # 3. Notify
    notif_cfg = config.get("notifications", {})
    min_confidence = notif_cfg.get("min_confidence", 0.5)
    dedup_hours = notif_cfg.get("dedup_window_hours", 24)

    notifier = SlackNotifier(
        webhook_url=config["secrets"]["slack_webhook_url"],
        webhook_url_urgent=config["secrets"].get("slack_webhook_url_urgent"),
        urgent_threshold=notif_cfg.get("urgent_threshold", 0.80),
    )

    for opp in result.opportunities:
        if opp.confidence < min_confidence:
            continue

        alert = build_alert(opp, unprocessed)

        if db.alert_exists(alert.alert_hash, dedup_hours):
            logger.debug("Duplicate alert suppressed: %s %s", opp.ticker, opp.alert_type)
            continue

        db.insert_alert(alert)
        if notifier.send_alert(alert):
            stats.alerted += 1

    db.log_run(started_at, stats.collected, len(result.opportunities), stats.alerted)
    logger.info("Pipeline complete: %s", stats)
    return stats
