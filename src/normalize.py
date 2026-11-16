import html
import re
from typing import Optional

from src.models import SecurityItem
from src.state import BotState

CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"[ \t\r\f\v]+")
CVSS_PATTERN = re.compile(
    r"(?:cvss(?:\s*v?\d(?:\.\d)?)?(?:\s*base\s*score)?|基本値)\s*[:：]?\s*(\d{1,2}\.\d)",
    re.IGNORECASE,
)


def strip_html(text: str) -> str:
    """HTMLタグを除去して整形する"""
    if not text:
        return ""
    unescaped = html.unescape(text)
    no_tags = HTML_TAG_PATTERN.sub(" ", unescaped)
    lines = [WHITESPACE_PATTERN.sub(" ", line).strip() for line in no_tags.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned[:1000]


def extract_cves(text: str) -> list[str]:
    """テキストから重複なしのCVE IDリストを抽出する"""
    found = CVE_PATTERN.findall(text)
    seen: set[str] = set()
    result: list[str] = []
    for cve in found:
        upper = cve.upper()
        if upper not in seen:
            seen.add(upper)
            result.append(upper)
    return result


def extract_cvss(text: str) -> Optional[float]:
    """テキストからCVSSスコアを抽出する"""
    match = CVSS_PATTERN.search(text)
    if not match:
        return None
    try:
        score = float(match.group(1))
        if 0.0 <= score <= 10.0:
            return score
    except ValueError:
        return None
    return None


def normalize_and_dedupe(
    items: list[SecurityItem], state: BotState
) -> list[SecurityItem]:
    """テキスト整形・CVE/CVSS抽出・既読およびURL重複の排除を行う"""
    unique_items: list[SecurityItem] = []
    batch_urls: set[str] = set()

    for item in items:
        if state.is_seen(item.item_id):
            continue

        norm_url = item.url.strip().rstrip("/")
        if norm_url in batch_urls:
            continue
        batch_urls.add(norm_url)

        item.summary = strip_html(item.summary)
        combined = f"{item.title}\n{item.summary}"

        if not item.cve_ids:
            item.cve_ids = extract_cves(combined)
        if item.cvss_score is None:
            item.cvss_score = extract_cvss(combined)

        unique_items.append(item)

    return unique_items
