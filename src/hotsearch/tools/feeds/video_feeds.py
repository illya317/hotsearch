#!/usr/bin/env python3
"""
Video feed tracker — Bilibili RSS via RSSHub.
Usage:
    python3 video_feeds.py                  # list latest videos from all feeds
    python3 video_feeds.py --check-new      # compare with state, output new only
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
from hotsearch import CACHE_FEEDS_DIR  # noqa: E402

from hotsearch.tools.base import StandardItem, StandardResult  # noqa: E402
from hotsearch.tools.feeds import FeedAdapter  # noqa: E402
from hotsearch.tools.tag import classify  # noqa: E402

CACHE_FEEDS_DIR.mkdir(parents=True, exist_ok=True)
RSSHUB = os.environ.get("RSSHUB", "http://localhost:1200")
STATE_FILE = CACHE_FEEDS_DIR / "video_state.json"


class VideoFeedsAdapter(FeedAdapter):
    name = "videos"
    display_name = "视频频道"
    tags = ["视频", "娱乐"]
    state_file = "video_state.json"

    def get_status(self) -> list[dict]:
        state = load_state().get("videos", {})
        results = []
        for name, url in VIDEO_FEEDS:
            check_url = url.replace("limit=3", "limit=1")
            data = fetch_url(check_url)
            stored_title = state.get(name, {}).get("title", "")
            if data.startswith("Error"):
                status = "❌"
                current_title = "(获取失败)"
            else:
                item = parse_latest_item(data)
                if item:
                    current_title = item["title"]
                    status = "✅已最新" if current_title == stored_title else "🆕有更新"
                else:
                    current_title = "(解析失败)"
                    status = "❌"
            title = current_title[:40] + "..." if len(current_title) > 40 else current_title
            results.append({
                "name": name,
                "title": title,
                "summary": "",
                "status": status,
                "timestamp": state.get(name, {}).get("timestamp", 0),
            })
        return results

    def get_daily_items(self, threshold: float) -> list[dict]:
        state = load_state().get("videos", {})
        recent = []
        for name, val in state.items():
            if isinstance(val, dict) and val.get("timestamp", 0) >= threshold:
                recent.append({
                    "name": name,
                    "title": val.get("title", ""),
                    "summary": "",
                    "time": val.get("time", ""),
                    "timestamp": val.get("timestamp", 0),
                })
        return recent

    def normalize(self, raw: dict | list) -> StandardResult:
        assert isinstance(raw, dict)
        ts = raw.get("timestamp", time.time())
        items: list[StandardItem] = []
        for section in raw.get("videos", []):
            for entry in section.get("titles", []):
                if isinstance(entry, dict):
                    title = entry.get("title", "")
                    tags = entry.get("tags", [])
                else:
                    title = str(entry).lstrip(" •")
                    tags = []
                if not tags:
                    tags = classify(title)
                items.append(
                    {
                        "id": None,
                        "title": title,
                        "url": None,
                        "time": None,
                        "tags": tags,
                        "summary": None,
                        "source_name": section.get("name", ""),
                        "timestamp": ts,
                        "raw": {"name": section.get("name"), "title": title},
                    }
                )
        return {
            "source_name": "视频更新",
            "items": items,
            "meta": None,
            "output": None,
        }

    def fetch(self, query: str = "", **kwargs) -> dict:
        sections = []
        for name, url in VIDEO_FEEDS:
            data = fetch_url(url)
            if not data.startswith("Error"):
                titles = parse_rss_titles(data, 2)
                if titles:
                    sections.append({"name": name, "titles": titles})
        return {"videos": sections, "timestamp": time.time()}

    def check_new(self) -> list[str]:
        return check_new_videos()


VIDEO_FEEDS = [
    ("军武志", f"{RSSHUB}/bilibili/user/video/435931665?limit=3"),
    ("麻薯波比呀", f"{RSSHUB}/bilibili/user/video/703186600?limit=3"),
    ("河畔的伯爵", f"{RSSHUB}/bilibili/user/video/1596926736?limit=3"),
    ("空山猎人", f"{RSSHUB}/bilibili/user/video/3493108557809994?limit=3"),
    ("小约翰可汗", f"{RSSHUB}/bilibili/user/video/23947287?limit=3"),
    ("军情巴朗", f"{RSSHUB}/bilibili/user/video/1975692083?limit=3"),
]


def fetch_url(url: str, timeout: int = 15) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Anya/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        return f"Error: {e}"


def parse_latest_item(xml_text: str) -> dict | None:
    try:
        root = ET.fromstring(xml_text)
        item = root.find(".//item")
        if item is not None:
            return {
                "title": item.findtext("title", ""),
                "link": item.findtext("link", ""),
            }
    except Exception:
        pass
    return None


def parse_rss_titles(xml_text: str, limit: int = 3) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
        titles = []
        for item in root.findall(".//item"):
            t = item.findtext("title", "")
            if t:
                titles.append(f"  • {t}")
                if len(titles) >= limit:
                    break
        return titles
    except Exception:
        return ["  • (parse error)"]


def load_state() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text())
        # Migrate old format:
        # {"videos": {"name": "title"}} ->
        # {"videos": {"name": {"title": "...", "updated_at": "..."}}}}
        videos = data.get("videos", {})
        migrated = {}
        for name, val in videos.items():
            if isinstance(val, str):
                migrated[name] = {
                    "title": val,
                    "time": "1970-01-01 00:00",
                    "timestamp": 0,
                }
            else:
                migrated[name] = val
        return {"videos": migrated}
    except Exception:
        return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def get_videos() -> str:
    """Return formatted video list from all feeds."""
    sections = ["📺 视频更新"]
    for name, url in VIDEO_FEEDS:
        data = fetch_url(url)
        if not data.startswith("Error"):
            titles = parse_rss_titles(data, 2)
            if titles:
                sections.append(f"\n【{name}】")
                sections.extend(titles)
    return "\n".join(sections)


def check_new_videos() -> list[dict]:
    """Check for new videos, update state, return structured new items."""
    state = load_state()
    videos = state.get("videos", {})
    new_items = []
    now = datetime.now()
    for name, url in VIDEO_FEEDS:
        check_url = url.replace("limit=3", "limit=1")
        data = fetch_url(check_url)
        if data.startswith("Error"):
            continue
        item = parse_latest_item(data)
        current_title = videos.get(name, {}).get("title")
        if item and item["title"] != current_title:
            new_items.append({
                "title": item["title"],
                "summary": name,
                "timestamp": time.time(),
                "name": name,
            })
            videos[name] = {
                "title": item["title"],
                "time": now.strftime("%Y-%m-%d %H:%M"),
                "timestamp": time.time(),
            }
    state["videos"] = videos
    save_state(state)
    return new_items


def main():
    parser = argparse.ArgumentParser(description="Video feed tracker")
    parser.add_argument(
        "--check-new", action="store_true", help="Check for new videos only"
    )
    args = parser.parse_args()

    if args.check_new:
        new_items = check_new_videos()
        if new_items:
            for item in new_items:
                print(f"📺 {item['summary']}: {item['title']}")
        else:
            print("No new videos")
    else:
        print(get_videos())


if __name__ == "__main__":
    main()
