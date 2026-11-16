import json
import logging
import os
from typing import Any

import requests

from src.models import SecurityItem

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)


def _call_gemini(api_key: str, item: SecurityItem) -> tuple[str | None, str | None]:
    prompt = (
        "あなたはセキュリティ情報の解説アシスタントです。\n"
        "以下の情報をもとに、日本語で簡潔に2点だけJSONで返してください。\n"
        "1. summary: 何が起きているか・影響範囲（100〜180文字）\n"
        "2. action: ユーザーが取るべき具体的な対応・回避策（80〜120文字）\n"
        "注意: 元情報にないバージョン番号やCVE番号を推測で書かないでください。\n\n"
        f"情報元: {item.source_name}\n"
        f"タイトル: {item.title}\n"
        f"本文抜粋: {item.summary[:700]}\n"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }

    try:
        resp = requests.post(
            GEMINI_ENDPOINT,
            params={"key": api_key},
            json=payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.warning("Gemini API通信エラー: %s", exc)
        return None, None

    if resp.status_code != 200:
        logger.warning("Gemini API HTTP %s: %s", resp.status_code, resp.text[:200])
        return None, None

    try:
        body = resp.json()
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        summary = str(parsed.get("summary") or "").strip() or None
        action = str(parsed.get("action") or "").strip() or None
        return summary, action
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        logger.warning("Gemini APIレスポンス解析エラー: %s", exc)
        return None, None


def summarize_items(items: list[SecurityItem], rules: dict[str, Any]) -> None:
    """GEMINI_API_KEYがある場合、対象優先度のアイテムを日本語要約する"""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return

    ai_cfg = rules.get("ai_summarize", {})
    target_priorities = set(ai_cfg.get("target_priorities", ["urgent", "high"]))
    max_items = int(ai_cfg.get("max_items_per_run", 10))

    count = 0
    for item in items:
        if count >= max_items:
            break
        if item.priority not in target_priorities:
            continue
        summary, action = _call_gemini(api_key, item)
        if summary:
            item.ai_summary = summary
        if action:
            item.ai_action = action
        count += 1
