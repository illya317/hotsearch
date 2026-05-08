#!/usr/bin/env python3
"""
Scheduled feeds + push notifications via Feishu.

Cron schedule:
- Every hour: check for new videos (Bilibili) and new releases (OpenClaw/lark-cli) → push only if new
- 8:00: 知乎热搜
- 8:15: 微博热搜
- 8:30: 东方财富
- 8:40: IT之家
- 8:45: AI News
- 15:30: 东方财富 (afternoon)
"""

import os
import subprocess
import sys
from datetime import datetime

from hotsearch import PROJECT_ROOT
from hotsearch.tools.system.feishu_send import send_to_feishu
from hotsearch.tools.search.video_feeds import check_new_videos
from hotsearch.tools.search.release_feeds import check_new_releases


def _run_tool(*args) -> str:
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise Exception(r.stderr.strip() or "tool failed")
    return r.stdout.strip()


def feishu_voice(text):
    if len(text) > 300:
        return
    try:
        subprocess.run(
            ["python3", "-m", "hotsearch.tools.system.feishu_voice",
             "--text", text,
             "--agent", "anya",
             "--receiver", os.environ.get("FS_KOITO_ANYA", "")],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:
        print(f"Voice error: {e}")


COMMANDS = {
    "zhihu":    ["python3", "-m", "hotsearch.tools.search.hotsearch", "zhihu", "5"],
    "weibo":    ["python3", "-m", "hotsearch.tools.search.hotsearch", "weibo", "5"],
    "eastmoney":["python3", "-m", "hotsearch.tools.search.hotsearch", "eastmoney", "5"],
    "ithome":   ["python3", "-m", "hotsearch.tools.search.hotsearch", "ithome", "5"],
    "ainews":   ["python3", "-m", "hotsearch.tools.search.ainews", "decoder", "5"],
    "github":   ["python3", "-m", "hotsearch.tools.search.github_trending", "5"],
}

PLATFORM_NAMES = {
    "zhihu": "知乎热搜", "weibo": "微博热搜", "eastmoney": "东方财富热榜",
    "ithome": "IT之家热榜", "ainews": "AI 新闻", "github": "GitHub Trending",
}


def task_push():
    notifications = []
    notifications.extend(check_new_videos())
    notifications.extend(check_new_releases())
    if notifications:
        msg = "🔔 新内容更新!\n\n" + "\n\n".join(notifications)
        print(msg)
        send_to_feishu(msg)
    else:
        print("No new content")


def task_scheduled(name, content):
    msg = f"⏰ {name}\n\n{content}"
    if len(msg) > 4000:
        msg = msg[:3950] + "\n\n... (截断)"
    print(msg)
    send_to_feishu(msg)


def main():
    now = datetime.now()
    mode = sys.argv[1] if len(sys.argv) > 1 else "push"
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Mode: {mode}")

    if mode == "push":
        task_push()
    elif mode in COMMANDS:
        content = _run_tool(*COMMANDS[mode])
        task_scheduled(PLATFORM_NAMES[mode], content)
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
