from __future__ import annotations

import hashlib
import logging

from slack_sdk.webhook import WebhookClient

from src.analysis.models import StockOpportunity
from src.storage.database import Database
from src.storage.models import Alert

logger = logging.getLogger(__name__)


class SlackNotifier:
    def __init__(
        self,
        webhook_url: str,
        webhook_url_urgent: str | None = None,
        urgent_threshold: float = 0.80,
    ):
        self.client = WebhookClient(webhook_url)
        self.client_urgent = (
            WebhookClient(webhook_url_urgent) if webhook_url_urgent else self.client
        )
        self.urgent_threshold = urgent_threshold

    def send_alert(self, alert: Alert) -> bool:
        client = (
            self.client_urgent
            if alert.confidence >= self.urgent_threshold
            else self.client
        )

        urgency_emoji = {"urgent": ":rotating_light:", "standard": ":chart_with_upwards_trend:", "low": ":eyes:"}
        emoji = urgency_emoji.get(alert.urgency, ":memo:")

        ticker_display = f"${alert.ticker}" if alert.ticker else "マーケット情報"
        conf_pct = int(alert.confidence * 100)

        urgency_label = {"urgent": "緊急", "standard": "通常", "low": "参考"}
        alert_type_label = {
            "upcoming_ipo": "IPO関連",
            "policy_announcement": "政策発表",
            "sector_rotation": "セクターローテーション",
            "basket_buying": "バスケット買い",
            "earnings_catalyst": "決算カタリスト",
            "general_insight": "総合分析",
        }

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} [{urgency_label.get(alert.urgency, alert.urgency)}] {ticker_display}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*種別:* {alert_type_label.get(alert.alert_type, alert.alert_type)}"},
                    {"type": "mrkdwn", "text": f"*信頼度:* {conf_pct}%"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*分析:*\n{alert.reasoning}"},
            },
        ]

        if alert.source_urls:
            source_links = "\n".join(f"- <{url}>" for url in alert.source_urls[:5])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*ソース:*\n{source_links}"},
            })

        blocks.append({"type": "divider"})

        try:
            resp = client.send(blocks=blocks)
            if resp.status_code == 200:
                logger.info("Slack alert sent: %s", ticker_display)
                return True
            else:
                logger.error("Slack send failed: %s", resp.body)
                return False
        except Exception:
            logger.exception("Slack send error")
            return False


def build_alert(
    opp: StockOpportunity,
    raw_items: list,
) -> Alert:
    source_urls = [item.url for item in raw_items if item.url][:5]
    raw_ids = [item.id for item in raw_items if item.id]

    # Dedup hash: same ticker + type + date = same alert
    from datetime import date
    hash_input = f"{opp.ticker}:{opp.alert_type}:{date.today().isoformat()}"
    alert_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    return Alert(
        ticker=opp.ticker,
        alert_type=opp.alert_type,
        confidence=opp.confidence,
        urgency=opp.urgency,
        reasoning=f"{opp.reasoning}\n\n*アクション:* {opp.action_suggestion}\n*期限:* {opp.time_sensitivity}",
        source_urls=source_urls,
        raw_item_ids=raw_ids,
        alert_hash=alert_hash,
    )
