import logging
import os
import time

import requests

from src.models import SecurityItem
from src.notifiers.discord import CATEGORY_LABELS, PRIORITY_LABELS

logger = logging.getLogger(__name__)


def send_slack_items(items: list[SecurityItem]) -> int:
    """Slack Incoming Webhookへ送信し、送信件数を返す"""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url or not items:
        return 0

    sent = 0
    for item in items:
        prio = PRIORITY_LABELS.get(item.priority, item.priority)
        cat = CATEGORY_LABELS.get(item.category, item.category)
        body_parts = [f"*{prio}* | {cat} | {item.source_name}", f"<{item.url}|{item.title}>"]
        if item.ai_summary:
            body_parts.append(item.ai_summary)
        elif item.summary:
            body_parts.append(item.summary[:220])
        if item.ai_action:
            body_parts.append(f"*推奨対応:* {item.ai_action}")
        if item.is_browser_update:
            body_parts.append("🔄 ブラウザの最新バージョン確認・更新をおすすめします。")

        try:
            resp = requests.post(
                webhook_url,
                json={"text": "\n".join(body_parts)},
                timeout=15,
            )
            if resp.status_code < 400:
                sent += 1
            else:
                logger.warning("Slack HTTP %s: %s", resp.status_code, resp.text[:200])
        except requests.RequestException as exc:
            logger.warning("Slack送信エラー: %s", exc)
        time.sleep(0.3)

    return sent
