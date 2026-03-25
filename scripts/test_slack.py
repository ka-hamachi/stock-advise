#!/usr/bin/env python3
"""Send a test Slack alert to verify webhook configuration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.notifications.slack_notifier import SlackNotifier
from src.storage.models import Alert


def main():
    config = load_config()
    webhook = config["secrets"]["slack_webhook_url"]
    if not webhook:
        print("ERROR: SLACK_WEBHOOK_URL not set in .env")
        sys.exit(1)

    notifier = SlackNotifier(webhook_url=webhook)
    alert = Alert(
        ticker="TEST",
        alert_type="general_insight",
        confidence=0.75,
        urgency="standard",
        reasoning="This is a test alert to verify Slack integration is working correctly.\n\n*Suggestion:* No action needed.\n*Time:* N/A",
        source_urls=["https://example.com"],
        alert_hash="test",
    )
    success = notifier.send_alert(alert)
    print("Test alert sent!" if success else "Failed to send test alert.")


if __name__ == "__main__":
    main()
