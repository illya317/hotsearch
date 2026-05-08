#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
AI 新闻聚合脚本
用法: python3 ainews.py [源] [数量]
      python3 ainews.py all 5
      python3 ainews.py all 5 --feishu          # 发飞书（自动检测 agent）
      python3 ainews.py all 5 --feishu --agent anya --retry 5
"""

import sys
import json
import os
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
import re

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

SOURCES = {
    "decoder":    "THE DECODER",
    "hn":         "Hacker News AI",
    "techcrunch": "TechCrunch AI",
}

FEEDS = {
    "decoder": "https://the-decoder.com/feed/",
    "hn": "https://news.ycombinator.com/rss",
}

TECHCRUNCH_URL = "https://techcrunch.com/category/artificial-intelligence/feed/"


def strip_html(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_rss(url: str, limit: int) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read().decode("utf-8")

    root = ET.fromstring(data)

    items = []
    for item in root.findall(".//item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        pub = item.findtext("pubDate", "")
        desc = strip_html(item.findtext("description", ""))
        if len(desc) > 120:
            desc = desc[:117] + "..."
        items.append({"title": title, "link": link, "date": pub, "desc": desc})
        if len(items) >= limit:
            break

    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", ns):
            title = entry.findtext("atom:title", "", ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            pub = entry.findtext("atom:published", "", ns) or entry.findtext("atom:updated", "", ns)
            desc = strip_html(entry.findtext("atom:summary", "", ns) or entry.findtext("atom:content", "", ns) or "")
            if len(desc) > 120:
                desc = desc[:117] + "..."
            items.append({"title": title, "link": link, "date": pub, "desc": desc})
            if len(items) >= limit:
                break

    return items


def fetch_decoder(limit: int) -> list[dict]:
    return fetch_rss(FEEDS["decoder"], limit)


def fetch_hn(limit: int) -> list[dict]:
    AI_KEYWORDS = re.compile(r"\bAI\b|LLM|GPT|Claude|Anthropic|OpenAI|Gemini|agent|model|neural|deep.?learn", re.I)
    all_items = fetch_rss(FEEDS["hn"], 80)
    filtered = [item for item in all_items if AI_KEYWORDS.search(item["title"])]
    return filtered[:limit]


def fetch_techcrunch(limit: int) -> list[dict]:
    return fetch_rss(TECHCRUNCH_URL, limit)


FETCHERS = {
    "decoder": fetch_decoder,
    "hn": fetch_hn,
    "techcrunch": fetch_techcrunch,
}


# --- 格式化 ---

def format_text(source: str, items: list[dict]) -> str:
    name = SOURCES[source]
    lines = [f"🤖 {name} TOP {len(items)}", ""]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item['title']}")
        if item["desc"]:
            lines.append(f"   {item['desc']}")
        lines.append("")
    return "\n".join(lines)


def display(source: str, items: list[dict]):
    print(format_text(source, items))


def list_sources():
    print("\n支持的源：\n")
    for key, name in sorted(SOURCES.items()):
        print(f"  {key:15} - {name}")
    print(f"  {'all':15} - 全部")
    print()


# --- 主入口 ---

def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        list_sources()
        sys.exit(0)

    if args[0] in ("-l", "--list"):
        list_sources()
        sys.exit(0)

    source = args[0]
    limit = int(args[1]) if len(args) > 1 else 5

    if source == "all":
        sources = ["decoder", "hn", "techcrunch"]
    elif source in FETCHERS:
        sources = [source]
    else:
        print(f"不支持的源: {source}")
        list_sources()
        sys.exit(1)

    # 收集内容
    all_text = []
    for s in sources:
        try:
            items = FETCHERS[s](limit)
            if items:
                all_text.append(format_text(s, items))
            else:
                all_text.append(f"⚠️ {SOURCES[s]}: 未获取到数据\n")
        except Exception as e:
            all_text.append(f"⚠️ {SOURCES[s]}: {e}\n")

    output = "\n".join(all_text).strip()
    print(output)


if __name__ == "__main__":
    main()
