import tempfile
import unittest
from pathlib import Path

from src.classify import classify_item
from src.models import SecurityItem
from src.normalize import extract_cves, extract_cvss, normalize_and_dedupe, strip_html
from src.notifiers.discord import build_discord_embed
from src.notifiers.line import build_line_message
from src.state import BotState


SAMPLE_RULES = {
    "priority_rules": {
        "urgent_sources": ["cisa_kev", "jpcert"],
        "urgent_keywords": ["緊急", "zero-day"],
        "high_keywords": ["security update", "脆弱性"],
        "cvss_urgent_threshold": 9.0,
        "cvss_high_threshold": 7.0,
        "digest_categories": ["vulnerability"],
    },
    "recategorize_keywords": {
        "browser": ["chrome", "firefox"],
        "outage": ["outage", "障害"],
    },
}


class TestPipeline(unittest.TestCase):
    def test_strip_html_and_extractors(self) -> None:
        raw = "<p>Details for <b>CVE-2026-1234</b> and cve-2026-1234. CVSS v3: 9.8</p>"
        cleaned = strip_html(raw)
        self.assertEqual(cleaned, "Details for CVE-2026-1234 and cve-2026-1234. CVSS v3: 9.8")
        self.assertEqual(extract_cves(cleaned), ["CVE-2026-1234"])
        self.assertEqual(extract_cvss(cleaned), 9.8)

    def test_normalize_and_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = BotState(Path(tmp) / "state.json")
            state.mark_seen("already_seen")

            items = [
                SecurityItem("already_seen", "jvn", "JVN", "Old", "https://a.example", "", "", "vulnerability"),
                SecurityItem("new1", "jvn", "JVN", "New CVE-2026-9999", "https://b.example/", "", "CVSS: 7.5", "vulnerability"),
                SecurityItem("new2", "jvn2", "JVN2", "Dup URL", "https://b.example", "", "", "vulnerability"),
            ]
            result = normalize_and_dedupe(items, state)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].item_id, "new1")
            self.assertEqual(result[0].cve_ids, ["CVE-2026-9999"])
            self.assertEqual(result[0].cvss_score, 7.5)

    def test_classify_priorities_and_browser_flag(self) -> None:
        kev = SecurityItem("1", "cisa_kev", "KEV", "Test", "https://ex", "", "", "vulnerability")
        self.assertEqual(classify_item(kev, SAMPLE_RULES).priority, "urgent")

        chrome = SecurityItem("2", "chrome_releases", "Chrome", "Stable Channel Update for Desktop", "https://ex2", "", "Security fixes", "browser")
        classified_chrome = classify_item(chrome, SAMPLE_RULES)
        self.assertEqual(classified_chrome.priority, "high")
        self.assertTrue(classified_chrome.is_browser_update)

        low_vuln = SecurityItem("3", "jvn_new", "JVN", "Minor issue", "https://ex3", "", "info", "vulnerability", cvss_score=4.3)
        self.assertEqual(classify_item(low_vuln, SAMPLE_RULES).priority, "digest")

    def test_state_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = BotState(path)
            state.mark_seen("id1")
            state.update_http_cache("https://example.com/rss", '"etag1"', "Mon, 01 Jan 2026 00:00:00 GMT")
            state.save()

            loaded = BotState(path)
            loaded.load()
            self.assertTrue(loaded.is_seen("id1"))
            headers = loaded.get_http_headers("https://example.com/rss")
            self.assertEqual(headers["If-None-Match"], '"etag1"')

    def test_notifiers_format(self) -> None:
        item = SecurityItem(
            "1", "chrome_releases", "Chrome", "Chrome Update", "https://chrome.example",
            "2026-11-16", "Fix", "browser", priority="high", is_browser_update=True,
        )
        embed = build_discord_embed(item)
        self.assertIn("Chrome Update", embed["title"])
        self.assertTrue(any(f["name"] == "ブラウザ更新のお願い" for f in embed["fields"]))

        line_msg = build_line_message([item])
        self.assertIn("緊急セキュリティ情報（1件）", line_msg)
        self.assertIn("https://chrome.example", line_msg)


if __name__ == "__main__":
    unittest.main()
