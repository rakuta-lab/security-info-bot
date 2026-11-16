from typing import Any

from src.models import SecurityItem


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in keywords)


def classify_item(item: SecurityItem, rules: dict[str, Any]) -> SecurityItem:
    """ルールに基づいてカテゴリ調整・優先度判定・ブラウザ更新フラグ設定を行う"""
    combined = f"{item.title}\n{item.summary}"

    # 二次情報（howto）などはキーワードで適切なカテゴリへ再分類する
    if item.category == "howto":
        recat = rules.get("recategorize_keywords", {})
        for target_cat, keywords in recat.items():
            if _contains_any(combined, keywords):
                item.category = target_cat
                break

    # ブラウザの更新促しフラグ
    if item.category == "browser" and _contains_any(
        combined, ["update", "release", "stable", "security", "アップデート", "更新"]
    ):
        item.is_browser_update = True

    prio_rules = rules.get("priority_rules", {})
    urgent_sources = set(prio_rules.get("urgent_sources", []))
    urgent_keywords = prio_rules.get("urgent_keywords", [])
    high_keywords = prio_rules.get("high_keywords", [])
    cvss_urgent = float(prio_rules.get("cvss_urgent_threshold", 9.0))
    cvss_high = float(prio_rules.get("cvss_high_threshold", 7.0))
    digest_cats = set(prio_rules.get("digest_categories", []))

    if (
        item.source_id in urgent_sources
        or (item.cvss_score is not None and item.cvss_score >= cvss_urgent)
        or _contains_any(combined, urgent_keywords)
    ):
        item.priority = "urgent"
    elif (
        (item.cvss_score is not None and item.cvss_score >= cvss_high)
        or item.category in ("browser", "os_app", "advisory")
        or _contains_any(combined, high_keywords)
    ):
        item.priority = "high"
    elif item.category in digest_cats:
        item.priority = "digest"
    else:
        item.priority = "normal"

    return item


def classify_all(
    items: list[SecurityItem], rules: dict[str, Any]
) -> list[SecurityItem]:
    return [classify_item(item, rules) for item in items]
