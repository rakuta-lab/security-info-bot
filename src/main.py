import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from src.classify import classify_all
from src.collectors.cisa_kev_collector import fetch_cisa_kev
from src.collectors.rss_collector import fetch_rss_source
from src.models import SecurityItem
from src.normalize import normalize_and_dedupe
from src.notifiers.discord import send_discord_digest, send_discord_items
from src.notifiers.line import send_line_items
from src.notifiers.slack import send_slack_items
from src.state import BotState
from src.summarize import summarize_items

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("security_bot")

BASE_DIR = Path(__file__).resolve().parent.parent


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def collect_all(sources: list[dict[str, Any]], state: BotState) -> list[SecurityItem]:
    items: list[SecurityItem] = []
    for src in sources:
        if not src.get("enabled", True):
            continue
        src_type = src.get("type", "rss")
        if src_type == "rss":
            fetched = fetch_rss_source(src, state)
        elif src_type == "cisa_kev":
            fetched = fetch_cisa_kev(src, state)
        else:
            logger.warning("未知のソースタイプ: %s (%s)", src_type, src.get("id"))
            continue
        logger.info("収集 [%s]: %d件", src.get("id"), len(fetched))
        items.extend(fetched)
    return items


def run(args: argparse.Namespace) -> None:
    sources_cfg = load_yaml(BASE_DIR / "config" / "sources.yaml")
    rules_cfg = load_yaml(BASE_DIR / "config" / "rules.yaml")

    state = BotState(BASE_DIR / "state" / "state.json")
    state.load()

    is_first_run = len(state.seen_ids) == 0 and not args.force_notify
    init_only = args.init_only or is_first_run
    if is_first_run:
        logger.info("初回実行のため、既存記事を既読登録のみ行い通知をスキップします。")

    raw_items = collect_all(sources_cfg.get("sources", []), state)
    new_items = normalize_and_dedupe(raw_items, state)
    classified = classify_all(new_items, rules_cfg)
    logger.info("新着アイテム: %d件", len(classified))

    if init_only:
        for item in classified:
            state.mark_seen(item.item_id)
        if not args.dry_run:
            state.save()
        logger.info("既読登録完了: %d件", len(classified))
        return

    digest_items = [i for i in classified if i.priority == "digest"]
    realtime_items = [i for i in classified if i.priority != "digest"]
    logger.info(
        "分類結果: リアルタイム=%d件, 日次まとめ=%d件",
        len(realtime_items),
        len(digest_items),
    )

    if realtime_items and not args.dry_run:
        summarize_items(realtime_items, rules_cfg)

    routing = rules_cfg.get("routing", {})
    discord_targets = [
        i for i in realtime_items if i.priority in set(routing.get("discord", []))
    ]
    slack_targets = [
        i for i in realtime_items if i.priority in set(routing.get("slack", []))
    ]
    line_targets = [
        i for i in realtime_items if i.priority in set(routing.get("line", []))
    ]

    if args.dry_run:
        for item in realtime_items:
            print(
                f"[{item.priority.upper()}][{item.category}] "
                f"{item.title} ({item.source_name}) -> {item.url}"
            )
        print(f"日次まとめキュー追加予定: {len(digest_items)}件")
        return

    if discord_targets:
        sent = send_discord_items(discord_targets)
        logger.info("Discord送信: %d件", sent)
    if slack_targets:
        sent = send_slack_items(slack_targets)
        logger.info("Slack送信: %d件", sent)
    if line_targets:
        sent = send_line_items(line_targets)
        logger.info("LINE送信対象: %d件", sent)

    for item in digest_items:
        state.digest_queue.append(item.to_digest_dict())

    # 日次まとめの送信判定（JST 08:00以降に1日1回送信）
    jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst)
    today_str = now_jst.strftime("%Y-%m-%d")
    digest_cfg = rules_cfg.get("digest", {})
    send_hour_jst = int(digest_cfg.get("send_hour_jst", 8))
    max_digest = int(digest_cfg.get("max_items_per_digest", 30))

    should_send_digest = args.send_digest or (
        now_jst.hour >= send_hour_jst
        and state.last_digest_date != today_str
        and len(state.digest_queue) > 0
    )
    if should_send_digest and state.digest_queue:
        batch = state.digest_queue[:max_digest]
        if send_discord_digest(batch):
            logger.info("日次まとめ送信: %d件", len(batch))
            state.digest_queue = state.digest_queue[max_digest:]
            state.last_digest_date = today_str

    for item in classified:
        state.mark_seen(item.item_id)
    state.save()


def main() -> None:
    parser = argparse.ArgumentParser(description="セキュリティ情報収集・配信Bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="通知を送らず標準出力に表示し、state.jsonも更新しない",
    )
    parser.add_argument(
        "--init-only",
        action="store_true",
        help="既存記事を既読登録のみ行い通知しない",
    )
    parser.add_argument(
        "--force-notify",
        action="store_true",
        help="state.jsonが空でも通知を実行する",
    )
    parser.add_argument(
        "--send-digest",
        action="store_true",
        help="時刻に関わらず日次まとめを即時送信する",
    )
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
