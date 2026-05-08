#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
热榜查询脚本
用法: python3 hotsearch.py <平台> [数量]
      python3 hotsearch.py eastmoney 5 --feishu --agent anya --retry 5
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hotsearch import PLATFORMS_CONFIG


def _load_config():
    data = json.loads(PLATFORMS_CONFIG.read_text())
    return data["platforms"], data.get("tab_overrides", {}), data.get("groups", {})


PLATFORMS, TAB_OVERRIDES, GROUPS = _load_config()


def fetch_hotsearch(platform: str, limit: int = 10):
    cfg = PLATFORMS[platform]
    name = cfg["display_name"]
    version = cfg["version"]
    sub_tab = cfg.get("sub_tab")
    needs_page = cfg.get("needs_page", False)

    tab = TAB_OVERRIDES.get(platform, platform)
    params = f"tab={tab}&date_type=now&version={version}"
    if sub_tab:
        params += f"&sub_tab={sub_tab}"
    if needs_page:
        params += "&page=1"

    url = f"https://api.rebang.today/v1/items?{params}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("code") != 200:
        msg = data.get("msg", data.get("message", "未知错误"))
        raise Exception(f"API 返回错误 (code={data.get('code')}): {msg}")

    items = json.loads(data["data"]["list"])
    return items[:limit]


def format_hotsearch(platform: str, items: list) -> str:
    name = PLATFORMS[platform]["display_name"]
    lines = [f"🔥 {name}热榜 TOP {len(items)}", ""]

    for i, item in enumerate(items, 1):
        title = item.get("title", "无标题")
        heat = item.get("heat_str", "")

        label = item.get("label_name", "")
        heat_num = item.get("heat_num", 0)
        label_str = f" [{label}]" if label else ""
        heat_display = f" {heat_num//10000}万" if heat_num >= 10000 else (f" {heat_num}" if heat_num else "")
        lines.append(f"{i}. {title}{label_str}{heat_display}")
        rating = item.get("rating")
        if rating and rating.get("value"):
            lines.append(f"   评分: {rating['value']} ({rating.get('count', 0)}人评价)")
        elif platform == "douban":
            lines.append(f"   评分: 暂无")
        if heat and platform != "zhihu":
            lines.append(f"   热度: {heat}")
        lines.append("")

    return "\n".join(lines)


def list_platforms():
    print("\n支持的平台：\n")
    for key, cfg in sorted(PLATFORMS.items()):
        print(f"  {key:15} - {cfg['display_name']}")
    print()


# --- 主入口 ---

def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        list_platforms()
        sys.exit(0)

    if args[0] in ("-l", "--list"):
        list_platforms()
        sys.exit(0)

    platform = args[0]
    limit = int(args[1]) if len(args) > 1 else 5

    # 收集内容
    if platform in GROUPS:
        platforms = GROUPS[platform]
    elif platform in PLATFORMS:
        platforms = [platform]
    else:
        print(f"不支持的平台: {platform}")
        list_platforms()
        sys.exit(1)

    all_text = []
    for p in platforms:
        try:
            items = fetch_hotsearch(p, limit)
            if items:
                all_text.append(format_hotsearch(p, items))
            else:
                all_text.append(f"⚠️ {PLATFORMS[p]['display_name']}: 未获取到数据\n")
        except Exception as e:
            all_text.append(f"⚠️ {PLATFORMS[p]['display_name']}: {e}\n")

    output = "\n".join(all_text).strip()
    print(output)


if __name__ == "__main__":
    main()
