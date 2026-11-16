import json
from pathlib import Path
from typing import Any

MAX_SEEN_IDS = 5000


class BotState:
    """既読ID、HTTPキャッシュ、日次まとめキューを管理する"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.seen_ids: list[str] = []
        self._seen_set: set[str] = set()
        self.http_cache: dict[str, dict[str, str]] = {}
        self.digest_queue: list[dict[str, Any]] = []
        self.last_digest_date: str = ""

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        self.seen_ids = list(data.get("seen_ids", []))
        self._seen_set = set(self.seen_ids)
        self.http_cache = dict(data.get("http_cache", {}))
        self.digest_queue = list(data.get("digest_queue", []))
        self.last_digest_date = str(data.get("last_digest_date", ""))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        trimmed_seen = self.seen_ids[-MAX_SEEN_IDS:]
        payload = {
            "seen_ids": trimmed_seen,
            "http_cache": self.http_cache,
            "digest_queue": self.digest_queue,
            "last_digest_date": self.last_digest_date,
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def is_seen(self, item_id: str) -> bool:
        return item_id in self._seen_set

    def mark_seen(self, item_id: str) -> None:
        if item_id not in self._seen_set:
            self.seen_ids.append(item_id)
            self._seen_set.add(item_id)

    def get_http_headers(self, url: str) -> dict[str, str]:
        cache = self.http_cache.get(url, {})
        headers: dict[str, str] = {}
        if cache.get("etag"):
            headers["If-None-Match"] = cache["etag"]
        if cache.get("last_modified"):
            headers["If-Modified-Since"] = cache["last_modified"]
        return headers

    def update_http_cache(
        self, url: str, etag: str | None, last_modified: str | None
    ) -> None:
        if not etag and not last_modified:
            return
        entry = self.http_cache.setdefault(url, {})
        if etag:
            entry["etag"] = etag
        if last_modified:
            entry["last_modified"] = last_modified
