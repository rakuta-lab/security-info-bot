import logging
import os

import requests

from src.models import SecurityItem

logger = logging.getLogger(__name__)

LINE_PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"


def build_line_message(items: list[SecurityItem]) -> str:
    """月200通枠を節約するため、緊急通知を1通のテキストにまとめる"""
    lines = [f"🚨 緊急セキュリティ情報（{len(items)}件）"]
    for idx, item in enumerate(items[:8], start=1):
        summary = item.ai_action or item.ai_summary or item.source_name
        lines.append(f"\n{idx}. {item.title}\n{summary[:120]}\n{item.url}")
    if len(items) > 8:
        lines.append(f"\n※他 {len(items) - 8} 件はDiscordをご確認ください。")
    return "\n".join(lines)[:4900]


def send_line_items(items: list[SecurityItem]) -> int:
    """LINE Messaging APIへ緊急通知を1通にまとめて送信する"""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("LINE_USER_ID", "").strip()
    if not token or not user_id or not items:
        return 0

    text = build_line_message(items)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}],
    }

    try:
        resp = requests.post(
            LINE_PUSH_ENDPOINT, headers=headers, json=payload, timeout=15
        )
        if resp.status_code < 400:
            return len(items)
        logger.warning("LINE HTTP %s: %s", resp.status_code, resp.text[:200])
    except requests.RequestException as exc:
        logger.warning("LINE送信エラー: %s", exc)
    return 0
