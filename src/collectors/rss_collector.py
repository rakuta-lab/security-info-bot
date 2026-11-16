import hashlib
import logging
from typing import Any

import feedparser
import requests

from src.models import SecurityItem
from src.state import BotState

logger = logging.getLogger(__name__)

USER_AGENT = "SecurityInfoBot/1.0 (+https://github.com/)"
REQUEST_TIMEOUT = 20


def _build_item_id(source_id: str, raw_id: str, url: str) -> str:
    key = raw_id or url
    digest = hashlib.sha256(f"{source_id}:{key}".encode("utf-8")).hexdigest()[:16]
    return f"{source_id}:{digest}"


def fetch_rss_source(source: dict[str, Any], state: BotState) -> list[SecurityItem]:
    """RSS/Atom/RDFフィードを取得してSecurityItemのリストを返す"""
    source_id = source["id"]
    source_name = source["name"]
    url = source["url"]
    category = source.get("category", "howto")

    headers = {"User-Agent": USER_AGENT}
    headers.update(state.get_http_headers(url))

    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("RSS取得エラー [%s]: %s", source_id, exc)
        return []

    if resp.status_code == 304:
        logger.debug("変更なし (304) [%s]", source_id)
        return []

    if resp.status_code >= 400:
        logger.warning("RSS HTTP %s [%s]: %s", resp.status_code, source_id, url)
        return []

    state.update_http_cache(
        url,
        resp.headers.get("ETag"),
        resp.headers.get("Last-Modified"),
    )

    feed = feedparser.parse(resp.content)
    items: list[SecurityItem] = []

    for entry in feed.entries:
        link = entry.get("link", "")
        raw_id = entry.get("id") or link or entry.get("title", "")
        title = (entry.get("title") or "").strip()
        if not title or not link:
            continue

        summary = (
            entry.get("summary")
            or entry.get("description")
            or ""
        )
        if not summary and entry.get("content"):
            summary = entry["content"][0].get("value", "")

        published = (
            entry.get("published")
            or entry.get("updated")
            or entry.get("dc_date")
            or ""
        )

        items.append(
            SecurityItem(
                item_id=_build_item_id(source_id, raw_id, link),
                source_id=source_id,
                source_name=source_name,
                title=title,
                url=link,
                published_at=str(published),
                summary=str(summary),
                category=category,
            )
        )

    return items
