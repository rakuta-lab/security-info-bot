import logging
import os
import time
from typing import Any

import requests

from src.models import SecurityItem

logger = logging.getLogger(__name__)

PRIORITY_COLORS = {
    "urgent": 0xE74C3C,
    "high": 0xE67E22,
    "normal": 0x2ECC71,
    "digest": 0x3498DB,
}

PRIORITY_LABELS = {
    "urgent": "🚨 緊急",
    "high": "⚠️ 重要",
    "normal": "ℹ️ 通常",
    "digest": "📋 日次まとめ",
}

CATEGORY_LABELS = {
    "vulnerability": "脆弱性",
    "advisory": "注意喚起",
    "os_app": "OS・アプリ更新",
    "browser": "ブラウザ更新",
    "outage": "障害情報",
    "howto": "対策・How-to",
}


def _resolve_webhook(item: SecurityItem) -> str:
    default_url = os.environ.get("DISCORD_WEBHOOK_DEFAULT", "").strip()
    if item.priority == "urgent":
        return os.environ.get("DISCORD_WEBHOOK_URGENT", "").strip() or default_url
    env_key = f"DISCORD_WEBHOOK_{item.category.upper()}"
    return os.environ.get(env_key, "").strip() or default_url


def build_discord_embed(item: SecurityItem) -> dict[str, Any]:
    prio_label = PRIORITY_LABELS.get(item.priority, item.priority)
    cat_label = CATEGORY_LABELS.get(item.category, item.category)
    description = item.ai_summary or (item.summary[:350] + ("..." if len(item.summary) > 350 else ""))

    fields: list[dict[str, Any]] = [
        {"name": "情報元", "value": item.source_name, "inline": True},
        {"name": "カテゴリ", "value": cat_label, "inline": True},
    ]
    if item.cvss_score is not None:
        fields.append({"name": "CVSS", "value": str(item.cvss_score), "inline": True})
    if item.cve_ids:
        fields.append(
            {"name": "CVE", "value": ", ".join(item.cve_ids[:5]), "inline": False}
        )
    if item.ai_action:
        fields.append({"name": "推奨対応", "value": item.ai_action, "inline": False})
    if item.is_browser_update:
        fields.append(
            {
                "name": "ブラウザ更新のお願い",
                "value": "ご利用中のブラウザが最新バージョンか確認し、更新を適用してください。",
                "inline": False,
            }
        )

    return {
        "title": f"[{prio_label}] {item.title}"[:250],
        "url": item.url,
        "description": description[:4000] if description else None,
        "color": PRIORITY_COLORS.get(item.priority, 0x95A5A6),
        "fields": fields,
        "footer": {"text": f"公開: {item.published_at}" if item.published_at else "Security Info Bot"},
    }


def _post_webhook(webhook_url: str, payload: dict[str, Any]) -> bool:
    for attempt in range(2):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=15)
        except requests.RequestException as exc:
            logger.warning("Discord送信エラー: %s", exc)
            return False

        if resp.status_code == 429 and attempt == 0:
            retry_after = 2.0
            try:
                retry_after = float(resp.json().get("retry_after", 2.0))
            except ValueError:
                pass
            time.sleep(min(retry_after, 10.0))
            continue

        if resp.status_code >= 400:
            logger.warning("Discord HTTP %s: %s", resp.status_code, resp.text[:200])
            return False
        return True
    return False


def send_discord_items(items: list[SecurityItem]) -> int:
    """アイテムを適切なDiscordチャンネルへ送信し、送信件数を返す"""
    grouped: dict[str, list[dict[str, Any]]] = {}
    skipped = 0
    for item in items:
        webhook_url = _resolve_webhook(item)
        if not webhook_url:
            skipped += 1
            continue
        grouped.setdefault(webhook_url, []).append(build_discord_embed(item))

    if skipped > 0:
        logger.warning(
            "Discord Webhook URLが未設定のため %d件の送信をスキップしました。"
            "GitHub Secrets (DISCORD_WEBHOOK_DEFAULT 等) を確認してください。",
            skipped,
        )

    sent = 0
    for webhook_url, embeds in grouped.items():
        # Discordは1リクエストあたり最大10 embeds
        for i in range(0, len(embeds), 10):
            chunk = embeds[i : i + 10]
            if _post_webhook(webhook_url, {"embeds": chunk}):
                sent += len(chunk)
            time.sleep(0.5)
    return sent


def send_discord_digest(digest_items: list[dict[str, Any]]) -> bool:
    """日次まとめアイテムをDiscordに送信する"""
    webhook_url = (
        os.environ.get("DISCORD_WEBHOOK_DIGEST", "").strip()
        or os.environ.get("DISCORD_WEBHOOK_DEFAULT", "").strip()
    )
    if not digest_items:
        return False
    if not webhook_url:
        logger.warning(
            "DISCORD_WEBHOOK_DIGEST / DISCORD_WEBHOOK_DEFAULT が未設定のため日次まとめをスキップしました。"
        )
        return False

    lines: list[str] = []
    for entry in digest_items:
        cves = f" ({', '.join(entry['cve_ids'][:3])})" if entry.get("cve_ids") else ""
        cvss = f" [CVSS {entry['cvss_score']}]" if entry.get("cvss_score") else ""
        lines.append(f"• [{entry['title']}]({entry['url']}){cves}{cvss} - {entry['source_name']}")

    description = "\n".join(lines)[:4000]
    embed = {
        "title": f"📋 本日のセキュリティ情報まとめ（{len(digest_items)}件）",
        "description": description,
        "color": PRIORITY_COLORS["digest"],
    }
    return _post_webhook(webhook_url, {"embeds": [embed]})
