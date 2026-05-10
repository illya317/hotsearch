#!/usr/bin/env python3
"""
Agent entry point.
Outputs AGENTS.md + 24h data context for external AI consumption.

Usage:
    python3 -m hotsearch.agents.main
    python3 -m hotsearch.agents.main --no-prompts
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

import jinja2

from hotsearch.config import prompt_templates

_api = {"base": "http://localhost:3000"}
_jinja_env = jinja2.Environment(loader=jinja2.DictLoader(prompt_templates()))


# 禁用系统代理，避免 localhost 请求被拦截
_proxy_handler = urllib.request.ProxyHandler({})
_url_opener = urllib.request.build_opener(_proxy_handler)
urllib.request.install_opener(_url_opener)


def api_get(path):
    url = f"{_api['base']}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return (
                data.get("data") if isinstance(data, dict) and "data" in data else data
            )
    except urllib.error.HTTPError as e:
        print(f"API error {e.code}: {e.read().decode()}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"API failed: {e}", file=sys.stderr)
        return None


def _to_text(data) -> str:
    """把 API 返回的 dict 转成可读的 JSON 字符串。"""
    if data is None:
        return ""
    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False, indent=2)
    return str(data)


def _daily_feeds(period="24h"):
    return _to_text(api_get(f"/daily?period={period}"))


def _trends_text(platform="hot", limit="10"):
    return _to_text(api_get(f"/hotsearch?platform={platform}&limit={limit}"))


def _ainews_text(source="all", limit="5"):
    return _to_text(api_get(f"/ainews?source={source}&limit={limit}"))


def _github_text(limit="10"):
    return _to_text(api_get(f"/github-trending?limit={limit}"))


def main():
    ap = argparse.ArgumentParser(description="Agent entry point")
    ap.add_argument("--api-base", default=_api["base"], help="API base URL")
    ap.add_argument(
        "--no-prompts", action="store_true", help="Skip prompt files, output data only"
    )
    ap.add_argument(
        "--feeds",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="包含 feeds (默认: True)",
    )
    ap.add_argument(
        "--trends",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="包含热榜 (默认: True)",
    )
    ap.add_argument(
        "--ainews",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="包含 AI 新闻 (默认: True)",
    )
    ap.add_argument(
        "--github",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="包含 GitHub Trending (默认: True)",
    )
    ap.add_argument("--period", default="12h", help="feeds 时间范围 (默认: 12h)")
    ap.add_argument(
        "--trends-platform", default="hot", help="热榜平台或 group (默认: hot)"
    )
    ap.add_argument("--trends-limit", default="10", help="热榜条数 (默认: 10)")
    ap.add_argument("--ainews-source", default="all", help="AI 新闻来源 (默认: all)")
    ap.add_argument("--ainews-limit", default="5", help="AI 新闻条数 (默认: 5)")
    ap.add_argument(
        "--github-limit", default="10", help="GitHub Trending 条数 (默认: 10)"
    )
    args = ap.parse_args()

    _api["base"] = args.api_base

    # 收集各板块内容
    contents = []
    if args.feeds:
        text = _daily_feeds(args.period)
        if text:
            contents.append(text)
    if args.trends:
        text = _trends_text(args.trends_platform, args.trends_limit)
        if text:
            contents.append(text)
    if args.ainews:
        text = _ainews_text(args.ainews_source, args.ainews_limit)
        if text:
            contents.append(text)
    if args.github:
        text = _github_text(args.github_limit)
        if text:
            contents.append(text)

    if args.no_prompts:
        if contents:
            print("\n---\n".join(contents))
        return

    templates = prompt_templates()
    rendered = _jinja_env.get_template("main").render(
        summary=templates.get("summary", ""),
        preference=templates.get("preference", ""),
        search_guide=templates.get("search", ""),
        prune_guide=templates.get("prune", ""),
        template=templates.get("template", ""),
        contents=contents,
    )
    print(rendered)


if __name__ == "__main__":
    main()
