import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    load_dotenv(BASE_DIR / ".env")
    config_path = BASE_DIR / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["secrets"] = {
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "newsapi_key": os.environ.get("NEWSAPI_KEY", ""),
        "slack_webhook_url": os.environ.get("SLACK_WEBHOOK_URL", ""),
        "slack_webhook_url_urgent": os.environ.get("SLACK_WEBHOOK_URL_URGENT", ""),
    }
    return cfg
