#!/usr/bin/env python3
"""
GitHub Release feed tracker — Atom feed parsing.
Usage:
    python3 release_feeds.py                  # list latest releases
    python3 release_feeds.py --check-new      # compare with state, output new only
"""

import argparse
import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
from hotsearch import CACHE_FEEDS_DIR

CACHE_FEEDS_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = CACHE_FEEDS_DIR / "release_state.json"

RELEASE_FEEDS = {
    "OpenClaw": "https://github.com/openclaw/openclaw/releases.atom",
    "lark-cli": "https://github.com/larksuite/cli/releases.atom",
}


def fetch_url(url: str, timeout: int = 15) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Anya/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        return f"Error: {e}"


def get_latest_release(atom_url: str) -> dict | None:
    data = fetch_url(atom_url)
    if data.startswith("Error"):
        return None
    try:
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", ns)
        if entry is not None:
            title = entry.findtext("atom:title", "", ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            return {"title": title, "link": link}
    except Exception:
        pass
    return None


def load_state() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text())
        # Migrate old format: {"releases": {"name": "title"}} -> {"releases": {"name": {"title": "...", "updated_at": "..."}}}
        releases = data.get("releases", {})
        migrated = {}
        for name, val in releases.items():
            if isinstance(val, str):
                migrated[name] = {"title": val, "time": "1970-01-01 00:00", "timestamp": 0}
            else:
                migrated[name] = val
        return {"releases": migrated}
    except Exception:
        return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def get_releases() -> str:
    """Return formatted release list."""
    lines = ["📦 软件仓库"]
    for name, url in RELEASE_FEEDS.items():
        release = get_latest_release(url)
        if release:
            lines.append(f"  • {name}: {release['title']}")
        else:
            lines.append(f"  • {name}: (获取失败)")
    return "\n".join(lines)


def check_new_releases() -> list[str]:
    """Check for new releases, update state, return formatted new items."""
    state = load_state()
    releases = state.get("releases", {})
    new_items = []
    now = datetime.now()
    for name, url in RELEASE_FEEDS.items():
        release = get_latest_release(url)
        current_title = releases.get(name, {}).get("title")
        if release and release["title"] != current_title:
            new_items.append(f"📦 {name}: {release['title']}")
            releases[name] = {
                "title": release["title"],
                "time": now.strftime("%Y-%m-%d %H:%M"),
                "timestamp": time.time(),
            }
    state["releases"] = releases
    save_state(state)
    return new_items


def main():
    parser = argparse.ArgumentParser(description="GitHub Release feed tracker")
    parser.add_argument("--check-new", action="store_true", help="Check for new releases only")
    args = parser.parse_args()

    if args.check_new:
        new_items = check_new_releases()
        if new_items:
            print("\n".join(new_items))
        else:
            print("No new releases")
    else:
        print(get_releases())


if __name__ == "__main__":
    main()
