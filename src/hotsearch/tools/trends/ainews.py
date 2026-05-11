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

import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
from hotsearch import CACHE_TRENDS_DIR  # noqa: E402
from hotsearch.tools.tag import classify  # noqa: E402

from .base import StandardItem, StandardResult, TrendAdapter  # noqa: E402


class AINewsAdapter(TrendAdapter):
    name = "ainews"
    tags = ["AI", "tech"]

    def normalize(self, raw: dict | list) -> StandardResult:
        assert isinstance(raw, dict)
        ts = raw.get("timestamp", time.time())
        items: list[StandardItem] = []
        for src in raw.get("sources", []):
            for item in src.get("items", []):
                items.append(
                    {
                        "id": None,
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "time": item.get("date", ""),
                        "tags": item.get("tags", []),
                        "summary": item.get("desc", ""),
                        "source_name": src.get("display_name", src.get("source", "")),
                        "timestamp": ts,
                        "raw": item,
                    }
                )
        return {
            "source_name": "AI 新闻",
            "items": items,
            "meta": None,
            "output": None,
        }

    def fetch(self, query: str = "", **kwargs) -> dict:
        source = query or kwargs.get("source", "all")
        limit = int(kwargs.get("limit", 5))

        if source == "all":
            sources = ["decoder", "hn", "techcrunch"]
        elif source in FETCHERS:
            sources = [source]
        else:
            raise ValueError(f"不支持的源: {source}")

        result: dict[str, Any] = {"sources": [], "timestamp": time.time()}
        for s in sources:
            try:
                items = FETCHERS[s](limit)
                tagged = []
                for item in items:
                    copy = dict(item)
                    copy["tags"] = classify(copy.get("title", ""))
                    tagged.append(copy)
                result["sources"].append(
                    {
                        "source": s,
                        "display_name": SOURCES[s],
                        "items": tagged,
                    }
                )
            except Exception as e:
                result["sources"].append(
                    {
                        "source": s,
                        "display_name": SOURCES[s],
                        "items": [],
                        "error": str(e),
                    }
                )
        return result


SOURCES = {
    "decoder": "THE DECODER",
    "hn": "Hacker News AI",
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
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
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
            pub = entry.findtext("atom:published", "", ns) or entry.findtext(
                "atom:updated", "", ns
            )
            desc = strip_html(
                entry.findtext("atom:summary", "", ns)
                or entry.findtext("atom:content", "", ns)
                or ""
            )
            if len(desc) > 120:
                desc = desc[:117] + "..."
            items.append({"title": title, "link": link, "date": pub, "desc": desc})
            if len(items) >= limit:
                break

    return items


def fetch_decoder(limit: int) -> list[dict]:
    return fetch_rss(FEEDS["decoder"], limit)


def fetch_hn(limit: int) -> list[dict]:
    AI_KEYWORDS = re.compile(
        r"\bAI\b|LLM|GPT|Claude|Anthropic|OpenAI|Gemini|agent|model|neural|deep.?learn",
        re.I,
    )
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
    use_json = "--json" in args
    args = [a for a in args if a != "--json"]

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

    if use_json:
        result = {"sources": []}
        for s in sources:
            try:
                items = FETCHERS[s](limit)
                result["sources"].append(
                    {
                        "source": s,
                        "display_name": SOURCES[s],
                        "items": items,
                    }
                )
            except Exception as e:
                result["sources"].append(
                    {
                        "source": s,
                        "display_name": SOURCES[s],
                        "items": [],
                        "error": str(e),
                    }
                )
        CACHE_TRENDS_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        cache_file = CACHE_TRENDS_DIR / f"ainews_{source}_{ts}.json"
        cache_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=False))
    else:
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
