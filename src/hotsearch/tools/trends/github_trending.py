#!/usr/bin/env python3
"""GitHub 热门项目（过去 30 天新建，按 star 排序）"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
from hotsearch import CACHE_TRENDS_DIR  # noqa: E402
from hotsearch.tools.tag import classify  # noqa: E402

from .base import StandardItem, StandardResult, TrendAdapter  # noqa: E402


class GitHubTrendingAdapter(TrendAdapter):
    name = "github"
    tags = ["tech", "opensource"]

    def normalize(self, raw: dict | list) -> StandardResult:
        assert isinstance(raw, dict)
        items: list[StandardItem] = []
        for item in raw.get("items", []):
            name = item.get("name", "")
            items.append(
                {
                    "id": name,
                    "title": name,
                    "url": f"https://github.com/{name}" if name else None,
                    "time": None,
                    "tags": item.get("tags", []),
                    "summary": item.get("desc", ""),
                    "source_name": "GitHub",
                    "raw": item,
                }
            )
        return {
            "source_name": "GitHub Trending",
            "items": items,
            "meta": None,
            "output": None,
        }

    def fetch(self, query: str = "", **kwargs) -> dict:
        limit = int(kwargs.get("limit", 10))
        since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        url = f"https://api.github.com/search/repositories?q=stars:>500+created:>{since}&sort=stars&order=desc&per_page={limit}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Anya/1.0",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        items = []
        for repo in data.get("items", [])[:limit]:
            text = f"{repo['full_name']} {repo.get('description') or ''}"
            items.append(
                {
                    "name": repo["full_name"],
                    "stars": repo["stargazers_count"],
                    "desc": repo.get("description") or "",
                    "lang": repo.get("language") or "",
                    "tags": classify(text),
                }
            )
        return {"items": items}


def fetch_trending(limit=10):
    since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/repositories?q=stars:>500+created:>{since}&sort=stars&order=desc&per_page={limit}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Anya/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    items = []
    for repo in data.get("items", [])[:limit]:
        items.append(
            {
                "name": repo["full_name"],
                "stars": repo["stargazers_count"],
                "desc": repo.get("description") or "",
                "lang": repo.get("language") or "",
            }
        )
    return items


def format_trending(items):
    lines = [f"🐙 GitHub Trending TOP {len(items)}", ""]
    for i, item in enumerate(items, 1):
        lang = f" [{item['lang']}]" if item["lang"] else ""
        lines.append(f"{i}. {item['name']} ⭐{item['stars']}{lang}")
        if item["desc"]:
            desc = item["desc"][:80] + ("..." if len(item["desc"]) > 80 else "")
            lines.append(f"   {desc}")
        lines.append("")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    use_json = "--json" in args
    args = [a for a in args if a != "--json" and not a.startswith("--")]
    limit = int(args[0]) if args else 10
    try:
        items = fetch_trending(limit)
        if use_json:
            result = {"items": items}
            CACHE_TRENDS_DIR.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            cache_file = CACHE_TRENDS_DIR / f"github_{ts}.json"
            cache_file.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(format_trending(items))
    except Exception as e:
        print(f"获取失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
