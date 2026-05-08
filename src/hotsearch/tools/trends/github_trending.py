#!/usr/bin/env python3
"""GitHub 热门项目（过去 30 天新建，按 star 排序）"""

import sys
import json
import urllib.request
from datetime import datetime, timedelta


def fetch_trending(limit=10):
    since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/repositories?q=stars:>500+created:>{since}&sort=stars&order=desc&per_page={limit}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Anya/1.0",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    items = []
    for repo in data.get("items", [])[:limit]:
        items.append({
            "name": repo["full_name"],
            "stars": repo["stargazers_count"],
            "desc": repo.get("description") or "",
            "lang": repo.get("language") or "",
        })
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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    limit = int(args[0]) if args else 10
    try:
        items = fetch_trending(limit)
        print(format_trending(items))
    except Exception as e:
        print(f"获取失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
