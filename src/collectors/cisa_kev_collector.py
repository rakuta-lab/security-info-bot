import logging
from typing import Any

import requests

from src.models import SecurityItem
from src.state import BotState

logger = logging.getLogger(__name__)

USER_AGENT = "SecurityInfoBot/1.0 (+https://github.com/)"
REQUEST_TIMEOUT = 25


def fetch_cisa_kev(source: dict[str, Any], state: BotState) -> list[SecurityItem]:
    """CISA Known Exploited Vulnerabilities JSONを取得する"""
    source_id = source["id"]
    source_name = source["name"]
    url = source["url"]
    category = source.get("category", "vulnerability")

    headers = {"User-Agent": USER_AGENT}
    headers.update(state.get_http_headers(url))

    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("CISA KEV取得エラー: %s", exc)
        return []

    if resp.status_code == 304:
        logger.debug("CISA KEV変更なし (304)")
        return []

    if resp.status_code >= 400:
        logger.warning("CISA KEV HTTP %s", resp.status_code)
        return []

    state.update_http_cache(
        url,
        resp.headers.get("ETag"),
        resp.headers.get("Last-Modified"),
    )

    try:
        data = resp.json()
    except ValueError as exc:
        logger.warning("CISA KEV JSONパースエラー: %s", exc)
        return []

    vulnerabilities = data.get("vulnerabilities", [])
    items: list[SecurityItem] = []

    # 新しい順に処理しやすいよう末尾（最新追加分）から取得
    for vuln in vulnerabilities[-100:]:
        cve_id = vuln.get("cveID", "")
        if not cve_id:
            continue
        vendor = vuln.get("vendorProject", "")
        product = vuln.get("product", "")
        vuln_name = vuln.get("vulnerabilityName", "")
        short_desc = vuln.get("shortDescription", "")
        required_action = vuln.get("requiredAction", "")
        date_added = vuln.get("dateAdded", "")
        due_date = vuln.get("dueDate", "")

        title = f"[{cve_id}] {vendor} {product}: {vuln_name}".strip()
        summary = (
            f"{short_desc}\n"
            f"推奨対応: {required_action} (対応期限: {due_date})"
        ).strip()
        nvd_url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"

        items.append(
            SecurityItem(
                item_id=f"{source_id}:{cve_id}",
                source_id=source_id,
                source_name=source_name,
                title=title,
                url=nvd_url,
                published_at=date_added,
                summary=summary,
                category=category,
                cve_ids=[cve_id],
            )
        )

    return items
