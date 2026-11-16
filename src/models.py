from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SecurityItem:
    """正規化されたセキュリティ情報アイテム"""

    item_id: str
    source_id: str
    source_name: str
    title: str
    url: str
    published_at: str
    summary: str
    category: str
    priority: str = "normal"
    cve_ids: list[str] = field(default_factory=list)
    cvss_score: Optional[float] = None
    ai_summary: Optional[str] = None
    ai_action: Optional[str] = None
    is_browser_update: bool = False

    def to_digest_dict(self) -> dict:
        """日次まとめキュー保存用の辞書表現"""
        return {
            "item_id": self.item_id,
            "source_name": self.source_name,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at,
            "cve_ids": self.cve_ids,
            "cvss_score": self.cvss_score,
        }
