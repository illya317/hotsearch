#!/usr/bin/env python3
"""
Agent entry point.
Outputs AGENTS.md + 24h data context for external AI consumption.

Usage:
    python3 -m hotsearch.agents.main
    python3 -m hotsearch.agents.main --no-agent-doc
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

_api = {"base": "http://localhost:3000"}
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_SUMMARY_MD = _PROMPTS_DIR / "summary.md"
_PREFERENCE_MD = _PROMPTS_DIR / "preference.md"
_SEARCH_MD = _PROMPTS_DIR / "search.md"
_PRUNE_MD = _PROMPTS_DIR / "prune.md"


def _read_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def api_get(path):
    url = f"{_api['base']}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("data") if isinstance(data, dict) and "data" in data else data
    except urllib.error.HTTPError as e:
        print(f"API error {e.code}: {e.read().decode()}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"API failed: {e}", file=sys.stderr)
        return None


def _section(title, items, fmt=None):
    lines = [f"## {title}"]
    if not items:
        lines.append("无更新")
        return lines
    for item in items[:10]:
        lines.append(fmt(item) if fmt else f"- {item}")
    return lines


def _daily_feeds():
    data = api_get("/daily?period=24h")
    if not data:
        return ""
    lines = ["# 24小时数据简报\n"]
    feeds = data.get("feeds", {})

    videos = feeds.get("videos", [])
    lines.extend(_section("视频更新", videos, lambda v: f"- {v['name']}: {v['title']}"))
    lines.append("")

    releases = feeds.get("releases", [])
    lines.extend(_section("开源发布", releases, lambda r: f"- {r['name']}: {r['title']}"))
    lines.append("")

    laws = feeds.get("laws")
    if laws:
        lines.extend(_section("新法速递", [laws], lambda l: f"- 国家法规: {l['count']}条 ({l['time']})"))
        lines.append("")

    laws_sh = feeds.get("laws_shanghai")
    if laws_sh:
        lines.extend(_section("上海法规", [laws_sh], lambda l: f"- 上海法规: {l['count']}条 ({l['time']})"))
        lines.append("")

    return "\n".join(lines)


def _trends_text():
    data = api_get("/hotsearch?platform=hot&limit=10")
    if not data:
        return ""
    lines = ["# 当前热榜\n"]
    for line in data.split("\n")[:15]:
        lines.append(line)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Agent entry point")
    ap.add_argument("--api-base", default=_api["base"], help="API base URL")
    ap.add_argument("--no-prompts", action="store_true", help="Skip prompt files, output data only")
    args = ap.parse_args()

    _api["base"] = args.api_base

    feeds = _daily_feeds()
    trends = _trends_text()

    if not args.no_prompts:
        summary = _read_file(_SUMMARY_MD)
        preference = _read_file(_PREFERENCE_MD)
        search_guide = _read_file(_SEARCH_MD)
        prune_guide = _read_file(_PRUNE_MD)
        if summary:
            print(summary)
        if preference:
            print("\n---\n")
            print(preference)
        if feeds or trends:
            print("\n" + "=" * 40 + "\n")

    if feeds:
        print(feeds)
    if trends:
        if feeds:
            print("\n---\n")
        print(trends)

    if not args.no_prompts:
        if search_guide or prune_guide:
            print("\n" + "=" * 40 + "\n")
        if search_guide:
            print(search_guide)
        if prune_guide:
            if search_guide:
                print("\n---\n")
            print(prune_guide)


if __name__ == "__main__":
    main()
